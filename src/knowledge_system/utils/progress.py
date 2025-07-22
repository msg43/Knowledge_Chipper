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

# Import all classes for backward compatibility
from .cancellation import CancellationToken, CancellationError
from .tracking import (
    TranscriptionProgress, SummarizationProgress, ExtractionProgress, MOCProgress,
    TaskStatus, TaskInfo, ProgressTracker
)
from .display import ProgressDisplay
from .batch_processing import (
    HangDetectionLevel, OperationType, HangDetectionConfig, TrackedOperation,
    HangDetector, get_hang_detector, configure_hang_detection, HangDetectionContext
)

# Re-export all classes for compatibility
__all__ = [
    # Cancellation
    'CancellationToken', 'CancellationError',
    
    # Progress tracking
    'TranscriptionProgress', 'SummarizationProgress', 'ExtractionProgress', 'MOCProgress',
    'TaskStatus', 'TaskInfo', 'ProgressTracker',
    
    # Display
    'ProgressDisplay',
    
    # Batch processing / hang detection
    'HangDetectionLevel', 'OperationType', 'HangDetectionConfig', 'TrackedOperation',
    'HangDetector', 'get_hang_detector', 'configure_hang_detection', 'HangDetectionContext'
]
