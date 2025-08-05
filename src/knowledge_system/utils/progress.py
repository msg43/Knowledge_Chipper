"""
Progress Tracking and Resume-from-Failure Utilities

This module now serves as a compatibility layer, importing from the new
modular progress system for backward compatibility.

The progress system has been split into focused modules:
- cancellation.py: CancellationToken, CancellationError
- tracking.py: Progress classes and ProgressTracker
- display.py: ProgressDisplay
- batch_processing.py: Hang detection classes
"""

from .batch_processing import (
    HangDetectionConfig,
    HangDetectionContext,
    HangDetectionLevel,
    HangDetector,
    OperationType,
    TrackedOperation,
    configure_hang_detection,
    get_hang_detector,
)

# Import all classes for backward compatibility
from .cancellation import CancellationError, CancellationToken
from .display import ProgressDisplay
from .tracking import (
    ExtractionProgress,
    MOCProgress,
    ProgressTracker,
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
    # Batch processing / hang detection
    "HangDetectionLevel",
    "OperationType",
    "HangDetectionConfig",
    "TrackedOperation",
    "HangDetector",
    "get_hang_detector",
    "configure_hang_detection",
    "HangDetectionContext",
]
