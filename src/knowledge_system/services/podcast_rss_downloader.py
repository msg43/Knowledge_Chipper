#!/usr/bin/env python3
"""
Podcast RSS Downloader

Downloads audio files from podcast RSS feeds with deterministic source_id generation.
Matches specific episodes to YouTube videos for selective downloading.
"""

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from tqdm import tqdm

from ..database.service import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)

try:
    import feedparser

    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logger.warning("feedparser not available. Podcast RSS downloading will not work.")


class PodcastRSSDownloader:
    """
    Downloads audio files from podcast RSS feeds.

    Features:
    - Parses podcast RSS feeds for audio enclosures
    - Matches episodes to YouTube videos by title/date
    - Generates deterministic source_ids for episodes
    - Downloads audio directly from podcast CDN (no rate limiting)
    - Stores source metadata in database
    """

    def __init__(self, db_service: DatabaseService | None = None):
        """
        Initialize downloader.

        Args:
            db_service: Database service for storing source metadata
        """
        if not FEEDPARSER_AVAILABLE:
            raise ImportError(
                "feedparser is required for podcast RSS downloading. "
                "Install it with: pip install feedparser"
            )

        self.db_service = db_service or DatabaseService()
        logger.info("PodcastRSSDownloader initialized")

    def download_episode_by_id(
        self,
        rss_url: str,
        episode_id: str,
        output_dir: Path,
    ) -> tuple[Path, str] | None:
        """
        Download a specific episode from RSS feed by episode ID.

        Args:
            rss_url: Podcast RSS feed URL
            episode_id: Episode identifier (Apple Podcasts ID, RSS.com ID, or GUID)
            output_dir: Directory to save downloaded audio file

        Returns:
            (audio_file_path, podcast_source_id) or None if not found

        This method is useful when you have a direct link to a specific episode
        (e.g., from Apple Podcasts or RSS.com) and want to download just that episode.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Downloading episode {episode_id} from RSS feed: {rss_url[:60]}..."
        )

        # Parse podcast feed
        episodes = self._parse_podcast_feed(rss_url)
        if not episodes:
            logger.warning(f"No episodes found in RSS feed: {rss_url}")
            return None

        logger.info(
            f"Found {len(episodes)} episodes in feed, searching for ID: {episode_id}"
        )

        # Find episode by ID
        # Episode IDs can appear in different formats:
        # - Apple Podcasts: ?i=1000734606759 (just the number)
        # - RSS.com: https://rss.com/podcasts/zeihan/2296354 (full URL or just number)
        # - GUID: Various formats
        target_episode = None
        for episode in episodes:
            guid = episode.get("guid", "")
            link = episode.get("link", "")

            # Check if episode_id matches:
            # 1. Exact match in GUID or link
            # 2. Episode ID appears in GUID or link
            if (
                episode_id in guid
                or episode_id in link
                or guid.endswith(episode_id)
                or link.endswith(episode_id)
            ):
                target_episode = episode
                logger.info(f"✅ Found episode: {episode['title'][:50]}...")
                break

        if not target_episode:
            logger.warning(f"Episode {episode_id} not found in RSS feed")
            return None

        # Download the episode
        audio_url = target_episode["audio_url"]
        audio_file = self._download_audio_file(audio_url, output_dir)

        if not audio_file:
            logger.error(f"Failed to download episode {episode_id}")
            return None

        # Generate podcast source_id
        podcast_source_id = self._generate_podcast_source_id(
            rss_url, target_episode["guid"]
        )

        # Store source metadata in database
        self._store_source_metadata(
            podcast_source_id,
            target_episode,
            rss_url,
            str(audio_file),
        )

        logger.info(f"✅ Downloaded episode: {audio_file.name}")
        return (audio_file, podcast_source_id)

    def download_from_rss(
        self,
        rss_url: str,
        target_source_ids: dict[str, str],  # {youtube_source_id: youtube_url}
        output_dir: Path,
    ) -> list[tuple[Path, str]]:
        """
        Download specific episodes from RSS feed.

        Args:
            rss_url: Podcast RSS feed URL
            target_source_ids: YouTube source_ids to match against
            output_dir: Directory to save downloaded audio files

        Returns:
            [(audio_file_path, podcast_source_id), ...]

        Only downloads episodes that match the target YouTube videos.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading from podcast RSS: {rss_url[:60]}...")
        logger.info(f"Target episodes: {len(target_source_ids)}")

        # Parse podcast feed
        episodes = self._parse_podcast_feed(rss_url)
        if not episodes:
            logger.warning(f"No episodes found in RSS feed: {rss_url}")
            return []

        logger.info(f"Found {len(episodes)} episodes in feed")

        # Match episodes to YouTube videos
        matched_episodes = []
        logger.info(
            f"🔍 Matching {len(episodes)} episodes against {len(target_source_ids)} target(s)..."
        )
        logger.info(
            f"💡 Will stop early once all {len(target_source_ids)} target(s) are matched"
        )

        # Track which targets have been matched
        unmatched_targets = set(target_source_ids.keys())

        # Use progress bar for terminal feedback
        with tqdm(
            total=len(episodes), desc="Matching episodes", unit="ep", disable=None
        ) as pbar:
            for idx, episode in enumerate(episodes, 1):
                # Check against remaining unmatched targets only
                for youtube_source_id in list(unmatched_targets):
                    youtube_url = target_source_ids[youtube_source_id]
                    is_match, confidence, method = self._match_episode_to_youtube(
                        episode, youtube_source_id, youtube_url
                    )
                    if is_match:
                        matched_episodes.append(
                            (
                                episode,
                                youtube_source_id,
                                youtube_url,
                                confidence,
                                method,
                            )
                        )
                        unmatched_targets.remove(youtube_source_id)
                        logger.info(
                            f"✅ [{len(matched_episodes)}/{len(target_source_ids)}] Matched: {episode['title'][:50]}... "
                            f"(confidence={confidence:.2f}, method={method})"
                        )
                        pbar.set_postfix(
                            {
                                "matches": f"{len(matched_episodes)}/{len(target_source_ids)}",
                                "remaining": len(unmatched_targets),
                            }
                        )
                        break

                pbar.update(1)

                # Early exit: Stop if all targets matched
                if not unmatched_targets:
                    logger.info(
                        f"✅ All {len(target_source_ids)} target(s) matched! Stopping early (checked {idx}/{len(episodes)} episodes)"
                    )
                    pbar.total = idx  # Update progress bar total to current position
                    pbar.refresh()
                    break

        logger.info(
            f"Matched {len(matched_episodes)}/{len(target_source_ids)} episodes "
            f"({len(matched_episodes)/len(target_source_ids)*100:.1f}%)"
        )

        # Download matched episodes
        downloaded_files = []
        logger.info(f"📥 Downloading {len(matched_episodes)} matched episode(s)...")

        for idx, (
            episode,
            youtube_source_id,
            youtube_url,
            confidence,
            method,
        ) in enumerate(matched_episodes, 1):
            try:
                logger.info(
                    f"[{idx}/{len(matched_episodes)}] Downloading: {episode['title'][:50]}..."
                )
                audio_file, podcast_source_id = self._download_episode(
                    episode, rss_url, output_dir
                )
                if audio_file:
                    downloaded_files.append((audio_file, podcast_source_id))
                    logger.info(f"✅ Downloaded: {audio_file.name}")

                    # Create source alias linking YouTube and podcast source_ids
                    self.db_service.create_source_alias(
                        primary_source_id=youtube_source_id,
                        alias_source_id=podcast_source_id,
                        alias_type="youtube_to_podcast",
                        match_confidence=confidence,
                        match_method=method,
                        match_metadata={
                            "episode_title": episode.get("title"),
                            "youtube_url": youtube_url,
                            "rss_url": rss_url,
                        },
                        verified_by="system",
                    )

                    logger.info(
                        f"🔗 Created alias: {youtube_source_id} ↔ {podcast_source_id}"
                    )

            except Exception as e:
                logger.error(f"Failed to download episode {episode['title'][:30]}: {e}")

        logger.info(
            f"Successfully downloaded {len(downloaded_files)} episodes from RSS feed"
        )
        return downloaded_files

    def _parse_podcast_feed(self, rss_url: str) -> list[dict]:
        """
        Parse podcast RSS feed and extract episode metadata.

        Args:
            rss_url: Podcast RSS feed URL

        Returns:
            List of episode dicts with metadata
        """
        try:
            # Set user agent to avoid blocking
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }

            logger.info(f"📡 Fetching podcast feed (timeout: 30s)...")
            response = requests.get(rss_url, headers=headers, timeout=30)
            response.raise_for_status()
            logger.info(f"✅ Feed fetched successfully ({len(response.content)} bytes)")

            # Parse with feedparser
            feed_data = feedparser.parse(response.content)

            if feed_data.bozo and not feed_data.entries:
                logger.warning(f"Podcast feed may be malformed: {rss_url}")
                return []

            # Extract episode metadata
            episodes = []
            for entry in feed_data.entries:
                episode = self._extract_episode_metadata(entry)
                if episode:
                    episodes.append(episode)

            logger.debug(f"Parsed {len(episodes)} episodes from feed")
            return episodes

        except Exception as e:
            logger.error(f"Failed to parse podcast feed {rss_url}: {e}")
            return []

    def _extract_episode_metadata(self, entry: Any) -> dict | None:
        """
        Extract metadata from podcast RSS entry.

        Args:
            entry: feedparser entry object

        Returns:
            Episode metadata dict or None
        """
        try:
            # Extract audio enclosure URL
            audio_url = None
            audio_type = None
            audio_length = None

            if hasattr(entry, "enclosures") and entry.enclosures:
                # Collect all audio enclosures
                audio_enclosures = []
                for enclosure in entry.enclosures:
                    # Look for audio/* MIME types
                    if enclosure.get("type", "").startswith("audio/"):
                        audio_enclosures.append(enclosure)

                # Prefer lowest quality (smallest file) to minimize bandwidth
                # Sort by length (file size) ascending - smallest first
                if audio_enclosures:
                    # Sort by length if available, otherwise use first
                    audio_enclosures_with_length = [
                        e for e in audio_enclosures if e.get("length")
                    ]

                    if audio_enclosures_with_length:
                        # Sort by length (ascending) - smallest file first
                        selected = min(
                            audio_enclosures_with_length,
                            key=lambda e: int(e.get("length", 0)),
                        )
                        logger.debug(
                            f"Selected lowest quality audio: "
                            f"{int(selected.get('length', 0)) / 1024 / 1024:.1f} MB "
                            f"({selected.get('type', 'unknown')})"
                        )
                    else:
                        # No length info, just use first audio enclosure
                        selected = audio_enclosures[0]
                        logger.debug(
                            f"Using first audio enclosure (no size info): "
                            f"{selected.get('type', 'unknown')}"
                        )

                    audio_url = selected.get("href") or selected.get("url")
                    audio_type = selected.get("type")
                    audio_length = selected.get("length")

            if not audio_url:
                return None

            # Extract episode metadata
            episode = {
                "title": entry.get("title", "Unknown Episode"),
                "description": entry.get("summary", ""),
                "guid": entry.get("id") or entry.get("guid", ""),
                "published": entry.get("published", ""),
                "published_parsed": entry.get("published_parsed"),
                "audio_url": audio_url,
                "audio_type": audio_type,
                "audio_length": audio_length,
                "duration": entry.get("itunes_duration", ""),
                "link": entry.get("link", ""),
            }

            return episode

        except Exception as e:
            logger.debug(f"Failed to extract episode metadata: {e}")
            return None

    def _match_episode_to_youtube(
        self, episode: dict, youtube_source_id: str, youtube_url: str
    ) -> tuple[bool, float, str]:
        """
        Match RSS episode to YouTube video by title/date.

        Uses fuzzy matching on title and date proximity.

        Args:
            episode: Episode metadata dict
            youtube_source_id: YouTube video ID
            youtube_url: YouTube video URL

        Returns:
            (is_match, confidence, method) where:
            - is_match: True if episode matches YouTube video
            - confidence: Match confidence (0-1)
            - method: Match method used ('title_fuzzy', 'title_exact', 'date_proximity')
        """
        from datetime import datetime
        from difflib import SequenceMatcher

        # Get YouTube video metadata
        youtube_metadata = self._get_youtube_metadata_for_matching(youtube_source_id)
        if not youtube_metadata:
            return (False, 0.0, "no_youtube_metadata")

        episode_title = episode.get("title", "").lower().strip()
        youtube_title = youtube_metadata.get("title", "").lower().strip()

        # Method 1: Exact title match (after normalization)
        if episode_title == youtube_title:
            return (True, 1.0, "title_exact")

        # Method 2: Fuzzy title match (using SequenceMatcher)
        title_similarity = SequenceMatcher(None, episode_title, youtube_title).ratio()

        # Method 3: Check date proximity (±2 days)
        date_match = False
        date_diff_days = None

        episode_published = episode.get("published_parsed")
        youtube_upload_date = youtube_metadata.get("upload_date")

        if episode_published and youtube_upload_date:
            try:
                # Convert episode published to datetime
                episode_date = datetime(*episode_published[:6])

                # Convert YouTube upload_date (format: YYYYMMDD) to datetime
                youtube_date = datetime.strptime(youtube_upload_date, "%Y%m%d")

                # Calculate difference
                date_diff = abs((episode_date - youtube_date).days)
                date_diff_days = date_diff

                # Match if within 2 days
                if date_diff <= 2:
                    date_match = True
            except (ValueError, TypeError) as e:
                logger.debug(f"Date parsing failed: {e}")

        # Decision logic:
        # - Title similarity >= 0.9 → match (high confidence)
        # - Title similarity >= 0.8 + date match → match (medium confidence)
        # - Title similarity >= 0.7 + date match → match (low confidence)

        if title_similarity >= 0.9:
            return (True, title_similarity, "title_fuzzy")
        elif title_similarity >= 0.8 and date_match:
            confidence = (
                title_similarity + 1.0
            ) / 2  # Average of title sim and perfect date match
            return (True, confidence, "title_fuzzy_date")
        elif title_similarity >= 0.7 and date_match:
            confidence = (title_similarity + 0.8) / 2
            return (True, confidence, "title_fuzzy_date")

        # No match
        return (False, title_similarity, "no_match")

    def _get_youtube_metadata_for_matching(self, video_id: str) -> dict | None:
        """
        Get YouTube video metadata for matching.

        First checks database, then falls back to yt-dlp if needed.

        Args:
            video_id: YouTube video ID

        Returns:
            Metadata dict with title, upload_date, duration, etc.
        """
        # Check database first (faster)
        source = self.db_service.get_source(video_id)
        if source:
            return {
                "title": source.title,
                "upload_date": source.upload_date,
                "duration_seconds": source.duration_seconds,
                "uploader": source.uploader,
            }

        # Fall back to yt-dlp (slower but works for new videos)
        try:
            import yt_dlp

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
            }

            url = f"https://www.youtube.com/watch?v={video_id}"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    return None

                return {
                    "title": info.get("title"),
                    "upload_date": info.get("upload_date"),
                    "duration_seconds": info.get("duration"),
                    "uploader": info.get("uploader"),
                }

        except Exception as e:
            logger.debug(f"Failed to get YouTube metadata for {video_id}: {e}")
            return None

    def _download_episode(
        self, episode: dict, feed_url: str, output_dir: Path
    ) -> tuple[Path, str] | None:
        """
        Download audio file for episode.

        Args:
            episode: Episode metadata dict
            feed_url: Podcast RSS feed URL
            output_dir: Directory to save audio file

        Returns:
            (audio_file_path, podcast_source_id) or None
        """
        audio_url = episode["audio_url"]

        # Generate deterministic source_id
        podcast_source_id = self._generate_podcast_source_id(feed_url, episode["guid"])

        # Generate filename from title
        safe_title = self._sanitize_filename(episode["title"])

        # Determine file extension from audio URL or type
        ext = self._get_audio_extension(audio_url, episode.get("audio_type"))

        audio_file = output_dir / f"{safe_title}_{podcast_source_id[:8]}{ext}"

        # Download audio file
        try:
            logger.debug(f"Downloading audio: {audio_url[:60]}...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }

            response = requests.get(audio_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            # Write to file
            with open(audio_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            logger.debug(f"Downloaded {audio_file.stat().st_size / 1024 / 1024:.1f} MB")

            # Store source metadata in database
            self._store_source_metadata(
                podcast_source_id, episode, audio_file, feed_url
            )

            return (audio_file, podcast_source_id)

        except Exception as e:
            logger.error(f"Failed to download audio from {audio_url[:60]}: {e}")
            if audio_file.exists():
                audio_file.unlink()  # Clean up partial download
            return None

    def _generate_podcast_source_id(self, feed_url: str, episode_guid: str) -> str:
        """
        Generate deterministic source_id for podcast episode.

        Format: podcast_{feed_hash}_{guid_hash}

        Args:
            feed_url: Podcast RSS feed URL
            episode_guid: Episode GUID from RSS feed

        Returns:
            Deterministic source_id
        """
        # Hash feed URL (8 chars)
        feed_hash = hashlib.md5(feed_url.encode(), usedforsecurity=False).hexdigest()[
            :8
        ]

        # Hash episode GUID (8 chars)
        guid_hash = hashlib.md5(
            episode_guid.encode(), usedforsecurity=False
        ).hexdigest()[:8]

        return f"podcast_{feed_hash}_{guid_hash}"

    def _sanitize_filename(self, title: str) -> str:
        """
        Sanitize episode title for use as filename.

        Args:
            title: Episode title

        Returns:
            Safe filename string
        """
        # Remove invalid filename characters
        safe = re.sub(r'[<>:"/\\|?*]', "", title)
        # Replace spaces with underscores
        safe = safe.replace(" ", "_")
        # Limit length
        safe = safe[:100]
        return safe

    def _get_audio_extension(self, audio_url: str, audio_type: str | None) -> str:
        """
        Determine audio file extension from URL or MIME type.

        Args:
            audio_url: Audio file URL
            audio_type: MIME type (e.g., "audio/mpeg")

        Returns:
            File extension (e.g., ".mp3")
        """
        # Try to get extension from URL
        parsed = urlparse(audio_url)
        path = Path(parsed.path)
        if path.suffix:
            return path.suffix

        # Try to get extension from MIME type
        if audio_type:
            mime_to_ext = {
                "audio/mpeg": ".mp3",
                "audio/mp3": ".mp3",
                "audio/mp4": ".m4a",
                "audio/m4a": ".m4a",
                "audio/x-m4a": ".m4a",
                "audio/wav": ".wav",
                "audio/x-wav": ".wav",
                "audio/ogg": ".ogg",
                "audio/opus": ".opus",
            }
            return mime_to_ext.get(audio_type.lower(), ".mp3")

        # Default to .mp3
        return ".mp3"

    def _store_source_metadata(
        self, source_id: str, episode_data: dict, audio_file_path: Path, feed_url: str
    ) -> None:
        """
        Store source metadata in MediaSource table.

        Args:
            source_id: Podcast source_id
            episode_data: Episode metadata dict
            audio_file_path: Path to downloaded audio file
            feed_url: Podcast RSS feed URL
        """
        try:
            # Check if source already exists
            source = self.db_service.get_source(source_id)

            if source:
                # Update existing source
                self.db_service.update_source(
                    source_id=source_id,
                    audio_file_path=str(audio_file_path),
                    title=episode_data.get("title"),
                    description=episode_data.get("description"),
                )
                logger.debug(f"Updated existing source: {source_id}")
            else:
                # Create new source
                self.db_service.create_source(
                    source_id=source_id,
                    source_type="podcast",
                    audio_file_path=str(audio_file_path),
                    title=episode_data.get("title"),
                    description=episode_data.get("description"),
                    url=feed_url,
                    metadata={
                        "feed_url": feed_url,
                        "episode_guid": episode_data.get("guid"),
                        "published": episode_data.get("published"),
                        "duration": episode_data.get("duration"),
                        "audio_url": episode_data.get("audio_url"),
                    },
                )
                logger.debug(f"Created new source: {source_id}")

        except Exception as e:
            logger.error(f"Failed to store source metadata for {source_id}: {e}")
