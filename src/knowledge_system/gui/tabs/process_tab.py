""" Process pipeline tab for comprehensive file processing with transcription, summarization, and MOC generation."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
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
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ..components.base_tab import BaseTab
from ..components.file_operations import FileOperationsMixin
from ..core.settings_manager import get_gui_settings_manager

logger = get_logger(__name__)


class ProcessPipelineWorker(QThread):
    """Worker thread for running the complete processing pipeline."""

    progress_updated = pyqtSignal(int, int, str)  # current, total, status
    file_completed = pyqtSignal(str, bool, str)  # file_path, success, message
    processing_finished = pyqtSignal(dict)  # final results
    processing_error = pyqtSignal(str)

    def __init__(self, files: Any, config: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.files = files
        self.config = config
        self.should_stop = False

    def run(self) -> None:
        """Run the complete processing pipeline."""
        try:
            results: dict[str, Any] = {
                "transcribed": [],
                "summarized": [],
                "moc_generated": [],
                "errors": [],
                "total_files": len(self.files),
                "claims_extracted": 0,
                "tier_a_claims": 0,
                "tier_b_claims": 0,
                "tier_c_claims": 0,
                "top_claims": [],
                "contradictions_found": 0,
                "relations_mapped": 0,
            }

            # Import processors and adapter
            from ...processors.audio_processor import AudioProcessor
            from ...processors.moc import MOCProcessor
            from ...processors.summarizer import SummarizerProcessor
            from ..adapters.hce_adapter import HCEAdapter

            # Initialize processors
            audio_processor = None
            summarizer_processor = None
            moc_processor = None
            hce_adapter = HCEAdapter()

            if self.config["transcribe"]:
                audio_processor = AudioProcessor(
                    device=self.config["device"],
                    model=self.config["transcription_model"],
                )

            if self.config["summarize"]:
                # Use HCE adapter to create summarizer with progress tracking
                summarizer_processor = hce_adapter.create_summarizer(
                    provider=self.config["summarization_provider"],
                    model=self.config["summarization_model"],
                    max_tokens=self.config["max_tokens"],
                )

            if self.config["moc"]:
                # Use HCE adapter to create MOC processor
                moc_processor = hce_adapter.create_moc_processor()

            # Track files for MOC generation
            moc_input_files = []

            # Process each file
            for i, file_path in enumerate(self.files):
                if self.should_stop:
                    break

                file_path_obj = Path(file_path)
                self.progress_updated.emit(
                    i + 1, len(self.files), f"Processing {file_path_obj.name}"
                )

                try:
                    # Step 1: Transcription (if enabled and file is audio/video)
                    transcript_path = None
                    if (
                        self.config["transcribe"]
                        and audio_processor
                        and file_path_obj.suffix.lower()
                        in [".mp4", ".mp3", ".wav", ".m4a", ".avi", ".mov", ".mkv"]
                    ):
                        try:
                            result = audio_processor.process(file_path_obj)
                            if result.success:
                                results["transcribed"].append(str(file_path_obj))
                                # Check for output file in result data
                                if hasattr(result, "data") and result.data:
                                    if (
                                        isinstance(result.data, dict)
                                        and "output_file" in result.data
                                    ):
                                        transcript_path = Path(
                                            result.data["output_file"]
                                        )
                                        moc_input_files.append(transcript_path)

                                self.file_completed.emit(
                                    str(file_path_obj),
                                    True,
                                    f"✅ Transcribed: {file_path_obj.name}",
                                )
                            else:
                                error_msg = (
                                    "; ".join(result.errors)
                                    if result.errors
                                    else "Unknown error"
                                )
                                results["errors"].append(
                                    f"Transcription failed for {file_path_obj}: {error_msg}"
                                )
                                self.file_completed.emit(
                                    str(file_path_obj),
                                    False,
                                    f"❌ Transcription failed: {error_msg}",
                                )
                        except Exception as e:
                            error_msg = f"Transcription error: {e}"
                            results["errors"].append(f"{file_path_obj}: {error_msg}")
                            self.file_completed.emit(
                                str(file_path_obj), False, f"❌ {error_msg}"
                            )

                    # Step 2: Summarization (if enabled and file is document/transcript)
                    if (
                        self.config["summarize"]
                        and summarizer_processor
                        and file_path_obj.suffix.lower() in [".pdf", ".txt", ".md"]
                    ):
                        # Use transcript if it was just created, otherwise use original file
                        summarize_file = (
                            transcript_path if transcript_path else file_path_obj
                        )

                        try:
                            # Process with HCE progress tracking
                            result = hce_adapter.process_with_progress(
                                summarizer_processor,
                                summarize_file,
                                progress_callback=lambda stage, pct: self.progress_updated.emit(
                                    i + 1,
                                    len(self.files),
                                    f"{file_path_obj.name}: {stage} ({pct}%)",
                                ),
                            )
                            if result.success:
                                results["summarized"].append(str(file_path_obj))

                                # Extract claim analytics from HCE data
                                if hasattr(result, "data") and result.data:
                                    if isinstance(result.data, dict):
                                        # Add summary file to MOC inputs
                                        if "output_file" in result.data:
                                            summary_path = Path(
                                                result.data["output_file"]
                                            )
                                            moc_input_files.append(summary_path)

                                        # Extract HCE claim data for analytics
                                        if "hce_data" in result.data:
                                            hce_data = result.data["hce_data"]
                                            if isinstance(hce_data, dict):
                                                # Count claims by tier
                                                claims = hce_data.get("claims", [])
                                                tier_a = tier_b = tier_c = 0
                                                top_file_claims = []

                                                for claim in claims:
                                                    if isinstance(claim, dict):
                                                        tier = claim.get("tier", "C")
                                                        canonical = claim.get(
                                                            "canonical", ""
                                                        )

                                                        if tier == "A":
                                                            tier_a += 1
                                                        elif tier == "B":
                                                            tier_b += 1
                                                        else:
                                                            tier_c += 1

                                                        # Collect top claims (A and B tier)
                                                        if (
                                                            tier in ["A", "B"]
                                                            and canonical
                                                        ):
                                                            top_file_claims.append(
                                                                {
                                                                    "claim": canonical,
                                                                    "tier": tier,
                                                                    "file": file_path_obj.name,
                                                                }
                                                            )

                                                # Update totals
                                                results["claims_extracted"] += len(
                                                    claims
                                                )
                                                results["tier_a_claims"] += tier_a
                                                results["tier_b_claims"] += tier_b
                                                results["tier_c_claims"] += tier_c

                                                # Add top claims (limit to prevent overflow)
                                                results["top_claims"].extend(
                                                    top_file_claims[:5]
                                                )

                                                # Count contradictions and relations
                                                contradictions = hce_data.get(
                                                    "contradictions", []
                                                )
                                                relations = hce_data.get(
                                                    "relations", []
                                                )
                                                results["contradictions_found"] += len(
                                                    contradictions
                                                )
                                                results["relations_mapped"] += len(
                                                    relations
                                                )

                                self.file_completed.emit(
                                    str(file_path_obj),
                                    True,
                                    f"✅ Analyzed: {file_path_obj.name}",
                                )
                            else:
                                error_msg = (
                                    "; ".join(result.errors)
                                    if result.errors
                                    else "Unknown error"
                                )
                                results["errors"].append(
                                    f"Summarization failed for {file_path_obj}: {error_msg}"
                                )
                                self.file_completed.emit(
                                    str(file_path_obj),
                                    False,
                                    f"❌ Summarization failed: {error_msg}",
                                )
                        except Exception as e:
                            error_msg = f"Summarization error: {e}"
                            results["errors"].append(f"{file_path_obj}: {error_msg}")
                            self.file_completed.emit(
                                str(file_path_obj), False, f"❌ {error_msg}"
                            )

                    # Add original file to MOC inputs if it's a text file
                    if file_path_obj.suffix.lower() in [".md", ".txt"]:
                        moc_input_files.append(file_path_obj)

                except Exception as e:
                    error_msg = f"Processing error: {e}"
                    results["errors"].append(f"{file_path_obj}: {error_msg}")
                    self.file_completed.emit(
                        str(file_path_obj), False, f"❌ {error_msg}"
                    )

            # Step 3: MOC Generation (if enabled and we have input files)
            if (
                self.config["moc"]
                and moc_processor
                and moc_input_files
                and not self.should_stop
            ):
                self.progress_updated.emit(
                    len(self.files), len(self.files), "Generating Maps of Content..."
                )

                try:
                    # Remove duplicates and filter existing files
                    unique_files = []
                    for file_path in moc_input_files:
                        if file_path.exists() and str(file_path) not in unique_files:
                            unique_files.append(str(file_path))

                    if unique_files:
                        # Process with HCE progress tracking
                        result = hce_adapter.process_with_progress(
                            moc_processor,
                            unique_files,
                            theme=self.config.get("moc_theme", "topical"),
                            depth=self.config.get("moc_depth", 3),
                            include_beliefs=self.config.get("include_beliefs", True),
                            progress_callback=lambda stage, pct: self.progress_updated.emit(
                                len(self.files),
                                len(self.files),
                                f"MOC Generation: {stage} ({pct}%)",
                            ),
                        )

                        if result.success:
                            results["moc_generated"] = unique_files
                            self.file_completed.emit(
                                "MOC Generation",
                                True,
                                f"✅ Generated MOC from {len(unique_files)} files",
                            )
                        else:
                            error_msg = (
                                "; ".join(result.errors)
                                if result.errors
                                else "Unknown error"
                            )
                            results["errors"].append(
                                f"MOC generation failed: {error_msg}"
                            )
                            self.file_completed.emit(
                                "MOC Generation",
                                False,
                                f"❌ MOC generation failed: {error_msg}",
                            )
                except Exception as e:
                    error_msg = f"MOC generation error: {e}"
                    results["errors"].append(error_msg)
                    self.file_completed.emit("MOC Generation", False, f"❌ {error_msg}")

            self.processing_finished.emit(results)

        except Exception as e:
            logger.error(f"Pipeline worker error: {e}")
            self.processing_error.emit(str(e))

    def stop(self) -> None:
        """Stop processing."""
        self.should_stop = True


class ProcessTab(BaseTab, FileOperationsMixin):
    """Tab for comprehensive file processing pipeline."""

    def __init__(self, parent: Any = None) -> None:
        # Initialize attributes before calling super() to prevent AttributeError
        self.processing_worker: ProcessPipelineWorker | None = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "Process Pipeline"

        # Now call super() which will call _setup_ui()
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """Setup the process pipeline UI."""
        # Create splitter for main layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(splitter)

        # Left side: Configuration
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Input files section
        input_section = self._create_input_section()
        left_layout.addWidget(input_section)

        # Processing options section
        options_section = self._create_processing_options_section()
        left_layout.addWidget(options_section)

        # Action buttons
        action_layout = self._create_action_layout_without_stop()
        left_layout.addLayout(action_layout)

        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # Right side: Progress and output
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Progress section
        progress_section = self._create_progress_section()
        right_layout.addWidget(progress_section)

        # Output section
        output_layout = self._create_output_section()
        right_layout.addLayout(
            output_layout, 1
        )  # Give stretch factor to allow expansion

        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setSizes([400, 600])

        # Load saved settings after UI is set up
        self._load_settings()

    def _create_input_section(self) -> QGroupBox:
        """Create the input files section."""
        input_group = self.create_file_input_section(
            "Input Files and Folders",
            "process_files",
            "All supported files (*.mp4 *.mp3 *.wav *.pdf *.txt *.md);;Audio/Video (*.mp4 *.mp3 *.wav *.m4a *.avi *.mov);;Documents (*.pdf *.txt *.md);;All files (*.*)",
        )
        return input_group

    def _create_processing_options_section(self) -> QGroupBox:
        """Create the processing options section with inherited settings."""
        group = QGroupBox("Processing Options")
        layout = QGridLayout()

        # Processing steps
        layout.addWidget(QLabel("Operations:"), 0, 0)

        self.transcribe_checkbox = QCheckBox("Transcribe audio/video files")
        self.transcribe_checkbox.setChecked(True)
        self.transcribe_checkbox.toggled.connect(self._on_setting_changed)
        self.transcribe_checkbox.setToolTip(
            "Enable transcription of audio and video files.\n"
            "• Uses Whisper AI for high-quality speech-to-text conversion\n"
            "• Supports multiple audio/video formats (MP3, MP4, WAV, M4A, etc.)\n"
            "• Settings are configured in the Audio Transcription tab\n"
            "• Outputs .txt files with transcribed text"
        )
        layout.addWidget(self.transcribe_checkbox, 0, 1)

        self.summarize_checkbox = QCheckBox("Summarize documents")
        self.summarize_checkbox.setChecked(True)
        self.summarize_checkbox.toggled.connect(self._on_setting_changed)
        self.summarize_checkbox.setToolTip(
            "Enable AI-powered summarization of documents and transcripts.\n"
            "• Works with .txt, .md, .pdf, and other text files\n"
            "• Uses OpenAI GPT or Anthropic Claude models\n"
            "• Settings are configured in the Document Summarization tab\n"
            "• Outputs .md files with intelligent summaries"
        )
        layout.addWidget(self.summarize_checkbox, 0, 2)

        self.moc_checkbox = QCheckBox("Generate Maps of Content")
        self.moc_checkbox.setChecked(True)
        self.moc_checkbox.toggled.connect(self._on_setting_changed)
        self.moc_checkbox.setToolTip(
            "Generate Maps of Content (MOCs) to organize knowledge.\n"
            "• Creates structured knowledge maps from processed content\n"
            "• Links related concepts and documents together\n"
            "• Useful for building comprehensive knowledge bases\n"
            "• Settings are configured in the Maps of Content tab"
        )
        layout.addWidget(self.moc_checkbox, 0, 3)

        # Settings inherited from other tabs (read-only display)
        layout.addWidget(QLabel("Settings (from individual tabs):"), 1, 0, 1, 4)

        # Transcription settings
        transcription_label = QLabel("Transcription:")
        transcription_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(transcription_label, 2, 0)

        self.transcription_settings_label = QLabel("Loading...")
        self.transcription_settings_label.setStyleSheet("color: #888;")
        layout.addWidget(self.transcription_settings_label, 2, 1, 1, 2)

        transcription_btn = QPushButton("Change")
        transcription_btn.clicked.connect(
            lambda: self._switch_to_tab("Audio Transcription")
        )
        transcription_btn.setMaximumWidth(80)
        transcription_btn.setToolTip(
            "Switch to Audio Transcription tab to modify transcription settings.\n"
            "• Configure Whisper model, device, and performance options\n"
            "• Set language, format, and quality retry settings"
        )
        layout.addWidget(transcription_btn, 2, 3)

        # Claim Analysis settings
        analysis_label = QLabel("Claim Analysis:")
        analysis_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(analysis_label, 3, 0)

        self.analysis_settings_label = QLabel("Loading...")
        self.analysis_settings_label.setStyleSheet("color: #888;")
        layout.addWidget(self.analysis_settings_label, 3, 1, 1, 2)

        analysis_btn = QPushButton("Change")
        analysis_btn.clicked.connect(lambda: self._switch_to_tab("Content Analysis"))
        analysis_btn.setMaximumWidth(80)
        analysis_btn.setToolTip(
            "Switch to Content Analysis tab to modify HCE claim extraction settings.\n"
            "• Choose AI provider (OpenAI, Anthropic, or Local)\n"
            "• Select model, claim tiers, and analysis depth\n"
            "• Configure contradiction and relationship analysis"
        )
        layout.addWidget(analysis_btn, 3, 3)

        # MOC settings
        moc_label = QLabel("MOC Generation:")
        moc_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(moc_label, 4, 0)

        self.moc_settings_label = QLabel("Loading...")
        self.moc_settings_label.setStyleSheet("color: #888;")
        layout.addWidget(self.moc_settings_label, 4, 1, 1, 2)

        moc_btn = QPushButton("Change")
        moc_btn.clicked.connect(lambda: self._switch_to_tab("Maps of Content"))
        moc_btn.setMaximumWidth(80)
        moc_btn.setToolTip(
            "Switch to Maps of Content tab to modify MOC generation settings.\n"
            "• Configure knowledge mapping and linking options\n"
            "• Set templates and organization preferences"
        )
        layout.addWidget(moc_btn, 4, 3)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Settings")
        refresh_btn.clicked.connect(self._refresh_inherited_settings)
        refresh_btn.setStyleSheet("background-color: #1976d2;")
        refresh_btn.setToolTip(
            "Refresh settings from other tabs.\n"
            "• Updates the displayed settings summary\n"
            "• Use this if you've changed settings in other tabs\n"
            "• Ensures you see the current configuration"
        )
        layout.addWidget(refresh_btn, 5, 0, 1, 2)

        # HCE Analysis Settings
        hce_label = QLabel("🔍 Analysis Settings:")
        hce_label.setStyleSheet("font-weight: bold; color: #1976d2;")
        layout.addWidget(hce_label, 6, 0)

        # Analysis Depth Slider
        depth_label = QLabel("Analysis Depth:")
        depth_label.setToolTip("Adjust the depth of claim extraction analysis")
        layout.addWidget(depth_label, 7, 0)

        from PyQt6.QtWidgets import QSlider

        self.analysis_depth_slider = QSlider()
        self.analysis_depth_slider.setOrientation(Qt.Orientation.Horizontal)
        self.analysis_depth_slider.setRange(1, 5)
        self.analysis_depth_slider.setValue(3)
        self.analysis_depth_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.analysis_depth_slider.setTickInterval(1)
        self.analysis_depth_slider.valueChanged.connect(self._on_setting_changed)
        self.analysis_depth_slider.setToolTip(
            "Analysis depth level (1-5):\n"
            "• 1: Quick extraction (surface-level claims)\n"
            "• 2: Standard extraction (key claims)\n"
            "• 3: Balanced extraction (recommended)\n"
            "• 4: Deep extraction (detailed claims)\n"
            "• 5: Comprehensive extraction (all possible claims)"
        )
        layout.addWidget(self.analysis_depth_slider, 7, 1, 1, 2)

        self.depth_value_label = QLabel("Balanced (3)")
        self.depth_value_label.setStyleSheet("color: #666;")
        layout.addWidget(self.depth_value_label, 7, 3)

        # Connect slider to update label
        self.analysis_depth_slider.valueChanged.connect(self._update_depth_label)

        # Claim Tier Selection
        tier_label = QLabel("Minimum Claim Tier:")
        tier_label.setToolTip("Select minimum tier of claims to include in results")
        layout.addWidget(tier_label, 8, 0)

        from PyQt6.QtWidgets import QComboBox

        self.claim_tier_combo = QComboBox()
        self.claim_tier_combo.addItems(["All Tiers", "Tier A+", "Tier B+", "Tier C+"])
        self.claim_tier_combo.setCurrentText("All Tiers")
        self.claim_tier_combo.currentTextChanged.connect(self._on_setting_changed)
        self.claim_tier_combo.setToolTip(
            "Minimum claim tier to include:\n"
            "• All Tiers: Include all confidence levels\n"
            "• Tier A+: High-confidence claims only (85%+)\n"
            "• Tier B+: Medium+ confidence claims (65%+)\n"
            "• Tier C+: All confidence levels (no filtering)"
        )
        layout.addWidget(self.claim_tier_combo, 8, 1, 1, 2)

        # Output directory
        layout.addWidget(QLabel("Output Directory:"), 9, 0)
        self.output_directory = QLineEdit()
        self.output_directory.setPlaceholderText(
            "Click Browse to select output directory (required)"
        )
        self.output_directory.textChanged.connect(self._on_setting_changed)
        self.output_directory.setToolTip(
            "Directory where all processed files will be saved.\n"
            "• Transcripts, summaries, and MOCs will be saved here\n"
            "• Organized in subdirectories by file type\n"
            "• Ensure you have write permissions to this location\n"
            "• Required before starting processing"
        )
        layout.addWidget(self.output_directory, 9, 1, 1, 2)

        browse_output_btn = QPushButton("Browse")
        browse_output_btn.clicked.connect(self._select_output_directory)
        browse_output_btn.setToolTip(
            "Browse and select the output directory for processed files.\n"
            "• Choose a directory with sufficient space\n"
            "• All output files will be organized in subdirectories"
        )
        layout.addWidget(browse_output_btn, 9, 3)

        # Load initial settings
        QTimer.singleShot(100, self._refresh_inherited_settings)

        group.setLayout(layout)
        return group

    def _create_action_layout_without_stop(self) -> QHBoxLayout:
        """Create action layout without stop button (ProcessTab has its own stop button)."""
        from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QPushButton

        layout = QHBoxLayout()

        # Start button
        self.start_btn = QPushButton(self._get_start_button_text())
        self.start_btn.clicked.connect(self._start_processing)
        self.start_btn.setStyleSheet("background-color: #4caf50; font-weight: bold;")
        self.start_btn.setToolTip(
            "Start the batch processing of all selected files.\n"
            "• Processes files according to selected operations (transcribe, summarize, MOC)\n"
            "• Uses settings from individual tabs\n"
            "• Shows real-time progress for each file\n"
            "• Can be paused or stopped at any time"
        )
        layout.addWidget(self.start_btn)

        # Dry run checkbox
        self.dry_run_checkbox = QCheckBox("Dry run (test without processing)")
        self.dry_run_checkbox.toggled.connect(self._on_setting_changed)
        self.dry_run_checkbox.setToolTip(
            "Test the processing pipeline without actually processing files.\n"
            "• Validates all settings and file accessibility\n"
            "• Shows what would be processed without consuming API credits\n"
            "• Useful for testing configurations before real processing\n"
            "• No output files will be created in dry run mode"
        )
        layout.addWidget(self.dry_run_checkbox)

        layout.addStretch()
        return layout

    def _create_progress_section(self) -> QGroupBox:
        """Create the progress tracking section."""
        group = QGroupBox("Processing Progress")
        layout = QVBoxLayout()

        # Overall progress bar
        self.overall_progress = QProgressBar()
        self.overall_progress.setVisible(False)
        layout.addWidget(self.overall_progress)

        # Status label
        self.status_label = QLabel("Ready to process")
        self.status_label.setStyleSheet("font-weight: bold; color: #333;")
        layout.addWidget(self.status_label)

        # File progress list with improved size policy
        self.file_progress_list = QListWidget()
        self.file_progress_list.setMinimumHeight(150)
        # Remove maximum height constraint to allow better resizing
        # self.file_progress_list.setMaximumHeight(200)  # This was causing layout issues
        from PyQt6.QtWidgets import QSizePolicy

        self.file_progress_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        layout.addWidget(self.file_progress_list)

        # Control buttons
        control_layout = QHBoxLayout()

        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setStyleSheet("background-color: #ff9800; font-weight: bold;")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setToolTip(
            "Pause or resume the processing pipeline.\n"
            "• Pauses after the current file finishes processing\n"
            "• No progress is lost when paused\n"
            "• Click again to resume processing\n"
            "• Useful for managing system resources"
        )
        control_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._stop_processing)
        self.stop_btn.setStyleSheet(
            "background-color: #d32f2f; color: white; font-weight: bold;"
        )
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip(
            "Stop the processing pipeline completely.\n"
            "• Stops after the current file finishes processing\n"
            "• All completed files will be saved\n"
            "• Unprocessed files remain in the list for later\n"
            "• Use this to cancel processing permanently"
        )
        control_layout.addWidget(self.stop_btn)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        group.setLayout(layout)
        return group

    def _switch_to_tab(self, tab_name: str):
        """Switch to the specified tab for changing settings."""
        # Get the parent tab widget and switch to the named tab
        parent = self.parent()
        if parent and hasattr(parent, "tabs"):
            for i in range(parent.tabs.count()):
                if parent.tabs.tabText(i) == tab_name:
                    parent.tabs.setCurrentIndex(i)
                    break

    def _refresh_inherited_settings(self):
        """Refresh the display of inherited settings from other tabs."""
        try:
            parent = self.parent()
            if not parent or not hasattr(parent, "tabs"):
                return

            # Get transcription settings
            transcription_tab = self._find_tab_by_name("Audio Transcription")
            if transcription_tab:
                device = getattr(transcription_tab, "device_combo", None)
                model = getattr(transcription_tab, "model_combo", None)
                if device and model:
                    self.transcription_settings_label.setText(
                        f"Model: {model.currentText()}, Device: {device.currentText()}"
                    )
                else:
                    self.transcription_settings_label.setText(
                        "Model: base, Device: auto"
                    )
            else:
                self.transcription_settings_label.setText("Model: base, Device: auto")

            # Get summarization settings
            summarization_tab = self._find_tab_by_name("Document Summarization")
            if summarization_tab:
                provider = getattr(summarization_tab, "provider_combo", None)
                model = getattr(summarization_tab, "model_combo", None)
                max_tokens = getattr(summarization_tab, "max_tokens_spin", None)
                if provider and model:
                    tokens_text = f", {max_tokens.value()} tokens" if max_tokens else ""
                    self.analysis_settings_label.setText(
                        f"{provider.currentText()}: {model.currentText()}{tokens_text}"
                    )
                else:
                    self.analysis_settings_label.setText(
                        "openai: gpt-4o-mini-2024-07-18"
                    )
            else:
                self.analysis_settings_label.setText("openai: gpt-4o-mini-2024-07-18")

            # MOC settings (using defaults since MOC tab was consolidated into Content Analysis)
            self.moc_settings_label.setText("Knowledge Map: Enabled (Default settings)")

        except Exception as e:
            logger.error(f"Error refreshing inherited settings: {e}")

    def _find_tab_by_name(self, tab_name: str):
        """Find a tab by its name."""
        try:
            parent = self.parent()
            if not parent or not hasattr(parent, "tabs"):
                return None

            for i in range(parent.tabs.count()):
                if parent.tabs.tabText(i) == tab_name:
                    return parent.tabs.widget(i)
            return None
        except Exception:
            return None

    def _get_inherited_config(self):
        """Get configuration from other tabs."""
        config = {}

        # Get transcription settings
        transcription_tab = self._find_tab_by_name("Audio Transcription")
        if transcription_tab:
            config["device"] = getattr(transcription_tab, "device_combo", None)
            config["device"] = (
                config["device"].currentText() if config["device"] else "auto"
            )
            config["transcription_model"] = getattr(
                transcription_tab, "model_combo", None
            )
            config["transcription_model"] = (
                config["transcription_model"].currentText()
                if config["transcription_model"]
                else "base"
            )
        else:
            config["device"] = "auto"
            config["transcription_model"] = "base"

        # Get summarization settings
        summarization_tab = self._find_tab_by_name("Document Summarization")
        if summarization_tab:
            provider = getattr(summarization_tab, "provider_combo", None)
            model = getattr(summarization_tab, "model_combo", None)
            max_tokens = getattr(summarization_tab, "max_tokens_spin", None)

            config["summarization_provider"] = (
                provider.currentText() if provider else "openai"
            )
            config["summarization_model"] = (
                model.currentText() if model else "gpt-4o-mini-2024-07-18"
            )
            config["max_tokens"] = max_tokens.value() if max_tokens else 1000
        else:
            config["summarization_provider"] = "openai"
            config["summarization_model"] = "gpt-4o-mini-2024-07-18"
            config["max_tokens"] = 1000

        # Get MOC settings
        moc_tab = self._find_tab_by_name("Maps of Content")
        if moc_tab:
            depth = getattr(moc_tab, "depth_spin", None)
            beliefs = getattr(moc_tab, "beliefs_checkbox", None)

            config["moc_depth"] = depth.value() if depth else 3
            config["include_beliefs"] = beliefs.isChecked() if beliefs else True
        else:
            config["moc_depth"] = 3
            config["include_beliefs"] = True

        return config

    # _update_summarization_models removed - settings now inherited from other tabs

    def _select_output_directory(self) -> None:
        """Select output directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", "", QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self.output_directory.setText(directory)

    def _clear_progress(self) -> None:
        """Clear the progress display."""
        self.file_progress_list.clear()
        self.overall_progress.setVisible(False)
        self.status_label.setText("Ready to process")

    def _toggle_pause(self) -> None:
        """Toggle pause/resume processing."""
        if self.processing_worker and self.processing_worker.isRunning():
            # Toggle pause state (implementation would depend on worker)
            if hasattr(self.processing_worker, "paused"):
                self.processing_worker.paused = not self.processing_worker.paused
                if self.processing_worker.paused:
                    self.pause_btn.setText("▶ Resume")
                    self.pause_btn.setStyleSheet(
                        "background-color: #4caf50; font-weight: bold;"
                    )
                    self.append_log("⏸ Processing paused")
                else:
                    self.pause_btn.setText("⏸ Pause")
                    self.pause_btn.setStyleSheet(
                        "background-color: #ff9800; font-weight: bold;"
                    )
                    self.append_log("▶ Processing resumed")
            else:
                self.append_log("⚠ Pause/resume not supported by current worker")

    def _stop_processing(self) -> None:
        """Stop the current processing operation."""
        if self.processing_worker:
            self.processing_worker.should_stop = True
            self.append_log("⏹ Stopping processing...")

        # Reset UI state
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸ Pause")
        self.pause_btn.setStyleSheet("background-color: #ff9800; font-weight: bold;")

    def _get_start_button_text(self) -> str:
        return "Start Processing Pipeline"

    def _start_processing(self) -> None:
        """Start the processing pipeline."""
        # Validate inputs
        if not self.validate_file_selection("process_files", 1):
            return

        # Check that output directory is selected
        output_dir = self.output_directory.text().strip()
        if not output_dir:
            self.show_warning(
                "No Output Directory",
                "Please select an output directory before starting processing.",
            )
            return

        if not Path(output_dir).exists():
            self.show_warning(
                "Invalid Output Directory",
                f"Output directory does not exist: {output_dir}",
            )
            return

        if not Path(output_dir).is_dir():
            self.show_warning(
                "Invalid Output Directory",
                f"Output directory is not a directory: {output_dir}",
            )
            return

        # Get configuration from checkboxes and inherited settings
        inherited_config = self._get_inherited_config()
        config = {
            "transcribe": self.transcribe_checkbox.isChecked(),
            "summarize": self.summarize_checkbox.isChecked(),
            "moc": self.moc_checkbox.isChecked(),
            "output_directory": output_dir,  # Use validated output directory
        }
        # Merge inherited configuration
        config.update(inherited_config)
        # Add default MOC theme
        config["moc_theme"] = "topical"  # Default theme, can be customized in prompts

        # Check that at least one operation is enabled
        if not (config["transcribe"] or config["summarize"] or config["moc"]):
            self.show_warning(
                "No Operations", "Please enable at least one processing operation"
            )
            return

        # Get files to process
        files = self.get_selected_files("process_files")

        # Clear previous progress
        self._clear_progress()

        # Start processing worker
        self.processing_worker = ProcessPipelineWorker(files, config)
        self.processing_worker.progress_updated.connect(self._update_progress)
        self.processing_worker.file_completed.connect(self._file_completed)
        self.processing_worker.processing_finished.connect(self._processing_finished)
        self.processing_worker.processing_error.connect(self._processing_error)

        self.active_workers.append(self.processing_worker)
        self.processing_worker.start()

        # Update UI
        self.set_processing_state(True)
        self.stop_btn.setEnabled(True)
        self.overall_progress.setVisible(True)
        self.overall_progress.setMaximum(len(files))
        self.overall_progress.setValue(0)

        self.append_log(f"Started processing {len(files)} files with configuration:")
        self.append_log(f"  Transcribe: {config['transcribe']}")
        self.append_log(f"  Summarize: {config['summarize']}")
        self.append_log(f"  Generate MOC: {config['moc']}")
        if config["transcribe"]:
            self.append_log(f"  Transcription model: {config['transcription_model']}")
        if config["summarize"]:
            self.append_log(
                f"  Summarization: {config['summarization_provider']} {config['summarization_model']}"
            )

    def _update_progress(self, current: int, total: int, status: str) -> None:
        """Update progress display."""
        self.overall_progress.setValue(current)
        self.overall_progress.setMaximum(total)
        self.status_label.setText(status)

    def _file_completed(self, file_path: str, success: bool, message: str):
        """Handle file completion."""
        self.file_progress_list.addItem(message)
        # Scroll to bottom
        self.file_progress_list.scrollToBottom()
        self.append_log(message)

    def _processing_finished(self, results: dict[str, Any]) -> None:
        """Handle processing completion."""
        self.set_processing_state(False)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Processing completed")

        # Show summary
        self.append_log("\n=== Processing Summary ===")
        self.append_log(f"📁 Total files: {results['total_files']}")
        self.append_log(f"🎤 Transcribed: {len(results['transcribed'])}")
        self.append_log(f"🔍 Analyzed: {len(results['summarized'])}")

        # HCE Claim Analytics
        if results.get("claims_extracted", 0) > 0:
            self.append_log(f"\n📊 Claim Extraction Results:")
            self.append_log(
                f"   • Total claims extracted: {results['claims_extracted']}"
            )
            if results.get("tier_a_claims", 0) > 0:
                self.append_log(
                    f"   • Tier A claims (high confidence): {results['tier_a_claims']}"
                )
            if results.get("tier_b_claims", 0) > 0:
                self.append_log(
                    f"   • Tier B claims (medium confidence): {results['tier_b_claims']}"
                )
            if results.get("tier_c_claims", 0) > 0:
                self.append_log(
                    f"   • Tier C claims (supporting): {results['tier_c_claims']}"
                )

            if results.get("contradictions_found", 0) > 0:
                self.append_log(
                    f"   • Contradictions identified: {results['contradictions_found']}"
                )
            if results.get("relations_mapped", 0) > 0:
                self.append_log(f"   • Relations mapped: {results['relations_mapped']}")

            # Show top claims
            top_claims = results.get("top_claims", [])
            if top_claims:
                self.append_log(f"\n🏆 Top Claims:")
                for i, claim_info in enumerate(top_claims[:5]):  # Show max 5
                    tier_icon = "🥇" if claim_info["tier"] == "A" else "🥈"
                    self.append_log(
                        f"   {tier_icon} [{claim_info['file']}] {claim_info['claim'][:100]}{'...' if len(claim_info['claim']) > 100 else ''}"
                    )

        if results["moc_generated"]:
            self.append_log(
                f"🗺️ MOC generated from: {len(results['moc_generated'])} files"
            )
        if results["errors"]:
            self.append_log(f"\n❌ Errors: {len(results['errors'])}")
            for error in results["errors"]:
                self.append_log(f"     - {error}")
        self.append_log("=== End Summary ===")

        # Show completion message
        claims_count = results.get("claims_extracted", 0)
        if results["errors"]:
            message = f"Processed {results['total_files']} files with {len(results['errors'])} errors."
            if claims_count > 0:
                message += f" Extracted {claims_count} claims total."
            message += " Check the output log for details."
            self.show_info("Processing Completed with Errors", message)
        else:
            message = f"Successfully processed all {results['total_files']} files!"
            if claims_count > 0:
                tier_a = results.get("tier_a_claims", 0)
                message += (
                    f" Extracted {claims_count} claims ({tier_a} high-confidence)."
                )
            self.show_info("Processing Completed Successfully", message)

    def _processing_error(self, error: str) -> None:
        """Handle processing error."""
        self.set_processing_state(False)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Processing failed")
        self.append_log(f"❌ Processing failed: {error}")
        self.show_error("Processing Error", f"Processing failed: {error}")

    def validate_inputs(self) -> bool:
        """Validate inputs before processing."""
        return self.validate_file_selection("process_files", 1)

    def _load_settings(self) -> None:
        """Load saved settings from session."""
        try:
            # Block signals during loading to prevent redundant saves
            widgets_to_block = [
                self.output_directory,
                self.transcribe_checkbox,
                self.summarize_checkbox,
                self.moc_checkbox,
                self.dry_run_checkbox,
            ]

            # Block all signals
            for widget in widgets_to_block:
                widget.blockSignals(True)

            try:
                # Load output directory
                saved_output_dir = self.gui_settings.get_output_directory(
                    self.tab_name, ""
                )
                self.output_directory.setText(saved_output_dir)

                # Load checkbox states
                self.transcribe_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "transcribe", True
                    )
                )
                self.summarize_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "summarize", True
                    )
                )
                self.moc_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(self.tab_name, "moc", True)
                )
                self.dry_run_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "dry_run", False
                    )
                )

            finally:
                # Always restore signals
                for widget in widgets_to_block:
                    widget.blockSignals(False)

            logger.debug(f"Loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")

    def _save_settings(self) -> None:
        """Save current settings to session."""
        try:
            # Save output directory
            self.gui_settings.set_output_directory(
                self.tab_name, self.output_directory.text()
            )

            # Save checkbox states
            self.gui_settings.set_checkbox_state(
                self.tab_name, "transcribe", self.transcribe_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "summarize", self.summarize_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "moc", self.moc_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "dry_run", self.dry_run_checkbox.isChecked()
            )

            logger.debug(f"Saved settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")

    def _on_setting_changed(self) -> None:
        """Called when any setting changes to automatically save."""
        self._save_settings()

    def _update_depth_label(self, value: int) -> None:
        """Update the analysis depth label based on slider value."""
        depth_labels = {
            1: "Quick (1)",
            2: "Standard (2)",
            3: "Balanced (3)",
            4: "Deep (4)",
            5: "Comprehensive (5)",
        }
        self.depth_value_label.setText(depth_labels.get(value, f"Level {value}"))
