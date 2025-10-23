"""
Simple, reliable progress bar component for transcription operations.
Clean implementation focused on clarity and proper percentage display.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)


class SimpleTranscriptionProgressBar(QFrame):
    """
    Simple, reliable progress bar for transcription operations.
    Focuses on clear percentage display and accurate progress tracking.
    Cancel functionality is handled by the parent tab's 'Stop Processing' button.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0
        self.current_file_progress = 0  # Track progress within current file (0-100)
        self.current_phase = "Initializing"  # Track current processing phase
        self.phase_progress = 0  # Track progress within current phase (0-100)

        self._setup_ui()

        # Hide initially
        self.hide()

    def _setup_ui(self):
        """Setup the simple UI with clear progress display."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Title bar without cancel button (handled by BaseTab's Stop Processing button)
        title_layout = QHBoxLayout()

        self.title_label = QLabel("Processing...")
        self.title_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #ffffff;"
        )
        title_layout.addWidget(self.title_label)

        title_layout.addStretch()

        layout.addLayout(title_layout)

        # Phase progress bar (current phase: download, transcription, diarization, etc.)
        self.phase_label = QLabel("Phase: Initializing")
        self.phase_label.setStyleSheet("font-weight: normal; font-size: 11px; color: #b0b0b0;")
        layout.addWidget(self.phase_label)
        
        self.phase_progress_bar = QProgressBar()
        self.phase_progress_bar.setMinimum(0)
        self.phase_progress_bar.setMaximum(100)
        self.phase_progress_bar.setValue(0)
        self.phase_progress_bar.setTextVisible(True)
        self.phase_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phase_progress_bar.setFormat("%p%")
        self.phase_progress_bar.setFixedHeight(22)
        self.phase_progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #4c4c4c;
                border-radius: 4px;
                background-color: #2d2d2d;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 3px;
            }
        """
        )
        layout.addWidget(self.phase_progress_bar)
        
        # Add spacing
        layout.addSpacing(6)
        
        # Overall progress bar (total file progress)
        self.overall_label = QLabel("Overall Progress")
        self.overall_label.setStyleSheet("font-weight: normal; font-size: 11px; color: #b0b0b0;")
        layout.addWidget(self.overall_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedHeight(30)

        # Dark mode styling to match the app
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 2px solid #4c4c4c;
                border-radius: 5px;
                background-color: #2d2d2d;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 3px;
            }
        """
        )

        layout.addWidget(self.progress_bar)

        # Status line with file counts
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #b0b0b0; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Set frame styling - dark mode to match the app
        self.setStyleSheet(
            """
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
            }
        """
        )

    def start_processing(self, total_files: int, title: str = "Processing"):
        """Start processing with a known number of files."""
        self.total_files = total_files
        self.completed_files = 0
        self.failed_files = 0

        self.title_label.setText(title)

        if total_files > 0:
            # Determinate mode - always use 0-100 scale for proper percentage display
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)
        else:
            # Indeterminate mode
            self.progress_bar.setMaximum(0)
            self.progress_bar.setValue(0)

        self._update_status()
        self.show()

    def update_progress(self, completed: int, failed: int, current_file: str = ""):
        """Update progress with completed and failed counts."""
        self.completed_files = completed
        self.failed_files = failed

        total_processed = completed + failed

        # Calculate percentage and update progress bar (0-100 scale)
        # Include current file progress if available
        if self.total_files > 0:
            # Base percentage from completed files
            base_percentage = (total_processed / self.total_files) * 100
            
            # Add fractional progress from current file being processed
            if total_processed < self.total_files and self.current_file_progress > 0:
                # Each file represents (100 / total_files)% of total
                file_weight = 100 / self.total_files
                # Add the portion of the current file that's done
                current_file_contribution = (self.current_file_progress / 100) * file_weight
                percentage = int(base_percentage + current_file_contribution)
            else:
                percentage = int(base_percentage)
            
            self.progress_bar.setValue(percentage)
        else:
            percentage = 0

        # Update status text
        self._update_status(current_file)

    def update_current_file_progress(self, progress_percent: int):
        """Update progress within the current file being processed (0-100).
        
        This allows showing smooth progress during single file transcription.
        """
        self.current_file_progress = max(0, min(100, progress_percent))
        
        # Recalculate total progress including current file contribution
        if self.total_files > 0:
            total_processed = self.completed_files + self.failed_files
            base_percentage = (total_processed / self.total_files) * 100
            
            # Add fractional progress from current file
            if total_processed < self.total_files and self.current_file_progress > 0:
                file_weight = 100 / self.total_files
                current_file_contribution = (self.current_file_progress / 100) * file_weight
                percentage = int(base_percentage + current_file_contribution)
            else:
                percentage = int(base_percentage)
            
            self.progress_bar.setValue(percentage)
    
    def update_phase_progress(self, phase_name: str, phase_percent: int):
        """Update the current processing phase and its progress.
        
        Args:
            phase_name: Name of the current phase (e.g., "Downloading", "Transcribing", "Diarization")
            phase_percent: Progress within this phase (0-100)
        """
        self.current_phase = phase_name
        self.phase_progress = max(0, min(100, phase_percent))
        
        # Update phase label and progress bar
        self.phase_label.setText(f"Phase: {phase_name}")
        self.phase_progress_bar.setValue(self.phase_progress)
    
    def set_total_files(self, total: int):
        """Set or update the total number of files (for when total is determined later)."""
        self.total_files = total

        if total > 0:
            # Switch to determinate mode - always use 0-100 scale
            self.progress_bar.setMaximum(100)
            total_processed = self.completed_files + self.failed_files
            percentage = int((total_processed / total) * 100) if total > 0 else 0
            self.progress_bar.setValue(percentage)
            self._update_status()

    def _update_status(self, current_file: str = ""):
        """Update the status label with current file counts."""
        status_parts = []

        if self.total_files > 0:
            total_processed = self.completed_files + self.failed_files
            status_parts.append(
                f"Processing: {total_processed}/{self.total_files} files"
            )
        else:
            status_parts.append("Processing...")

        if self.completed_files > 0:
            status_parts.append(f"✅ {self.completed_files} completed")

        if self.failed_files > 0:
            status_parts.append(f"❌ {self.failed_files} failed")

        if current_file:
            status_parts.append(f"Current: {current_file[:40]}...")

        self.status_label.setText(" | ".join(status_parts))

    def finish(self, completed: int, failed: int):
        """Finish processing and show final results."""
        self.completed_files = completed
        self.failed_files = failed

        if failed == 0:
            self.title_label.setText("✅ Completed Successfully")
            self.title_label.setStyleSheet(
                "font-weight: bold; font-size: 13px; color: #4caf50;"
            )
        else:
            self.title_label.setText(f"⚠️ Completed with {failed} Failures")
            self.title_label.setStyleSheet(
                "font-weight: bold; font-size: 13px; color: #ff9800;"
            )

        # Set progress bar to 100%
        self.progress_bar.setValue(100)

        self._update_status()

    def reset(self):
        """Reset the progress bar to initial state."""
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0
        self.current_phase = "Initializing"
        self.phase_progress = 0

        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        
        self.phase_progress_bar.setValue(0)
        self.phase_label.setText("Phase: Initializing")

        self.title_label.setText("Processing...")
        self.title_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #ffffff;"
        )

        self.status_label.setText("Ready")

        self.hide()
