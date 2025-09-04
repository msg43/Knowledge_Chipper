"""
Example: How to integrate the ResourceCoordinator with existing tabs.

This shows how transcription_tab.py would be modified to use
the queuing and authorization system.
"""

from PyQt6.QtWidgets import QLabel

from ..gui.components.base_tab import BaseTab
from ..gui.mixins.resource_aware_tab import ResourceAwareTabMixin
from ..gui.workers.processing_workers import EnhancedTranscriptionWorker
from ..utils.resource_coordinator import ProcessingType


class ExampleResourceAwareTranscriptionTab(BaseTab, ResourceAwareTabMixin):
    """Example of how to make TranscriptionTab resource-aware."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_name = "Local Transcription"

        # Connect the authorization signal
        self.resource_authorized.connect(self._start_processing_with_resources)

        # Add queue status label to UI
        self.queue_status_label = QLabel()
        self.queue_status_label.setVisible(False)
        # In real implementation, add this to the layout

    def _start_processing(self) -> None:
        """
        MODIFIED: Instead of starting immediately, request authorization first.
        """
        # Get files to process
        files = self._get_files_to_process()
        if not files:
            self.show_warning("Warning", "No files selected for transcription")
            return

        # Validate inputs
        if not self.validate_inputs():
            return

        # Get requested concurrent setting from UI
        requested_concurrent = self.max_concurrent.value()

        # Estimate duration (optional)
        estimated_duration = len(files) * 60.0  # Rough estimate: 1 minute per file

        # Request authorization instead of starting immediately
        self.append_log(
            f"🔍 Requesting authorization for {len(files)} files with {requested_concurrent} concurrent processes..."
        )

        self.request_processing_authorization(
            processing_type=ProcessingType.TRANSCRIPTION,
            requested_concurrent=requested_concurrent,
            estimated_duration=estimated_duration,
        )

        # Disable start button while waiting
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Requesting Resources...")

    def _start_processing_with_resources(
        self, granted_concurrent: int, operation_id: str
    ) -> None:
        """
        Called when resources are authorized - now actually start processing.
        """
        self.append_log(
            f"✅ Authorized! Starting transcription with {granted_concurrent} concurrent processes"
        )

        # Update UI to show granted vs requested
        if granted_concurrent < self.max_concurrent.value():
            self.append_log(
                f"ℹ️ Note: Granted {granted_concurrent} of {self.max_concurrent.value()} requested due to system load"
            )

        # Get transcription settings
        gui_settings = self._get_transcription_settings()
        gui_settings["max_concurrent"] = granted_concurrent  # Use granted limit

        # Get files again (in case user changed them while waiting)
        files = self._get_files_to_process()

        # Start the actual transcription worker
        self.transcription_worker = EnhancedTranscriptionWorker(
            files, self.settings, gui_settings, self
        )

        # Connect worker signals
        self.transcription_worker.progress_updated.connect(self._update_progress)
        self.transcription_worker.processing_finished.connect(
            self._processing_finished_with_cleanup
        )
        self.transcription_worker.processing_error.connect(
            self._processing_error_with_cleanup
        )

        # Start worker
        self.active_workers.append(self.transcription_worker)
        self.transcription_worker.start()

        # Update UI
        self.start_btn.setText("Stop Transcription")
        self.start_btn.setEnabled(True)

        self.status_updated.emit("Transcription in progress...")

    def _processing_finished_with_cleanup(self):
        """Handle transcription completion WITH resource cleanup."""
        # Call original finish handler
        self._processing_finished()

        # Clean up resources
        self.finish_processing()

        self.append_log("🏁 Transcription completed and resources released")

    def _processing_error_with_cleanup(self, error_msg: str):
        """Handle transcription error WITH resource cleanup."""
        # Call original error handler
        self._processing_error(error_msg)

        # Clean up resources
        self.finish_processing()

        self.append_log("🏁 Resources released after error")

    def _stop_processing(self) -> None:
        """
        MODIFIED: Handle stop for both queued and active operations.
        """
        if self.pending_request_id:
            # Cancel pending request
            self.cancel_pending_request()
            self.append_log("❌ Cancelled resource request")
            self.start_btn.setText("Start Transcription")
            self.start_btn.setEnabled(True)

        elif self.current_operation_id:
            # Stop active operation
            if self.transcription_worker and self.transcription_worker.isRunning():
                self.transcription_worker.should_stop = True
                self.transcription_worker.terminate()
                self.transcription_worker.wait(3000)

            # Clean up resources
            self.finish_processing()

            self.append_log("🛑 Transcription stopped and resources released")
            self.start_btn.setText("Start Transcription")
            self.start_btn.setEnabled(True)


# Example usage scenario:
def example_concurrent_scenario():
    """
    Example of how the system would handle the scenario you asked about.
    """

    # User clicks "Start" on YouTube Tab
    # youtube_tab.request_processing_authorization(
    #     ProcessingType.YOUTUBE_DOWNLOAD,
    #     requested_concurrent=8
    # )
    # → Immediately authorized: 8 concurrent downloads
    # → YouTube tab starts processing

    # User clicks "Start" on Transcription Tab (while YouTube is running)
    # transcription_tab.request_processing_authorization(
    #     ProcessingType.TRANSCRIPTION,
    #     requested_concurrent=8
    # )
    # → Coordinator calculates: 8 already used, system max = 12, available = 4
    # → Immediately authorized: 4 concurrent transcriptions
    # → Transcription tab starts with reduced concurrency

    # User clicks "Start" on Summarization Tab (while both are running)
    # summarization_tab.request_processing_authorization(
    #     ProcessingType.SUMMARIZATION,
    #     requested_concurrent=4
    # )
    # → Coordinator calculates: 12 already used, system max = 12, available = 0
    # → QUEUED: "⏳ Waiting in queue... 0 operations ahead"
    # → User sees: "Requesting Resources..." button + queue status

    # When YouTube processing finishes:
    # → youtube_tab.finish_processing() called
    # → Coordinator frees 8 concurrent slots
    # → Queue processor wakes up
    # → Summarization tab authorized with 4 concurrent processes
    # → User sees: "✅ Authorized! Starting summarization with 4 concurrent processes"
