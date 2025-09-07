"""Enhanced progress display component for transcription operations."""

import time
from typing import Any, Dict, Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class TranscriptionProgressDisplay(QFrame):
    """Enhanced progress display for transcription operations with detailed feedback."""

    cancellation_requested = pyqtSignal()
    retry_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(160)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet(
            """
            QFrame {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin: 5px;
            }
        """
        )

        # Progress tracking data
        self.start_time = None
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0
        self.current_file = ""
        self.operation_type = ""

        # Hide initially
        self.hide()

        # Setup UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the enhanced progress display UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # Top section: Operation header and controls
        header_layout = QHBoxLayout()

        # Operation title and status
        self.operation_label = QLabel("Transcription Progress")
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.operation_label.setFont(font)
        self.operation_label.setStyleSheet("color: #2c3e50;")
        header_layout.addWidget(self.operation_label)

        header_layout.addStretch()

        # Control buttons
        self.retry_btn = QPushButton("🔄 Retry Failed")
        self.retry_btn.clicked.connect(self.retry_requested.emit)
        self.retry_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """
        )
        self.retry_btn.hide()
        header_layout.addWidget(self.retry_btn)

        self.cancel_btn = QPushButton("⏹ Cancel")
        self.cancel_btn.clicked.connect(self.cancellation_requested.emit)
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
        self.cancel_btn.hide()
        header_layout.addWidget(self.cancel_btn)

        layout.addLayout(header_layout)

        # Progress bar section
        progress_layout = QVBoxLayout()

        # Main progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                text-align: center;
                font-weight: bold;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 4px;
            }
        """
        )
        progress_layout.addWidget(self.progress_bar)

        # Status and ETA info
        info_layout = QHBoxLayout()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #34495e; font-weight: bold;")
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()

        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        info_layout.addWidget(self.eta_label)

        progress_layout.addLayout(info_layout)
        layout.addLayout(progress_layout)

        # Statistics grid
        stats_layout = QGridLayout()

        # Files statistics
        self.total_files_label = QLabel("Total: 0")
        self.total_files_label.setStyleSheet("color: #34495e; font-weight: bold;")
        stats_layout.addWidget(QLabel("📁"), 0, 0)
        stats_layout.addWidget(self.total_files_label, 0, 1)

        self.completed_files_label = QLabel("✅ Completed: 0")
        self.completed_files_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        stats_layout.addWidget(self.completed_files_label, 0, 2)

        self.failed_files_label = QLabel("❌ Failed: 0")
        self.failed_files_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        stats_layout.addWidget(self.failed_files_label, 0, 3)

        # Current operation info
        self.current_file_label = QLabel("Current: None")
        self.current_file_label.setStyleSheet("color: #2c3e50;")
        stats_layout.addWidget(QLabel("🎤"), 1, 0)
        stats_layout.addWidget(self.current_file_label, 1, 1, 1, 3)

        layout.addLayout(stats_layout)

    def start_operation(
        self, operation_type: str, total_files: int, title: str | None = None
    ) -> None:
        """Start a new transcription operation."""
        self.operation_type = operation_type
        self.total_files = total_files
        self.completed_files = 0
        self.failed_files = 0
        self.current_file = ""
        self.start_time = time.time()

        # Update UI
        display_title = title or f"{operation_type.title()} Progress"
        self.operation_label.setText(display_title)

        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)

        self._update_statistics()
        self._update_status("Starting...")

        # Show controls
        self.cancel_btn.show()
        self.retry_btn.hide()

        # Show the widget
        self.show()

    def update_progress(
        self,
        completed: int,
        failed: int,
        current_file: str = "",
        current_status: str = "",
        step_progress: int = 0,
    ) -> None:
        """Update progress with current statistics."""
        self.completed_files = completed
        self.failed_files = failed
        self.current_file = current_file

        total_processed = completed + failed
        self.progress_bar.setValue(total_processed)

        # Update current status
        if current_file and current_status:
            display_status = f"{current_status}: {current_file}"
            if step_progress > 0:
                display_status += f" ({step_progress}%)"
        elif current_status:
            display_status = current_status
        else:
            display_status = (
                f"Processing file {total_processed + 1} of {self.total_files}"
            )

        self._update_status(display_status)
        self._update_statistics()
        self._update_eta()

    def set_current_step(self, step_description: str, step_progress: int = 0) -> None:
        """Update the current step being performed."""
        if step_progress > 0:
            status = f"{step_description} ({step_progress}%)"
        else:
            status = step_description
        self._update_status(status)

    def complete_operation(self, success_count: int, failure_count: int) -> None:
        """Complete the operation and show final results."""
        self.completed_files = success_count
        self.failed_files = failure_count

        # Update final status
        if failure_count == 0:
            self._update_status(
                f"✅ Completed! All {success_count} files processed successfully"
            )
            self.operation_label.setText("✅ Transcription Complete")
            self.operation_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self._update_status(
                f"⚠️ Completed with {failure_count} failed out of {success_count + failure_count} files"
            )
            self.operation_label.setText("⚠️ Transcription Complete (with failures)")
            self.operation_label.setStyleSheet("color: #f39c12; font-weight: bold;")

            # Show retry button if there were failures
            self.retry_btn.show()

        # Hide cancel button, update statistics
        self.cancel_btn.hide()
        self._update_statistics()
        self.eta_label.setText("")

        # Auto-hide after delay if no failures
        if failure_count == 0:
            QTimer.singleShot(5000, self.hide)

    def set_error(self, error_message: str) -> None:
        """Show error state with detailed message."""
        self.operation_label.setText("❌ Transcription Error")
        self.operation_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self._update_status(f"Error: {error_message}")

        # Show retry button
        self.retry_btn.show()
        self.cancel_btn.hide()

        self.eta_label.setText("")

    def _update_status(self, status: str) -> None:
        """Update the status label."""
        self.status_label.setText(status)

    def _update_statistics(self) -> None:
        """Update the statistics display."""
        self.total_files_label.setText(f"Total: {self.total_files}")
        self.completed_files_label.setText(f"✅ Completed: {self.completed_files}")
        self.failed_files_label.setText(f"❌ Failed: {self.failed_files}")

        if self.current_file:
            display_name = self.current_file
            if len(display_name) > 40:
                display_name = "..." + display_name[-37:]
            self.current_file_label.setText(f"Current: {display_name}")
        else:
            self.current_file_label.setText("Current: None")

    def _update_eta(self) -> None:
        """Update the ETA display."""
        if not self.start_time or self.completed_files == 0:
            return

        elapsed = time.time() - self.start_time
        processed = self.completed_files + self.failed_files

        if processed > 0:
            avg_time_per_file = elapsed / processed
            remaining_files = self.total_files - processed
            eta_seconds = avg_time_per_file * remaining_files

            if eta_seconds > 60:
                eta_minutes = int(eta_seconds // 60)
                eta_secs = int(eta_seconds % 60)
                eta_text = f"ETA: ~{eta_minutes}m {eta_secs}s"
            else:
                eta_text = f"ETA: ~{int(eta_seconds)}s"

            # Add speed information
            files_per_minute = (processed / elapsed) * 60 if elapsed > 0 else 0
            eta_text += f" ({files_per_minute:.1f} files/min)"

            self.eta_label.setText(eta_text)

    def reset(self) -> None:
        """Reset the progress display to initial state."""
        self.hide()
        self.operation_label.setText("Transcription Progress")
        self.operation_label.setStyleSheet("color: #2c3e50; font-weight: bold;")
        self.status_label.setText("Ready")
        self.eta_label.setText("")
        self.progress_bar.setValue(0)
        self.cancel_btn.hide()
        self.retry_btn.hide()

        # Reset tracking data
        self.start_time = None
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0
        self.current_file = ""
        self.operation_type = ""


class CloudTranscriptionStatusDisplay(QFrame):
    """Specialized status display for cloud transcription operations."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Just enough height for a progress bar
        self.setFixedHeight(30)
        # Remove all frame styling - no blue box, no borders
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet("")  # No background styling

        self.hide()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup ONLY a blue progress bar - no text, no labels, no clutter."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)  # Minimal margins
        layout.setSpacing(0)

        # ONLY the blue progress bar - nothing else
        self.cloud_progress = QProgressBar()
        self.cloud_progress.setStyleSheet(
            """
            QProgressBar {
                background-color: #ffffff;
                border: 1px solid #3498db;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """
        )
        layout.addWidget(self.cloud_progress)

    def update_cloud_status(
        self,
        current_url: int,
        total_urls: int,
        current_operation: str,
        api_status: str = "",
    ) -> None:
        """Update ONLY the progress bar - no text updates."""
        self.show()

        # Update ONLY the progress bar
        if total_urls > 0:
            self.cloud_progress.setMaximum(total_urls)
            self.cloud_progress.setValue(current_url)
        else:
            self.cloud_progress.setMaximum(0)  # Indeterminate

    def set_connection_status(self, connected: bool, message: str = "") -> None:
        """No-op - only showing progress bar."""
        pass

    def set_error(self, error_message: str) -> None:
        """Show error by hiding the progress bar."""
        self.hide()

    def complete(self, success_count: int, failure_count: int) -> None:
        """Complete - set progress to 100% then auto-hide."""
        self.cloud_progress.setValue(self.cloud_progress.maximum())
        # Auto-hide after delay
        QTimer.singleShot(3000, self.hide)

    def reset(self) -> None:
        """Reset to initial state."""
        self.hide()
        self.cloud_progress.setValue(0)
