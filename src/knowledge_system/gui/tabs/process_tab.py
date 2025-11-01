"""Process pipeline tab for comprehensive file processing with transcription, summarization, and MOC generation."""

import asyncio
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal
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

from ...core.system2_orchestrator import System2Orchestrator
from ...logger import get_logger
from ...processors.audio_processor import AudioProcessor
from ..components.base_tab import BaseTab
from ..components.file_operations import FileOperationsMixin
from ..core.settings_manager import get_gui_settings_manager

logger = get_logger(__name__)


class ProcessPipelineWorker(QThread):
    """Thread-based worker for batch processing using System2Orchestrator."""

    progress_updated = pyqtSignal(int, int, str)  # current, total, status
    file_completed = pyqtSignal(str, bool, str)  # file_path, success, message
    processing_finished = pyqtSignal(dict)  # final results
    processing_error = pyqtSignal(str)

    def __init__(
        self, files: list[str], config: dict[str, Any], parent: Any = None
    ) -> None:
        super().__init__(parent)
        self.files = files
        self.config = config
        self.should_stop = False
        self.output_dir = None

        # Processing state
        self.files_processed = 0
        self.files_failed = 0
        self.successful_files = []
        self.failed_files = []

    def set_output_directory(self, output_dir: str | Path):
        """Set the output directory for processing."""
        self.output_dir = Path(output_dir)

    def run(self) -> None:
        """Execute the processing pipeline."""
        try:
            if not self.output_dir:
                self.processing_error.emit("Output directory not set")
                return

            total_files = len(self.files)
            logger.info(f"Starting batch processing of {total_files} files")

            self.progress_updated.emit(0, total_files, "Initializing...")

            # Process each file sequentially
            for idx, file_path in enumerate(self.files, 1):
                if self.should_stop:
                    logger.info("Processing stopped by user")
                    break

                file_obj = Path(file_path)
                logger.info(f"Processing file {idx}/{total_files}: {file_obj.name}")
                self.progress_updated.emit(
                    idx - 1, total_files, f"Processing {file_obj.name}..."
                )

                try:
                    # Determine file type and process accordingly
                    if file_obj.suffix.lower() in [
                        ".mp3",
                        ".wav",
                        ".m4a",
                        ".mp4",
                        ".avi",
                        ".mkv",
                    ]:
                        success = self._process_audio_video(file_path)
                    elif file_obj.suffix.lower() in [
                        ".pdf",
                        ".txt",
                        ".md",
                        ".docx",
                        ".doc",
                        ".rtf",
                        ".html",
                        ".htm",
                    ]:
                        success = self._process_document(file_path)
                    else:
                        self.file_completed.emit(
                            file_path,
                            False,
                            f"Unsupported file type: {file_obj.suffix}",
                        )
                        self.files_failed += 1
                        self.failed_files.append((file_path, f"Unsupported file type"))
                        continue

                    if success:
                        self.files_processed += 1
                        self.successful_files.append(file_path)
                        self.file_completed.emit(
                            file_path, True, "Completed successfully"
                        )
                    else:
                        self.files_failed += 1
                        self.failed_files.append((file_path, "Processing failed"))
                        self.file_completed.emit(file_path, False, "Processing failed")

                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    self.files_failed += 1
                    self.failed_files.append((file_path, str(e)))
                    self.file_completed.emit(file_path, False, str(e))

            # Emit final results
            results = {
                "total_files": total_files,
                "files_processed": self.files_processed,
                "files_failed": self.files_failed,
                "successful_files": self.successful_files,
                "failed_files": self.failed_files,
            }
            self.processing_finished.emit(results)

        except Exception as e:
            logger.error(f"Processing pipeline error: {e}")
            self.processing_error.emit(str(e))

    def _process_audio_video(self, file_path: str) -> bool:
        """Process audio/video files through transcription and optional summarization."""
        try:
            file_obj = Path(file_path)

            # Step 1: Transcription (if enabled)
            transcript_path = None
            if self.config.get("transcribe", True):
                self.progress_updated.emit(
                    self.files_processed,
                    len(self.files),
                    f"Transcribing {file_obj.name}...",
                )

                audio_processor = AudioProcessor(
                    device=self.config.get("device", "cpu"),
                    model=self.config.get("transcription_model", "medium"),
                )

                result = audio_processor.process(
                    file_path, output_dir=str(self.output_dir)
                )

                if not result.success:
                    logger.error(f"Transcription failed: {result.errors}")
                    return False

                transcript_path = result.output_file
                logger.info(f"Transcription completed: {transcript_path}")

            # Step 2: Summarization (if enabled and we have a transcript)
            if self.config.get("summarize", False) and transcript_path:
                self.progress_updated.emit(
                    self.files_processed,
                    len(self.files),
                    f"Summarizing {file_obj.name}...",
                )

                # Use System2Orchestrator for mining/summarization
                orchestrator = System2Orchestrator()
                source_id = file_obj.stem

                job_id = orchestrator.create_job(
                    job_type="mine",
                    input_id=source_id,
                    config={
                        "source": "process_tab",
                        "file_path": str(transcript_path),
                        "output_dir": str(self.output_dir),
                        "miner_model": f"{self.config.get('summarization_provider', 'local')}:{self.config.get('summarization_model', 'qwen2.5:7b-instruct')}",
                    },
                    auto_process=False,
                )

                # Execute synchronously
                result = asyncio.run(orchestrator.process_job(job_id))

                if result.get("status") != "succeeded":
                    logger.error(f"Summarization failed: {result.get('error_message')}")
                    return False

                logger.info(f"Summarization completed for {file_obj.name}")

            return True

        except Exception as e:
            logger.error(f"Error processing audio/video {file_path}: {e}")
            return False

    def _process_document(self, file_path: str) -> bool:
        """Process documents through summarization."""
        try:
            file_obj = Path(file_path)

            if self.config.get("summarize", False):
                self.progress_updated.emit(
                    self.files_processed,
                    len(self.files),
                    f"Summarizing {file_obj.name}...",
                )

                # Use System2Orchestrator for mining/summarization
                orchestrator = System2Orchestrator()
                source_id = file_obj.stem

                job_id = orchestrator.create_job(
                    job_type="mine",
                    input_id=source_id,
                    config={
                        "source": "process_tab",
                        "file_path": str(file_path),
                        "output_dir": str(self.output_dir),
                        "miner_model": f"{self.config.get('summarization_provider', 'local')}:{self.config.get('summarization_model', 'qwen2.5:7b-instruct')}",
                    },
                    auto_process=False,
                )

                # Execute synchronously
                result = asyncio.run(orchestrator.process_job(job_id))

                if result.get("status") != "succeeded":
                    logger.error(f"Summarization failed: {result.get('error_message')}")
                    return False

                logger.info(f"Summarization completed for {file_obj.name}")

            return True

        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            return False

    def stop_processing(self):
        """Stop the processing pipeline."""
        self.should_stop = True
        logger.info("Stop requested for processing pipeline")


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
        # Don't set default - let _load_settings() handle it via settings manager
        layout.addWidget(self.transcribe_checkbox, row, 0)

        self.summarize_checkbox = QCheckBox("Summarize Content")
        # Don't set default - let _load_settings() handle it via settings manager
        layout.addWidget(self.summarize_checkbox, row, 1)
        row += 1

        # Connect checkboxes to save settings
        self.transcribe_checkbox.toggled.connect(self._save_settings)
        self.summarize_checkbox.toggled.connect(self._save_settings)

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
                "device": "cpu",  # Default for now
                "transcription_model": "base",  # Default for now
                "summarization_provider": "local",  # Use local LLM by default
                "summarization_model": "qwen2.5:7b-instruct",  # Default local model
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

            logger.debug(f"Settings saved for {self.tab_name} tab")

        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")

    def _load_settings(self) -> None:
        """Load settings from session."""
        try:
            # Load output directory
            output_dir = self.gui_settings.get_output_directory(self.tab_name, "")
            self.output_dir_line.setText(output_dir)

            # Load checkbox states - let settings manager handle hierarchy
            transcribe_state = self.gui_settings.get_checkbox_state(
                self.tab_name, "transcribe", None
            )
            if transcribe_state is not None:
                self.transcribe_checkbox.setChecked(transcribe_state)

            summarize_state = self.gui_settings.get_checkbox_state(
                self.tab_name, "summarize", None
            )
            if summarize_state is not None:
                self.summarize_checkbox.setChecked(summarize_state)

            logger.debug(f"Settings loaded for {self.tab_name} tab")

        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")
