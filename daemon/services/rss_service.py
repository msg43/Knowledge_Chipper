"""
RSS Feed Service

Wrapper around existing podcast RSS downloader for daemon use.
Provides simplified interface for downloading latest episodes from RSS feeds.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.knowledge_system.services.podcast_rss_downloader import PodcastRSSDownloader
    from src.knowledge_system.services.database_service import DatabaseService
    RSS_SUPPORT_AVAILABLE = True
except ImportError as e:
    RSS_SUPPORT_AVAILABLE = False
    import_error = str(e)

logger = logging.getLogger(__name__)


class RSSService:
    """
    Simplified RSS feed service for daemon use.
    
    Downloads latest episodes from podcast RSS feeds without requiring
    YouTube video matching.
    """

    def __init__(self, db_service: Optional[any] = None):
        """Initialize RSS service."""
        if not RSS_SUPPORT_AVAILABLE:
            raise RuntimeError(f"RSS support not available: {import_error}")
        
        # Initialize with database service
        self.db_service = db_service or DatabaseService()
        self.downloader = PodcastRSSDownloader(db_service=self.db_service)
        logger.info("RSSService initialized")

    def get_latest_episodes(self, rss_url: str, max_episodes: int = 9999) -> list[dict]:
        """
        Get metadata for latest episodes from RSS feed.
        
        Args:
            rss_url: Podcast RSS feed URL
            max_episodes: Maximum number of episodes to retrieve
            
        Returns:
            List of episode metadata dicts with keys:
            - title: Episode title
            - audio_url: Direct download URL for audio file
            - published: Publication date (ISO format string)
            - description: Episode description
            - duration: Duration in seconds (if available)
            - guid: Unique identifier
        """
        logger.info(f"Fetching latest {max_episodes} episodes from: {rss_url[:60]}...")
        
        # Parse the RSS feed (uses existing _parse_podcast_feed method)
        episodes = self.downloader._parse_podcast_feed(rss_url)
        
        if not episodes:
            logger.warning(f"No episodes found in RSS feed: {rss_url}")
            return []
        
        # Sort by published date (most recent first) and limit
        episodes_sorted = sorted(
            episodes, 
            key=lambda ep: ep.get('published', ''), 
            reverse=True
        )
        
        latest_episodes = episodes_sorted[:max_episodes]
        
        logger.info(f"Found {len(episodes)} total episodes, returning {len(latest_episodes)} latest")
        
        # Return simplified episode metadata
        return [
            {
                'title': ep.get('title', 'Unknown Title'),
                'audio_url': ep.get('audio_url'),
                'published': ep.get('published'),
                'description': ep.get('description', ''),
                'duration': ep.get('duration'),
                'guid': ep.get('guid'),
                'feed_url': rss_url,
            }
            for ep in latest_episodes
        ]

    def is_rss_url(self, url: str) -> bool:
        """
        Check if URL looks like an RSS feed.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL appears to be an RSS feed
        """
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Check for common RSS feed patterns
        rss_indicators = [
            '.rss',
            '.xml',
            '/rss',
            '/feed',
            'feeds.',
            'feed.',
            'rss.',
        ]
        
        return any(indicator in url_lower for indicator in rss_indicators)


# Global instance
rss_service = RSSService() if RSS_SUPPORT_AVAILABLE else None

