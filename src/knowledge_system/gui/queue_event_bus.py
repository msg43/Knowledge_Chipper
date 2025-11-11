"""
Queue Event Bus

Provides real-time event propagation for queue status updates.
Thread-safe implementation using Qt signals.
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..logger import get_logger

logger = get_logger(__name__)

# Environment variable for debug logging
QUEUE_DEBUG = os.getenv("QUEUE_DEBUG", "").lower() in ("1", "true", "yes")


@dataclass
class QueueEvent:
    """Represents a queue status change event."""

    source_id: str
    stage: str
    status: str
    progress_percent: float = 0.0
    metadata: dict[str, Any] | None = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "stage": self.stage,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class QueueEventBus(QObject):
    """
    Central event bus for queue status updates.

    Uses Qt signals for thread-safe event propagation to GUI components.
    """

    # Signals
    stage_status_changed = pyqtSignal(QueueEvent)  # Individual stage update
    source_completed = pyqtSignal(str)  # Source ID when all stages complete
    batch_progress = pyqtSignal(int, int)  # Completed, Total
    error_occurred = pyqtSignal(str, str, str)  # Source ID, Stage, Error

    def __init__(self):
        super().__init__()
        self._event_buffer: list[QueueEvent] = []
        self._buffer_timer = None
        self._enable_buffering = True
        self._buffer_interval_ms = 100  # Batch events every 100ms

        logger.info("QueueEventBus initialized")

    def emit_stage_update(
        self,
        source_id: str,
        stage: str,
        status: str,
        progress_percent: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Emit a stage status update event.

        Thread-safe - can be called from any thread.
        """
        event = QueueEvent(
            source_id=source_id,
            stage=stage,
            status=status,
            progress_percent=progress_percent,
            metadata=metadata,
        )

        if self._enable_buffering:
            # Add to buffer for batched emission
            self._event_buffer.append(event)

            # Start timer if not already running
            if not self._buffer_timer:
                self._buffer_timer = QTimer.singleShot(
                    self._buffer_interval_ms, self._flush_buffer
                )
        else:
            # Emit immediately
            self._emit_event(event)

        # Check for source completion
        if status == "completed" and stage == "flagship_evaluation":
            self.source_completed.emit(source_id)

        # Check for errors
        if status == "failed" and metadata:
            error = metadata.get("error", "Unknown error")
            self.error_occurred.emit(source_id, stage, error)

    def emit_batch_progress(self, completed: int, total: int):
        """
        Emit batch processing progress.

        Thread-safe - can be called from any thread.
        """
        QTimer.singleShot(0, lambda: self.batch_progress.emit(completed, total))

    def set_buffering(self, enabled: bool, interval_ms: int = 100):
        """
        Configure event buffering.

        Args:
            enabled: Whether to buffer events
            interval_ms: Buffer interval in milliseconds
        """
        self._enable_buffering = enabled
        self._buffer_interval_ms = interval_ms

        if not enabled:
            self._flush_buffer()

    def _emit_event(self, event: QueueEvent):
        """Emit event on the main thread."""
        # Use QTimer to ensure emission on main thread
        QTimer.singleShot(0, lambda: self.stage_status_changed.emit(event))

        if QUEUE_DEBUG:
            logger.debug(
                f"[QUEUE_EVENT] Emitted: source_id={event.source_id}, "
                f"stage={event.stage}, status={event.status}, "
                f"progress={event.progress_percent:.1f}%, "
                f"metadata={event.metadata}"
            )
        else:
            logger.debug(
                f"Queue event: source_id={event.source_id}, stage={event.stage}, "
                f"status={event.status}, progress={event.progress_percent:.1f}%"
            )

    def _flush_buffer(self):
        """Flush buffered events."""
        if not self._event_buffer:
            return

        # Process all buffered events
        events = self._event_buffer[:]
        self._event_buffer.clear()
        self._buffer_timer = None

        # Emit events
        for event in events:
            self._emit_event(event)

        logger.debug(f"Flushed {len(events)} buffered queue events")


_QUEUE_EVENT_BUS: QueueEventBus | None = None


# Convenience function for getting the singleton instance
def get_queue_event_bus() -> QueueEventBus:
    """Get the singleton QueueEventBus instance."""
    global _QUEUE_EVENT_BUS
    if _QUEUE_EVENT_BUS is None:
        _QUEUE_EVENT_BUS = QueueEventBus()
    return _QUEUE_EVENT_BUS
