"""
Speaker Attribution Tab for Knowledge System GUI (PyQt6).

Provides interface for managing speaker identification and voice assignments
for transcripts, including manual correction and speaker database management.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QListWidget, QFileDialog, QMessageBox,
    QProgressBar, QFrame, QGroupBox, QScrollArea
)
from PyQt6.QtGui import QTextCharFormat, QColor, QFont

from ...database import DatabaseService
from ...logger import get_logger
from ...database.speaker_models import (
    get_speaker_db_service,
    SpeakerAssignmentModel,
)

logger = get_logger(__name__)


class SpeakerSegment:
    """Represents a speaker segment in a transcript."""
    
    def __init__(self, start_time: float, end_time: float, speaker_id: str, text: str):
        self.start_time = start_time
        self.end_time = end_time
        self.speaker_id = speaker_id
        self.text = text
        self.assigned_name: Optional[str] = None


class SpeakerAttributionTab(QWidget):
    """Tab for managing speaker attribution and identification."""
    
    status_update = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.db = DatabaseService()
        self.db_speakers = get_speaker_db_service()
        self.current_transcript_path: Optional[Path] = None
        self.speaker_segments: List[SpeakerSegment] = []
        self.speaker_mappings: Dict[str, str] = {}  # speaker_id -> assigned_name
        self.known_speakers: Dict[str, Dict] = {}  # name -> voice characteristics
        self.unconfirmed_queue: List[Path] = []
        self.queue_index: int = -1
        
        self.setup_ui()
        self.load_known_speakers()
        # Auto-build queue of transcripts needing confirmation and load first
        try:
            self.build_unconfirmed_queue()
            if self.unconfirmed_queue:
                self.queue_index = 0
                self.load_transcript_from_path(self.unconfirmed_queue[0])
                self.update_queue_label()
        except Exception as e:
            logger.warning(f"Failed to initialize unconfirmed transcript queue: {e}")
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Speaker Attribution Manager")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Load transcript button
        self.load_btn = QPushButton("Load Transcript")
        self.load_btn.clicked.connect(self.load_transcript)
        self.load_btn.setToolTip(
            "Load a transcript file for speaker attribution and review.\n"
            "• Supports transcripts with speaker diarization data\n"
            "• Allows manual assignment of real names to detected speakers\n"
            "• Automatically detects transcripts needing speaker confirmation\n"
            "• Supports both individual files and batch processing"
        )
        header_layout.addWidget(self.load_btn)

        # Queue/navigation controls
        self.queue_label = QLabel("")
        self.queue_label.setStyleSheet("font-size: 12px; color: #666;")
        self.queue_label.setToolTip(
            "Shows current position in the queue of transcripts needing speaker confirmation.\n"
            "• Automatically builds a queue of unconfirmed transcripts\n"
            "• Navigate through transcripts using Previous/Next buttons\n"
            "• Shows progress through the confirmation process"
        )
        header_layout.addWidget(self.queue_label)

        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(self.on_prev_in_queue)
        self.prev_btn.setEnabled(False)
        self.prev_btn.setToolTip(
            "Navigate to the previous transcript in the confirmation queue.\n"
            "• Moves backward through transcripts needing speaker attribution\n"
            "• Saves current speaker assignments before navigating\n"
            "• Disabled when at the beginning of the queue"
        )
        header_layout.addWidget(self.prev_btn)

        self.confirm_next_btn = QPushButton("Confirm & Next")
        self.confirm_next_btn.clicked.connect(self.on_confirm_and_next)
        self.confirm_next_btn.setEnabled(False)
        self.confirm_next_btn.setToolTip(
            "Confirm current speaker assignments and move to next transcript.\n"
            "• Saves all speaker name assignments to the current transcript\n"
            "• Automatically advances to the next unconfirmed transcript\n"
            "• Updates the transcript files with confirmed speaker names\n"
            "• Most efficient way to process multiple transcripts"
        )
        header_layout.addWidget(self.confirm_next_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.on_next_in_queue)
        self.next_btn.setEnabled(False)
        self.next_btn.setToolTip(
            "Move to the next transcript without saving current assignments.\n"
            "• Advances to the next transcript in the confirmation queue\n"
            "• Does not save current speaker assignments\n"
            "• Use this to skip transcripts or review multiple files\n"
            "• Disabled when at the end of the queue"
        )
        header_layout.addWidget(self.next_btn)

        # Batch preview button
        self.preview_all_btn = QPushButton("Preview All Unconfirmed")
        self.preview_all_btn.clicked.connect(self.show_batch_preview_all)
        self.preview_all_btn.setToolTip(
            "Preview all transcripts that need speaker confirmation.\n"
            "• Shows a batch overview of all unconfirmed transcripts\n"
            "• Allows bulk speaker assignment across multiple files\n"
            "• Helps identify patterns and common speakers\n"
            "• Efficient for processing large batches of similar content"
        )
        header_layout.addWidget(self.preview_all_btn)
        
        layout.addLayout(header_layout)
        
        # Main content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Transcript view
        self.transcript_widget = self.create_transcript_panel()
        splitter.addWidget(self.transcript_widget)
        
        # Right panel - Speaker management
        self.speaker_widget = self.create_speaker_panel()
        splitter.addWidget(self.speaker_widget)
        
        # Set splitter sizes (3:1 ratio)
        splitter.setSizes([600, 200])
        
        layout.addWidget(splitter)
        
        # Status bar
        self.create_status_bar(layout)
    
    def create_transcript_panel(self) -> QWidget:
        """Create the transcript viewing panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Transcript info
        self.transcript_label = QLabel("No transcript loaded")
        self.transcript_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.transcript_label)
        
        # Transcript display
        self.transcript_text = QTextEdit()
        self.transcript_text.setReadOnly(True)
        self.transcript_text.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, monospace;
                font-size: 11pt;
                background-color: #2b2b2b;
                color: #ffffff;
            }
        """)
        layout.addWidget(self.transcript_text)
        
        # Controls - simplified after removing auto-assign and export buttons
        controls_layout = QHBoxLayout()
        
        self.save_assignments_btn = QPushButton("Save Assignments")
        self.save_assignments_btn.clicked.connect(self.save_assignments)
        self.save_assignments_btn.setToolTip(
            "Save current speaker name assignments to the transcript file.\n"
            "• Updates the transcript with assigned speaker names\n"
            "• Preserves speaker timing and segment information\n"
            "• Creates backup of original file before modification\n"
            "• Required before moving to next transcript"
        )
        controls_layout.addWidget(self.save_assignments_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        return widget
    
    def create_speaker_panel(self) -> QWidget:
        """Create the speaker management panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Speaker list
        speaker_group = QGroupBox("Detected Speakers")
        speaker_layout = QVBoxLayout(speaker_group)
        
        # Speaker tree
        self.speaker_tree = QTreeWidget()
        self.speaker_tree.setHeaderLabels(["Speaker", "Segments", "Duration", "Assigned To"])
        self.speaker_tree.itemSelectionChanged.connect(self.on_speaker_select)
        speaker_layout.addWidget(self.speaker_tree)
        
        # Assignment controls
        assign_layout = QHBoxLayout()
        assign_layout.addWidget(QLabel("Assign to:"))
        
        self.name_entry = QLineEdit()
        assign_layout.addWidget(self.name_entry)
        
        self.assign_btn = QPushButton("Assign")
        self.assign_btn.clicked.connect(self.assign_speaker)
        self.assign_btn.setToolTip(
            "Assign the entered name to the selected speaker ID.\n"
            "• Maps the real name to all segments from this speaker\n"
            "• Updates the transcript display with the assigned name\n"
            "• Creates consistent speaker identification across the transcript\n"
            "• Can be changed later if needed"
        )
        assign_layout.addWidget(self.assign_btn)
        
        speaker_layout.addLayout(assign_layout)
        layout.addWidget(speaker_group)
        
        # All speakers samples (current transcript)
        all_group = QGroupBox("All Speakers (first five per speaker)")
        all_layout = QVBoxLayout(all_group)
        self.all_speakers_scroll = QScrollArea()
        self.all_speakers_scroll.setWidgetResizable(True)
        all_layout.addWidget(self.all_speakers_scroll)
        layout.addWidget(all_group)
        
        # Speaker samples panel
        samples_group = QGroupBox("Speaker Samples (first five)")
        samples_layout = QVBoxLayout(samples_group)
        self.speaker_samples_text = QTextEdit()
        self.speaker_samples_text.setReadOnly(True)
        self.speaker_samples_text.setStyleSheet(
            "QTextEdit { font-family: Consolas, monospace; font-size: 10pt; }"
        )
        samples_layout.addWidget(self.speaker_samples_text)
        layout.addWidget(samples_group)
        
        # Known speakers
        known_group = QGroupBox("Known Speakers")
        known_layout = QVBoxLayout(known_group)
        
        self.known_speakers_listbox = QListWidget()
        self.known_speakers_listbox.itemDoubleClicked.connect(self.assign_from_known)
        known_layout.addWidget(self.known_speakers_listbox)
        
        layout.addWidget(known_group)
        
        return widget
    
    def create_status_bar(self, parent_layout):
        """Create the status bar."""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.Box)
        status_layout = QHBoxLayout(status_frame)
        
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        parent_layout.addWidget(status_frame)

    def show_batch_preview_all(self):
        """Show a quick preview list of all unconfirmed transcripts in the queue.

        This provides a lightweight, non-blocking overview so users can see
        what will be processed without starting the confirmation flow.
        """
        try:
            if not self.unconfirmed_queue:
                QMessageBox.information(
                    self,
                    "Batch Preview",
                    "No pending transcripts to preview."
                )
                return

            # Build a concise preview (limit to first 20 items to keep dialog readable)
            max_items = 20
            items = [
                f"{idx+1}. {p.name} — {p.parent}"
                for idx, p in enumerate(self.unconfirmed_queue[:max_items])
            ]
            if len(self.unconfirmed_queue) > max_items:
                items.append(f"… and {len(self.unconfirmed_queue) - max_items} more")

            preview_text = "\n".join(items)

            dlg = QMessageBox(self)
            dlg.setWindowTitle("Batch Preview - Unconfirmed Transcripts")
            dlg.setIcon(QMessageBox.Icon.Information)
            dlg.setText(
                f"Pending transcripts: {len(self.unconfirmed_queue)}\n\n"
                "This is a preview of files awaiting speaker confirmation."
            )
            dlg.setDetailedText(preview_text)
            dlg.addButton(QMessageBox.StandardButton.Ok)
            dlg.exec()
        except Exception as e:
            logger.warning(f"Failed to show batch preview: {e}")
    
    def load_transcript(self):
        """Load a transcript file for speaker attribution."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Transcript",
            "",
            "Markdown files (*.md);;Text files (*.txt);;JSON files (*.json);;All files (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            self.load_transcript_from_path(Path(file_path))
            
        except Exception as e:
            logger.error(f"Failed to load transcript: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load transcript: {str(e)}")

    def load_transcript_from_path(self, file_path: Path):
        """Load transcript from a given path and pre-apply any existing assignments."""
        self.current_transcript_path = file_path
        self.update_status(f"Loading {self.current_transcript_path.name}...")

        # Reset current mappings before load
        self.speaker_mappings = {}

        # Load existing assignments from database
        pre_assignments: Dict[str, str] = {}
        recording_path = str(file_path)
        
        try:
            # First check database for assignments
            assignments = self.db_speakers.get_assignments_for_recording(recording_path)
            if assignments:
                for assignment in assignments:
                    pre_assignments[assignment.speaker_id] = assignment.assigned_name
                logger.info(f"Loaded {len(assignments)} assignments from database")
            
            # Fallback: extract from JSON transcript if no database assignments
            if not pre_assignments and file_path.suffix.lower() == ".json" and file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        # Prefer explicit speaker_assignments if present
                        pre_assignments = data.get("speaker_assignments", {}) or {}
                        # If not present, attempt to derive mapping from segments preserving original ids
                        if not pre_assignments and "segments" in data:
                            for seg in data["segments"]:
                                orig_id = seg.get("original_speaker_id") or seg.get("speaker")
                                name = seg.get("speaker")
                                if orig_id and name:
                                    pre_assignments.setdefault(str(orig_id), str(name))
                        logger.debug(f"Fallback: extracted {len(pre_assignments)} assignments from JSON")
                except Exception as e:
                    logger.debug(f"No fallback assignments available from JSON: {e}")
                    
        except Exception as e:
            logger.error(f"Error loading assignments from database: {e}")

        # Parse transcript into segments
        self.speaker_segments = self.parse_transcript(self.current_transcript_path)

        # Apply pre-assignments if available
        if pre_assignments:
            self.speaker_mappings.update(pre_assignments)
        else:
            # Try to get auto-suggestions from learning service
            try:
                from ...services.speaker_learning_service import get_speaker_learning_service
                learning_service = get_speaker_learning_service()
                
                # Extract speaker data for suggestions
                speaker_data = self._extract_speaker_data_from_transcript(file_path)
                if speaker_data:
                    learned_suggestions = learning_service.suggest_assignments_from_learning(
                        recording_path, speaker_data
                    )
                    
                    if learned_suggestions:
                        # Apply learned suggestions as initial mappings
                        for speaker_id, (suggested_name, confidence) in learned_suggestions.items():
                            if confidence > 0.5:  # Only use high-confidence suggestions
                                self.speaker_mappings[speaker_id] = suggested_name
                        
                        logger.info(f"Applied {len(learned_suggestions)} learned suggestions")
                        self.update_status(f"Applied learned suggestions for {len(learned_suggestions)} speakers")
                    
            except Exception as e:
                logger.debug(f"Could not get learned suggestions: {e}")

        # Render UI
        self.display_transcript()
        self.update_speaker_list()
        self.transcript_label.setText(self._make_source_header_text())
        self._update_all_speakers_samples()
        self.update_status(
            f"Loaded {len(self.speaker_segments)} segments with {len(self.get_unique_speakers())} speakers"
        )
        # Enable queue controls if we have a queue
        has_queue = len(self.unconfirmed_queue) > 0
        self.prev_btn.setEnabled(has_queue and self.queue_index > 0)
        self.next_btn.setEnabled(has_queue and self.queue_index < len(self.unconfirmed_queue) - 1)
        self.confirm_next_btn.setEnabled(True if self.speaker_segments else False)
    
    def parse_transcript(self, file_path: Path) -> List[SpeakerSegment]:
        """Parse transcript file and extract speaker segments."""
        segments = []
        
        # Check file type
        if file_path.suffix == ".json":
            # JSON format (from diarization)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if "segments" in data:
                for seg in data["segments"]:
                    segments.append(SpeakerSegment(
                        start_time=seg.get("start", 0),
                        end_time=seg.get("end", 0),
                        speaker_id=seg.get("speaker", "Unknown"),
                        text=seg.get("text", "")
                    ))
        else:
            # Text/Markdown format
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for speaker patterns
            # Pattern: [Speaker_0] (00:00:00): Text...
            import re
            pattern = r'\[([^\]]+)\]\s*\((\d{2}:\d{2}:\d{2})\):\s*(.+?)(?=\n\[|$)'
            matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            
            for speaker, timestamp, text in matches:
                # Convert timestamp to seconds
                h, m, s = map(int, timestamp.split(':'))
                start_time = h * 3600 + m * 60 + s
                
                segments.append(SpeakerSegment(
                    start_time=start_time,
                    end_time=start_time + 30,  # Estimate
                    speaker_id=speaker,
                    text=text.strip()
                ))
        
        return segments
    
    def display_transcript(self):
        """Display the loaded transcript with speaker highlighting."""
        self.transcript_text.clear()
        
        # Define colors for different speakers
        speaker_colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#96E6A1",
            "#DDA0DD", "#F7DC6F", "#85C1E2", "#F8B195"
        ]
        
        cursor = self.transcript_text.textCursor()
        
        for i, segment in enumerate(self.speaker_segments):
            # Format timestamp
            timestamp = self.format_timestamp(segment.start_time)
            
            # Get speaker display name
            speaker_name = self.speaker_mappings.get(
                segment.speaker_id,
                segment.speaker_id
            )
            
            # Determine color
            speaker_index = self.get_speaker_index(segment.speaker_id)
            color = speaker_colors[speaker_index % len(speaker_colors)]
            
            # Create format for speaker name
            speaker_format = QTextCharFormat()
            speaker_format.setForeground(QColor(color))
            speaker_format.setFontWeight(QFont.Weight.Bold)
            
            # Insert speaker and timestamp
            cursor.insertText(f"[{speaker_name}] ({timestamp}):\n", speaker_format)
            
            # Insert text with normal format
            normal_format = QTextCharFormat()
            cursor.insertText(f"{segment.text}\n\n", normal_format)
    
    def update_speaker_list(self):
        """Update the speaker list in the tree widget."""
        self.speaker_tree.clear()
        
        # Calculate speaker statistics
        speaker_stats = self.calculate_speaker_stats()
        
        # Add speakers to tree
        for speaker_id, stats in speaker_stats.items():
            assigned_name = self.speaker_mappings.get(speaker_id, "")
            
            item = QTreeWidgetItem([
                speaker_id,
                str(stats["segments"]),
                self.format_duration(stats["duration"]),
                assigned_name
            ])
            self.speaker_tree.addTopLevelItem(item)
    
    def calculate_speaker_stats(self) -> Dict[str, Dict]:
        """Calculate statistics for each speaker."""
        stats = {}
        
        for segment in self.speaker_segments:
            if segment.speaker_id not in stats:
                stats[segment.speaker_id] = {
                    "segments": 0,
                    "duration": 0
                }
            
            stats[segment.speaker_id]["segments"] += 1
            stats[segment.speaker_id]["duration"] += (
                segment.end_time - segment.start_time
            )
        
        return stats
    
    def get_unique_speakers(self) -> List[str]:
        """Get list of unique speaker IDs."""
        return list(set(seg.speaker_id for seg in self.speaker_segments))
    
    def get_speaker_index(self, speaker_id: str) -> int:
        """Get consistent index for a speaker ID."""
        speakers = sorted(self.get_unique_speakers())
        return speakers.index(speaker_id) if speaker_id in speakers else 0
    
    def on_speaker_select(self):
        """Handle speaker selection in tree widget."""
        selected_items = self.speaker_tree.selectedItems()
        if selected_items:
            speaker_id = selected_items[0].text(0)
            self.highlight_speaker_segments(speaker_id)
            self._populate_speaker_samples(speaker_id)
    
    def highlight_speaker_segments(self, speaker_id: str):
        """Highlight all segments for a specific speaker."""
        # This is a simplified version - could be enhanced with proper text selection
        cursor = self.transcript_text.textCursor()
        cursor.setPosition(0)
        
        # Clear existing selections
        self.transcript_text.setExtraSelections([])
        
        # Find and highlight segments
        # In a real implementation, we'd track text positions during display
    
    def assign_speaker(self):
        """Assign selected speaker to entered name."""
        selected_items = self.speaker_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a speaker")
            return
        
        name = self.name_entry.text().strip()
        if not name:
            QMessageBox.warning(self, "No Name", "Please enter a name")
            return
        
        # Get selected speaker
        speaker_id = selected_items[0].text(0)
        
        # Update mapping
        self.speaker_mappings[speaker_id] = name
        
        # Update displays
        self.update_speaker_list()
        self.display_transcript()
        
        # Clear entry
        self.name_entry.clear()
        
        self.update_status(f"Assigned {speaker_id} to {name}")
    
    def assign_from_known(self, item):
        """Assign speaker from known speakers list."""
        if item:
            name = item.text()
            self.name_entry.setText(name)
            self.assign_speaker()
    

    
    def save_assignments(self):
        """Save speaker assignments to database only."""
        if not self.current_transcript_path:
            return
        
        try:
            recording_path = str(self.current_transcript_path)
            
            # Save each assignment to database with enhanced data
            for speaker_id, assigned_name in self.speaker_mappings.items():
                # Find speaker data for this ID
                speaker_segments = [seg for seg in self.speaker_segments if seg.speaker_id == speaker_id]
                
                if speaker_segments:
                    # Prepare sample segments
                    sample_segments = []
                    for i, seg in enumerate(speaker_segments[:5]):
                        sample_segments.append({
                            'start': seg.start_time,
                            'end': seg.end_time,
                            'text': seg.text[:200],
                            'sequence': i + 1
                        })
                    
                    # Calculate totals
                    total_duration = sum(seg.end_time - seg.start_time for seg in speaker_segments)
                    segment_count = len(speaker_segments)
                    
                    # Create assignment model
                    assignment_data = SpeakerAssignmentModel(
                        recording_path=recording_path,
                        speaker_id=speaker_id,
                        assigned_name=assigned_name,
                        user_confirmed=False,  # Will be confirmed later
                        sample_segments=sample_segments,
                        total_duration=total_duration,
                        segment_count=segment_count,
                        suggestion_method="manual_assignment",
                        confidence=1.0
                    )
                    
                    # Save to database
                    self.db_speakers.create_speaker_assignment(assignment_data)
            
            self.update_status(f"Saved {len(self.speaker_mappings)} assignments to database")
            
        except Exception as e:
            logger.error(f"Failed to save assignments: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

    # ===== Queue and confirmation workflow =====
    def find_default_transcript_dirs(self) -> List[Path]:
        """Return plausible transcript directories to scan."""
        candidates = [
            Path("output/transcripts"),
            Path("Output/Transcripts"),
            Path("output"),
            Path("Output"),
        ]
        return [p for p in candidates if p.exists() and p.is_dir()]

    def build_unconfirmed_queue(self):
        """Build list of transcripts that have assignments but are not confirmed using database queries and learning."""
        try:
            # Get recordings needing review from database (with AI suggestions)
            recordings_needing_review = self.db_speakers.get_recordings_needing_review()
            queue: List[Path] = []
            
            # Add recordings with existing AI suggestions
            for recording_data in recordings_needing_review:
                path = Path(recording_data['recording_path'])
                if path.exists() and path.suffix.lower() in ['.json', '.md', '.txt']:
                    queue.append(path)
                    logger.debug(f"Added to queue with AI suggestions: {path.name}")
            
            # Also check for recordings that could benefit from learned auto-assignment
            from ...services.speaker_learning_service import get_speaker_learning_service
            learning_service = get_speaker_learning_service()
            
            # Find recent recordings without assignments that could be auto-assigned
            unconfirmed_paths = self.db_speakers.get_unconfirmed_recordings()
            for recording_path in unconfirmed_paths:
                path = Path(recording_path)
                if (path.exists() and path.suffix.lower() in ['.json', '.md', '.txt'] 
                    and path not in queue):
                    
                    # Try to generate learned suggestions for this recording
                    try:
                        # Extract basic speaker data from transcript
                        speaker_data = self._extract_speaker_data_from_transcript(path)
                        if speaker_data:
                            suggestions = learning_service.suggest_assignments_from_learning(
                                recording_path, speaker_data
                            )
                            if suggestions:
                                queue.append(path)
                                logger.debug(f"Added to queue with learned suggestions: {path.name}")
                    except Exception as e:
                        logger.debug(f"Could not generate suggestions for {path.name}: {e}")
            
            # Sort by modification time (newest first)
            queue.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            
            self.unconfirmed_queue = queue
            logger.info(f"Built enhanced queue with {len(queue)} recordings from database and learning")
            
        except Exception as e:
            logger.error(f"Error building unconfirmed queue: {e}")
            self.unconfirmed_queue = []
    
    def _extract_speaker_data_from_transcript(self, transcript_path: Path) -> List[Dict]:
        """Extract basic speaker data from transcript for learning suggestions."""
        try:
            if transcript_path.suffix.lower() != '.json':
                return []
            
            with open(transcript_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, dict) or 'segments' not in data:
                return []
            
            # Group segments by speaker
            speaker_stats = {}
            for segment in data['segments']:
                speaker_id = segment.get('speaker', 'UNKNOWN')
                if speaker_id not in speaker_stats:
                    speaker_stats[speaker_id] = {
                        'speaker_id': speaker_id,
                        'total_duration': 0.0,
                        'segment_count': 0,
                        'total_text': ''
                    }
                
                start = segment.get('start', 0)
                end = segment.get('end', 0)
                text = segment.get('text', '')
                
                speaker_stats[speaker_id]['total_duration'] += (end - start)
                speaker_stats[speaker_id]['segment_count'] += 1
                speaker_stats[speaker_id]['total_text'] += ' ' + text
            
            return list(speaker_stats.values())
            
        except Exception as e:
            logger.debug(f"Error extracting speaker data from {transcript_path}: {e}")
            return []
        # Update controls
        self.update_queue_label()
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(len(self.unconfirmed_queue) > 1)
        self.confirm_next_btn.setEnabled(len(self.unconfirmed_queue) > 0)

    def update_queue_label(self):
        """Update the queue status label."""
        if not self.unconfirmed_queue:
            self.queue_label.setText("No pending confirmations")
        else:
            self.queue_label.setText(
                f"Pending: {self.queue_index + 1}/{len(self.unconfirmed_queue)}"
            )

    def on_prev_in_queue(self):
        if not self.unconfirmed_queue:
            return
        if self.queue_index > 0:
            self.queue_index -= 1
            self.load_transcript_from_path(self.unconfirmed_queue[self.queue_index])
            self.update_queue_label()

    def on_next_in_queue(self):
        if not self.unconfirmed_queue:
            return
        if self.queue_index < len(self.unconfirmed_queue) - 1:
            self.queue_index += 1
            self.load_transcript_from_path(self.unconfirmed_queue[self.queue_index])
            self.update_queue_label()

    def on_confirm_and_next(self):
        """Mark current transcript as confirmed and move to next."""
        try:
            self._save_confirmation(True)
        except Exception as e:
            logger.error(f"Failed to save confirmation: {e}")
            QMessageBox.warning(self, "Warning", f"Failed to save confirmation: {e}")
        # Remove from queue
        if self.unconfirmed_queue and 0 <= self.queue_index < len(self.unconfirmed_queue):
            del self.unconfirmed_queue[self.queue_index]
            # Adjust index and navigate
            if self.queue_index >= len(self.unconfirmed_queue):
                self.queue_index = max(0, len(self.unconfirmed_queue) - 1)
        # Load next or clear
        if self.unconfirmed_queue:
            self.load_transcript_from_path(self.unconfirmed_queue[self.queue_index])
        else:
            self.transcript_label.setText("All speaker attributions confirmed ✅")
            self.transcript_text.clear()
            self.speaker_tree.clear()
            self.confirm_next_btn.setEnabled(False)
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
        self.update_queue_label()

    def _save_confirmation(self, confirmed: bool):
        """Persist confirmation to database only."""
        if not self.current_transcript_path:
            return
            
        recording_path = str(self.current_transcript_path)
        
        try:
            # Update existing assignments or create new ones with confirmation flag
            for spk_id, name in self.speaker_mappings.items():
                # Check if assignment already exists
                existing_assignments = self.db_speakers.get_assignments_for_recording(recording_path)
                existing_assignment = None
                for assignment in existing_assignments:
                    if assignment.speaker_id == spk_id:
                        existing_assignment = assignment
                        break
                
                if existing_assignment:
                    # Update existing assignment
                    self.db_speakers.update_assignment_with_enhancement(
                        existing_assignment.id,
                        assigned_name=str(name),
                        user_confirmed=bool(confirmed),
                        updated_at=datetime.now()
                    )
                    logger.debug(f"Updated assignment confirmation: {spk_id} -> {name}")
                else:
                    # Create new assignment
                    assignment = SpeakerAssignmentModel(
                        recording_path=recording_path,
                        speaker_id=str(spk_id),
                        assigned_name=str(name),
                        confidence=1.0,
                        user_confirmed=bool(confirmed),
                    )
                    self.db_speakers.create_speaker_assignment(assignment)
                    logger.debug(f"Created new assignment: {spk_id} -> {name}")
            
            logger.info(f"Saved confirmation for {len(self.speaker_mappings)} assignments: confirmed={confirmed}")
            
        except Exception as e:
            logger.error(f"Error saving confirmation to database: {e}")

    # ===== Utilities =====
    def _make_source_header_text(self) -> str:
        """Build a header showing a friendly source name."""
        source_name = self._get_sanitized_source_name()
        return f"Source: {source_name}  •  File: {self.current_transcript_path.name}"

    def _get_sanitized_source_name(self) -> str:
        """Derive a sanitized source/episode/document name from metadata or filename."""
        try:
            if self.current_transcript_path and self.current_transcript_path.suffix.lower() == ".json":
                with open(self.current_transcript_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                original = None
                if isinstance(data, dict):
                    original = data.get("original_file_path") or data.get("source_file")
                if original:
                    return self._sanitize_name(Path(original).stem)
        except Exception:
            pass
        # Fallback to transcript filename stem
        return self._sanitize_name(self.current_transcript_path.stem if self.current_transcript_path else "Unknown")

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name: keep alnum, space, dash, underscore; convert spaces to underscores for clarity."""
        safe = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_"))
        return safe.strip().replace("  ", " ").replace(" ", "_")

    def _populate_speaker_samples(self, speaker_id: str):
        """Show the first five snippets for the selected speaker with timestamps."""
        if not self.speaker_segments:
            self.speaker_samples_text.clear()
            return
        # Collect segments for this speaker in chronological order
        segs = [s for s in self.speaker_segments if s.speaker_id == speaker_id]
        # Sort by start_time to ensure order
        segs.sort(key=lambda s: s.start_time)
        samples = []
        for seg in segs[:5]:
            ts = self.format_timestamp(seg.start_time)
            text = seg.text.strip()
            if len(text) > 200:
                text = text[:197] + "..."
            # Map to assigned display name if available
            disp_name = self.speaker_mappings.get(speaker_id, speaker_id)
            samples.append(f"[{disp_name}] ({ts})\n{text}")
        if not samples:
            self.speaker_samples_text.setPlainText("No samples available for this speaker.")
        else:
            self.speaker_samples_text.setPlainText("\n\n".join(samples))
    

    
    def load_known_speakers(self):
        """Load known speakers from database."""
        # This would load from the speaker_voices table
        # For now, we'll use some defaults
        default_speakers = [
            "Host",
            "Guest",
            "Interviewer", 
            "Interviewee",
            "Narrator",
            "Speaker 1",
            "Speaker 2"
        ]
        
        for speaker in default_speakers:
            self.known_speakers_listbox.addItem(speaker)
    
    def format_timestamp(self, seconds: float) -> str:
        """Format seconds to HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def format_duration(self, seconds: float) -> str:
        """Format duration in human-readable form."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"
    
    def update_status(self, message: str):
        """Update the status bar."""
        self.status_label.setText(message)
        self.status_update.emit(message)
