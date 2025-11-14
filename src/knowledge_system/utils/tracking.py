"""Progress data structures for tracking processing operations.

This module contains dataclass definitions for progress tracking across different
operation types (transcription, summarization, extraction, MOC generation).

Note: The old JSON-based ProgressTracker class has been removed and replaced with
the SQLite-based ProgressTracker in utils.progress_tracker module.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from .cancellation import CancellationToken


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
    current_file_chars_done: int | None = None  # Characters processed in current file

    # Progress calculations (automatically computed)
    file_percent: float | None = None  # Current file progress (0.0-100.0)
    batch_percent: float | None = None  # Overall batch progress (0.0-100.0)

    # Legacy compatibility (DEPRECATED - auto-calculated for backward compatibility)
    percent: float | None = None  # DEPRECATED: Use file_percent instead (auto-calculated)
    status: str | None = None  # Current status/stage (still used)
    batch_percent_characters: float | None = None  # DEPRECATED: Use batch_percent instead (auto-calculated)

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
