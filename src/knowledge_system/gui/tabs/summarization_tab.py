"""Content analysis tab for document analysis using AI models with various analysis types."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from ...logger import get_logger
from ...utils.ollama_manager import get_ollama_manager
from ..components.base_tab import BaseTab
from ..core.settings_manager import get_gui_settings_manager
from ..dialogs import ModelDownloadDialog, OllamaServiceDialog

logger = get_logger(__name__)


class EnhancedSummarizationWorker(QThread):
    """Enhanced worker thread for summarization with real-time progress dialog."""

    progress_updated = pyqtSignal(object)  # SummarizationProgress
    file_completed = pyqtSignal(int, int)  # current, total
    processing_finished = pyqtSignal(
        int, int, int
    )  # success_count, failure_count, total_count
    processing_error = pyqtSignal(str)

    def __init__(self, files, settings, gui_settings, parent=None) -> None:
        super().__init__(parent)
        self.files = files
        self.settings = settings
        self.gui_settings = gui_settings
        self.progress_dialog = None
        self.should_stop = False
        # Create cancellation token for proper cancellation handling
        from ...utils.cancellation import CancellationToken

        self.cancellation_token = CancellationToken()

    def run(self):
        """Run the summarization process."""
        try:
            from datetime import datetime
            from pathlib import Path

            from ...processors.summarizer import SummarizerProcessor
            from ...utils.file_io import overwrite_or_insert_summary_section
            from ...utils.ollama_manager import get_ollama_manager
            from ...utils.progress import SummarizationProgress

            provider = self.gui_settings.get("provider", "openai")
            model = self.gui_settings.get("model", "gpt-4o-mini-2024-07-18")

            # Strip both "(Installed)" and "(X GB)" suffixes to get clean model name
            clean_model_name = model.replace(" (Installed)", "")
            # Remove size suffix pattern like " (4 GB)"
            import re

            clean_model_name = re.sub(r" \(\d+ GB\)$", "", clean_model_name)

            # Double-check Ollama service for local provider (in case it stopped between GUI check and worker execution)
            if provider == "local":
                ollama_manager = get_ollama_manager()
                if not ollama_manager.is_service_running():
                    self.processing_error.emit(
                        "Ollama service is not running. Please start Ollama service first using the Hardware tab or by running 'ollama serve' in your terminal."
                    )
                    return

                # Also check if model is available (use clean name)
                if not ollama_manager.is_model_available(clean_model_name):
                    self.processing_error.emit(
                        f"Model '{clean_model_name}' is not available in Ollama. Please download the model first using the Hardware tab or by running 'ollama pull {clean_model_name}'."
                    )
                    return

            # Create processor with GUI settings (use clean model name)
            processor = SummarizerProcessor(
                provider=provider,
                model=clean_model_name,
                max_tokens=self.gui_settings.get("max_tokens", 10000),
            )

            # Get output directory (if not updating in-place)
            output_dir = None
            if not self.gui_settings.get("update_in_place", False):
                output_dir = Path(self.gui_settings.get("output_dir", ""))
                if output_dir:
                    output_dir.mkdir(parents=True, exist_ok=True)

            # Build index if not forcing re-summarization
            summary_index = {}
            skipped_files = []
            force_regenerate = self.gui_settings.get("force_regenerate", False)

            if output_dir and not force_regenerate:
                summary_index = processor._build_summary_index(output_dir)

                # Check each file
                files_to_process = []
                for file_path in self.files:
                    file_path_obj = Path(file_path)
                    needs_summary, reason = processor._check_needs_summarization(
                        file_path_obj, summary_index
                    )
                    if not needs_summary:
                        skipped_files.append((file_path, reason))
                        # Emit progress for skipped file
                        skip_progress = SummarizationProgress(
                            current_file=file_path,
                            total_files=len(self.files),
                            completed_files=len(skipped_files),
                            current_step=f"⏭️ Skipping: {reason}",
                            percent=(len(skipped_files) / len(self.files)) * 100.0,
                            status="skipped_unchanged",
                            provider=self.gui_settings.get("provider", "openai"),
                            model_name=self.gui_settings.get(
                                "model", "gpt-4o-mini-2024-07-18"
                            ),
                        )
                        self.progress_updated.emit(skip_progress)
                    else:
                        files_to_process.append(file_path)

                # Update files list to only process needed files
                if skipped_files:
                    self.progress_updated.emit(
                        SummarizationProgress(
                            current_step=f"⏭️ Skipped {len(skipped_files)} unchanged files",
                            percent=0.0,
                            status="skipping_complete",
                            provider=self.gui_settings.get("provider", "openai"),
                            model_name=self.gui_settings.get(
                                "model", "gpt-4o-mini-2024-07-18"
                            ),
                        )
                    )
                    self.files = files_to_process

            success_count = 0
            failure_count = 0
            total_count = len(self.files)

            # Calculate character-based progress weighting for accurate ETAs
            file_sizes = []
            total_characters = 0
            characters_completed = 0

            # Get file sizes for character-weighted progress
            for file_path in self.files:
                try:
                    file_size = Path(file_path).stat().st_size
                    file_sizes.append(file_size)
                    total_characters += file_size
                except Exception:
                    # Fallback for files we can't read
                    estimated_size = 10000  # 10KB default estimate
                    file_sizes.append(estimated_size)
                    total_characters += estimated_size

            logger.info(
                f"📊 Batch character analysis: {len(self.files)} files, {total_characters:,} total characters"
            )
            for i, file_path in enumerate(self.files):
                file_name = Path(file_path).name
                size_kb = file_sizes[i] / 1024
                weight_pct = (file_sizes[i] / total_characters) * 100
                logger.info(
                    f"  📄 {file_name}: {size_kb:.1f}KB ({weight_pct:.1f}% of batch)"
                )

            for i, file_path in enumerate(self.files):
                if self.should_stop:
                    self.processing_error.emit("Processing was cancelled by user")
                    return

                file_path_obj = Path(file_path)
                current_file_size = file_sizes[i]

                # Character-based batch progress calculation
                batch_progress_start = (characters_completed / total_characters) * 100.0

                # Create enhanced progress object with character-weighted batch progress
                progress = SummarizationProgress(
                    current_file=file_path,
                    total_files=len(self.files),
                    completed_files=i,
                    current_step=f"📄 Starting {file_path_obj.name} ({i+1}/{len(self.files)}) - {current_file_size/1024:.1f}KB",
                    percent=batch_progress_start,
                    provider=self.gui_settings.get("provider", "openai"),
                    model_name=self.gui_settings.get("model", "gpt-4o-mini-2024-07-18"),
                )

                # Add character-based batch information
                progress.total_characters = total_characters
                progress.characters_completed = characters_completed
                progress.current_file_size = current_file_size

                self.progress_updated.emit(progress)

                # Process the file
                template_path = self.gui_settings.get("template_path", None)
                if template_path:
                    template_path = Path(template_path)
                    if not template_path.exists():
                        template_path = None

                # Create enhanced progress callback with character-based tracking
                def enhanced_progress_callback(p):
                    """Enhanced progress callback with character-based batch tracking."""
                    # Add batch progress context to the progress object
                    if hasattr(p, "__dict__"):
                        # File-level information
                        p.total_files = len(self.files)
                        p.completed_files = i  # Files completed so far
                        p.current_file = file_path

                        # Character-based progress calculation
                        p.total_characters = total_characters
                        p.current_file_size = current_file_size

                        # Handle character progress based on processing status
                        if hasattr(p, "status") and p.status == "completed":
                            # File completed - mark all characters as done
                            current_file_chars_done = current_file_size
                        elif (
                            hasattr(p, "status")
                            and p.status in ["chunk_completed", "processing_chunks"]
                            and hasattr(p, "chunk_number")
                            and hasattr(p, "total_chunks")
                            and p.total_chunks
                        ):
                            # Chunking: progress based on completed chunks
                            chunks_completed = (
                                getattr(p, "chunk_number", 1) - 1
                            )  # chunk_number is 1-based
                            if p.status == "chunk_completed":
                                chunks_completed = getattr(
                                    p, "chunk_number", 1
                                )  # Include current chunk as completed
                            current_file_chars_done = (
                                chunks_completed / p.total_chunks
                            ) * current_file_size
                        else:
                            # File still in progress - no characters completed yet
                            current_file_chars_done = 0

                        # Total characters completed (previous files + current file completion)
                        p.characters_completed = (
                            characters_completed + current_file_chars_done
                        )

                        # Note: batch_percent_characters is auto-calculated in __post_init__
                        # Keep individual file progress in percent field
                        # p.percent already contains the file-level progress

                    self.progress_updated.emit(p)

                # Check for cancellation before processing each file
                if self.should_stop:
                    logger.info("Stopping summarization as requested")
                    self.cancellation_token.cancel("User requested stop")
                    break

                result = processor.process(
                    file_path_obj,
                    style=self.gui_settings.get("style", "general"),
                    prompt_template=template_path,
                    progress_callback=enhanced_progress_callback,
                    cancellation_token=self.cancellation_token,
                )

                if result.success:
                    # File completed successfully - update character counter
                    characters_completed += current_file_size

                    # Save the summary to file
                    try:
                        if (
                            self.gui_settings.get("update_in_place", False)
                            and file_path_obj.suffix.lower() == ".md"
                        ):
                            # Update existing .md file in-place
                            overwrite_or_insert_summary_section(
                                file_path_obj, result.data
                            )
                            self.progress_updated.emit(
                                SummarizationProgress(
                                    current_file=file_path,
                                    total_files=len(self.files),
                                    completed_files=i + 1,
                                    current_step=f"✅ Updated summary in-place: {file_path_obj.name}",
                                    percent=100.0,  # Individual file complete
                                    total_characters=total_characters,
                                    characters_completed=characters_completed,
                                    provider=self.gui_settings.get(
                                        "provider", "openai"
                                    ),
                                    model_name=self.gui_settings.get(
                                        "model", "gpt-4o-mini-2024-07-18"
                                    ),
                                )
                            )
                        else:
                            # Create new summary file
                            # Clean filename by removing hyphens for better readability
                            clean_filename = file_path_obj.stem.replace("-", "_")
                            if not output_dir:
                                # Fallback: create summary next to original file
                                output_file = (
                                    file_path_obj.parent
                                    / f"{clean_filename}_summary.md"
                                )
                            else:
                                output_file = (
                                    output_dir / f"{clean_filename}_summary.md"
                                )

                            # Ensure output directory exists
                            output_file.parent.mkdir(parents=True, exist_ok=True)

                            # Extract thumbnail from original file and prepare YAML metadata
                            metadata = result.metadata or {}
                            thumbnail_content = self._extract_thumbnail_from_file(
                                file_path_obj
                            )

                            # Copy thumbnail image file if it exists and update reference
                            (
                                thumbnail_copied,
                                updated_thumbnail_content,
                            ) = self._copy_thumbnail_file_and_update_reference(
                                file_path_obj, output_file, thumbnail_content
                            )
                            if thumbnail_copied:
                                thumbnail_content = updated_thumbnail_content

                            with open(output_file, "w", encoding="utf-8") as f:
                                # Write YAML frontmatter
                                f.write("---\n")
                                # Clean filename for title by removing hyphens and file extension
                                clean_filename = file_path_obj.stem.replace("-", " ")
                                f.write(f'title: "Summary of {clean_filename}"\n')
                                f.write(f'source_file: "{file_path_obj.name}"\n')
                                f.write(f'source_path: "{file_path_obj.absolute()}"\n')
                                f.write(
                                    f"model: \"{self.gui_settings.get('model', 'gpt-4o-mini-2024-07-18')}\"\n"
                                )
                                f.write(
                                    f"provider: \"{metadata.get('provider', self.gui_settings.get('provider', 'unknown'))}\"\n"
                                )

                                if self.gui_settings.get("template_path"):
                                    f.write(
                                        f"template: \"{self.gui_settings.get('template_path')}\"\n"
                                    )

                                # Performance metadata
                                processing_time = metadata.get("processing_time", 0)
                                f.write(f"processing_time: {processing_time:.1f}\n")

                                prompt_tokens = metadata.get("prompt_tokens", 0)
                                completion_tokens = metadata.get("completion_tokens", 0)
                                total_tokens = metadata.get("total_tokens", 0)
                                f.write(f"prompt_tokens: {prompt_tokens}\n")
                                f.write(f"completion_tokens: {completion_tokens}\n")
                                f.write(f"total_tokens: {total_tokens}\n")

                                tokens_per_second = metadata.get("tokens_per_second", 0)
                                f.write(
                                    f"speed_tokens_per_second: {tokens_per_second:.1f}\n"
                                )

                                # Content analysis metadata
                                input_length = metadata.get("input_length", 0)
                                summary_length = len(result.data) if result.data else 0
                                f.write(f"input_length: {input_length}\n")
                                f.write(f"summary_length: {summary_length}\n")

                                compression_ratio = metadata.get("compression_ratio", 0)
                                reduction_percent = (
                                    (1 - compression_ratio) * 100
                                    if compression_ratio > 0
                                    else 0
                                )
                                f.write(
                                    f"compression_reduction_percent: {reduction_percent:.1f}\n"
                                )

                                # Add chunking info if available
                                if metadata.get("chunks_processed"):
                                    f.write(
                                        f"chunks_processed: {metadata.get('chunks_processed')}\n"
                                    )
                                    if metadata.get("chunking_summary"):
                                        f.write(
                                            f"chunking_strategy: \"{metadata.get('chunking_summary')}\"\n"
                                        )

                                f.write(f'generated: "{datetime.now().isoformat()}"\n')
                                f.write("---\n\n")

                                # Add thumbnail if found
                                if thumbnail_content:
                                    f.write(thumbnail_content + "\n\n")

                                # Write the actual summary content
                                # Clean filename for title by removing hyphens and file extension
                                clean_filename = file_path_obj.stem.replace("-", " ")
                                f.write(f"# Summary of {clean_filename}\n\n")
                                f.write(result.data)

                            self.progress_updated.emit(
                                SummarizationProgress(
                                    current_file=file_path,
                                    total_files=len(self.files),
                                    completed_files=i + 1,
                                    current_step=f"✅ Summary saved: {output_file.name}",
                                    percent=100.0,  # Individual file complete
                                    total_characters=total_characters,
                                    characters_completed=characters_completed,
                                    provider=self.gui_settings.get(
                                        "provider", "openai"
                                    ),
                                    model_name=self.gui_settings.get(
                                        "model", "gpt-4o-mini-2024-07-18"
                                    ),
                                )
                            )

                    except Exception as save_error:
                        self.processing_error.emit(
                            f"Failed to save summary for {file_path_obj.name}: {save_error}"
                        )
                        failure_count += 1
                        continue

                    success_count += 1
                else:
                    # Handle processing failure - still update character counter for batch ETA accuracy
                    characters_completed += current_file_size

                    error_msg = (
                        "; ".join(result.errors) if result.errors else "Unknown error"
                    )
                    self.progress_updated.emit(
                        SummarizationProgress(
                            current_file=file_path,
                            total_files=len(self.files),
                            completed_files=i + 1,
                            current_step=f"❌ Failed: {error_msg}",
                            percent=100.0,  # Individual file complete (even if failed)
                            total_characters=total_characters,
                            characters_completed=characters_completed,
                            provider=self.gui_settings.get("provider", "openai"),
                            model_name=self.gui_settings.get(
                                "model", "gpt-4o-mini-2024-07-18"
                            ),
                        )
                    )
                    failure_count += 1

                self.file_completed.emit(i + 1, len(self.files))

            self.processing_finished.emit(success_count, failure_count, total_count)

        except Exception as e:
            # Import CancellationError to handle cancellation properly
            from ...utils.cancellation import CancellationError

            if isinstance(e, CancellationError):
                logger.info(f"Summarization cancelled: {e}")
                # Don't emit this as an error - it's a normal cancellation
                self.processing_finished.emit(
                    success_count, failure_count, len(self.files)
                )
            else:
                logger.error(f"Summarization error: {e}")
                self.processing_error.emit(str(e))

    def stop(self):
        """Stop the summarization process."""
        logger.info("EnhancedSummarizationWorker.stop() called")
        self.should_stop = True
        if hasattr(self, "cancellation_token") and self.cancellation_token:
            self.cancellation_token.cancel("User requested cancellation")

    def _extract_thumbnail_from_file(self, file_path: Path) -> str:
        """
        Extract thumbnail content from the original markdown file.

        Looks for thumbnail images in various formats:
        - ![thumbnail](path/to/image)
        - ![](path/to/thumbnail.jpg)
        - References to Thumbnails/ directories

        Args:
            file_path: Path to the original markdown file

        Returns:
            Thumbnail markdown content if found, empty string otherwise
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Look for thumbnail patterns in the first 2000 characters (usually at top of file)
            search_content = content[:2000]

            # Pattern 1: ![thumbnail](path) or ![](path/thumbnail.ext)
            import re

            thumbnail_patterns = [
                r"!\[thumbnail[^\]]*\]\([^)]+\)",  # ![thumbnail](path)
                r"!\[[^\]]*\]\([^)]*[Tt]humbnail[^)]*\)",  # ![anything](path/thumbnail/path)
                r"!\[[^\]]*\]\([^)]*[Tt]humbnails?/[^)]+\)",  # ![](Thumbnails/file.jpg)
                r"!\[[^\]]*\]\([^)]*\.(?:jpg|jpeg|png|gif|webp)[^)]*\)",  # Any image file
            ]

            for pattern in thumbnail_patterns:
                matches = re.findall(pattern, search_content, re.IGNORECASE)
                if matches:
                    # Return the first thumbnail found
                    return matches[0]

            # Pattern 2: Look for references to Thumbnails directory
            thumbnails_match = re.search(
                r"(Thumbnails?/[^\s\]]+\.(?:jpg|jpeg|png|gif|webp))",
                search_content,
                re.IGNORECASE,
            )
            if thumbnails_match:
                thumbnail_path = thumbnails_match.group(1)
                return f"![thumbnail]({thumbnail_path})"

            return ""

        except Exception as e:
            logger.debug(f"Could not extract thumbnail from {file_path}: {e}")
            return ""

    def _copy_thumbnail_file_and_update_reference(
        self, source_file: Path, output_file: Path, original_thumbnail_content: str
    ) -> tuple[bool, str]:
        """
        Copy thumbnail image file from source directory to output Thumbnails subdirectory and update reference.

        Args:
            source_file: Path to the source markdown file
            output_file: Path to the output summary file
            original_thumbnail_content: Original thumbnail markdown content

        Returns:
            Tuple of (success_flag, updated_thumbnail_content)
        """
        try:
            import re
            import shutil

            # Read source file to find thumbnail references
            with open(source_file, encoding="utf-8") as f:
                content = f.read()

            # Look for thumbnail paths in the first 2000 characters
            search_content = content[:2000]

            # Extract thumbnail file paths from markdown
            thumbnail_path_patterns = [
                r"!\[[^\]]*\]\(([^)]*[Tt]humbnails?/[^)]+\.(?:jpg|jpeg|png|gif|webp))[^)]*\)",  # ![](Thumbnails/file.jpg)
                r"!\[[^\]]*\]\(([^)]*\.(?:jpg|jpeg|png|gif|webp))[^)]*\)",  # ![](any_image.jpg)
            ]

            for pattern in thumbnail_path_patterns:
                matches = re.findall(pattern, search_content, re.IGNORECASE)
                for thumbnail_path in matches:
                    # Resolve thumbnail path relative to source file
                    source_thumbnail = source_file.parent / thumbnail_path

                    if source_thumbnail.exists():
                        # Create Thumbnails subdirectory in output location
                        output_thumbnails_dir = output_file.parent / "Thumbnails"
                        output_thumbnails_dir.mkdir(exist_ok=True)

                        # Copy thumbnail to output Thumbnails directory
                        thumbnail_filename = source_thumbnail.name
                        output_thumbnail = output_thumbnails_dir / thumbnail_filename

                        shutil.copy2(source_thumbnail, output_thumbnail)
                        logger.info(
                            f"Copied thumbnail: {source_thumbnail} → {output_thumbnail}"
                        )

                        # Update thumbnail reference to point to Thumbnails subdirectory
                        updated_content = (
                            f"![thumbnail](Thumbnails/{thumbnail_filename})"
                        )
                        return True, updated_content
                    else:
                        logger.debug(f"Thumbnail file not found: {source_thumbnail}")

            return False, original_thumbnail_content

        except Exception as e:
            logger.debug(f"Could not copy thumbnail from {source_file}: {e}")
            return False, original_thumbnail_content


class SummarizationTab(BaseTab):
    """Tab for document summarization using AI models."""

    def __init__(self, parent=None) -> None:
        self.summarization_worker = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "Content Analysis"
        super().__init__(parent)

    def _setup_ui(self):
        """Setup the summarization UI."""
        layout = QVBoxLayout(self)

        # Input section
        input_group = QGroupBox("Input Documents")
        input_layout = QVBoxLayout()

        # Add supported file types info
        supported_types_label = QLabel(
            "📁 Supported formats: PDF (.pdf), Text (.txt), Markdown (.md), HTML (.html, .htm), JSON (.json)"
        )
        supported_types_label.setStyleSheet(
            "color: #666; font-style: italic; margin-bottom: 8px;"
        )
        supported_types_label.setWordWrap(True)
        input_layout.addWidget(supported_types_label)

        # File list
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(150)
        input_layout.addWidget(self.file_list)

        # File buttons
        button_layout = QHBoxLayout()
        add_files_btn = QPushButton("Add Files")
        add_files_btn.clicked.connect(self._add_files)
        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.clicked.connect(self._add_folder)
        clear_btn = QPushButton("🗑️ Clear All Files")
        clear_btn.clicked.connect(self._clear_files)
        clear_btn.setStyleSheet(
            "background-color: #d32f2f; font-weight: bold; color: white;"
        )
        clear_btn.setToolTip(
            "Remove all files from the list (including files from previous sessions)"
        )

        button_layout.addWidget(add_files_btn)
        button_layout.addWidget(add_folder_btn)
        button_layout.addWidget(clear_btn)
        button_layout.addStretch()
        input_layout.addLayout(button_layout)

        input_group.setLayout(input_layout)
        # Input section should also maintain its size and not shrink
        input_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(input_group)

        # Analysis Type section
        analysis_group = QGroupBox("Analysis Type")
        analysis_layout = QHBoxLayout()

        analysis_label = QLabel("Analysis Type:")
        analysis_label.setToolTip(
            "Select the type of analysis to perform on your documents. Each type uses a different prompt template optimized for specific purposes."
        )

        self.analysis_type_combo = QComboBox()
        self.analysis_type_combo.addItems(
            [
                "Document Summary",
                "Knowledge Map (MOC Style)",
                "Entity Extraction",
                "Relationship Analysis",
            ]
        )
        self.analysis_type_combo.setToolTip(
            "Choose analysis type: Document Summary (comprehensive overview), Knowledge Map (structured knowledge extraction), Entity Extraction (people, places, concepts), or Relationship Analysis (connections and networks)"
        )
        self.analysis_type_combo.currentTextChanged.connect(
            self._on_analysis_type_changed
        )
        self.analysis_type_combo.setMinimumWidth(280)

        analysis_layout.addWidget(analysis_label)
        analysis_layout.addWidget(self.analysis_type_combo)
        analysis_layout.addStretch()

        analysis_group.setLayout(analysis_layout)
        analysis_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(analysis_group)

        # Settings section
        settings_group = QGroupBox("Settings")
        settings_layout = QGridLayout()

        # Provider selection (made narrower)
        provider_label = QLabel("Provider:")
        provider_label.setToolTip(
            "Choose AI provider: OpenAI (GPT models), Anthropic (Claude models), or Local (self-hosted models). Requires API keys in Settings."
        )
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openai", "anthropic", "local"])
        self.provider_combo.currentTextChanged.connect(self._update_models)
        self.provider_combo.currentTextChanged.connect(self._on_setting_changed)
        self.provider_combo.setToolTip(
            "Choose AI provider: OpenAI (GPT models), Anthropic (Claude models), or Local (self-hosted models). Requires API keys in Settings."
        )
        self.provider_combo.setMaximumWidth(120)  # Make provider field narrower

        settings_layout.addWidget(provider_label, 0, 0)
        settings_layout.addWidget(self.provider_combo, 0, 1)

        # Model selection (made wider)
        model_label = QLabel("Model:")
        model_label.setToolTip(
            "Select the specific AI model to use for summarization. Different models have different capabilities, costs, and speed."
        )
        self.model_combo = QComboBox()
        self._update_models()  # Initialize with correct models
        self.model_combo.currentTextChanged.connect(self._on_setting_changed)
        self.model_combo.setToolTip(
            "Select the specific AI model to use for summarization. Different models have different capabilities, costs, and speed."
        )
        self.model_combo.setMinimumWidth(
            300
        )  # Make model field wider to accommodate long model names

        settings_layout.addWidget(model_label, 0, 2)
        settings_layout.addWidget(
            self.model_combo, 0, 3, 1, 2
        )  # Span 2 columns to make it wider

        # Add refresh button for local models
        self.refresh_models_btn = QPushButton("🔄")
        self.refresh_models_btn.setToolTip("Refresh available local models")
        self.refresh_models_btn.setMaximumWidth(40)
        self.refresh_models_btn.clicked.connect(self._refresh_models)
        settings_layout.addWidget(self.refresh_models_btn, 0, 5)

        # Max tokens
        max_tokens_label = QLabel("Max Response Size (Tokens):")
        max_tokens_label.setToolTip(
            "Maximum length of generated summary in tokens. Higher values create longer summaries but cost more. 1000 tokens ≈ 750 words."
        )
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 100000)
        self.max_tokens_spin.setValue(10000)
        self.max_tokens_spin.setToolTip(
            "Maximum length of generated summary in tokens. Higher values create longer summaries but cost more. 1000 tokens ≈ 750 words."
        )
        self.max_tokens_spin.valueChanged.connect(self._on_setting_changed)
        self.max_tokens_spin.setMinimumWidth(120)
        self.max_tokens_spin.setToolTip(
            "Maximum length of generated summary in tokens. Higher values create longer summaries but cost more. 1000 tokens ≈ 750 words."
        )

        settings_layout.addWidget(max_tokens_label, 1, 0)
        settings_layout.addWidget(self.max_tokens_spin, 1, 1)

        # Prompt file
        prompt_label = QLabel("Prompt File:")
        prompt_label.setToolTip(
            "Path to custom prompt template file for summarization. Leave empty to use default prompts."
        )
        self.template_path_edit = QLineEdit("")
        self.template_path_edit.setMinimumWidth(180)
        self.template_path_edit.setToolTip(
            "Path to custom prompt template file for summarization. Leave empty to use default prompts."
        )
        self.template_path_edit.textChanged.connect(self._on_setting_changed)

        settings_layout.addWidget(prompt_label, 1, 2)
        settings_layout.addWidget(
            self.template_path_edit, 1, 3, 1, 1
        )  # Adjusted to fit in same row
        browse_template_btn = QPushButton("Browse")
        browse_template_btn.setFixedWidth(80)
        browse_template_btn.clicked.connect(self._select_template)
        browse_template_btn.setToolTip(
            "Browse and select a custom prompt template file.\n"
            "• Template files define how the AI analyzes your content\n"
            "• Must be .txt files with specific formatting\n"
            "• Leave empty to use built-in templates for each analysis type"
        )
        settings_layout.addWidget(browse_template_btn, 1, 4)

        # Options
        self.update_md_checkbox = QCheckBox("Update .md files in-place")
        self.update_md_checkbox.setToolTip(
            "If checked, will update the ## Summary section of existing .md files instead of creating new files"
        )
        self.update_md_checkbox.toggled.connect(self._toggle_output_options)
        self.update_md_checkbox.toggled.connect(self._on_setting_changed)
        settings_layout.addWidget(self.update_md_checkbox, 2, 0, 1, 2)

        self.progress_checkbox = QCheckBox("Show progress tracking")
        self.progress_checkbox.toggled.connect(self._on_setting_changed)
        self.progress_checkbox.setToolTip(
            "Show detailed progress tracking during summarization.\n"
            "• Displays real-time progress for each file\n"
            "• Shows token usage and processing statistics\n"
            "• Useful for monitoring long-running batch jobs"
        )
        settings_layout.addWidget(self.progress_checkbox, 2, 2, 1, 2)

        self.resume_checkbox = QCheckBox("Resume from checkpoint")
        self.resume_checkbox.setToolTip(
            "If a previous summarization was interrupted, resume from where it left off using the checkpoint file"
        )
        self.resume_checkbox.toggled.connect(self._on_setting_changed)
        settings_layout.addWidget(self.resume_checkbox, 3, 0, 1, 2)

        self.force_regenerate_checkbox = QCheckBox("Force regenerate all")
        self.force_regenerate_checkbox.setToolTip(
            "If checked, will regenerate all summaries even if they are up-to-date. Otherwise, only modified files will be summarized."
        )
        self.force_regenerate_checkbox.toggled.connect(self._on_setting_changed)
        settings_layout.addWidget(self.force_regenerate_checkbox, 3, 2, 1, 2)

        # Output folder (only shown when not updating in-place)
        self.output_label = QLabel("Output:")
        settings_layout.addWidget(self.output_label, 4, 0)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            "Click Browse to select output directory (required)"
        )
        self.output_edit.textChanged.connect(self._on_setting_changed)
        self.output_edit.setToolTip(
            "Directory where summary files will be saved.\n"
            "• Only used when 'Update .md files in-place' is unchecked\n"
            "• Summary files will be organized by analysis type\n"
            "• Ensure you have write permissions to this directory"
        )
        settings_layout.addWidget(self.output_edit, 4, 1, 1, 3)
        browse_output_btn = QPushButton("Browse")
        browse_output_btn.setFixedWidth(80)
        browse_output_btn.clicked.connect(self._select_output)
        browse_output_btn.setToolTip(
            "Select the directory where summary files will be saved.\n"
            "• If 'Update .md files in-place' is checked, summaries are saved next to original files.\n"
            "• If unchecked, summaries are saved to this selected directory."
        )
        # Store reference so other methods can show/hide it
        self.output_btn = browse_output_btn
        settings_layout.addWidget(browse_output_btn, 4, 4)

        # Initially hide output selector if update in-place is checked
        self._toggle_output_options(self.update_md_checkbox.isChecked())

        settings_group.setLayout(settings_layout)
        # Settings should never shrink - use a fixed size policy
        settings_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(settings_group)

        # Action buttons
        action_layout = self._create_action_layout()
        layout.addLayout(action_layout)

        # Output section - this should expand and contract with window resizing
        output_layout = self._create_output_section()
        layout.addLayout(
            output_layout, 1
        )  # Stretch factor of 1 to consume remaining space

        # Remove addStretch() to allow output section to properly expand

    def _connect_signals(self):
        """Connect internal signals."""
        # Load settings after UI is fully set up and signals are connected
        # Use a timer to ensure this happens after the widget is fully initialized
        QTimer.singleShot(0, self._load_settings)

    def _get_start_button_text(self) -> str:
        """Get the text for the start button."""
        return "📝 Start Processing"

    def _start_processing(self):
        """Start the summarization process."""
        if not self.validate_inputs():
            return

        files = self._get_file_list()
        logger.info(
            f"🎯 DEBUG: _start_processing got {len(files) if files else 0} files from _get_file_list()"
        )
        if files:
            for i, f in enumerate(files):
                logger.info(f"🎯 DEBUG: File {i}: '{f}' ({len(f)} chars)")

        if not files:
            self.show_warning("No Files", "Please add files to summarize.")
            return

        # Check if model is available for local provider
        provider = self.provider_combo.currentText()
        model = self.model_combo.currentText()

        logger.info(
            f"🔧 DEBUG: Starting summarization with provider='{provider}', model='{model}'"
        )
        self.append_log(f"🔧 Using provider: {provider}, model: {model}")

        if provider == "local":
            logger.info(
                f"🔧 DEBUG: Local provider detected, checking model availability for '{model}'"
            )
            self.append_log(f"🔧 Checking local model availability: {model}")
            if not self._check_model_availability(model):
                logger.info(f"🔧 DEBUG: Model availability check failed for '{model}'")
                return  # Model check will handle dialog and potential download
            logger.info(f"🔧 DEBUG: Model availability check passed for '{model}'")

        # Prepare settings
        gui_settings = {
            "provider": provider,
            "model": model,
            "max_tokens": self.max_tokens_spin.value(),
            "template_path": self.template_path_edit.text(),
            "output_dir": self.output_edit.text()
            if not self.update_md_checkbox.isChecked()
            else None,
            "update_in_place": self.update_md_checkbox.isChecked(),
            "force_regenerate": self.force_regenerate_checkbox.isChecked(),
        }

        # Start worker
        self.summarization_worker = EnhancedSummarizationWorker(
            files, self.settings, gui_settings, self
        )
        self.summarization_worker.progress_updated.connect(self._on_progress_updated)
        self.summarization_worker.file_completed.connect(self._on_file_completed)
        self.summarization_worker.processing_finished.connect(
            self._on_processing_finished
        )
        self.summarization_worker.processing_error.connect(self._on_processing_error)

        self.active_workers.append(self.summarization_worker)
        self.set_processing_state(True)
        self.clear_log()

        # Show informative startup message with file count and details
        file_list = self._get_file_list()
        file_count = len(file_list)
        if file_count == 1:
            file_info = f"file: {Path(file_list[0]).name}"
        elif file_count <= 3:
            file_names = [Path(f).name for f in file_list]
            file_info = f"files: {', '.join(file_names)}"
        else:
            file_info = f"{file_count} files"

        provider = self.provider_combo.currentText()
        model = self.model_combo.currentText()

        self.append_log(f"🚀 Starting Enhanced Summarization ({provider} {model})")
        self.append_log(f"📁 Processing {file_info}")
        if file_count > 1:
            self.append_log(
                f"⏱️  Estimated processing time: {file_count * 2}-{file_count * 5} minutes"
            )
        self.append_log("=" * 50)

        # Initialize batch timing when processing actually starts (not when first progress arrives)
        import time

        self._batch_start_time = time.time()
        self._file_start_time = time.time()  # Initialize for first file

        self.summarization_worker.start()

    def validate_inputs(self) -> bool:
        """Validate inputs before processing."""
        if not self._get_file_list():
            return False

        if not self.update_md_checkbox.isChecked() and not self.output_edit.text():
            self.show_warning(
                "No Output Directory",
                "Please select an output directory or enable in-place updates.",
            )
            return False

        # If output directory is specified, validate it exists
        if not self.update_md_checkbox.isChecked():
            output_dir = self.output_edit.text().strip()
            if output_dir:
                if not Path(output_dir).exists():
                    self.show_warning(
                        "Invalid Output Directory",
                        f"Output directory does not exist: {output_dir}",
                    )
                    return False
                if not Path(output_dir).is_dir():
                    self.show_warning(
                        "Invalid Output Directory",
                        f"Output directory is not a directory: {output_dir}",
                    )
                    return False

        return True

    def _check_model_availability(self, model: str) -> bool:
        """Check if the model is available locally and offer to download if not."""
        try:
            # Strip both "(Installed)" and "(X GB)" suffixes to get clean model name
            clean_model_name = model.replace(" (Installed)", "")
            # Remove size suffix pattern like " (4 GB)"
            import re

            clean_model_name = re.sub(r" \(\d+ GB\)$", "", clean_model_name)

            ollama_manager = get_ollama_manager()

            # If model already has "(Installed)" suffix, it's available
            if model.endswith(" (Installed)"):
                return True

            # First check if Ollama service is running
            if not ollama_manager.is_service_running():
                # Show dialog offering to start Ollama
                dialog = OllamaServiceDialog(self)

                # Disable the start button while dialog is shown
                if hasattr(self, "start_btn"):
                    self.start_btn.setEnabled(False)
                    self.start_btn.setText("⏳ Starting Ollama Service...")

                # Connect dialog completion to re-enable button
                def on_service_dialog_finished():
                    if hasattr(self, "start_btn"):
                        self.start_btn.setEnabled(True)
                        self.start_btn.setText(self._get_start_button_text())

                dialog.finished.connect(on_service_dialog_finished)
                result = dialog.exec()

                if result == QDialog.DialogCode.Accepted:
                    # Check again if service is now running
                    if ollama_manager.is_service_running():
                        return True  # Continue with model checking
                    else:
                        return False  # Service still not running
                else:
                    return False  # User cancelled

            # Check if model is available using clean name
            if ollama_manager.is_model_available(clean_model_name):
                return True

            # Model not available - show download dialog
            dialog = ModelDownloadDialog(clean_model_name, self)

            # Disable the start button while dialog is shown
            if hasattr(self, "start_btn"):
                self.start_btn.setEnabled(False)
                self.start_btn.setText("⏳ Model Download Required")

            # Connect to download progress to update button text
            def on_download_progress(progress):
                if hasattr(self, "start_btn") and hasattr(progress, "percent"):
                    if progress.percent > 0:
                        self.start_btn.setText(
                            f"⏳ Downloading Model ({progress.percent:.0f}%)"
                        )

            # Connect dialog completion to re-enable button
            def on_dialog_finished():
                if hasattr(self, "start_btn"):
                    self.start_btn.setEnabled(True)
                    self.start_btn.setText(self._get_start_button_text())

            # Connect signals
            dialog.download_progress.connect(on_download_progress)
            dialog.download_completed.connect(lambda success: on_dialog_finished())
            dialog.finished.connect(on_dialog_finished)

            result = dialog.exec()

            if result == QDialog.DialogCode.Accepted:
                # Check again if model is now available
                return ollama_manager.is_model_available(model)
            else:
                return False

        except Exception as e:
            logger.error(f"Error checking model availability: {e}")
            self.show_warning(
                "Model Check Failed",
                f"Could not check model availability: {str(e)}\n\n"
                f"Please ensure Ollama is properly installed and running.",
            )
            return False

    def _add_files(self):
        """Add files to the summarization list."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Summarize",
            str(Path.home()),
            "All Supported (*.txt *.md *.pdf *.html *.htm *.json);;Text Files (*.txt);;Markdown Files (*.md);;PDF Files (*.pdf);;HTML Files (*.html *.htm);;JSON Files (*.json);;All Files (*)",
        )

        for file_path in files:
            self.file_list.addItem(file_path)

    def _add_folder(self):
        """Add all compatible files from a folder."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            folder = Path(folder_path)
            extensions = [".txt", ".md", ".pdf", ".html", ".htm", ".json"]

            for file_path in folder.rglob("*"):
                if file_path.suffix.lower() in extensions:
                    self.file_list.addItem(str(file_path))

    def _clear_files(self):
        """Clear all files from the list."""
        self.file_list.clear()

    def _get_file_list(self) -> list[str]:
        """Get the list of files to process."""
        logger.info(
            f"🎯 DEBUG: _get_file_list() called - file_list has {self.file_list.count()} items"
        )
        files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item:
                file_path = item.text()
                logger.info(
                    f"🎯 DEBUG: File list item {i}: '{file_path}' ({len(file_path)} chars)"
                )

                # Debug: Check if this looks like a file path
                if (
                    len(file_path) < 200
                    and not file_path.startswith("/")
                    and not file_path.startswith("\\")
                ):
                    logger.warning(
                        f"🎯 WARNING: Suspicious file path: '{file_path}' - too short or doesn't look like a path"
                    )

                files.append(file_path)

        logger.info(f"🎯 DEBUG: Total files collected: {len(files)}")
        return files

    def _refresh_models(self):
        """Refresh the model list, especially useful for local models."""
        current_model = self.model_combo.currentText()
        self._update_models()

        # Try to restore the previously selected model
        if current_model:
            index = self.model_combo.findText(current_model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
            else:
                logger.info(
                    f"Previously selected model '{current_model}' no longer available"
                )

        # Show feedback to user
        provider = self.provider_combo.currentText()
        if provider == "local":
            self.append_log("🔄 Refreshed local model list")

    def _update_models(self):
        """Update the model list based on selected provider with dynamic registry."""
        provider = self.provider_combo.currentText()
        logger.info(f"🔄 NEW DYNAMIC MODEL SYSTEM ACTIVATED - Provider: {provider}")
        self.model_combo.clear()

        if provider == "openai":
            models = [
                "gpt-3.5-turbo-0125",
                "gpt-3.5-turbo-1106",
                "gpt-4-0613",
                "gpt-4-1106-preview",
                "gpt-4-turbo-2024-04-09",
                "gpt-4o-2024-05-13",
                "gpt-4o-2024-08-06",
                "gpt-4o-mini-2024-07-18",
            ]
        elif provider == "anthropic":
            models = [
                "claude-3-haiku-20240307",
                "claude-3-sonnet-20240229",
                "claude-3-opus-20240229",
                "claude-3-5-sonnet-20240620",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
            ]
        else:  # local
            # Use the new dynamic registry system
            try:
                ollama_manager = get_ollama_manager()
                registry_models = ollama_manager.get_registry_models()

                models = []
                for model_info in registry_models:
                    if "(Installed)" in model_info.name:
                        models.append(model_info.name)
                    else:
                        # Add size information for non-installed models
                        size_gb = model_info.size_bytes / 1_000_000_000
                        models.append(f"{model_info.name} ({size_gb:.0f} GB)")

                if registry_models:
                    installed_count = len(
                        [m for m in registry_models if "(Installed)" in m.name]
                    )
                    available_count = len(registry_models) - installed_count
                    logger.info(
                        f"Found {installed_count} installed and {available_count} available models from dynamic registry"
                    )
                else:
                    logger.warning("No models found in registry")
                    models = ["No models available - Please install Ollama"]

            except Exception as e:
                logger.error(f"Failed to fetch dynamic model list: {e}")
                # Fallback to static list with modern models
                models = [
                    "llama3.2:3b (2 GB)",
                    "llama3.1:8b (5 GB)",
                    "qwen2.5:7b (4 GB)",
                    "mistral:7b (4 GB)",
                    "codellama:7b (4 GB)",
                    "phi3:mini (2 GB)",
                    "qwen2.5:14b (8 GB)",
                    "mixtral:8x7b (26 GB)",
                    "llama3.1:70b (40 GB)",
                ]

        self.model_combo.addItems(models)

        # Set a reasonable default
        if models:
            if provider == "openai":
                self.model_combo.setCurrentText("gpt-4o-mini-2024-07-18")
            elif provider == "anthropic":
                self.model_combo.setCurrentText("claude-3-5-sonnet-20241022")
            else:
                # Try to set a good default for local models
                preferred_defaults = [
                    "qwen2.5-coder:7b-instruct",
                    "phi3:mini-128k",
                    "llama3.1:8b-instruct",
                    "mistral:7b-instruct-v0.3",
                ]
                for default in preferred_defaults:
                    if default in models:
                        self.model_combo.setCurrentText(default)
                        break
                else:
                    # If none of the preferred defaults are available, use the first model
                    self.model_combo.setCurrentIndex(0)

    def _select_template(self):
        """Select a template file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Template File",
            str(Path.home()),
            "Text Files (*.txt);;All Files (*)",
        )
        if file_path:
            self.template_path_edit.setText(file_path)

    def _select_output(self):
        """Select output directory."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder_path:
            self.output_edit.setText(folder_path)

    def _toggle_output_options(self, in_place: bool):
        """Toggle output directory visibility based on in-place option."""
        self.output_label.setVisible(not in_place)
        self.output_edit.setVisible(not in_place)
        self.output_btn.setVisible(not in_place)

    def _on_progress_updated(self, progress):
        """Handle progress updates with clean, informative status."""
        import time

        # Initialize timing tracking (batch time already set when worker starts)
        if not hasattr(self, "_last_progress_update"):
            self._last_progress_update = 0

        current_time = time.time()

        # Calculate unified ETA based on current file progress
        file_eta = ""
        batch_eta = ""

        # Get file information for consistent ETA calculation
        total_files = getattr(progress, "total_files", 1)
        completed_files = getattr(progress, "completed_files", 0)

        if hasattr(progress, "percent") and progress.percent and progress.percent > 1:
            # File ETA: linear extrapolation from current file progress
            file_elapsed = current_time - self._file_start_time

            # Only calculate if we have meaningful data (>1% progress and >3 seconds elapsed)
            if file_elapsed > 3 and progress.percent > 0:
                file_total_estimated = (file_elapsed / progress.percent) * 100
                file_remaining = max(0, file_total_estimated - file_elapsed)

                # Format file ETA
                if file_remaining < 60:
                    file_eta = f" (ETA: {file_remaining:.0f}s)"
                elif file_remaining < 3600:
                    file_eta = f" (ETA: {file_remaining/60:.1f}m)"
                else:
                    file_eta = f" (ETA: {file_remaining/3600:.1f}h)"

                # Batch ETA: for single file, same as file ETA; for multiple files, extrapolate
                if total_files == 1:
                    # Single file: batch ETA = file ETA
                    batch_eta = f" | Batch{file_eta.replace(' (', ' ')}"
                else:
                    # Multiple files: estimate time for remaining files
                    batch_elapsed = current_time - self._batch_start_time
                    if completed_files > 0:
                        # Estimate based on completed files
                        avg_time_per_file = batch_elapsed / (
                            completed_files + (progress.percent / 100.0)
                        )
                        remaining_files = (
                            total_files - completed_files - (progress.percent / 100.0)
                        )
                        batch_remaining = max(0, remaining_files * avg_time_per_file)
                    else:
                        # First file: estimate based on current file progress
                        estimated_total_time_per_file = file_total_estimated
                        remaining_files = total_files - (progress.percent / 100.0)
                        batch_remaining = max(
                            0, remaining_files * estimated_total_time_per_file
                        )

                    # Format batch ETA
                    if batch_remaining < 60:
                        batch_eta = f" | Batch ETA: {batch_remaining:.0f}s"
                    elif batch_remaining < 3600:
                        batch_eta = f" | Batch ETA: {batch_remaining/60:.1f}m"
                    else:
                        batch_eta = f" | Batch ETA: {batch_remaining/3600:.1f}h"

        # Only show key progress updates to reduce noise
        should_update = False

        if hasattr(progress, "status"):
            # Show important status changes
            if progress.status in [
                "starting",
                "loading_file",
                "chunking",
                "generating",
                "generating_llm",
                "reassembling",
                "completed",
                "failed",
            ]:
                should_update = True

            # Always show heartbeat updates during long LLM processing
            elif progress.status == "generating_llm":
                should_update = True

            # Show chunk progress but throttle updates
            elif progress.status in ["processing_chunks", "chunk_completed"]:
                if hasattr(progress, "percent"):
                    # Only update every 10% or if significant time has passed
                    if (progress.percent - self._last_progress_update >= 10) or (
                        current_time - getattr(self, "_last_update_time", 0) > 30
                    ):
                        should_update = True
                        self._last_progress_update = progress.percent
                        self._last_update_time = current_time

        # Format enhanced character-based progress message
        if should_update and hasattr(progress, "current_step"):
            # Use detailed current_step if available, otherwise fall back to status
            base_message = progress.current_step or getattr(
                progress, "status", "Processing..."
            )

            # Build enhanced progress information
            progress_parts = []

            # Add file progress percentage
            if hasattr(progress, "percent") and progress.percent is not None:
                progress_parts.append(f"({progress.percent:.0f}%)")

            # Add character-based info for context (but don't show inflated progress during generation)
            if (
                hasattr(progress, "total_characters")
                and progress.total_characters
                and hasattr(progress, "characters_completed")
                and progress.characters_completed is not None
            ):
                chars_completed_k = progress.characters_completed / 1000
                total_chars_k = progress.total_characters / 1000

                # Only show character progress if we've actually completed some files
                if progress.characters_completed > 0:
                    char_progress = (
                        progress.characters_completed / progress.total_characters
                    ) * 100.0
                    progress_parts.append(
                        f"Batch: {char_progress:.0f}% ({chars_completed_k:.1f}k/{total_chars_k:.1f}k chars)"
                    )
                else:
                    # Show total characters being processed
                    progress_parts.append(f"Processing: {total_chars_k:.1f}k chars")

            # Add file information if available
            if (
                hasattr(progress, "current_file")
                and progress.current_file
                and hasattr(progress, "total_files")
                and progress.total_files
                and hasattr(progress, "completed_files")
                and progress.completed_files is not None
            ):
                file_info = (
                    f"File {progress.completed_files + 1}/{progress.total_files}"
                )
                progress_parts.append(file_info)

            # Add chunk info for chunked processing
            if (
                hasattr(progress, "chunk_number")
                and hasattr(progress, "total_chunks")
                and progress.total_chunks
            ):
                progress_parts.append(
                    f"Chunk {progress.chunk_number}/{progress.total_chunks}"
                )

            # Build the final message
            if progress_parts:
                progress_info = " | ".join(progress_parts)
                full_message = f"{base_message} | {progress_info}{file_eta}{batch_eta}"
            else:
                full_message = f"{base_message}{file_eta}{batch_eta}"

            self.append_log(full_message)

        # Reset file timing for new files
        if hasattr(progress, "status") and progress.status == "starting":
            self._file_start_time = current_time

    def _on_file_completed(self, current: int, total: int):
        """Handle file completion with detailed progress."""
        import time

        # Calculate file processing time
        if hasattr(self, "_file_start_time"):
            file_time = time.time() - self._file_start_time
            if file_time < 60:
                time_text = f" (completed in {file_time:.0f}s)"
            else:
                time_text = f" (completed in {file_time/60:.1f}m)"
        else:
            time_text = ""

        # Calculate overall progress
        percent = (current / total) * 100 if total > 0 else 0

        # Calculate batch ETA for remaining files
        batch_eta = ""
        if hasattr(self, "_batch_start_time") and current > 0:
            batch_elapsed = time.time() - self._batch_start_time
            avg_time_per_file = batch_elapsed / current
            remaining_files = total - current
            remaining_time = avg_time_per_file * remaining_files

            if remaining_files > 0 and remaining_time > 0:
                if remaining_time < 60:
                    batch_eta = f" | {remaining_time:.0f}s remaining for batch"
                elif remaining_time < 3600:
                    batch_eta = f" | {remaining_time/60:.1f}m remaining for batch"
                else:
                    batch_eta = f" | {remaining_time/3600:.1f}h remaining for batch"

        progress_msg = f"Progress: {current}/{total} files completed ({percent:.0f}%){time_text}{batch_eta}"
        self.append_log(progress_msg)

        # Reset file timer for next file
        if current < total:
            self._file_start_time = time.time()

    def _on_processing_finished(
        self, success_count: int, failure_count: int, total_count: int
    ):
        """Handle processing completion with success summary."""
        import time

        self.set_processing_state(False)

        # Calculate total batch time
        total_time_text = ""
        if hasattr(self, "_batch_start_time"):
            total_time = time.time() - self._batch_start_time
            if total_time < 60:
                total_time_text = f" in {total_time:.0f}s"
            elif total_time < 3600:
                total_time_text = f" in {total_time/60:.1f}m"
            else:
                total_time_text = f" in {total_time/3600:.1f}h"

        self.append_log("\n" + "=" * 50)
        self.append_log("🎉 BATCH PROCESSING COMPLETED!")
        self.append_log("=" * 50)

        # Show results summary
        if failure_count == 0:
            self.append_log(
                f"✅ All {success_count} files processed successfully{total_time_text}"
            )
        else:
            self.append_log(
                f"📊 Results: {success_count} succeeded, {failure_count} failed{total_time_text}"
            )

        # Show output location information
        if self.update_md_checkbox.isChecked():
            self.append_log("📝 Summary sections updated in-place for .md files")
        else:
            output_dir = self.output_edit.text()
            if output_dir:
                self.append_log(f"📁 Summary files saved to: {output_dir}")
            else:
                self.append_log("📁 Summary files saved next to original files")

        # Enable report button if available
        if hasattr(self, "report_btn"):
            self.report_btn.setEnabled(True)

    def _on_processing_error(self, error: str):
        """Handle processing errors."""
        self.set_processing_state(False)
        self.append_log(f"Error: {error}")
        self.show_error("Processing Error", error)

    def _stop_processing(self):
        """Stop the summarization process."""
        if self.summarization_worker and self.summarization_worker.isRunning():
            self.summarization_worker.stop()  # Use the worker's stop method which handles cancellation token
            self.append_log("⏹ Stopping summarization process...")
        super()._stop_processing()

    def cleanup_workers(self):
        """Clean up worker threads."""
        if self.summarization_worker and self.summarization_worker.isRunning():
            self.summarization_worker.stop()  # Use the worker's stop method which handles cancellation token
            self.summarization_worker.wait(3000)
        super().cleanup_workers()

    def _load_settings(self):
        """Load saved settings from session."""
        logger.info(f"🔧 Loading settings for {self.tab_name} tab...")
        try:
            # Block signals during loading to prevent redundant saves
            widgets_to_block = [
                self.output_edit,
                self.provider_combo,
                self.model_combo,
                self.max_tokens_spin,
                self.template_path_edit,
                self.update_md_checkbox,
                self.force_regenerate_checkbox,
                self.progress_checkbox,
                self.resume_checkbox,
            ]

            # Block all signals
            for widget in widgets_to_block:
                widget.blockSignals(True)

            try:
                # Load output directory - use configured summaries path as default
                default_output_dir = str(self.settings.paths.summaries)
                saved_output_dir = self.gui_settings.get_output_directory(
                    self.tab_name, default_output_dir
                )
                self.output_edit.setText(saved_output_dir)

                # Load provider selection
                saved_provider = self.gui_settings.get_combo_selection(
                    self.tab_name, "provider", "local"
                )
                index = self.provider_combo.findText(saved_provider)
                if index >= 0:
                    self.provider_combo.setCurrentIndex(index)
                    self._update_models()  # Update models after setting provider

                # Load model selection
                saved_model = self.gui_settings.get_combo_selection(
                    self.tab_name, "model", "qwen2.5-coder:7b-instruct"
                )
                index = self.model_combo.findText(saved_model)
                if index >= 0:
                    self.model_combo.setCurrentIndex(index)

                # Load max tokens
                saved_max_tokens = self.gui_settings.get_spinbox_value(
                    self.tab_name, "max_tokens", 10000
                )
                self.max_tokens_spin.setValue(saved_max_tokens)

                # Load template path
                saved_template = self.gui_settings.get_line_edit_text(
                    self.tab_name, "template_path", ""
                )
                self.template_path_edit.setText(saved_template)

                # Load checkbox states
                self.update_md_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "update_in_place", False
                    )
                )
                self.force_regenerate_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "force_regenerate", False
                    )
                )
                self.progress_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "show_progress", True
                    )
                )
                self.resume_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "resume_checkpoint", False
                    )
                )

                # Update output visibility based on checkbox state
                self._toggle_output_options(self.update_md_checkbox.isChecked())

            finally:
                # Always restore signals, even if an exception occurred
                for widget in widgets_to_block:
                    widget.blockSignals(False)

            logger.info(f"✅ Successfully loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")

    def _save_settings(self):
        """Save current settings to session."""
        logger.debug(f"💾 Saving settings for {self.tab_name} tab...")
        try:
            # Save output directory
            self.gui_settings.set_output_directory(
                self.tab_name, self.output_edit.text()
            )

            # Save combo selections
            self.gui_settings.set_combo_selection(
                self.tab_name, "provider", self.provider_combo.currentText()
            )
            self.gui_settings.set_combo_selection(
                self.tab_name, "model", self.model_combo.currentText()
            )

            # Save spinbox values
            self.gui_settings.set_spinbox_value(
                self.tab_name, "max_tokens", self.max_tokens_spin.value()
            )

            # Save line edit text
            self.gui_settings.set_line_edit_text(
                self.tab_name, "template_path", self.template_path_edit.text()
            )

            # Save checkbox states
            self.gui_settings.set_checkbox_state(
                self.tab_name, "update_in_place", self.update_md_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "force_regenerate",
                self.force_regenerate_checkbox.isChecked(),
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "show_progress", self.progress_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "resume_checkpoint", self.resume_checkbox.isChecked()
            )

            logger.info(f"✅ Successfully saved settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")

    def _on_setting_changed(self):
        """Called when any setting changes to automatically save."""
        logger.debug(f"🔄 Setting changed in {self.tab_name} tab, triggering save...")
        self._save_settings()

    def _on_analysis_type_changed(self, analysis_type: str):
        """Called when analysis type changes to auto-populate template path."""
        template_mapping = {
            "Document Summary": "config/prompts/document_summary.txt",
            "Knowledge Map (MOC Style)": "config/prompts/knowledge_map_moc.txt",
            "Entity Extraction": "config/prompts/entity_extraction.txt",
            "Relationship Analysis": "config/prompts/relationship_analysis.txt",
        }

        if analysis_type in template_mapping:
            template_path = template_mapping[analysis_type]
            self.template_path_edit.setText(template_path)
            logger.debug(
                f"🔄 Analysis type changed to '{analysis_type}', auto-populated template: {template_path}"
            )
            # Trigger settings save after template path is updated
            self._on_setting_changed()
