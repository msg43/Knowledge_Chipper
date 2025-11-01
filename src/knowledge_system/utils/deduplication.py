"""
Video deduplication service for Knowledge System.

Provides deduplication logic to prevent reprocessing YouTube videos that already
exist in the SQLite database, optimizing costs and reducing redundant work.
"""

import re
from enum import Enum
from urllib.parse import parse_qs, urlparse

from ..database import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


class DuplicationPolicy(Enum):
    """Policies for handling duplicate videos."""

    SKIP_ALL = "skip_all"  # Skip all duplicates, never reprocess
    ALLOW_RETRANSCRIBE = (
        "allow_retranscribe"  # Allow retranscription with different settings
    )
    ALLOW_RESUMMARY = (
        "allow_resummary"  # Allow resummary with different models/templates
    )
    FORCE_REPROCESS = (
        "force_reprocess"  # Force reprocessing regardless of existing data
    )


class DeduplicationResult:
    """Result of deduplication check."""

    def __init__(
        self,
        source_id: str,
        is_duplicate: bool,
        existing_video: dict | None = None,
        skip_reason: str | None = None,
        recommendations: list[str] | None = None,
    ):
        self.source_id = source_id
        self.is_duplicate = is_duplicate
        self.existing_video = existing_video
        self.skip_reason = skip_reason
        self.recommendations = recommendations or []


class VideoDeduplicationService:
    """
    Service for detecting and handling duplicate YouTube videos.

    Integrates with SQLite database to track processed videos and provides
    intelligent deduplication based on processing history and user preferences.
    """

    def __init__(self, database_service: DatabaseService | None = None):
        """Initialize deduplication service."""
        self.db = database_service or DatabaseService()
        self._video_cache = {}  # Cache for recently checked videos

    def extract_video_id(self, url: str) -> str | None:
        """
        Extract YouTube video ID from various URL formats.

        Args:
            url: YouTube URL in any format

        Returns:
            Video ID if found, None otherwise
        """
        if not url:
            return None

        # Handle various YouTube URL formats
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
            r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
            r"^([a-zA-Z0-9_-]{11})$",  # Direct video ID
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # Try parsing as URL with query parameters
        try:
            parsed = urlparse(url)
            if "v" in parse_qs(parsed.query):
                source_id = parse_qs(parsed.query)["v"][0]
                if len(source_id) == 11:
                    return source_id
        except Exception:
            pass

        return None

    def check_duplicate(
        self,
        url: str,
        policy: DuplicationPolicy = DuplicationPolicy.SKIP_ALL,
        force_check: bool = False,
    ) -> DeduplicationResult:
        """
        Check if a video is a duplicate and should be skipped.

        Args:
            url: YouTube URL to check
            policy: Deduplication policy to apply
            force_check: Force database check even if cached

        Returns:
            DeduplicationResult with duplicate status and recommendations
        """
        source_id = self.extract_video_id(url)
        if not source_id:
            return DeduplicationResult(
                source_id="unknown",
                is_duplicate=False,
                skip_reason="Could not extract video ID from URL",
            )

        # Check cache first (unless force_check)
        if not force_check and source_id in self._video_cache:
            cached_result = self._video_cache[source_id]
            logger.debug(f"Using cached result for video {source_id}")
            return cached_result

        # Check database for existing video
        existing_video = self.db.get_video(source_id)

        if not existing_video:
            # Video not in database - not a duplicate
            result = DeduplicationResult(source_id=source_id, is_duplicate=False)
            self._video_cache[source_id] = result
            return result

        # Video exists - apply deduplication policy
        result = self._apply_policy(source_id, existing_video, policy)
        self._video_cache[source_id] = result

        return result

    def _apply_policy(
        self, source_id: str, existing_video, policy: DuplicationPolicy
    ) -> DeduplicationResult:
        """Apply deduplication policy to existing video."""

        # Convert SQLAlchemy object to dict for easier handling
        # Use source_id (claim-centric schema) instead of source_id
        video_data = {
            "source_id": existing_video.source_id,
            "title": existing_video.title,
            "status": existing_video.status,
            "processed_at": existing_video.processed_at,
            "audio_downloaded": getattr(existing_video, "audio_downloaded", False),
            "metadata_complete": getattr(existing_video, "metadata_complete", False),
        }

        # CRITICAL: Check if video is actually complete (has both audio and metadata)
        # Partial downloads should NOT be considered duplicates
        is_complete = getattr(existing_video, "audio_downloaded", False) and getattr(
            existing_video, "metadata_complete", False
        )

        if not is_complete:
            # Video exists but is incomplete - allow reprocessing
            logger.info(
                f"Video {source_id} exists but is incomplete "
                f"(audio={getattr(existing_video, 'audio_downloaded', False)}, "
                f"metadata={getattr(existing_video, 'metadata_complete', False)}). "
                "Allowing reprocessing."
            )
            return DeduplicationResult(
                source_id=source_id,
                is_duplicate=False,  # Not a duplicate - needs completion
                existing_video=video_data,
                recommendations=[
                    "Video has partial download - will attempt to complete",
                    f"Missing: {'audio' if not getattr(existing_video, 'audio_downloaded', False) else ''}"
                    f"{' and ' if not getattr(existing_video, 'audio_downloaded', False) and not getattr(existing_video, 'metadata_complete', False) else ''}"
                    f"{'metadata' if not getattr(existing_video, 'metadata_complete', False) else ''}",
                ],
            )

        if policy == DuplicationPolicy.FORCE_REPROCESS:
            return DeduplicationResult(
                source_id=source_id,
                is_duplicate=False,  # Allow reprocessing
                existing_video=video_data,
                recommendations=["Video will be reprocessed (force mode)"],
            )

        if policy == DuplicationPolicy.SKIP_ALL:
            return DeduplicationResult(
                source_id=source_id,
                is_duplicate=True,
                existing_video=video_data,
                skip_reason=f"Video already processed on {existing_video.processed_at}",
                recommendations=[
                    "Use --force flag to reprocess anyway",
                    "Check existing files in output directory",
                ],
            )

        # For ALLOW_RETRANSCRIBE and ALLOW_RESUMMARY, check what processing exists
        transcripts = self.db.get_transcripts_for_video(source_id)
        summaries = self.db.get_summaries_for_video(source_id)

        recommendations = []

        if policy == DuplicationPolicy.ALLOW_RETRANSCRIBE:
            if transcripts:
                recommendations.append(
                    f"Found {len(transcripts)} existing transcript(s)"
                )
                recommendations.append(
                    "Use different transcription settings to create new transcript"
                )
            else:
                recommendations.append("No transcripts found - transcription allowed")

        if policy == DuplicationPolicy.ALLOW_RESUMMARY:
            if summaries:
                recommendations.append(f"Found {len(summaries)} existing summary(ies)")
                recommendations.append(
                    "Use different model/template to create new summary"
                )
            else:
                recommendations.append("No summaries found - summarization allowed")

        # Determine if should skip based on what already exists
        should_skip = False
        skip_reason = None

        if policy == DuplicationPolicy.ALLOW_RETRANSCRIBE and transcripts:
            should_skip = True
            skip_reason = (
                "Transcripts already exist (use different settings or force mode)"
            )
        elif policy == DuplicationPolicy.ALLOW_RESUMMARY and summaries:
            should_skip = True
            skip_reason = (
                "Summaries already exist (use different model/template or force mode)"
            )

        return DeduplicationResult(
            source_id=source_id,
            is_duplicate=should_skip,
            existing_video=video_data,
            skip_reason=skip_reason,
            recommendations=recommendations,
        )

    def check_batch_duplicates(
        self, urls: list[str], policy: DuplicationPolicy = DuplicationPolicy.SKIP_ALL
    ) -> tuple[list[str], list[DeduplicationResult]]:
        """
        Check a batch of URLs for duplicates.

        Args:
            urls: List of YouTube URLs to check
            policy: Deduplication policy to apply

        Returns:
            Tuple of (unique_urls, duplicate_results)
        """
        unique_urls = []
        duplicate_results = []

        for url in urls:
            result = self.check_duplicate(url, policy)

            if result.is_duplicate:
                duplicate_results.append(result)
                logger.info(
                    f"Skipping duplicate video {result.source_id}: {result.skip_reason}"
                )
            else:
                unique_urls.append(url)

        logger.info(
            f"Deduplication complete: {len(unique_urls)} unique, {len(duplicate_results)} duplicates"
        )
        return unique_urls, duplicate_results

    def get_duplicate_statistics(self) -> dict[str, any]:
        """Get statistics about duplicate detection and savings."""
        try:
            stats = self.db.get_processing_stats()

            # Calculate potential cost savings from deduplication
            total_videos = stats.get("total_videos", 0)
            stats.get("completed_videos", 0)
            avg_cost_per_video = stats.get("average_cost_per_video", 0)

            # Estimate savings (this would be more accurate with actual duplicate counts)
            estimated_duplicate_rate = 0.15  # Assume 15% duplicate rate
            estimated_duplicates_prevented = int(
                total_videos * estimated_duplicate_rate
            )
            estimated_cost_savings = estimated_duplicates_prevented * avg_cost_per_video

            return {
                "total_videos_checked": total_videos,
                "estimated_duplicates_prevented": estimated_duplicates_prevented,
                "estimated_cost_savings": estimated_cost_savings,
                "duplicate_rate_estimate": estimated_duplicate_rate,
                "cache_size": len(self._video_cache),
            }
        except Exception as e:
            logger.error(f"Failed to get duplicate statistics: {e}")
            return {}

    def clear_cache(self) -> None:
        """Clear the video cache."""
        self._video_cache.clear()
        logger.info("Deduplication cache cleared")

    def add_video_to_database(
        self, source_id: str, title: str, url: str, **metadata
    ) -> bool:
        """
        Add a video to the database for future deduplication.

        Args:
            source_id: YouTube video ID
            title: Video title
            url: Original URL
            **metadata: Additional video metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            video = self.db.create_video(
                source_id=source_id, title=title, url=url, **metadata
            )

            if video:
                # Update cache
                self._video_cache[source_id] = DeduplicationResult(
                    source_id=source_id,
                    is_duplicate=True,
                    existing_video={
                        "source_id": source_id,
                        "title": title,
                        "status": "processing",
                        "processed_at": "now",
                    },
                )
                logger.info(
                    f"Added video {source_id} to database for deduplication tracking"
                )
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to add video {source_id} to database: {e}")
            return False


# Convenience functions for easy integration
def check_video_duplicate(
    url: str, policy: DuplicationPolicy = DuplicationPolicy.SKIP_ALL
) -> DeduplicationResult:
    """Convenience function to check if a single video is a duplicate."""
    service = VideoDeduplicationService()
    return service.check_duplicate(url, policy)


def filter_duplicate_urls(
    urls: list[str], policy: DuplicationPolicy = DuplicationPolicy.SKIP_ALL
) -> tuple[list[str], list[DeduplicationResult]]:
    """Convenience function to filter duplicate URLs from a list."""
    service = VideoDeduplicationService()
    return service.check_batch_duplicates(urls, policy)


def extract_video_id_from_url(url: str) -> str | None:
    """Convenience function to extract video ID from URL."""
    service = VideoDeduplicationService()
    return service.extract_video_id(url)
