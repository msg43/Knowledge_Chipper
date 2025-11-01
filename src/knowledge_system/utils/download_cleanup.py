"""
Startup cleanup and validation for partial downloads.

Scans the database for incomplete downloads, orphaned files, and validates
that audio files referenced in the database actually exist on disk.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..database.service import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


class DownloadCleanupService:
    """Service for cleaning up and validating partial downloads on startup."""

    def __init__(self, db_service: DatabaseService, output_dir: Path | None = None):
        """
        Initialize cleanup service.

        Args:
            db_service: Database service instance
            output_dir: Directory where audio files are stored (for orphan detection)
        """
        self.db_service = db_service
        self.output_dir = output_dir or Path("output")
        self.cleanup_report = {
            "timestamp": datetime.now().isoformat(),
            "orphaned_files_found": [],
            "missing_audio_files": [],
            "incomplete_videos": [],
            "failed_videos": [],
            "videos_needing_retry": [],
            "actions_taken": [],
        }

    def run_startup_validation(self) -> dict[str, Any]:
        """
        Run full startup validation and cleanup.

        Returns:
            Dictionary with cleanup report
        """
        logger.info("=" * 80)
        logger.info("STARTUP DOWNLOAD VALIDATION AND CLEANUP")
        logger.info("=" * 80)

        # Step 1: Validate audio files exist for database entries
        self._validate_audio_files()

        # Step 2: Find orphaned audio files (not in database)
        self._find_orphaned_files()

        # Step 3: Identify incomplete videos
        self._identify_incomplete_videos()

        # Step 4: Get failed videos (exceeded retry limit)
        self._get_failed_videos()

        # Step 5: Get videos needing retry
        self._get_videos_needing_retry()

        # Generate summary
        self._generate_summary()

        return self.cleanup_report

    def _validate_audio_files(self):
        """Validate that audio files in database actually exist on disk."""
        logger.info("Validating audio file existence...")

        try:
            with self.db_service.get_session() as session:
                from ..database import MediaSource

                # Get all videos with audio_file_path set (claim-centric schema doesn't track audio_downloaded)
                videos_with_audio = (
                    session.query(MediaSource)
                    .filter(MediaSource.audio_file_path.isnot(None))
                    .all()
                )

                for video in videos_with_audio:
                    audio_path = Path(video.audio_file_path)
                    if not audio_path.exists():
                        logger.warning(
                            f"Audio file missing for {video.source_id}: {video.audio_file_path}"
                        )
                        self.cleanup_report["missing_audio_files"].append(
                            {
                                "source_id": video.source_id,
                                "title": video.title,
                                "url": video.url,
                                "expected_path": video.audio_file_path,
                            }
                        )
                        # Note: Retry tracking not available in claim-centric schema

                logger.info(
                    f"Validated {len(videos_with_audio)} videos with audio paths. "
                    f"Found {len(self.cleanup_report['missing_audio_files'])} missing files."
                )

        except Exception as e:
            logger.error(f"Error validating audio files: {e}")

    def _find_orphaned_files(self):
        """Find audio files on disk that aren't referenced in database."""
        if not self.output_dir.exists():
            logger.info(
                f"Output directory {self.output_dir} doesn't exist, skipping orphan check"
            )
            return

        logger.info(f"Scanning for orphaned audio files in {self.output_dir}...")

        try:
            # Get all audio files in output directory
            audio_extensions = ["m4a", "opus", "webm", "ogg", "mp3", "aac", "wav"]
            audio_files = []
            for ext in audio_extensions:
                audio_files.extend(self.output_dir.rglob(f"*.{ext}"))

            # Get all audio file paths from database
            with self.db_service.get_session() as session:
                from ..database import MediaSource

                db_audio_paths = {
                    row[0]
                    for row in session.query(MediaSource.audio_file_path)
                    .filter(MediaSource.audio_file_path.isnot(None))
                    .all()
                }

            # Find orphans
            for audio_file in audio_files:
                audio_file_str = str(audio_file.absolute())
                if audio_file_str not in db_audio_paths:
                    # Also check relative path
                    audio_file_rel = str(audio_file)
                    if audio_file_rel not in db_audio_paths:
                        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
                        self.cleanup_report["orphaned_files_found"].append(
                            {
                                "path": audio_file_str,
                                "size_mb": round(file_size_mb, 2),
                                "modified": datetime.fromtimestamp(
                                    audio_file.stat().st_mtime
                                ).isoformat(),
                            }
                        )

            logger.info(
                f"Found {len(self.cleanup_report['orphaned_files_found'])} orphaned audio files"
            )

        except Exception as e:
            logger.error(f"Error finding orphaned files: {e}")

    def _identify_incomplete_videos(self):
        """Identify videos with partial downloads (missing audio or metadata)."""
        logger.info("Identifying incomplete videos...")

        try:
            incomplete = self.db_service.get_incomplete_videos()

            for video in incomplete:
                self.cleanup_report["incomplete_videos"].append(
                    {
                        "source_id": video.source_id,
                        "title": video.title,
                        "url": video.url,
                        # Note: Completion tracking columns not available in claim-centric schema
                    }
                )

            logger.info(f"Found {len(incomplete)} incomplete videos")

        except Exception as e:
            logger.error(f"Error identifying incomplete videos: {e}")

    def _get_failed_videos(self):
        """Get videos that exceeded max retry attempts."""
        logger.info("Getting failed videos (exceeded retry limit)...")

        try:
            failed = self.db_service.get_failed_videos()

            for video in failed:
                self.cleanup_report["failed_videos"].append(
                    {
                        "source_id": video.source_id,
                        "title": video.title,
                        "url": video.url,
                        # Note: Retry tracking columns not available in claim-centric schema
                    }
                )

            logger.info(f"Found {len(failed)} failed videos (exceeded retry limit)")

        except Exception as e:
            logger.error(f"Error getting failed videos: {e}")

    def _get_videos_needing_retry(self):
        """Get videos that need retry (haven't exceeded limit yet)."""
        logger.info("Getting videos needing retry...")

        try:
            needing_retry = self.db_service.get_videos_needing_retry()

            for video in needing_retry:
                self.cleanup_report["videos_needing_retry"].append(
                    {
                        "source_id": video.source_id,
                        "title": video.title,
                        "url": video.url,
                        # Note: Retry tracking columns not available in claim-centric schema
                    }
                )

            logger.info(f"Found {len(needing_retry)} videos needing retry")

        except Exception as e:
            logger.error(f"Error getting videos needing retry: {e}")

    def _generate_summary(self):
        """Generate and log summary of cleanup results."""
        logger.info("=" * 80)
        logger.info("CLEANUP SUMMARY")
        logger.info("=" * 80)
        logger.info(
            f"Missing audio files: {len(self.cleanup_report['missing_audio_files'])}"
        )
        logger.info(
            f"Orphaned audio files: {len(self.cleanup_report['orphaned_files_found'])}"
        )
        logger.info(
            f"Incomplete videos: {len(self.cleanup_report['incomplete_videos'])}"
        )
        logger.info(
            f"Videos needing retry: {len(self.cleanup_report['videos_needing_retry'])}"
        )
        logger.info(
            f"Failed videos (max retries): {len(self.cleanup_report['failed_videos'])}"
        )
        logger.info(f"Actions taken: {len(self.cleanup_report['actions_taken'])}")
        logger.info("=" * 80)

    def save_cleanup_report(self, output_path: Path | None = None):
        """
        Save cleanup report to JSON file.

        Args:
            output_path: Path to save report (defaults to logs/cleanup_report_TIMESTAMP.json)
        """
        if output_path is None:
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = logs_dir / f"cleanup_report_{timestamp}.json"

        try:
            with open(output_path, "w") as f:
                json.dump(self.cleanup_report, f, indent=2)
            logger.info(f"Saved cleanup report to: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to save cleanup report: {e}")
            return None

    def get_failed_urls_for_retry(self) -> list[str]:
        """
        Get list of URLs for failed videos that user can retry manually.

        Returns:
            List of URLs for failed videos
        """
        return [video["url"] for video in self.cleanup_report["failed_videos"]]

    def save_failed_urls_to_file(self, output_path: Path | None = None) -> Path | None:
        """
        Save failed URLs to a text file for easy copy-paste retry.

        Args:
            output_path: Path to save URLs (defaults to logs/failed_urls_TIMESTAMP.txt)

        Returns:
            Path to saved file or None if failed
        """
        if output_path is None:
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = logs_dir / f"failed_urls_{timestamp}.txt"

        try:
            failed_urls = self.get_failed_urls_for_retry()
            if not failed_urls:
                logger.info("No failed URLs to save")
                return None

            with open(output_path, "w") as f:
                f.write("# Failed Download URLs - Ready for Retry\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(
                    f"# Total: {len(failed_urls)} videos exceeded max retry attempts\n"
                )
                f.write("#\n")
                f.write(
                    "# Copy and paste these URLs back into the download tab to retry\n"
                )
                f.write("#\n\n")

                for url in failed_urls:
                    f.write(f"{url}\n")

            logger.info(f"Saved {len(failed_urls)} failed URLs to: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save failed URLs: {e}")
            return None
