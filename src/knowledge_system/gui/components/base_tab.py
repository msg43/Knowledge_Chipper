"""Base tab class for consistent tab interface and shared functionality."""

from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
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
    QSizePolicy,
    QSpinBox,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...config import get_settings
from ...logger import get_logger
from ..assets.icons import get_app_icon


class BaseTab(QWidget):
    """Base class for all GUI tabs with common functionality."""

    # Signals for communication with main window
    status_updated = pyqtSignal(str)
    log_message = pyqtSignal(str)
    processing_started = pyqtSignal()
    processing_finished = pyqtSignal()
    report_generated = pyqtSignal(str, str)  # report_type, report_path

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.settings = get_settings()
        self.logger = get_logger(self.__class__.__name__)
        self.active_workers: list[Any] = []
        self.current_report = None

        # Initialize UI
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Setup the UI for this tab. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _setup_ui()")

    def _connect_signals(self) -> None:
        """Connect internal signals. Can be overridden by subclasses."""
        pass

    def _create_action_layout(self) -> QHBoxLayout:
        """Create a standard action button layout."""
        layout = QHBoxLayout()

        # Start button
        self.start_btn = QPushButton(self._get_start_button_text())
        self.start_btn.clicked.connect(self._start_processing)
        self.start_btn.setStyleSheet("background-color: #4caf50; font-weight: bold;")
        layout.addWidget(self.start_btn)

        # Stop button
        self.stop_btn = QPushButton("Stop Processing")
        self.stop_btn.clicked.connect(self._stop_processing)
        self.stop_btn.setStyleSheet(
            "background-color: #d32f2f; color: white; font-weight: bold;"
        )
        self.stop_btn.setEnabled(False)  # Initially disabled
        layout.addWidget(self.stop_btn)

        # Dry run checkbox
        self.dry_run_checkbox = QCheckBox("Dry run (test without processing)")
        layout.addWidget(self.dry_run_checkbox)

        layout.addStretch()
        return layout

    def _create_output_section(self) -> QVBoxLayout:
        """Create a standard output section with log display."""
        layout = QVBoxLayout()

        # Header with report button
        header_layout = QHBoxLayout()
        output_label = QLabel("Output:")
        header_layout.addWidget(output_label)
        header_layout.addStretch()

        self.report_btn = QPushButton("View Last Report")
        self.report_btn.clicked.connect(self._view_last_report)
        self.report_btn.setEnabled(
            True
        )  # Always enabled since we can find reports automatically
        self.report_btn.setStyleSheet("background-color: #1976d2;")
        header_layout.addWidget(self.report_btn)

        layout.addLayout(header_layout)

        # Output text area with responsive resizing behavior
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(
            150
        )  # Increased minimum height to prevent excessive compression
        # Remove maximum height constraint to allow expansion
        # Use Expanding vertical policy to grow/shrink with window
        self.output_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # Set stretch factor to ensure it gets priority in layout distribution
        layout.addWidget(
            self.output_text, 1
        )  # Give stretch factor to ensure proper expansion

        return layout

    def _add_field_with_info(
        self,
        layout: QGridLayout,
        label_text: str,
        widget: Any,
        tooltip: str,
        row: int,
        col: int,
    ) -> None:
        """Add a field with label and tooltip to a grid layout."""
        label = QLabel(label_text)
        label.setToolTip(tooltip)
        widget.setToolTip(tooltip)

        layout.addWidget(label, row, col)
        layout.addWidget(widget, row, col + 1)

    def append_log(self, message: str) -> None:
        """Append a message to the output log."""
        if hasattr(self, "output_text"):
            self.output_text.append(message)
            self.output_text.repaint()
        self.log_message.emit(message)

    def clear_log(self) -> None:
        """Clear the output log."""
        if hasattr(self, "output_text"):
            self.output_text.clear()

    def set_processing_state(self, processing: bool) -> None:
        """Set the processing state (enable/disable controls)."""
        if hasattr(self, "start_btn"):
            self.start_btn.setEnabled(not processing)
        if hasattr(self, "stop_btn"):
            self.stop_btn.setEnabled(processing)

        status_msg = "Processing..." if processing else "Ready"
        self.status_updated.emit(status_msg)

        if processing:
            self.processing_started.emit()
        else:
            self.processing_finished.emit()

    def show_error(self, title: str, message: str) -> None:
        """Show an error message box with custom icon."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

        # Set custom window icon
        custom_icon = get_app_icon()
        if custom_icon:
            msg_box.setWindowIcon(custom_icon)

        msg_box.exec()

    def show_warning(self, title: str, message: str) -> None:
        """Show a warning message box with custom icon."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

        # Set custom window icon
        custom_icon = get_app_icon()
        if custom_icon:
            msg_box.setWindowIcon(custom_icon)

        msg_box.exec()

    def show_info(self, title: str, message: str) -> None:
        """Show an info message box with custom icon."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

        # Set custom window icon
        custom_icon = get_app_icon()
        if custom_icon:
            msg_box.setWindowIcon(custom_icon)

        msg_box.exec()

    def cleanup_workers(self) -> None:
        """Clean up any active worker threads."""
        for worker in self.active_workers:
            if worker.isRunning():
                worker.terminate()
                worker.wait(3000)  # Wait up to 3 seconds
        self.active_workers.clear()

    def _get_start_button_text(self) -> str:
        """Get the text for the start button. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _get_start_button_text()")

    def _start_processing(self) -> None:
        """Start the main processing operation. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _start_processing()")

    def _stop_processing(self) -> None:
        """Stop the current processing operation. Can be overridden by subclasses."""
        # Default implementation - stop all active workers
        for worker in self.active_workers:
            if worker.isRunning():
                if hasattr(worker, "should_stop"):
                    worker.should_stop = True
                    self.append_log("⏹ Stopping processing...")
                elif hasattr(worker, "stop"):
                    worker.stop()
                    self.append_log("⏹ Stopping processing...")
                else:
                    worker.terminate()
                    self.append_log("⏹ Force stopping processing...")

        # Reset UI state
        self.set_processing_state(False)

    def _view_last_report(self) -> None:
        """View the last generated report."""
        # First try current_report if set
        report_path = self.current_report

        # If no current report, find the most recent report file
        if not report_path:
            report_path = self._find_latest_report()

        if report_path and Path(report_path).exists():
            try:
                import platform
                import subprocess

                if platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", str(report_path)])
                elif platform.system() == "Windows":
                    subprocess.run(["start", str(report_path)], shell=True)
                else:  # Linux
                    subprocess.run(["xdg-open", str(report_path)])

                self.append_log(f"📄 Opened report: {Path(report_path).name}")
            except Exception as e:
                self.show_error("Error", f"Failed to open report: {e}")
        else:
            self.show_info(
                "No Report",
                "No report available yet. Complete a processing operation to generate a report.",
            )

    def _find_latest_report(self) -> str | None:
        """Find the most recent report file for this tab type."""
        try:
            # Get the tab-specific report type
            tab_type = getattr(
                self, "tab_name", self.__class__.__name__.lower().replace("tab", "")
            )

            # Check standard report locations
            report_dirs = [
                Path.home() / ".knowledge_system" / "reports",
                Path("Reports"),
                Path("logs"),
            ]

            latest_report = None
            latest_time = 0.0

            for report_dir in report_dirs:
                if not report_dir.exists():
                    continue

                # Look for reports matching this tab type
                patterns = [
                    f"*{tab_type.lower()}*.md",
                    f"*{tab_type.lower()}*.txt",
                    f"*{tab_type.lower()}*.log",
                ]

                for pattern in patterns:
                    for report_file in report_dir.glob(pattern):
                        if report_file.is_file():
                            mtime = report_file.stat().st_mtime
                            if mtime > latest_time:
                                latest_time = mtime
                                latest_report = str(report_file)

            return latest_report
        except Exception as e:
            self.logger.error(f"Error finding latest report: {e}")
            return None

    def get_output_directory(self, default_path: str) -> Path:
        """Get the configured output directory or return default."""
        return Path(default_path)

    def validate_inputs(self) -> bool:
        """Validate inputs before processing. Can be overridden by subclasses."""
        return True
