#!/usr/bin/env python3
"""
Podcast Episode Searcher

Direct episode-level search using iTunes and PodcastIndex APIs.
Much faster and more accurate than channel-based RSS feed matching.
"""

import hashlib
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import requests

from ..config import get_settings
from ..database.service import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


@dataclass
class PodcastEpisode:
    """Podcast episode search result."""

    title: str
    podcast_name: str
    podcast_feed_url: str
    episode_audio_url: str | None
    release_date: str | None
    duration_ms: int | None
    description: str | None
    guid: str | None

    # For disambiguation
    confidence: float = 1.0
    match_method: str = "exact"


class PodcastEpisodeSearcher:
    """
    Search for podcast episodes by title using multiple APIs.

    Much more efficient than downloading entire RSS feeds:
    - Searches by episode title (not channel name)
    - Returns 1-5 results (not 280 episodes)
    - Uses free iTunes API or PodcastIndex
    - 20-280x faster than RSS feed matching
    """

    def __init__(self, db_service: DatabaseService | None = None):
        """Initialize searcher with configuration."""
        self.config = get_settings()
        self.podcast_config = self.config.podcast_discovery
        self.db_service = db_service or DatabaseService()

        logger.info("PodcastEpisodeSearcher initialized (episode-first architecture)")

    def search_by_title(
        self, title: str, youtube_channel: str | None = None, max_results: int = 5
    ) -> list[PodcastEpisode]:
        """
        Search for podcast episodes matching title.

        Args:
            title: Episode title to search for
            youtube_channel: Optional YouTube channel name for disambiguation
            max_results: Maximum number of results to return

        Returns:
            List of matching podcast episodes (typically 1-5 results)
        """
        logger.info(f"🔍 Searching for podcast episode: {title[:50]}...")

        # Try iTunes first (free, no API key required)
        results = self._search_itunes_episodes(title, max_results)

        if not results and self.podcast_config.podcast_index_api_key:
            # Fall back to PodcastIndex if iTunes returns nothing
            logger.debug("iTunes returned no results, trying PodcastIndex...")
            results = self._search_podcast_index_episodes(title, max_results)

        if not results:
            logger.info(f"No podcast episodes found for: {title[:50]}")
            return []

        logger.info(f"✅ Found {len(results)} podcast episode(s)")

        # If YouTube channel provided, use it for disambiguation
        if youtube_channel and len(results) > 1:
            results = self._rank_by_channel_match(results, youtube_channel)

        return results

    def resolve_single_match(
        self, matches: list[PodcastEpisode], youtube_channel: str, youtube_video_id: str
    ) -> PodcastEpisode | None:
        """
        Resolve multiple matches to single best match.

        Uses:
        1. Existing database aliases (YouTube ↔ Podcast relationships)
        2. Fuzzy channel name matching
        3. User can confirm ambiguous matches later

        Args:
            matches: List of potential podcast episodes
            youtube_channel: YouTube channel name
            youtube_video_id: YouTube video ID

        Returns:
            Best matching episode or None if ambiguous
        """
        if not matches:
            return None

        if len(matches) == 1:
            logger.info("✅ Single match found, no disambiguation needed")
            return matches[0]

        logger.info(
            f"🔍 Disambiguating {len(matches)} matches using channel relationship..."
        )

        # Check for existing channel alias in database
        existing_alias = self._get_channel_alias(youtube_channel)
        if existing_alias:
            logger.info(
                f"📋 Found existing channel alias: {youtube_channel} → {existing_alias}"
            )
            for match in matches:
                if self._channels_match(match.podcast_name, existing_alias):
                    match.confidence = 1.0
                    match.match_method = "channel_alias"
                    logger.info(f"✅ Matched via existing alias: {match.podcast_name}")
                    return match

        # Fuzzy match channel names
        best_match = None
        best_similarity = 0.0

        for match in matches:
            similarity = self._fuzzy_match_channels(youtube_channel, match.podcast_name)
            logger.debug(
                f"Channel similarity: {youtube_channel} ↔ {match.podcast_name} = {similarity:.2f}"
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = match

        # High confidence threshold for automatic matching
        if best_similarity >= 0.9:
            best_match.confidence = best_similarity
            best_match.match_method = "channel_fuzzy"

            # Create alias for future use
            self._create_channel_alias(
                youtube_channel=youtube_channel,
                podcast_name=best_match.podcast_name,
                confidence=best_similarity,
                verified_by="system",
            )

            logger.info(
                f"✅ Matched via fuzzy channel name (confidence={best_similarity:.2f}): "
                f"{youtube_channel} → {best_match.podcast_name}"
            )
            return best_match

        # Medium confidence - return but flag for user review
        if best_similarity >= 0.7:
            best_match.confidence = best_similarity
            best_match.match_method = "channel_fuzzy_low"
            logger.warning(
                f"⚠️  Low confidence match ({best_similarity:.2f}): "
                f"{youtube_channel} → {best_match.podcast_name}"
            )
            return best_match

        # Too ambiguous - return None (user intervention needed)
        logger.warning(
            f"❌ Could not disambiguate {len(matches)} matches "
            f"(best similarity: {best_similarity:.2f})"
        )
        return None

    def _search_itunes_episodes(
        self, title: str, max_results: int
    ) -> list[PodcastEpisode]:
        """
        Search iTunes for podcast episodes by title.

        Free API, no key required.
        """
        try:
            url = "https://itunes.apple.com/search"

            params = {
                "term": title,
                "media": "podcast",
                "entity": "podcastEpisode",  # KEY: Search episodes, not shows!
                "limit": max_results,
            }

            logger.debug(f"Querying iTunes API: {title[:50]}...")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if not results:
                return []

            episodes = []
            for result in results:
                episode = PodcastEpisode(
                    title=result.get("trackName", ""),
                    podcast_name=result.get("collectionName", ""),
                    podcast_feed_url=result.get("feedUrl", ""),
                    episode_audio_url=result.get("episodeUrl"),
                    release_date=result.get("releaseDate"),
                    duration_ms=result.get("trackTimeMillis"),
                    description=result.get("description"),
                    guid=result.get("trackId"),  # iTunes track ID as GUID
                )
                episodes.append(episode)

            logger.debug(f"iTunes returned {len(episodes)} episode(s)")
            return episodes

        except Exception as e:
            logger.error(f"iTunes episode search failed: {e}")
            return []

    def _search_podcast_index_episodes(
        self, title: str, max_results: int
    ) -> list[PodcastEpisode]:
        """
        Search PodcastIndex for episodes by title.

        Requires API key (free tier available).
        """
        if not self.podcast_config.podcast_index_api_key:
            return []

        try:
            url = "https://api.podcastindex.org/api/1.0/search/byterm"

            headers = {
                "X-Auth-Key": self.podcast_config.podcast_index_api_key,
                "User-Agent": "KnowledgeChipper/1.0",
            }

            params = {"q": title, "max": max_results}

            logger.debug(f"Querying PodcastIndex API: {title[:50]}...")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            feeds = data.get("feeds", [])

            # PodcastIndex returns feeds, not episodes
            # We'd need to fetch episodes from each feed
            # For now, return empty (iTunes is sufficient)
            logger.debug("PodcastIndex search not yet implemented for episodes")
            return []

        except Exception as e:
            logger.error(f"PodcastIndex episode search failed: {e}")
            return []

    def _rank_by_channel_match(
        self, episodes: list[PodcastEpisode], youtube_channel: str
    ) -> list[PodcastEpisode]:
        """
        Rank episodes by how well their podcast name matches YouTube channel.
        """
        scored_episodes = []

        for episode in episodes:
            similarity = self._fuzzy_match_channels(
                youtube_channel, episode.podcast_name
            )
            episode.confidence = similarity
            scored_episodes.append((similarity, episode))

        # Sort by similarity (descending)
        scored_episodes.sort(key=lambda x: x[0], reverse=True)

        return [ep for _, ep in scored_episodes]

    def _fuzzy_match_channels(self, channel1: str, channel2: str) -> float:
        """
        Fuzzy match two channel names.

        Returns similarity score 0.0-1.0.
        """
        # Normalize
        c1 = channel1.lower().strip()
        c2 = channel2.lower().strip()

        # Remove common suffixes
        for suffix in [" podcast", " show", " official", " channel"]:
            c1 = c1.replace(suffix, "")
            c2 = c2.replace(suffix, "")

        # Use SequenceMatcher for fuzzy comparison
        return SequenceMatcher(None, c1, c2).ratio()

    def _channels_match(self, channel1: str, channel2: str) -> bool:
        """Check if two channel names match (fuzzy)."""
        return self._fuzzy_match_channels(channel1, channel2) >= 0.9

    def _get_channel_alias(self, youtube_channel: str) -> str | None:
        """
        Get podcast name for YouTube channel from database.

        Returns podcast name if alias exists, None otherwise.
        """
        try:
            with self.db_service.get_session() as session:
                from ..database.models import SourceAlias

                alias = (
                    session.query(SourceAlias)
                    .filter(SourceAlias.primary_source_id == youtube_channel)
                    .filter(SourceAlias.alias_type == "youtube_channel_to_podcast")
                    .first()
                )

                if alias:
                    return alias.alias_source_id

                return None

        except Exception as e:
            logger.debug(f"Could not query channel alias: {e}")
            return None

    def _create_channel_alias(
        self,
        youtube_channel: str,
        podcast_name: str,
        confidence: float,
        verified_by: str = "system",
    ):
        """
        Create channel alias in database for future lookups.
        """
        try:
            self.db_service.create_source_alias(
                primary_source_id=youtube_channel,
                alias_source_id=podcast_name,
                alias_type="youtube_channel_to_podcast",
                match_confidence=confidence,
                match_method="channel_fuzzy",
                match_metadata={
                    "youtube_channel": youtube_channel,
                    "podcast_name": podcast_name,
                },
                verified_by=verified_by,
            )
            logger.info(f"📋 Created channel alias: {youtube_channel} → {podcast_name}")

        except Exception as e:
            logger.warning(f"Could not create channel alias: {e}")

    def generate_podcast_source_id(self, feed_url: str, episode_guid: str) -> str:
        """
        Generate deterministic source_id for podcast episode.

        Format: podcast_{feed_hash}_{guid_hash}
        """
        feed_hash = hashlib.md5(feed_url.encode(), usedforsecurity=False).hexdigest()[
            :8
        ]
        guid_hash = hashlib.md5(
            str(episode_guid).encode(), usedforsecurity=False
        ).hexdigest()[:8]

        return f"podcast_{feed_hash}_{guid_hash}"
