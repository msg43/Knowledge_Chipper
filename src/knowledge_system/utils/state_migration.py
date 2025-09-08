"""
State migration utility for Knowledge System.

Migrates legacy JSON-based state files to the new SQLite database architecture.
Handles application state, progress checkpoints, GUI sessions, and processing history.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..database import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


class StateMigrator:
    """
    Utility for migrating legacy JSON state files to SQLite database.

    Handles migration of:
    - application_state.json - General application state and settings
    - progress checkpoints - Processing job progress and resume data
    - gui_session.json - GUI session state and user preferences
    - processing history - Historical processing results and metadata
    """

    def __init__(
        self,
        database_service: DatabaseService | None = None,
        legacy_state_dir: Path | None = None,
    ):
        """Initialize state migrator."""
        self.db = database_service or DatabaseService()
        self.legacy_state_dir = (
            Path(legacy_state_dir) if legacy_state_dir else Path("state")
        )

        # Common legacy file paths
        self.legacy_files = {
            "application_state": self.legacy_state_dir / "application_state.json",
            "progress_checkpoints": self.legacy_state_dir / "progress_checkpoints.json",
            "gui_session": self.legacy_state_dir / "gui_session.json",
            "processing_history": self.legacy_state_dir / "processing_history.json",
            "video_metadata": self.legacy_state_dir / "video_metadata.json",
            "job_queue": self.legacy_state_dir / "job_queue.json",
        }

    def migrate_all_state(self, backup_legacy: bool = True) -> dict[str, Any]:
        """
        Migrate all legacy state files to SQLite database.

        Args:
            backup_legacy: Whether to backup legacy files before migration

        Returns:
            Dictionary with migration results for each file type
        """
        migration_results = {
            "started_at": datetime.utcnow().isoformat(),
            "files_processed": {},
            "total_records_migrated": 0,
            "errors": [],
            "warnings": [],
        }

        try:
            # Backup legacy files if requested
            if backup_legacy:
                self._backup_legacy_files()
                migration_results["backup_created"] = True

            # Migrate each type of state file
            migration_functions = {
                "application_state": self._migrate_application_state,
                "progress_checkpoints": self._migrate_progress_checkpoints,
                "gui_session": self._migrate_gui_session,
                "processing_history": self._migrate_processing_history,
                "video_metadata": self._migrate_video_metadata,
                "job_queue": self._migrate_job_queue,
            }

            for file_type, migrate_func in migration_functions.items():
                try:
                    result = migrate_func()
                    migration_results["files_processed"][file_type] = result
                    migration_results["total_records_migrated"] += result.get(
                        "records_migrated", 0
                    )

                    if result.get("warnings"):
                        migration_results["warnings"].extend(result["warnings"])

                except Exception as e:
                    error_msg = f"Failed to migrate {file_type}: {e}"
                    logger.error(error_msg)
                    migration_results["errors"].append(error_msg)
                    migration_results["files_processed"][file_type] = {
                        "success": False,
                        "error": str(e),
                    }

            migration_results["completed_at"] = datetime.utcnow().isoformat()
            migration_results["success"] = len(migration_results["errors"]) == 0

            # Log migration summary
            if migration_results["success"]:
                logger.info("✅ State migration completed successfully")
                logger.info(
                    f"   Total records migrated: {migration_results['total_records_migrated']}"
                )
                logger.info(
                    f"   Files processed: {len(migration_results['files_processed'])}"
                )
            else:
                logger.warning("⚠️ State migration completed with errors")
                logger.warning(f"   Errors: {len(migration_results['errors'])}")
                logger.warning(f"   Warnings: {len(migration_results['warnings'])}")

            return migration_results

        except Exception as e:
            error_msg = f"Critical migration error: {e}"
            logger.error(error_msg)
            migration_results["success"] = False
            migration_results["errors"].append(error_msg)
            return migration_results

    def _backup_legacy_files(self) -> None:
        """Create backup copies of legacy state files."""
        backup_dir = (
            self.legacy_state_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        backup_dir.mkdir(exist_ok=True)

        backed_up_count = 0
        for file_type, file_path in self.legacy_files.items():
            if file_path.exists():
                backup_path = backup_dir / file_path.name
                backup_path.write_text(file_path.read_text())
                backed_up_count += 1
                logger.info(f"Backed up {file_path} to {backup_path}")

        logger.info(
            f"Created backup of {backed_up_count} legacy state files in {backup_dir}"
        )

    def _migrate_application_state(self) -> dict[str, Any]:
        """Migrate application_state.json to database."""
        file_path = self.legacy_files["application_state"]
        result = {"success": False, "records_migrated": 0, "warnings": []}

        if not file_path.exists():
            result.update(
                {"success": True, "message": "No legacy application state found"}
            )
            return result

        try:
            with open(file_path) as f:
                app_state = json.load(f)

            # Extract useful state information
            last_session = app_state.get("last_session", {})
            user_preferences = app_state.get("user_preferences", {})
            system_stats = app_state.get("system_stats", {})

            # Create a general processing job record for historical tracking
            if last_session:
                job_id = str(uuid.uuid4())
                self.db.create_processing_job(
                    job_type="legacy_migration",
                    input_urls=[],
                    config={
                        "source": "application_state.json",
                        "last_session": last_session,
                        "user_preferences": user_preferences,
                        "system_stats": system_stats,
                    },
                )

                # Mark as completed since it's historical
                self.db.update_job_progress(
                    job_id=job_id, status="completed", completed_at=datetime.utcnow()
                )

                result["records_migrated"] = 1

            result["success"] = True
            logger.info(f"Migrated application state from {file_path}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to migrate application state: {e}")

        return result

    def _migrate_progress_checkpoints(self) -> dict[str, Any]:
        """Migrate progress checkpoints to database job tracking."""
        file_path = self.legacy_files["progress_checkpoints"]
        result = {"success": False, "records_migrated": 0, "warnings": []}

        if not file_path.exists():
            result.update(
                {"success": True, "message": "No legacy progress checkpoints found"}
            )
            return result

        try:
            with open(file_path) as f:
                checkpoints = json.load(f)

            migrated_count = 0
            for checkpoint_id, checkpoint_data in checkpoints.items():
                try:
                    # Create processing job from checkpoint data
                    job_type = checkpoint_data.get("job_type", "unknown")
                    input_urls = checkpoint_data.get("input_urls", [])
                    config = checkpoint_data.get("config", {})

                    job = self.db.create_processing_job(
                        job_type=job_type, input_urls=input_urls, config=config
                    )

                    if job:
                        # Update with checkpoint progress
                        progress = checkpoint_data.get("progress", {})
                        self.db.update_job_progress(
                            job_id=job.job_id,
                            status=checkpoint_data.get("status", "unknown"),
                            completed_items=progress.get("completed", 0),
                            failed_items=progress.get("failed", 0),
                            total_cost=checkpoint_data.get("total_cost", 0.0),
                            total_tokens=checkpoint_data.get("total_tokens", 0),
                        )

                        migrated_count += 1
                        logger.debug(
                            f"Migrated checkpoint {checkpoint_id} to job {job.job_id}"
                        )

                except Exception as checkpoint_error:
                    warning = f"Failed to migrate checkpoint {checkpoint_id}: {checkpoint_error}"
                    result["warnings"].append(warning)
                    logger.warning(warning)

            result.update(
                {
                    "success": True,
                    "records_migrated": migrated_count,
                    "message": f"Migrated {migrated_count} progress checkpoints",
                }
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to migrate progress checkpoints: {e}")

        return result

    def _migrate_gui_session(self) -> dict[str, Any]:
        """Migrate GUI session state to database."""
        file_path = self.legacy_files["gui_session"]
        result = {"success": False, "records_migrated": 0, "warnings": []}

        if not file_path.exists():
            result.update({"success": True, "message": "No legacy GUI session found"})
            return result

        try:
            with open(file_path) as f:
                gui_session = json.load(f)

            # Store GUI session as a special processing job for tracking
            str(uuid.uuid4())
            job = self.db.create_processing_job(
                job_type="gui_session_migration",
                input_urls=[],
                config={
                    "source": "gui_session.json",
                    "session_data": gui_session,
                    "migrated_at": datetime.utcnow().isoformat(),
                },
            )

            if job:
                self.db.update_job_progress(
                    job_id=job.job_id,
                    status="completed",
                    completed_at=datetime.utcnow(),
                )
                result["records_migrated"] = 1

            result.update({"success": True, "message": "Migrated GUI session state"})

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to migrate GUI session: {e}")

        return result

    def _migrate_processing_history(self) -> dict[str, Any]:
        """Migrate processing history to database video records."""
        file_path = self.legacy_files["processing_history"]
        result = {"success": False, "records_migrated": 0, "warnings": []}

        if not file_path.exists():
            result.update(
                {"success": True, "message": "No legacy processing history found"}
            )
            return result

        try:
            with open(file_path) as f:
                history = json.load(f)

            migrated_count = 0
            for record_id, record_data in history.items():
                try:
                    # Extract video information
                    video_id = record_data.get("video_id")
                    url = record_data.get("url")
                    title = record_data.get("title", "Unknown Title")

                    if video_id and url:
                        # Create video record
                        video = self.db.create_video(
                            video_id=video_id,
                            title=title,
                            url=url,
                            uploader=record_data.get("uploader"),
                            duration_seconds=record_data.get("duration_seconds"),
                            upload_date=record_data.get("upload_date"),
                            status="completed",
                            extraction_method="legacy_migration",
                        )

                        if video:
                            migrated_count += 1

                            # Migrate transcript if available
                            if "transcript" in record_data:
                                transcript_data = record_data["transcript"]
                                self.db.create_transcript(
                                    video_id=video_id,
                                    language=transcript_data.get("language", "en"),
                                    transcript_text=transcript_data.get("text", ""),
                                    transcript_type="legacy_migration",
                                )

                            # Migrate summary if available
                            if "summary" in record_data:
                                summary_data = record_data["summary"]
                                self.db.create_summary(
                                    video_id=video_id,
                                    summary_text=summary_data.get("text", ""),
                                    llm_model=summary_data.get("model", "unknown"),
                                    processing_cost=summary_data.get("cost", 0.0),
                                )

                        logger.debug(f"Migrated processing record for video {video_id}")

                except Exception as record_error:
                    warning = f"Failed to migrate processing record {record_id}: {record_error}"
                    result["warnings"].append(warning)
                    logger.warning(warning)

            result.update(
                {
                    "success": True,
                    "records_migrated": migrated_count,
                    "message": f"Migrated {migrated_count} processing history records",
                }
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to migrate processing history: {e}")

        return result

    def _migrate_video_metadata(self) -> dict[str, Any]:
        """Migrate video metadata files to database."""
        file_path = self.legacy_files["video_metadata"]
        result = {"success": False, "records_migrated": 0, "warnings": []}

        if not file_path.exists():
            result.update(
                {"success": True, "message": "No legacy video metadata found"}
            )
            return result

        try:
            with open(file_path) as f:
                metadata = json.load(f)

            migrated_count = 0
            for video_id, video_data in metadata.items():
                try:
                    # Check if video already exists (avoid duplicates)
                    existing_video = self.db.get_video(video_id)
                    if existing_video:
                        logger.debug(f"Video {video_id} already exists, skipping")
                        continue

                    # Create video record from metadata
                    video = self.db.create_video(
                        video_id=video_id,
                        title=video_data.get("title", "Unknown Title"),
                        url=video_data.get(
                            "url", f"https://youtube.com/watch?v={video_id}"
                        ),
                        uploader=video_data.get("uploader"),
                        duration_seconds=video_data.get("duration"),
                        upload_date=video_data.get("upload_date"),
                        description=video_data.get("description"),
                        status="completed",
                        extraction_method="metadata_migration",
                    )

                    if video:
                        migrated_count += 1
                        logger.debug(f"Migrated metadata for video {video_id}")

                except Exception as video_error:
                    warning = f"Failed to migrate metadata for video {video_id}: {video_error}"
                    result["warnings"].append(warning)
                    logger.warning(warning)

            result.update(
                {
                    "success": True,
                    "records_migrated": migrated_count,
                    "message": f"Migrated {migrated_count} video metadata records",
                }
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to migrate video metadata: {e}")

        return result

    def _migrate_job_queue(self) -> dict[str, Any]:
        """Migrate job queue to database processing jobs."""
        file_path = self.legacy_files["job_queue"]
        result = {"success": False, "records_migrated": 0, "warnings": []}

        if not file_path.exists():
            result.update({"success": True, "message": "No legacy job queue found"})
            return result

        try:
            with open(file_path) as f:
                job_queue = json.load(f)

            migrated_count = 0
            for job_id, job_data in job_queue.items():
                try:
                    # Create processing job
                    job = self.db.create_processing_job(
                        job_type=job_data.get("type", "unknown"),
                        input_urls=job_data.get("urls", []),
                        config=job_data.get("config", {}),
                    )

                    if job:
                        # Update job status
                        status = job_data.get("status", "pending")
                        if status == "completed":
                            self.db.update_job_progress(
                                job_id=job.job_id,
                                status="completed",
                                completed_items=job_data.get("completed_items", 0),
                                total_cost=job_data.get("total_cost", 0.0),
                                completed_at=datetime.utcnow(),
                            )
                        elif status == "failed":
                            self.db.update_job_progress(
                                job_id=job.job_id,
                                status="failed",
                                error_message=job_data.get(
                                    "error", "Legacy job failed"
                                ),
                                completed_at=datetime.utcnow(),
                            )
                        else:
                            self.db.update_job_progress(
                                job_id=job.job_id, status=status
                            )

                        migrated_count += 1
                        logger.debug(f"Migrated job queue item {job_id}")

                except Exception as job_error:
                    warning = f"Failed to migrate job {job_id}: {job_error}"
                    result["warnings"].append(warning)
                    logger.warning(warning)

            result.update(
                {
                    "success": True,
                    "records_migrated": migrated_count,
                    "message": f"Migrated {migrated_count} job queue items",
                }
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to migrate job queue: {e}")

        return result

    def cleanup_legacy_files(self, confirm: bool = False) -> dict[str, Any]:
        """
        Clean up legacy state files after successful migration.

        Args:
            confirm: Must be True to actually delete files

        Returns:
            Dictionary with cleanup results
        """
        cleanup_results = {"files_removed": [], "files_skipped": [], "errors": []}

        if not confirm:
            cleanup_results["message"] = "Cleanup not confirmed - no files removed"
            return cleanup_results

        for file_type, file_path in self.legacy_files.items():
            try:
                if file_path.exists():
                    file_path.unlink()
                    cleanup_results["files_removed"].append(str(file_path))
                    logger.info(f"Removed legacy file: {file_path}")
                else:
                    cleanup_results["files_skipped"].append(str(file_path))
            except Exception as e:
                error_msg = f"Failed to remove {file_path}: {e}"
                cleanup_results["errors"].append(error_msg)
                logger.error(error_msg)

        cleanup_results["success"] = len(cleanup_results["errors"]) == 0
        return cleanup_results


# Convenience functions
def migrate_legacy_state(
    legacy_state_dir: Path | None = None, backup_files: bool = True
) -> dict[str, Any]:
    """Convenience function to migrate all legacy state to SQLite."""
    migrator = StateMigrator(legacy_state_dir=legacy_state_dir)
    return migrator.migrate_all_state(backup_legacy=backup_files)


def cleanup_legacy_state(confirm: bool = False) -> dict[str, Any]:
    """Convenience function to cleanup legacy state files."""
    migrator = StateMigrator()
    return migrator.cleanup_legacy_files(confirm=confirm)
