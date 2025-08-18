""" File watcher tab for monitoring directories and auto-processing files."""

from pathlib import Path
from typing import Any

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ...logger import get_logger
from ...watchers import FileWatcher
from ..components.base_tab import BaseTab
from ..components.file_operations import FileOperationsMixin
from ..core.settings_manager import get_gui_settings_manager

logger = get_logger(__name__)


class WatcherTab(BaseTab, FileOperationsMixin):
    """Tab for managing file watcher operations."""

    def __init__(self, parent=None) -> None:
        # Initialize attributes before calling super() to prevent AttributeError
        self.watcher = None
        self.is_watching = False
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "File Watcher"

        # Now call super() which will call _setup_ui()
        super().__init__(parent)

    def _setup_ui(self):
        """Setup the file watcher UI."""
        layout = QVBoxLayout(self)

        # Watch configuration section
        config_section = self._create_configuration_section()
        layout.addWidget(config_section)

        # Control section
        control_section = self._create_control_section()
        layout.addWidget(control_section)

        # Status section
        status_section = self._create_status_section()
        layout.addWidget(status_section)

        # Output section
        output_layout = self._create_output_section()
        layout.addLayout(output_layout, 1)  # Give stretch factor to allow expansion

        # Load saved settings after UI is set up
        self._load_settings()

    def _create_configuration_section(self) -> QGroupBox:
        """Create the watch configuration section."""
        group = QGroupBox("Watch Configuration")
        layout = QGridLayout()

        # Watch directory
        layout.addWidget(QLabel("Watch Directory:"), 0, 0)
        self.watch_directory = QLineEdit()
        self.watch_directory.setPlaceholderText(
            "Select a directory to watch for new files..."
        )
        self.watch_directory.textChanged.connect(self._on_setting_changed)
        self.watch_directory.setToolTip(
            "Directory to monitor for new files.\n"
            "• New files matching the patterns will be detected automatically\n"
            "• Ensure you have read permissions to this directory\n"
            "• Can watch subdirectories if recursive option is enabled\n"
            "• Click Browse to select a directory"
        )
        layout.addWidget(self.watch_directory, 0, 1, 1, 2)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._select_watch_directory)
        browse_btn.setToolTip(
            "Browse and select a directory to watch for new files.\n"
            "• Choose a directory where new files will be added\n"
            "• The watcher will monitor this location continuously"
        )
        layout.addWidget(browse_btn, 0, 3)

        # File patterns
        layout.addWidget(QLabel("File Patterns:"), 1, 0)
        self.file_patterns = QLineEdit()
        self.file_patterns.setText("*.mp4,*.mp3,*.wav,*.pdf,*.txt,*.md")
        self.file_patterns.setToolTip(
            "Comma-separated file patterns to watch for (supports wildcards).\n"
            "• Examples: *.mp4, *.mp3, *.wav (audio/video files)\n"
            "• Examples: *.pdf, *.txt, *.md (document files)\n"
            "• Use * as wildcard for any characters\n"
            "• Separate multiple patterns with commas"
        )
        self.file_patterns.textChanged.connect(self._on_setting_changed)
        layout.addWidget(self.file_patterns, 1, 1, 1, 3)

        # Recursive watching
        self.recursive_checkbox = QCheckBox("Watch subdirectories recursively")
        self.recursive_checkbox.setChecked(True)
        self.recursive_checkbox.toggled.connect(self._on_setting_changed)
        self.recursive_checkbox.setToolTip(
            "Monitor subdirectories within the watch directory.\n"
            "• When enabled, watches all subdirectories for matching files\n"
            "• When disabled, only watches the root directory\n"
            "• Useful for monitoring nested folder structures"
        )
        layout.addWidget(self.recursive_checkbox, 2, 0, 1, 4)

        # Debounce delay
        layout.addWidget(QLabel("Debounce Delay:"), 3, 0)
        self.debounce_delay = QSpinBox()
        self.debounce_delay.setMinimum(1)
        self.debounce_delay.setMaximum(300)
        self.debounce_delay.setValue(5)
        self.debounce_delay.setSuffix(" seconds")
        self.debounce_delay.setToolTip(
            "Wait time in seconds before processing files after they are added or modified. "
            "Prevents processing files while they're still being written. "
            "Use higher values (10-30s) for large files or slow storage, "
            "lower values (1-5s) for small files or fast storage."
        )
        self.debounce_delay.valueChanged.connect(self._on_setting_changed)
        layout.addWidget(self.debounce_delay, 3, 1)

        group.setLayout(layout)
        return group

    def _create_control_section(self) -> QGroupBox:
        """Create the watcher control section."""
        group = QGroupBox("Watcher Control")
        layout = QVBoxLayout()

        # Control buttons
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶️ Start Watching")
        self.start_btn.clicked.connect(self._start_watching)
        self.start_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;"
        )
        self.start_btn.setToolTip(
            "Start monitoring the watch directory for new files.\n"
            "• Continuously monitors for files matching the specified patterns\n"
            "• Automatically processes new files if auto-process is enabled\n"
            "• Runs in the background until stopped\n"
            "• Shows detected files in the Recent Files list"
        )
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️ Stop Watching")
        self.stop_btn.clicked.connect(self._stop_watching)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            "background-color: #f44336; color: white; font-weight: bold; padding: 8px;"
        )
        self.stop_btn.setToolTip(
            "Stop monitoring the watch directory.\n"
            "• Stops the file watching service\n"
            "• Already detected files remain in the list\n"
            "• No new files will be detected until watching is restarted"
        )
        button_layout.addWidget(self.stop_btn)

        # Auto-process toggle (simplified)
        self.auto_process_checkbox = QCheckBox(
            "Auto-process new files (uses settings from other tabs)"
        )
        self.auto_process_checkbox.setChecked(True)
        self.auto_process_checkbox.setToolTip(
            "Automatically process new files as they are detected.\n"
            "• Uses current settings from Audio Transcription and Document Summarization tabs\n"
            "• Processes files immediately when they appear in the watch directory\n"
            "• When disabled, files are only detected but not processed\n"
            "• Requires valid API keys for processing"
        )
        self.auto_process_checkbox.toggled.connect(self._on_setting_changed)

        # Dry run option
        self.dry_run_checkbox = QCheckBox("Dry run (detect files but don't process)")
        self.dry_run_checkbox.toggled.connect(self._on_setting_changed)
        self.dry_run_checkbox.setToolTip(
            "Detect and list new files without actually processing them.\n"
            "• Shows what files would be processed\n"
            "• No API credits are consumed\n"
            "• Useful for testing file detection patterns\n"
            "• Files appear in the Recent Files list but are not processed"
        )
        layout.addLayout(button_layout)
        layout.addWidget(self.auto_process_checkbox)
        layout.addWidget(self.dry_run_checkbox)

        group.setLayout(layout)
        return group

    def _create_status_section(self) -> QGroupBox:
        """Create the status monitoring section."""
        group = QGroupBox("Watch Status")
        layout = QVBoxLayout()

        # Status info
        self.status_label = QLabel("Not watching")
        font = QFont()
        font.setBold(True)
        self.status_label.setFont(font)
        layout.addWidget(self.status_label)

        # Recent files list
        recent_label = QLabel("Recent Files Detected:")
        layout.addWidget(recent_label)

        self.recent_files_list = QListWidget()
        self.recent_files_list.setMaximumHeight(120)
        layout.addWidget(self.recent_files_list)

        # Clear recent files
        clear_btn = QPushButton("Clear Recent Files")
        clear_btn.clicked.connect(self._clear_recent_files)
        clear_btn.setToolTip(
            "Clear the list of recently detected files.\n"
            "• Removes all files from the Recent Files list\n"
            "• Does not affect the file watcher or processing\n"
            "• Useful for starting with a clean list"
        )
        layout.addWidget(clear_btn)

        group.setLayout(layout)
        return group

    def _select_watch_directory(self):
        """Select directory to watch."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory to Watch", "", QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self.watch_directory.setText(directory)

    def _start_watching(self):
        """Start file watching."""
        watch_path = self.watch_directory.text().strip()
        if not watch_path:
            self.show_warning("No Directory", "Please select a directory to watch")
            return

        watch_path_obj = Path(watch_path)
        if not watch_path_obj.exists():
            self.show_error(
                "Invalid Directory", f"Directory does not exist: {watch_path}"
            )
            return

        if not watch_path_obj.is_dir():
            self.show_error(
                "Invalid Directory", f"Path is not a directory: {watch_path}"
            )
            return

        try:
            # Parse file patterns
            patterns = [
                p.strip() for p in self.file_patterns.text().split(",") if p.strip()
            ]
            if not patterns:
                patterns = ["*"]

            # Create watcher configuration with simplified settings
            config = {
                "watch_path": watch_path_obj,
                "patterns": patterns,
                "recursive": self.recursive_checkbox.isChecked(),
                "debounce_delay": self.debounce_delay.value(),
                "auto_process": self.auto_process_checkbox.isChecked(),
                "dry_run": self.dry_run_checkbox.isChecked(),
            }

            # Initialize file watcher with callback
            def file_callback(file_path: Path):
                """Process detected files."""
                self._on_file_detected(str(file_path))

                if config["auto_process"] and not config["dry_run"]:
                    self._process_file(file_path, config)

            self.watcher = FileWatcher(
                directory=config["watch_path"],
                patterns=config["patterns"],
                callback=file_callback,
                debounce=config["debounce_delay"],
                recursive=config["recursive"],
            )

            # Start watching
            self.watcher.start()
            self.is_watching = True

            # Update UI
            self._update_watch_status(True)
            self.append_log(f"Started watching: {watch_path}")
            self.append_log(f"Patterns: {', '.join(patterns)}")
            self.append_log(f"Recursive: {config['recursive']}")
            self.append_log(f"Auto-process: {config['auto_process']}")

        except Exception as e:
            self.show_error("Failed to Start Watching", f"Error: {e}")
            logger.error(f"Failed to start file watcher: {e}")

    def _stop_watching(self):
        """Stop file watching."""
        if self.watcher:
            try:
                self.watcher.stop()
                self.watcher = None
                self.is_watching = False
                self._update_watch_status(False)
                self.append_log("Stopped file watching")
            except Exception as e:
                self.show_error("Failed to Stop Watching", f"Error: {e}")
                logger.error(f"Failed to stop file watcher: {e}")

    def _test_configuration(self):
        """Test the current configuration."""
        watch_path = self.watch_directory.text().strip()
        if not watch_path:
            self.show_warning("No Directory", "Please select a directory to watch")
            return

        watch_path_obj = Path(watch_path)
        if not watch_path_obj.exists():
            self.show_error(
                "Invalid Directory", f"Directory does not exist: {watch_path}"
            )
            return

        try:
            patterns = [
                p.strip() for p in self.file_patterns.text().split(",") if p.strip()
            ]
            if not patterns:
                patterns = ["*"]

            # Find matching files
            matching_files = []

            if self.recursive_checkbox.isChecked():
                for pattern in patterns:
                    matching_files.extend(watch_path_obj.rglob(pattern))
            else:
                for pattern in patterns:
                    matching_files.extend(watch_path_obj.glob(pattern))

            # Remove duplicates and sort
            matching_files = sorted(list(set(matching_files)))

            # Show results
            self.append_log("\n=== Configuration Test ===")
            self.append_log(f"Directory: {watch_path}")
            self.append_log(f"Patterns: {', '.join(patterns)}")
            self.append_log(f"Recursive: {self.recursive_checkbox.isChecked()}")
            self.append_log(f"Found {len(matching_files)} matching files:")

            for file_path in matching_files[:20]:  # Show first 20
                self.append_log(f"  - {file_path.name}")

            if len(matching_files) > 20:
                self.append_log(f"  ... and {len(matching_files) - 20} more files")

            self.append_log("=== End Test ===\n")

        except Exception as e:
            self.show_error("Configuration Test Failed", f"Error: {e}")

    def _update_watch_status(self, watching: bool):
        """Update the watch status UI."""
        if watching:
            self.status_label.setText("Watching (active)")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)

            # Disable configuration controls
            self.watch_directory.setEnabled(False)
            self.file_patterns.setEnabled(False)

        else:
            self.status_label.setText("Not watching")
            self.status_label.setStyleSheet("color: #666; font-weight: bold;")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

            # Enable configuration controls
            self.watch_directory.setEnabled(True)
            self.file_patterns.setEnabled(True)

    def _clear_recent_files(self):
        """Clear the recent files list."""
        self.recent_files_list.clear()

    def _on_file_detected(self, file_path: str):
        """Handle file detection signal."""
        self.recent_files_list.insertItem(0, f"Detected: {Path(file_path).name}")

        # Keep only last 50 items
        while self.recent_files_list.count() > 50:
            self.recent_files_list.takeItem(self.recent_files_list.count() - 1)

        self.append_log(f"File detected: {file_path}")

    def _on_processing_started(self, file_path: str):
        """Handle processing started signal."""
        self.recent_files_list.insertItem(0, f"Processing: {Path(file_path).name}")
        self.append_log(f"Started processing: {file_path}")

    def _process_file(self, file_path: Path, config: dict[str, Any]):
        """Process a detected file with automatic type detection and default settings."""
        try:
            self._on_processing_started(str(file_path))

            # Import processors
            from ...processors.audio_processor import AudioProcessor
            from ...processors.summarizer import SummarizerProcessor

            success = False
            output_files = []

            # Transcription for audio/video files (automatic)
            if file_path.suffix.lower() in [
                ".mp4",
                ".mp3",
                ".wav",
                ".webm",
                ".m4a",
                ".flac",
                ".ogg",
            ]:
                try:
                    processor = AudioProcessor(
                        device="auto",  # Use automatic device selection
                        model="base",  # Use base model as default
                    )
                    result = processor.process(file_path)

                    if result.success:
                        self.append_log(f"✅ Transcribed: {file_path}")
                        success = True
                        # Check for output files in result data
                        if hasattr(result, "data") and result.data:
                            if (
                                isinstance(result.data, dict)
                                and "output_file" in result.data
                            ):
                                output_files.append(str(result.data["output_file"]))
                    else:
                        self.append_log(
                            f"❌ Transcription failed: {'; '.join(result.errors)}"
                        )

                except Exception as e:
                    self.append_log(f"❌ Transcription error: {e}")

            # Summarization for text files (automatic)
            elif file_path.suffix.lower() in [".md", ".txt"]:
                try:
                    processor = SummarizerProcessor(
                        provider=self.settings.summarization.provider,
                        model="gpt-4o-mini-2024-07-18",  # Use default model
                        max_tokens=self.settings.summarization.max_tokens,
                    )
                    result = processor.process(file_path)

                    if result.success:
                        self.append_log(f"✅ Summarized: {file_path}")
                        success = True
                        # Check for output files in result data
                        if hasattr(result, "data") and result.data:
                            if (
                                isinstance(result.data, dict)
                                and "output_file" in result.data
                            ):
                                output_files.append(str(result.data["output_file"]))
                    else:
                        self.append_log(
                            f"❌ Summarization failed: {'; '.join(result.errors)}"
                        )

                except Exception as e:
                    self.append_log(f"❌ Summarization error: {e}")

            else:
                self.append_log(f"ℹ️ Unsupported file type: {file_path.suffix}")
                return

            # Update UI
            if success:
                self.recent_files_list.insertItem(0, f"✅ Completed: {file_path.name}")
                for output_file in output_files:
                    self.append_log(f"  → {output_file}")
            else:
                self.recent_files_list.insertItem(0, f"❌ Failed: {file_path.name}")

        except Exception as e:
            self.recent_files_list.insertItem(0, f"❌ Error: {file_path.name}")
            self.append_log(f"❌ Processing error: {file_path}")
            self.append_log(f"  Error: {e}")
            logger.error(f"File processing error: {e}")

    def _get_start_button_text(self) -> str:
        return "Start Watching"

    def _start_processing(self):
        """Start the main processing operation."""
        self._start_watching()

    def validate_inputs(self) -> bool:
        """Validate inputs before starting."""
        watch_path = self.watch_directory.text().strip()
        if not watch_path:
            self.show_warning("No Directory", "Please select a directory to watch")
            return False

        if not Path(watch_path).exists():
            self.show_error(
                "Invalid Directory", f"Directory does not exist: {watch_path}"
            )
            return False

        return True

    def _load_settings(self):
        """Load saved settings from session."""
        try:
            # Load watch directory
            saved_watch_dir = self.gui_settings.get_line_edit_text(
                self.tab_name, "watch_directory", ""
            )
            self.watch_directory.setText(saved_watch_dir)

            # Load file patterns
            saved_patterns = self.gui_settings.get_line_edit_text(
                self.tab_name, "file_patterns", "*.mp4,*.mp3,*.wav,*.pdf,*.txt,*.md"
            )
            self.file_patterns.setText(saved_patterns)

            # Load checkbox states
            self.recursive_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(self.tab_name, "recursive", True)
            )
            self.auto_process_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "auto_process", True
                )
            )
            self.dry_run_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(self.tab_name, "dry_run", False)
            )

            # Load debounce delay
            saved_debounce = self.gui_settings.get_spinbox_value(
                self.tab_name, "debounce_delay", 5
            )
            self.debounce_delay.setValue(saved_debounce)

            logger.debug(f"Loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")

    def _save_settings(self):
        """Save current settings to session."""
        try:
            # Save line edit text
            self.gui_settings.set_line_edit_text(
                self.tab_name, "watch_directory", self.watch_directory.text()
            )
            self.gui_settings.set_line_edit_text(
                self.tab_name, "file_patterns", self.file_patterns.text()
            )

            # Save checkbox states
            self.gui_settings.set_checkbox_state(
                self.tab_name, "recursive", self.recursive_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "auto_process", self.auto_process_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "dry_run", self.dry_run_checkbox.isChecked()
            )

            # Save spinbox values
            self.gui_settings.set_spinbox_value(
                self.tab_name, "debounce_delay", self.debounce_delay.value()
            )

            logger.debug(f"Saved settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")

    def _on_setting_changed(self):
        """Called when any setting changes to automatically save."""
        self._save_settings()
