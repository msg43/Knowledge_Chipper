#!/usr/bin/env python3
"""
YouTube to Podcast RSS Mapper

Maps YouTube URLs to native podcast RSS feeds using multiple discovery APIs.
Generates deterministic source_ids for both YouTube and podcast content.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from ..config import get_settings
from ..logger import get_logger

logger = get_logger(__name__)


class YouTubeToPodcastMapper:
    """
    Maps YouTube URLs to native podcast RSS feeds.
    
    Features:
    - Queries multiple podcast discovery APIs (PodcastIndex, ListenNotes, iTunes)
    - Generates deterministic source_ids for podcast episodes
    - Caches mappings to avoid repeated API calls
    - Extracts YouTube video IDs as source_ids
    """
    
    def __init__(self):
        """Initialize mapper with configuration."""
        self.config = get_settings()
        self.podcast_config = self.config.podcast_discovery
        
        # Load cache
        self.cache_path = Path(self.podcast_config.mapping_cache_path).expanduser()
        self.cache = self._load_cache()
        
        logger.info(
            f"YouTubeToPodcastMapper initialized: "
            f"cache_enabled={self.podcast_config.cache_mappings}, "
            f"cache_entries={len(self.cache)}"
        )
    
    def map_url_to_rss(self, youtube_url: str) -> tuple[str, str] | None:
        """
        Map single YouTube URL to podcast RSS feed.
        
        Args:
            youtube_url: YouTube video URL
            
        Returns:
            (rss_feed_url, podcast_source_id) or None if not found
            
        Example:
            ("https://feeds.megaphone.fm/hubermanlab", "podcast_abc123_def456")
        """
        if not self.podcast_config.enable_youtube_to_rss_mapping:
            return None
        
        # Check cache first
        if self.podcast_config.cache_mappings and youtube_url in self.cache:
            cached = self.cache[youtube_url]
            logger.debug(f"Cache hit for {youtube_url[:50]}...")
            return (cached["rss_url"], cached["source_id"])
        
        # Extract YouTube metadata
        video_id = self._extract_youtube_source_id(youtube_url)
        if not video_id:
            logger.warning(f"Could not extract video ID from {youtube_url}")
            return None
        
        # Get video metadata to extract channel info
        video_metadata = self._get_youtube_metadata(video_id)
        if not video_metadata:
            logger.warning(f"Could not fetch metadata for video {video_id}")
            return None
        
        channel_id = video_metadata.get("channel_id")
        channel_name = video_metadata.get("channel_name")
        video_title = video_metadata.get("title")
        
        if not channel_id or not channel_name:
            logger.warning(f"Missing channel info for video {video_id}")
            return None
        
        # Try to find podcast RSS feed
        rss_url = self._find_podcast_feed(channel_id, channel_name)
        if not rss_url:
            logger.debug(f"No podcast feed found for channel: {channel_name}")
            return None
        
        # Generate podcast source_id
        # We'll use the video_id as a temporary identifier until we can match to episode
        # The actual episode matching happens in PodcastRSSDownloader
        podcast_source_id = f"podcast_pending_{video_id}"
        
        # Cache the result
        if self.podcast_config.cache_mappings:
            self.cache[youtube_url] = {
                "rss_url": rss_url,
                "source_id": podcast_source_id,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "video_title": video_title
            }
            self._save_cache()
        
        logger.info(
            f"✅ Mapped YouTube video to podcast RSS:\n"
            f"   Video: {video_title[:50]}...\n"
            f"   Channel: {channel_name}\n"
            f"   RSS: {rss_url[:60]}..."
        )
        
        return (rss_url, podcast_source_id)
    
    def map_urls_batch(self, youtube_urls: list[str]) -> dict[str, tuple[str, str]]:
        """
        Map batch of YouTube URLs to podcast RSS feeds.
        
        Args:
            youtube_urls: List of YouTube video URLs
            
        Returns:
            {youtube_url: (rss_feed_url, podcast_source_id)}
            
        Only includes URLs that successfully mapped to podcast feeds.
        """
        mappings = {}
        
        logger.info(f"Mapping {len(youtube_urls)} YouTube URLs to podcast RSS feeds...")
        
        for idx, url in enumerate(youtube_urls, 1):
            if idx % 10 == 0:
                logger.info(f"Progress: {idx}/{len(youtube_urls)} URLs processed")
            
            result = self.map_url_to_rss(url)
            if result:
                mappings[url] = result
        
        logger.info(
            f"📊 Mapping complete: {len(mappings)}/{len(youtube_urls)} URLs mapped to podcast feeds "
            f"({len(mappings)/len(youtube_urls)*100:.1f}%)"
        )
        
        return mappings
    
    def _extract_youtube_source_id(self, youtube_url: str) -> str | None:
        """
        Extract source_id (11-char video ID) from YouTube URL.
        
        Args:
            youtube_url: YouTube video URL
            
        Returns:
            11-character video ID or None
        """
        from ..utils.video_id_extractor import VideoIDExtractor
        
        video_id = VideoIDExtractor.extract_video_id(youtube_url)
        return video_id
    
    def _get_youtube_metadata(self, video_id: str) -> dict[str, Any] | None:
        """
        Get YouTube video metadata (channel ID, title, etc.).
        
        Uses yt-dlp to extract metadata without downloading.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Metadata dict or None
        """
        try:
            import yt_dlp
            
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,  # Don't download, just get metadata
                "skip_download": True,
            }
            
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                return {
                    "video_id": video_id,
                    "title": info.get("title"),
                    "channel_id": info.get("channel_id"),
                    "channel_name": info.get("channel") or info.get("uploader"),
                    "description": info.get("description"),
                    "upload_date": info.get("upload_date"),
                }
        
        except Exception as e:
            logger.error(f"Failed to get YouTube metadata for {video_id}: {e}")
            return None
    
    def _find_podcast_feed(self, channel_id: str, channel_name: str) -> str | None:
        """
        Find podcast RSS feed for YouTube channel.
        
        Tries multiple discovery APIs in order:
        1. PodcastIndex.org
        2. ListenNotes.com
        3. iTunes Search API
        
        Args:
            channel_id: YouTube channel ID
            channel_name: YouTube channel name
            
        Returns:
            RSS feed URL or None
        """
        # Try PodcastIndex.org first (best coverage, free tier)
        rss_url = self._query_podcast_index(channel_name)
        if rss_url:
            logger.debug(f"Found via PodcastIndex: {rss_url[:60]}...")
            return rss_url
        
        # Try ListenNotes.com (fallback)
        rss_url = self._query_listen_notes(channel_name)
        if rss_url:
            logger.debug(f"Found via ListenNotes: {rss_url[:60]}...")
            return rss_url
        
        # Try iTunes Search API (free, no key required)
        rss_url = self._query_itunes(channel_name)
        if rss_url:
            logger.debug(f"Found via iTunes: {rss_url[:60]}...")
            return rss_url
        
        return None
    
    def _query_podcast_index(self, channel_name: str) -> str | None:
        """
        Query PodcastIndex.org API for podcast feed.
        
        Args:
            channel_name: YouTube channel name
            
        Returns:
            RSS feed URL or None
        """
        if not self.podcast_config.podcast_index_api_key:
            logger.debug("PodcastIndex API key not configured, skipping")
            return None
        
        try:
            # PodcastIndex.org API: https://podcastindex-org.github.io/docs-api/
            url = "https://api.podcastindex.org/api/1.0/search/byterm"
            
            headers = {
                "X-Auth-Key": self.podcast_config.podcast_index_api_key,
                "User-Agent": "KnowledgeChipper/1.0"
            }
            
            params = {
                "q": channel_name,
                "max": 5  # Get top 5 results
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            feeds = data.get("feeds", [])
            
            if not feeds:
                return None
            
            # Return first match (best match)
            # TODO: Could add fuzzy matching to find best match
            return feeds[0].get("url")
        
        except Exception as e:
            logger.debug(f"PodcastIndex query failed: {e}")
            return None
    
    def _query_listen_notes(self, channel_name: str) -> str | None:
        """
        Query ListenNotes.com API for podcast feed.
        
        Args:
            channel_name: YouTube channel name
            
        Returns:
            RSS feed URL or None
        """
        if not self.podcast_config.listen_notes_api_key:
            logger.debug("ListenNotes API key not configured, skipping")
            return None
        
        try:
            # ListenNotes API: https://www.listennotes.com/api/
            url = "https://listen-api.listennotes.com/api/v2/search"
            
            headers = {
                "X-ListenAPI-Key": self.podcast_config.listen_notes_api_key
            }
            
            params = {
                "q": channel_name,
                "type": "podcast",
                "len_max": 5
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                return None
            
            # Return first match RSS URL
            return results[0].get("rss")
        
        except Exception as e:
            logger.debug(f"ListenNotes query failed: {e}")
            return None
    
    def _query_itunes(self, channel_name: str) -> str | None:
        """
        Query iTunes Search API for podcast feed.
        
        Free API, no key required.
        
        Args:
            channel_name: YouTube channel name
            
        Returns:
            RSS feed URL or None
        """
        try:
            # iTunes Search API: https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/
            url = "https://itunes.apple.com/search"
            
            params = {
                "term": channel_name,
                "media": "podcast",
                "limit": 5
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                return None
            
            # Return first match feed URL
            return results[0].get("feedUrl")
        
        except Exception as e:
            logger.debug(f"iTunes query failed: {e}")
            return None
    
    def _generate_podcast_source_id(
        self,
        feed_url: str,
        episode_guid: str
    ) -> str:
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
        feed_hash = hashlib.md5(
            feed_url.encode(), 
            usedforsecurity=False
        ).hexdigest()[:8]
        
        # Hash episode GUID (8 chars)
        guid_hash = hashlib.md5(
            episode_guid.encode(), 
            usedforsecurity=False
        ).hexdigest()[:8]
        
        return f"podcast_{feed_hash}_{guid_hash}"
    
    def _load_cache(self) -> dict:
        """Load mapping cache from disk."""
        if not self.podcast_config.cache_mappings:
            return {}
        
        try:
            if self.cache_path.exists():
                with open(self.cache_path, 'r') as f:
                    cache = json.load(f)
                logger.info(f"Loaded {len(cache)} cached mappings from {self.cache_path}")
                return cache
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
        
        return {}
    
    def _save_cache(self) -> None:
        """Save mapping cache to disk."""
        if not self.podcast_config.cache_mappings:
            return
        
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logger.debug(f"Saved {len(self.cache)} mappings to cache")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

