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
        for episode in episodes:
            for youtube_source_id, youtube_url in target_source_ids.items():
                if self._match_episode_to_youtube(
                    episode, youtube_source_id, youtube_url
                ):
                    matched_episodes.append((episode, youtube_source_id, youtube_url))
                    logger.info(f"✅ Matched episode: {episode['title'][:50]}...")
                    break

        logger.info(
            f"Matched {len(matched_episodes)}/{len(target_source_ids)} episodes "
            f"({len(matched_episodes)/len(target_source_ids)*100:.1f}%)"
        )

        # Download matched episodes
        downloaded_files = []
        for episode, youtube_source_id, youtube_url in matched_episodes:
            try:
                audio_file, podcast_source_id = self._download_episode(
                    episode, rss_url, output_dir
                )
                if audio_file:
                    downloaded_files.append((audio_file, podcast_source_id))
                    logger.info(f"✅ Downloaded: {audio_file.name}")
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

            logger.debug(f"Fetching podcast feed: {rss_url}")
            response = requests.get(rss_url, headers=headers, timeout=30)
            response.raise_for_status()

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
                for enclosure in entry.enclosures:
                    # Look for audio/* MIME types
                    if enclosure.get("type", "").startswith("audio/"):
                        audio_url = enclosure.get("href") or enclosure.get("url")
                        audio_type = enclosure.get("type")
                        audio_length = enclosure.get("length")
                        break

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
    ) -> bool:
        """
        Match RSS episode to YouTube video by title/date.

        Uses fuzzy matching on title and date proximity.

        Args:
            episode: Episode metadata dict
            youtube_source_id: YouTube video ID
            youtube_url: YouTube video URL

        Returns:
            True if episode matches YouTube video
        """
        # TODO: Implement more sophisticated matching
        # For now, we'll use a simple title-based match
        # In production, you'd want to:
        # 1. Normalize titles (remove punctuation, lowercase)
        # 2. Check date proximity (published within 1-2 days)
        # 3. Use fuzzy string matching (e.g., difflib.SequenceMatcher)
        # 4. Check duration if available

        episode_title = episode.get("title", "").lower()

        # Extract title from YouTube URL metadata if available
        # For now, we'll just return False to indicate no match
        # The actual matching logic would need YouTube metadata

        return False  # Placeholder - needs YouTube metadata integration

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
                    file_path=str(audio_file_path),
                    title=episode_data.get("title"),
                    description=episode_data.get("description"),
                )
                logger.debug(f"Updated existing source: {source_id}")
            else:
                # Create new source
                self.db_service.create_source(
                    source_id=source_id,
                    source_type="podcast",
                    file_path=str(audio_file_path),
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
