""" Audio transcription tab for processing audio and video files using Whisper."""

import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ...logger import get_logger
from ..components.base_tab import BaseTab
from ..components.file_operations import FileOperationsMixin
from ..core.settings_manager import get_gui_settings_manager

logger = get_logger(__name__)


class EnhancedTranscriptionWorker(QThread):
    """ Enhanced worker thread for transcription with real-time progress."""

    progress_updated = pyqtSignal(object)  # Progress object
    file_completed = pyqtSignal(int, int)  # current, total
    processing_finished = pyqtSignal()
    processing_error = pyqtSignal(str)
    transcription_step_updated = pyqtSignal(
        str, int
    )  # step_description, progress_percent

    def __init__(
        self, files: Any, settings: Any, gui_settings: Any, parent: Any = None
    ) -> None:
        super().__init__(parent)
        self.files = files
        self.settings = settings
        self.gui_settings = gui_settings
        self.should_stop = False
        self.current_file_index = 0
        self.total_files = len(files)

    def _transcription_progress_callback(
        self, step_description_or_dict: Any, progress_percent: int = 0
    ) -> None:
        """ Callback to emit real-time transcription progress."""
        # Handle both string step descriptions and model download dictionaries
        if isinstance(step_description_or_dict, dict):
            # This is a model download progress update
            progress_dict = step_description_or_dict
            status = progress_dict.get("status", "unknown")
            model = progress_dict.get("model", "model")

            if status == "starting_download":
                message = progress_dict.get(
                    "message", f"Starting download of {model} model..."
                )
                self.transcription_step_updated.emit(f"📥 {message}", 0)
            elif status == "downloading":
                percent = progress_dict.get("percent", 0)
                speed_mbps = progress_dict.get("speed_mbps", 0)
                downloaded_mb = progress_dict.get("downloaded_mb", 0)
                total_mb = progress_dict.get("total_mb", 0)
                message = f"Downloading {model} model: {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB @ {speed_mbps:.1f} MB/s)"
                self.transcription_step_updated.emit(f"📥 {message}", int(percent))
            elif status == "download_complete":
                message = progress_dict.get(
                    "message", f"Successfully downloaded {model} model"
                )
                self.transcription_step_updated.emit(f"✅ {message}", 100)
            else:
                # Generic progress message
                message = progress_dict.get("message", f"Model {model}: {status}")
                self.transcription_step_updated.emit(f"🔄 {message}", progress_percent)
        else:
            # This is a regular string step description
            self.transcription_step_updated.emit(
                step_description_or_dict, progress_percent
            )

    def run(self) -> None:
        """ Run the transcription process with real-time progress tracking."""
        try:
            from ...processors.audio_processor import AudioProcessor

            # Create processor with GUI settings - filter out conflicting diarization parameter
            kwargs = self.gui_settings.get("kwargs", {})
            # Extract diarization setting and pass it as enable_diarization
            enable_diarization = kwargs.get("diarization", False)

            # Valid AudioProcessor constructor parameters
            valid_audio_processor_params = {
                "normalize_audio",
                "target_format",
                "device",
                "temp_dir",
                "use_whisper_cpp",
                "model",
                "progress_callback",
                "enable_diarization",
                "hf_token",
                "enable_quality_retry",
                "max_retry_attempts",
            }

            # Filter kwargs to only include valid AudioProcessor constructor parameters
            audio_processor_kwargs = {}
            processing_kwargs = {}

            for k, v in kwargs.items():
                if k in valid_audio_processor_params:
                    audio_processor_kwargs[k] = v
                else:
                    # These will be passed to the .process() method instead
                    processing_kwargs[k] = v

            # Ensure timestamps preference is passed to the process method
            if "timestamps" in self.gui_settings:
                processing_kwargs["timestamps"] = self.gui_settings["timestamps"]

            # Add progress callback to processor
            processor = AudioProcessor(
                model=self.gui_settings["model"],
                device=self.gui_settings["device"],
                enable_diarization=enable_diarization,
                enable_quality_retry=self.gui_settings.get(
                    "enable_quality_retry", True
                ),
                max_retry_attempts=self.gui_settings.get("max_retry_attempts", 1),
                progress_callback=self._transcription_progress_callback,
                **audio_processor_kwargs,
            )

            self.total_files = len(self.files)

            for i, file_path in enumerate(self.files):
                if self.should_stop:
                    break

                self.current_file_index = i
                file_name = Path(file_path).name

                # Emit file start progress
                self.transcription_step_updated.emit(
                    f"Starting transcription of {file_name}...", 0
                )
                self.file_completed.emit(i, self.total_files)

                try:
                    # Pass processing parameters (like omp_threads, batch_size, output_dir) to the process method
                    # Include output_dir for markdown file generation
                    processing_kwargs_with_output = processing_kwargs.copy()

                    # REQUIRE: Always ensure output_dir is set for file saving
                    # User must have specified an output directory
                    output_dir = self.gui_settings.get("output_dir")
                    if not output_dir or not output_dir.strip():
                        # This should be caught by validation, but just in case
                        raise ValueError(
                            "Output directory is required but was not specified"
                        )

                    processing_kwargs_with_output["output_dir"] = output_dir

                    result = processor.process(
                        Path(file_path), **processing_kwargs_with_output
                    )

                    if result.success:
                        # Get transcription data info
                        transcript_data = result.data
                        text_length = (
                            len(transcript_data.get("text", ""))
                            if transcript_data
                            else 0
                        )

                        # Check if markdown file was saved
                        saved_file = (
                            result.metadata.get("saved_markdown_file")
                            if result.metadata
                            else None
                        )
                        if saved_file:
                            status_msg = f"transcription completed ({text_length:,} characters) - saved to {Path(saved_file).name}"
                            step_msg = f"✅ Transcription of {file_name} completed and saved to {Path(saved_file).name}"
                            logger.info(
                                f"Successfully transcribed and saved: {file_path} -> {saved_file}"
                            )
                        else:
                            status_msg = f"transcription completed ({text_length:,} characters) - WARNING: file not saved"
                            step_msg = f"⚠️ Transcription of {file_name} completed but file was not saved!"
                            logger.warning(
                                f"Transcription succeeded but file not saved for: {file_path}"
                            )

                        # Emit progress update with success
                        progress_data = {
                            "file": file_path,
                            "current": i + 1,
                            "total": self.total_files,
                            "status": status_msg,
                            "success": True,
                            "text_length": text_length,
                            "saved_file": saved_file,
                        }
                        self.progress_updated.emit(progress_data)
                        self.transcription_step_updated.emit(step_msg, 100)
                    else:
                        # Emit progress update with failure
                        progress_data = {
                            "file": file_path,
                            "current": i + 1,
                            "total": self.total_files,
                            "status": f"transcription failed: {'; '.join(result.errors)}",
                            "success": False,
                        }
                        self.progress_updated.emit(progress_data)
                        self.transcription_step_updated.emit(
                            f"❌ Transcription of {file_name} failed", 0
                        )

                except Exception as e:
                    progress_data = {
                        "file": file_path,
                        "current": i + 1,
                        "total": self.total_files,
                        "status": f"transcription error: {str(e)}",
                        "success": False,
                    }
                    self.progress_updated.emit(progress_data)
                    self.transcription_step_updated.emit(
                        f"❌ Error transcribing {file_name}: {str(e)}", 0
                    )

            self.processing_finished.emit()

        except Exception as e:
            self.processing_error.emit(str(e))

    def stop(self) -> None:
        """ Stop the transcription process."""
        self.should_stop = True


class TranscriptionTab(BaseTab, FileOperationsMixin):
    """ Tab for audio and video transcription using Whisper."""

    def __init__(self, parent=None) -> None:
        self.transcription_worker: EnhancedTranscriptionWorker | None = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "Audio Transcription"
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """ Setup the transcription UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)  # Add consistent spacing
        layout.setContentsMargins(10, 10, 10, 10)  # Add margins

        # Hardware recommendations section (buttons only, no instructions)
        recommendations_section = self._create_recommendations_section()
        layout.addWidget(recommendations_section)

        # Input section with stretch factor
        input_section = self._create_input_section()
        layout.addWidget(input_section, 1)  # Give some stretch to input section

        # Settings section
        settings_section = self._create_settings_section()
        layout.addWidget(settings_section)

        # Performance section (consolidated thread/hardware management)
        performance_section = self._create_performance_section()
        layout.addWidget(performance_section)

        # Action buttons
        action_layout = self._create_action_layout()
        layout.addLayout(action_layout)

        # Progress section
        progress_section = self._create_progress_section()
        layout.addWidget(progress_section)

        # Output section with proper stretch
        output_layout = self._create_output_section()
        layout.addLayout(output_layout, 2)  # Give more stretch to output section

        # Load saved settings after UI is set up
        self._load_settings()

    def _create_input_section(self) -> QGroupBox:
        """ Create the input files section."""
        group = QGroupBox("Input Files")
        layout = QVBoxLayout()
        layout.setSpacing(8)  # Add spacing between elements

        # File list with improved size policy
        self.transcription_files = QListWidget()
        self.transcription_files.setMinimumHeight(100)  # Smaller minimum height
        self.transcription_files.setMaximumHeight(150)  # Smaller maximum to save space
        # Set size policy to allow proper vertical expansion/contraction
        from PyQt6.QtWidgets import QSizePolicy

        self.transcription_files.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self.transcription_files)

        # File buttons with proper spacing
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)  # Add spacing between buttons

        add_files_btn = QPushButton("Add Files")
        add_files_btn.setMinimumHeight(30)  # Ensure minimum button height
        add_files_btn.clicked.connect(self._add_files)
        button_layout.addWidget(add_files_btn)

        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.setMinimumHeight(30)  # Ensure minimum button height
        add_folder_btn.clicked.connect(self._add_folder)
        button_layout.addWidget(add_folder_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setMinimumHeight(30)  # Ensure minimum button height
        clear_btn.clicked.connect(self._clear_files)
        clear_btn.setStyleSheet(
            "background-color: #d32f2f; color: white; font-weight: bold;"
        )
        button_layout.addWidget(clear_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

    def _create_recommendations_section(self) -> QGroupBox:
        """ Create the hardware recommendations section."""
        group = QGroupBox("Hardware Recommendations")

        # Use horizontal layout
        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)

        # Left side: Use Recommended Settings button
        self.use_recommended_btn = QPushButton("⚡ Get & Apply Recommended Settings")
        self.use_recommended_btn.setMinimumHeight(35)
        self.use_recommended_btn.setMaximumHeight(35)
        self.use_recommended_btn.clicked.connect(self._apply_recommended_settings)
        self.use_recommended_btn.setStyleSheet(
            "background-color: #4caf50; color: white; font-weight: bold; padding: 8px;"
        )
        self.use_recommended_btn.setToolTip(
            "Automatically detects your hardware capabilities and applies optimal transcription settings. "
            "This will configure the best model, device, batch size, and thread count for your system."
        )
        main_layout.addWidget(self.use_recommended_btn)

        # Right side: Info box with expandable height
        self.recommendations_label = QLabel(
            "Click 'Get & Apply Recommended Settings' to automatically detect and configure optimal settings for your hardware."
        )
        self.recommendations_label.setWordWrap(True)
        self.recommendations_label.setStyleSheet(
            """
            background-color: #f5f5f5;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 11px;
        """
        )
        self.recommendations_label.setMinimumHeight(35)
        # Remove max height limit to allow expansion for recommendations
        # Set size policy to allow both horizontal and vertical expansion
        from PyQt6.QtWidgets import QSizePolicy

        self.recommendations_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        main_layout.addWidget(self.recommendations_label, 1)  # Give it more space

        group.setLayout(main_layout)
        return group

    def _create_settings_section(self) -> QGroupBox:
        """ Create the transcription settings section."""
        group = QGroupBox("Settings")
        layout = QGridLayout()

        # Model selection
        layout.addWidget(QLabel("Transcription Model:"), 0, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large"])
        self.model_combo.setCurrentText("base")
        self.model_combo.setToolTip(
            "Choose the Whisper model size. Larger models are more accurate but slower and use more memory. "
            "'base' is recommended for most users."
        )
        self.model_combo.currentTextChanged.connect(self._on_setting_changed)
        layout.addWidget(self.model_combo, 0, 1)

        # Language selection
        layout.addWidget(QLabel("Language:"), 0, 2)
        self.language_combo = QComboBox()
        self.language_combo.addItems(
            ["auto", "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]
        )
        self.language_combo.setCurrentText("auto")
        self.language_combo.setToolTip(
            "Select the language of the audio. 'auto' lets Whisper detect the language automatically. "
            "Specifying the exact language can improve accuracy."
        )
        self.language_combo.currentTextChanged.connect(self._on_setting_changed)
        layout.addWidget(self.language_combo, 0, 3)

        # Device selection
        layout.addWidget(QLabel("GPU Acceleration:"), 1, 0)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cpu", "cuda", "mps"])
        self.device_combo.setCurrentText("auto")
        self.device_combo.setToolTip(
            "Choose processing device: 'auto' detects best available, 'cpu' uses CPU only, "
            "'cuda' uses NVIDIA GPU, 'mps' uses Apple Silicon GPU."
        )
        self.device_combo.currentTextChanged.connect(self._on_setting_changed)
        layout.addWidget(self.device_combo, 1, 1)

        # Output format
        layout.addWidget(QLabel("Format:"), 1, 2)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["txt", "md", "srt", "vtt"])
        self.format_combo.setCurrentText("md")
        self.format_combo.setToolTip(
            "Output format: 'txt' for plain text, 'md' for Markdown, 'srt' and 'vtt' for subtitle files with precise timing."
        )
        self.format_combo.currentTextChanged.connect(self._on_setting_changed)
        layout.addWidget(self.format_combo, 1, 3)

        # Output directory (make more compact)
        layout.addWidget(QLabel("Output Directory:"), 2, 0)
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText(
            "Click Browse to select output directory (required)"
        )
        # Remove default setting - require user selection
        self.output_dir_input.textChanged.connect(self._on_setting_changed)
        # Make output directory field take only 1 column instead of 2
        layout.addWidget(self.output_dir_input, 2, 1, 1, 1)

        browse_output_btn = QPushButton("Browse")
        browse_output_btn.setMaximumWidth(80)  # Limit browse button width
        browse_output_btn.clicked.connect(self._select_output_directory)
        layout.addWidget(browse_output_btn, 2, 2)

        # Add some spacing in the last column
        layout.addWidget(QLabel(""), 2, 3)

        # Options
        self.timestamps_checkbox = QCheckBox("Include timestamps")
        self.timestamps_checkbox.setChecked(True)
        self.timestamps_checkbox.toggled.connect(self._on_setting_changed)
        layout.addWidget(self.timestamps_checkbox, 3, 0, 1, 2)

        self.diarization_checkbox = QCheckBox("Enable speaker diarization")
        self.diarization_checkbox.toggled.connect(self._on_setting_changed)
        layout.addWidget(self.diarization_checkbox, 3, 2, 1, 2)

        self.overwrite_checkbox = QCheckBox("Overwrite existing transcripts")
        self.overwrite_checkbox.setToolTip(
            "If unchecked, existing transcripts will be skipped"
        )
        self.overwrite_checkbox.toggled.connect(self._on_setting_changed)
        layout.addWidget(self.overwrite_checkbox, 4, 0, 1, 2)

        # Quality retry options
        self.quality_retry_checkbox = QCheckBox("Enable automatic quality retry")
        self.quality_retry_checkbox.setChecked(True)
        self.quality_retry_checkbox.setToolTip(
            "When enabled, failed transcriptions will automatically retry with a larger model. "
            "Improves accuracy but may increase processing time."
        )
        self.quality_retry_checkbox.toggled.connect(self._on_setting_changed)
        self.quality_retry_checkbox.toggled.connect(self._on_quality_retry_toggled)
        layout.addWidget(self.quality_retry_checkbox, 4, 2, 1, 2)

        # Max retry attempts
        layout.addWidget(QLabel("Max Retry Attempts:"), 5, 0)
        self.max_retry_attempts = QSpinBox()
        self.max_retry_attempts.setMinimum(0)
        self.max_retry_attempts.setMaximum(3)
        self.max_retry_attempts.setValue(1)
        self.max_retry_attempts.setToolTip(
            "Maximum number of retry attempts with larger models when quality validation fails. "
            "0 = No retries (fastest), 1 = One retry (recommended), 2-3 = Multiple retries (slowest but highest quality)"
        )
        self.max_retry_attempts.valueChanged.connect(self._on_setting_changed)
        layout.addWidget(self.max_retry_attempts, 5, 1)

        # Quality vs Performance info label
        quality_info_label = QLabel(
            "💡 Tip: Disable retry for fastest processing, enable for best quality"
        )
        quality_info_label.setStyleSheet(
            "color: #666; font-size: 10px; font-style: italic;"
        )
        layout.addWidget(quality_info_label, 5, 2, 1, 2)

        group.setLayout(layout)
        return group

    def _create_performance_section(self) -> QGroupBox:
        """ Create the thread & resource management section."""
        group = QGroupBox("Thread & Resource Management")
        layout = QGridLayout()

        # OpenMP thread count
        layout.addWidget(QLabel("OpenMP Threads:"), 0, 0)
        self.omp_threads = QSpinBox()
        self.omp_threads.setMinimum(1)
        self.omp_threads.setMaximum(32)
        self.omp_threads.setValue(max(1, min(8, os.cpu_count() or 4)))
        self.omp_threads.setToolTip(
            "Number of OpenMP threads for whisper.cpp processing. Passed as -t parameter."
        )
        self.omp_threads.valueChanged.connect(self._on_setting_changed)
        layout.addWidget(self.omp_threads, 0, 1)

        # Max concurrent files
        layout.addWidget(QLabel("Max Concurrent Files:"), 0, 2)
        self.max_concurrent = QSpinBox()
        self.max_concurrent.setMinimum(1)
        self.max_concurrent.setMaximum(16)
        self.max_concurrent.setValue(max(1, min(4, (os.cpu_count() or 4) // 2)))
        self.max_concurrent.setToolTip(
            "Maximum number of files to process simultaneously. Controls actual parallel processing."
        )
        self.max_concurrent.valueChanged.connect(self._on_setting_changed)
        layout.addWidget(self.max_concurrent, 0, 3)

        # Batch size
        layout.addWidget(QLabel("Batch Size:"), 1, 0)
        self.batch_size = QSpinBox()
        self.batch_size.setMinimum(1)
        self.batch_size.setMaximum(64)
        self.batch_size.setValue(16)
        self.batch_size.setToolTip(
            "Batch size for whisper.cpp processing. Passed as -bs parameter."
        )
        self.batch_size.valueChanged.connect(self._on_setting_changed)
        layout.addWidget(self.batch_size, 1, 1)

        # Processing mode
        layout.addWidget(QLabel("Processing Mode:"), 1, 2)
        self.processing_mode = QComboBox()
        self.processing_mode.addItems(["Parallel", "Sequential"])
        self.processing_mode.setCurrentText("Parallel")
        self.processing_mode.setToolTip(
            "Parallel processes multiple files at once (faster). Sequential processes one at a time (uses less resources)."
        )
        self.processing_mode.currentTextChanged.connect(self._on_setting_changed)
        layout.addWidget(self.processing_mode, 1, 3)

        group.setLayout(layout)
        return group

    def _create_progress_section(self) -> QGroupBox:
        """ Create the progress tracking section."""
        group = QGroupBox("Transcription Progress")
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # Progress bar for individual file progress
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setMinimum(0)
        self.file_progress_bar.setMaximum(100)
        self.file_progress_bar.setValue(0)
        self.file_progress_bar.setVisible(False)  # Hidden initially
        self.file_progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4caf50;
                border-radius: 4px;
            }
        """
        )
        layout.addWidget(self.file_progress_bar)

        # Progress status label
        self.progress_status_label = QLabel("")
        self.progress_status_label.setVisible(False)  # Hidden initially
        self.progress_status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.progress_status_label)

        group.setLayout(layout)
        return group

    def _add_files(
        self,
        file_list_attr: str = "transcription_files",
        file_patterns: str = "Audio/Video files (*.mp4 *.mp3 *.wav *.webm *.m4a *.flac *.ogg);;All files (*.*)",
    ):
        """ Add files for transcription."""
        file_list = getattr(self, file_list_attr, self.transcription_files)
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio/Video Files",
            "",
            file_patterns,
        )
        for file in files:
            file_list.addItem(file)

    def _add_folder(self):
        """ Add transcription folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            folder_path = Path(folder)
            extensions = [".mp4", ".mp3", ".wav", ".webm", ".m4a", ".flac", ".ogg"]
            for file in folder_path.rglob("*"):
                if file.suffix.lower() in extensions:
                    self.transcription_files.addItem(str(file))

    def _clear_files(self):
        """ Clear transcription file list."""
        self.transcription_files.clear()

    def _select_output_directory(self):
        """ Select output directory for transcripts."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_dir_input.setText(dir_path)

    def _get_start_button_text(self) -> str:
        """ Get the text for the start button."""
        return "Start Transcription"

    def _start_processing(self) -> None:
        """ Start transcription process."""
        # Get files to process
        files = []
        for i in range(self.transcription_files.count()):
            item = self.transcription_files.item(i)
            if item is not None:
                files.append(item.text())

        if not files:
            self.show_warning("Warning", "No files selected for transcription")
            return

        # Validate inputs
        if not self.validate_inputs():
            return

        # Clear output and show progress
        self.output_text.clear()
        self.append_log(f"Starting transcription of {len(files)} files...")

        # Disable start button
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Processing...")

        # Get transcription settings
        gui_settings = self._get_transcription_settings()

        # Start transcription worker
        self.transcription_worker = EnhancedTranscriptionWorker(
            files, self.settings, gui_settings, self
        )
        self.transcription_worker.progress_updated.connect(self._update_progress)
        self.transcription_worker.file_completed.connect(self._file_completed)
        self.transcription_worker.processing_finished.connect(self._processing_finished)
        self.transcription_worker.processing_error.connect(self._processing_error)
        self.transcription_worker.transcription_step_updated.connect(
            self._update_transcription_step
        )

        self.active_workers.append(self.transcription_worker)
        self.transcription_worker.start()

        self.status_updated.emit("Transcription in progress...")

    def _update_transcription_step(self, step_description: str, progress_percent: int):
        """ Update real-time transcription step display."""
        self.append_log(f"🎤 {step_description}")

        # Update progress bar and status
        if hasattr(self, "file_progress_bar") and hasattr(
            self, "progress_status_label"
        ):
            self.file_progress_bar.setVisible(True)
            self.progress_status_label.setVisible(True)
            self.file_progress_bar.setValue(progress_percent)
            self.progress_status_label.setText(step_description)

    def _update_progress(self, progress_data):
        """ Update transcription progress display."""
        if isinstance(progress_data, dict):
            file_name = Path(progress_data["file"]).name
            current = progress_data["current"]
            total = progress_data["total"]
            status = progress_data["status"]
            success = progress_data.get("success", True)
            text_length = progress_data.get("text_length", 0)

            status_icon = "✅" if success else "❌"

            # Show detailed transcription result information
            if success and text_length > 0:
                self.append_log(
                    f"[{current}/{total}] {file_name}: {status_icon} {status}"
                )
                self.append_log(
                    f"   📝 Generated {text_length:,} characters of transcription text"
                )
            else:
                self.append_log(
                    f"[{current}/{total}] {file_name}: {status_icon} {status}"
                )
        else:
            self.append_log(f"Progress: {progress_data}")

    def _file_completed(self, current: int, total: int):
        """ Handle transcription file completion."""
        if current < total:
            self.append_log(f"📁 Processing file {current + 1} of {total}...")

    def _processing_finished(self):
        """ Handle transcription completion."""
        self.append_log("\n✅ All transcriptions completed!")
        self.append_log(
            "📋 Note: Transcriptions are processed in memory. Use the Process Pipeline tab to save transcripts to markdown files."
        )

        # Hide progress bar and status
        if hasattr(self, "file_progress_bar") and hasattr(
            self, "progress_status_label"
        ):
            self.file_progress_bar.setVisible(False)
            self.progress_status_label.setVisible(False)

        # Re-enable start button
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())

        self.status_updated.emit("Transcription completed")
        self.processing_finished.emit()

    def _processing_error(self, error_msg: str):
        """ Handle transcription error."""
        self.append_log(f"❌ Error: {error_msg}")
        self.show_error("Transcription Error", f"Transcription failed: {error_msg}")

        # Hide progress bar and status
        if hasattr(self, "file_progress_bar") and hasattr(
            self, "progress_status_label"
        ):
            self.file_progress_bar.setVisible(False)
            self.progress_status_label.setVisible(False)

        # Re-enable start button
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())

        self.status_updated.emit("Ready")

    def _get_hardware_recommendations(self):
        """ Get hardware recommendations and display them."""
        try:
            from ...utils.device_selection import get_device_recommendations
            from ...utils.hardware_detection import get_hardware_detector

            detector = get_hardware_detector()
            specs = detector.detect_hardware()
            recommendations = get_device_recommendations("transcription")

            # Store recommendations for later use
            self._current_recommendations = {
                "specs": specs,
                "recommendations": recommendations,
            }

            # Display hardware specs in left column
            spec_text = []
            spec_text.append(f"🎯 Recommended Device: {specs.recommended_device}")
            spec_text.append(f"🧠 Recommended Model: {specs.recommended_whisper_model}")
            spec_text.append(f"📦 Batch Size: {specs.optimal_batch_size}")
            spec_text.append(f"🔄 Max Concurrent: {specs.max_concurrent_transcriptions}")

            # Combine specifications and performance notes into single display
            display_text = []
            display_text.extend(spec_text)

            if recommendations["performance_notes"]:
                display_text.append("")  # Empty line separator
                display_text.append("💡 Performance Notes:")
                for note in recommendations["performance_notes"]:
                    display_text.append(f"• {note}")

            self.recommendations_label.setText("\n".join(display_text))
            self.recommendations_label.setStyleSheet(
                """
                background-color: #e8f5e8;
                padding: 10px;
                border: 1px solid #4caf50;
                border-radius: 5px;
                font-size: 11px;
                """
            )

            # Enable the "Use Recommended Settings" button
            self.use_recommended_btn.setEnabled(True)

            self.append_log("Hardware recommendations loaded successfully")

        except Exception as e:
            error_msg = f"Failed to get hardware recommendations: {e}"
            self.recommendations_label.setText(f"❌ {error_msg}")
            self.recommendations_label.setStyleSheet(
                """
                background-color: #ffeaea;
                padding: 10px;
                border: 1px solid #f44336;
                border-radius: 5px;
                font-size: 11px;
                """
            )

    def _apply_recommended_settings(self):
        """ Get hardware recommendations if needed, then apply them to the UI controls."""
        # First, check if we have recommendations - if not, get them
        if not hasattr(self, "_current_recommendations"):
            self.append_log("🔍 Getting hardware recommendations...")
            self._get_hardware_recommendations()

            # Check if we successfully got recommendations
            if not hasattr(self, "_current_recommendations"):
                self.append_log(
                    "❌ Failed to get recommendations. Please check hardware detection."
                )
                return

        try:
            specs = self._current_recommendations["specs"]

            # Apply recommended settings
            # Model
            if specs.recommended_whisper_model in [
                "tiny",
                "base",
                "small",
                "medium",
                "large",
            ]:
                index = self.model_combo.findText(specs.recommended_whisper_model)
                if index >= 0:
                    self.model_combo.setCurrentIndex(index)

            # Device
            device_mapping = {"cpu": "cpu", "cuda": "cuda", "mps": "mps"}
            recommended_device = device_mapping.get(
                specs.recommended_device.lower(), "auto"
            )
            index = self.device_combo.findText(recommended_device)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)

            # Batch size
            if hasattr(specs, "optimal_batch_size") and specs.optimal_batch_size:
                self.batch_size.setValue(specs.optimal_batch_size)

            # Max concurrent files
            if (
                hasattr(specs, "max_concurrent_transcriptions")
                and specs.max_concurrent_transcriptions
            ):
                self.max_concurrent.setValue(specs.max_concurrent_transcriptions)

            # Calculate optimal thread count (usually leave some cores free)
            if hasattr(specs, "cpu_cores") and specs.cpu_cores:
                optimal_threads = max(1, min(8, specs.cpu_cores - 1))
                self.omp_threads.setValue(optimal_threads)

            self.append_log("✅ Recommended settings applied successfully!")

        except Exception as e:
            error_msg = f"Failed to apply recommended settings: {e}"
            self.append_log(f"❌ {error_msg}")

    def _get_transcription_settings(self) -> dict[str, Any]:
        """ Get current transcription settings."""
        return {
            "model": self.model_combo.currentText(),
            "device": self.device_combo.currentText(),
            "language": (
                self.language_combo.currentText()
                if self.language_combo.currentText() != "auto"
                else None
            ),
            "format": self.format_combo.currentText(),
            "timestamps": self.timestamps_checkbox.isChecked(),
            "diarization": self.diarization_checkbox.isChecked(),
            "overwrite": self.overwrite_checkbox.isChecked(),
            "output_dir": self.output_dir_input.text().strip() or None,
            "batch_size": self.batch_size.value(),
            "omp_threads": self.omp_threads.value(),
            "max_concurrent": self.max_concurrent.value(),
            "processing_mode": self.processing_mode.currentText(),
            "enable_quality_retry": self.quality_retry_checkbox.isChecked(),
            "max_retry_attempts": self.max_retry_attempts.value(),
            "tokenizers_parallelism": False,  # Disabled: causes warnings and minimal benefit
            "mps_fallback": True,  # Enabled: MPS automatically falls back to CPU when needed
            "hf_token": getattr(
                self.settings.api_keys, "huggingface_token", None
            ),  # Add HF token for diarization
            "kwargs": {
                "diarization": self.diarization_checkbox.isChecked(),
                "omp_threads": self.omp_threads.value(),
                "batch_size": self.batch_size.value(),
                "hf_token": getattr(
                    self.settings.api_keys, "huggingface_token", None
                ),  # Also add to kwargs for AudioProcessor
            },
        }

    def validate_inputs(self) -> bool:
        """ Validate inputs before processing."""
        # Check output directory
        output_dir = self.output_dir_input.text().strip()
        if not output_dir:
            self.show_error("Invalid Output", "Output directory must be selected.")
            return False

        if not Path(output_dir).parent.exists():
            self.show_error("Invalid Output", "Output directory parent doesn't exist")
            return False

        # Check speaker diarization requirements
        if self.diarization_checkbox.isChecked():
            # Check if diarization is available
            try:
                from knowledge_system.processors.diarization import (
                    get_diarization_installation_instructions,
                    is_diarization_available,
                )

                if not is_diarization_available():
                    self.show_error(
                        "Missing Diarization Dependencies",
                        "Speaker diarization requires additional dependencies.\n\n"
                        + get_diarization_installation_instructions(),
                    )
                    return False
            except ImportError:
                self.show_error(
                    "Missing Dependency",
                    "Speaker diarization requires 'pyannote.audio' to be installed.\n\n"
                    "Install it with: pip install -e '.[diarization]'\n\n"
                    "Please install this dependency or disable speaker diarization.",
                )
                return False

            # Check if HuggingFace token is configured
            hf_token = getattr(self.settings.api_keys, "huggingface_token", None)
            if not hf_token:
                self.show_warning(
                    "Missing HuggingFace Token",
                    "Speaker diarization requires a HuggingFace token to access the pyannote models.\n\n"
                    "Please configure your HuggingFace token in the Settings tab or disable speaker diarization.\n\n"
                    "You can get a free token at: https://huggingface.co/settings/tokens",
                )
                # Don't return False here, just warn - let the user proceed if they want

        return True

    def cleanup_workers(self):
        """ Clean up any active workers."""
        if self.transcription_worker and self.transcription_worker.isRunning():
            # Set stop flag and terminate if needed
            if hasattr(self.transcription_worker, "should_stop"):
                self.transcription_worker.should_stop = True
            self.transcription_worker.terminate()
            self.transcription_worker.wait(3000)
        super().cleanup_workers()

    def _load_settings(self) -> None:
        """ Load saved settings from session."""
        try:
            # Block signals during loading to prevent redundant saves
            widgets_to_block = [
                self.output_dir_input,
                self.model_combo,
                self.device_combo,
                self.language_combo,
                self.format_combo,
                self.timestamps_checkbox,
                self.diarization_checkbox,
            ]

            # Block all signals
            for widget in widgets_to_block:
                widget.blockSignals(True)

            try:
                # Load output directory - no hardcoded default
                saved_output_dir = self.gui_settings.get_output_directory(
                    self.tab_name, ""  # Empty string - require user selection
                )
                self.output_dir_input.setText(saved_output_dir)

                # Load model selection
                saved_model = self.gui_settings.get_combo_selection(
                    self.tab_name, "model", "base"
                )
                index = self.model_combo.findText(saved_model)
                if index >= 0:
                    self.model_combo.setCurrentIndex(index)

                # Load device selection
                saved_device = self.gui_settings.get_combo_selection(
                    self.tab_name, "device", "auto"
                )
                index = self.device_combo.findText(saved_device)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)

                # Load language selection
                saved_language = self.gui_settings.get_combo_selection(
                    self.tab_name, "language", "auto"
                )
                index = self.language_combo.findText(saved_language)
                if index >= 0:
                    self.language_combo.setCurrentIndex(index)

                # Load format selection
                saved_format = self.gui_settings.get_combo_selection(
                    self.tab_name, "format", "md"
                )
                index = self.format_combo.findText(saved_format)
                if index >= 0:
                    self.format_combo.setCurrentIndex(index)

                # Load checkbox states
                self.timestamps_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "include_timestamps", True
                    )
                )
                self.diarization_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "enable_diarization", False
                    )
                )

            finally:
                # Always restore signals
                for widget in widgets_to_block:
                    widget.blockSignals(False)
            self.overwrite_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "overwrite_existing", False
                )
            )
            self.quality_retry_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "enable_quality_retry", True
                )
            )

            # Load spinbox values
            self.batch_size.setValue(
                self.gui_settings.get_spinbox_value(self.tab_name, "batch_size", 1)
            )
            self.omp_threads.setValue(
                self.gui_settings.get_spinbox_value(self.tab_name, "omp_threads", 4)
            )
            self.max_concurrent.setValue(
                self.gui_settings.get_spinbox_value(self.tab_name, "max_concurrent", 1)
            )
            self.max_retry_attempts.setValue(
                self.gui_settings.get_spinbox_value(
                    self.tab_name, "max_retry_attempts", 1
                )
            )

            # Load processing mode selection
            saved_mode = self.gui_settings.get_combo_selection(
                self.tab_name, "processing_mode", "balanced"
            )
            index = self.processing_mode.findText(saved_mode)
            if index >= 0:
                self.processing_mode.setCurrentIndex(index)

            # Ensure quality retry state is properly reflected in UI
            self._on_quality_retry_toggled(self.quality_retry_checkbox.isChecked())

            logger.debug(f"Loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")

    def _save_settings(self) -> None:
        """ Save current settings to session."""
        try:
            # Save output directory
            self.gui_settings.set_output_directory(
                self.tab_name, self.output_dir_input.text()
            )

            # Save combo selections
            self.gui_settings.set_combo_selection(
                self.tab_name, "model", self.model_combo.currentText()
            )
            self.gui_settings.set_combo_selection(
                self.tab_name, "device", self.device_combo.currentText()
            )
            self.gui_settings.set_combo_selection(
                self.tab_name, "language", self.language_combo.currentText()
            )
            self.gui_settings.set_combo_selection(
                self.tab_name, "format", self.format_combo.currentText()
            )
            self.gui_settings.set_combo_selection(
                self.tab_name, "processing_mode", self.processing_mode.currentText()
            )

            # Save checkbox states
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "include_timestamps",
                self.timestamps_checkbox.isChecked(),
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "enable_diarization",
                self.diarization_checkbox.isChecked(),
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "overwrite_existing", self.overwrite_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "enable_quality_retry",
                self.quality_retry_checkbox.isChecked(),
            )

            # Save spinbox values
            self.gui_settings.set_spinbox_value(
                self.tab_name, "batch_size", self.batch_size.value()
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name, "omp_threads", self.omp_threads.value()
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name, "max_concurrent", self.max_concurrent.value()
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name, "max_retry_attempts", self.max_retry_attempts.value()
            )

            logger.debug(f"Saved settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")

    def _on_setting_changed(self):
        """ Called when any setting changes to automatically save."""
        self._save_settings()

    def _on_quality_retry_toggled(self, checked: bool):
        """ Handle toggling of quality retry checkbox."""
        # Enable/disable max retry attempts based on quality retry setting
        self.max_retry_attempts.setEnabled(checked)

        # Update tooltip to clarify when disabled
        if checked:
            self.max_retry_attempts.setToolTip(
                "Maximum number of retry attempts with larger models when quality validation fails. "
                "0 = No retries (fastest), 1 = One retry (recommended), 2-3 = Multiple retries (slowest but highest quality)"
            )
        else:
            self.max_retry_attempts.setToolTip(
                "Disabled because automatic quality retry is turned off"
            )
