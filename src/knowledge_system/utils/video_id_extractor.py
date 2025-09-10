"""
Unified Video ID Extraction Utility

Provides a robust, consistent method for extracting YouTube video IDs from various URL formats.
Handles edge cases and validates results to ensure 100% reliable video_id capture.
"""

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

from ..logger import get_logger

logger = get_logger(__name__)


class VideoIDExtractor:
    """
    Unified video ID extractor with comprehensive URL format support and validation.
    """

    # YouTube video ID is always exactly 11 characters: [a-zA-Z0-9_-]
    YOUTUBE_VIDEO_ID_LENGTH = 11
    YOUTUBE_VIDEO_ID_PATTERN = r"^[a-zA-Z0-9_-]{11}$"

    # Comprehensive patterns for all YouTube URL formats
    URL_PATTERNS = [
        # Standard watch URLs
        r"(?:youtube\.com|m\.youtube\.com)/watch\?.*[?&]v=([a-zA-Z0-9_-]{11})",
        # Short URLs
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        # Embed URLs
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        # Old-style v/ URLs
        r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
        # YouTube shorts
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        # Gaming URLs
        r"gaming\.youtube\.com/watch\?.*[?&]v=([a-zA-Z0-9_-]{11})",
        # Music URLs
        r"music\.youtube\.com/watch\?.*[?&]v=([a-zA-Z0-9_-]{11})",
    ]

    @classmethod
    def extract_video_id(cls, url: str) -> str | None:
        """
        Extract YouTube video ID from URL with comprehensive format support.

        Args:
            url: YouTube URL in any supported format

        Returns:
            11-character video ID if valid, None otherwise
        """
        if not url or not isinstance(url, str):
            logger.debug(f"Invalid URL input: {type(url)} - {url}")
            return None

        url = url.strip()
        if not url:
            return None

        # Method 1: Try regex patterns (most reliable)
        video_id = cls._extract_with_patterns(url)
        if video_id:
            return video_id

        # Method 2: Try URL parsing (handles complex query strings)
        video_id = cls._extract_with_url_parsing(url)
        if video_id:
            return video_id

        # Method 3: Check if it's already a video ID
        if cls._is_valid_video_id(url):
            return url

        logger.debug(f"Could not extract video ID from URL: {url}")
        return None

    @classmethod
    def _extract_with_patterns(cls, url: str) -> str | None:
        """Extract video ID using regex patterns."""
        for pattern in cls.URL_PATTERNS:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                video_id = match.group(1)
                if cls._is_valid_video_id(video_id):
                    return video_id
        return None

    @classmethod
    def _extract_with_url_parsing(cls, url: str) -> str | None:
        """Extract video ID using URL parsing (handles complex query strings)."""
        try:
            # Handle URLs without protocol
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            parsed = urlparse(url)

            # Check if it's a YouTube domain
            if not any(
                domain in parsed.netloc.lower()
                for domain in [
                    "youtube.com",
                    "youtu.be",
                    "m.youtube.com",
                    "gaming.youtube.com",
                    "music.youtube.com",
                ]
            ):
                return None

            # Handle youtu.be short URLs
            if "youtu.be" in parsed.netloc:
                path_parts = parsed.path.strip("/").split("/")
                if path_parts and cls._is_valid_video_id(path_parts[0]):
                    return path_parts[0]

            # Handle query parameters
            query_params = parse_qs(parsed.query)
            if "v" in query_params:
                video_id = query_params["v"][0]
                if cls._is_valid_video_id(video_id):
                    return video_id

            # Handle path-based formats (/embed/, /v/, /shorts/)
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) >= 2:
                if path_parts[0] in ["embed", "v", "shorts"]:
                    video_id = path_parts[1]
                    if cls._is_valid_video_id(video_id):
                        return video_id

        except Exception as e:
            logger.debug(f"URL parsing failed for {url}: {e}")

        return None

    @classmethod
    def _is_valid_video_id(cls, video_id: str) -> bool:
        """
        Validate that a string is a valid YouTube video ID.

        Args:
            video_id: String to validate

        Returns:
            True if valid YouTube video ID format
        """
        if not video_id or not isinstance(video_id, str):
            return False

        # Must be exactly 11 characters
        if len(video_id) != cls.YOUTUBE_VIDEO_ID_LENGTH:
            return False

        # Must match YouTube video ID pattern
        return bool(re.match(cls.YOUTUBE_VIDEO_ID_PATTERN, video_id))

    @classmethod
    def extract_and_validate(
        cls, url: str, strict: bool = True
    ) -> tuple[str | None, list[str]]:
        """
        Extract video ID with detailed validation and error reporting.

        Args:
            url: YouTube URL to extract from
            strict: If True, apply strict validation

        Returns:
            Tuple of (video_id, list_of_warnings)
        """
        warnings = []

        if not url:
            warnings.append("Empty URL provided")
            return None, warnings

        if not isinstance(url, str):
            warnings.append(f"URL is not a string: {type(url)}")
            url = str(url)

        video_id = cls.extract_video_id(url)

        if not video_id:
            warnings.append(f"Could not extract video ID from URL: {url}")
            return None, warnings

        if strict:
            # Additional strict validation
            if not cls._is_valid_video_id(video_id):
                warnings.append(
                    f"Extracted ID '{video_id}' is not a valid YouTube video ID"
                )
                return None, warnings

        return video_id, warnings


# Convenience functions for backward compatibility
def extract_video_id_from_url(url: str) -> str | None:
    """
    Extract YouTube video ID from URL.

    Args:
        url: YouTube URL

    Returns:
        Video ID if found, None otherwise
    """
    return VideoIDExtractor.extract_video_id(url)


def is_valid_youtube_video_id(video_id: str) -> bool:
    """
    Check if a string is a valid YouTube video ID.

    Args:
        video_id: String to validate

    Returns:
        True if valid YouTube video ID
    """
    return VideoIDExtractor._is_valid_video_id(video_id)


def extract_video_id_with_validation(url: str) -> tuple[str | None, list[str]]:
    """
    Extract video ID with detailed validation and warnings.

    Args:
        url: YouTube URL

    Returns:
        Tuple of (video_id, warnings_list)
    """
    return VideoIDExtractor.extract_and_validate(url)
