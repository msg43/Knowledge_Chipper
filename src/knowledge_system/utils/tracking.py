"""
DEPRECATED: JSON-based Progress Tracking

⚠️ This module is deprecated and replaced by SQLite-based progress tracking.

MIGRATION NOTICE:
- Use `ProgressTracker` from `..utils.progress_tracker` for SQLite-based job tracking
- Use `DatabaseService` from `..database.service` for operational data storage
- The new SQLite-based system provides better reliability and resume capabilities

This file is maintained for backward compatibility but will be removed in a future version.
"""

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .cancellation import CancellationToken

logger = None


def get_logger(name: str = "tracking") -> Any:
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
    """Progress tracking for transcription operations with duration-based progress."""

    current_file: str | None = None
    total_files: int | None = None
    completed_files: int | None = None
    failed_files: int | None = None
    current_step: str | None = None

    # Transcription-specific details
    model_name: str | None = None
    device: str | None = None

    # Duration-based progress tracking (for audio/video files)
    total_duration: float | None = None  # Total duration in seconds across all files
    duration_completed: float | None = None  # Duration completed across all files
    current_file_duration: float | None = None  # Duration of current file
    current_file_progress: float | None = None  # Duration processed in current file

    # Progress calculations (automatically computed)
    file_percent: float | None = None  # Current file progress (0.0-100.0)
    batch_percent: float | None = None  # Overall batch progress (0.0-100.0)

    # Performance metrics
    processing_speed: float | None = None  # ratio of real-time (1.0 = real-time)
    duration_per_second: float | None = None  # seconds of audio processed per second

    # Time estimates
    eta_seconds: int | None = None  # Time remaining for current file
    batch_eta_seconds: int | None = None  # Time remaining for entire batch
    elapsed_seconds: float | None = None  # Time elapsed so far

    # Cancellation support
    cancellation_token: CancellationToken | None = None

    def __post_init__(self) -> None:
        """Auto-calculate progress percentages and ETAs based on duration data."""
        # Calculate file progress
        if self.current_file_duration and self.current_file_progress is not None:
            self.file_percent = min(
                100.0, (self.current_file_progress / self.current_file_duration) * 100.0
            )

        # Calculate batch progress
        if self.total_duration and self.duration_completed is not None:
            self.batch_percent = min(
                100.0, (self.duration_completed / self.total_duration) * 100.0
            )

        # Calculate processing rate and ETAs
        if self.elapsed_seconds and self.elapsed_seconds > 0:
            if self.duration_completed and self.duration_completed > 0:
                self.duration_per_second = (
                    self.duration_completed / self.elapsed_seconds
                )
                self.processing_speed = (
                    self.duration_per_second
                )  # For audio, this is the processing ratio

                # File ETA
                if (
                    self.current_file_duration
                    and self.current_file_progress is not None
                ):
                    remaining_file_duration = (
                        self.current_file_duration - self.current_file_progress
                    )
                    if self.duration_per_second > 0:
                        self.eta_seconds = int(
                            remaining_file_duration / self.duration_per_second
                        )

                # Batch ETA
                if self.total_duration:
                    remaining_batch_duration = (
                        self.total_duration - self.duration_completed
                    )
                    if self.duration_per_second > 0:
                        self.batch_eta_seconds = int(
                            remaining_batch_duration / self.duration_per_second
                        )


@dataclass
class SummarizationProgress:
    """Progress tracking for summarization operations with character-based progress."""

    current_file: str | None = None
    total_files: int | None = None
    completed_files: int | None = None
    failed_files: int | None = None
    current_step: str | None = None

    # Summarization-specific details
    model_name: str | None = None
    provider: str | None = None  # openai, anthropic, local
    chunk_number: int | None = None
    total_chunks: int | None = None
    tokens_processed: int | None = None

    # Character-based progress tracking (NEW - more accurate)
    total_characters: int | None = None  # Total characters in entire batch
    characters_completed: int | None = None  # Characters completed across all files
    current_file_size: int | None = None  # Size of current file being processed
    current_file_chars_done: None | (int) = None  # Characters processed in current file

    # Progress calculations (automatically computed)
    file_percent: float | None = None  # Current file progress (0.0-100.0)
    batch_percent: float | None = None  # Overall batch progress (0.0-100.0)

    # Legacy compatibility (DEPRECATED - auto-calculated for backward compatibility)
    percent: None | (float) = (
        None  # DEPRECATED: Use file_percent instead (auto-calculated)
    )
    status: str | None = None  # Current status/stage (still used)
    batch_percent_characters: None | (float) = (
        None  # DEPRECATED: Use batch_percent instead (auto-calculated)
    )

    # Performance metrics
    chars_per_second: float | None = None  # Character processing rate
    tokens_generated: int | None = None
    speed_tokens_per_sec: float | None = None

    # Time estimates (more accurate with character-based tracking)
    eta_seconds: int | None = None  # Time remaining for current file
    batch_eta_seconds: int | None = None  # Time remaining for entire batch
    elapsed_seconds: float | None = None  # Time elapsed so far

    # Cancellation support
    cancellation_token: CancellationToken | None = None

    def __post_init__(self) -> None:
        """Auto-calculate progress percentages and ETAs based on character data."""
        # Calculate file progress
        if self.current_file_size and self.current_file_chars_done is not None:
            self.file_percent = min(
                100.0, (self.current_file_chars_done / self.current_file_size) * 100.0
            )

        # Calculate batch progress
        if self.total_characters and self.characters_completed is not None:
            self.batch_percent = min(
                100.0, (self.characters_completed / self.total_characters) * 100.0
            )

        # Calculate processing rate and ETAs
        if self.elapsed_seconds and self.elapsed_seconds > 0:
            if self.characters_completed and self.characters_completed > 0:
                self.chars_per_second = self.characters_completed / self.elapsed_seconds

                # File ETA
                if self.current_file_size and self.current_file_chars_done is not None:
                    remaining_file_chars = (
                        self.current_file_size - self.current_file_chars_done
                    )
                    if self.chars_per_second > 0:
                        self.eta_seconds = int(
                            remaining_file_chars / self.chars_per_second
                        )

                # Batch ETA
                if self.total_characters:
                    remaining_batch_chars = (
                        self.total_characters - self.characters_completed
                    )
                    if self.chars_per_second > 0:
                        self.batch_eta_seconds = int(
                            remaining_batch_chars / self.chars_per_second
                        )

        # Maintain backward compatibility
        if self.file_percent is not None:
            self.percent = self.file_percent
        if self.batch_percent is not None:
            self.batch_percent_characters = self.batch_percent


@dataclass
class ExtractionProgress:
    """Progress tracking for YouTube extraction operations with URL-based progress."""

    current_url: str | None = None
    total_urls: int | None = None
    completed_urls: int | None = None
    failed_urls: int | None = None
    current_step: str | None = None

    # Extraction-specific details
    proxy_status: str | None = None
    retry_count: int | None = None
    transcript_length: int | None = None

    # URL-based progress tracking
    urls_processed: int | None = None  # URLs processed so far
    current_url_index: int | None = None  # Index of current URL (0-based)

    # Progress calculations (automatically computed)
    batch_percent: float | None = None  # Overall batch progress (0.0-100.0)

    # Performance metrics
    urls_per_minute: float | None = None  # URLs processed per minute
    avg_processing_time: float | None = None  # Average time per URL

    # Time estimates
    eta_seconds: int | None = None  # Time remaining for batch
    elapsed_seconds: float | None = None  # Time elapsed so far

    # Cancellation support
    cancellation_token: CancellationToken | None = None

    def __post_init__(self) -> None:
        """Auto-calculate progress percentages and ETAs based on URL processing data."""
        # Calculate batch progress
        if self.total_urls and self.urls_processed is not None:
            self.batch_percent = min(
                100.0, (self.urls_processed / self.total_urls) * 100.0
            )

        # Calculate processing rate and ETAs
        if self.elapsed_seconds and self.elapsed_seconds > 0:
            if self.urls_processed and self.urls_processed > 0:
                self.urls_per_minute = (self.urls_processed / self.elapsed_seconds) * 60
                self.avg_processing_time = self.elapsed_seconds / self.urls_processed

                # Batch ETA
                if self.total_urls:
                    remaining_urls = self.total_urls - self.urls_processed
                    if self.avg_processing_time > 0:
                        self.eta_seconds = int(
                            remaining_urls * self.avg_processing_time
                        )


@dataclass
class MOCProgress:
    """Progress tracking for Map of Content generation operations with file-based progress."""

    current_file: str | None = None
    total_files: int | None = None
    completed_files: int | None = None
    failed_files: int | None = None
    current_step: str | None = None

    # MOC-specific details
    moc_type: str | None = None  # people, topics, themes, etc.
    files_analyzed: int | None = None
    entities_found: int | None = None
    connections_made: int | None = None

    # File-based progress tracking
    files_processed: int | None = None  # Files processed so far
    current_file_index: int | None = None  # Index of current file (0-based)

    # Progress calculations (automatically computed)
    batch_percent: float | None = None  # Overall batch progress (0.0-100.0)

    # Performance metrics
    files_per_minute: float | None = None  # Files processed per minute
    avg_processing_time: float | None = None  # Average time per file

    # Time estimates
    eta_seconds: int | None = None  # Time remaining for batch
    elapsed_seconds: float | None = None  # Time elapsed so far

    # Cancellation support
    cancellation_token: CancellationToken | None = None

    def __post_init__(self) -> None:
        """Auto-calculate progress percentages and ETAs based on file processing data."""
        # Calculate batch progress
        if self.total_files and self.files_processed is not None:
            self.batch_percent = min(
                100.0, (self.files_processed / self.total_files) * 100.0
            )

        # Calculate processing rate and ETAs
        if self.elapsed_seconds and self.elapsed_seconds > 0:
            if self.files_processed and self.files_processed > 0:
                self.files_per_minute = (
                    self.files_processed / self.elapsed_seconds
                ) * 60
                self.avg_processing_time = self.elapsed_seconds / self.files_processed

                # Batch ETA
                if self.total_files:
                    remaining_files = self.total_files - self.files_processed
                    if self.avg_processing_time > 0:
                        self.eta_seconds = int(
                            remaining_files * self.avg_processing_time
                        )


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
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration: float | None = None
    error_message: str | None = None
    result_data: dict[str, Any] | None = None
    retry_count: int = 0
    max_retries: int = 3


# ============================================================================
# PROGRESS TRACKER
# ============================================================================


class ProgressTracker:
    """
    DEPRECATED: Tracks progress of batch operations with resume capabilities.

    ⚠️ This class is deprecated. Use the new SQLite-based ProgressTracker from utils.progress_tracker instead.
    """

    def __init__(
        self,
        operation_name: str,
        total_tasks: int,
        checkpoint_file: Path | None = None,
    ) -> None:
        self.operation_name = operation_name
        self.total_tasks = total_tasks
        self.checkpoint_file = checkpoint_file or Path(
            f"progress_{operation_name}_{int(time.time())}.json"
        )
        self.tasks: dict[str, TaskInfo] = {}
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
        self, task_id: str, result_data: dict[str, Any] | None = None
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
                get_logger().info(
                    f"Task {task_id} will be retried ({task.retry_count}/{task.max_retries})"
                )
            else:
                get_logger().error(
                    f"Task {task_id} failed after {task.retry_count} retries: {error_message}"
                )

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

    def get_pending_tasks(self) -> list[TaskInfo]:
        """Get all pending tasks."""
        return [
            task for task in self.tasks.values() if task.status == TaskStatus.PENDING
        ]

    def get_failed_tasks(self) -> list[TaskInfo]:
        """Get all failed tasks."""
        return [
            task for task in self.tasks.values() if task.status == TaskStatus.FAILED
        ]

    def get_completed_tasks(self) -> list[TaskInfo]:
        """Get all completed tasks."""
        return [
            task for task in self.tasks.values() if task.status == TaskStatus.COMPLETED
        ]

    def get_progress_summary(self) -> dict[str, Any]:
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
            "completion_percentage": (
                (completed_tasks / self.total_tasks * 100)
                if self.total_tasks > 0
                else 0
            ),
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
            with open(self.checkpoint_file) as f:
                checkpoint_data = json.load(f)

            # Restore basic info
            self.operation_name = checkpoint_data.get(
                "operation_name", self.operation_name
            )
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


# ============================================================================
# PROGRESS TRACKING UTILITIES
# ============================================================================


def format_time_remaining(seconds: int | None) -> str:
    """Format time remaining in a human-readable format."""
    if seconds is None or seconds <= 0:
        return "Unknown"

    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        if secs > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{hours}h"


def format_progress_message(progress: Any, operation_type: str = "processing") -> str:
    """
    Format a comprehensive progress message with ETAs
    Format a comprehensive progress message with ETAs.

    Args:
        progress: Any of the progress classes (SummarizationProgress, etc.)
        operation_type: Type of operation for display (e.g., "summarizing", "transcribing")

    Returns:
        Formatted progress string with current status and ETAs
    """
    parts = []

    # Current operation status
    if hasattr(progress, "current_step") and progress.current_step:
        parts.append(progress.current_step)

    # File progress
    if hasattr(progress, "file_percent") and progress.file_percent is not None:
        parts.append(f"({progress.file_percent:.0f}%)")
    elif hasattr(progress, "percent") and progress.percent is not None:
        parts.append(f"({progress.percent:.0f}%)")

    # File ETA
    if hasattr(progress, "eta_seconds") and progress.eta_seconds is not None:
        parts.append(f"ETA: {format_time_remaining(progress.eta_seconds)}")

    # Batch information
    batch_parts = []
    if hasattr(progress, "batch_percent") and progress.batch_percent is not None:
        batch_parts.append(f"Batch: {progress.batch_percent:.0f}%")
    elif (
        hasattr(progress, "batch_percent_characters")
        and progress.batch_percent_characters is not None
    ):
        batch_parts.append(f"Batch: {progress.batch_percent_characters:.0f}%")

    # Batch ETA
    if (
        hasattr(progress, "batch_eta_seconds")
        and progress.batch_eta_seconds is not None
    ):
        batch_parts.append(
            f"Batch ETA: {format_time_remaining(progress.batch_eta_seconds)}"
        )

    if batch_parts:
        parts.append(" | ".join(batch_parts))

    return " | ".join(parts)


def create_character_progress_tracker(
    file_paths: list[str], start_time: float
) -> dict[str, Any]:
    """
    Create a character-based progress tracker for a batch of files
    Create a character-based progress tracker for a batch of files.

    Args:
        file_paths: List of file paths to process
        start_time: Start time of the operation

    Returns:
        Dictionary with tracking information
    """
    from pathlib import Path

    file_sizes = []
    total_characters = 0

    # Calculate file sizes
    for file_path in file_paths:
        try:
            file_size = Path(file_path).stat().st_size
            file_sizes.append(file_size)
            total_characters += file_size
        except Exception:
            # Fallback for files we can't read
            estimated_size = 10000  # 10KB default estimate
            file_sizes.append(estimated_size)
            total_characters += estimated_size

    return {
        "file_paths": file_paths,
        "file_sizes": file_sizes,
        "total_characters": total_characters,
        "characters_completed": 0,
        "start_time": start_time,
        "current_file_index": 0,
    }


def create_duration_progress_tracker(
    audio_files: list[str], start_time: float
) -> dict[str, Any]:
    """
    Create a duration-based progress tracker for audio/video files
    Create a duration-based progress tracker for audio/video files.

    Args:
        audio_files: List of audio/video file paths
        start_time: Start time of the operation

    Returns:
        Dictionary with tracking information
    """
    # This would need to integrate with audio duration detection

    # This would need to integrate with audio duration detection
    # For now, use file size as a proxy
    return create_character_progress_tracker(audio_files, start_time)


def update_progress_with_character_tracking(
    progress_tracker: dict[str, Any],
    current_file_index: int,
    current_file_progress_percent: float,
    elapsed_time: float,
) -> dict[str, Any]:
    """
    Update progress tracking with current file progress
    Update progress tracking with current file progress.

    Args:
        progress_tracker: Progress tracker from create_character_progress_tracker
        current_file_index: Index of current file being processed
        current_file_progress_percent: Progress percentage for current file (0-100)
        elapsed_time: Time elapsed since start

    Returns:
        Updated progress information with ETAs
    """

    # Calculate characters completed
    characters_completed = 0

    # Add completed files
    for i in range(current_file_index):
        characters_completed += progress_tracker["file_sizes"][i]

    # Add current file progress
    if current_file_index < len(progress_tracker["file_sizes"]):
        current_file_size = progress_tracker["file_sizes"][current_file_index]
        current_file_chars_done = (
            current_file_progress_percent / 100.0
        ) * current_file_size
        characters_completed += current_file_chars_done

    # Calculate batch progress
    total_characters = progress_tracker["total_characters"]
    batch_percent = (
        (characters_completed / total_characters) * 100.0
        if total_characters > 0
        else 0.0
    )

    # Calculate processing rate and ETAs
    chars_per_second = characters_completed / elapsed_time if elapsed_time > 0 else 0

    # File ETA
    file_eta_seconds = None
    if (
        current_file_index < len(progress_tracker["file_sizes"])
        and chars_per_second > 0
    ):
        current_file_size = progress_tracker["file_sizes"][current_file_index]
        current_file_chars_done = (
            current_file_progress_percent / 100.0
        ) * current_file_size
        remaining_file_chars = current_file_size - current_file_chars_done
        file_eta_seconds = (
            int(remaining_file_chars / chars_per_second)
            if remaining_file_chars > 0
            else 0
        )

    # Batch ETA
    batch_eta_seconds = None
    if chars_per_second > 0:
        remaining_batch_chars = total_characters - characters_completed
        batch_eta_seconds = (
            int(remaining_batch_chars / chars_per_second)
            if remaining_batch_chars > 0
            else 0
        )

    return {
        "characters_completed": characters_completed,
        "batch_percent": batch_percent,
        "chars_per_second": chars_per_second,
        "file_eta_seconds": file_eta_seconds,
        "batch_eta_seconds": batch_eta_seconds,
        "current_file_size": (
            progress_tracker["file_sizes"][current_file_index]
            if current_file_index < len(progress_tracker["file_sizes"])
            else 0
        ),
        "current_file_chars_done": (
            (current_file_progress_percent / 100.0)
            * progress_tracker["file_sizes"][current_file_index]
            if current_file_index < len(progress_tracker["file_sizes"])
            else 0
        ),
    }
