"""
Speaker Assignment Dialog

Main dialog for assigning real names to diarized speakers with intelligent
suggestions, keyboard shortcuts, and intuitive columnar layout.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QPalette
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QFrame,
    QScrollArea,
    QWidget,
    QProgressBar,
    QCheckBox,
    QComboBox,
    QMessageBox,
    QDialogButtonBox,
    QGroupBox,
    QSplitter,
    QApplication
)

from ...logger import get_logger
from ...processors.speaker_processor import SpeakerData, SpeakerAssignment
from ...utils.speaker_intelligence import SpeakerNameSuggester
from ...database.speaker_models import get_speaker_db_service, SpeakerAssignmentModel

logger = get_logger(__name__)


class SpeakerCard(QFrame):
    """Individual speaker card widget for the assignment dialog."""
    
    name_changed = pyqtSignal(str, str)  # speaker_id, new_name
    switch_requested = pyqtSignal(str, str)  # speaker_id1, speaker_id2
    focus_requested = pyqtSignal(str)  # speaker_id
    
    def __init__(self, speaker_data: SpeakerData, color: str, parent=None):
        """
        Initialize speaker card.
        
        Args:
            speaker_data: Speaker information
            color: Assigned color for this speaker
            parent: Parent widget
        """
        super().__init__(parent)
        self.speaker_data = speaker_data
        self.color = color
        self.is_focused = False
        
        self._setup_ui()
        self._connect_signals()
        self._apply_styling()
    
    def _setup_ui(self):
        """Setup the speaker card UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header with speaker ID and stats
        header_layout = QHBoxLayout()
        
        # Speaker ID label
        self.speaker_id_label = QLabel(f"Speaker {self.speaker_data.speaker_id.replace('SPEAKER_', '')}")
        self.speaker_id_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.speaker_id_label)
        
        header_layout.addStretch()
        
        # Stats label
        duration_min = int(self.speaker_data.total_duration // 60)
        duration_sec = int(self.speaker_data.total_duration % 60)
        stats_text = f"{self.speaker_data.segment_count} segments, {duration_min}:{duration_sec:02d}"
        self.stats_label = QLabel(stats_text)
        self.stats_label.setFont(QFont("Arial", 9))
        self.stats_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self.stats_label)
        
        layout.addLayout(header_layout)
        
        # Name input section
        name_layout = QVBoxLayout()
        
        # Name input field
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter speaker name...")
        self.name_input.setFont(QFont("Arial", 11))
        
        # Pre-fill with suggestion if available
        if self.speaker_data.suggested_name:
            self.name_input.setText(self.speaker_data.suggested_name)
            self.name_input.selectAll()
        
        name_layout.addWidget(self.name_input)
        
        # Confidence indicator and suggestion info
        if self.speaker_data.suggested_name:
            confidence_layout = QHBoxLayout()
            
            confidence_text = f"AI Suggestion (confidence: {self.speaker_data.confidence_score:.0%})"
            self.confidence_label = QLabel(confidence_text)
            self.confidence_label.setFont(QFont("Arial", 8))
            self.confidence_label.setStyleSheet("color: #888;")
            confidence_layout.addWidget(self.confidence_label)
            
            confidence_layout.addStretch()
            
            # Confidence bar
            self.confidence_bar = QProgressBar()
            self.confidence_bar.setMaximum(100)
            self.confidence_bar.setValue(int(self.speaker_data.confidence_score * 100))
            self.confidence_bar.setMaximumWidth(60)
            self.confidence_bar.setMaximumHeight(8)
            confidence_layout.addWidget(self.confidence_bar)
            
            name_layout.addLayout(confidence_layout)
        
        layout.addLayout(name_layout)
        
        # Sample text display
        samples_group = QGroupBox("Sample Speech")
        samples_layout = QVBoxLayout(samples_group)
        
        self.samples_text = QTextEdit()
        self.samples_text.setMaximumHeight(120)
        self.samples_text.setFont(QFont("Arial", 9))
        self.samples_text.setReadOnly(True)
        
        # Add sample texts
        sample_content = ""
        for i, sample in enumerate(self.speaker_data.sample_texts[:3]):
            sample_content += f"• {sample}\n\n"
        
        if not sample_content:
            sample_content = "No substantial speech samples available."
        
        self.samples_text.setPlainText(sample_content.strip())
        samples_layout.addWidget(self.samples_text)
        
        layout.addWidget(samples_group)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        
        # Switch button (will be populated with other speakers)
        self.switch_button = QPushButton("🔄 Switch")
        self.switch_button.setToolTip("Switch assignment with another speaker (Ctrl+S)")
        self.switch_button.setMaximumWidth(80)
        buttons_layout.addWidget(self.switch_button)
        
        buttons_layout.addStretch()
        
        # Audio play button (future enhancement)
        self.play_button = QPushButton("🔊 Play")
        self.play_button.setToolTip("Play audio sample (Ctrl+P)")
        self.play_button.setMaximumWidth(80)
        self.play_button.setEnabled(False)  # Disabled for now
        buttons_layout.addWidget(self.play_button)
        
        layout.addLayout(buttons_layout)
    
    def _connect_signals(self):
        """Connect widget signals."""
        self.name_input.textChanged.connect(self._on_name_changed)
        self.name_input.returnPressed.connect(self._on_return_pressed)
        self.switch_button.clicked.connect(self._on_switch_clicked)
        self.name_input.focusInEvent = self._on_focus_in
    
    def _apply_styling(self):
        """Apply visual styling to the card."""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(2)
        
        # Apply color-coded border
        style = f"""
        SpeakerCard {{
            border: 2px solid {self.color};
            border-radius: 8px;
            background-color: {self.color}15;
            margin: 4px;
        }}
        SpeakerCard:focus {{
            border: 3px solid {self.color};
            background-color: {self.color}25;
        }}
        """
        self.setStyleSheet(style)
    
    def _on_name_changed(self, text: str):
        """Handle name input changes."""
        self.name_changed.emit(self.speaker_data.speaker_id, text)
    
    def _on_return_pressed(self):
        """Handle return key press in name input."""
        self.focus_requested.emit("next")
    
    def _on_switch_clicked(self):
        """Handle switch button click."""
        # This will be handled by the parent dialog
        pass
    
    def _on_focus_in(self, event):
        """Handle focus in event."""
        self.focus_requested.emit(self.speaker_data.speaker_id)
        # Call original focus in event
        QLineEdit.focusInEvent(self.name_input, event)
    
    def set_focus_state(self, focused: bool):
        """Set the visual focus state of the card."""
        self.is_focused = focused
        if focused:
            self.name_input.setFocus()
            self.name_input.selectAll()
    
    def get_assigned_name(self) -> str:
        """Get the currently assigned name."""
        return self.name_input.text().strip()
    
    def set_assigned_name(self, name: str):
        """Set the assigned name."""
        self.name_input.setText(name)
    
    def update_switch_button(self, other_speakers: List[str]):
        """Update switch button with menu of other speakers."""
        # For now, just enable/disable based on availability
        self.switch_button.setEnabled(len(other_speakers) > 0)


class SpeakerAssignmentDialog(QDialog):
    """Main dialog for assigning names to diarized speakers."""
    
    # Signals
    speaker_assignments_completed = pyqtSignal(dict)  # {speaker_id: name}
    assignment_cancelled = pyqtSignal()
    
    def __init__(self, speaker_data_list: List[SpeakerData], recording_path: str = "", parent=None):
        """
        Initialize the speaker assignment dialog.
        
        Args:
            speaker_data_list: List of speaker data objects
            recording_path: Path to the recording file
            parent: Parent widget
        """
        super().__init__(parent)
        self.speaker_data_list = speaker_data_list
        self.recording_path = recording_path
        self.speaker_cards: Dict[str, SpeakerCard] = {}
        self.current_focus_index = 0
        self.assignments: Dict[str, str] = {}
        
        self.name_suggester = SpeakerNameSuggester()
        self.db_service = get_speaker_db_service()
        
        self._setup_ui()
        self._setup_keyboard_shortcuts()
        self._connect_signals()
        self._load_existing_assignments()
    
    def _setup_ui(self):
        """Setup the main dialog UI."""
        self.setWindowTitle("Speaker Identification")
        self.setModal(True)
        self.setMinimumSize(900, 600)
        self.resize(1200, 700)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        
        # Header section
        header_layout = self._create_header()
        main_layout.addLayout(header_layout)
        
        # Speaker cards section (scrollable)
        cards_section = self._create_speaker_cards_section()
        main_layout.addWidget(cards_section)
        
        # Options section
        options_section = self._create_options_section()
        main_layout.addWidget(options_section)
        
        # Button box
        button_box = self._create_button_box()
        main_layout.addWidget(button_box)
    
    def _create_header(self) -> QHBoxLayout:
        """Create the header section."""
        layout = QHBoxLayout()
        
        # Title and info
        title_layout = QVBoxLayout()
        
        title_label = QLabel("Assign Names to Speakers")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        
        if self.recording_path:
            file_name = Path(self.recording_path).name
            info_label = QLabel(f"Recording: {file_name}")
            info_label.setFont(QFont("Arial", 10))
            info_label.setStyleSheet("color: #666;")
            title_layout.addWidget(info_label)
        
        speaker_count_label = QLabel(f"Found {len(self.speaker_data_list)} speakers")
        speaker_count_label.setFont(QFont("Arial", 10))
        speaker_count_label.setStyleSheet("color: #666;")
        title_layout.addWidget(speaker_count_label)
        
        layout.addLayout(title_layout)
        layout.addStretch()
        
        # Help text
        help_text = QLabel(
            "💡 Use Tab to move between speakers, Enter to confirm and move to next\n"
            "🎯 Ctrl+S to switch speakers, Ctrl+P to play audio (coming soon)"
        )
        help_text.setFont(QFont("Arial", 9))
        help_text.setStyleSheet("color: #888; background-color: #f5f5f5; padding: 8px; border-radius: 4px;")
        help_text.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(help_text)
        
        return layout
    
    def _create_speaker_cards_section(self) -> QScrollArea:
        """Create the scrollable speaker cards section."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Container widget
        container = QWidget()
        
        # Grid layout for speaker cards
        grid_layout = QGridLayout(container)
        grid_layout.setSpacing(12)
        
        # Generate colors for speakers
        colors = self._generate_speaker_colors()
        
        # Create speaker cards
        columns = min(3, len(self.speaker_data_list))  # Max 3 columns
        for i, speaker_data in enumerate(self.speaker_data_list):
            color = colors.get(speaker_data.speaker_id, "#999999")
            
            card = SpeakerCard(speaker_data, color, self)
            self.speaker_cards[speaker_data.speaker_id] = card
            
            # Position in grid
            row = i // columns
            col = i % columns
            grid_layout.addWidget(card, row, col)
        
        # Add stretch to fill remaining space
        grid_layout.setRowStretch(grid_layout.rowCount(), 1)
        grid_layout.setColumnStretch(columns, 1)
        
        scroll_area.setWidget(container)
        return scroll_area
    
    def _create_options_section(self) -> QGroupBox:
        """Create the options section."""
        group = QGroupBox("Options")
        layout = QHBoxLayout(group)
        
        # Save for future use checkbox
        self.save_for_future_cb = QCheckBox("Save speaker identities for future recordings")
        self.save_for_future_cb.setChecked(True)
        self.save_for_future_cb.setToolTip("Learn these speaker voices for automatic suggestions in future recordings")
        layout.addWidget(self.save_for_future_cb)
        
        layout.addStretch()
        
        # Apply to folder checkbox
        self.apply_to_folder_cb = QCheckBox("Apply to other recordings in this folder")
        self.apply_to_folder_cb.setToolTip("Apply these assignments to other unprocessed recordings in the same folder")
        layout.addWidget(self.apply_to_folder_cb)
        
        return group
    
    def _create_button_box(self) -> QDialogButtonBox:
        """Create the dialog button box."""
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Reset
        )
        
        # Customize button text
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Confirm Assignments")
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")
        button_box.button(QDialogButtonBox.StandardButton.Reset).setText("Reset to Suggestions")
        
        # Connect signals
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self._on_reject)
        button_box.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self._on_reset)
        
        return button_box
    
    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Tab to move to next speaker
        tab_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Tab), self)
        tab_shortcut.activated.connect(self._move_to_next_speaker)
        
        # Shift+Tab to move to previous speaker
        shift_tab_shortcut = QShortcut(QKeySequence("Shift+Tab"), self)
        shift_tab_shortcut.activated.connect(self._move_to_previous_speaker)
        
        # Ctrl+S to switch speakers
        switch_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        switch_shortcut.activated.connect(self._show_switch_dialog)
        
        # Ctrl+P to play audio (placeholder)
        play_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        play_shortcut.activated.connect(self._play_current_speaker_audio)
        
        # Enter to confirm and move to next
        enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        enter_shortcut.activated.connect(self._confirm_current_and_next)
    
    def _connect_signals(self):
        """Connect widget signals."""
        for card in self.speaker_cards.values():
            card.name_changed.connect(self._on_speaker_name_changed)
            card.focus_requested.connect(self._on_focus_requested)
    
    def _generate_speaker_colors(self) -> Dict[str, str]:
        """Generate consistent colors for speakers."""
        colors = [
            '#FF6B6B',  # Red
            '#4ECDC4',  # Teal
            '#45B7D1',  # Blue
            '#96CEB4',  # Green
            '#FFEAA7',  # Yellow
            '#DDA0DD',  # Plum
            '#98D8C8',  # Mint
            '#F7DC6F',  # Light Yellow
            '#BB8FCE',  # Light Purple
            '#85C1E9'   # Light Blue
        ]
        
        color_map = {}
        for i, speaker_data in enumerate(self.speaker_data_list):
            color_map[speaker_data.speaker_id] = colors[i % len(colors)]
        
        return color_map
    
    def _load_existing_assignments(self):
        """Load any existing speaker assignments for this recording."""
        try:
            if self.recording_path:
                existing_assignments = self.db_service.get_assignments_for_recording(self.recording_path)
                for assignment in existing_assignments:
                    if assignment.speaker_id in self.speaker_cards:
                        card = self.speaker_cards[assignment.speaker_id]
                        card.set_assigned_name(assignment.assigned_name)
                        self.assignments[assignment.speaker_id] = assignment.assigned_name
                        
                logger.info(f"Loaded {len(existing_assignments)} existing assignments")
        except Exception as e:
            logger.warning(f"Could not load existing assignments: {e}")
    
    def _move_to_next_speaker(self):
        """Move focus to the next speaker."""
        if not self.speaker_cards:
            return
        
        speaker_ids = list(self.speaker_cards.keys())
        self.current_focus_index = (self.current_focus_index + 1) % len(speaker_ids)
        
        # Update focus
        self._update_focus_state()
    
    def _move_to_previous_speaker(self):
        """Move focus to the previous speaker."""
        if not self.speaker_cards:
            return
        
        speaker_ids = list(self.speaker_cards.keys())
        self.current_focus_index = (self.current_focus_index - 1) % len(speaker_ids)
        
        # Update focus
        self._update_focus_state()
    
    def _update_focus_state(self):
        """Update the focus state of all cards."""
        speaker_ids = list(self.speaker_cards.keys())
        if not speaker_ids:
            return
        
        current_speaker_id = speaker_ids[self.current_focus_index]
        
        for speaker_id, card in self.speaker_cards.items():
            is_focused = (speaker_id == current_speaker_id)
            card.set_focus_state(is_focused)
    
    def _confirm_current_and_next(self):
        """Confirm current assignment and move to next."""
        # Validate current assignment
        speaker_ids = list(self.speaker_cards.keys())
        if speaker_ids and self.current_focus_index < len(speaker_ids):
            current_speaker_id = speaker_ids[self.current_focus_index]
            current_card = self.speaker_cards[current_speaker_id]
            
            name = current_card.get_assigned_name()
            if name:
                self.assignments[current_speaker_id] = name
                logger.debug(f"Confirmed assignment: {current_speaker_id} -> {name}")
        
        # Move to next speaker
        self._move_to_next_speaker()
    
    def _show_switch_dialog(self):
        """Show dialog to switch speaker assignments."""
        # Simple implementation: switch with next speaker
        speaker_ids = list(self.speaker_cards.keys())
        if len(speaker_ids) < 2:
            return
        
        current_id = speaker_ids[self.current_focus_index]
        next_index = (self.current_focus_index + 1) % len(speaker_ids)
        next_id = speaker_ids[next_index]
        
        # Switch the names
        current_card = self.speaker_cards[current_id]
        next_card = self.speaker_cards[next_id]
        
        current_name = current_card.get_assigned_name()
        next_name = next_card.get_assigned_name()
        
        current_card.set_assigned_name(next_name)
        next_card.set_assigned_name(current_name)
        
        logger.debug(f"Switched assignments between {current_id} and {next_id}")
    
    def _play_current_speaker_audio(self):
        """Play audio sample for current speaker (placeholder)."""
        QMessageBox.information(
            self,
            "Audio Playback",
            "Audio playback feature coming soon!\n\nThis will play a sample of the selected speaker's voice."
        )
    
    def _on_speaker_name_changed(self, speaker_id: str, name: str):
        """Handle speaker name changes."""
        self.assignments[speaker_id] = name
        logger.debug(f"Name changed: {speaker_id} -> {name}")
    
    def _on_focus_requested(self, speaker_id: str):
        """Handle focus requests from speaker cards."""
        if speaker_id == "next":
            self._move_to_next_speaker()
        else:
            # Find the speaker index and update focus
            speaker_ids = list(self.speaker_cards.keys())
            if speaker_id in speaker_ids:
                self.current_focus_index = speaker_ids.index(speaker_id)
                self._update_focus_state()
    
    def _on_accept(self):
        """Handle dialog acceptance."""
        # Collect all assignments
        final_assignments = {}
        missing_assignments = []
        
        for speaker_id, card in self.speaker_cards.items():
            name = card.get_assigned_name()
            if name:
                final_assignments[speaker_id] = name
            else:
                missing_assignments.append(speaker_id)
        
        # Check for missing assignments
        if missing_assignments:
            reply = QMessageBox.question(
                self,
                "Incomplete Assignments",
                f"The following speakers don't have names assigned:\n"
                f"{', '.join(missing_assignments)}\n\n"
                f"Do you want to continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
        
        # Save assignments to database if requested
        if self.save_for_future_cb.isChecked():
            self._save_assignments_to_database(final_assignments)
        
        # Emit completion signal
        self.speaker_assignments_completed.emit(final_assignments)
        self.accept()
    
    def _on_reject(self):
        """Handle dialog rejection."""
        self.assignment_cancelled.emit()
        self.reject()
    
    def _on_reset(self):
        """Reset all assignments to AI suggestions."""
        for speaker_id, card in self.speaker_cards.items():
            # Find original speaker data
            speaker_data = next(
                (s for s in self.speaker_data_list if s.speaker_id == speaker_id),
                None
            )
            
            if speaker_data and speaker_data.suggested_name:
                card.set_assigned_name(speaker_data.suggested_name)
            else:
                card.set_assigned_name("")
        
        logger.info("Reset all assignments to AI suggestions")
    
    def _save_assignments_to_database(self, assignments: Dict[str, str]):
        """Save speaker assignments to database for future learning."""
        try:
            for speaker_id, name in assignments.items():
                assignment_data = SpeakerAssignmentModel(
                    recording_path=self.recording_path,
                    speaker_id=speaker_id,
                    assigned_name=name,
                    confidence=1.0,  # User-confirmed
                    user_confirmed=True
                )
                
                self.db_service.create_speaker_assignment(assignment_data)
                
                # Learn voice patterns (placeholder for future audio analysis)
                self.name_suggester.learn_speaker_voice_patterns(
                    speaker_id, {}, name
                )
            
            logger.info(f"Saved {len(assignments)} speaker assignments to database")
            
        except Exception as e:
            logger.error(f"Error saving assignments to database: {e}")
    
    def get_assignments(self) -> Dict[str, str]:
        """Get the current speaker assignments."""
        assignments = {}
        for speaker_id, card in self.speaker_cards.items():
            name = card.get_assigned_name()
            if name:
                assignments[speaker_id] = name
        return assignments
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        # Let the shortcuts handle most key events
        super().keyPressEvent(event)
    
    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)
        
        # Set initial focus
        if self.speaker_cards:
            QTimer.singleShot(100, self._update_focus_state)


def show_speaker_assignment_dialog(
    speaker_data_list: List[SpeakerData],
    recording_path: str = "",
    parent=None
) -> Optional[Dict[str, str]]:
    """
    Show speaker assignment dialog and return assignments.
    
    Args:
        speaker_data_list: List of speaker data objects
        recording_path: Path to the recording file
        parent: Parent widget
        
    Returns:
        Dictionary of speaker assignments or None if cancelled
    """
    dialog = SpeakerAssignmentDialog(speaker_data_list, recording_path, parent)
    
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_assignments()
    
    return None
