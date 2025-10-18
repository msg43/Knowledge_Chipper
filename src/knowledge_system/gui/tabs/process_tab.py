"""Process pipeline tab for comprehensive file processing with transcription, summarization, and MOC generation."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QProcess, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ...logger import get_logger
from ..components.base_tab import BaseTab
from ..components.file_operations import FileOperationsMixin
from ..core.settings_manager import get_gui_settings_manager

logger = get_logger(__name__)


class ProcessPipelineWorker(QProcess):
    """QProcess-based worker for crash-isolated batch processing."""

    progress_updated = pyqtSignal(int, int, str)  # current, total, status
    file_completed = pyqtSignal(str, bool, str)  # file_path, success, message
    processing_finished = pyqtSignal(dict)  # final results
    processing_error = pyqtSignal(str)

    def __init__(self, files: Any, config: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.files = files
        self.config = config
        self.should_stop = False
        self.output_dir = None
        self.checkpoint_file = None

        # IPC communication
        from ...utils.ipc_communication import ProcessCommunicationManager

        self.comm_manager = ProcessCommunicationManager()

        # Setup communication callbacks
        self.comm_manager.register_progress_callback(self._handle_progress)
        self.comm_manager.register_file_complete_callback(self._handle_file_complete)
        self.comm_manager.register_error_callback(self._handle_error)
        self.comm_manager.register_finished_callback(self._handle_finished)
        self.comm_manager.register_message_callback(self._handle_message)

        # Connect QProcess signals
        self.readyReadStandardOutput.connect(self._read_stdout)
        self.readyReadStandardError.connect(self._read_stderr)
        self.finished.connect(self._handle_process_finished)
        self.errorOccurred.connect(self._handle_process_error)

        # Process management
        self.restart_attempts = 0
        self.max_restart_attempts = 3

    def _handle_progress(
        self,
        current_file: int,
        total_files: int,
        message: str,
        progress: int | None,
        stage: str,
    ):
        """Handle progress messages from worker process."""
        display_message = f"[{stage}] {message}"
        self.progress_updated.emit(current_file, total_files, display_message)

    def _handle_file_complete(self, file_path: str, success: bool, message: str):
        """Handle file completion messages from worker process."""
        self.file_completed.emit(file_path, success, message)

    def _handle_error(self, error_message: str):
        """Handle error messages from worker process."""
        self.processing_error.emit(error_message)

    def _handle_finished(self, results: dict):
        """Handle completion messages from worker process."""
        self.processing_finished.emit(results)

    def _handle_message(self, level: str, message: str):
        """Handle general messages from worker process."""
        logger.info(f"Worker {level}: {message}")

        # Forward important messages to UI
        if level in ["ERROR", "WARNING"]:
            self.processing_error.emit(f"{level}: {message}")

    def _read_stdout(self):
        """Read and process stdout from worker process."""
        while self.canReadLine():
            line = self.readLine().data().decode("utf-8").strip()
            if line:
                self.comm_manager.process_output_line(line)

    def _read_stderr(self):
        """Read stderr from worker process."""
        while self.canReadLine():
            line = self.readLine().data().decode("utf-8").strip()
            if line:
                logger.warning(f"Worker stderr: {line}")

    def _handle_process_finished(self, exit_code: int, exit_status):
        """Handle process completion."""
        if exit_code == 0:
            logger.info("Worker process completed successfully")
        else:
            error_msg = f"Worker process failed with exit code {exit_code}"
            logger.error(error_msg)

            # Attempt restart if configured
            if self.restart_attempts < self.max_restart_attempts:
                self.restart_attempts += 1
                delay = (
                    min(300, 2**self.restart_attempts) * 1000
                )  # Exponential backoff in ms
                logger.info(
                    f"Restarting worker process in {delay/1000}s (attempt {self.restart_attempts})"
                )
                QTimer.singleShot(delay, self._restart_processing)
            else:
                self.processing_error.emit(
                    f"Maximum restart attempts exceeded: {error_msg}"
                )

    def _handle_process_error(self, error):
        """Handle QProcess errors."""
        error_msg = f"Process error: {error}"
        logger.error(error_msg)
        self.processing_error.emit(error_msg)

    def _restart_processing(self):
        """Restart the processing with current configuration."""
        logger.info("Restarting worker process")
        self.start_processing()

    def _build_command(self) -> list:
        """Build command line for the batch processor."""
        import sys

        # Create temporary config file
        config_fd, config_path = tempfile.mkstemp(suffix=".json", prefix="kc_config_")
        try:
            with os.fdopen(config_fd, "w") as f:
                json.dump(self.config, f)
        except Exception:
            os.close(config_fd)
            raise

        # Create temporary checkpoint file if needed
        if not self.checkpoint_file:
            checkpoint_fd, self.checkpoint_file = tempfile.mkstemp(
                suffix=".json", prefix="kc_checkpoint_"
            )
            os.close(checkpoint_fd)

        # Build command
        cmd = (
            [
                sys.executable,
                "-m",
                "knowledge_system.workers.batch_processor_main",
                "--files",
            ]
            + [str(f) for f in self.files]
            + [
                "--config",
                config_path,
                "--output-dir",
                str(self.output_dir),
                "--checkpoint-file",
                str(self.checkpoint_file),
                "--log-level",
                "INFO",
            ]
        )

        return cmd

    def _prepare_environment(self) -> dict:
        """Prepare environment variables for the worker process."""
        env = os.environ.copy()

        # Add any specific environment variables needed
        env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent.parent)

        return env

    def set_output_directory(self, output_dir: str | Path):
        """Set the output directory for processing."""
        self.output_dir = Path(output_dir)

    def set_checkpoint_file(self, checkpoint_file: str | Path):
        """Set the checkpoint file path."""
        self.checkpoint_file = Path(checkpoint_file)

    def start_processing(self):
        """Start the batch processing in a separate process."""
        try:
            if not self.output_dir:
                raise ValueError("Output directory not set")

            cmd = self._build_command()
            self._prepare_environment()

            logger.info(f"Starting worker process with command: {' '.join(cmd[:5])}...")

            # Start heartbeat monitoring
            self.comm_manager.start_heartbeat_monitoring(
                timeout_callback=lambda: self.processing_error.emit(
                    "Worker process heartbeat timeout"
                )
            )

            # Start the process
            self.start(cmd[0], cmd[1:])

        except Exception as e:
            error_msg = f"Failed to start worker process: {e}"
            logger.error(error_msg)
            self.processing_error.emit(error_msg)

    def stop_processing(self):
        """Stop the processing pipeline (non-blocking)."""
        self.should_stop = True

        # Stop heartbeat monitoring
        self.comm_manager.stop_heartbeat_monitoring()

        # Terminate process gracefully
        if self.state() == QProcess.ProcessState.Running:
            logger.info("Terminating worker process")
            self.terminate()
            
            # Don't block on waitForFinished - QProcess will emit finished signal
            # when it's done, and the signal handler will clean up
            # The process will terminate in the background
            logger.info("Worker process termination initiated (non-blocking)")


class ProcessTab(BaseTab, FileOperationsMixin):
    """Tab for comprehensive file processing pipeline."""

    def __init__(self, parent: Any = None) -> None:
        # Initialize attributes before calling super() to prevent AttributeError
        self.processing_worker: ProcessPipelineWorker | None = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "Process Pipeline"

        # Now call super() which will call _setup_ui()
        super().__init__(parent)

        # Load settings after UI is set up
        self._load_settings()

    def _setup_ui(self) -> None:
        """Set up the user interface for the process tab."""
        layout = QVBoxLayout(self)

        # File selection section
        file_section = self._create_file_section()
        layout.addWidget(file_section)

        # Configuration section
        config_section = self._create_config_section()
        layout.addWidget(config_section)

        # Processing section
        processing_section = self._create_processing_section()
        layout.addWidget(processing_section)

        # Results section
        results_section = self._create_results_section()
        layout.addWidget(results_section)

    def _create_file_section(self) -> QGroupBox:
        """Create file selection section."""
        group = QGroupBox("File Selection")
        layout = QVBoxLayout(group)

        # File selection buttons
        button_layout = QHBoxLayout()

        self.add_files_btn = QPushButton("Add Files")
        self.add_files_btn.clicked.connect(self._add_files)
        button_layout.addWidget(self.add_files_btn)

        self.add_directory_btn = QPushButton("Add Directory")
        self.add_directory_btn.clicked.connect(self._add_directory)
        button_layout.addWidget(self.add_directory_btn)

        self.clear_files_btn = QPushButton("Clear All")
        self.clear_files_btn.clicked.connect(self._clear_files)
        button_layout.addWidget(self.clear_files_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # File list
        self.files_list = QListWidget()
        self.files_list.setMaximumHeight(150)
        layout.addWidget(self.files_list)

        return group

    def _create_config_section(self) -> QGroupBox:
        """Create configuration section."""
        group = QGroupBox("Processing Configuration")
        layout = QGridLayout(group)

        row = 0

        # Processing options
        self.transcribe_checkbox = QCheckBox("Transcribe Audio/Video")
        self.transcribe_checkbox.setChecked(True)
        layout.addWidget(self.transcribe_checkbox, row, 0)

        self.summarize_checkbox = QCheckBox("Summarize Content")
        self.summarize_checkbox.setChecked(True)
        layout.addWidget(self.summarize_checkbox, row, 1)

        self.moc_checkbox = QCheckBox("Generate MOC")
        self.moc_checkbox.setChecked(False)
        layout.addWidget(self.moc_checkbox, row, 2)
        row += 1

        # MOC Obsidian Pages checkbox (only enabled when MOC is enabled)
        self.moc_obsidian_pages_checkbox = QCheckBox("Write MOC Obsidian Pages")
        self.moc_obsidian_pages_checkbox.setChecked(False)
        self.moc_obsidian_pages_checkbox.setEnabled(False)
        self.moc_obsidian_pages_checkbox.setToolTip(
            "Generate People.md, Mental_Models.md, Jargon.md, and MOC.md files with dataview queries.\n"
            "These files contain dynamic Obsidian queries and can be copied to your vault."
        )
        layout.addWidget(self.moc_obsidian_pages_checkbox, row, 0, 1, 3)
        row += 1

        # Enable/disable MOC pages checkbox based on MOC checkbox
        self.moc_checkbox.toggled.connect(
            lambda checked: self.moc_obsidian_pages_checkbox.setEnabled(checked)
        )

        # Connect checkboxes to save settings
        self.transcribe_checkbox.toggled.connect(self._save_settings)
        self.summarize_checkbox.toggled.connect(self._save_settings)
        self.moc_checkbox.toggled.connect(self._save_settings)
        self.moc_obsidian_pages_checkbox.toggled.connect(self._save_settings)

        # Output directory
        layout.addWidget(QLabel("Output Directory:"), row, 0)
        self.output_dir_line = QLineEdit()
        layout.addWidget(self.output_dir_line, row, 1)

        self.output_dir_btn = QPushButton("Browse")
        self.output_dir_btn.clicked.connect(self._browse_output_dir)
        layout.addWidget(self.output_dir_btn, row, 2)

        # Connect output directory to save settings
        self.output_dir_line.textChanged.connect(self._save_settings)

        return group

    def _create_processing_section(self) -> QGroupBox:
        """Create processing control section."""
        group = QGroupBox("Processing Control")
        layout = QVBoxLayout(group)

        # Control buttons
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Processing")
        self.start_btn.clicked.connect(self._start_processing)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Processing")
        self.stop_btn.clicked.connect(self._stop_processing)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready to process files...")
        layout.addWidget(self.status_label)

        return group

    def _create_results_section(self) -> QGroupBox:
        """Create results display section."""
        group = QGroupBox("Processing Results")
        layout = QVBoxLayout(group)

        # Results display
        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(200)
        layout.addWidget(self.results_list)

        return group

    def _add_files(self) -> None:
        """Add files to processing list."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Process",
            "",
            "All Supported (*.mp3 *.wav *.m4a *.mp4 *.avi *.mkv *.pdf *.txt *.md *.docx *.doc *.rt *.html *.htm);;Audio Files (*.mp3 *.wav *.m4a);;Video Files (*.mp4 *.avi *.mkv);;Documents (*.pdf *.txt *.md *.docx *.doc *.rt *.html *.htm)",
        )

        for file_path in files:
            self.files_list.addItem(file_path)

    def _add_directory(self) -> None:
        """Add all supported files from a directory."""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", "")

        if directory:
            extensions = [
                ".mp3",
                ".wav",
                ".m4a",
                ".mp4",
                ".avi",
                ".mkv",
                ".pdf",
                ".txt",
                ".md",
                ".docx",
                ".doc",
                ".rt",
                ".html",
                ".htm",
            ]
            directory_path = Path(directory)

            for file_path in directory_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in extensions:
                    self.files_list.addItem(str(file_path))

    def _clear_files(self) -> None:
        """Clear all files from the list."""
        self.files_list.clear()

    def _browse_output_dir(self) -> None:
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", ""
        )

        if directory:
            self.output_dir_line.setText(directory)

    def _start_processing(self) -> None:
        """Start the processing pipeline."""
        try:
            # Validate inputs
            if self.files_list.count() == 0:
                self._show_error("No files selected for processing")
                return

            output_dir = self.output_dir_line.text().strip()
            if not output_dir:
                self._show_error("Please select an output directory")
                return

            # Get file list
            files = [
                self.files_list.item(i).text() for i in range(self.files_list.count())
            ]

            # Build configuration
            config = {
                "transcribe": self.transcribe_checkbox.isChecked(),
                "summarize": self.summarize_checkbox.isChecked(),
                "create_moc": self.moc_checkbox.isChecked(),
                "write_moc_obsidian_pages": self.moc_obsidian_pages_checkbox.isChecked(),
                "device": "cpu",  # Default for now
                "transcription_model": "base",  # Default for now
                "summarization_provider": "local",  # Use local LLM by default
                "summarization_model": "qwen2.5:7b-instruct",  # Default local model
                "moc_provider": "local",  # Use local LLM by default
                "moc_model": "qwen2.5:7b-instruct",  # Default local model
            }

            # Create and configure worker
            self.processing_worker = ProcessPipelineWorker(files, config, self)
            self.processing_worker.set_output_directory(output_dir)

            # Connect signals
            self.processing_worker.progress_updated.connect(self._update_progress)
            self.processing_worker.file_completed.connect(self._file_completed)
            self.processing_worker.processing_finished.connect(
                self._processing_finished
            )
            self.processing_worker.processing_error.connect(self._processing_error)

            # Update UI state
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setRange(0, len(files))
            self.progress_bar.setValue(0)
            self.status_label.setText("Starting processing...")
            self.results_list.clear()

            # Start processing
            self.processing_worker.start_processing()

        except Exception as e:
            self._show_error(f"Failed to start processing: {e}")

    def _stop_processing(self) -> None:
        """Stop the processing pipeline."""
        if self.processing_worker:
            self.processing_worker.stop_processing()
            self.processing_worker = None

        self._reset_ui_state()

    def _update_progress(self, current: int, total: int, message: str) -> None:
        """Update progress display."""
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"({current}/{total}) {message}")

    def _file_completed(self, file_path: str, success: bool, message: str) -> None:
        """Handle file completion."""
        status_icon = "✅" if success else "❌"
        filename = Path(file_path).name
        self.results_list.addItem(f"{status_icon} {filename}: {message}")

    def _processing_finished(self, results: dict) -> None:
        """Handle processing completion."""
        self._reset_ui_state()

        total_files = results.get("total_files", 0)
        files_processed = results.get("files_processed", 0)
        files_failed = results.get("files_failed", 0)

        self.status_label.setText(
            f"Processing completed: {files_processed}/{total_files} files processed, {files_failed} failed"
        )

        # Show completion message
        if files_failed == 0:
            self._show_info(
                f"Processing completed successfully!\n{files_processed} files processed."
            )
        else:
            self._show_warning(
                f"Processing completed with {files_failed} failures.\n{files_processed} files processed successfully."
            )

    def _processing_error(self, error_message: str) -> None:
        """Handle processing errors."""
        self._reset_ui_state()
        self.status_label.setText(f"Processing failed: {error_message}")
        self._show_error(f"Processing error: {error_message}")

    def _reset_ui_state(self) -> None:
        """Reset UI to initial state."""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(0)

    def _show_error(self, message: str) -> None:
        """Show error message."""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.critical(self, "Error", message)

    def _show_warning(self, message: str) -> None:
        """Show warning message."""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.warning(self, "Warning", message)

    def _show_info(self, message: str) -> None:
        """Show info message."""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.information(self, "Information", message)

    def _save_settings(self) -> None:
        """Save current settings to session."""
        try:
            # Save output directory
            self.gui_settings.set_output_directory(
                self.tab_name, self.output_dir_line.text()
            )

            # Save checkbox states
            self.gui_settings.set_checkbox_state(
                self.tab_name, "transcribe", self.transcribe_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "summarize", self.summarize_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "create_moc", self.moc_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "write_moc_obsidian_pages",
                self.moc_obsidian_pages_checkbox.isChecked(),
            )

            logger.debug(f"Settings saved for {self.tab_name} tab")

        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")

    def _load_settings(self) -> None:
        """Load settings from session."""
        try:
            # Load output directory
            output_dir = self.gui_settings.get_output_directory(self.tab_name, "")
            self.output_dir_line.setText(output_dir)

            # Load checkbox states
            self.transcribe_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(self.tab_name, "transcribe", True)
            )
            self.summarize_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(self.tab_name, "summarize", True)
            )
            self.moc_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(self.tab_name, "create_moc", False)
            )
            self.moc_obsidian_pages_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "write_moc_obsidian_pages", False
                )
            )

            # Update checkbox states based on dependencies
            self.moc_obsidian_pages_checkbox.setEnabled(self.moc_checkbox.isChecked())

            logger.debug(f"Settings loaded for {self.tab_name} tab")

        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")
