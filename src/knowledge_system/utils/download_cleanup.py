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
            "incomplete_downloads": [],
            "failed_downloads": [],
            "downloads_needing_retry": [],
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

        # Step 3: Identify incomplete downloads
        self._identify_incomplete_downloads()

        # Step 4: Get failed downloads (exceeded retry limit)
        self._get_failed_downloads()

        # Step 5: Get downloads needing retry
        self._get_downloads_needing_retry()

        # Generate summary
        self._generate_summary()

        return self.cleanup_report

    def _validate_audio_files(self):
        """Validate that audio files in database actually exist on disk."""
        logger.info("Validating audio file existence...")

        try:
            with self.db_service.get_session() as session:
                from datetime import timedelta

                from ..database import MediaSource

                # Get all audio files with audio_file_path set (claim-centric schema doesn't track audio_downloaded)
                audio_downloads = (
                    session.query(MediaSource)
                    .filter(MediaSource.audio_file_path.isnot(None))
                    .all()
                )

                # Only warn about missing files from the last 30 days
                # Older entries are likely from moved/deleted files or old output directories
                cutoff_date = datetime.now() - timedelta(days=30)

                for download in audio_downloads:
                    audio_path = Path(download.audio_file_path)
                    if not audio_path.exists():
                        # Skip test files and temporary paths
                        if "/tmp/" in str(audio_path) or "test_" in download.source_id:
                            logger.debug(
                                f"Skipping test/temp file: {download.source_id} -> {download.audio_file_path}"
                            )
                            continue

                        # Only warn about recent entries (last 30 days)
                        if download.processed_at and download.processed_at < cutoff_date:
                            logger.debug(
                                f"Skipping old entry (>{cutoff_date.date()}): {download.source_id} -> {download.audio_file_path}"
                            )
                            continue

                        logger.warning(
                            f"Audio file missing for {download.source_id}: {download.audio_file_path}"
                        )
                        self.cleanup_report["missing_audio_files"].append(
                            {
                                "source_id": download.source_id,
                                "title": download.title,
                                "url": download.url,
                                "expected_path": download.audio_file_path,
                            }
                        )
                        # Note: Retry tracking not available in claim-centric schema

                logger.info(
                    f"Validated {len(audio_downloads)} audio files with paths. "
                    f"Found {len(self.cleanup_report['missing_audio_files'])} missing files (recent only, ignoring test/old entries)."
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

    def _identify_incomplete_downloads(self):
        """Identify downloads with partial completion (missing audio or metadata)."""
        logger.info("Identifying incomplete downloads...")

        try:
            incomplete = self.db_service.get_incomplete_videos()

            for download in incomplete:
                self.cleanup_report["incomplete_downloads"].append(
                    {
                        "source_id": download.source_id,
                        "title": download.title,
                        "url": download.url,
                        # Note: Completion tracking columns not available in claim-centric schema
                    }
                )

            logger.info(f"Found {len(incomplete)} incomplete downloads")

        except Exception as e:
            logger.error(f"Error identifying incomplete downloads: {e}")

    def _get_failed_downloads(self):
        """Get downloads that exceeded max retry attempts."""
        logger.info("Getting failed downloads (exceeded retry limit)...")

        try:
            failed = self.db_service.get_failed_videos()

            for download in failed:
                self.cleanup_report["failed_downloads"].append(
                    {
                        "source_id": download.source_id,
                        "title": download.title,
                        "url": download.url,
                        # Note: Retry tracking columns not available in claim-centric schema
                    }
                )

            logger.info(f"Found {len(failed)} failed downloads (exceeded retry limit)")

        except Exception as e:
            logger.error(f"Error getting failed downloads: {e}")

    def _get_downloads_needing_retry(self):
        """Get downloads that need retry (haven't exceeded limit yet)."""
        logger.info("Getting downloads needing retry...")

        try:
            needing_retry = self.db_service.get_videos_needing_retry()

            for download in needing_retry:
                self.cleanup_report["downloads_needing_retry"].append(
                    {
                        "source_id": download.source_id,
                        "title": download.title,
                        "url": download.url,
                        # Note: Retry tracking columns not available in claim-centric schema
                    }
                )

            logger.info(f"Found {len(needing_retry)} downloads needing retry")

        except Exception as e:
            logger.error(f"Error getting downloads needing retry: {e}")

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
            f"Incomplete downloads: {len(self.cleanup_report['incomplete_downloads'])}"
        )
        logger.info(
            f"Downloads needing retry: {len(self.cleanup_report['downloads_needing_retry'])}"
        )
        logger.info(
            f"Failed downloads (max retries): {len(self.cleanup_report['failed_downloads'])}"
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
        Get list of URLs for failed downloads that user can retry manually.

        Returns:
            List of URLs for failed downloads
        """
        return [download["url"] for download in self.cleanup_report["failed_downloads"]]

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
                    f"# Total: {len(failed_urls)} downloads exceeded max retry attempts\n"
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
