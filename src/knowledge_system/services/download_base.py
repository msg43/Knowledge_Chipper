"""
Base Download Coordinator

Provides common functionality for all download orchestrators:
- URL validation and parsing
- Progress callback standardization
- Cookie file management
- Video ID extraction

This eliminates duplication across 6 download-related classes.
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from ..database import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


class DownloadCoordinator(ABC):
    """Base class for download orchestrators with common functionality."""

    # YouTube URL patterns for video ID extraction
    YOUTUBE_PATTERNS = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
    ]

    def __init__(
        self,
        db_service: DatabaseService | None = None,
        progress_callback: Callable | None = None,
    ):
        """Initialize base coordinator."""
        self.db_service = db_service or DatabaseService()
        self.progress_callback = progress_callback

    @staticmethod
    def extract_youtube_video_id(url: str) -> str | None:
        """
        Extract YouTube video ID from URL.

        Supports:
        - youtube.com/watch?v=VIDEO_ID
        - youtu.be/VIDEO_ID
        - youtube.com/embed/VIDEO_ID
        - youtube.com/v/VIDEO_ID

        Returns:
            11-character video ID or None if not found
        """
        for pattern in DownloadCoordinator.YOUTUBE_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def validate_url(url: str) -> tuple[bool, str]:
        """
        Validate URL format.

        Returns:
            (is_valid, error_message) tuple
        """
        if not url or not isinstance(url, str):
            return (False, "URL must be a non-empty string")

        url = url.strip()

        if not url.startswith(("http://", "https://")):
            return (False, "URL must start with http:// or https://")

        if "youtube.com" not in url and "youtu.be" not in url:
            return (False, "Only YouTube URLs are supported")

        video_id = DownloadCoordinator.extract_youtube_video_id(url)
        if not video_id:
            return (False, "Could not extract video ID from URL")

        return (True, "")

    @staticmethod
    def validate_cookie_files(cookie_files: list[str]) -> tuple[bool, str, list[str]]:
        """
        Validate cookie files exist and are readable.

        Returns:
            (all_valid, error_message, valid_files) tuple
        """
        if not cookie_files:
            return (True, "", [])  # No cookies is valid

        valid_files = []
        missing_files = []

        for cookie_file in cookie_files:
            path = Path(cookie_file)
            if path.exists() and path.is_file():
                valid_files.append(cookie_file)
            else:
                missing_files.append(cookie_file)

        if missing_files:
            error = f"Cookie files not found: {', '.join(missing_files)}"
            return (False, error, valid_files)

        return (True, "", valid_files)

    def report_progress(self, stage: str, percent: float, context: str = "") -> None:
        """
        Report progress via callback if configured.

        Args:
            stage: Current stage name (e.g., "downloading", "processing")
            percent: Progress percentage (0-100)
            context: Additional context (e.g., video title, filename)
        """
        if self.progress_callback:
            try:
                self.progress_callback(stage, percent, context)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    @abstractmethod
    def download(self) -> dict:
        """
        Execute the download operation.

        Returns:
            Dictionary with download results
        """
        pass

    def validate_configuration(self) -> tuple[bool, str]:
        """
        Validate orchestrator configuration.

        Returns:
            (is_valid, error_message) tuple
        """
        return (True, "")  # Override in subclasses as needed
