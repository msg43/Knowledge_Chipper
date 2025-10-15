"""
Browser Fingerprinting Utilities

Provides consistent, realistic browser headers and user agents across all YouTube processors
to avoid bot detection while maintaining the appearance of legitimate browser traffic.
"""

# Use basic logging instead of the full logger system to avoid dependencies
import logging
import random
from typing import Any, Dict

logger = logging.getLogger(__name__)


class BrowserFingerprint:
    """Manages consistent browser fingerprinting for YouTube requests."""

    # Realistic Chrome user agents (updated to current versions - October 2025)
    CHROME_USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    ]

    # Default user agent (most common)
    DEFAULT_USER_AGENT = CHROME_USER_AGENTS[0]

    def __init__(self, user_agent: str | None = None):
        """Initialize with a specific user agent or use default."""
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self._detect_platform_from_user_agent()

    def _detect_platform_from_user_agent(self):
        """Detect platform from user agent for consistent headers."""
        ua = self.user_agent.lower()
        if "macintosh" in ua:
            self.platform = "macOS"
            self.sec_ch_ua_platform = '"macOS"'
        elif "windows" in ua:
            self.platform = "Windows"
            self.sec_ch_ua_platform = '"Windows"'
        elif "linux" in ua:
            self.platform = "Linux"
            self.sec_ch_ua_platform = '"Linux"'
        else:
            self.platform = "Unknown"
            self.sec_ch_ua_platform = '"Unknown"'

    def get_standard_headers(self) -> dict[str, str]:
        """Get complete, realistic browser headers."""
        return {
            # Standard headers
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            # Connection headers
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            # Chrome client hints (modern browsers send these)
            "Sec-Ch-Ua": '"Google Chrome";v="120", "Chromium";v="120", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": self.sec_ch_ua_platform,
            # Cache control
            "Cache-Control": "max-age=0",
        }

    def get_yt_dlp_headers(self) -> dict[str, str]:
        """Get headers formatted for yt-dlp http_headers option."""
        return self.get_standard_headers()

    def get_requests_headers(self) -> dict[str, str]:
        """Get headers formatted for requests library."""
        return self.get_standard_headers()

    @classmethod
    def get_random_fingerprint(cls) -> "BrowserFingerprint":
        """Get a random browser fingerprint for variety."""
        user_agent = random.choice(cls.CHROME_USER_AGENTS)
        return cls(user_agent)

    @classmethod
    def get_default_fingerprint(cls) -> "BrowserFingerprint":
        """Get the default browser fingerprint for consistency."""
        return cls()


# Global fingerprint instance for consistency across the application
_global_fingerprint: BrowserFingerprint | None = None


def get_global_browser_fingerprint() -> BrowserFingerprint:
    """Get the global browser fingerprint instance."""
    global _global_fingerprint
    if _global_fingerprint is None:
        _global_fingerprint = BrowserFingerprint.get_default_fingerprint()
        logger.info(
            f"Initialized global browser fingerprint: {_global_fingerprint.platform}"
        )
    return _global_fingerprint


def get_standard_yt_dlp_headers() -> dict[str, str]:
    """Get standardized headers for yt-dlp requests."""
    fingerprint = get_global_browser_fingerprint()
    return fingerprint.get_yt_dlp_headers()


def get_standard_requests_headers() -> dict[str, str]:
    """Get standardized headers for requests library."""
    fingerprint = get_global_browser_fingerprint()
    return fingerprint.get_requests_headers()


def get_standard_user_agent() -> str:
    """Get the standardized user agent string."""
    fingerprint = get_global_browser_fingerprint()
    return fingerprint.user_agent
