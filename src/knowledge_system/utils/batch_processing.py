"""
Batch Processing and Hang Detection

Provides hang detection for long-running batch operations to prevent
operations from hanging indefinitely.
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional
from collections.abc import Callable

from .cancellation import CancellationToken

logger = None


def get_logger(name: str = "batch_processing"):
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
# HANG DETECTION
# ============================================================================


class HangDetectionLevel(Enum):
    """Levels of hang detection aggressiveness."""

    DISABLED = "disabled"
    BASIC = "basic"  # Only detect obvious hangs
    MODERATE = "moderate"  # Balanced detection
    AGGRESSIVE = "aggressive"  # Detect potential hangs quickly


class OperationType(Enum):
    """Types of operations for hang detection configuration."""

    TRANSCRIPTION = "transcription"
    SUMMARIZATION = "summarization"
    YOUTUBE_EXTRACTION = "youtube_extraction"
    MOC_GENERATION = "moc_generation"
    FILE_PROCESSING = "file_processing"
    NETWORK_OPERATION = "network_operation"
    MODEL_INFERENCE = "model_inference"


@dataclass
class HangDetectionConfig:
    """Configuration for hang detection system."""

    level: HangDetectionLevel = HangDetectionLevel.MODERATE
    check_interval: int = 30  # seconds between checks

    # Timeout thresholds per operation type (in seconds)
    timeouts: dict[OperationType, int] = field(
        default_factory=lambda: {
            OperationType.TRANSCRIPTION: 300,  # 5 minutes per file
            OperationType.SUMMARIZATION: 180,  # 3 minutes per file
            OperationType.YOUTUBE_EXTRACTION: 120,  # 2 minutes per URL
            OperationType.MOC_GENERATION: 600,  # 10 minutes total
            OperationType.FILE_PROCESSING: 240,  # 4 minutes per file
            OperationType.NETWORK_OPERATION: 60,  # 1 minute per request
            OperationType.MODEL_INFERENCE: 300,  # 5 minutes per inference
        }
    )

    # Multipliers based on detection level
    level_multipliers: dict[HangDetectionLevel, float] = field(
        default_factory=lambda: {
            HangDetectionLevel.DISABLED: 0,  # No timeouts
            HangDetectionLevel.BASIC: 3.0,  # Very lenient
            HangDetectionLevel.MODERATE: 2.0,  # Reasonable timeouts
            HangDetectionLevel.AGGRESSIVE: 1.0,  # Quick detection
        }
    )

    def get_timeout(self, operation_type: OperationType) -> int | None:
        """Get timeout for operation type with level multiplier applied."""
        if self.level == HangDetectionLevel.DISABLED:
            return None

        base_timeout = self.timeouts.get(operation_type, 300)  # 5 min default
        multiplier = self.level_multipliers.get(self.level, 2.0)
        return int(base_timeout * multiplier)

    def set_custom_timeout(self, operation_type: OperationType, timeout: int):
        """Set custom timeout for an operation type."""
        self.timeouts[operation_type] = timeout


@dataclass
class TrackedOperation:
    """Information about an operation being tracked for hangs."""

    operation_id: str
    operation_type: OperationType
    start_time: datetime
    last_update: datetime
    cancellation_token: CancellationToken | None = None
    recovery_callback: Callable[[str], None] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_stale(self, timeout_seconds: int) -> bool:
        """Check if operation has been inactive for too long."""
        if timeout_seconds <= 0:
            return False
        elapsed = (datetime.now() - self.last_update).total_seconds()
        return elapsed > timeout_seconds

    def total_runtime(self) -> timedelta:
        """Get total runtime of the operation."""
        return datetime.now() - self.start_time


class HangDetector:
    """Monitors operations for potential hangs and provides recovery."""

    def __init__(self, config: HangDetectionConfig) -> None:
        self.config = config
        self.operations: dict[str, TrackedOperation] = {}
        self.monitoring = False
        self.monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start_monitoring(self):
        """Start the hang detection monitoring thread."""
        if self.config.level == HangDetectionLevel.DISABLED:
            get_logger().info("Hang detection is disabled")
            return

        if self.monitoring:
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        get_logger().info(
            f"Started hang detection monitoring (level: {self.config.level.value})"
        )

    def stop_monitoring(self) -> None:
        """Stop the hang detection monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        get_logger().info("Stopped hang detection monitoring")

    def register_operation(
        self,
        operation_id: str,
        operation_type: OperationType,
        cancellation_token: CancellationToken | None = None,
        recovery_callback: Callable[[str], None] | None = None,
    ):
        """Register an operation for hang detection."""
        with self._lock:
            now = datetime.now()
            self.operations[operation_id] = TrackedOperation(
                operation_id=operation_id,
                operation_type=operation_type,
                start_time=now,
                last_update=now,
                cancellation_token=cancellation_token,
                recovery_callback=recovery_callback,
            )
        get_logger().debug(f"Registered operation for hang detection: {operation_id}")

    def unregister_operation(self, operation_id: str):
        """Unregister an operation from hang detection."""
        with self._lock:
            if operation_id in self.operations:
                del self.operations[operation_id]
                get_logger().debug(
                    f"Unregistered operation from hang detection: {operation_id}"
                )

    def update_operation(
        self, operation_id: str, metadata: dict[str, Any] | None = None
    ):
        """Update an operation's last activity time."""
        with self._lock:
            if operation_id in self.operations:
                self.operations[operation_id].last_update = datetime.now()
                if metadata:
                    self.operations[operation_id].metadata.update(metadata)

    def _monitor_loop(self):
        """Main monitoring loop that checks for hung operations."""
        while self.monitoring:
            try:
                self._check_for_hangs()
                time.sleep(self.config.check_interval)
            except Exception as e:
                get_logger().error(f"Error in hang detection loop: {e}")
                time.sleep(5)  # Brief pause before retrying

    def _check_for_hangs(self):
        """Check all registered operations for potential hangs."""
        with self._lock:
            hung_operations = []

            for op in self.operations.values():
                timeout = self.config.get_timeout(op.operation_type)
                if timeout and op.is_stale(timeout):
                    hung_operations.append(op)

            # Handle hung operations outside the lock
            for op in hung_operations:
                self._handle_hung_operation(op)

    def _handle_hung_operation(self, operation: TrackedOperation):
        """Handle a detected hung operation."""
        runtime = operation.total_runtime()
        timeout = self.config.get_timeout(operation.operation_type)

        get_logger().warning(
            f"Detected hung operation: {operation.operation_id} "
            f"(type: {operation.operation_type.value}, "
            f"runtime: {runtime}, timeout: {timeout}s)"
        )

        # Try cancellation first
        if operation.cancellation_token:
            try:
                operation.cancellation_token.cancel(
                    f"Operation hung (runtime: {runtime}, timeout: {timeout}s)"
                )
                get_logger().info(f"Cancelled hung operation: {operation.operation_id}")
            except Exception as e:
                get_logger().error(
                    f"Failed to cancel hung operation {operation.operation_id}: {e}"
                )

        # Try recovery callback
        if operation.recovery_callback:
            try:
                operation.recovery_callback(operation.operation_id)
                get_logger().info(
                    f"Executed recovery callback for: {operation.operation_id}"
                )
            except Exception as e:
                get_logger().error(
                    f"Recovery callback failed for {operation.operation_id}: {e}"
                )

        # Remove from tracking
        with self._lock:
            if operation.operation_id in self.operations:
                del self.operations[operation.operation_id]

    def get_status(self) -> dict[str, Any]:
        """Get current status of hang detection."""
        with self._lock:
            active_ops = len(self.operations)
            oldest_op = None

            if self.operations:
                oldest = min(self.operations.values(), key=lambda op: op.start_time)
                oldest_op = {
                    "id": oldest.operation_id,
                    "type": oldest.operation_type.value,
                    "runtime_seconds": int(oldest.total_runtime().total_seconds()),
                }

            return {
                "enabled": self.monitoring,
                "level": self.config.level.value,
                "active_operations": active_ops,
                "oldest_operation": oldest_op,
                "check_interval": self.config.check_interval,
            }


# Global hang detector instance
_hang_detector: HangDetector | None = None


def get_hang_detector() -> HangDetector:
    """Get the global hang detector instance."""
    global _hang_detector
    if _hang_detector is None:
        config = HangDetectionConfig()
        _hang_detector = HangDetector(config)
    return _hang_detector


def configure_hang_detection(level: HangDetectionLevel):
    """Configure global hang detection level."""
    global _hang_detector

    # Stop existing detector if running
    if _hang_detector:
        _hang_detector.stop_monitoring()

    config = HangDetectionConfig(level)
    _hang_detector = HangDetector(config)
    _hang_detector.start_monitoring()
    get_logger().info(f"Configured hang detection to {level.value} level")


class HangDetectionContext:
    """Context manager for automatic hang detection registration."""

    def __init__(
        self,
        operation_id: str,
        operation_type: OperationType,
        cancellation_token: CancellationToken | None = None,
        recovery_callback: Callable[[str], None] | None = None,
        custom_timeout: int | None = None,
    ) -> None:
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.cancellation_token = cancellation_token
        self.recovery_callback = recovery_callback
        self.custom_timeout = custom_timeout
        self.detector = get_hang_detector()

    def __enter__(self):
        """Register operation for hang detection."""
        if self.custom_timeout:
            self.detector.config.set_custom_timeout(
                self.operation_type, self.custom_timeout
            )

        self.detector.register_operation(
            self.operation_id,
            self.operation_type,
            self.cancellation_token,
            self.recovery_callback,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Unregister operation from hang detection."""
        self.detector.unregister_operation(self.operation_id)

    def update(self, metadata: dict[str, Any] | None = None):
        """Update operation status."""
        self.detector.update_operation(self.operation_id, metadata)
