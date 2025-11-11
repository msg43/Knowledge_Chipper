#!/usr/bin/env python3
"""
RSS Feed URL Extractor

Extracts raw RSS feed URLs from podcast platform URLs (Apple Podcasts, RSS.com, etc.)
"""

import re
from urllib.parse import urlparse

import requests

from ..logger import get_logger

logger = get_logger(__name__)


class RSSFeedExtractor:
    """
    Extracts raw RSS feed URLs from podcast platform URLs.

    Supports:
    - Apple Podcasts (podcasts.apple.com) - with episode ID extraction
    - RSS.com (rss.com/podcasts/) - with episode ID extraction
    - Direct RSS feed URLs (pass-through)
    """

    def __init__(self):
        """Initialize extractor."""
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    def extract_feed_and_episode(self, url: str) -> tuple[str | None, str | None]:
        """
        Extract RSS feed URL and episode ID from podcast platform URL.

        Args:
            url: Podcast URL (Apple Podcasts, RSS.com, or direct RSS feed)

        Returns:
            (rss_feed_url, episode_id) tuple
            - rss_feed_url: Raw RSS feed URL
            - episode_id: Episode identifier (Apple Podcasts episode ID, RSS.com episode ID, or None)

        Examples:
            >>> extractor = RSSFeedExtractor()
            >>> extractor.extract_feed_and_episode(
            ...     "https://podcasts.apple.com/us/podcast/id1702067155?i=1000734606759"
            ... )
            ("https://media.rss.com/zeihan/feed.xml", "1000734606759")
        """
        if not url:
            return None, None

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Apple Podcasts (with episode ID)
        if "podcasts.apple.com" in domain:
            feed_url = self._extract_from_apple_podcasts(url)
            episode_id = self._extract_apple_episode_id(url)
            return feed_url, episode_id

        # RSS.com (with episode ID)
        if "rss.com" in domain:
            feed_url = self._extract_from_rss_com(url)
            episode_id = self._extract_rss_com_episode_id(url)
            return feed_url, episode_id

        # Direct RSS feed (no episode ID)
        if self._is_direct_rss_feed(url):
            return url, None

        # Unknown platform
        feed_url = self._try_extract_from_html(url)
        return feed_url, None

    def _extract_apple_episode_id(self, url: str) -> str | None:
        """
        Extract episode ID from Apple Podcasts URL.

        Apple Podcasts episode URLs contain ?i=EPISODE_ID
        Example: https://podcasts.apple.com/.../id1702067155?i=1000734606759

        Args:
            url: Apple Podcasts URL

        Returns:
            Episode ID or None
        """
        # Extract episode ID from query parameter ?i=...
        episode_id_match = re.search(r"[?&]i=(\d+)", url)
        if episode_id_match:
            episode_id = episode_id_match.group(1)
            logger.info(f"Extracted Apple Podcasts episode ID: {episode_id}")
            return episode_id
        return None

    def _extract_rss_com_episode_id(self, url: str) -> str | None:
        """
        Extract episode ID from RSS.com URL.

        RSS.com episode URLs contain the episode ID in the path
        Example: https://rss.com/podcasts/zeihan/2296354/

        Args:
            url: RSS.com URL

        Returns:
            Episode ID or None
        """
        # Extract episode ID from URL path
        # Format: https://rss.com/podcasts/zeihan/2296354/
        episode_id_match = re.search(r"rss\.com/podcasts/[^/]+/(\d+)", url)
        if episode_id_match:
            episode_id = episode_id_match.group(1)
            logger.info(f"Extracted RSS.com episode ID: {episode_id}")
            return episode_id
        return None

    def extract_feed_url(self, url: str) -> str | None:
        """
        Extract raw RSS feed URL from podcast platform URL.

        Args:
            url: Podcast URL (Apple Podcasts, RSS.com, or direct RSS feed)

        Returns:
            Raw RSS feed URL, or None if extraction failed

        Examples:
            >>> extractor = RSSFeedExtractor()
            >>> extractor.extract_feed_url("https://podcasts.apple.com/us/podcast/id1702067155")
            "https://media.rss.com/zeihan/feed.xml"

            >>> extractor.extract_feed_url("https://rss.com/podcasts/zeihan/")
            "https://media.rss.com/zeihan/feed.xml"

            >>> extractor.extract_feed_url("https://feeds.megaphone.fm/hubermanlab")
            "https://feeds.megaphone.fm/hubermanlab"  # Pass-through
        """
        if not url:
            return None

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Apple Podcasts
        if "podcasts.apple.com" in domain:
            return self._extract_from_apple_podcasts(url)

        # RSS.com
        if "rss.com" in domain:
            return self._extract_from_rss_com(url)

        # Already a direct RSS feed (common patterns)
        if self._is_direct_rss_feed(url):
            logger.info(f"URL appears to be a direct RSS feed: {url[:60]}...")
            return url

        # Unknown platform - try to detect RSS feed in HTML
        logger.warning(f"Unknown podcast platform: {domain}")
        return self._try_extract_from_html(url)

    def _extract_from_apple_podcasts(self, url: str) -> str | None:
        """
        Extract RSS feed from Apple Podcasts URL.

        Apple Podcasts URLs contain a podcast ID (e.g., id1702067155).
        We can use Apple's lookup API to get the feed URL.

        Args:
            url: Apple Podcasts URL

        Returns:
            RSS feed URL or None
        """
        # Extract podcast ID from URL
        # Format: https://podcasts.apple.com/us/podcast/name/id1702067155
        podcast_id_match = re.search(r"id(\d+)", url)
        if not podcast_id_match:
            logger.warning(
                f"Could not extract podcast ID from Apple Podcasts URL: {url}"
            )
            return None

        podcast_id = podcast_id_match.group(1)
        logger.info(f"Extracted Apple Podcasts ID: {podcast_id}")

        # Use Apple's iTunes Search API to get feed URL
        try:
            api_url = f"https://itunes.apple.com/lookup?id={podcast_id}&entity=podcast"
            response = self.session.get(api_url, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("resultCount", 0) > 0:
                feed_url = data["results"][0].get("feedUrl")
                if feed_url:
                    logger.info(
                        f"✅ Found RSS feed for Apple Podcasts ID {podcast_id}: {feed_url[:60]}..."
                    )
                    return feed_url

            logger.warning(f"No RSS feed found for Apple Podcasts ID: {podcast_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch RSS feed from Apple Podcasts API: {e}")
            return None

    def _extract_from_rss_com(self, url: str) -> str | None:
        """
        Extract RSS feed from RSS.com URL.

        RSS.com URLs follow patterns:
        - https://rss.com/podcasts/{slug}/
        - https://rss.com/podcasts/{slug}/{episode-id}/

        The RSS feed is typically at:
        - https://media.rss.com/{slug}/feed.xml

        Args:
            url: RSS.com URL

        Returns:
            RSS feed URL or None
        """
        # Extract podcast slug from URL
        # Format: https://rss.com/podcasts/zeihan/ or https://rss.com/podcasts/zeihan/2296354/
        slug_match = re.search(r"rss\.com/podcasts/([^/]+)", url)
        if not slug_match:
            logger.warning(f"Could not extract podcast slug from RSS.com URL: {url}")
            return None

        slug = slug_match.group(1)
        logger.info(f"Extracted RSS.com slug: {slug}")

        # Construct RSS feed URL
        feed_url = f"https://media.rss.com/{slug}/feed.xml"

        # Verify the feed exists
        try:
            response = self.session.head(feed_url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                logger.info(
                    f"✅ Found RSS feed for RSS.com podcast '{slug}': {feed_url}"
                )
                return feed_url
            else:
                logger.warning(
                    f"RSS feed not found at expected URL: {feed_url} (status: {response.status_code})"
                )
                return None
        except Exception as e:
            logger.error(f"Failed to verify RSS.com feed URL: {e}")
            return None

    def _is_direct_rss_feed(self, url: str) -> bool:
        """
        Check if URL appears to be a direct RSS feed.

        Common RSS feed patterns:
        - Contains 'feed' in path
        - Ends with .xml or .rss
        - Common podcast CDN domains
        """
        url_lower = url.lower()

        # Common RSS feed patterns
        rss_patterns = [
            r"/feed",
            r"\.xml$",
            r"\.rss$",
            r"/rss",
        ]

        for pattern in rss_patterns:
            if re.search(pattern, url_lower):
                return True

        # Common podcast CDN domains
        podcast_cdns = [
            "feeds.megaphone.fm",
            "feeds.simplecast.com",
            "feeds.libsyn.com",
            "feeds.buzzsprout.com",
            "feeds.transistor.fm",
            "feeds.soundcloud.com",
            "anchor.fm",
            "media.rss.com",
        ]

        parsed = urlparse(url)
        if any(cdn in parsed.netloc.lower() for cdn in podcast_cdns):
            return True

        return False

    def _try_extract_from_html(self, url: str) -> str | None:
        """
        Try to extract RSS feed URL from HTML page.

        Looks for common RSS feed link patterns in HTML:
        - <link rel="alternate" type="application/rss+xml" href="...">
        - <a href="..." class="rss-link">

        Args:
            url: Web page URL

        Returns:
            RSS feed URL or None
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            html = response.text

            # Look for RSS feed link in HTML
            # Pattern: <link rel="alternate" type="application/rss+xml" href="FEED_URL">
            feed_link_match = re.search(
                r'<link[^>]+type=["\']application/rss\+xml["\'][^>]+href=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )

            if feed_link_match:
                feed_url = feed_link_match.group(1)
                logger.info(f"✅ Found RSS feed in HTML: {feed_url[:60]}...")
                return feed_url

            # Alternative pattern: href first, then type
            feed_link_match = re.search(
                r'<link[^>]+href=["\']([^"\']+)["\'][^>]+type=["\']application/rss\+xml["\']',
                html,
                re.IGNORECASE,
            )

            if feed_link_match:
                feed_url = feed_link_match.group(1)
                logger.info(f"✅ Found RSS feed in HTML: {feed_url[:60]}...")
                return feed_url

            logger.warning(f"No RSS feed link found in HTML: {url}")
            return None

        except Exception as e:
            logger.error(f"Failed to extract RSS feed from HTML: {e}")
            return None


# Convenience function
def extract_rss_feed_url(url: str) -> str | None:
    """
    Extract raw RSS feed URL from podcast platform URL.

    Args:
        url: Podcast URL (Apple Podcasts, RSS.com, or direct RSS feed)

    Returns:
        Raw RSS feed URL, or None if extraction failed
    """
    extractor = RSSFeedExtractor()
    return extractor.extract_feed_url(url)
