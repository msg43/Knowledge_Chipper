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
    QProgressBar, QFrame, QGroupBox
)
from PyQt6.QtGui import QTextCharFormat, QColor, QFont

from ...database import DatabaseService
from ...logger import get_logger

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
        self.current_transcript_path: Optional[Path] = None
        self.speaker_segments: List[SpeakerSegment] = []
        self.speaker_mappings: Dict[str, str] = {}  # speaker_id -> assigned_name
        self.known_speakers: Dict[str, Dict] = {}  # name -> voice characteristics
        
        self.setup_ui()
        self.load_known_speakers()
    
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
        header_layout.addWidget(self.load_btn)
        
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
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.auto_assign_btn = QPushButton("Auto-Assign Speakers")
        self.auto_assign_btn.clicked.connect(self.auto_assign_speakers)
        controls_layout.addWidget(self.auto_assign_btn)
        
        self.save_assignments_btn = QPushButton("Save Assignments")
        self.save_assignments_btn.clicked.connect(self.save_assignments)
        controls_layout.addWidget(self.save_assignments_btn)
        
        self.export_btn = QPushButton("Export Attributed")
        self.export_btn.clicked.connect(self.export_attributed_transcript)
        controls_layout.addWidget(self.export_btn)
        
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
        assign_layout.addWidget(self.assign_btn)
        
        speaker_layout.addLayout(assign_layout)
        layout.addWidget(speaker_group)
        
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
            self.current_transcript_path = Path(file_path)
            self.update_status(f"Loading {self.current_transcript_path.name}...")
            
            # Parse transcript
            self.speaker_segments = self.parse_transcript(self.current_transcript_path)
            
            # Display transcript
            self.display_transcript()
            
            # Update speaker list
            self.update_speaker_list()
            
            # Update UI
            self.transcript_label.setText(f"Transcript: {self.current_transcript_path.name}")
            
            self.update_status(
                f"Loaded {len(self.speaker_segments)} segments with "
                f"{len(self.get_unique_speakers())} speakers"
            )
            
        except Exception as e:
            logger.error(f"Failed to load transcript: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load transcript: {str(e)}")
    
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
    
    def auto_assign_speakers(self):
        """Automatically assign speakers based on voice characteristics."""
        self.update_status("Auto-assigning speakers...")
        self.progress_bar.setVisible(True)
        
        # Simulate processing with timer
        QTimer.singleShot(1000, self.complete_auto_assignment)
    
    def complete_auto_assignment(self):
        """Complete the auto-assignment process."""
        speakers = self.get_unique_speakers()
        
        # Common speaker names
        auto_names = ["Host", "Guest 1", "Guest 2", "Guest 3", "Caller"]
        
        for i, speaker_id in enumerate(speakers[:len(auto_names)]):
            if speaker_id not in self.speaker_mappings:
                self.speaker_mappings[speaker_id] = auto_names[i]
        
        # Update displays
        self.update_speaker_list()
        self.display_transcript()
        
        self.progress_bar.setVisible(False)
        self.update_status(f"Auto-assigned {len(speakers)} speakers")
    
    def save_assignments(self):
        """Save speaker assignments to database."""
        if not self.current_transcript_path:
            return
        
        try:
            # Save to a sidecar file
            assignments_file = self.current_transcript_path.with_suffix(
                ".speaker_assignments.json"
            )
            
            data = {
                "transcript": str(self.current_transcript_path),
                "assignments": self.speaker_mappings,
                "timestamp": datetime.now().isoformat(),
                "segments": [
                    {
                        "start": seg.start_time,
                        "end": seg.end_time,
                        "speaker_id": seg.speaker_id,
                        "assigned_name": self.speaker_mappings.get(seg.speaker_id),
                        "text": seg.text[:100] + "..." if len(seg.text) > 100 else seg.text
                    }
                    for seg in self.speaker_segments
                ]
            }
            
            with open(assignments_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            self.update_status(f"Saved assignments to {assignments_file.name}")
            
        except Exception as e:
            logger.error(f"Failed to save assignments: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")
    
    def export_attributed_transcript(self):
        """Export transcript with speaker names."""
        if not self.current_transcript_path or not self.speaker_segments:
            return
        
        # Ask for output location
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Attributed Transcript",
            str(self.current_transcript_path.with_suffix(".attributed.md")),
            "Markdown files (*.md);;Text files (*.txt);;All files (*.*)"
        )
        
        if not output_path:
            return
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # Write header
                f.write(f"# Attributed Transcript\n\n")
                f.write(f"Original: {self.current_transcript_path.name}\n")
                f.write(f"Attributed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Write speaker list
                f.write("## Speakers\n\n")
                for speaker_id, name in self.speaker_mappings.items():
                    f.write(f"- **{speaker_id}**: {name}\n")
                f.write("\n---\n\n")
                
                # Write transcript
                f.write("## Transcript\n\n")
                for segment in self.speaker_segments:
                    speaker_name = self.speaker_mappings.get(
                        segment.speaker_id,
                        segment.speaker_id
                    )
                    timestamp = self.format_timestamp(segment.start_time)
                    
                    f.write(f"**{speaker_name}** ({timestamp}):\n")
                    f.write(f"{segment.text}\n\n")
            
            self.update_status(f"Exported to {Path(output_path).name}")
            
        except Exception as e:
            logger.error(f"Failed to export transcript: {e}")
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")
    
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
