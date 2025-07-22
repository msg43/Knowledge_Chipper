"""
Progress Tracking for Batch Operations

Provides progress tracking classes for various operation types and 
a ProgressTracker for managing batch operations with resume capabilities.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from .cancellation import CancellationToken


logger = None

def get_logger(name: str = "tracking"):
    global logger
    if logger is None:
        try:
            from ..logger import get_logger as _get_logger
            logger = _get_logger(name)
        except ImportError:
            import logging
            logger = logging.getLogger(name)
    return logger


# ============================================================================
# PROGRESS DATA STRUCTURES
# ============================================================================

@dataclass
class TranscriptionProgress:
    """Progress tracking for transcription operations."""
    
    current_file: Optional[str] = None
    total_files: Optional[int] = None
    completed_files: Optional[int] = None
    failed_files: Optional[int] = None
    current_step: Optional[str] = None
    
    # Transcription-specific details
    model_name: Optional[str] = None
    device: Optional[str] = None
    audio_duration: Optional[float] = None
    processing_speed: Optional[float] = None  # ratio of real-time
    
    # Performance metrics
    eta_seconds: Optional[int] = None
    
    # Cancellation support
    cancellation_token: Optional[CancellationToken] = None


@dataclass
class SummarizationProgress:
    """Progress tracking for summarization operations."""
    
    current_file: Optional[str] = None
    total_files: Optional[int] = None
    completed_files: Optional[int] = None
    failed_files: Optional[int] = None
    current_step: Optional[str] = None
    
    # Summarization-specific details
    model_name: Optional[str] = None
    provider: Optional[str] = None  # openai, anthropic, local
    chunk_number: Optional[int] = None
    total_chunks: Optional[int] = None
    tokens_processed: Optional[int] = None
    
    # Performance metrics
    eta_seconds: Optional[int] = None
    
    # Cancellation support
    cancellation_token: Optional[CancellationToken] = None


@dataclass
class ExtractionProgress:
    """Progress tracking for YouTube extraction operations."""
    
    current_url: Optional[str] = None
    total_urls: Optional[int] = None
    completed_urls: Optional[int] = None
    failed_urls: Optional[int] = None
    current_step: Optional[str] = None
    
    # Extraction-specific details
    proxy_status: Optional[str] = None
    retry_count: Optional[int] = None
    transcript_length: Optional[int] = None
    
    # Performance metrics
    eta_seconds: Optional[int] = None
    
    # Cancellation support
    cancellation_token: Optional[CancellationToken] = None


@dataclass
class MOCProgress:
    """Progress tracking for Map of Content generation operations."""
    
    current_file: Optional[str] = None
    total_files: Optional[int] = None
    completed_files: Optional[int] = None
    failed_files: Optional[int] = None
    current_step: Optional[str] = None
    
    # MOC-specific details
    moc_type: Optional[str] = None  # people, topics, themes, etc.
    files_analyzed: Optional[int] = None
    entities_found: Optional[int] = None
    connections_made: Optional[int] = None
    
    # Performance metrics
    eta_seconds: Optional[int] = None
    
    # Cancellation support
    cancellation_token: Optional[CancellationToken] = None


class TaskStatus(Enum):
    """Status of a processing task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskInfo:
    """Information about a processing task."""

    id: str
    input_path: str
    task_type: str  # 'transcribe', 'summarize', 'moc', etc.
    status: TaskStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3


# ============================================================================
# PROGRESS TRACKER
# ============================================================================

class ProgressTracker:
    """Tracks progress of batch operations with resume capabilities."""

    def __init__(
        self,
        operation_name: str,
        total_tasks: int,
        checkpoint_file: Optional[Path] = None,
    ):
        self.operation_name = operation_name
        self.total_tasks = total_tasks
        self.checkpoint_file = checkpoint_file or Path(
            f"progress_{operation_name}_{int(time.time())}.json"
        )
        self.tasks: Dict[str, TaskInfo] = {}
        self.completed_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.start_time = datetime.now()

        # Load existing progress if checkpoint exists
        self._load_checkpoint()

    def add_task(self, task_id: str, input_path: str, task_type: str) -> None:
        """Add a new task to track."""
        if task_id not in self.tasks:
            self.tasks[task_id] = TaskInfo(
                id=task_id,
                input_path=input_path,
                task_type=task_type,
                status=TaskStatus.PENDING,
            )

    def start_task(self, task_id: str) -> None:
        """Mark a task as started."""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.RUNNING
            self.tasks[task_id].start_time = datetime.now()
            self._save_checkpoint()

    def complete_task(
        self, task_id: str, result_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark a task as completed."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.end_time = datetime.now()
            task.duration = (
                (task.end_time - task.start_time).total_seconds()
                if task.start_time
                else None
            )
            task.result_data = result_data
            self.completed_count += 1
            self._save_checkpoint()

    def fail_task(self, task_id: str, error_message: str) -> None:
        """Mark a task as failed."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.FAILED
            task.end_time = datetime.now()
            task.duration = (
                (task.end_time - task.start_time).total_seconds()
                if task.start_time
                else None
            )
            task.error_message = error_message
            self.failed_count += 1

            # Check if we should retry
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                get_logger().info(f"Task {task_id} will be retried ({task.retry_count}/{task.max_retries})")
            else:
                get_logger().error(f"Task {task_id} failed after {task.retry_count} retries: {error_message}")

            self._save_checkpoint()

    def skip_task(self, task_id: str, reason: str) -> None:
        """Mark a task as skipped."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.SKIPPED
            task.end_time = datetime.now()
            task.error_message = f"Skipped: {reason}"
            self.skipped_count += 1
            self._save_checkpoint()

    def get_pending_tasks(self) -> List[TaskInfo]:
        """Get all pending tasks."""
        return [task for task in self.tasks.values() if task.status == TaskStatus.PENDING]

    def get_failed_tasks(self) -> List[TaskInfo]:
        """Get all failed tasks."""
        return [task for task in self.tasks.values() if task.status == TaskStatus.FAILED]

    def get_completed_tasks(self) -> List[TaskInfo]:
        """Get all completed tasks."""
        return [task for task in self.tasks.values() if task.status == TaskStatus.COMPLETED]

    def get_progress_summary(self) -> Dict[str, Any]:
        """Get a summary of current progress."""
        elapsed = datetime.now() - self.start_time
        completed_tasks = len(self.get_completed_tasks())
        
        # Calculate ETA
        eta_seconds = None
        if completed_tasks > 0:
            avg_time_per_task = elapsed.total_seconds() / completed_tasks
            remaining_tasks = self.total_tasks - completed_tasks
            eta_seconds = int(avg_time_per_task * remaining_tasks)

        return {
            "operation": self.operation_name,
            "total_tasks": self.total_tasks,
            "completed": completed_tasks,
            "failed": self.failed_count,
            "skipped": self.skipped_count,
            "pending": len(self.get_pending_tasks()),
            "elapsed_seconds": int(elapsed.total_seconds()),
            "eta_seconds": eta_seconds,
            "completion_percentage": (completed_tasks / self.total_tasks * 100) if self.total_tasks > 0 else 0,
        }

    def is_complete(self) -> bool:
        """Check if all tasks are complete (or failed/skipped)."""
        pending_tasks = self.get_pending_tasks()
        return len(pending_tasks) == 0

    def _save_checkpoint(self) -> None:
        """Save current progress to checkpoint file."""
        try:
            checkpoint_data = {
                "operation_name": self.operation_name,
                "total_tasks": self.total_tasks,
                "start_time": self.start_time.isoformat(),
                "completed_count": self.completed_count,
                "failed_count": self.failed_count,
                "skipped_count": self.skipped_count,
                "tasks": {},
            }

            # Convert tasks to serializable format
            for task_id, task in self.tasks.items():
                task_dict = asdict(task)
                # Convert datetime objects to strings
                if task.start_time:
                    task_dict["start_time"] = task.start_time.isoformat()
                if task.end_time:
                    task_dict["end_time"] = task.end_time.isoformat()
                # Convert enum to string
                task_dict["status"] = task.status.value
                checkpoint_data["tasks"][task_id] = task_dict

            with open(self.checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=2)

        except Exception as e:
            get_logger().error(f"Failed to save checkpoint: {e}")

    def _load_checkpoint(self) -> None:
        """Load progress from checkpoint file if it exists."""
        if not self.checkpoint_file.exists():
            return

        try:
            with open(self.checkpoint_file, "r") as f:
                checkpoint_data = json.load(f)

            # Restore basic info
            self.operation_name = checkpoint_data.get("operation_name", self.operation_name)
            self.total_tasks = checkpoint_data.get("total_tasks", self.total_tasks)
            self.completed_count = checkpoint_data.get("completed_count", 0)
            self.failed_count = checkpoint_data.get("failed_count", 0)
            self.skipped_count = checkpoint_data.get("skipped_count", 0)

            if "start_time" in checkpoint_data:
                self.start_time = datetime.fromisoformat(checkpoint_data["start_time"])

            # Restore tasks
            for task_id, task_data in checkpoint_data.get("tasks", {}).items():
                task = TaskInfo(
                    id=task_data["id"],
                    input_path=task_data["input_path"],
                    task_type=task_data["task_type"],
                    status=TaskStatus(task_data["status"]),
                    error_message=task_data.get("error_message"),
                    result_data=task_data.get("result_data"),
                    retry_count=task_data.get("retry_count", 0),
                    max_retries=task_data.get("max_retries", 3),
                    duration=task_data.get("duration"),
                )

                # Convert datetime strings back to datetime objects
                if task_data.get("start_time"):
                    task.start_time = datetime.fromisoformat(task_data["start_time"])
                if task_data.get("end_time"):
                    task.end_time = datetime.fromisoformat(task_data["end_time"])

                self.tasks[task_id] = task

            get_logger().info(
                f"Loaded checkpoint: {self.completed_count} completed, {self.failed_count} failed"
            )

        except Exception as e:
            get_logger().error(f"Failed to load checkpoint: {e}") 