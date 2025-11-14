"""
Processing Configuration Classes

Centralized configuration for processing operations to replace magic numbers
and hardcoded values throughout the codebase.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptChunkingConfig:
    """Configuration for transcript chunking operations."""

    MAX_CHUNK_TOKENS: int = 1000
    """Maximum tokens per chunk before splitting"""

    OVERLAP_TOKENS: int = 100
    """Token overlap between chunks for context preservation"""

    MIN_CHUNK_TOKENS: int = 300
    """Minimum tokens per chunk (except for final chunks)"""

    TARGET_TOKENS: int = 750
    """Target token count for optimal chunk size"""

    MAX_TOKENS_LIMIT: int = 1000
    """Hard limit for token count per chunk"""


@dataclass(frozen=True)
class DownloadConfig:
    """Configuration for download operations and rate limiting."""

    MIN_DELAY_SECONDS: float = 180.0
    """Minimum delay between downloads (3 minutes)"""

    MAX_DELAY_SECONDS: float = 300.0
    """Maximum delay between downloads (5 minutes)"""

    TIMEOUT_SECONDS: int = 600
    """Timeout for download operations (10 minutes)"""

    DEFAULT_PARALLEL_WORKERS: int = 20
    """Default number of parallel download workers"""

    SLEEP_START_HOUR: int = 0
    """Start hour for sleep period (24-hour format)"""

    SLEEP_END_HOUR: int = 6
    """End hour for sleep period (24-hour format)"""


@dataclass(frozen=True)
class ProcessingConfig:
    """Configuration for general processing operations."""

    DEFAULT_BATCH_SIZE: int = 8
    """Default batch size for processing operations"""

    MAX_CONCURRENT_JOBS: int = 4
    """Maximum concurrent processing jobs"""

    CHECKPOINT_INTERVAL_SECONDS: int = 300
    """Interval for saving checkpoints (5 minutes)"""

    PROGRESS_UPDATE_INTERVAL: float = 1.0
    """Interval for progress updates in seconds"""


@dataclass(frozen=True)
class HTTPConfig:
    """Configuration for HTTP operations."""

    DEFAULT_STATUS_CODE: int = 200
    """Default HTTP status code for successful operations"""

    DEFAULT_TIMEOUT_SECONDS: int = 30
    """Default timeout for HTTP requests"""

    MAX_RETRIES: int = 3
    """Maximum number of retry attempts"""

    RETRY_BACKOFF_FACTOR: float = 2.0
    """Exponential backoff factor for retries"""


# Global configuration instances
CHUNKING = TranscriptChunkingConfig()
DOWNLOAD = DownloadConfig()
PROCESSING = ProcessingConfig()
HTTP = HTTPConfig()
