"""
Speaker Assignment Dialog

Main dialog for assigning real names to diarized speakers with intelligent
suggestions, keyboard shortcuts, and intuitive columnar layout.
"""

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...database.speaker_models import SpeakerAssignmentModel, get_speaker_db_service
from ...logger import get_logger
from ...processors.speaker_processor import SpeakerData
from ...utils.llm_speaker_validator import LLMSpeakerValidator

# Pattern-based suggestions removed - LLM only approach

logger = get_logger(__name__)


class SpeakerCard(QFrame):
    """Individual speaker card widget for the assignment dialog."""

    name_changed = pyqtSignal(str, str)  # speaker_id, new_name
    switch_requested = pyqtSignal(str, str)  # speaker_id1, speaker_id2
    focus_requested = pyqtSignal(str)  # speaker_id
    play_requested = pyqtSignal(str)  # speaker_id

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
        self.speaker_id_label = QLabel(
            f"Speaker {self.speaker_data.speaker_id.replace('SPEAKER_', '')}"
        )
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

        # Name input field with priority-based styling
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter speaker name...")
        self.name_input.setFont(QFont("Arial", 11))

        # Pre-fill with suggestion and apply priority-based styling
        if self.speaker_data.suggested_name:
            self.name_input.setText(self.speaker_data.suggested_name)

            # Visual indicators based on assignment source
            source = getattr(self.speaker_data, "assignment_source", "ai_suggestion")
            if source == "manual_override":
                # Green border for manual overrides
                self.name_input.setStyleSheet(
                    """
                    QLineEdit {
                        border: 2px solid #4caf50;
                        background-color: #f0fff0;
                        font-weight: bold;
                    }
                """
                )
                self.name_input.setToolTip(
                    "🎯 Manual assignment (saved from previous session)"
                )
            elif source == "ai_suggestion":
                # Blue border for AI suggestions
                self.name_input.setStyleSheet(
                    """
                    QLineEdit {
                        border: 2px solid #2196f3;
                        background-color: #f0f8ff;
                    }
                """
                )
                self.name_input.setToolTip(
                    "🤖 AI suggestion (may include learned mappings)"
                )
                self.name_input.selectAll()
            else:
                # Default styling for no suggestion
                self.name_input.setStyleSheet("border: 1px solid #ccc;")

        name_layout.addWidget(self.name_input)

        # Add priority indicator label
        if hasattr(self.speaker_data, "assignment_source"):
            source = self.speaker_data.assignment_source
            if source == "manual_override":
                priority_label = QLabel("🎯 Manual Override")
                priority_label.setStyleSheet(
                    "color: #4caf50; font-weight: bold; font-size: 9px;"
                )
            elif source == "ai_suggestion":
                priority_label = QLabel("🤖 AI Suggestion")
                priority_label.setStyleSheet("color: #2196f3; font-size: 9px;")
            else:
                priority_label = QLabel("❓ No Suggestion")
                priority_label.setStyleSheet("color: #666; font-size: 9px;")

            name_layout.addWidget(priority_label)

        # Confidence indicator and suggestion info
        if self.speaker_data.suggested_name:
            confidence_layout = QHBoxLayout()

            confidence_text = (
                f"AI Suggestion (confidence: {self.speaker_data.confidence_score:.0%})"
            )
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

        # Sample text display - First 5 speaking segments for identification
        samples_group = QGroupBox("First 5 Speaking Segments")
        samples_layout = QVBoxLayout(samples_group)

        self.samples_text = QTextEdit()
        self.samples_text.setMaximumHeight(
            250
        )  # Increased height to fit 5 segments comfortably
        self.samples_text.setFont(
            QFont("Arial", 10)
        )  # Slightly larger font for readability
        self.samples_text.setReadOnly(True)

        # Add first 5 speaking segments with timestamps for better identification
        sample_content = ""
        segments_to_show = getattr(
            self.speaker_data, "first_five_segments", self.speaker_data.sample_texts[:5]
        )

        for i, segment in enumerate(segments_to_show[:5]):
            if isinstance(segment, dict) and "text" in segment:
                # If segment has timestamp info
                timestamp = segment.get("start", 0)
                mins, secs = divmod(int(timestamp), 60)
                text = segment["text"].strip()
                sample_content += f"[{mins:02d}:{secs:02d}] {text}\n\n"
            else:
                # Fallback to text-only
                sample_content += f"{i+1}. {str(segment).strip()}\n\n"

        if not sample_content:
            sample_content = "No speech segments available for this speaker."

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

        # Audio play button
        self.play_button = QPushButton("🔊 Play")
        self.play_button.setToolTip("Play audio sample (Ctrl+P)")
        self.play_button.setMaximumWidth(80)
        self.play_button.setEnabled(True)  # Enable the play button
        buttons_layout.addWidget(self.play_button)

        layout.addLayout(buttons_layout)

    def _connect_signals(self):
        """Connect widget signals."""
        self.name_input.textChanged.connect(self._on_name_changed)
        self.name_input.returnPressed.connect(self._on_return_pressed)
        self.switch_button.clicked.connect(self._on_switch_clicked)
        self.play_button.clicked.connect(self._on_play_clicked)
        self.name_input.focusInEvent = self._on_focus_in

    def _apply_styling(self):
        """Apply visual styling to the card."""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(2)

        # Apply color-coded border
        style = """
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

    def _on_play_clicked(self):
        """Handle play button click."""
        # Emit signal for parent dialog to handle audio playback
        self.play_requested.emit(self.speaker_data.speaker_id)

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

    def update_switch_button(self, other_speakers: list[str]):
        """Update switch button with menu of other speakers."""
        # For now, just enable/disable based on availability
        self.switch_button.setEnabled(len(other_speakers) > 0)


class SpeakerAssignmentDialog(QDialog):
    """Main dialog for assigning names to diarized speakers."""

    # Signals
    speaker_assignments_completed = pyqtSignal(dict)  # {speaker_id: name}
    assignment_cancelled = pyqtSignal()

    def __init__(
        self,
        speaker_data_list: list[SpeakerData],
        recording_path: str = "",
        metadata: dict | None = None,
        parent=None,
    ):
        """
        Initialize the speaker assignment dialog with priority-based assignments.

        Priority order:
        1. Existing manual assignments (highest)
        2. Channel-to-host mappings
        3. Fresh AI suggestions (lowest)
        """
        # CRITICAL TESTING SAFETY: Use unified testing mode detection
        from ...logger import get_logger
        from ...utils.testing import get_testing_mode_info, is_testing_mode

        logger = get_logger(__name__)

        testing_mode = is_testing_mode()
        testing_info = get_testing_mode_info()

        logger.info(
            f"🧪 TESTING DEBUG: Testing mode = {testing_mode}, details = {testing_info}"
        )

        if testing_mode:
            logger.error(
                "🧪 CRITICAL: Attempted to create SpeakerAssignmentDialog during testing mode - BLOCKED!"
            )
            # Raise exception to prevent dialog creation entirely
            raise RuntimeError(
                "SpeakerAssignmentDialog cannot be created during testing mode"
            )

        super().__init__(parent)
        self.speaker_data_list = speaker_data_list
        self.recording_path = recording_path
        self.metadata = metadata or {}
        self.speaker_cards: dict[str, SpeakerCard] = {}
        self.current_focus_index = 0
        self.assignments: dict[str, str] = {}

        self.db_service = get_speaker_db_service()
        self.llm_validator = LLMSpeakerValidator()

        # LLM validation state
        self.llm_validation_result = None
        self.pending_validation = False

        # CRITICAL: Apply priority-based assignment resolution BEFORE UI creation
        self._resolve_assignment_priorities()

        self._setup_ui()
        self._setup_keyboard_shortcuts()
        self._connect_signals()

        # No longer needed - assignments already resolved in _resolve_assignment_priorities()
        # self._load_existing_assignments()

        # Automatically trigger LLM validation if metadata is available
        if self.metadata:
            self._trigger_llm_validation()

    def _get_display_name(self) -> str:
        """Get display name for the recording, preferring sanitized metadata title."""
        # Check if we have title in metadata (for YouTube videos)
        if self.metadata and "title" in self.metadata:
            title = self.metadata["title"]
            if title and title.strip():
                # Sanitize the title for display (similar to filename sanitization)
                import re

                sanitized = re.sub(r'[<>:"/\\|?*]', "_", title)
                sanitized = re.sub(r"_+", "_", sanitized).strip("_")
                return sanitized[:80] + "..." if len(sanitized) > 80 else sanitized

        # Fallback to filename
        return Path(self.recording_path).name

    def _setup_ui(self):
        """Setup the main dialog UI."""
        self.setWindowTitle("Speaker Identification")
        self.setModal(True)
        self.setMinimumSize(900, 600)

        # Inherit the standard dark theme from parent application - no custom styling

        # Set full height but keep current width
        from PyQt6.QtWidgets import QApplication

        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(1200, screen.height() - 50)  # Full height minus small margin

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)

        # Header section
        header_layout = self._create_header()
        main_layout.addLayout(header_layout)

        # Speaker cards section (scrollable)
        cards_section = self._create_speaker_cards_section()
        main_layout.addWidget(cards_section)

        # LLM Validation section
        validation_section = self._create_llm_validation_section()
        main_layout.addWidget(validation_section)

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
            # Use sanitized title from metadata if available, otherwise use filename
            display_name = self._get_display_name()
            info_label = QLabel(f"Recording: {display_name}")
            info_label.setFont(QFont("Arial", 10))
            info_label.setStyleSheet("color: #666;")
            title_layout.addWidget(info_label)

        speaker_count_label = QLabel(f"Found {len(self.speaker_data_list)} speakers")
        speaker_count_label.setFont(QFont("Arial", 10))
        speaker_count_label.setStyleSheet("color: #666;")
        title_layout.addWidget(speaker_count_label)

        layout.addLayout(title_layout)
        layout.addStretch()

        # Help text - Enhanced for fast batch processing with LLM validation
        help_text = QLabel(
            "⚡ FAST REVIEW SHORTCUTS:\n"
            "• Tab/Shift+Tab: Navigate speakers\n"
            "• Enter: Confirm current and move to next\n"
            "• Ctrl+Enter: Accept all and finish\n"
            "• Ctrl+S: Switch current with next\n"
            "• Ctrl+R: Auto-assign from metadata\n"
            "• Ctrl+L: Trigger LLM validation\n"
            "• Ctrl+1,2,3...: Quick assign to Speaker 1,2,3..."
        )
        help_text.setFont(QFont("Arial", 8))
        help_text.setStyleSheet(
            "color: #666; background-color: #f0f8ff; padding: 8px; border-radius: 4px; border: 1px solid #d0e8ff;"
        )
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

    def _create_llm_validation_section(self) -> QGroupBox:
        """Create the LLM validation status section."""
        group = QGroupBox("🤖 AI Validation")
        layout = QVBoxLayout(group)

        # Status display
        self.validation_status_label = QLabel("⏳ Preparing LLM validation...")
        self.validation_status_label.setFont(QFont("Arial", 10))
        self.validation_status_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(self.validation_status_label)

        # Detailed validation info (initially hidden)
        self.validation_details = QTextEdit()
        self.validation_details.setMaximumHeight(80)
        self.validation_details.setFont(QFont("Arial", 9))
        self.validation_details.setReadOnly(True)
        self.validation_details.setVisible(False)
        layout.addWidget(self.validation_details)

        # Validation actions
        actions_layout = QHBoxLayout()

        self.apply_llm_suggestions_btn = QPushButton("✨ Apply LLM Suggestions")
        self.apply_llm_suggestions_btn.setEnabled(False)
        self.apply_llm_suggestions_btn.clicked.connect(self._apply_llm_suggestions)
        actions_layout.addWidget(self.apply_llm_suggestions_btn)

        self.retry_validation_btn = QPushButton("🔄 Retry Validation")
        self.retry_validation_btn.clicked.connect(self._trigger_llm_validation)
        actions_layout.addWidget(self.retry_validation_btn)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        return group

    def _create_options_section(self) -> QGroupBox:
        """Create the options section."""
        group = QGroupBox("Options")
        layout = QHBoxLayout(group)

        # Save for future use checkbox
        self.save_for_future_cb = QCheckBox(
            "Save speaker identities for future recordings"
        )
        self.save_for_future_cb.setChecked(True)
        self.save_for_future_cb.setToolTip(
            "Learn these speaker voices for automatic suggestions in future recordings"
        )
        layout.addWidget(self.save_for_future_cb)

        layout.addStretch()

        # Apply to folder checkbox
        self.apply_to_folder_cb = QCheckBox("Apply to other recordings in this folder")
        self.apply_to_folder_cb.setToolTip(
            "Apply these assignments to other unprocessed recordings in the same folder"
        )
        layout.addWidget(self.apply_to_folder_cb)

        return group

    def _create_button_box(self) -> QDialogButtonBox:
        """Create the dialog button box."""
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Reset
        )

        # Customize button text
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Confirm Assignments"
        )
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")
        button_box.button(QDialogButtonBox.StandardButton.Reset).setText(
            "Reset to Suggestions"
        )

        # Connect signals
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self._on_reject)
        button_box.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(
            self._on_reset
        )

        return button_box

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for efficient navigation and fast batch processing."""
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

        # NEW: Ctrl+Enter to accept all and finish (fast batch processing)
        ctrl_enter_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        ctrl_enter_shortcut.activated.connect(self._accept_all_and_finish)

        # NEW: Auto-assign from metadata
        auto_assign_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        auto_assign_shortcut.activated.connect(self._auto_assign_from_metadata)

        # NEW: LLM validation trigger
        llm_validation_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        llm_validation_shortcut.activated.connect(self._trigger_llm_validation)

        # NEW: Quick number assignments (Ctrl+1, Ctrl+2, etc.)
        for i in range(1, 10):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            shortcut.activated.connect(
                lambda checked, num=i: self._quick_assign_speaker(num)
            )

    def _connect_signals(self):
        """Connect widget signals."""
        for card in self.speaker_cards.values():
            card.name_changed.connect(self._on_speaker_name_changed)
            card.focus_requested.connect(self._on_focus_requested)
            card.play_requested.connect(self._on_play_requested)

    def _generate_speaker_colors(self) -> dict[str, str]:
        """Generate consistent colors for speakers."""
        colors = [
            "#FF6B6B",  # Red
            "#4ECDC4",  # Teal
            "#45B7D1",  # Blue
            "#96CEB4",  # Green
            "#FFEAA7",  # Yellow
            "#DDA0DD",  # Plum
            "#98D8C8",  # Mint
            "#F7DC6F",  # Light Yellow
            "#BB8FCE",  # Light Purple
            "#85C1E9",  # Light Blue
        ]

        color_map = {}
        for i, speaker_data in enumerate(self.speaker_data_list):
            color_map[speaker_data.speaker_id] = colors[i % len(colors)]

        return color_map

    def _resolve_assignment_priorities(self):
        """
        Resolve assignment conflicts by applying strict priority order.
        This ensures manual assignments always override AI suggestions.
        """
        try:
            logger.info("🎯 Resolving speaker assignment priorities...")

            # Get existing manual assignments (highest priority)
            existing_assignments = {}
            if self.recording_path:
                db_assignments = self.db_service.get_assignments_for_recording(
                    self.recording_path
                )
                for assignment in db_assignments:
                    existing_assignments[
                        assignment.speaker_id
                    ] = assignment.assigned_name
                    logger.info(
                        f"Found existing assignment: {assignment.speaker_id} → '{assignment.assigned_name}'"
                    )

            # Apply priority resolution to each speaker
            priority_stats = {
                "manual_override": 0,
                "ai_suggestion": 0,
                "no_suggestion": 0,
            }

            for speaker_data in self.speaker_data_list:
                speaker_id = speaker_data.speaker_id

                # Priority 1: Existing manual assignment (ALWAYS wins)
                if speaker_id in existing_assignments:
                    final_name = existing_assignments[speaker_id]
                    original_suggestion = speaker_data.suggested_name
                    speaker_data.suggested_name = final_name
                    speaker_data.assignment_source = "manual_override"
                    priority_stats["manual_override"] += 1

                    if original_suggestion != final_name:
                        logger.info(
                            f"🎯 OVERRIDE: {speaker_id} AI:'{original_suggestion}' → Manual:'{final_name}'"
                        )
                    else:
                        logger.info(
                            f"🎯 CONFIRMED: {speaker_id} → '{final_name}' (manual matches AI)"
                        )

                # Priority 2: Keep AI suggestion (may include channel mappings)
                elif speaker_data.suggested_name:
                    final_name = speaker_data.suggested_name
                    speaker_data.assignment_source = "ai_suggestion"
                    priority_stats["ai_suggestion"] += 1
                    logger.info(f"🤖 AI suggestion: {speaker_id} → '{final_name}'")

                # Priority 3: No suggestion available
                else:
                    speaker_data.suggested_name = ""
                    speaker_data.assignment_source = "no_suggestion"
                    priority_stats["no_suggestion"] += 1
                    logger.info(f"❓ No suggestion: {speaker_id}")

            logger.info(
                f"✅ Priority resolution complete: {priority_stats['manual_override']} manual, {priority_stats['ai_suggestion']} AI, {priority_stats['no_suggestion']} none"
            )

        except Exception as e:
            logger.error(f"❌ Error resolving assignment priorities: {e}")
            # Continue with original suggestions on error

    def _load_existing_assignments(self):
        """
        DEPRECATED: This method is now handled by _resolve_assignment_priorities()
        Keeping for backward compatibility in case it's called elsewhere.
        """
        logger.warning(
            "⚠️ _load_existing_assignments() called but priority resolution should handle this"
        )
        # Don't actually do anything - priorities already resolved

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
            is_focused = speaker_id == current_speaker_id
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
        """Play audio sample for current speaker."""
        speaker_ids = list(self.speaker_cards.keys())
        if self.current_focus_index < len(speaker_ids):
            current_speaker_id = speaker_ids[self.current_focus_index]
            self._play_speaker_audio(current_speaker_id)

    def _on_play_requested(self, speaker_id: str):
        """Handle play button click from speaker card."""
        self._play_speaker_audio(speaker_id)

    def _play_speaker_audio(self, speaker_id: str):
        """Play audio sample for a specific speaker."""
        try:
            speaker_data = next(
                (
                    data
                    for data in self.speaker_data_list
                    if data.speaker_id == speaker_id
                ),
                None,
            )

            if not speaker_data:
                QMessageBox.warning(
                    self, "Audio Playback", f"Speaker {speaker_id} not found."
                )
                return

            # Get first speaking segment with timestamp
            first_segment = None
            segments_to_check = getattr(
                speaker_data, "first_five_segments", speaker_data.sample_texts[:5]
            )

            for segment in segments_to_check:
                if (
                    isinstance(segment, dict)
                    and "start" in segment
                    and "text" in segment
                ):
                    first_segment = segment
                    break

            if not first_segment:
                QMessageBox.information(
                    self,
                    "Audio Playback",
                    f"No timestamped segments available for {speaker_id}.\n\nAudio playback requires segments with timing information.",
                )
                return

            # Extract audio segment from the original recording
            if not self.recording_path or not Path(self.recording_path).exists():
                QMessageBox.warning(
                    self,
                    "Audio Playback",
                    "Original recording file not found.\n\nAudio playback requires access to the source file.",
                )
                return

            self._extract_and_play_audio_segment(first_segment, speaker_id)

        except Exception as e:
            logger.error(f"Error playing speaker audio: {e}")
            QMessageBox.critical(
                self, "Audio Playback Error", f"Failed to play audio sample:\n{str(e)}"
            )

    def _extract_and_play_audio_segment(self, segment: dict, speaker_id: str):
        """Extract and play a specific audio segment."""
        import platform
        import subprocess
        import tempfile

        from PyQt6.QtCore import QThread

        # Calculate segment timing (play 3-5 seconds max)
        start_time = segment.get("start", 0)
        duration = min(segment.get("duration", 3.0), 5.0)  # Max 5 seconds
        if duration < 1.0:
            duration = 3.0  # Default to 3 seconds if duration is too short

        # Create worker thread for audio extraction and playback
        class AudioPlaybackWorker(QThread):
            def __init__(self, recording_path, start_time, duration, speaker_id):
                super().__init__()
                self.recording_path = recording_path
                self.start_time = start_time
                self.duration = duration
                self.speaker_id = speaker_id

            def run(self):
                try:
                    with tempfile.NamedTemporaryFile(
                        suffix=".wav", delete=False
                    ) as temp_file:
                        temp_path = temp_file.name

                    # Extract audio segment using FFmpeg
                    ffmpeg_cmd = [
                        "ffmpeg",
                        "-y",
                        "-v",
                        "quiet",
                        "-i",
                        str(self.recording_path),
                        "-ss",
                        str(self.start_time),
                        "-t",
                        str(self.duration),
                        "-acodec",
                        "pcm_s16le",
                        "-ar",
                        "44100",
                        "-ac",
                        "1",  # Mono
                        temp_path,
                    ]

                    extract_result = subprocess.run(
                        ffmpeg_cmd, capture_output=True, text=True, timeout=30
                    )

                    if extract_result.returncode != 0:
                        logger.error(
                            f"FFmpeg extraction failed: {extract_result.stderr}"
                        )
                        return

                    # Play audio using system command
                    if platform.system() == "Darwin":  # macOS
                        play_cmd = ["afplay", temp_path]
                    elif platform.system() == "Linux":
                        # Try different players
                        if (
                            subprocess.run(
                                ["which", "paplay"], capture_output=True
                            ).returncode
                            == 0
                        ):
                            play_cmd = ["paplay", temp_path]
                        elif (
                            subprocess.run(
                                ["which", "aplay"], capture_output=True
                            ).returncode
                            == 0
                        ):
                            play_cmd = ["aplay", temp_path]
                        else:
                            logger.error("No audio player found on Linux")
                            return
                    elif platform.system() == "Windows":
                        # Use PowerShell for Windows
                        play_cmd = [
                            "powershell",
                            "-c",
                            f"(New-Object Media.SoundPlayer '{temp_path}').PlaySync()",
                        ]
                    else:
                        logger.error(f"Unsupported platform: {platform.system()}")
                        return

                    # Play the audio
                    subprocess.run(play_cmd, timeout=10)

                    # Clean up temporary file
                    Path(temp_path).unlink(missing_ok=True)

                except Exception as e:
                    logger.error(f"Audio playback error: {e}")

        # Start the worker thread
        worker = AudioPlaybackWorker(
            self.recording_path, start_time, duration, speaker_id
        )
        worker.start()

        # Show feedback to user
        from PyQt6.QtWidgets import QMessageBox

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Playing Audio")
        msg_box.setText(f"Playing audio sample for {speaker_id}...")
        msg_box.setInformativeText(
            f"Duration: {duration:.1f} seconds\nTimestamp: {start_time:.1f}s"
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)

        # Auto-close the dialog after a short delay
        from PyQt6.QtCore import QTimer

        timer = QTimer()
        timer.singleShot(
            int(duration * 1000) + 500, msg_box.accept
        )  # Close 500ms after audio ends

        msg_box.exec()

    def _accept_all_and_finish(self):
        """Accept all current assignments and finish (fast batch processing)."""
        try:
            # Collect all current assignments
            for speaker_id, card in self.speaker_cards.items():
                name = card.get_assigned_name()
                if name:
                    self.assignments[speaker_id] = name

            logger.info(
                f"Fast batch completion: {len(self.assignments)} speakers assigned"
            )
            self.accept()

        except Exception as e:
            logger.error(f"Error in accept all and finish: {e}")
            QMessageBox.warning(self, "Error", f"Failed to complete assignments: {e}")

    def _auto_assign_from_metadata(self):
        """Auto-assignment removed - LLM suggestions are already shown in the dialog."""
        try:
            # LLM suggestions are already displayed when dialog opens
            # This button is no longer needed since we're LLM-only
            QMessageBox.information(
                self,
                "LLM-Only Approach",
                "Speaker suggestions are provided by LLM when the dialog opens.\n\n"
                "The suggested names shown are based on LLM analysis of metadata and transcript.\n"
                "Please review and adjust the names as needed, then press Ctrl+Enter to finish.",
            )

            logger.info(
                "Auto-assign from metadata clicked - informed user about LLM-only approach"
            )

        except Exception as e:
            logger.error(f"Error in auto-assign message: {e}")

    def _quick_assign_speaker(self, target_speaker_num: int):
        """Quick assign current speaker to target speaker number (Ctrl+1,2,3...)."""
        try:
            current_speaker_ids = list(self.speaker_cards.keys())
            if self.current_focus_index >= len(current_speaker_ids):
                return

            current_speaker_id = current_speaker_ids[self.current_focus_index]
            current_card = self.speaker_cards[current_speaker_id]

            # Set name to "Speaker X"
            speaker_name = f"Speaker {target_speaker_num}"
            current_card.set_assigned_name(speaker_name)
            self.assignments[current_speaker_id] = speaker_name

            logger.debug(f"Quick assigned {current_speaker_id} to {speaker_name}")

            # Move to next speaker for continued fast processing
            self._move_to_next_speaker()

        except Exception as e:
            logger.error(f"Error in quick assign speaker: {e}")

    def _trigger_llm_validation(self):
        """Trigger LLM validation of current speaker assignments."""
        try:
            self.pending_validation = True
            self.validation_status_label.setText("⏳ Running LLM validation...")
            self.apply_llm_suggestions_btn.setEnabled(False)
            self.validation_details.setVisible(False)

            # Collect current assignments and segments
            current_assignments = {}
            speaker_segments = {}

            for speaker_id, card in self.speaker_cards.items():
                assigned_name = card.get_assigned_name()
                if assigned_name:
                    current_assignments[speaker_id] = assigned_name

                # Get speaker data
                speaker_data = next(
                    (
                        data
                        for data in self.speaker_data_list
                        if data.speaker_id == speaker_id
                    ),
                    None,
                )
                if speaker_data:
                    speaker_segments[speaker_id] = [
                        {"text": seg.text, "start": seg.start, "end": seg.end}
                        for seg in speaker_data.segments
                    ]

            if not current_assignments:
                self.validation_status_label.setText("❌ No assignments to validate")
                self.pending_validation = False
                return

            # Run LLM validation in a separate thread (simplified for now)
            self._run_llm_validation(current_assignments, speaker_segments)

        except Exception as e:
            logger.error(f"Error triggering LLM validation: {e}")
            self.validation_status_label.setText(f"❌ Validation error: {str(e)}")
            self.pending_validation = False

    def _run_llm_validation(
        self, assignments: dict[str, str], segments: dict[str, list[dict]]
    ):
        """Run LLM validation (blocking for now, could be threaded)."""
        try:
            # Perform LLM validation
            self.llm_validation_result = (
                self.llm_validator.validate_speaker_assignments(
                    assignments, segments, self.metadata
                )
            )

            # Update UI with results
            self._display_llm_validation_results()

        except Exception as e:
            logger.error(f"Error in LLM validation: {e}")
            self.validation_status_label.setText(f"❌ LLM validation failed: {str(e)}")
            self.pending_validation = False

    def _display_llm_validation_results(self):
        """Display LLM validation results in the UI."""
        try:
            if not self.llm_validation_result:
                return

            # Update status
            summary = self.llm_validator.create_validation_summary_for_user(
                self.llm_validation_result
            )
            self.validation_status_label.setText(summary)

            # Show detailed validation info
            validations = self.llm_validation_result.get("validations", {})
            details_text = ""

            for speaker_id, validation in validations.items():
                recommendation = validation.get("recommendation", "UNCERTAIN")
                reasoning = validation.get("reasoning", "No reasoning provided")
                confidence = validation.get("llm_confidence", 0.5)

                emoji = (
                    "✅"
                    if recommendation == "ACCEPT"
                    else "❌"
                    if recommendation == "REJECT"
                    else "❓"
                )
                details_text += f"{emoji} {validation.get('original_assignment', 'Unknown')} ({confidence:.0%}): {reasoning}\n"

            if details_text:
                self.validation_details.setPlainText(details_text.strip())
                self.validation_details.setVisible(True)

            # Enable apply suggestions if there are recommendations
            recommendations = self.llm_validation_result.get("recommendations", {})
            has_changes = any(
                recommendations.get(sid) != assignments.get(sid)
                for sid in recommendations.keys()
                for assignments in [self._get_current_assignments()]
            )

            self.apply_llm_suggestions_btn.setEnabled(has_changes)
            self.pending_validation = False

            logger.info("LLM validation results displayed successfully")

        except Exception as e:
            logger.error(f"Error displaying LLM validation results: {e}")
            self.validation_status_label.setText(
                "❌ Error displaying validation results"
            )
            self.pending_validation = False

    def _apply_llm_suggestions(self):
        """Apply LLM validation suggestions to speaker assignments."""
        try:
            if not self.llm_validation_result:
                return

            recommendations = self.llm_validation_result.get("recommendations", {})
            applied_count = 0

            for speaker_id, recommended_name in recommendations.items():
                if speaker_id in self.speaker_cards:
                    current_name = self.speaker_cards[speaker_id].get_assigned_name()
                    if current_name != recommended_name:
                        self.speaker_cards[speaker_id].set_assigned_name(
                            recommended_name
                        )
                        self.assignments[speaker_id] = recommended_name
                        applied_count += 1

            if applied_count > 0:
                self.validation_status_label.setText(
                    f"✅ Applied {applied_count} LLM suggestions"
                )
                self.apply_llm_suggestions_btn.setEnabled(False)
                logger.info(f"Applied {applied_count} LLM validation suggestions")
            else:
                self.validation_status_label.setText("ℹ️ No changes needed")

        except Exception as e:
            logger.error(f"Error applying LLM suggestions: {e}")
            self.validation_status_label.setText(
                f"❌ Error applying suggestions: {str(e)}"
            )

    def _get_current_assignments(self) -> dict[str, str]:
        """Get current speaker assignments from UI."""
        return {
            speaker_id: card.get_assigned_name()
            for speaker_id, card in self.speaker_cards.items()
            if card.get_assigned_name()
        }

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
        """Handle dialog acceptance with detailed change tracking."""
        logger.info("🎯 Speaker assignment dialog accepted - analyzing changes...")

        # Collect all assignments and track changes
        final_assignments = {}
        missing_assignments = []
        changes_made = []

        for speaker_id, card in self.speaker_cards.items():
            current_name = card.get_assigned_name()
            original_name = getattr(card.speaker_data, "suggested_name", "")
            original_source = getattr(card.speaker_data, "assignment_source", "unknown")

            if current_name:
                final_assignments[speaker_id] = current_name

                # Track changes from original suggestions
                if current_name != original_name:
                    change_type = "EDIT" if original_name else "NEW"
                    changes_made.append(
                        f"{change_type}: {speaker_id} '{original_name}' → '{current_name}' (was {original_source})"
                    )
                else:
                    changes_made.append(
                        f"KEPT: {speaker_id} → '{current_name}' ({original_source})"
                    )
            else:
                missing_assignments.append(speaker_id)

        # Log the results
        if changes_made:
            logger.info(f"📝 User actions on {len(self.speaker_data_list)} speakers:")
            for change in changes_made:
                logger.info(f"   {change}")
        else:
            logger.info("✅ No changes made to speaker assignments")

        # Check for missing assignments
        if missing_assignments:
            reply = QMessageBox.question(
                self,
                "Incomplete Assignments",
                f"The following speakers don't have names assigned:\n"
                f"{', '.join(missing_assignments)}\n\n"
                "Do you want to continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.No:
                return

        # Save assignments to database if requested
        if self.save_for_future_cb.isChecked():
            self._save_assignments_to_database(final_assignments)

        # Check if HCE data exists and offer to update
        self._check_and_offer_hce_update(final_assignments)

        # Emit completion signal
        self.speaker_assignments_completed.emit(final_assignments)
        self.accept()

    def _on_reject(self):
        """Handle dialog rejection."""
        self.assignment_cancelled.emit()
        self.reject()

    def closeEvent(self, event):
        """Handle window close event - treat as acceptance."""
        # When user closes window, treat it as accepting current assignments
        logger.info("🎯 Speaker assignment dialog closed - treating as acceptance")

        # Collect all current assignments
        final_assignments = {}
        for speaker_id, card in self.speaker_cards.items():
            name = card.get_assigned_name()
            if name:
                final_assignments[speaker_id] = name

        # Save assignments to database if requested
        if self.save_for_future_cb.isChecked():
            self._save_assignments_to_database(final_assignments)

        # Emit completion signal
        self.speaker_assignments_completed.emit(final_assignments)

        # Accept the dialog
        event.accept()
        self.accept()

    def _on_reset(self):
        """Reset all assignments to AI suggestions."""
        for speaker_id, card in self.speaker_cards.items():
            # Find original speaker data
            speaker_data = next(
                (s for s in self.speaker_data_list if s.speaker_id == speaker_id), None
            )

            if speaker_data and speaker_data.suggested_name:
                card.set_assigned_name(speaker_data.suggested_name)
            else:
                card.set_assigned_name("")

        logger.info("Reset all assignments to AI suggestions")

    def _save_assignments_to_database(self, assignments: dict[str, str]):
        """Save speaker assignments to database with conflict prevention and detailed logging."""
        try:
            logger.info(
                f"💾 Saving {len(assignments)} speaker assignments with conflict prevention..."
            )

            # Get existing assignments for comparison
            existing_assignments = self.db_service.get_assignments_for_recording(
                self.recording_path
            )
            existing_map = {a.speaker_id: a.assigned_name for a in existing_assignments}

            save_stats = {"updated": 0, "created": 0, "unchanged": 0}

            for speaker_id, name in assignments.items():
                existing_name = existing_map.get(speaker_id)

                if existing_name:
                    if existing_name != name:
                        logger.info(
                            f"🔄 UPDATING: {speaker_id} '{existing_name}' → '{name}'"
                        )
                        save_stats["updated"] += 1
                    else:
                        logger.info(f"✅ UNCHANGED: {speaker_id} → '{name}'")
                        save_stats["unchanged"] += 1
                else:
                    logger.info(f"🆕 CREATING: {speaker_id} → '{name}'")
                    save_stats["created"] += 1

                assignment_data = SpeakerAssignmentModel(
                    recording_path=self.recording_path,
                    speaker_id=speaker_id,
                    assigned_name=name,
                    confidence=1.0,  # User-confirmed
                    user_confirmed=True,
                    suggestion_method="manual_assignment",
                )

                self.db_service.create_speaker_assignment(assignment_data)

            # Learn channel-to-host mapping from user corrections
            self._learn_channel_mappings(assignments)

            logger.info(
                f"✅ Save complete: {save_stats['created']} created, {save_stats['updated']} updated, {save_stats['unchanged']} unchanged"
            )

        except Exception as e:
            logger.error(f"❌ Error saving assignments to database: {e}")

    def _learn_channel_mappings(self, assignments: dict[str, str]):
        """Learn channel-to-host mappings from user assignments."""
        try:
            if not self.metadata or not self.metadata.get("uploader"):
                return

            channel_name = self.metadata["uploader"]

            # Look for patterns that suggest host vs guest
            # Typically the host speaks first and more frequently
            if len(assignments) >= 2:
                # Get speaker speaking stats to identify likely host
                host_candidate = self._identify_likely_host()
                if host_candidate and host_candidate in assignments:
                    host_name = assignments[host_candidate]

                    # Save the channel mapping
                    self.db_service.create_or_update_channel_mapping(
                        channel_name=channel_name,
                        host_name=host_name,
                        created_by="user_correction",
                        confidence=0.8,
                    )
                    logger.info(
                        f"Learned channel mapping: {channel_name} -> {host_name}"
                    )

        except Exception as e:
            logger.error(f"Error learning channel mappings: {e}")

    def _check_and_offer_hce_update(self, assignments: dict[str, str]):
        """
        Check if HCE data exists for this episode and offer to update it.

        Args:
            assignments: Final speaker assignments {speaker_id: name}
        """
        try:
            # Only proceed if we have a video_id
            video_id = self.metadata.get("video_id") or self.metadata.get("id")
            if not video_id:
                logger.debug("No video_id found, skipping HCE update check")
                return

            # Check if HCE data exists for this video
            from ...processors.speaker_processor import SpeakerProcessor

            episode_id = SpeakerProcessor.find_episode_id_for_video(video_id)

            if not episode_id:
                logger.debug(f"No HCE data found for video {video_id}, skipping update")
                return

            logger.info(
                f"Found HCE episode {episode_id} for video {video_id}, offering update"
            )

            # Build speaker mappings (old_speaker -> new_speaker)
            speaker_mappings = {}
            for speaker_data in self.speaker_data_list:
                old_speaker = speaker_data.speaker_id
                new_speaker = assignments.get(old_speaker)

                if new_speaker and old_speaker != new_speaker:
                    speaker_mappings[old_speaker] = new_speaker

            if not speaker_mappings:
                logger.debug("No speaker name changes detected, skipping HCE update")
                return

            # We need the transcript data to reprocess
            # Try to load it from the database
            try:
                from ...database.service import DatabaseService

                db_service = DatabaseService()
                transcripts = db_service.get_transcripts_for_video(video_id)

                if not transcripts:
                    logger.warning(f"No transcript found for video {video_id}")
                    return

                # Get the most recent transcript
                transcript = transcripts[0]

                # Build transcript data dictionary
                transcript_data = {
                    "segments": transcript.transcript_segments_json or [],
                    "text": transcript.transcript_text or "",
                }

                # Apply speaker assignments to transcript data (in memory)
                for segment in transcript_data["segments"]:
                    old_speaker = segment.get("speaker")
                    if old_speaker in assignments:
                        segment["speaker"] = assignments[old_speaker]

                # Show HCE update dialog
                from .hce_update_dialog import show_hce_update_dialog

                segment_count = len(transcript_data["segments"])

                logger.info(
                    f"Showing HCE update dialog for episode {episode_id} "
                    f"with {len(speaker_mappings)} speaker changes"
                )

                # This will handle the update and reprocessing
                show_hce_update_dialog(
                    episode_id=episode_id,
                    video_id=video_id,
                    speaker_mappings=speaker_mappings,
                    transcript_data=transcript_data,
                    segment_count=segment_count,
                    parent=self,
                )

            except Exception as e:
                logger.error(f"Failed to load transcript for HCE update: {e}")

        except Exception as e:
            logger.error(f"Error checking for HCE update: {e}")

    def _identify_likely_host(self) -> str | None:
        """Identify the speaker most likely to be the host based on speaking patterns."""
        try:
            # Host typically speaks first and has more segments
            speaker_stats = {}

            for speaker_data in self.speaker_data_list:
                speaker_id = speaker_data.speaker_id
                total_segments = len(speaker_data.segments)
                first_appearance = min(
                    (seg.start for seg in speaker_data.segments), default=float("inf")
                )
                total_duration = speaker_data.total_duration

                speaker_stats[speaker_id] = {
                    "segments": total_segments,
                    "first_appearance": first_appearance,
                    "duration": total_duration,
                    "score": 0,
                }

            # Score speakers (host typically speaks first and more)
            for speaker_id, stats in speaker_stats.items():
                # Points for speaking early (within first 30 seconds gets bonus)
                if stats["first_appearance"] <= 30:
                    stats["score"] += 3
                elif stats["first_appearance"] <= 120:  # First 2 minutes
                    stats["score"] += 1

                # Points for having more segments (more interactive)
                max_segments = max(
                    (s["segments"] for s in speaker_stats.values()), default=1
                )
                if (
                    stats["segments"] >= max_segments * 0.8
                ):  # Top speakers by segment count
                    stats["score"] += 2

            # Return speaker with highest score
            if speaker_stats:
                host_candidate = max(
                    speaker_stats.keys(), key=lambda k: speaker_stats[k]["score"]
                )
                logger.debug(
                    f"Identified likely host: {host_candidate} with score {speaker_stats[host_candidate]['score']}"
                )
                return host_candidate

        except Exception as e:
            logger.error(f"Error identifying likely host: {e}")

        return None

    def get_assignments(self) -> dict[str, str]:
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
    speaker_data_list: list[SpeakerData],
    recording_path: str = "",
    metadata: dict | None = None,
    parent=None,
) -> dict[str, str] | None:
    """
    Show speaker assignment dialog and return assignments.

    Args:
        speaker_data_list: List of speaker data objects
        recording_path: Path to the recording file
        metadata: Optional YouTube/podcast metadata for auto-assignment
        parent: Parent widget

    Returns:
        Dictionary of speaker assignments or None if cancelled
    """
    # Critical safety check: Never show dialog during testing mode
    from ...utils.testing import is_testing_mode

    if is_testing_mode():
        logger.error(
            "🧪 CRITICAL: Attempted to show SpeakerAssignmentDialog during testing mode - BLOCKED!"
        )
        return None

    dialog = SpeakerAssignmentDialog(
        speaker_data_list, recording_path, metadata, parent
    )

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_assignments()

    return None
