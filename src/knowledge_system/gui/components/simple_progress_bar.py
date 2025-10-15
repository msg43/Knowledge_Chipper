"""
Simple, reliable progress bar component for transcription operations.
Clean implementation focused on clarity and proper percentage display.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class SimpleTranscriptionProgressBar(QFrame):
    """
    Simple, reliable progress bar for transcription operations.
    Focuses on clear percentage display and accurate progress tracking.
    """

    # Signals
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0

        self._setup_ui()

        # Hide initially
        self.hide()

    def _setup_ui(self):
        """Setup the simple UI with clear progress display."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Title bar with cancel button
        title_layout = QHBoxLayout()

        self.title_label = QLabel("Processing...")
        self.title_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #ffffff;"
        )
        title_layout.addWidget(self.title_label)

        title_layout.addStretch()

        self.cancel_btn = QPushButton("⏹ Cancel")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        self.cancel_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """
        )
        title_layout.addWidget(self.cancel_btn)

        layout.addLayout(title_layout)

        # Progress bar with percentage
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
            # Determinate mode
            self.progress_bar.setMaximum(total_files)
            self.progress_bar.setValue(0)
        else:
            # Indeterminate mode
            self.progress_bar.setMaximum(0)
            self.progress_bar.setValue(0)

        self._update_status()
        self.show()

        print(
            f"🔍 [SimpleProgressBar] Started: total={total_files}, mode={'determinate' if total_files > 0 else 'indeterminate'}"
        )

    def update_progress(self, completed: int, failed: int, current_file: str = ""):
        """Update progress with completed and failed counts."""
        self.completed_files = completed
        self.failed_files = failed

        total_processed = completed + failed

        # Update progress bar value
        if self.total_files > 0:
            self.progress_bar.setValue(total_processed)

        # Update status text
        self._update_status(current_file)

        # Calculate percentage for logging
        percentage = (
            int((total_processed / self.total_files) * 100)
            if self.total_files > 0
            else 0
        )
        print(
            f"🔍 [SimpleProgressBar] Updated: {total_processed}/{self.total_files} = {percentage}% (completed={completed}, failed={failed})"
        )

    def set_total_files(self, total: int):
        """Set or update the total number of files (for when total is determined later)."""
        self.total_files = total

        if total > 0:
            # Switch to determinate mode
            self.progress_bar.setMaximum(total)
            total_processed = self.completed_files + self.failed_files
            self.progress_bar.setValue(total_processed)
            self._update_status()
            print(
                f"🔍 [SimpleProgressBar] Total set: {total}, switching to determinate mode"
            )

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
        if self.total_files > 0:
            self.progress_bar.setValue(self.total_files)

        self._update_status()
        self.cancel_btn.hide()

        print(f"🔍 [SimpleProgressBar] Finished: completed={completed}, failed={failed}")

    def reset(self):
        """Reset the progress bar to initial state."""
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0

        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)

        self.title_label.setText("Processing...")
        self.title_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #ffffff;"
        )

        self.status_label.setText("Ready")
        self.cancel_btn.show()

        self.hide()

        print("🔍 [SimpleProgressBar] Reset")
