"""Base tab class for consistent tab interface and shared functionality."""

from typing import Dict, Any, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QLabel, QPushButton, QTextEdit, QMessageBox, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, QTimer

from ...config import get_settings
from ...logger import get_logger


class BaseTab(QWidget):
    """Base class for all GUI tabs with common functionality."""
    
    # Signals for communication with main window
    status_updated = pyqtSignal(str)
    log_message = pyqtSignal(str)
    processing_started = pyqtSignal()
    processing_finished = pyqtSignal()
    report_generated = pyqtSignal(str, str)  # report_type, report_path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_settings()
        self.logger = get_logger(self.__class__.__name__)
        self.active_workers = []
        self.current_report = None
        
        # Initialize UI
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup the UI for this tab. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _setup_ui()")
        
    def _connect_signals(self):
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
        self.stop_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
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
        self.report_btn.setEnabled(False)
        self.report_btn.setStyleSheet("background-color: #1976d2;")
        header_layout.addWidget(self.report_btn)
        
        layout.addLayout(header_layout)
        
        # Output text area with improved size policy for better resizing
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(200)
        # Use MinimumExpanding vertically to allow proper resizing during window resize
        self.output_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        layout.addWidget(self.output_text)
        
        return layout
        
    def _add_field_with_info(self, layout: QGridLayout, label_text: str, widget, 
                           tooltip: str, row: int, col: int):
        """Add a field with label and tooltip to a grid layout."""
        label = QLabel(label_text)
        label.setToolTip(tooltip)
        widget.setToolTip(tooltip)
        
        layout.addWidget(label, row, col)
        layout.addWidget(widget, row, col + 1)
        
    def append_log(self, message: str):
        """Append a message to the output log."""
        if hasattr(self, 'output_text'):
            self.output_text.append(message)
            self.output_text.repaint()
        self.log_message.emit(message)
        
    def clear_log(self):
        """Clear the output log."""
        if hasattr(self, 'output_text'):
            self.output_text.clear()
            
    def set_processing_state(self, processing: bool):
        """Set the processing state (enable/disable controls)."""
        if hasattr(self, 'start_btn'):
            self.start_btn.setEnabled(not processing)
        if hasattr(self, 'stop_btn'):
            self.stop_btn.setEnabled(processing)
        
        status_msg = "Processing..." if processing else "Ready"
        self.status_updated.emit(status_msg)
        
        if processing:
            self.processing_started.emit()
        else:
            self.processing_finished.emit()
            
    def show_error(self, title: str, message: str):
        """Show an error message box."""
        QMessageBox.critical(self, title, message)
        
    def show_warning(self, title: str, message: str):
        """Show a warning message box."""
        QMessageBox.warning(self, title, message)
        
    def show_info(self, title: str, message: str):
        """Show an info message box."""
        QMessageBox.information(self, title, message)
        
    def cleanup_workers(self):
        """Clean up any active worker threads."""
        for worker in self.active_workers:
            if worker.isRunning():
                worker.terminate()
                worker.wait(3000)  # Wait up to 3 seconds
        self.active_workers.clear()
        
    def _get_start_button_text(self) -> str:
        """Get the text for the start button. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _get_start_button_text()")
        
    def _start_processing(self):
        """Start the main processing operation. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _start_processing()")
        
    def _stop_processing(self):
        """Stop the current processing operation. Can be overridden by subclasses."""
        # Default implementation - stop all active workers
        for worker in self.active_workers:
            if worker.isRunning():
                if hasattr(worker, 'should_stop'):
                    worker.should_stop = True
                    self.append_log("⏹ Stopping processing...")
                elif hasattr(worker, 'stop'):
                    worker.stop()
                    self.append_log("⏹ Stopping processing...")
                else:
                    worker.terminate()
                    self.append_log("⏹ Force stopping processing...")
        
        # Reset UI state
        self.set_processing_state(False)
        
    def _view_last_report(self):
        """View the last generated report."""
        if self.current_report:
            try:
                import subprocess
                import platform
                
                if platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", self.current_report])
                elif platform.system() == "Windows":
                    subprocess.run(["start", self.current_report], shell=True)
                else:  # Linux
                    subprocess.run(["xdg-open", self.current_report])
            except Exception as e:
                self.show_error("Error", f"Failed to open report: {e}")
        else:
            self.show_info("No Report", "No report available yet.")
            
    def get_output_directory(self, default_path: str) -> Path:
        """Get the configured output directory or return default."""
        return Path(default_path)
        
    def validate_inputs(self) -> bool:
        """Validate inputs before processing. Can be overridden by subclasses."""
        return True 