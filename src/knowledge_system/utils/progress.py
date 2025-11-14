"""
Progress Tracking and Resume-from-Failure Utilities
Progress Tracking and Resume-from-Failure Utilities

This module now serves as a compatibility layer, importing from the new
modular progress system for backward compatibility.

The progress system has been split into focused modules:
- cancellation.py: CancellationToken, CancellationError
- tracking.py: Progress classes and ProgressTracker
- display.py: ProgressDisplay
- batch_processing.py: Hang detection classes
"""

# Note: Hang detection classes were moved to a separate module
# from .batch_processing import (...)

# Import all classes for backward compatibility
from .cancellation import CancellationError, CancellationToken
from .display import ProgressDisplay
from .progress_tracker import ProgressTracker
from .tracking import (
    ExtractionProgress,
    MOCProgress,
    SummarizationProgress,
    TaskInfo,
    TaskStatus,
    TranscriptionProgress,
)

# Re-export all classes for compatibility
__all__ = [
    # Cancellation
    "CancellationToken",
    "CancellationError",
    # Progress tracking
    "TranscriptionProgress",
    "SummarizationProgress",
    "ExtractionProgress",
    "MOCProgress",
    "TaskStatus",
    "TaskInfo",
    "ProgressTracker",
    # Display
    "ProgressDisplay",
    # Batch processing / hang detection (deprecated)
    # "HangDetectionLevel",
    # "OperationType",
    # "HangDetectionConfig",
    # "TrackedOperation",
    # "HangDetector",
    # "get_hang_detector",
    # "configure_hang_detection",
    # "HangDetectionContext",
]
