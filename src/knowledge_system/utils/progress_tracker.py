"""
SQLite-based progress tracking system for Knowledge System.

Replaces JSON-based progress tracking with database-backed tracking for better
resume capabilities, job management, and progress persistence.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from ..database import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


class JobStatus(Enum):
    """Status values for processing jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ProgressTracker:
    """
    SQLite-based progress tracking for processing jobs.

    Provides robust progress tracking with database persistence, enabling
    job resumption, progress monitoring, and comprehensive job management.
    """

    def __init__(self, database_service: DatabaseService | None = None):
        """Initialize progress tracker with database service."""
        self.db = database_service or DatabaseService()

    def create_job(
        self,
        job_type: str,
        input_urls: list[str],
        config: dict[str, Any],
        description: str | None = None,
    ) -> str | None:
        """
        Create a new processing job.

        Args:
            job_type: Type of job ('transcription', 'summarization', 'download', etc.)
            input_urls: List of input URLs or file paths
            config: Job configuration parameters
            description: Optional job description

        Returns:
            Job ID if successful, None if failed
        """
        try:
            job = self.db.create_processing_job(
                job_type=job_type, input_urls=input_urls, config=config
            )

            if job:
                logger.info(
                    f"Created job {job.job_id} for {job_type} with {len(input_urls)} items"
                )
                return job.job_id
            else:
                logger.error(f"Failed to create job for {job_type}")
                return None

        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            return None

    def start_job(self, job_id: str) -> bool:
        """
        Mark job as started.

        Args:
            job_id: Job identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            success = self.db.update_job_progress(
                job_id=job_id,
                status=JobStatus.RUNNING.value,
                started_at=datetime.utcnow(),
            )

            if success:
                logger.info(f"Started job {job_id}")
            else:
                logger.error(f"Failed to start job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to start job {job_id}: {e}")
            return False

    def update_progress(
        self,
        job_id: str,
        completed_items: int,
        failed_items: int = 0,
        total_cost: float = 0.0,
        total_tokens: int = 0,
        processing_time: float = 0.0,
        status: JobStatus | None = None,
    ) -> bool:
        """
        Update job progress.

        Args:
            job_id: Job identifier
            completed_items: Number of completed items
            failed_items: Number of failed items
            total_cost: Total cost incurred
            total_tokens: Total tokens consumed
            processing_time: Total processing time in seconds
            status: New job status

        Returns:
            True if successful, False otherwise
        """
        try:
            updates = {
                "completed_items": completed_items,
                "failed_items": failed_items,
                "total_cost": total_cost,
                "total_tokens_consumed": total_tokens,
                "total_processing_time_seconds": processing_time,
            }

            if status:
                updates["status"] = status.value

            success = self.db.update_job_progress(job_id=job_id, **updates)

            if success:
                logger.debug(
                    f"Updated progress for job {job_id}: {completed_items} completed, {failed_items} failed"
                )
            else:
                logger.error(f"Failed to update progress for job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to update progress for job {job_id}: {e}")
            return False

    def complete_job(
        self, job_id: str, final_stats: dict[str, Any] | None = None
    ) -> bool:
        """
        Mark job as completed.

        Args:
            job_id: Job identifier
            final_stats: Final job statistics

        Returns:
            True if successful, False otherwise
        """
        try:
            updates = {
                "status": JobStatus.COMPLETED.value,
                "completed_at": datetime.utcnow(),
            }

            if final_stats:
                updates.update(final_stats)

            success = self.db.update_job_progress(job_id=job_id, **updates)

            if success:
                logger.info(f"Completed job {job_id}")
            else:
                logger.error(f"Failed to complete job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to complete job {job_id}: {e}")
            return False

    def fail_job(
        self,
        job_id: str,
        error_message: str,
        failed_items: list[dict[str, Any]] | None = None,
    ) -> bool:
        """
        Mark job as failed.

        Args:
            job_id: Job identifier
            error_message: Error description
            failed_items: List of failed items with error details

        Returns:
            True if successful, False otherwise
        """
        try:
            updates = {
                "status": JobStatus.FAILED.value,
                "error_message": error_message,
                "completed_at": datetime.utcnow(),
            }

            if failed_items:
                updates["failed_items_json"] = failed_items

            success = self.db.update_job_progress(job_id=job_id, **updates)

            if success:
                logger.info(f"Failed job {job_id}: {error_message}")
            else:
                logger.error(f"Failed to mark job {job_id} as failed")

            return success

        except Exception as e:
            logger.error(f"Failed to fail job {job_id}: {e}")
            return False

    def pause_job(self, job_id: str, reason: str | None = None) -> bool:
        """
        Pause a running job.

        Args:
            job_id: Job identifier
            reason: Optional reason for pausing

        Returns:
            True if successful, False otherwise
        """
        try:
            updates = {"status": JobStatus.PAUSED.value}
            if reason:
                updates["error_message"] = f"Paused: {reason}"

            success = self.db.update_job_progress(job_id=job_id, **updates)

            if success:
                logger.info(f"Paused job {job_id}")
            else:
                logger.error(f"Failed to pause job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False

    def resume_job(self, job_id: str) -> bool:
        """
        Resume a paused job.

        Args:
            job_id: Job identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            success = self.db.update_job_progress(
                job_id=job_id,
                status=JobStatus.RUNNING.value,
                error_message=None,  # Clear pause reason
            )

            if success:
                logger.info(f"Resumed job {job_id}")
            else:
                logger.error(f"Failed to resume job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False

    def cancel_job(self, job_id: str, reason: str | None = None) -> bool:
        """
        Cancel a job.

        Args:
            job_id: Job identifier
            reason: Optional cancellation reason

        Returns:
            True if successful, False otherwise
        """
        try:
            updates = {
                "status": JobStatus.CANCELLED.value,
                "completed_at": datetime.utcnow(),
            }

            if reason:
                updates["error_message"] = f"Cancelled: {reason}"

            success = self.db.update_job_progress(job_id=job_id, **updates)

            if success:
                logger.info(f"Cancelled job {job_id}")
            else:
                logger.error(f"Failed to cancel job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """
        Get current job status and progress.

        Args:
            job_id: Job identifier

        Returns:
            Dictionary with job status and progress, or None if not found
        """
        try:
            with self.db.get_session() as session:
                from ..database.models import ProcessingJob

                job = (
                    session.query(ProcessingJob)
                    .filter(ProcessingJob.job_id == job_id)
                    .first()
                )

                if not job:
                    logger.warning(f"Job {job_id} not found")
                    return None

                # Calculate progress percentage
                progress_percentage = 0.0
                if job.total_items > 0:
                    progress_percentage = (job.completed_items / job.total_items) * 100

                # Calculate estimated completion time
                estimated_completion = None
                if (
                    job.started_at
                    and job.completed_items > 0
                    and job.status == JobStatus.RUNNING.value
                ):
                    elapsed = (datetime.utcnow() - job.started_at).total_seconds()
                    rate = job.completed_items / elapsed  # items per second
                    remaining_items = job.total_items - job.completed_items

                    if rate > 0:
                        remaining_seconds = remaining_items / rate
                        estimated_completion = (
                            datetime.utcnow().timestamp() + remaining_seconds
                        )

                return {
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "created_at": (
                        job.created_at.isoformat() if job.created_at else None
                    ),
                    "started_at": (
                        job.started_at.isoformat() if job.started_at else None
                    ),
                    "completed_at": (
                        job.completed_at.isoformat() if job.completed_at else None
                    ),
                    "total_items": job.total_items,
                    "completed_items": job.completed_items,
                    "failed_items": job.failed_items,
                    "skipped_items": job.skipped_items,
                    "progress_percentage": progress_percentage,
                    "total_cost": job.total_cost,
                    "total_tokens": job.total_tokens_consumed,
                    "processing_time_seconds": job.total_processing_time_seconds,
                    "error_message": job.error_message,
                    "estimated_completion": estimated_completion,
                    "config": job.config_json,
                }

        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            return None

    def get_active_jobs(self) -> list[dict[str, Any]]:
        """
        Get all active (running or paused) jobs.

        Returns:
            List of active job status dictionaries
        """
        try:
            with self.db.get_session() as session:
                from ..database.models import ProcessingJob

                active_jobs = (
                    session.query(ProcessingJob)
                    .filter(
                        ProcessingJob.status.in_(
                            [JobStatus.RUNNING.value, JobStatus.PAUSED.value]
                        )
                    )
                    .order_by(ProcessingJob.created_at.desc())
                    .all()
                )

                return [self._job_to_dict(job) for job in active_jobs]

        except Exception as e:
            logger.error(f"Failed to get active jobs: {e}")
            return []

    def get_recent_jobs(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recent jobs (all statuses).

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of recent job status dictionaries
        """
        try:
            with self.db.get_session() as session:
                from ..database.models import ProcessingJob

                recent_jobs = (
                    session.query(ProcessingJob)
                    .order_by(ProcessingJob.created_at.desc())
                    .limit(limit)
                    .all()
                )

                return [self._job_to_dict(job) for job in recent_jobs]

        except Exception as e:
            logger.error(f"Failed to get recent jobs: {e}")
            return []

    def get_resumable_jobs(self) -> list[dict[str, Any]]:
        """
        Get jobs that can be resumed (paused or failed with resumable errors).

        Returns:
            List of resumable job status dictionaries
        """
        try:
            with self.db.get_session() as session:
                from ..database.models import ProcessingJob

                resumable_jobs = (
                    session.query(ProcessingJob)
                    .filter(
                        ProcessingJob.status.in_(
                            [JobStatus.PAUSED.value, JobStatus.FAILED.value]
                        )
                    )
                    .filter(ProcessingJob.completed_items < ProcessingJob.total_items)
                    .order_by(ProcessingJob.created_at.desc())
                    .all()
                )

                return [self._job_to_dict(job) for job in resumable_jobs]

        except Exception as e:
            logger.error(f"Failed to get resumable jobs: {e}")
            return []

    def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """
        Clean up old completed jobs.

        Args:
            days_old: Remove jobs older than this many days

        Returns:
            Number of jobs cleaned up
        """
        try:
            from datetime import timedelta

            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            with self.db.get_session() as session:
                from ..database.models import ProcessingJob

                old_jobs = (
                    session.query(ProcessingJob)
                    .filter(
                        ProcessingJob.status.in_(
                            [
                                JobStatus.COMPLETED.value,
                                JobStatus.FAILED.value,
                                JobStatus.CANCELLED.value,
                            ]
                        )
                    )
                    .filter(ProcessingJob.completed_at < cutoff_date)
                    .all()
                )

                count = len(old_jobs)
                for job in old_jobs:
                    session.delete(job)

                session.commit()
                logger.info(f"Cleaned up {count} old jobs")
                return count

        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0

    def _job_to_dict(self, job) -> dict[str, Any]:
        """Convert job model to dictionary."""
        progress_percentage = 0.0
        if job.total_items > 0:
            progress_percentage = (job.completed_items / job.total_items) * 100

        return {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "total_items": job.total_items,
            "completed_items": job.completed_items,
            "failed_items": job.failed_items,
            "progress_percentage": progress_percentage,
            "total_cost": job.total_cost,
            "error_message": job.error_message,
        }


class JobProgressCallback:
    """
    Callback wrapper for updating job progress during processing.

    Provides a simple interface for processors to report progress that
    automatically updates the SQLite database.
    """

    def __init__(self, job_id: str, tracker: ProgressTracker | None = None):
        """Initialize callback with job ID and tracker."""
        self.job_id = job_id
        self.tracker = tracker or ProgressTracker()
        self.completed_items = 0
        self.failed_items = 0
        self.total_cost = 0.0
        self.total_tokens = 0

    def __call__(self, message: str, **kwargs):
        """Handle progress callback with optional statistics update."""
        # Log the progress message
        logger.info(f"[{self.job_id}] {message}")

        # Update statistics if provided
        if "completed" in kwargs:
            self.completed_items = kwargs["completed"]
        if "failed" in kwargs:
            self.failed_items = kwargs["failed"]
        if "cost" in kwargs:
            self.total_cost += kwargs["cost"]
        if "tokens" in kwargs:
            self.total_tokens += kwargs["tokens"]

        # Update database with current progress
        try:
            self.tracker.update_progress(
                job_id=self.job_id,
                completed_items=self.completed_items,
                failed_items=self.failed_items,
                total_cost=self.total_cost,
                total_tokens=self.total_tokens,
            )
        except Exception as e:
            logger.warning(f"Failed to update job progress: {e}")

    def complete(self, **final_stats):
        """Mark job as completed with final statistics."""
        final_stats.update(
            {
                "completed_items": self.completed_items,
                "failed_items": self.failed_items,
                "total_cost": self.total_cost,
                "total_tokens_consumed": self.total_tokens,
            }
        )

        self.tracker.complete_job(self.job_id, final_stats)

    def fail(self, error_message: str, **kwargs):
        """Mark job as failed with error details."""
        self.tracker.fail_job(self.job_id, error_message, kwargs.get("failed_items"))


# Convenience functions
def create_download_job(urls: list[str], config: dict[str, Any]) -> str | None:
    """Convenience function to create a download job."""
    tracker = ProgressTracker()
    return tracker.create_job("download", urls, config)


def create_transcription_job(urls: list[str], config: dict[str, Any]) -> str | None:
    """Convenience function to create a transcription job."""
    tracker = ProgressTracker()
    return tracker.create_job("transcription", urls, config)


def get_job_progress(job_id: str) -> dict[str, Any] | None:
    """Convenience function to get job progress."""
    tracker = ProgressTracker()
    return tracker.get_job_status(job_id)
