"""
Batch Speaker Assignment Dialog

Dialog for processing multiple recordings with speaker identification,
allowing bulk operations and consistent speaker assignments across files.
"""

from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...database.speaker_models import get_speaker_db_service
from ...logger import get_logger
from ...processors.speaker_processor import SpeakerData

# Pattern-based suggestions removed - LLM only approach

logger = get_logger(__name__)


class RecordingItem:
    """Represents a recording in the batch processing queue."""

    def __init__(self, file_path: Path, speaker_data_list: list[SpeakerData]):
        """
        Initialize recording item.

        Args:
            file_path: Path to the recording file
            speaker_data_list: List of detected speakers
        """
        self.file_path = file_path
        self.speaker_data_list = speaker_data_list
        self.assignments: dict[str, str] = {}
        self.processed = False
        self.confidence_scores: dict[str, float] = {}

        # Calculate overall confidence
        if speaker_data_list:
            total_confidence = sum(
                speaker.confidence_score for speaker in speaker_data_list
            )
            self.overall_confidence = total_confidence / len(speaker_data_list)
        else:
            self.overall_confidence = 0.0

    def get_speaker_count(self) -> int:
        """Get number of speakers in this recording."""
        return len(self.speaker_data_list)

    def get_total_duration(self) -> float:
        """Get total duration of all speakers."""
        return sum(speaker.total_duration for speaker in self.speaker_data_list)

    def has_assignments(self) -> bool:
        """Check if this recording has speaker assignments."""
        return len(self.assignments) > 0

    def is_complete(self) -> bool:
        """Check if all speakers have been assigned."""
        return len(self.assignments) == len(self.speaker_data_list)


class BatchProcessingWorker(QThread):
    """Worker thread for batch processing speaker assignments."""

    progress_updated = pyqtSignal(int, str)  # progress, message
    recording_processed = pyqtSignal(str, dict)  # file_path, assignments
    batch_completed = pyqtSignal(bool, str)  # success, message

    def __init__(self, recordings: list[RecordingItem], apply_to_all: bool = False):
        """
        Initialize batch processing worker.

        Args:
            recordings: List of recordings to process
            apply_to_all: Whether to apply consistent assignments across all recordings
        """
        super().__init__()
        self.recordings = recordings
        self.apply_to_all = apply_to_all
        self.cancelled = False

    def cancel(self):
        """Cancel the batch processing."""
        self.cancelled = True

    def run(self):
        """Run the batch processing."""
        try:
            total_recordings = len(self.recordings)
            processed_count = 0

            for i, recording in enumerate(self.recordings):
                if self.cancelled:
                    break

                # Update progress
                progress = int((i / total_recordings) * 100)
                self.progress_updated.emit(
                    progress, f"Processing {recording.file_path.name}..."
                )

                # Process recording (placeholder - actual processing would be done in main thread)
                if recording.has_assignments():
                    self.recording_processed.emit(
                        str(recording.file_path), recording.assignments
                    )
                    processed_count += 1

                # Small delay to show progress
                self.msleep(100)

            # Complete
            success = processed_count > 0 and not self.cancelled
            message = f"Processed {processed_count}/{total_recordings} recordings"
            self.batch_completed.emit(success, message)

        except Exception as e:
            logger.error(f"Error in batch processing worker: {e}")
            self.batch_completed.emit(False, f"Error: {e}")


class BatchSpeakerAssignmentDialog(QDialog):
    """Dialog for batch processing multiple recordings with speaker identification."""

    # Signals
    batch_completed = pyqtSignal(dict)  # {file_path: assignments}
    batch_cancelled = pyqtSignal()

    def __init__(self, recordings: list[RecordingItem], parent=None):
        """
        Initialize the batch speaker assignment dialog.

        Args:
            recordings: List of RecordingItem objects to process
            parent: Parent widget
        """
        super().__init__(parent)
        self.recordings = recordings
        self.current_index = 0
        self.completed_assignments: dict[str, dict[str, str]] = {}
        self.consistent_speakers: dict[str, str] = {}  # For cross-recording consistency

        self.db_service = get_speaker_db_service()

        self._setup_ui()
        self._connect_signals()
        self._analyze_batch_consistency()
        self._load_first_recording()

    def _setup_ui(self):
        """Setup the batch dialog UI."""
        self.setWindowTitle("Batch Speaker Assignment")
        self.setModal(True)
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)

        # Header section
        header_layout = self._create_header()
        main_layout.addLayout(header_layout)

        # Content splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Recording list
        left_panel = self._create_recording_list_panel()
        content_splitter.addWidget(left_panel)

        # Right panel - Current recording details
        right_panel = self._create_current_recording_panel()
        content_splitter.addWidget(right_panel)

        # Set splitter proportions
        content_splitter.setSizes([300, 700])
        main_layout.addWidget(content_splitter)

        # Options section
        options_section = self._create_options_section()
        main_layout.addWidget(options_section)

        # Progress section
        progress_section = self._create_progress_section()
        main_layout.addWidget(progress_section)

        # Button box
        button_box = self._create_button_box()
        main_layout.addWidget(button_box)

    def _create_header(self) -> QHBoxLayout:
        """Create the header section."""
        layout = QHBoxLayout()

        # Title and info
        title_layout = QVBoxLayout()

        title_label = QLabel("Batch Speaker Assignment")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_layout.addWidget(title_label)

        info_label = QLabel(f"Processing {len(self.recordings)} recordings")
        info_label.setFont(QFont("Arial", 10))
        info_label.setStyleSheet("color: #666;")
        title_layout.addWidget(info_label)

        layout.addLayout(title_layout)
        layout.addStretch()

        # Statistics
        stats_layout = QVBoxLayout()

        total_speakers = sum(
            recording.get_speaker_count() for recording in self.recordings
        )
        total_duration = sum(
            recording.get_total_duration() for recording in self.recordings
        )

        stats_label = QLabel(
            f"📊 {total_speakers} total speakers\n"
            f"⏱️ {total_duration/60:.1f} minutes total"
        )
        stats_label.setFont(QFont("Arial", 9))
        stats_label.setStyleSheet(
            "color: #888; background-color: #f5f5f5; padding: 8px; border-radius: 4px;"
        )
        stats_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        stats_layout.addWidget(stats_label)

        layout.addLayout(stats_layout)

        return layout

    def _create_recording_list_panel(self) -> QWidget:
        """Create the recording list panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Panel title
        title_label = QLabel("📁 Recordings")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # Recording list
        self.recording_list = QListWidget()
        self.recording_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        # Populate recording list
        for i, recording in enumerate(self.recordings):
            item = QListWidgetItem()

            # Create item text with status indicators
            status_icon = "✅" if recording.has_assignments() else "⏳"
            confidence_text = (
                f"{recording.overall_confidence:.0%}"
                if recording.overall_confidence > 0
                else "N/A"
            )

            item_text = (
                f"{status_icon} {recording.file_path.name}\n"
                f"   {recording.get_speaker_count()} speakers, "
                f"confidence: {confidence_text}"
            )

            item.setText(item_text)
            item.setData(Qt.ItemDataRole.UserRole, i)  # Store index

            # Color coding based on status
            if recording.has_assignments():
                item.setBackground(Qt.GlobalColor.lightGray)
            elif recording.overall_confidence > 0.7:
                item.setBackground(Qt.GlobalColor.green)
            elif recording.overall_confidence > 0.4:
                item.setBackground(Qt.GlobalColor.yellow)
            else:
                item.setBackground(Qt.GlobalColor.red)

            self.recording_list.addItem(item)

        layout.addWidget(self.recording_list)

        # Quick actions
        actions_layout = QHBoxLayout()

        self.prev_btn = QPushButton("⬅️ Previous")
        self.prev_btn.clicked.connect(self._go_to_previous)
        actions_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next ➡️")
        self.next_btn.clicked.connect(self._go_to_next)
        actions_layout.addWidget(self.next_btn)

        layout.addLayout(actions_layout)

        return panel

    def _create_current_recording_panel(self) -> QWidget:
        """Create the current recording details panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Current recording info
        self.current_info_label = QLabel("Select a recording to begin")
        self.current_info_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(self.current_info_label)

        # Speaker assignment area
        self.speaker_area = QScrollArea()
        self.speaker_area.setWidgetResizable(True)
        self.speaker_area.setMinimumHeight(300)
        layout.addWidget(self.speaker_area)

        # Assignment actions
        actions_layout = QHBoxLayout()

        self.assign_speakers_btn = QPushButton("🎭 Assign Speakers")
        self.assign_speakers_btn.clicked.connect(self._show_speaker_assignment_dialog)
        self.assign_speakers_btn.setStyleSheet(
            "background-color: #4caf50; font-weight: bold;"
        )
        actions_layout.addWidget(self.assign_speakers_btn)

        self.apply_consistent_btn = QPushButton("🔄 Apply Consistent Names")
        self.apply_consistent_btn.clicked.connect(self._apply_consistent_assignments)
        actions_layout.addWidget(self.apply_consistent_btn)

        self.clear_assignments_btn = QPushButton("🗑️ Clear")
        self.clear_assignments_btn.clicked.connect(self._clear_current_assignments)
        actions_layout.addWidget(self.clear_assignments_btn)

        layout.addLayout(actions_layout)

        return panel

    def _create_options_section(self) -> QGroupBox:
        """Create the options section."""
        group = QGroupBox("Batch Options")
        layout = QHBoxLayout(group)

        # Consistency options
        self.maintain_consistency_cb = QCheckBox(
            "Maintain speaker consistency across recordings"
        )
        self.maintain_consistency_cb.setChecked(True)
        self.maintain_consistency_cb.setToolTip(
            "Try to assign the same names to similar speakers across different recordings"
        )
        layout.addWidget(self.maintain_consistency_cb)

        layout.addStretch()

        # Learning options
        self.learn_voices_cb = QCheckBox("Learn voice patterns for future use")
        self.learn_voices_cb.setChecked(True)
        self.learn_voices_cb.setToolTip(
            "Save speaker voice characteristics for automatic suggestions in future recordings"
        )
        layout.addWidget(self.learn_voices_cb)

        return group

    def _create_progress_section(self) -> QGroupBox:
        """Create the progress section."""
        group = QGroupBox("Progress")
        layout = QVBoxLayout(group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Progress label
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        return group

    def _create_button_box(self) -> QDialogButtonBox:
        """Create the dialog button box."""
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        # Customize button text
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Process All Recordings"
        )
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")

        # Connect signals
        button_box.accepted.connect(self._process_all_recordings)
        button_box.rejected.connect(self._cancel_batch)

        return button_box

    def _connect_signals(self):
        """Connect widget signals."""
        self.recording_list.currentRowChanged.connect(self._on_recording_selected)

    def _analyze_batch_consistency(self):
        """Analyze recordings for consistent speakers."""
        try:
            # Simple consistency analysis based on folder and speaker count
            folder_path = (
                self.recordings[0].file_path.parent if self.recordings else None
            )

            if folder_path:
                # Consistency analysis removed - LLM only approach
                consistency_analysis = {}
                consistent_speakers = consistency_analysis.get(
                    "consistent_speakers", []
                )

                # Store consistent speaker suggestions
                for i, speaker_name in enumerate(consistent_speakers):
                    speaker_id = f"SPEAKER_{i:02d}"
                    self.consistent_speakers[speaker_id] = speaker_name

                logger.info(
                    f"Found {len(consistent_speakers)} consistent speakers for batch processing"
                )

        except Exception as e:
            logger.warning(f"Error analyzing batch consistency: {e}")

    def _load_first_recording(self):
        """Load the first recording in the list."""
        if self.recordings:
            self.recording_list.setCurrentRow(0)
            self._update_current_recording_display()

    def _on_recording_selected(self, row: int):
        """Handle recording selection change."""
        if 0 <= row < len(self.recordings):
            self.current_index = row
            self._update_current_recording_display()

    def _update_current_recording_display(self):
        """Update the display for the currently selected recording."""
        if not (0 <= self.current_index < len(self.recordings)):
            return

        recording = self.recordings[self.current_index]

        # Update info label
        self.current_info_label.setText(
            f"📁 {recording.file_path.name} "
            f"({recording.get_speaker_count()} speakers, "
            f"{recording.get_total_duration()/60:.1f} min)"
        )

        # Update speaker area
        self._update_speaker_area(recording)

        # Update button states
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.recordings) - 1)
        self.apply_consistent_btn.setEnabled(len(self.consistent_speakers) > 0)

    def _update_speaker_area(self, recording: RecordingItem):
        """Update the speaker area with current recording's speakers."""
        # Create widget for speaker display
        widget = QWidget()
        layout = QVBoxLayout(widget)

        if not recording.speaker_data_list:
            layout.addWidget(QLabel("No speakers detected in this recording."))
        else:
            for speaker_data in recording.speaker_data_list:
                speaker_frame = self._create_speaker_preview_frame(
                    speaker_data, recording
                )
                layout.addWidget(speaker_frame)

        layout.addStretch()
        self.speaker_area.setWidget(widget)

    def _create_speaker_preview_frame(
        self, speaker_data: SpeakerData, recording: RecordingItem
    ) -> QFrame:
        """Create a preview frame for a speaker."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box)
        frame.setStyleSheet(
            "QFrame { border: 1px solid #ddd; border-radius: 4px; padding: 8px; margin: 4px; }"
        )

        layout = QHBoxLayout(frame)

        # Speaker info
        info_layout = QVBoxLayout()

        # Speaker ID and stats
        speaker_label = QLabel(f"🎤 {speaker_data.speaker_id}")
        speaker_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        info_layout.addWidget(speaker_label)

        stats_label = QLabel(
            f"{speaker_data.segment_count} segments, "
            f"{speaker_data.total_duration/60:.1f} min"
        )
        stats_label.setFont(QFont("Arial", 8))
        stats_label.setStyleSheet("color: #666;")
        info_layout.addWidget(stats_label)

        # Sample text
        if speaker_data.sample_texts:
            sample_text = (
                speaker_data.sample_texts[0][:100] + "..."
                if len(speaker_data.sample_texts[0]) > 100
                else speaker_data.sample_texts[0]
            )
            sample_label = QLabel(f'"{sample_text}"')
            sample_label.setFont(QFont("Arial", 8))
            sample_label.setStyleSheet("color: #888; font-style: italic;")
            sample_label.setWordWrap(True)
            info_layout.addWidget(sample_label)

        layout.addLayout(info_layout)

        # Assignment info
        assignment_layout = QVBoxLayout()

        # Current assignment
        assigned_name = recording.assignments.get(speaker_data.speaker_id, "Unassigned")
        assignment_label = QLabel(f"➡️ {assigned_name}")
        assignment_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))

        if assigned_name != "Unassigned":
            assignment_label.setStyleSheet("color: #4caf50;")
        else:
            assignment_label.setStyleSheet("color: #f44336;")

        assignment_layout.addWidget(assignment_label)

        # Suggestion
        if speaker_data.suggested_name:
            suggestion_label = QLabel(f"💡 Suggested: {speaker_data.suggested_name}")
            suggestion_label.setFont(QFont("Arial", 8))
            suggestion_label.setStyleSheet("color: #2196f3;")
            assignment_layout.addWidget(suggestion_label)

        layout.addLayout(assignment_layout)

        return frame

    def _show_speaker_assignment_dialog(self):
        """Show the speaker assignment dialog for the current recording."""
        # Critical safety check: Never show dialog during testing mode
        from ...utils.testing import is_testing_mode

        if is_testing_mode():
            from ...logger import get_logger

            logger = get_logger(__name__)
            logger.error(
                "🧪 CRITICAL: Attempted to show BatchSpeakerAssignmentDialog during testing mode - BLOCKED!"
            )
            return

        if not (0 <= self.current_index < len(self.recordings)):
            return

        recording = self.recordings[self.current_index]

        # Show speaker assignment dialog using safe wrapper function
        from .speaker_assignment_dialog import show_speaker_assignment_dialog

        assignments = show_speaker_assignment_dialog(
            recording.speaker_data_list,
            str(recording.file_path),
            None,  # metadata
            self,  # parent
        )

        if assignments:
            recording.assignments = assignments
            recording.processed = True

            # Update display
            self._update_current_recording_display()
            self._update_recording_list_item(self.current_index)

            logger.info(
                f"Updated assignments for {recording.file_path.name}: {assignments}"
            )

    def _apply_consistent_assignments(self):
        """Apply consistent speaker assignments to the current recording."""
        if not (0 <= self.current_index < len(self.recordings)):
            return

        recording = self.recordings[self.current_index]

        # Apply consistent assignments based on speaker order
        for i, speaker_data in enumerate(recording.speaker_data_list):
            speaker_id = f"SPEAKER_{i:02d}"
            if speaker_id in self.consistent_speakers:
                recording.assignments[
                    speaker_data.speaker_id
                ] = self.consistent_speakers[speaker_id]

        recording.processed = True

        # Update display
        self._update_current_recording_display()
        self._update_recording_list_item(self.current_index)

        logger.info(f"Applied consistent assignments to {recording.file_path.name}")

    def _clear_current_assignments(self):
        """Clear assignments for the current recording."""
        if not (0 <= self.current_index < len(self.recordings)):
            return

        recording = self.recordings[self.current_index]
        recording.assignments.clear()
        recording.processed = False

        # Update display
        self._update_current_recording_display()
        self._update_recording_list_item(self.current_index)

        logger.info(f"Cleared assignments for {recording.file_path.name}")

    def _update_recording_list_item(self, index: int):
        """Update a specific item in the recording list."""
        if not (0 <= index < len(self.recordings)):
            return

        recording = self.recordings[index]
        item = self.recording_list.item(index)

        # Update item text and color
        status_icon = "✅" if recording.has_assignments() else "⏳"
        confidence_text = (
            f"{recording.overall_confidence:.0%}"
            if recording.overall_confidence > 0
            else "N/A"
        )

        item_text = (
            f"{status_icon} {recording.file_path.name}\n"
            f"   {recording.get_speaker_count()} speakers, "
            f"confidence: {confidence_text}"
        )

        item.setText(item_text)

        # Update background color
        if recording.has_assignments():
            item.setBackground(Qt.GlobalColor.lightGreen)
        else:
            item.setBackground(Qt.GlobalColor.white)

    def _go_to_previous(self):
        """Go to the previous recording."""
        if self.current_index > 0:
            self.recording_list.setCurrentRow(self.current_index - 1)

    def _go_to_next(self):
        """Go to the next recording."""
        if self.current_index < len(self.recordings) - 1:
            self.recording_list.setCurrentRow(self.current_index + 1)

    def _process_all_recordings(self):
        """Process all recordings with their assignments."""
        # Collect all assignments
        all_assignments = {}
        unprocessed_count = 0

        for recording in self.recordings:
            if recording.has_assignments():
                all_assignments[str(recording.file_path)] = recording.assignments
            else:
                unprocessed_count += 1

        if unprocessed_count > 0:
            reply = QMessageBox.question(
                self,
                "Incomplete Assignments",
                f"{unprocessed_count} recordings don't have speaker assignments.\n"
                "Do you want to process only the completed recordings?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.No:
                return

        if not all_assignments:
            QMessageBox.warning(
                self,
                "No Assignments",
                "No recordings have speaker assignments to process.",
            )
            return

        # Emit completion signal
        self.batch_completed.emit(all_assignments)
        self.accept()

    def _cancel_batch(self):
        """Cancel the batch processing."""
        self.batch_cancelled.emit()
        self.reject()


def show_batch_speaker_assignment_dialog(
    recordings: list[RecordingItem], parent=None
) -> dict[str, dict[str, str]] | None:
    """
    Show batch speaker assignment dialog and return assignments.

    Args:
        recordings: List of RecordingItem objects
        parent: Parent widget

    Returns:
        Dictionary mapping file paths to speaker assignments or None if cancelled
    """
    dialog = BatchSpeakerAssignmentDialog(recordings, parent)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.completed_assignments

    return None
