"""
Checkpoint Manager

Handles checkpoint save/load/restore operations for processing jobs.
Extracted from System2Orchestrator to follow single responsibility principle.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..database import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


class CheckpointManager:
    """Manages checkpoints for processing jobs with automatic save/restore."""

    def __init__(self, db_service: DatabaseService | None = None):
        """Initialize checkpoint manager."""
        self.db_service = db_service or DatabaseService()

    def save_checkpoint(
        self,
        run_id: str,
        checkpoint_data: dict[str, Any],
        stage: str | None = None,
    ) -> bool:
        """
        Save checkpoint for a job run.

        Args:
            run_id: Job run ID
            checkpoint_data: Data to checkpoint (must be JSON-serializable)
            stage: Current processing stage (optional)

        Returns:
            True if saved successfully
        """
        try:
            # Serialize checkpoint data
            checkpoint_json = json.dumps(checkpoint_data)

            # Update job run with checkpoint
            with self.db_service.get_session() as session:
                from ..database.system2_models import JobRun

                run = session.query(JobRun).filter_by(run_id=run_id).first()
                if run:
                    run.checkpoint_data = checkpoint_json
                    if stage:
                        run.current_stage = stage
                    run.last_checkpoint_time = datetime.utcnow()
                    session.commit()
                    logger.debug(f"Saved checkpoint for {run_id}: stage={stage}")
                    return True
                else:
                    logger.error(f"Job run not found for checkpoint: {run_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to save checkpoint for {run_id}: {e}")
            return False

    def load_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        """
        Load checkpoint for a job run.

        Args:
            run_id: Job run ID

        Returns:
            Checkpoint data or None if not found
        """
        try:
            with self.db_service.get_session() as session:
                from ..database.system2_models import JobRun

                run = session.query(JobRun).filter_by(run_id=run_id).first()
                if run and run.checkpoint_data:
                    checkpoint_data = json.loads(run.checkpoint_data)
                    logger.debug(f"Loaded checkpoint for {run_id}")
                    return checkpoint_data
                else:
                    logger.debug(f"No checkpoint found for {run_id}")
                    return None

        except Exception as e:
            logger.error(f"Failed to load checkpoint for {run_id}: {e}")
            return None

    def has_checkpoint(self, run_id: str) -> bool:
        """
        Check if a job run has a checkpoint.

        Args:
            run_id: Job run ID

        Returns:
            True if checkpoint exists
        """
        try:
            with self.db_service.get_session() as session:
                from ..database.system2_models import JobRun

                run = session.query(JobRun).filter_by(run_id=run_id).first()
                return bool(run and run.checkpoint_data)

        except Exception as e:
            logger.error(f"Failed to check checkpoint for {run_id}: {e}")
            return False

    def delete_checkpoint(self, run_id: str) -> bool:
        """
        Delete checkpoint for a job run.

        Args:
            run_id: Job run ID

        Returns:
            True if deleted successfully
        """
        try:
            with self.db_service.get_session() as session:
                from ..database.system2_models import JobRun

                run = session.query(JobRun).filter_by(run_id=run_id).first()
                if run:
                    run.checkpoint_data = None
                    run.current_stage = None
                    run.last_checkpoint_time = None
                    session.commit()
                    logger.debug(f"Deleted checkpoint for {run_id}")
                    return True
                else:
                    logger.warning(f"Job run not found for checkpoint deletion: {run_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete checkpoint for {run_id}: {e}")
            return False

    def get_checkpoint_info(self, run_id: str) -> dict[str, Any] | None:
        """
        Get checkpoint metadata without loading full data.

        Args:
            run_id: Job run ID

        Returns:
            Dictionary with checkpoint info or None
        """
        try:
            with self.db_service.get_session() as session:
                from ..database.system2_models import JobRun

                run = session.query(JobRun).filter_by(run_id=run_id).first()
                if run and run.checkpoint_data:
                    return {
                        "has_checkpoint": True,
                        "current_stage": run.current_stage,
                        "last_checkpoint_time": run.last_checkpoint_time,
                        "checkpoint_size": len(run.checkpoint_data),
                    }
                else:
                    return {
                        "has_checkpoint": False,
                        "current_stage": None,
                        "last_checkpoint_time": None,
                        "checkpoint_size": 0,
                    }

        except Exception as e:
            logger.error(f"Failed to get checkpoint info for {run_id}: {e}")
            return None


class CheckpointContext:
    """Context manager for automatic checkpoint saving."""

    def __init__(
        self,
        manager: CheckpointManager,
        run_id: str,
        stage: str,
        checkpoint_data: dict[str, Any],
    ):
        """Initialize checkpoint context."""
        self.manager = manager
        self.run_id = run_id
        self.stage = stage
        self.checkpoint_data = checkpoint_data

    def __enter__(self):
        """Enter context - save checkpoint."""
        self.manager.save_checkpoint(self.run_id, self.checkpoint_data, self.stage)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - optionally save error state."""
        if exc_type is not None:
            # Save error state to checkpoint
            error_data = self.checkpoint_data.copy()
            error_data["error"] = str(exc_val)
            error_data["error_stage"] = self.stage
            self.manager.save_checkpoint(self.run_id, error_data, f"{self.stage}_error")
        return False  # Don't suppress exceptions
