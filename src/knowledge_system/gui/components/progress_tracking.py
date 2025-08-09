""" Progress tracking components for GUI operations."""

from typing import Any, Dict, Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ProgressTracker(QWidget):
    """ Widget for tracking operation progress with detailed information."""

    cancellation_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.is_visible = False
        self._setup_ui()

    def _setup_ui(self):
        """ Setup the progress tracking UI."""
        self.setFixedHeight(100)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Progress info layout
        info_layout = QHBoxLayout()

        # Status label
        self.status_label = QLabel("Ready")
        font = QFont()
        font.setBold(True)
        self.status_label.setFont(font)
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancellation_requested.emit)
        self.cancel_btn.setStyleSheet("background-color: #d32f2f;")
        self.cancel_btn.setVisible(False)
        info_layout.addWidget(self.cancel_btn)

        layout.addLayout(info_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Details label
        self.details_label = QLabel("")
        self.details_label.setStyleSheet("color: #888;")
        layout.addWidget(self.details_label)

        # Initially hide the widget
        self.hide()

    def set_progress(
        self, current: int, total: int, status: str = "", details: str = ""
    ):
        """ Update progress information."""
        if not self.is_visible:
            self.show()
            self.is_visible = True

        # Update progress bar
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.progress_bar.setVisible(True)

            # Update status with progress info
            if status:
                full_status = f"{status} ({current}/{total})"
            else:
                full_status = f"Processing ({current}/{total})"
        else:
            self.progress_bar.setVisible(False)
            full_status = status or "Processing..."

        self.status_label.setText(full_status)

        # Update details
        if details:
            self.details_label.setText(details)
            self.details_label.setVisible(True)
        else:
            self.details_label.setVisible(False)

        # Show cancel button during processing
        self.cancel_btn.setVisible(True)

    def set_indeterminate(self, status: str = "Processing...", details: str = ""):
        """ Set indeterminate progress (unknown total)."""
        if not self.is_visible:
            self.show()
            self.is_visible = True

        self.progress_bar.setMaximum(0)  # Indeterminate
        self.progress_bar.setVisible(True)
        self.status_label.setText(status)

        if details:
            self.details_label.setText(details)
            self.details_label.setVisible(True)
        else:
            self.details_label.setVisible(False)

        self.cancel_btn.setVisible(True)

    def finish(self, status: str = "Completed", show_for_seconds: int = 3):
        """ Finish progress and optionally hide after delay."""
        self.status_label.setText(status)
        self.progress_bar.setVisible(False)
        self.details_label.setVisible(False)
        self.cancel_btn.setVisible(False)

        if show_for_seconds > 0:
            QTimer.singleShot(show_for_seconds * 1000, self.reset)

    def reset(self):
        """ Reset and hide the progress tracker."""
        self.hide()
        self.is_visible = False
        self.status_label.setText("Ready")
        self.progress_bar.setVisible(False)
        self.details_label.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setValue(0)

    def set_error(self, error_message: str, show_for_seconds: int = 5):
        """ Show error state."""
        self.status_label.setText("Error")
        self.status_label.setStyleSheet("color: #d32f2f;")
        self.details_label.setText(error_message)
        self.details_label.setVisible(True)
        self.details_label.setStyleSheet("color: #d32f2f;")
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)

        if show_for_seconds > 0:
            QTimer.singleShot(show_for_seconds * 1000, self._reset_styles)

    def _reset_styles(self):
        """ Reset label styles and hide."""
        self.status_label.setStyleSheet("")
        self.details_label.setStyleSheet("color: #888;")
        self.reset()


class EnhancedProgressBar(QFrame):
    """ Enhanced progress bar widget with cancellation support."""

    cancellation_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet(
            """ QFrame {.

            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                margin: 5px;
            }
        """ ).
        )

        # Initially hide
        self.hide()

        # Setup UI
        self._setup_ui()

    def _setup_ui(self):
        """ Setup the enhanced progress bar UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Top row: status and cancel
        top_layout = QHBoxLayout()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        top_layout.addWidget(self.status_label)

        top_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancellation_requested.emit)
        self.cancel_btn.setStyleSheet(
            """ QPushButton {.

            QPushButton {
                background-color: #d32f2f;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
        """ ).

        )
        self.cancel_btn.hide()
        top_layout.addWidget(self.cancel_btn)

        layout.addLayout(top_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(
            """ QProgressBar {.

            QProgressBar {
                background-color: #3c3c3c;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 3px;
            }
        """ ).

        )
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Details label
        self.details_label = QLabel("")
        self.details_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        self.details_label.hide()
        layout.addWidget(self.details_label)

    def set_progress(
        self, current: int, total: int, status: str = "", details: str = ""
    ):
        """ Set progress with specific values."""
        self.show()

        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.progress_bar.show()

            full_status = (
                f"{status} - {percentage}%" if status else f"Progress - {percentage}%"
            )
        else:
            self.progress_bar.hide()
            full_status = status or "Processing..."

        self.status_label.setText(full_status)

        if details:
            self.details_label.setText(details)
            self.details_label.show()
        else:
            self.details_label.hide()

        self.cancel_btn.show()

    def set_indeterminate(self, status: str = "Processing...", details: str = ""):
        """ Set indeterminate progress."""
        self.show()
        self.progress_bar.setMaximum(0)
        self.progress_bar.show()
        self.status_label.setText(status)

        if details:
            self.details_label.setText(details)
            self.details_label.show()
        else:
            self.details_label.hide()

        self.cancel_btn.show()

    def finish(self, message: str = "Completed"):
        """ Finish progress display."""
        self.status_label.setText(message)
        self.progress_bar.hide()
        self.details_label.hide()
        self.cancel_btn.hide()

        # Auto-hide after 3 seconds
        QTimer.singleShot(3000, self.hide)

    def set_error(self, error_message: str):
        """ Show error state."""
        self.show()
        self.status_label.setText("Error occurred")
        self.status_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
        self.details_label.setText(error_message)
        self.details_label.setStyleSheet("color: #d32f2f;")
        self.details_label.show()
        self.progress_bar.hide()
        self.cancel_btn.hide()

        # Auto-hide after 5 seconds and reset styles
        QTimer.singleShot(5000, self._reset_error_state)

    def _reset_error_state(self):
        """ Reset error state styles and hide."""
        self.status_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        self.details_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        self.hide()

    def reset(self):
        """ Reset the progress bar to initial state."""
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        self.details_label.setText("")
        self.details_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self.details_label.hide()
        self.cancel_btn.hide()
        self.hide()
