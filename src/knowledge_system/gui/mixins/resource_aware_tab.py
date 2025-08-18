"""
Mixin for tabs that need resource coordination and queuing support.

This mixin provides tabs with the ability to request resources from the
ResourceCoordinator and handle queuing gracefully.
"""

from collections.abc import Callable
from typing import Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel

from ...logger import get_logger
from ...utils.resource_coordinator import ProcessingType, get_resource_coordinator

logger = get_logger(__name__)


class ResourceAwareTabMixin:
    """
    Mixin to add resource coordination capabilities to tabs.

    Tabs that inherit from this mixin can:
    1. Request resource authorization before starting operations
    2. Handle queuing gracefully with user feedback
    3. Automatically manage resource cleanup
    """

    # Signals that implementing classes should define
    resource_authorized = pyqtSignal(int, str)  # granted_concurrent, operation_id

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coordinator = get_resource_coordinator()
        self.current_operation_id: str | None = None
        self.pending_request_id: str | None = None

        # UI elements for queue status (tabs should create these)
        self.queue_status_label: QLabel | None = None
        self.queue_timer: QTimer | None = None

    def request_processing_authorization(
        self,
        processing_type: ProcessingType,
        requested_concurrent: int,
        estimated_duration: float | None = None,
    ) -> None:
        """
        Request authorization to start a processing operation.

        This will either:
        1. Immediately authorize and emit resource_authorized signal
        2. Queue the request and show "waiting" UI to user

        Args:
            processing_type: Type of processing operation
            requested_concurrent: Requested concurrent limit
            estimated_duration: Estimated duration in seconds
        """
        tab_name = getattr(self, "tab_name", self.__class__.__name__)

        # Show initial status
        self._show_queue_status("🔍 Requesting system resources...")

        # Request authorization
        self.pending_request_id = self.coordinator.request_operation(
            tab_name=tab_name,
            processing_type=processing_type,
            requested_concurrent=requested_concurrent,
            authorization_callback=self._on_authorization_granted,
            estimated_duration=estimated_duration,
        )

        # Start monitoring queue status
        self._start_queue_monitoring()

    def _on_authorization_granted(
        self, granted_concurrent: int, operation_id: str
    ) -> None:
        """Called when the operation is authorized by the coordinator."""
        self.current_operation_id = operation_id
        self.pending_request_id = None

        # Stop queue monitoring
        self._stop_queue_monitoring()
        self._hide_queue_status()

        # Emit signal for tab to start processing
        self.resource_authorized.emit(granted_concurrent, operation_id)

        logger.info(
            f"✅ {getattr(self, 'tab_name', 'Tab')} authorized with {granted_concurrent} concurrent processes"
        )

    def finish_processing(self) -> None:
        """Call this when processing is complete to free up resources."""
        if self.current_operation_id:
            self.coordinator.unregister_operation(self.current_operation_id)
            self.current_operation_id = None
            logger.info(f"🏁 {getattr(self, 'tab_name', 'Tab')} released resources")

    def cancel_pending_request(self) -> None:
        """Cancel a pending resource request (if queued)."""
        if self.pending_request_id:
            # Note: We don't have a cancel method in coordinator yet,
            # but we can stop monitoring and hide UI
            self.pending_request_id = None
            self._stop_queue_monitoring()
            self._hide_queue_status()
            logger.info(
                f"❌ {getattr(self, 'tab_name', 'Tab')} cancelled resource request"
            )

    def _start_queue_monitoring(self) -> None:
        """Start monitoring queue status for user feedback."""
        if self.queue_timer is None:
            self.queue_timer = QTimer()
            self.queue_timer.timeout.connect(self._update_queue_status)

        self.queue_timer.start(2000)  # Update every 2 seconds

    def _stop_queue_monitoring(self) -> None:
        """Stop monitoring queue status."""
        if self.queue_timer:
            self.queue_timer.stop()

    def _update_queue_status(self) -> None:
        """Update the queue status display for user feedback."""
        if not self.pending_request_id:
            self._stop_queue_monitoring()
            return

        # Get current queue info
        load_info = self.coordinator.get_system_load_info()
        queue_size = len(
            [
                op
                for op in load_info.get("operations", [])
                if op.get("tab") != getattr(self, "tab_name", "")
            ]
        )

        if queue_size > 0:
            self._show_queue_status(
                f"⏳ Waiting in queue... {queue_size} operations ahead"
            )
        else:
            self._show_queue_status("⏳ Waiting for system resources...")

    def _show_queue_status(self, message: str) -> None:
        """Show queue status message to user."""
        if hasattr(self, "append_log"):
            self.append_log(message)

        if self.queue_status_label:
            self.queue_status_label.setText(message)
            self.queue_status_label.setVisible(True)

    def _hide_queue_status(self) -> None:
        """Hide queue status display."""
        if self.queue_status_label:
            self.queue_status_label.setVisible(False)

    def get_resource_status(self) -> dict:
        """Get current resource status for this tab."""
        return {
            "has_active_operation": self.current_operation_id is not None,
            "has_pending_request": self.pending_request_id is not None,
            "operation_id": self.current_operation_id,
            "request_id": self.pending_request_id,
            "system_load": self.coordinator.get_system_load_info(),
        }
