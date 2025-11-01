"""
HCE Update Confirmation Dialog

Confirms user intent to update HCE database with corrected speaker names
and reprocess all affected claims and evidence.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ...logger import get_logger

logger = get_logger(__name__)


class HCEReprocessWorker(QThread):
    """Background worker thread for HCE reprocessing."""

    progress_updated = pyqtSignal(str)  # Progress message
    processing_complete = pyqtSignal(bool, str)  # (success, message)

    def __init__(
        self,
        source_id: str,
        transcript_data: dict,
        hce_config: dict | None = None,
    ):
        super().__init__()
        self.source_id = source_id
        self.transcript_data = transcript_data
        self.hce_config = hce_config

    def run(self):
        """Run HCE reprocessing in background."""
        try:
            from ...processors.speaker_processor import SpeakerProcessor

            def progress_callback(message: str):
                self.progress_updated.emit(message)

            success, message = SpeakerProcessor.reprocess_hce_with_updated_speakers(
                source_id=self.source_id,
                source_id=self.source_id,
                transcript_data=self.transcript_data,
                hce_config=self.hce_config,
                progress_callback=progress_callback,
            )

            self.processing_complete.emit(success, message)

        except Exception as e:
            logger.error(f"HCE reprocessing worker failed: {e}")
            self.processing_complete.emit(False, f"Reprocessing failed: {str(e)}")


class HCEUpdateConfirmationDialog(QDialog):
    """
    Confirm HCE database update and reprocessing.

    Explains:
    - Speaker names will be updated in HCE database
    - All claims, evidence, and entities will be reprocessed
    - Estimated time and cost for reprocessing
    - Cannot be undone (existing HCE data will be replaced)
    """

    def __init__(
        self,
        source_id: str,
        speaker_mappings: dict[str, str],
        transcript_data: dict,
        segment_count: int = 0,
        hce_config: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.source_id = source_id
        self.speaker_mappings = speaker_mappings
        self.transcript_data = transcript_data
        self.segment_count = segment_count
        self.hce_config = hce_config
        self.reprocess_worker = None

        self.setWindowTitle("Update HCE Database")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("Update HCE Database with Corrected Speaker Names")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # Warning message
        warning = QLabel(
            "⚠️  This will update speaker names and reprocess all HCE analysis data.\n"
            "The existing analysis will be replaced with new results."
        )
        warning.setStyleSheet(
            "color: #f39c12; background-color: #2c2c2c; padding: 10px; "
            "border-radius: 5px; margin-bottom: 10px;"
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Changes summary
        changes_label = QLabel("Speaker Name Changes:")
        changes_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(changes_label)

        changes_text = QTextEdit()
        changes_text.setReadOnly(True)
        changes_text.setMaximumHeight(120)
        changes_text.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #3c3c3c; "
            "padding: 5px; font-family: monospace;"
        )

        # Format speaker mappings
        changes_content = []
        for old_speaker, new_speaker in self.speaker_mappings.items():
            changes_content.append(f"  '{old_speaker}'  →  '{new_speaker}'")
        changes_text.setPlainText("\n".join(changes_content))
        layout.addWidget(changes_text)

        # What will be reprocessed
        reprocess_label = QLabel("What will be reprocessed:")
        reprocess_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(reprocess_label)

        reprocess_info = QLabel(
            f"• All {self.segment_count} segments will be updated\n"
            "• Existing claims, evidence spans, and relations will be deleted\n"
            "• Existing people, jargon, and mental models will be deleted\n"
            "• HCE pipeline will re-extract all entities with correct speaker context\n"
            "• New analysis will be saved to the database"
        )
        reprocess_info.setStyleSheet("margin-left: 20px; margin-bottom: 10px;")
        reprocess_info.setWordWrap(True)
        layout.addWidget(reprocess_info)

        # Estimate
        estimate_label = QLabel(
            f"⏱️  Estimated time: ~{self._estimate_processing_time()} minutes\n"
            f"💰  Estimated cost: ~${self._estimate_cost():.2f} (if using cloud LLM)"
        )
        estimate_label.setStyleSheet(
            "color: #95a5a6; font-style: italic; margin-bottom: 10px;"
        )
        layout.addWidget(estimate_label)

        # Progress area (hidden initially)
        self.progress_widget = QVBoxLayout()
        self.progress_label = QLabel("Processing...")
        self.progress_label.setStyleSheet("font-weight: bold;")
        self.progress_widget.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indeterminate
        self.progress_widget.addWidget(self.progress_bar)

        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)
        self.progress_text.setMaximumHeight(100)
        self.progress_text.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #3c3c3c; "
            "padding: 5px; font-family: monospace; font-size: 9pt;"
        )
        self.progress_widget.addWidget(self.progress_text)

        # Initially hide progress
        self.progress_label.hide()
        self.progress_bar.hide()
        self.progress_text.hide()

        layout.addLayout(self.progress_widget)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.confirm_button = QPushButton("Update and Reprocess")
        self.confirm_button.setStyleSheet(
            "background-color: #3498db; color: white; font-weight: bold; "
            "padding: 8px 16px;"
        )
        self.confirm_button.clicked.connect(self._start_reprocessing)
        button_layout.addWidget(self.confirm_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _estimate_processing_time(self) -> int:
        """Estimate processing time in minutes based on segment count."""
        # Rough estimate: ~1-2 seconds per segment for mining + evaluation
        if self.segment_count == 0:
            return 1

        minutes = (self.segment_count * 1.5) / 60  # Convert seconds to minutes
        return max(1, int(minutes))

    def _estimate_cost(self) -> float:
        """Estimate API cost based on segment count."""
        # Rough estimate for GPT-4o-mini: ~$0.001 per segment
        if self.segment_count == 0:
            return 0.05

        return self.segment_count * 0.001

    def _start_reprocessing(self):
        """Start the HCE reprocessing in background."""
        # Disable buttons
        self.confirm_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

        # Show progress widgets
        self.progress_label.show()
        self.progress_bar.show()
        self.progress_text.show()

        # Start worker thread
        self.reprocess_worker = HCEReprocessWorker(
            source_id=self.source_id,
            source_id=self.source_id,
            transcript_data=self.transcript_data,
            hce_config=self.hce_config,
        )

        self.reprocess_worker.progress_updated.connect(self._on_progress_update)
        self.reprocess_worker.processing_complete.connect(self._on_processing_complete)
        self.reprocess_worker.start()

        # Add initial log
        self.progress_text.append("Starting HCE reprocessing...")

    def _on_progress_update(self, message: str):
        """Handle progress updates from worker."""
        # Check if we should auto-scroll BEFORE appending
        scrollbar = self.progress_text.verticalScrollBar()
        should_scroll = scrollbar and scrollbar.value() >= scrollbar.maximum() - 10

        self.progress_text.append(message)

        # Only auto-scroll if user was already at the bottom
        if should_scroll and scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _on_processing_complete(self, success: bool, message: str):
        """Handle completion of reprocessing."""
        if self.progress_bar:
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(100)

        if success:
            self.progress_label.setText("✅ Reprocessing Complete!")
            self.progress_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
            self.progress_text.append(f"\n✅ SUCCESS: {message}")

            # Change button to close
            self.confirm_button.hide()
            self.cancel_button.setText("Close")
            self.cancel_button.setEnabled(True)
            self.cancel_button.clicked.disconnect()
            self.cancel_button.clicked.connect(self.accept)
        else:
            self.progress_label.setText("❌ Reprocessing Failed")
            self.progress_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.progress_text.append(f"\n❌ ERROR: {message}")

            # Re-enable cancel
            self.cancel_button.setText("Close")
            self.cancel_button.setEnabled(True)

        logger.info(f"HCE reprocessing completed: success={success}, message={message}")


def show_hce_update_dialog(
    source_id: str,
    speaker_mappings: dict[str, str],
    transcript_data: dict,
    segment_count: int = 0,
    hce_config: dict | None = None,
    parent=None,
) -> bool:
    """
    Show HCE update confirmation dialog and execute reprocessing if confirmed.

    Args:
        source_id: HCE episode ID
        source_id: Video/media ID
        speaker_mappings: Dict of old_speaker -> new_speaker
        transcript_data: Updated transcript with new speaker names
        segment_count: Number of segments (for estimation)
        hce_config: Optional HCE configuration
        parent: Parent widget

    Returns:
        True if reprocessing completed successfully, False otherwise
    """
    dialog = HCEUpdateConfirmationDialog(
        source_id=source_id,
        source_id=source_id,
        speaker_mappings=speaker_mappings,
        transcript_data=transcript_data,
        segment_count=segment_count,
        hce_config=hce_config,
        parent=parent,
    )

    result = dialog.exec()
    return result == QDialog.DialogCode.Accepted
