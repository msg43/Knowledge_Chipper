"""Base tab class for consistent tab interface and shared functionality."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
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
        """Add a field with label and enhanced tooltip to a grid layout."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QHBoxLayout

        # Create label with enhanced tooltip formatting
        label = QLabel(label_text)

        # Format tooltip for better readability
        formatted_tooltip = (
            f"<b>{label_text}</b><br/><br/>{tooltip.replace(chr(10), '<br/>')}"
        )

        label.setToolTip(formatted_tooltip)
        widget.setToolTip(formatted_tooltip)

        # Create a horizontal layout for the widget + info indicator
        widget_layout = QHBoxLayout()
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.setSpacing(8)

        # Add the main widget
        widget_layout.addWidget(widget)

        # Create a small, subtle info indicator using text
        info_label = QLabel("ⓘ")
        info_label.setFixedSize(16, 16)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setToolTip(formatted_tooltip)
        info_label.setStyleSheet(
            """
            QLabel {
                color: #007AFF;
                font-size: 12px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                color: #0051D5;
            }
        """
        )

        widget_layout.addWidget(info_label)
        widget_layout.addStretch()  # Push everything to the left

        # Create a container widget for the layout
        widget_container = QWidget()
        widget_container.setLayout(widget_layout)

        layout.addWidget(label, row, col)
        layout.addWidget(widget_container, row, col + 1)

    def append_log(self, message: str, force_update: bool = True) -> None:
        """Append a message to the output log with immediate GUI update."""
        if hasattr(self, "output_text"):
            self.output_text.append(message)
            
            if force_update:
                # Force immediate GUI update and scroll to bottom
                self.output_text.repaint()
                self.output_text.ensureCursorVisible()
                # Process events multiple times to ensure immediate visual update
                from PyQt6.QtWidgets import QApplication

                # Process events immediately to update GUI
                QApplication.processEvents()
                # Force another repaint cycle
                self.output_text.update()
                # Process events again for any pending redraws
                QApplication.processEvents()

        self.log_message.emit(message)

        if force_update:
            # Process events one more time after signal emission
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

    def update_last_log_line(self, message: str) -> None:
        """Update the last line in the output log instead of adding a new line."""
        if hasattr(self, "output_text"):
            # Get current content and remove the last line
            current_content = self.output_text.toPlainText()
            lines = current_content.split('\n')
            if lines:
                lines[-1] = message  # Replace last line
                self.output_text.setPlainText('\n'.join(lines))
            else:
                self.output_text.setPlainText(message)
            
            # Force immediate GUI update and scroll to bottom
            self.output_text.repaint()
            self.output_text.ensureCursorVisible()
            # Process events for immediate visual update
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

    def clear_log(self) -> None:
        """Clear the output log."""
        if hasattr(self, "output_text"):
            self.output_text.clear()

    def async_validate_directory(
        self,
        directory_path: str,
        callback: callable,
        check_writable: bool = False,
        check_parent: bool = False,
    ) -> None:
        """Asynchronously validate directory to prevent GUI blocking on slow filesystems."""
        from PyQt6.QtCore import QThread, pyqtSignal

        class DirectoryValidationWorker(QThread):
            """Worker thread for directory validation without blocking GUI."""

            validation_completed = pyqtSignal(
                bool, str, str
            )  # valid, path, error_message

            def __init__(
                self,
                directory_path: str,
                check_writable: bool = False,
                check_parent: bool = False,
            ):
                super().__init__()
                self.directory_path = directory_path
                self.check_writable = check_writable
                self.check_parent = check_parent

            def run(self):
                """Validate directory asynchronously."""
                try:
                    import os
                    from pathlib import Path

                    path = Path(self.directory_path)

                    # Check if path exists
                    if not path.exists():
                        self.validation_completed.emit(
                            False,
                            self.directory_path,
                            f"Directory does not exist: {self.directory_path}",
                        )
                        return

                    # Check if it's a directory
                    if not path.is_dir():
                        self.validation_completed.emit(
                            False,
                            self.directory_path,
                            f"Path is not a directory: {self.directory_path}",
                        )
                        return

                    # Check if parent exists (if requested)
                    if self.check_parent and not path.parent.exists():
                        self.validation_completed.emit(
                            False,
                            self.directory_path,
                            f"Parent directory does not exist: {path.parent}",
                        )
                        return

                    # Check if writable (if requested)
                    if self.check_writable and not os.access(path, os.W_OK):
                        self.validation_completed.emit(
                            False,
                            self.directory_path,
                            f"Directory is not writable: {self.directory_path}",
                        )
                        return

                    # All checks passed
                    self.validation_completed.emit(True, self.directory_path, "")

                except Exception as e:
                    self.validation_completed.emit(
                        False, self.directory_path, f"Validation error: {str(e)}"
                    )

        # Create and start worker
        worker = DirectoryValidationWorker(directory_path, check_writable, check_parent)
        worker.validation_completed.connect(
            lambda valid, path, error: self._handle_directory_validation(
                valid, path, error, callback, worker
            )
        )
        worker.start()

    def _handle_directory_validation(
        self,
        valid: bool,
        path: str,
        error_message: str,
        callback: callable,
        worker: "QThread",
    ) -> None:
        """Handle directory validation result."""
        try:
            # Call the provided callback with results
            callback(valid, path, error_message)
        finally:
            # Clean up worker
            worker.deleteLater()

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
        """View the last generated report asynchronously."""
        # First try current_report if set
        report_path = self.current_report

        if report_path and Path(report_path).exists():
            self._open_report_file(report_path)
        else:
            # Find the most recent report file asynchronously
            self.append_log("🔍 Searching for latest report...")
            self._async_find_and_open_latest_report()

    def _async_find_and_open_latest_report(self) -> None:
        """Asynchronously find and open the latest report to prevent GUI blocking."""
        from PyQt6.QtCore import QThread, pyqtSignal

        class ReportSearchWorker(QThread):
            """Worker thread for searching report files without blocking GUI."""

            search_completed = pyqtSignal(
                str
            )  # report_path (empty string if none found)
            search_error = pyqtSignal(str)  # error_message

            def __init__(self, tab_type: str):
                super().__init__()
                self.tab_type = tab_type

            def run(self):
                """Search for the latest report file."""
                try:
                    from pathlib import Path

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
                            f"*{self.tab_type.lower()}*.md",
                            f"*{self.tab_type.lower()}*.txt",
                            f"*{self.tab_type.lower()}*.log",
                        ]

                        for pattern in patterns:
                            for report_file in report_dir.glob(pattern):
                                if report_file.is_file():
                                    mtime = report_file.stat().st_mtime
                                    if mtime > latest_time:
                                        latest_time = mtime
                                        latest_report = str(report_file)

                    self.search_completed.emit(latest_report or "")
                except Exception as e:
                    self.search_error.emit(str(e))

        # Get tab type
        tab_type = getattr(
            self, "tab_name", self.__class__.__name__.lower().replace("tab", "")
        )

        # Create and start worker
        self._report_search_worker = ReportSearchWorker(tab_type)
        self._report_search_worker.search_completed.connect(
            self._handle_report_search_result
        )
        self._report_search_worker.search_error.connect(
            self._handle_report_search_error
        )
        self._report_search_worker.start()

    def _handle_report_search_result(self, report_path: str) -> None:
        """Handle report search result."""
        try:
            if report_path:
                self.append_log(f"📄 Found latest report: {Path(report_path).name}")
                self._open_report_file(report_path)
            else:
                self.append_log("❌ No recent reports found")
                self.show_warning(
                    "No Reports Found",
                    f"No recent reports found for {getattr(self, 'tab_name', 'this tab')}.\n\n"
                    "Reports are generated after processing operations complete.",
                )
        finally:
            # Clean up worker
            if hasattr(self, "_report_search_worker"):
                self._report_search_worker.deleteLater()
                del self._report_search_worker

    def _handle_report_search_error(self, error_message: str) -> None:
        """Handle report search error."""
        self.append_log(f"❌ Error searching for reports: {error_message}")
        self.show_error(
            "Report Search Error", f"Error searching for reports: {error_message}"
        )

        # Clean up worker
        if hasattr(self, "_report_search_worker"):
            self._report_search_worker.deleteLater()
            del self._report_search_worker

    def _open_report_file(self, report_path: str) -> None:
        """Open a report file using the system default application."""
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

    def async_open_file(self, file_path: str, file_description: str = "file") -> None:
        """Asynchronously open a file with the system default application to prevent GUI blocking."""
        from PyQt6.QtCore import QThread, pyqtSignal

        class FileOpenWorker(QThread):
            """Worker thread for opening files without blocking GUI."""

            open_completed = pyqtSignal(
                bool, str, str
            )  # success, file_path, error_message

            def __init__(self, file_path: str):
                super().__init__()
                self.file_path = file_path

            def run(self):
                """Open file asynchronously."""
                try:
                    import platform
                    import subprocess
                    from pathlib import Path

                    path = Path(self.file_path)

                    # Check if file exists
                    if not path.exists():
                        self.open_completed.emit(
                            False, self.file_path, f"File not found: {self.file_path}"
                        )
                        return

                    # Open with platform-specific command
                    if platform.system() == "Darwin":  # macOS
                        subprocess.run(["open", str(path)], check=False)
                    elif platform.system() == "Windows":
                        subprocess.run(["start", str(path)], shell=True, check=False)
                    else:  # Linux
                        subprocess.run(["xdg-open", str(path)], check=False)

                    self.open_completed.emit(True, self.file_path, "")

                except Exception as e:
                    self.open_completed.emit(False, self.file_path, str(e))

        # Create and start worker
        worker = FileOpenWorker(file_path)
        worker.open_completed.connect(
            lambda success, path, error: self._handle_file_open_result(
                success, path, error, file_description, worker
            )
        )
        worker.start()

    def _handle_file_open_result(
        self,
        success: bool,
        file_path: str,
        error_message: str,
        file_description: str,
        worker: "QThread",
    ) -> None:
        """Handle file opening result."""
        try:
            if success:
                self.append_log(f"📄 Opened {file_description}: {Path(file_path).name}")
            else:
                self.append_log(
                    f"❌ Failed to open {file_description}: {error_message}"
                )
                if "not found" in error_message.lower():
                    self.show_error("File Not Found", error_message)
                else:
                    self.show_error(
                        "Open Error",
                        f"Failed to open {file_description}: {error_message}",
                    )
        finally:
            # Clean up worker
            worker.deleteLater()

    def get_output_directory(self, default_path: str) -> Path:
        """Get the configured output directory or return default."""
        return Path(default_path)

    def validate_inputs(self) -> bool:
        """Validate inputs before processing. Can be overridden by subclasses."""
        return True
