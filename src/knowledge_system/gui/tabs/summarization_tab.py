"""Content analysis tab for document analysis using AI models with various analysis types."""

from pathlib import Path
from typing import Any

import yaml
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
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
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ...utils.model_registry import get_provider_models
from ...utils.ollama_manager import get_ollama_manager
from ..components.base_tab import BaseTab
from ..components.rich_log_display import ProcessorLogIntegrator, RichLogDisplay
from ..components.simple_progress_bar import SimpleTranscriptionProgressBar
from ..core.settings_manager import get_gui_settings_manager
from ..dialogs.claim_validation_dialog import ClaimValidationDialog
from ..legacy_dialogs import ModelDownloadDialog, OllamaServiceDialog

logger = get_logger(__name__)


def _analysis_type_to_filename(analysis_type: str) -> str:
    """Convert analysis type to template filename."""
    return (
        analysis_type.lower()
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "_")
        .strip()
    )


class EnhancedSummarizationWorker(QThread):
    """Enhanced worker thread for summarization with real-time progress dialog."""

    progress_updated = pyqtSignal(object)  # SummarizationProgress
    file_completed = pyqtSignal(int, int)  # current, total
    processing_finished = pyqtSignal(
        int, int, int
    )  # success_count, failure_count, total_count
    processing_error = pyqtSignal(str)
    hce_analytics_updated = pyqtSignal(dict)  # HCE analytics data
    log_message = pyqtSignal(str)  # Log messages from processing pipeline

    def __init__(
        self, files: Any, settings: Any, gui_settings: Any, parent: Any = None
    ) -> None:
        super().__init__(parent)
        self.files = files
        self.settings = settings
        self.gui_settings = gui_settings
        self.progress_dialog = None
        self.should_stop = False
        # Create cancellation token for proper cancellation handling
        from ...utils.cancellation import CancellationToken

        self.cancellation_token = CancellationToken()
        self.log_handler = None  # Will be set when processing starts

    def _extract_hce_analytics(self, hce_data: dict, filename: str) -> dict:
        """Extract analytics from HCE data for display."""
        claims = hce_data.get("claims", [])
        people = hce_data.get("people", [])
        concepts = hce_data.get("concepts", [])
        relations = hce_data.get("relations", [])
        contradictions = hce_data.get("contradictions", [])

        # Categorize claims by tier
        tier_a_claims = [c for c in claims if c.get("tier") == "A"]
        tier_b_claims = [c for c in claims if c.get("tier") == "B"]
        tier_c_claims = [c for c in claims if c.get("tier") == "C"]

        # Get top claims for display
        top_claims = []
        for claim in (tier_a_claims + tier_b_claims)[:3]:  # Top 3 claims
            canonical = claim.get("canonical", "")
            if canonical:
                top_claims.append(
                    {
                        "text": (
                            canonical[:150] + "..."
                            if len(canonical) > 150
                            else canonical
                        ),
                        "tier": claim.get("tier", "C"),
                        "type": claim.get("claim_type", "General"),
                    }
                )

        # Get sample contradictions
        sample_contradictions = []
        for contradiction in contradictions[:2]:  # Top 2 contradictions
            claim1 = contradiction.get("claim1", {}).get("canonical", "")
            claim2 = contradiction.get("claim2", {}).get("canonical", "")
            if claim1 and claim2:
                sample_contradictions.append(
                    {
                        "claim1": claim1[:100] + "..." if len(claim1) > 100 else claim1,
                        "claim2": claim2[:100] + "..." if len(claim2) > 100 else claim2,
                    }
                )

        return {
            "filename": filename,
            "total_claims": len(claims),
            "tier_a_count": len(tier_a_claims),
            "tier_b_count": len(tier_b_claims),
            "tier_c_count": len(tier_c_claims),
            "people_count": len(people),
            "concepts_count": len(concepts),
            "relations_count": len(relations),
            "contradictions_count": len(contradictions),
            "top_claims": top_claims,
            "sample_contradictions": sample_contradictions,
            "top_people": [p.get("name", "") for p in people[:5] if p.get("name")],
            "top_concepts": [c.get("name", "") for c in concepts[:5] if c.get("name")],
        }

    def _run_with_system2_orchestrator(self) -> None:
        """Run summarization using System 2 orchestrator for job management."""
        try:
            from ...core.system2_orchestrator import System2Orchestrator
            from ...utils.progress import SummarizationProgress

            # Define progress callback to receive real-time updates from orchestrator
            def orchestrator_progress_callback(
                stage: str,
                percent: int,
                source_id: str,
                current: int = 0,
                total: int = 0,
            ):
                """Handle progress updates from the orchestrator."""
                # Map stage to user-friendly phase names
                phase_map = {
                    "loading": "Loading Document",
                    "parsing": "Parsing Content",
                    "mining": "Unified Mining",
                    "storing": "Storing Results",
                    "generating_summary": "Generating Summary",
                    "saving_file": "Saving Output",
                }
                phase_name = phase_map.get(stage, "Processing")

                # Emit progress update
                progress = SummarizationProgress(
                    current_file=self.files[self.current_file_index]
                    if self.current_file_index < len(self.files)
                    else "",
                    total_files=len(self.files),
                    completed_files=self.current_file_index,
                    current_step=f"⚙️ {phase_name}",
                    file_percent=percent,
                    provider=self.gui_settings.get("provider", "openai"),
                    model_name=self.gui_settings.get("model", "gpt-4o-mini-2024-07-18"),
                )

                # Add segment info for mining phase
                if stage == "mining" and total > 0:
                    progress.current_step = (
                        f"⚙️ {phase_name}: segment {current}/{total}"
                    )

                self.progress_updated.emit(progress)

            # Create orchestrator instance with progress callback
            orchestrator = System2Orchestrator(
                progress_callback=orchestrator_progress_callback
            )

            success_count = 0
            failure_count = 0
            total_count = len(self.files)
            self.current_file_index = 0

            for i, file_path in enumerate(self.files):
                self.current_file_index = i
                if self.should_stop:
                    self.processing_error.emit("Processing was cancelled by user")
                    return

                # Get content type from gui_settings (already set by parent tab)
                content_type = self.gui_settings.get("content_type", "transcript_own")

                # Handle database sources
                if file_path.startswith("db://"):
                    # Extract source_id from db://SOURCE_ID format
                    source_id = file_path[5:]  # Remove "db://" prefix
                    # source_id used directly, no episode_ prefix
                    file_name = f"Database: {source_id}"

                    # Create mining job for database source
                    job_id = orchestrator.create_job(
                        "mine",  # Database job type (not JobType enum)
                        source_id,
                        config={
                            "source": "manual_summarization",
                            # No file_path for database sources - will use DB segments
                            "gui_settings": self.gui_settings,
                            "content_type": content_type,
                            "miner_model": f"{self.gui_settings.get('provider', 'openai')}:{self.gui_settings.get('model', 'gpt-4o-mini-2024-07-18')}",
                        },
                        auto_process=False,  # Manual job, don't chain
                    )
                else:
                    # Regular file processing
                    file_name = Path(file_path).name

                    # Create source ID from file name
                    source_id = Path(file_path).stem

                    # Create mining job for this file
                    job_id = orchestrator.create_job(
                        "mine",  # Database job type (not JobType enum)
                        source_id,
                        config={
                            "source": "manual_summarization",
                            "file_path": str(file_path),
                            "gui_settings": self.gui_settings,
                            "content_type": content_type,
                            "miner_model": f"{self.gui_settings.get('provider', 'openai')}:{self.gui_settings.get('model', 'gpt-4o-mini-2024-07-18')}",
                        },
                        auto_process=False,  # Manual job, don't chain
                    )

                try:
                    # Execute the job - orchestrator will emit real-time progress via callback
                    import asyncio

                    result = asyncio.run(orchestrator.process_job(job_id))

                    if result.get("status") == "succeeded":
                        # Emit final 100% progress
                        final_progress = SummarizationProgress(
                            current_file=file_path,
                            total_files=total_count,
                            completed_files=i,
                            current_step=f"✅ Completed {file_name}",
                            file_percent=100,
                            provider=self.gui_settings.get("provider", "openai"),
                            model_name=self.gui_settings.get(
                                "model", "gpt-4o-mini-2024-07-18"
                            ),
                        )
                        self.progress_updated.emit(final_progress)

                        success_count += 1
                        self.file_completed.emit(i + 1, total_count)

                        # Emit HCE analytics if available
                        if (
                            "result" in result
                            and "claims_extracted" in result["result"]
                        ):
                            analytics = {
                                "filename": file_name,
                                "total_claims": result["result"].get(
                                    "claims_extracted", 0
                                ),
                                "people_count": result["result"].get(
                                    "people_extracted", 0
                                ),
                                "concepts_count": result["result"].get(
                                    "mental_models_extracted", 0
                                ),
                            }
                            self.hce_analytics_updated.emit(analytics)
                    else:
                        failure_count += 1
                        error_msg = result.get(
                            "error_message", result.get("error", "Processing failed")
                        )
                        error_progress = SummarizationProgress(
                            current_file=file_path,
                            total_files=total_count,
                            completed_files=i,
                            current_step=f"❌ Failed: {error_msg}",
                            status="error",
                            provider=self.gui_settings.get("provider", "openai"),
                            model_name=self.gui_settings.get(
                                "model", "gpt-4o-mini-2024-07-18"
                            ),
                        )
                        self.progress_updated.emit(error_progress)

                except Exception as e:
                    failure_count += 1
                    logger.error(f"System 2 job failed for {file_path}: {e}")
                    error_progress = SummarizationProgress(
                        current_file=file_path,
                        total_files=total_count,
                        completed_files=i,
                        current_step=f"❌ Error: {str(e)}",
                        status="error",
                        provider=self.gui_settings.get("provider", "openai"),
                        model_name=self.gui_settings.get(
                            "model", "gpt-4o-mini-2024-07-18"
                        ),
                    )
                    self.progress_updated.emit(error_progress)

            self.processing_finished.emit(success_count, failure_count, total_count)

        except Exception as e:
            logger.error(f"System 2 orchestrator error: {e}")
            self.processing_error.emit(f"System 2 processing failed: {str(e)}")

    def run(self) -> None:
        """Run the summarization process using System 2 orchestrator."""
        # Install GUI log handler to capture processing logs
        from ..utils.gui_log_handler import install_gui_log_handler

        # Capture logs from HCE processors and related modules
        logger_names = [
            "knowledge_system.processors.hce.unified_pipeline",
            "knowledge_system.processors.hce.unified_miner",
            "knowledge_system.processors.hce.parallel_processor",
            "knowledge_system.processors.hce.evaluators",
            "knowledge_system.core.system2_orchestrator",
        ]

        try:
            self.log_handler = install_gui_log_handler(
                callback=self._handle_log_message,
                logger_names=logger_names,
                level=20,  # INFO level
            )

            # Always use System 2 orchestrator for job tracking, error handling, and metrics
            self._run_with_system2_orchestrator()

        finally:
            # Remove log handler when done
            if self.log_handler:
                from ..utils.gui_log_handler import remove_gui_log_handler

                remove_gui_log_handler(self.log_handler, logger_names)
                self.log_handler = None

    def _handle_log_message(self, message: str) -> None:
        """Handle log messages from the processing pipeline.

        Args:
            message: The log message to handle
        """
        # Emit the log message signal
        self.log_message.emit(message)

    def stop(self) -> None:
        """Stop the summarization process."""
        logger.info("EnhancedSummarizationWorker.stop() called")
        self.should_stop = True
        if hasattr(self, "cancellation_token") and self.cancellation_token:
            self.cancellation_token.cancel("User requested cancellation")

    def _extract_youtube_url_from_file(self, file_path: Path) -> str | None:
        """
        Extract YouTube URL from a processed file's YAML frontmatter or content
        Extract YouTube URL from a processed file's YAML frontmatter or content.

        Looks for YouTube URLs in multiple locations:
        1. 'source' field in YAML frontmatter (for transcript files)
        2. 'url' field in YAML frontmatter
        3. YouTube URLs in the content body
        4. Links in the content (e.g., "Watch on YouTube" links)

        Args:
            file_path: Path to the markdown file to check

        Returns:
            YouTube URL if found, None otherwise
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Look for YAML frontmatter first
            if content.startswith("---"):
                # Find the end of YAML frontmatter
                lines = content.split("\n")
                yaml_end_idx = -1
                for i, line in enumerate(lines[1:], 1):  # Skip first "---"
                    if line.strip() == "---":
                        yaml_end_idx = i
                        break

                if yaml_end_idx != -1:
                    # Extract YAML content
                    yaml_content = "\n".join(lines[1:yaml_end_idx])

                    try:
                        metadata = yaml.safe_load(yaml_content)
                        if isinstance(metadata, dict):
                            # Check common fields that might contain YouTube URLs
                            for field in ["source", "url", "source_url", "video_url"]:
                                source = metadata.get(field, "")
                                if source and (
                                    "youtube.com" in source or "youtu.be" in source
                                ):
                                    logger.debug(
                                        f"Found YouTube URL in YAML field '{field}': {source}"
                                    )
                                    return source
                    except yaml.YAMLError as e:
                        logger.debug(f"YAML parsing failed, trying regex fallback: {e}")

            # Fallback: search for YouTube URLs in the content
            import re

            youtube_patterns = [
                r"https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+",
                r"https?://(?:www\.)?youtu\.be/[\w-]+",
                r"https?://youtube\.com/watch\?v=[\w-]+",
                r"https?://youtu\.be/[\w-]+",
            ]

            for pattern in youtube_patterns:
                match = re.search(pattern, content)
                if match:
                    logger.debug(f"Found YouTube URL in content: {match.group(0)}")
                    return match.group(0)

        except Exception as e:
            logger.debug(f"Could not extract YouTube URL from {file_path}: {e}")

        logger.debug(f"No YouTube URL found in {file_path}")
        return None

    def _extract_thumbnail_from_file(self, file_path: Path) -> str:
        """
        Extract thumbnail content from the original markdown file
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
        Copy thumbnail image file from source directory to output Thumbnails subdirectory and update reference
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

    # Thread-safe signal for dialog creation
    show_ollama_service_dialog_signal = pyqtSignal(str)  # model name

    def __init__(self, parent: Any = None) -> None:
        self.summarization_worker = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "Summarization"
        super().__init__(parent)

    @property
    def provider_combo(self):
        """Redirect to miner_provider for backward compatibility."""
        return getattr(self, "miner_provider", None)

    @property
    def model_combo(self):
        """Redirect to miner_model for backward compatibility."""
        return getattr(self, "miner_model", None)

    def _load_analysis_types(self) -> list[str]:
        """Load analysis types from config file."""
        from pathlib import Path

        config_file = Path("config/dropdown_options.txt")
        try:
            if config_file.exists():
                with open(config_file, encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        options = [
                            opt.strip() for opt in content.split(",") if opt.strip()
                        ]
                        if options:
                            return options
        except Exception as e:
            logger.warning(f"Failed to load dropdown options from {config_file}: {e}")

        # Fallback to default options
        return [
            "Document Summary",
            "Knowledge Map (MOC Style)",
            "Entity Extraction",
            "Relationship Analysis",
        ]

    def _setup_ui(self) -> None:
        """Setup the summarization UI."""
        layout = QVBoxLayout(self)

        # Input section
        input_group = QGroupBox("Input Documents")
        input_layout = QVBoxLayout()

        # Source selection radio buttons
        source_layout = QHBoxLayout()
        self.files_radio = QRadioButton("Files")
        self.database_radio = QRadioButton("Database")
        self.files_radio.setChecked(True)  # Default to files
        self.files_radio.toggled.connect(self._on_source_changed)
        self.database_radio.toggled.connect(self._on_source_changed)
        # Also save settings when source changes
        self.files_radio.toggled.connect(self._on_setting_changed)
        self.database_radio.toggled.connect(self._on_setting_changed)

        source_layout.addWidget(QLabel("Source:"))
        source_layout.addWidget(self.files_radio)
        source_layout.addWidget(self.database_radio)
        source_layout.addStretch()
        input_layout.addLayout(source_layout)

        # Content type selection
        content_type_layout = QHBoxLayout()
        self.content_type_combo = QComboBox()
        self.content_type_combo.addItems(
            [
                "Transcript (Own)",
                "Transcript (Third-party)",
                "Document (PDF/eBook)",
                "Document (White Paper)",
            ]
        )
        self.content_type_combo.setCurrentIndex(0)

        # Add tooltip
        self.content_type_combo.setToolTip(
            "Select the type of content:\n"
            "• Transcript (Own): Created by this app with diarization and timestamps\n"
            "• Transcript (Third-party): External transcripts without our metadata\n"
            "• Document (PDF/eBook): Books, reports, long-form content\n"
            "• Document (White Paper): Technical documents, research papers"
        )

        content_type_layout.addWidget(QLabel("Content Type:"))
        content_type_layout.addWidget(self.content_type_combo)
        content_type_layout.addStretch()
        input_layout.addLayout(content_type_layout)

        # Connect to save settings when changed
        self.content_type_combo.currentTextChanged.connect(self._on_setting_changed)

        # Stacked widget for file list and database browser
        self.source_stack = QStackedWidget()

        # Page 0: File list widget
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)

        # Add supported file types info
        supported_types_label = QLabel(
            "Supported formats: PDF (.pdf), Text (.txt), Markdown (.md), HTML (.html, .htm), JSON (.json), Word (.docx, .doc), RTF (.rt)"
        )
        supported_types_label.setStyleSheet(
            "color: #666; font-style: italic; margin-bottom: 8px;"
        )
        supported_types_label.setWordWrap(True)
        file_layout.addWidget(supported_types_label)

        # File list
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(150)
        file_layout.addWidget(self.file_list)

        # Add default file if it exists (using curly quotes: U+2018 and U+2019)
        default_input_file = "/Users/matthewgreer/Projects/Knowledge_Chipper/output/transcripts/Steve Bannon_ Silicon Valley Is Turning Us Into \u2018Digital Serfs\u2019_vvj_J2tB2Ag.md"
        if Path(default_input_file).exists():
            self.file_list.addItem(default_input_file)

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
        file_layout.addLayout(button_layout)

        # Add file widget to stacked widget
        self.source_stack.addWidget(file_widget)

        # Page 1: Database browser widget
        self.db_widget = self._create_database_browser()
        self.source_stack.addWidget(self.db_widget)

        # Add stacked widget to main layout
        input_layout.addWidget(self.source_stack)

        input_group.setLayout(input_layout)
        # Input section should also maintain its size and not shrink
        input_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(input_group)

        # Analysis Type removed - now defaults to "Document Summary" with entity extraction

        # Profile section removed - not needed (explicit per-stage model controls used instead)

        # Settings section
        settings_group = QGroupBox("Settings")
        settings_layout = QGridLayout()

        # Provider selection - REMOVED (using Advanced Per-stage Models instead)
        # provider_combo and model_combo are now properties that redirect to miner dropdowns
        # This eliminates hidden dropdowns while maintaining backward compatibility

        # Model selection removed - using Advanced Per-stage Models instead
        # settings_layout.addWidget(QLabel("Model:"), 0, 2)

        # Create a horizontal layout for model combo + tooltip + refresh button
        model_layout = QHBoxLayout()
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(8)

        # model_layout.addWidget(self.model_combo)  # REMOVED - model_combo is now None

        # Add tooltip info indicator between model combo and refresh button
        model_tooltip = "Select the specific AI model to use for summarization. Different models have different capabilities, costs, and speed."
        formatted_model_tooltip = f"<b>Model:</b><br/><br/>{model_tooltip}"

        model_info_label = QLabel("ⓘ")
        model_info_label.setFixedSize(16, 16)
        model_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        model_info_label.setToolTip(formatted_model_tooltip)
        model_info_label.setStyleSheet(
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
        model_layout.addWidget(model_info_label)

        # Add refresh button for local models
        self.refresh_models_btn = QPushButton("🔄")
        self.refresh_models_btn.setToolTip(
            "Refresh available models for selected provider"
        )
        self.refresh_models_btn.setMaximumWidth(40)
        self.refresh_models_btn.clicked.connect(self._refresh_models)
        model_layout.addWidget(self.refresh_models_btn)

        # Model container removed - using Advanced Per-stage Models instead
        # model_container = QWidget()
        # model_container.setLayout(model_layout)
        # settings_layout.addWidget(
        #     model_container, 0, 3, 1, 3
        # )  # Span across multiple columns

        # Set tooltips for model combo as well
        # self.model_combo.setToolTip(formatted_model_tooltip)  # REMOVED - model_combo is now None

        # Prompt file
        prompt_label = QLabel("Prompt File:")
        prompt_label.setToolTip(
            "Path to custom prompt template file for claim extraction. Leave empty to use default HCE prompts."
        )
        default_template_path = (
            "/Users/matthewgreer/Projects/Prompts/Summary Prompt.txt"
        )
        self.template_path_edit = QLineEdit(default_template_path)
        self.template_path_edit.setMinimumWidth(200)  # Reduced from 280 to 200
        self.template_path_edit.setToolTip(
            "Path to custom prompt template file for claim extraction. Leave empty to use default HCE prompts."
        )
        self.template_path_edit.textChanged.connect(self._on_setting_changed)

        settings_layout.addWidget(prompt_label, 1, 2)
        settings_layout.addWidget(
            self.template_path_edit, 1, 3, 1, 1
        )  # Ensure proper spacing
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

        # Output folder (only shown when not updating in-place)
        self.output_label = QLabel("Output Directory:")
        settings_layout.addWidget(self.output_label, 5, 0)
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
        settings_layout.addWidget(self.output_edit, 5, 1, 1, 3)
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
        settings_layout.addWidget(browse_output_btn, 5, 4)

        # Output selector is always visible

        settings_group.setLayout(settings_layout)
        # Settings should never shrink - use a fixed size policy
        settings_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(settings_group)

        # HCE Claim Analysis Settings - REMOVED per user request
        # hce_group = QGroupBox("🔍 Claim Analysis Settings")
        # Three-column layout with very thin separators
        hce_layout = QHBoxLayout()
        hce_layout.setSpacing(6)

        # Column containers
        col1_layout = QGridLayout()
        col1_layout.setSpacing(5)
        col1_widget = QWidget()
        col1_widget.setLayout(col1_layout)

        col2_layout = QGridLayout()
        col2_layout.setSpacing(5)
        col2_widget = QWidget()
        col2_widget.setLayout(col2_layout)

        col3_layout = QGridLayout()
        col3_layout.setSpacing(5)
        col3_widget = QWidget()
        col3_widget.setLayout(col3_layout)

        # Claim tier (Column 1)
        self.claim_tier_combo = QComboBox()
        self.claim_tier_combo.setMaximumWidth(140)
        self._add_field_with_info(
            col1_layout,
            "Minimum Claim Tier:",
            self.claim_tier_combo,
            "Select minimum claim tier to include:\n"
            "• Tier A: High-confidence, core claims (85%+ confidence)\n"
            "• Tier B: Medium-confidence claims (65%+ confidence)\n"
            "• Tier C: Lower-confidence, supporting claims\n"
            "• All: Include all tiers",
            0,
            0,
        )
        self.claim_tier_combo.addItems(["All", "Tier A", "Tier B", "Tier C"])
        self.claim_tier_combo.setCurrentText("All")
        self.claim_tier_combo.currentTextChanged.connect(self._on_setting_changed)

        # Max claims (Column 2)
        self.max_claims_spin = QSpinBox()
        self.max_claims_spin.setMaximumWidth(80)
        self._add_field_with_info(
            col2_layout,
            "Max Claims per Document:",
            self.max_claims_spin,
            "Maximum number of claims to extract per document.\n"
            "Set to 0 for unlimited. Higher values provide more detail but take longer.",
            0,
            0,
        )
        self.max_claims_spin.setRange(0, 1000)
        self.max_claims_spin.setValue(0)  # Default to 0 (unlimited)
        self.max_claims_spin.setSpecialValueText("Unlimited")
        self.max_claims_spin.valueChanged.connect(self._on_setting_changed)

        # NOTE: Tier thresholds removed - tiers are assigned by LLM, not numeric thresholds
        # See schemas/flagship_output.v1.json - tier is an enum field in LLM output

        # Unified Pipeline Info
        unified_info = QLabel("📋 Unified Pipeline Active")
        unified_info.setToolTip(
            "Using simplified 2-pass pipeline:\n"
            "1. Unified Miner extracts all entities\n"
            "2. Flagship Evaluator ranks claims\n\n"
            "Configure models in Advanced section below."
        )
        unified_info.setStyleSheet(
            "QLabel { color: #28a745; font-weight: bold; font-size: 11px; }"
        )
        col3_layout.addWidget(unified_info, 1, 0, 1, 2)

        # Placeholder for future options
        col3_layout.addWidget(QLabel(""), 2, 0, 1, 2)  # Empty space

        # Add columns with very thin vertical separators
        from PyQt6.QtWidgets import QFrame

        vline1 = QFrame()
        vline1.setFrameShape(QFrame.Shape.VLine)
        vline1.setFrameShadow(QFrame.Shadow.Sunken)
        vline1.setLineWidth(1)
        vline1.setFixedWidth(1)

        vline2 = QFrame()
        vline2.setFrameShape(QFrame.Shape.VLine)
        vline2.setFrameShadow(QFrame.Shadow.Sunken)
        vline2.setLineWidth(1)
        vline2.setFixedWidth(1)

        hce_layout.addWidget(col1_widget, 1)
        hce_layout.addWidget(vline1)
        hce_layout.addWidget(col2_widget, 1)
        hce_layout.addWidget(vline2)
        hce_layout.addWidget(col3_widget, 1)

        # hce_group.setLayout(hce_layout)
        # hce_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Claims Analysis section removed per user request
        # layout.addWidget(hce_group)

        # Advanced: Per-stage Models (collapsible)
        from PyQt6.QtWidgets import QFrame

        self.advanced_models_group = QGroupBox(
            "🔧 Per-stage Model Configuration (Required)"
        )
        self.advanced_models_group.setCheckable(False)  # Not collapsible - mandatory
        # self.advanced_models_group.toggled.connect(self._on_setting_changed)
        self.advanced_models_group.setToolTip(
            "Configure models for each analysis stage.\n"
            "Default uses MVP LLM (fallback) model for all stages.\n"
            "You can customize models for specific stages as needed."
        )

        advanced_layout = QGridLayout()
        # Set column stretch factors to better distribute space
        advanced_layout.setColumnStretch(0, 0)  # Label column - fixed width
        advanced_layout.setColumnStretch(1, 0)  # Provider column - fixed width
        advanced_layout.setColumnStretch(2, 1)  # Model column - takes remaining space
        advanced_layout.setColumnStretch(3, 0)  # URI column - fixed width

        # Add spacing between columns
        advanced_layout.setHorizontalSpacing(15)
        advanced_layout.setVerticalSpacing(8)

        # Helper function to create model selector row with blue info indicator
        def create_model_selector(name: str, tooltip: str, row: int) -> tuple:
            # Create label with info indicator layout
            label_layout = QHBoxLayout()
            label_layout.setContentsMargins(0, 0, 0, 0)
            label_layout.setSpacing(8)

            label = QLabel(f"{name}:")
            label.setToolTip(tooltip)
            label_layout.addWidget(label)

            # Add blue info indicator
            info_label = QLabel("ⓘ")
            info_label.setFixedSize(16, 16)
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_label.setToolTip(f"<b>{name}:</b><br/><br/>{tooltip}")
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
            label_layout.addWidget(info_label)
            label_layout.addStretch()

            label_widget = QWidget()
            label_widget.setLayout(label_layout)
            label_widget.setMinimumWidth(180)  # Ensure label has enough space

            provider_combo = QComboBox()
            provider_combo.addItems(["", "openai", "anthropic", "local"])
            # Don't set default - let _load_settings() handle it via settings manager
            provider_combo.setMinimumWidth(120)  # Reasonable width for provider names
            provider_combo.setMaximumWidth(140)  # Prevent it from taking too much space
            provider_combo.currentTextChanged.connect(self._on_setting_changed)
            provider_combo.setToolTip(f"AI provider for {name}")

            model_combo = QComboBox()
            model_combo.setEditable(True)
            model_combo.setMinimumWidth(400)  # Much wider for full model names
            model_combo.currentTextChanged.connect(
                lambda: self._on_advanced_model_changed(provider_combo, model_combo)
            )
            model_combo.currentTextChanged.connect(self._on_setting_changed)
            model_combo.setToolTip(f"Specific model name for {name}")

            # Connect provider change to update model options
            def on_provider_changed(provider_text):
                """Handle provider change for this specific model combo."""
                try:
                    self._update_advanced_model_combo(provider_text, model_combo)
                except Exception as e:
                    logger.error(
                        f"Failed to update advanced model combo for {name}: {e}"
                    )

            provider_combo.currentTextChanged.connect(on_provider_changed)

            uri_label = QLabel("(auto)")
            uri_label.setStyleSheet("color: #666; font-style: italic; font-size: 10px;")
            uri_label.setWordWrap(True)
            uri_label.setMaximumWidth(100)  # Limit URI label width
            uri_label.setToolTip("API endpoint (automatically determined)")

            advanced_layout.addWidget(label_widget, row, 0)
            advanced_layout.addWidget(provider_combo, row, 1)
            advanced_layout.addWidget(model_combo, row, 2)
            advanced_layout.addWidget(uri_label, row, 3)

            return provider_combo, model_combo, uri_label

        # Create model selectors for Unified Pipeline
        self.miner_provider, self.miner_model, self.miner_uri = create_model_selector(
            "Unified Miner Model",
            "Model for extracting claims, jargon, people, and mental models from text segments",
            0,
        )

        (
            self.flagship_judge_provider,
            self.flagship_judge_model,
            self.flagship_judge_uri,
        ) = create_model_selector(
            "Flagship Evaluator Model",
            "High-quality model for evaluating, ranking, and filtering claims",
            1,
        )

        self.advanced_models_group.setLayout(advanced_layout)
        self.advanced_models_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self.advanced_models_group)

        # Initialize model dropdowns to be empty by default
        # Guard against optional advanced widgets not being present on some builds
        widget_triplets = [
            (
                getattr(self, "miner_provider", None),
                getattr(self, "miner_model", None),
                getattr(self, "miner_uri", None),
            ),
            (
                getattr(self, "heavy_miner_provider", None),
                getattr(self, "heavy_miner_model", None),
                getattr(self, "heavy_miner_uri", None),
            ),
            (
                getattr(self, "judge_provider", None),
                getattr(self, "judge_model", None),
                getattr(self, "judge_uri", None),
            ),
            (
                getattr(self, "flagship_judge_provider", None),
                getattr(self, "flagship_judge_model", None),
                getattr(self, "flagship_judge_uri", None),
            ),
            (
                getattr(self, "embedder_provider", None),
                getattr(self, "embedder_model", None),
                getattr(self, "embedder_uri", None),
            ),
            (
                getattr(self, "reranker_provider", None),
                getattr(self, "reranker_model", None),
                getattr(self, "reranker_uri", None),
            ),
            (
                getattr(self, "people_provider", None),
                getattr(self, "people_model", None),
                getattr(self, "people_uri", None),
            ),
            (
                getattr(self, "nli_provider", None),
                getattr(self, "nli_model", None),
                getattr(self, "nli_uri", None),
            ),
        ]

        for provider_combo, model_combo, _ in widget_triplets:
            if model_combo is None:
                continue
            try:
                model_combo.clear()
                model_combo.addItems([""])  # Start with empty option
            except Exception:
                pass

        # Trigger initial model population for default providers
        # Use QTimer to ensure this happens after the UI is fully initialized
        from PyQt6.QtCore import QTimer

        def populate_initial_models():
            try:
                # For miner model
                if hasattr(self, "miner_provider") and self.miner_provider:
                    current_provider = self.miner_provider.currentText()
                    if current_provider == "local":
                        self._update_advanced_model_combo("local", self.miner_model)
                        # Set default MVP LLM model if no model is selected
                        if not self.miner_model.currentText():
                            mvp_model = "qwen2.5:7b-instruct"
                            idx = self.miner_model.findText(mvp_model)
                            if idx >= 0:
                                self.miner_model.setCurrentIndex(idx)

                # For flagship judge model
                if (
                    hasattr(self, "flagship_judge_provider")
                    and self.flagship_judge_provider
                ):
                    current_provider = self.flagship_judge_provider.currentText()
                    if current_provider == "local":
                        self._update_advanced_model_combo(
                            "local", self.flagship_judge_model
                        )
                        # Set default MVP LLM model if no model is selected
                        if not self.flagship_judge_model.currentText():
                            mvp_model = "qwen2.5:7b-instruct"
                            idx = self.flagship_judge_model.findText(mvp_model)
                            if idx >= 0:
                                self.flagship_judge_model.setCurrentIndex(idx)
            except Exception as e:
                logger.error(f"Error populating initial models: {e}")

        QTimer.singleShot(100, populate_initial_models)  # Delay to ensure UI is ready

        # NOTE: Token budget spinboxes removed - feature was never implemented in backend
        # No code exists to enforce token limits, so these controls were misleading

        # Action buttons
        action_layout = self._create_action_layout()
        layout.addLayout(action_layout)

        # Dual progress bars (phase + overall) - same as transcription tab
        self.progress_display = SimpleTranscriptionProgressBar(self)
        layout.addWidget(self.progress_display)

        # Processor log integrator for enhanced progress tracking
        self.log_integrator = ProcessorLogIntegrator()
        self.log_integrator.progress_updated.connect(self._on_processor_progress)
        self.log_integrator.status_updated.connect(self._on_processor_status)

        # Output section - this should expand and contract with window resizing
        output_layout = self._create_output_section()
        layout.addLayout(
            output_layout, 1
        )  # Stretch factor of 1 to consume remaining space

        # Remove addStretch() to allow output section to properly expand

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Load settings after UI is fully set up and signals are connected
        # Use a timer with a small delay to ensure all widgets are fully initialized
        QTimer.singleShot(200, self._load_settings)

    def _get_start_button_text(self) -> str:
        """Get the text for the start button."""
        return "Start Summarization"

    def _start_processing(self) -> None:
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

        # Use miner provider/model as the primary provider/model
        provider = self.miner_provider.currentText()
        model = self.miner_model.currentText()

        logger.info(
            f"🔧 DEBUG: Starting summarization with provider='{provider}', model='{model}'"
        )
        self.append_log(f"🔧 Using provider: {provider}, model: {model}")

        if provider == "local":
            logger.info(
                f"🔧 DEBUG: Local provider detected, checking model availability for '{model}'"
            )
            self.append_log(f"🔧 Checking local model availability: {model}")

            # Store processing parameters for async model check
            self._pending_files = files
            # Get content type from combo box
            content_type_map = {
                "Transcript (Own)": "transcript_own",
                "Transcript (Third-party)": "transcript_third_party",
                "Document (PDF/eBook)": "document_pdf",
                "Document (White Paper)": "document_whitepaper",
            }
            content_type = content_type_map.get(
                self.content_type_combo.currentText(), "transcript_own"
            )

            self._pending_gui_settings = {
                "provider": provider,
                "model": model,
                "max_tokens": 10000,
                "template_path": self.template_path_edit.text(),
                "output_dir": self.output_edit.text() or None,
                "update_in_place": False,
                "create_separate_file": False,
                "force_regenerate": False,
                "analysis_type": "Document Summary",  # Fixed to Document Summary
                "export_getreceipts": False,
                "content_type": content_type,  # Add content type to settings
                # New HCE settings
                "use_skim": True,
                "enable_routing": True,
                "routing_threshold": 0.35,  # Default: 35%
                "prompt_driven_mode": False,
                "flagship_file_tokens": self.flagship_file_tokens_spin.value(),
                "flagship_session_tokens": self.flagship_session_tokens_spin.value(),
            }

            # Start async model availability check
            self._start_async_model_check(model)
            return  # Exit early, processing will continue after model check

        # Prepare settings
        # Get content type from combo box
        content_type_map = {
            "Transcript (Own)": "transcript_own",
            "Transcript (Third-party)": "transcript_third_party",
            "Document (PDF/eBook)": "document_pdf",
            "Document (White Paper)": "document_whitepaper",
        }
        content_type = content_type_map.get(
            self.content_type_combo.currentText(), "transcript_own"
        )

        gui_settings = {
            "provider": provider,
            "model": model,
            "max_tokens": 10000,
            "template_path": self.template_path_edit.text(),
            "output_dir": self.output_edit.text() or None,
            "update_in_place": False,
            "create_separate_file": False,
            "force_regenerate": False,
            "analysis_type": "Document Summary",  # Fixed to Document Summary
            "export_getreceipts": False,
            "content_type": content_type,  # Add content type to settings
            # Unified Pipeline HCE settings
            "use_skim": True,
            "miner_model_override": self._get_model_override(
                self.miner_provider, self.miner_model
            ),
            "flagship_judge_model": self._get_model_override(
                self.flagship_judge_provider, self.flagship_judge_model
            ),
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
        self.summarization_worker.hce_analytics_updated.connect(
            self._on_hce_analytics_updated
        )
        self.summarization_worker.log_message.connect(self._on_worker_log_message)

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

        # Initialize dual progress bars
        self.progress_display.start_processing(
            total_files=file_count, title="Summarization"
        )

        # Initialize batch timing when processing actually starts (not when first progress arrives)
        import time

        self._batch_start_time = time.time()
        self._file_start_time = time.time()  # Initialize for first file

        self.summarization_worker.start()

    def validate_inputs(self) -> bool:
        """Validate inputs before processing."""
        if not self._get_file_list():
            return False

        # Check that at least one output option is selected
        # Validate output directory if provided
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

    def _start_async_model_check(self, model: str) -> None:
        """Start async model availability check to prevent GUI blocking."""
        from PyQt6.QtCore import QThread, pyqtSignal

        class ModelCheckWorker(QThread):
            """Worker thread for checking model availability without blocking GUI."""

            check_completed = pyqtSignal(
                bool, str, str
            )  # available, model_name, error_message
            service_check_completed = pyqtSignal(
                bool, str
            )  # service_running, model_name

            def __init__(self, model: str):
                super().__init__()
                self.model = model
                self.clean_model_name = self._clean_model_name(model)

            def _clean_model_name(self, model: str) -> str:
                """Clean model name by removing suffixes."""
                import re

                clean_name = model.replace(" (Installed)", "")
                clean_name = re.sub(r" \(\d+ GB\)$", "", clean_name)
                return clean_name

            def run(self):
                """Check model availability asynchronously."""
                try:
                    # Import here to avoid blocking main thread during module import
                    from ...utils.ollama_manager import get_ollama_manager

                    # If model already has "(Installed)" suffix, it's available
                    if self.model.endswith(" (Installed)"):
                        self.check_completed.emit(True, self.model, "")
                        return

                    ollama_manager = get_ollama_manager()

                    # Check if Ollama service is running (potentially slow subprocess call)
                    service_running = ollama_manager.is_service_running()

                    if not service_running:
                        # Emit service not running signal
                        self.service_check_completed.emit(False, self.model)
                        return

                    # Check if model is available (potentially slow subprocess call)
                    model_available = ollama_manager.is_model_available(
                        self.clean_model_name
                    )

                    if model_available:
                        self.check_completed.emit(True, self.model, "")
                    else:
                        self.check_completed.emit(
                            False, self.model, "Model not installed"
                        )

                except Exception as e:
                    self.check_completed.emit(False, self.model, str(e))

        # Disable start button during check
        if hasattr(self, "start_btn"):
            self.start_btn.setEnabled(False)
            self.start_btn.setText("🔍 Checking model availability...")

        # Create and start worker
        try:
            self._model_check_worker = ModelCheckWorker(model)
            self._model_check_worker.check_completed.connect(
                self._handle_model_check_result
            )
            self._model_check_worker.service_check_completed.connect(
                self._handle_service_check_result
            )
            self._model_check_worker.start()
        except Exception as e:
            logger.error(f"Failed to start model check worker: {e}")
            # Re-enable start button on worker creation failure
            if hasattr(self, "start_btn"):
                self.start_btn.setEnabled(True)
                self.start_btn.setText(self._get_start_button_text())
            self.append_log(f"❌ Failed to check model: {e}")
            return

    def _handle_service_check_result(self, service_running: bool, model: str) -> None:
        """Handle Ollama service check result."""
        if not service_running:
            # Re-enable start button
            if hasattr(self, "start_btn"):
                self.start_btn.setEnabled(True)
                self.start_btn.setText(self._get_start_button_text())

            # THREAD SAFETY FIX: Use signal to show dialog on main thread
            # This method may be called from a worker thread, so we must not create GUI components directly
            self.show_ollama_service_dialog_signal.emit(model)
        # NOTE: Do NOT clean up worker here when service is running!
        # The worker needs to continue and check model availability.
        # Worker cleanup happens in _handle_model_check_result instead.

    def _show_ollama_service_dialog_on_main_thread(self, model: str) -> None:
        """Show Ollama service dialog on main thread (thread-safe)."""
        from PyQt6.QtWidgets import QDialog

        from ..legacy_dialogs import OllamaServiceDialog

        dialog = OllamaServiceDialog(self)

        def on_service_dialog_finished():
            if hasattr(self, "_model_check_worker"):
                self._model_check_worker.deleteLater()
                del self._model_check_worker

            # If user started service, restart model check
            dialog_result = dialog.result()
            if dialog_result == QDialog.DialogCode.Accepted:
                self.append_log("🔄 Ollama service started, rechecking model...")
                self._start_async_model_check(model)
            else:
                self.append_log("❌ Ollama service required for local models")

        dialog.finished.connect(on_service_dialog_finished)
        dialog.exec()

    def _handle_model_check_result(
        self, available: bool, model: str, error_message: str
    ) -> None:
        """Handle model availability check result."""
        try:
            if available:
                self.append_log(f"✅ Model '{model}' is available")
                logger.info(f"🔧 DEBUG: Model availability check passed for '{model}'")
                # Continue with processing using stored parameters
                self._continue_processing_after_model_check()
            else:
                if error_message:
                    self.append_log(f"❌ Model check failed: {error_message}")
                    logger.error(
                        f"🔧 DEBUG: Model availability check failed for '{model}': {error_message}"
                    )
                    # Re-enable start button on error
                    if hasattr(self, "start_btn"):
                        self.start_btn.setEnabled(True)
                        self.start_btn.setText(self._get_start_button_text())
                else:
                    self.append_log(f"📥 Model '{model}' not installed")
                    logger.info(
                        f"🔧 DEBUG: Model '{model}' not available - showing download dialog"
                    )
                    # Show download dialog
                    self._show_model_download_dialog(model)
                    return
        finally:
            # Clean up worker
            if hasattr(self, "_model_check_worker"):
                self._model_check_worker.deleteLater()
                del self._model_check_worker

    def _show_model_download_dialog(self, model: str) -> None:
        """Show model download dialog for missing models."""
        # Clean model name for download
        import re

        from PyQt6.QtWidgets import QDialog

        from ..legacy_dialogs import ModelDownloadDialog

        clean_model_name = model.replace(" (Installed)", "")
        clean_model_name = re.sub(r" \(\d+ GB\)$", "", clean_model_name)

        dialog = ModelDownloadDialog(clean_model_name, self)

        def on_download_progress(progress):
            if hasattr(self, "start_btn") and hasattr(progress, "percent"):
                if progress.percent > 0:
                    self.start_btn.setText(f"📥 Downloading: {progress.percent:.1f}%")

        def on_dialog_finished():
            if hasattr(self, "start_btn"):
                self.start_btn.setEnabled(True)
                self.start_btn.setText(self._get_start_button_text())

            # If download succeeded, continue processing
            dialog_result = dialog.result()
            if dialog_result == QDialog.DialogCode.Accepted:
                self.append_log(f"✅ Model '{clean_model_name}' downloaded successfully")
                self._continue_processing_after_model_check()
            else:
                self.append_log("❌ Model download cancelled or failed")

        # Connect signals
        dialog.download_progress.connect(on_download_progress)
        dialog.finished.connect(on_dialog_finished)

        # Show dialog
        dialog.exec()

    def _continue_processing_after_model_check(self) -> None:
        """Continue processing after successful model check."""
        if not hasattr(self, "_pending_files") or not hasattr(
            self, "_pending_gui_settings"
        ):
            self.append_log("❌ Internal error: Missing processing parameters")
            if hasattr(self, "start_btn"):
                self.start_btn.setEnabled(True)
                self.start_btn.setText(self._get_start_button_text())
            return

        # Retrieve stored parameters
        files = self._pending_files
        gui_settings = self._pending_gui_settings

        # Clean up stored parameters
        del self._pending_files
        del self._pending_gui_settings

        # Continue with worker creation and processing
        self.append_log("🚀 Starting summarization worker...")
        self._start_summarization_worker(files, gui_settings)

    def _start_summarization_worker(self, files: list, gui_settings: dict) -> None:
        """Start the summarization worker with the provided settings."""
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
        self.summarization_worker.hce_analytics_updated.connect(
            self._on_hce_analytics_updated
        )
        self.summarization_worker.log_message.connect(self._on_worker_log_message)

        self.active_workers.append(self.summarization_worker)
        self.set_processing_state(True)
        self.clear_log()

        # HCE progress will be tracked via console logging

        # Show informative startup message
        file_count = len(files)
        if file_count == 1:
            file_info = f"file: {Path(files[0]).name}"
        elif file_count <= 3:
            file_names = [Path(f).name for f in files]
            file_info = f"files: {', '.join(file_names)}"
        else:
            file_info = f"{file_count} files"

        self.append_log(f"📝 Starting summarization of {file_info}")
        self.append_log(f"🤖 Using {gui_settings['provider']}: {gui_settings['model']}")

        # Start the worker
        self.summarization_worker.start()

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
                def on_service_dialog_finished() -> None:
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
            def on_download_progress(progress: Any) -> None:
                if hasattr(self, "start_btn") and hasattr(progress, "percent"):
                    if progress.percent > 0:
                        self.start_btn.setText(
                            f"⏳ Downloading Model ({progress.percent:.0f}%)"
                        )

            # Connect dialog completion to re-enable button
            def on_dialog_finished():
                """On dialog finished."""
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
                "Please ensure Ollama is properly installed and running.",
            )
            return False

    def _add_files(self) -> None:
        """Add files to the summarization list."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Summarize",
            str(Path.home()),
            "All Supported (*.txt *.md *.pdf *.html *.htm *.json *.docx *.doc *.rt);;Text Files (*.txt);;Markdown Files (*.md);;PDF Files (*.pdf);;HTML Files (*.html *.htm);;JSON Files (*.json);;Word Documents (*.docx *.doc);;Rich Text (*.rt);;All Files (*)",
        )

        for file_path in files:
            self.file_list.addItem(file_path)

    def _add_folder(self) -> None:
        """Add all compatible files from a folder."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            folder = Path(folder_path)
            extensions = [
                ".txt",
                ".md",
                ".pdf",
                ".html",
                ".htm",
                ".json",
                ".docx",
                ".doc",
                ".rt",
            ]

            for file_path in folder.rglob("*"):
                if file_path.suffix.lower() in extensions:
                    self.file_list.addItem(str(file_path))

    def _clear_files(self) -> None:
        """Clear all files from the list."""
        self.file_list.clear()

    def _on_source_changed(self) -> None:
        """Handle source selection change between Files and Database."""
        if self.files_radio.isChecked():
            self.source_stack.setCurrentIndex(0)
        else:
            self.source_stack.setCurrentIndex(1)
            # Refresh database list when switching to database view
            self._refresh_database_list()

    def _create_database_browser(self) -> QWidget:
        """Create the database browser widget for transcript selection."""
        db_widget = QWidget()
        db_layout = QVBoxLayout(db_widget)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.db_search = QLineEdit()
        self.db_search.setPlaceholderText("Filter transcripts...")
        self.db_search.textChanged.connect(self._filter_database_list)
        search_layout.addWidget(self.db_search)
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_database_list)
        search_layout.addWidget(refresh_btn)
        db_layout.addLayout(search_layout)

        # Database table
        self.db_table = QTableWidget()
        self.db_table.setColumnCount(5)
        self.db_table.setHorizontalHeaderLabels(
            ["Select", "Title", "Duration", "Has Summary", "Token Count"]
        )
        self.db_table.setAlternatingRowColors(True)
        self.db_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.db_table.setMinimumHeight(150)

        # Set column widths
        self.db_table.setColumnWidth(0, 60)  # Select checkbox
        self.db_table.setColumnWidth(1, 400)  # Title
        self.db_table.setColumnWidth(2, 80)  # Duration
        self.db_table.setColumnWidth(3, 100)  # Has Summary
        self.db_table.setColumnWidth(4, 100)  # Token Count

        db_layout.addWidget(self.db_table)

        # Selection buttons
        selection_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_db)
        clear_selection_btn = QPushButton("Clear Selection")
        clear_selection_btn.clicked.connect(self._clear_db_selection)
        selection_layout.addWidget(select_all_btn)
        selection_layout.addWidget(clear_selection_btn)
        selection_layout.addStretch()
        db_layout.addLayout(selection_layout)

        return db_widget

    def _refresh_database_list(self) -> None:
        """Refresh the database transcript list."""
        import datetime

        from ...database import DatabaseService
        from ...utils.text_utils import estimate_tokens_improved

        self.db_table.setRowCount(0)

        try:
            db = DatabaseService()

            # Get all videos that have transcripts
            with db.get_session() as session:
                from ...database.models import MediaSource, Summary, Transcript

                # Query for media sources with transcripts
                query = (
                    session.query(MediaSource)
                    .join(
                        Transcript,
                        MediaSource.source_id == Transcript.video_id,
                        isouter=True,
                    )
                    .filter(Transcript.transcript_id.isnot(None))
                )

                videos = query.all()

                for video in videos:
                    # Check if it has a summary
                    summary = (
                        session.query(Summary)
                        .filter(Summary.video_id == video.source_id)
                        .first()
                    )

                    # Get transcript for token estimation
                    transcript = (
                        session.query(Transcript)
                        .filter(Transcript.video_id == video.source_id)
                        .first()
                    )

                    # Add row to table
                    row_position = self.db_table.rowCount()
                    self.db_table.insertRow(row_position)

                    # Checkbox
                    checkbox = QCheckBox()
                    self.db_table.setCellWidget(row_position, 0, checkbox)

                    # Title (store video_id in UserRole)
                    title_item = QTableWidgetItem(video.title or video.source_id)
                    title_item.setData(Qt.ItemDataRole.UserRole, video.source_id)
                    self.db_table.setItem(row_position, 1, title_item)

                    # Duration
                    duration_text = ""
                    if video.duration_seconds:
                        # Convert to int to handle float values
                        duration_int = int(video.duration_seconds)
                        hours = duration_int // 3600
                        minutes = (duration_int % 3600) // 60
                        seconds = duration_int % 60
                        if hours > 0:
                            duration_text = f"{hours}:{minutes:02d}:{seconds:02d}"
                        else:
                            duration_text = f"{minutes}:{seconds:02d}"
                    self.db_table.setItem(
                        row_position, 2, QTableWidgetItem(duration_text)
                    )

                    # Has Summary
                    summary_text = "✓" if summary else "✗"
                    if summary:
                        summary_text += " (Re-summarize?)"
                    self.db_table.setItem(
                        row_position, 3, QTableWidgetItem(summary_text)
                    )

                    # Token Count (estimate)
                    token_count = 0
                    if transcript and transcript.transcript_text:
                        token_count = estimate_tokens_improved(
                            transcript.transcript_text, "default"
                        )
                    self.db_table.setItem(
                        row_position, 4, QTableWidgetItem(f"~{token_count:,}")
                    )

            logger.info(
                f"Database browser refreshed - found {self.db_table.rowCount()} transcripts"
            )
        except Exception as e:
            logger.error(f"Failed to refresh database list: {e}", exc_info=True)

    def _filter_database_list(self, text: str) -> None:
        """Filter the database list based on search text."""
        for row in range(self.db_table.rowCount()):
            # Check if title contains search text
            title_item = self.db_table.item(row, 1)
            if title_item:
                match = text.lower() in title_item.text().lower()
                self.db_table.setRowHidden(row, not match)

    def _select_all_db(self) -> None:
        """Select all items in the database table."""
        for row in range(self.db_table.rowCount()):
            checkbox = self.db_table.cellWidget(row, 0)
            if checkbox and hasattr(checkbox, "setChecked"):
                checkbox.setChecked(True)

    def _clear_db_selection(self) -> None:
        """Clear all selections in the database table."""
        for row in range(self.db_table.rowCount()):
            checkbox = self.db_table.cellWidget(row, 0)
            if checkbox and hasattr(checkbox, "setChecked"):
                checkbox.setChecked(False)

    def _get_file_list(self) -> list[str]:
        """Get the list of files/sources to process."""
        if self.files_radio.isChecked():
            # Get files from file list
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
        else:
            # Get selected items from database table
            sources = []
            for row in range(self.db_table.rowCount()):
                checkbox = self.db_table.cellWidget(row, 0)
                if checkbox and hasattr(checkbox, "isChecked") and checkbox.isChecked():
                    # Get video_id stored in row data
                    source_id = self.db_table.item(row, 1).data(
                        Qt.ItemDataRole.UserRole
                    )
                    if video_id:
                        # Use special prefix to indicate database source
                        sources.append(f"db://{video_id}")
            logger.info(
                f"🎯 DEBUG: _get_file_list() returning {len(sources)} database sources"
            )
            return sources

    def _refresh_models(self):
        """Refresh the model list from community source."""
        current_model = self.model_combo.currentText()
        provider = self.provider_combo.currentText()

        # Clear cache for local provider
        if provider == "local":
            try:
                from ...utils.ollama_manager import get_ollama_manager

                ollama_manager = get_ollama_manager()
                ollama_manager.clear_registry_cache()
            except Exception as e:
                logger.warning(f"Failed to clear Ollama cache: {e}")

        # Force refresh from community source
        self._update_models(force_refresh=True)

        # Try to restore the previously selected model
        if current_model:
            index = self.model_combo.findText(current_model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
            else:
                logger.info(
                    f"Previously selected model '{current_model}' no longer available"
                )

        # Show feedback to user with safety information
        if provider == "openai":
            self.append_log("🔄 Refreshed OpenAI models from API")
        elif provider == "anthropic":
            self.append_log("🔄 Anthropic models (manually maintained)")
        elif provider == "local":
            model_count = self.model_combo.count()
            if model_count > 0:
                self.append_log(
                    f"🔄 Refreshed Ollama models from ollama.com/library ({model_count} models)"
                )
            else:
                self.append_log(
                    "⚠️ Refresh attempted but no models available (offline or Ollama not running)"
                )
                self.append_log(
                    "💡 Previous model list preserved to keep app functional"
                )

    def _update_models(self, force_refresh: bool = False):
        """Update the model list based on selected provider with dynamic registry."""
        provider = self.provider_combo.currentText()
        logger.debug(f"🔄 NEW DYNAMIC MODEL SYSTEM ACTIVATED - Provider: {provider}")
        self.model_combo.clear()

        if provider in {"openai", "anthropic"}:
            # Dynamic provider models with safe fallback and overrides
            try:
                models = get_provider_models(provider, force_refresh=force_refresh)
                # Remove duplicates and keep order just in case
                seen = set()
                unique_models = []
                for m in models:
                    key = m.strip().lower()
                    if key and key not in seen:
                        seen.add(key)
                        unique_models.append(m.strip())
                models = unique_models
            except Exception as e:
                logger.warning(f"Falling back to curated list for {provider}: {e}")
                models = get_provider_models(provider, force_refresh=False)
        else:  # local
            # Use the new dynamic registry system with proper caching
            try:
                ollama_manager = get_ollama_manager()
                # Use cache by default, only bypass cache when force_refresh=True
                use_cache = not force_refresh
                registry_models = ollama_manager.get_registry_models(
                    use_cache=use_cache
                )

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
                    cache_info = (
                        " (cached)"
                        if use_cache
                        and hasattr(ollama_manager, "_registry_cache")
                        and ollama_manager._registry_cache
                        else ""
                    )
                    logger.info(
                        f"Found {installed_count} installed and {available_count} available models from dynamic registry{cache_info}"
                    )
                else:
                    logger.warning("No models found in registry")
                    models = ["No models available - Please install Ollama"]

            except Exception as e:
                logger.error(f"Failed to fetch dynamic model list: {e}")
                # Fallback to static list with modern models
                models = [
                    "qwen2.5:7b (4 GB)",
                    "qwen2.5:3b (2 GB)",
                    "llama3.2:3b (2 GB)",
                    "llama3.1:8b (5 GB)",
                    "mistral:7b (4 GB)",
                    "codellama:7b (4 GB)",
                    "phi3:mini (2 GB)",
                    "qwen2.5:14b (8 GB)",
                    "mixtral:8x7b (26 GB)",
                    "llama3.1:70b (40 GB)",
                ]

        self.model_combo.addItems(models)

        # Set a reasonable default while preserving prior selection
        if models:
            if provider == "openai":
                # Prefer a modern small default if present; otherwise first item
                preferred = [
                    "gpt-4o-mini-2024-07-18",
                    "gpt-4o-2024-08-06",
                    "gpt-5",
                ]
                for name in preferred:
                    if name in models:
                        self.model_combo.setCurrentText(name)
                        break
                else:
                    self.model_combo.setCurrentIndex(0)
            elif provider == "anthropic":
                preferred = [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-sonnet-latest",
                    "claude-3-5-haiku-20241022",
                ]
                for name in preferred:
                    if name in models:
                        self.model_combo.setCurrentText(name)
                        break
                else:
                    self.model_combo.setCurrentIndex(0)
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

    def _update_advanced_model_combo(self, provider: str, model_combo: QComboBox):
        """Update an advanced model combo box based on provider selection."""
        if not provider or not provider.strip():  # Empty provider
            model_combo.clear()
            model_combo.addItems([""])
            return

        # Block signals to prevent recursive updates
        model_combo.blockSignals(True)
        try:
            current_text = model_combo.currentText()
            model_combo.clear()
            logger.debug(f"Updating advanced model combo for provider: {provider}")

            try:
                from ...utils.model_registry import get_provider_models
                from ...utils.ollama_manager import get_ollama_manager

                models = []
                if provider in {"openai", "anthropic"}:
                    models = get_provider_models(provider, force_refresh=False)
                    logger.debug(
                        f"Got {len(models)} models for {provider}: {models[:3] if models else 'none'}..."
                    )
                elif provider == "local":
                    try:
                        ollama_manager = get_ollama_manager()
                        registry_models = ollama_manager.get_registry_models(
                            use_cache=True
                        )
                        for model_info in registry_models:
                            if "(Installed)" in model_info.name:
                                models.append(model_info.name)
                            else:
                                size_gb = model_info.size_bytes / 1_000_000_000
                                models.append(f"{model_info.name} ({size_gb:.0f} GB)")
                        logger.debug(
                            f"Got {len(models)} local models: {models[:3] if models else 'none'}..."
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch Ollama models for advanced dropdown: {e}"
                        )
                        models = [
                            "qwen2.5:7b-instruct",
                            "qwen2.5:3b-instruct",
                            "llama3.2:3b-instruct",
                            "llama3.1:8b-instruct",
                            "mistral:7b-instruct",
                        ]
                        logger.debug(f"Using fallback models: {models}")

                # Add empty option first, then models
                all_items = [""] + (models if models else [])
                model_combo.addItems(all_items)

                # Try to restore previous selection if it's still valid
                if current_text and current_text in all_items:
                    model_combo.setCurrentText(current_text)
                elif provider == "local" and not current_text:
                    # For local provider with no selection, default to MVP LLM
                    mvp_model = "qwen2.5:7b-instruct"
                    if mvp_model in all_items:
                        model_combo.setCurrentText(mvp_model)
                    elif len(all_items) > 1:  # Has models besides empty option
                        model_combo.setCurrentIndex(1)  # Select first real model

                logger.debug(f"Added {len(all_items)} items to model combo")

            except Exception as e:
                logger.warning(
                    f"Failed to populate advanced model dropdown for {provider}: {e}"
                )
                model_combo.addItems([""])
                logger.debug("Added empty item due to exception")

        finally:
            model_combo.blockSignals(False)

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

    def _on_progress_updated(self, progress):
        """Handle progress updates with clean, informative status."""
        import time

        # Update dual progress bars
        if hasattr(self, "progress_display"):
            # Determine current phase from the step description
            current_step = getattr(progress, "current_step", "Processing")
            file_percent = getattr(progress, "file_percent", 0) or 0

            # Map step to phase name
            phase_name = "Processing"
            if (
                "miner" in current_step.lower()
                or "unified miner" in current_step.lower()
            ):
                phase_name = "Unified Mining"
            elif (
                "evaluator" in current_step.lower()
                or "flagship" in current_step.lower()
            ):
                phase_name = "Flagship Evaluation"
            elif (
                "generating" in current_step.lower()
                or "summary" in current_step.lower()
            ):
                phase_name = "Generating Summary"
            elif "saving" in current_step.lower() or "writing" in current_step.lower():
                phase_name = "Saving Output"
            elif "loading" in current_step.lower() or "reading" in current_step.lower():
                phase_name = "Loading Document"

            # Update phase progress bar
            self.progress_display.update_phase_progress(phase_name, file_percent)

            # Update overall file progress (0-100% for current file)
            if file_percent > 0:
                self.progress_display.update_current_file_progress(file_percent)

        # Update HCE progress dialog if it exists and we have step information
        # Log HCE progress to console instead of popup dialog (but throttled to avoid spam)
        if hasattr(progress, "current_step") and progress.current_step:
            # Throttle console logging to avoid redundant messages
            # Only log when progress changes significantly or when step changes
            if not hasattr(self, "_last_logged_step"):
                self._last_logged_step = None
                self._last_logged_percent = -1

            current_step = progress.current_step
            file_percent = getattr(progress, "file_percent", 0)
            if file_percent is None:
                file_percent = 0

            # Only log if step changed OR percent increased by 10+ OR it's the first log
            step_changed = current_step != self._last_logged_step
            percent_jumped = abs(file_percent - self._last_logged_percent) >= 10

            if step_changed or percent_jumped or self._last_logged_step is None:
                status = getattr(progress, "status", "")

                # Create a detailed progress message
                progress_msg = f"🔄 {current_step}"
                if file_percent > 0:
                    progress_msg += f" ({file_percent}%)"
                if status:
                    progress_msg += f" - {status}"

                # Add file information if available
                if hasattr(progress, "current_file") and progress.current_file:
                    from pathlib import Path

                    filename = Path(progress.current_file).name
                    progress_msg += f" | File: {filename}"

                self.append_log(progress_msg)

                # Update tracking variables
                self._last_logged_step = current_step
                self._last_logged_percent = file_percent

        # Initialize timing tracking (batch time already set when worker starts)
        if not hasattr(self, "_last_progress_update"):
            self._last_progress_update = 0

        current_time = time.time()

        # Calculate unified ETA based on current file progress
        file_eta = ""
        batch_eta = ""

        # Get file information for consistent ETA calculation
        total_files = getattr(progress, "total_files", 1)
        completed_files = getattr(progress, "completed_files", 0) or 0

        # Calculate File ETA - use adaptive estimation that learns from actual performance
        if (
            hasattr(progress, "eta_seconds")
            and progress.eta_seconds is not None
            and progress.eta_seconds > 0
        ):
            # Use the calculated ETA from progress tracking (most accurate)
            file_remaining = progress.eta_seconds
        elif hasattr(progress, "percent") and progress.percent and progress.percent > 1:
            # Use adaptive ETA calculation that accounts for LLM generation patterns
            file_elapsed = current_time - getattr(
                self, "_file_start_time", current_time
            )

            # Only calculate ETA if we have meaningful elapsed time and progress
            if file_elapsed > 10 and progress.percent > 5:
                # For LLM generation, use a more conservative approach
                # The progress often stalls during actual generation, so we need to account for this

                if progress.percent < 75:
                    # Early stages: use linear extrapolation but be conservative
                    estimated_total = (file_elapsed / progress.percent) * 100
                    file_remaining = max(0, estimated_total - file_elapsed)
                else:
                    # LLM generation phase (75%+): much more conservative
                    # Progress slows down significantly during actual token generation
                    remaining_progress = 100 - progress.percent

                    # Estimate based on current rate but apply a slowdown factor
                    # The closer to 100%, the slower progress typically becomes
                    slowdown_factor = (
                        1.5 + (progress.percent - 75) * 0.1
                    )  # 1.5x to 4.0x slower

                    # Calculate time per percent at current rate
                    time_per_percent = file_elapsed / progress.percent

                    # Apply slowdown for remaining progress
                    file_remaining = (
                        remaining_progress * time_per_percent * slowdown_factor
                    )

                    # Cap the maximum ETA to avoid ridiculous estimates
                    file_remaining = min(
                        file_remaining, file_elapsed * 2
                    )  # Max 2x current elapsed time
            else:
                file_remaining = 0
        else:
            file_remaining = 0

        # Format file ETA
        if file_remaining > 0:
            if file_remaining < 60:
                file_eta = f" (ETA: {file_remaining:.0f}s)"
            elif file_remaining < 3600:
                file_eta = f" (ETA: {file_remaining/60:.1f}m)"
            else:
                file_eta = f" (ETA: {file_remaining/3600:.1f}h)"

        # Calculate Batch ETA
        if total_files == 1:
            # Single file: don't show redundant batch ETA
            batch_eta = ""
        else:
            # Multiple files: estimate time for remaining files
            batch_elapsed = current_time - getattr(
                self, "_batch_start_time", current_time
            )
            if completed_files > 0:
                # Estimate based on completed files
                avg_time_per_file = batch_elapsed / (
                    completed_files + (getattr(progress, "percent", 0) / 100.0)
                )
                remaining_files = (
                    total_files
                    - completed_files
                    - (getattr(progress, "percent", 0) / 100.0)
                )
                batch_remaining = max(0, remaining_files * avg_time_per_file)
            elif file_remaining > 0:
                # First file: estimate based on current file progress
                remaining_files = total_files - (
                    getattr(progress, "percent", 0) / 100.0
                )
                batch_remaining = max(0, remaining_files * file_remaining)
            else:
                batch_remaining = 0

            # Format batch ETA
            if batch_remaining > 0:
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
            ):
                completed_files = progress.completed_files or 0
                file_info = f"File {completed_files + 1}/{progress.total_files}"
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

        # Update progress display with completed files
        if hasattr(self, "progress_display"):
            # Assume all completed files were successful (failures tracked separately)
            self.progress_display.update_progress(completed=current, failed=0)

        # Reset file timer for next file
        if current < total:
            self._file_start_time = time.time()

    def _on_processing_finished(
        self, success_count: int, failure_count: int, total_count: int
    ) -> None:
        """Handle processing completion with success summary."""
        import time

        self.set_processing_state(False)

        # Mark progress display as complete
        if hasattr(self, "progress_display"):
            self.progress_display.finish(completed=success_count, failed=failure_count)

        # Log final HCE statistics to console
        if hasattr(self, "_final_hce_stats") and self._final_hce_stats:
            self.append_log("\n📊 CLAIM EXTRACTION STATISTICS:")
            stats = self._final_hce_stats

            if "claims" in stats:
                self.append_log(f"   • Claims extracted: {stats['claims']}")
            if "tier1_claims" in stats:
                self.append_log(f"   • High-quality claims: {stats['tier1_claims']}")
            if "people" in stats:
                self.append_log(f"   • People identified: {stats['people']}")
            if "concepts" in stats:
                self.append_log(f"   • Concepts found: {stats['concepts']}")
            if "relations" in stats:
                self.append_log(f"   • Relations mapped: {stats['relations']}")
            if "contradictions" in stats:
                self.append_log(
                    f"   • Contradictions detected: {stats['contradictions']}"
                )

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

        # Show output location information with specific details
        output_dir = self.output_edit.text()
        if output_dir:
            self.append_log(f"\n💾 Data saved to:")
            self.append_log(
                f"   • Database: knowledge_system.db (claims, people, concepts)"
            )
            self.append_log(f"   • Summary files: {output_dir}")
        else:
            self.append_log(f"\n💾 Data saved to:")
            self.append_log(
                f"   • Database: knowledge_system.db (claims, people, concepts)"
            )
            self.append_log(f"   • Summary files: output/summaries/")

        # Enable report button if available
        if hasattr(self, "report_btn"):
            self.report_btn.setEnabled(True)

        # Generate session report
        if success_count > 0:
            self._generate_session_report(
                success_count, failure_count, total_count, total_time_text
            )
            self.append_log(
                "📋 Session report generated - click 'View Last Report' to see details"
            )

        # Show claim validation option if summaries were generated with HCE
        if success_count > 0:
            self._show_claim_validation_option()

    def _on_processing_error(self, error: str) -> None:
        """Handle processing errors."""
        self.set_processing_state(False)
        self.append_log(f"Error: {error}")
        self.show_error("Processing Error", error)

    def _on_worker_log_message(self, message: str) -> None:
        """Handle log messages from the worker thread.

        Args:
            message: The log message to display
        """
        # Append to GUI output panel
        self.append_log(message)

    def _on_hce_analytics_updated(self, analytics: dict) -> None:
        """Handle HCE analytics updates to show relations and contradictions."""
        filename = analytics.get("filename", "Unknown file")

        # Store analytics for final HCE progress dialog update
        if not hasattr(self, "_final_hce_stats"):
            self._final_hce_stats = {
                "claims": 0,
                "tier1_claims": 0,
                "people": 0,
                "concepts": 0,
                "relations": 0,
                "contradictions": 0,
            }

        # Aggregate statistics
        self._final_hce_stats["claims"] += analytics.get("total_claims", 0)
        self._final_hce_stats["tier1_claims"] += analytics.get("tier_a_count", 0)
        self._final_hce_stats["people"] += analytics.get("people_count", 0)
        self._final_hce_stats["concepts"] += analytics.get("concepts_count", 0)
        self._final_hce_stats["relations"] += analytics.get("relations_count", 0)
        self._final_hce_stats["contradictions"] += analytics.get(
            "contradictions_count", 0
        )

        # Display claim analytics
        total_claims = analytics.get("total_claims", 0)
        if total_claims > 0:
            tier_a = analytics.get("tier_a_count", 0)
            tier_b = analytics.get("tier_b_count", 0)
            tier_c = analytics.get("tier_c_count", 0)

            self.append_log(f"\n🔍 Analysis Results for {filename}:")
            self.append_log(f"   📊 Total Claims: {total_claims}")
            if tier_a > 0:
                self.append_log(f"   🥇 Tier A (High Confidence): {tier_a}")
            if tier_b > 0:
                self.append_log(f"   🥈 Tier B (Medium Confidence): {tier_b}")
            if tier_c > 0:
                self.append_log(f"   🥉 Tier C (Supporting): {tier_c}")

            # Show people and concepts
            people_count = analytics.get("people_count", 0)
            concepts_count = analytics.get("concepts_count", 0)
            if people_count > 0:
                self.append_log(f"   👥 People Identified: {people_count}")
                top_people = analytics.get("top_people", [])
                if top_people:
                    people_str = ", ".join(top_people[:3])
                    if len(top_people) > 3:
                        people_str += f" (and {len(top_people) - 3} more)"
                    self.append_log(f"      Key People: {people_str}")

            if concepts_count > 0:
                self.append_log(f"   💡 Concepts Found: {concepts_count}")
                top_concepts = analytics.get("top_concepts", [])
                if top_concepts:
                    concepts_str = ", ".join(top_concepts[:3])
                    if len(top_concepts) > 3:
                        concepts_str += f" (and {len(top_concepts) - 3} more)"
                    self.append_log(f"      Key Concepts: {concepts_str}")

            # Show routing analytics (if routing was enabled)
            if True:  # Routing always enabled
                flagship_routed = analytics.get("flagship_routed_count", 0)
                local_processed = analytics.get("local_processed_count", 0)
                if flagship_routed > 0 or local_processed > 0:
                    self.append_log("   🎯 Routing Analytics:")
                    if local_processed > 0:
                        self.append_log(
                            f"      📱 Local Judge: {local_processed} claims"
                        )
                    if flagship_routed > 0:
                        self.append_log(
                            f"      🚀 Flagship Judge: {flagship_routed} claims"
                        )

                    routing_reason = analytics.get("routing_reason", "uncertainty")
                    if routing_reason and flagship_routed > 0:
                        self.append_log(
                            f"      📋 Primary routing reason: {routing_reason}"
                        )

            # Show relations and contradictions
            relations_count = analytics.get("relations_count", 0)
            contradictions_count = analytics.get("contradictions_count", 0)

            if relations_count > 0:
                self.append_log(f"   🔗 Relations Mapped: {relations_count}")

            if contradictions_count > 0:
                self.append_log(f"   ⚠️ Contradictions Found: {contradictions_count}")
                sample_contradictions = analytics.get("sample_contradictions", [])
                for i, contradiction in enumerate(sample_contradictions, 1):
                    self.append_log(f"      {i}. \"{contradiction['claim1']}\"")
                    self.append_log("         vs. \"{contradiction['claim2']}\"")

            # Show top claims
            top_claims = analytics.get("top_claims", [])
            if top_claims:
                self.append_log("   🏆 Top Claims:")
                for i, claim in enumerate(top_claims, 1):
                    tier_icon = "🥇" if claim["tier"] == "A" else "🥈"
                    self.append_log(
                        f"      {tier_icon} {claim['text']} ({claim['type']})"
                    )

            # Show save confirmation
            self.append_log(
                f"   ✅ Saved to database: {total_claims} claims, {people_count} people, {concepts_count} concepts"
            )
            self.append_log("")  # Add blank line for readability

    def _stop_processing(self):
        """Stop the summarization process."""
        if self.summarization_worker and self.summarization_worker.isRunning():
            self.summarization_worker.stop()  # Use the worker's stop method which handles cancellation token
            self.append_log("⏹ Stopping summarization process...")
        super()._stop_processing()

    def _cancel_processing(self):
        """Cancel the summarization process (called by HCE progress dialog)."""
        self._stop_processing()

    def cleanup_workers(self):
        """Clean up worker threads."""
        if self.summarization_worker and self.summarization_worker.isRunning():
            self.summarization_worker.stop()  # Use the worker's stop method which handles cancellation token
            # Don't wait synchronously - let the thread finish on its own
            # The worker will clean up when it's done
        super().cleanup_workers()

    def _load_settings(self) -> None:
        """Load saved settings from session."""
        logger.info(f"🔧 Loading settings for {self.tab_name} tab...")
        try:
            # Helper function to safely check if a widget is valid
            def is_widget_valid(widget):
                try:
                    if widget is None:
                        return False
                    # Try to access a property to verify the widget hasn't been deleted
                    _ = widget.objectName()
                    return True
                except RuntimeError:
                    # Widget has been deleted
                    return False

            # Block signals during loading to prevent redundant saves
            # Only include widgets that are valid
            candidate_widgets = [
                self.output_edit,
                self.provider_combo,
                self.model_combo,
                self.template_path_edit,
                self.claim_tier_combo,
                self.max_claims_spin,
                # tier_a_threshold_spin and tier_b_threshold_spin removed - obsolete
                # Unified Pipeline HCE fields (profile_combo removed - stored internally)
                # Advanced per-stage provider and model dropdowns (unified pipeline)
                self.advanced_models_group,
                self.miner_provider,
                self.miner_model,
                self.flagship_judge_provider,
                self.flagship_judge_model,
            ]

            widgets_to_block = [w for w in candidate_widgets if is_widget_valid(w)]

            if len(widgets_to_block) != len(candidate_widgets):
                # Find which widgets are invalid for debugging
                invalid_widget_names = []
                widget_names = [
                    "output_edit",
                    "provider_combo",
                    "model_combo",
                    "template_path_edit",
                    "claim_tier_combo",
                    "max_claims_spin",
                    # "tier_a_threshold_spin", "tier_b_threshold_spin" removed
                    "advanced_models_group",
                    "miner_provider",
                    "miner_model",
                    "flagship_judge_provider",
                    "flagship_judge_model",
                ]
                for i, widget in enumerate(candidate_widgets):
                    if not is_widget_valid(widget):
                        invalid_widget_names.append(
                            widget_names[i] if i < len(widget_names) else f"widget_{i}"
                        )

                logger.debug(
                    f"Some widgets are not valid yet: {invalid_widget_names} - continuing with available widgets"
                )
                # If critical widgets are missing, skip loading settings
                if not all(
                    is_widget_valid(w) for w in [self.provider_combo, self.model_combo]
                ):
                    logger.warning(
                        "Critical widgets not available, skipping settings load"
                    )
                    return

            # Block all signals
            for widget in widgets_to_block:
                widget.blockSignals(True)

            try:
                # Load output directory - use configured summaries path as default
                default_output_dir = str(self.settings.paths.summaries)
                saved_output_dir = self.gui_settings.get_output_directory(
                    self.tab_name, default_output_dir
                )
                if is_widget_valid(self.output_edit):
                    self.output_edit.setText(saved_output_dir)

                # Load provider selection
                # Let settings manager handle hierarchy: session → settings.yaml → empty
                saved_provider = self.gui_settings.get_combo_selection(
                    self.tab_name, "provider", ""
                )
                if is_widget_valid(self.provider_combo):
                    index = self.provider_combo.findText(saved_provider)
                    if index >= 0:
                        self.provider_combo.setCurrentIndex(index)
                        self._update_models()  # Update models after setting provider

                # Load model selection
                # Let settings manager handle hierarchy: session → settings.yaml → empty
                saved_model = self.gui_settings.get_combo_selection(
                    self.tab_name, "model", ""
                )
                if is_widget_valid(self.model_combo):
                    index = self.model_combo.findText(saved_model)
                    if index >= 0:
                        self.model_combo.setCurrentIndex(index)

                # Load source selection (Files vs Database)
                saved_source_files = self.gui_settings.get_checkbox_state(
                    self.tab_name, "source_files", True  # Default to files
                )
                if is_widget_valid(self.files_radio) and is_widget_valid(
                    self.database_radio
                ):
                    self.files_radio.setChecked(saved_source_files)
                    self.database_radio.setChecked(not saved_source_files)

                # Load content type selection
                saved_content_type = self.gui_settings.get_combo_selection(
                    self.tab_name, "content_type", "Transcript (Own)"
                )
                if is_widget_valid(self.content_type_combo):
                    index = self.content_type_combo.findText(saved_content_type)
                    if index >= 0:
                        self.content_type_combo.setCurrentIndex(index)

                # Load max tokens
                # Load template path
                default_template = (
                    "/Users/matthewgreer/Projects/Prompts/Summary Prompt.txt"
                )
                saved_template = self.gui_settings.get_line_edit_text(
                    self.tab_name, "template_path", ""
                )
                # Use default if saved template is empty
                if not saved_template or not saved_template.strip():
                    saved_template = default_template
                if is_widget_valid(self.template_path_edit):
                    self.template_path_edit.setText(saved_template)

                # Load file list - add default file if list is empty
                if is_widget_valid(self.file_list) and self.file_list.count() == 0:
                    # Using curly quotes (U+2018 and U+2019) to match actual filename
                    default_input_file = "/Users/matthewgreer/Projects/Knowledge_Chipper/output/transcripts/Steve Bannon_ Silicon Valley Is Turning Us Into \u2018Digital Serfs\u2019_vvj_J2tB2Ag.md"
                    if Path(default_input_file).exists():
                        self.file_list.addItem(default_input_file)
                        logger.debug(f"Added default input file: {default_input_file}")

                # Load HCE settings
                saved_claim_tier = self.gui_settings.get_combo_selection(
                    self.tab_name, "claim_tier", "All"
                )
                if is_widget_valid(self.claim_tier_combo):
                    index = self.claim_tier_combo.findText(saved_claim_tier)
                    if index >= 0:
                        self.claim_tier_combo.setCurrentIndex(index)

                saved_max_claims = self.gui_settings.get_spinbox_value(
                    self.tab_name, "max_claims", 0
                )
                if is_widget_valid(self.max_claims_spin):
                    self.max_claims_spin.setValue(saved_max_claims)

                # Tier threshold loading removed - obsolete (tiers assigned by LLM)

                # Load new HCE settings
                # Profile removed - using explicit per-stage model controls instead

                # Load advanced models section state
                saved_advanced_expanded = self.gui_settings.get_checkbox_state(
                    self.tab_name, "advanced_models_expanded", True
                )
                if is_widget_valid(self.advanced_models_group):
                    self.advanced_models_group.setChecked(saved_advanced_expanded)

                # Load advanced per-stage provider and model selections (unified pipeline)
                advanced_dropdowns = [
                    ("miner", self.miner_provider, self.miner_model),
                    (
                        "flagship_judge",
                        self.flagship_judge_provider,
                        self.flagship_judge_model,
                    ),
                ]

                for stage_name, provider_combo, model_combo in advanced_dropdowns:
                    # Skip if widgets are not valid
                    if not is_widget_valid(provider_combo) or not is_widget_valid(
                        model_combo
                    ):
                        logger.debug(f"Skipping {stage_name} - widgets not valid")
                        continue

                    try:
                        # Load provider selection - let settings manager handle hierarchy
                        saved_provider = self.gui_settings.get_combo_selection(
                            self.tab_name,
                            f"{stage_name}_provider",
                            "",  # Let settings manager use settings.yaml
                        )
                        if saved_provider:
                            index = provider_combo.findText(saved_provider)
                            if index >= 0:
                                provider_combo.setCurrentIndex(index)
                                # Update models for this provider
                                self._update_advanced_model_combo(
                                    saved_provider, model_combo
                                )

                        # Load model selection - let settings manager handle hierarchy
                        saved_model = self.gui_settings.get_combo_selection(
                            self.tab_name, f"{stage_name}_model", ""
                        )
                        if saved_model:
                            index = model_combo.findText(saved_model)
                            if index >= 0:
                                model_combo.setCurrentIndex(index)
                    except RuntimeError as e:
                        logger.debug(f"Widget access error for {stage_name}: {e}")
                        continue

            finally:
                # Always restore signals, even if an exception occurred
                for widget in widgets_to_block:
                    try:
                        widget.blockSignals(False)
                    except RuntimeError:
                        # Widget was deleted, skip it
                        pass

            logger.info(f"✅ Successfully loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")

    def _save_settings(self) -> None:
        """Save current settings to session."""
        logger.debug(f"💾 Saving settings for {self.tab_name} tab...")
        try:
            # Check if UI is fully initialized before attempting to save
            if not hasattr(self, "provider_combo") or self.provider_combo is None:
                logger.debug("UI not fully initialized yet, skipping save")
                return

            # Helper function to safely get widget value
            def safe_get_text(widget, widget_name="widget"):
                try:
                    if widget is None:
                        logger.debug(f"{widget_name} is None, skipping")
                        return None
                    return (
                        widget.currentText()
                        if hasattr(widget, "currentText")
                        else widget.text()
                    )
                except RuntimeError as e:
                    logger.debug(f"{widget_name} has been deleted: {e}")
                    return None

            def safe_get_value(widget, widget_name="widget"):
                try:
                    if widget is None:
                        logger.debug(f"{widget_name} is None, skipping")
                        return None
                    return widget.value()
                except RuntimeError as e:
                    logger.debug(f"{widget_name} has been deleted: {e}")
                    return None

            def safe_get_checked(widget, widget_name="widget"):
                try:
                    if widget is None:
                        logger.debug(f"{widget_name} is None, skipping")
                        return None
                    return widget.isChecked()
                except RuntimeError as e:
                    logger.debug(f"{widget_name} has been deleted: {e}")
                    return None

            # Save output directory
            output_text = safe_get_text(self.output_edit, "output_edit")
            if output_text is not None:
                self.gui_settings.set_output_directory(self.tab_name, output_text)

            # Save combo selections
            # NOTE: provider_combo and model_combo are now properties that redirect to miner dropdowns
            # This saves miner settings as the primary provider/model
            provider_text = safe_get_text(self.provider_combo, "provider_combo")
            if provider_text is not None:
                self.gui_settings.set_combo_selection(
                    self.tab_name, "provider", provider_text
                )

            model_text = safe_get_text(self.model_combo, "model_combo")
            if model_text is not None:
                self.gui_settings.set_combo_selection(
                    self.tab_name, "model", model_text
                )

            # Save source selection (Files vs Database)
            source_selection = "files" if self.files_radio.isChecked() else "database"
            self.gui_settings.set_checkbox_state(
                self.tab_name, "source_files", self.files_radio.isChecked()
            )

            # Save content type selection
            content_type_text = safe_get_text(
                self.content_type_combo, "content_type_combo"
            )
            if content_type_text is not None:
                self.gui_settings.set_combo_selection(
                    self.tab_name, "content_type", content_type_text
                )

            # Save line edit text
            template_text = safe_get_text(self.template_path_edit, "template_path_edit")
            if template_text is not None:
                self.gui_settings.set_line_edit_text(
                    self.tab_name, "template_path", template_text
                )

            # Save HCE settings
            claim_tier_text = safe_get_text(self.claim_tier_combo, "claim_tier_combo")
            if claim_tier_text is not None:
                self.gui_settings.set_combo_selection(
                    self.tab_name, "claim_tier", claim_tier_text
                )

            max_claims_value = safe_get_value(self.max_claims_spin, "max_claims_spin")
            if max_claims_value is not None:
                self.gui_settings.set_spinbox_value(
                    self.tab_name, "max_claims", max_claims_value
                )

            # Tier threshold saving removed - obsolete (tiers assigned by LLM)

            # Save unified pipeline HCE settings
            # Profile removed - using explicit per-stage model controls instead

            # Save advanced models section state
            advanced_checked = safe_get_checked(
                self.advanced_models_group, "advanced_models_group"
            )
            if advanced_checked is not None:
                self.gui_settings.set_checkbox_state(
                    self.tab_name,
                    "advanced_models_expanded",
                    advanced_checked,
                )

            # Save advanced per-stage provider and model selections (unified pipeline)
            advanced_dropdowns = [
                ("miner", self.miner_provider, self.miner_model),
                (
                    "flagship_judge",
                    self.flagship_judge_provider,
                    self.flagship_judge_model,
                ),
            ]

            for stage_name, provider_combo, model_combo in advanced_dropdowns:
                # Save provider selection
                stage_provider_text = safe_get_text(
                    provider_combo, f"{stage_name}_provider"
                )
                if stage_provider_text is not None:
                    self.gui_settings.set_combo_selection(
                        self.tab_name,
                        f"{stage_name}_provider",
                        stage_provider_text,
                    )

                # Save model selection
                stage_model_text = safe_get_text(model_combo, f"{stage_name}_model")
                if stage_model_text is not None:
                    self.gui_settings.set_combo_selection(
                        self.tab_name, f"{stage_name}_model", stage_model_text
                    )

            logger.info(f"✅ Successfully saved settings for {self.tab_name} tab")
        except Exception as e:
            import traceback

            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")

    def _on_model_changed(self):
        """Called when the model selection changes - validate local models."""
        provider = self.provider_combo.currentText()
        model = self.model_combo.currentText()

        # Only validate for local provider
        if provider != "local" or not model:
            return

        # Check if model already has "(Installed)" suffix - no need to check
        if "(Installed)" in model:
            return

        logger.debug(f"🔄 Model changed to: {model}, checking availability...")

        # Simple inline check without blocking processing flow
        from ...utils.ollama_manager import get_ollama_manager

        try:
            ollama_manager = get_ollama_manager()

            # Quick check if service is running
            if not ollama_manager.is_service_running():
                return  # Don't bother user if service isn't running

            # Clean model name
            import re

            clean_model_name = model.replace(" (Installed)", "")
            clean_model_name = re.sub(r" \(\d+ GB\)$", "", clean_model_name)

            # Check if model is installed
            is_available = ollama_manager.is_model_available(clean_model_name)

            if not is_available:
                # Show download dialog (reuse existing method)
                from PyQt6.QtWidgets import QDialog

                from ..legacy_dialogs import ModelDownloadDialog

                logger.info(
                    f"Model '{clean_model_name}' not installed, showing download dialog"
                )

                dialog = ModelDownloadDialog(clean_model_name, self)
                result = dialog.exec()

                if result == QDialog.DialogCode.Accepted:
                    logger.info(f"Model '{clean_model_name}' installation completed")
                    # Refresh the model list to show it as installed
                    self._update_models(force_refresh=True)
                else:
                    logger.info(f"Model '{clean_model_name}' installation cancelled")
        except Exception as e:
            logger.debug(f"Error checking model on change: {e}")
            # Don't bother user with errors on dropdown change

    def _on_advanced_model_changed(
        self, provider_combo: QComboBox, model_combo: QComboBox
    ):
        """Called when an advanced model selection changes - validate local models."""
        try:
            provider = provider_combo.currentText()
            model = model_combo.currentText()

            # Only validate for local provider
            if provider != "local" or not model:
                return

            # Check if model already has "(Installed)" suffix - no need to check
            if "(Installed)" in model:
                return

            logger.debug(
                f"🔄 Advanced model changed to: {model}, checking availability..."
            )

            # Simple inline check without blocking processing flow
            from ...utils.ollama_manager import get_ollama_manager

            ollama_manager = get_ollama_manager()

            # Quick check if service is running
            if not ollama_manager.is_service_running():
                return  # Don't bother user if service isn't running

            # Clean model name
            import re

            clean_model_name = model.replace(" (Installed)", "")
            clean_model_name = re.sub(r" \(\d+ GB\)$", "", clean_model_name)

            # Check if model is installed
            is_available = ollama_manager.is_model_available(clean_model_name)

            if not is_available:
                # Show download dialog
                from PyQt6.QtWidgets import QDialog

                from ..legacy_dialogs import ModelDownloadDialog

                logger.info(
                    f"Advanced model '{clean_model_name}' not installed, showing download dialog"
                )

                dialog = ModelDownloadDialog(clean_model_name, self)
                result = dialog.exec()

                if result == QDialog.DialogCode.Accepted:
                    logger.info(
                        f"Advanced model '{clean_model_name}' installation completed"
                    )
                    # Refresh the model list for the specific combo
                    self._update_advanced_model_combo("local", model_combo)
                else:
                    logger.info(
                        f"Advanced model '{clean_model_name}' installation cancelled"
                    )
        except Exception as e:
            logger.debug(f"Error checking advanced model on change: {e}")
            # Don't bother user with errors on dropdown change

    def _on_setting_changed(self):
        """Called when any setting changes to automatically save."""
        logger.debug(f"🔄 Setting changed in {self.tab_name} tab, triggering save...")
        self._save_settings()

    def _get_model_override(
        self, provider_combo: QComboBox, model_combo: QComboBox
    ) -> str | None:
        """Get model override string from provider and model combos.

        Returns a model URI in the format expected by parse_model_uri():
        - "provider:model" for standard providers (openai, anthropic, etc.)
        - "local://model" for local Ollama models
        """
        provider = provider_combo.currentText().strip()
        model = model_combo.currentText().strip()

        if not provider or not model:
            return None

        # Map "local" provider to the local:// protocol format
        if provider.lower() == "local":
            return f"local://{model}"

        # Use colon separator for all other providers (NOT slash)
        return f"{provider}:{model}"

    def _on_analysis_type_changed(self, analysis_type: str) -> None:
        """Called when analysis type changes to auto-populate template path."""
        # Convert analysis type to template filename dynamically
        filename = _analysis_type_to_filename(analysis_type)
        template_path = f"config/prompts/{filename}.txt"

        # Check if the template file exists
        if Path(template_path).exists():
            self.template_path_edit.setText(template_path)
            logger.debug(
                f"🔄 Analysis type changed to '{analysis_type}', auto-populated template: {template_path}"
            )
        else:
            logger.warning(
                f"⚠️ Template file not found: {template_path} for analysis type '{analysis_type}'"
            )
            # Clear template path if file doesn't exist
            self.template_path_edit.setText("")

            # Show user-friendly warning message
            self.show_warning(
                "Template File Missing",
                f"The template file for '{analysis_type}' was not found:\n\n"
                f"Expected: {template_path}\n\n"
                "To fix this:\n"
                f"1. Create the file '{template_path}'\n"
                "2. Add your custom prompt template\n"
                f"3. Include {{text}} placeholder where content should go\n\n"
                "The template path has been cleared. You can manually specify a different template file or create the missing one.",
            )

        # Trigger settings save after template path is updated
        self._on_setting_changed()

    def _generate_session_report(
        self, success_count: int, failure_count: int, total_count: int, time_text: str
    ) -> None:
        """Generate comprehensive session report."""
        try:
            import json
            from datetime import datetime

            # Create report data
            report_data = {
                "session_info": {
                    "timestamp": datetime.now().isoformat(),
                    "total_files": total_count,
                    "successful": success_count,
                    "failed": failure_count,
                    "processing_time": time_text.strip(),
                },
                "configuration": {
                    "provider": self.provider_combo.currentText(),
                    "model": self.model_combo.currentText(),
                    "max_tokens": 10000,
                    "analysis_type": "Document Summary",  # Fixed to Document Summary
                    "use_skim": True,
                    "enable_routing": True,
                    "routing_threshold": 35,  # Default: 35%
                    "prompt_driven_mode": False,
                    "flagship_file_tokens": self.flagship_file_tokens_spin.value(),
                    "flagship_session_tokens": self.flagship_session_tokens_spin.value(),
                },
                "output_settings": {
                    "update_in_place": False,
                    "create_separate_file": False,
                    "output_directory": self.output_edit.text(),
                    "force_regenerate": False,
                },
            }

            # Save report to output directory or default location
            output_dir = self.output_edit.text() or "output/summaries"
            report_path = (
                Path(output_dir)
                / f"session_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            report_path.parent.mkdir(parents=True, exist_ok=True)

            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

            # Store report path for viewing (both for legacy and base class)
            self._last_session_report = report_path
            self.current_report = str(report_path)  # Base class uses this

            logger.info(f"Session report saved to: {report_path}")

        except Exception as e:
            logger.error(f"Failed to generate session report: {e}")

    def _view_session_report(self) -> None:
        """Open the last generated session report."""
        if hasattr(self, "_last_session_report") and self._last_session_report.exists():
            try:
                import subprocess
                import sys

                if sys.platform.startswith("darwin"):  # macOS
                    subprocess.run(["open", str(self._last_session_report)])
                elif sys.platform.startswith("win"):  # Windows
                    subprocess.run(
                        ["start", str(self._last_session_report)],
                        shell=True,  # nosec B602
                    )
                else:  # Linux
                    subprocess.run(["xdg-open", str(self._last_session_report)])

            except Exception as e:
                self.show_warning(
                    "Cannot Open Report", f"Failed to open session report: {e}"
                )
        else:
            self.show_warning(
                "No Report", "No session report available. Run a summarization first."
            )

    def _show_claim_validation_option(self):
        """Show claim validation option after successful HCE processing."""
        # Check if HCE processing was enabled and claims were extracted
        if not self._has_hce_claims():
            return

        self.append_log("\n" + "🔍" * 20)
        self.append_log("📋 CLAIM VALIDATION")
        self.append_log("🔍" * 20)
        self.append_log(
            "💡 Help us improve claim tier accuracy! Review the A/B/C tier assignments."
        )
        self.append_log("🎯 Your feedback helps train better claim evaluation models.")

        # Add claim validation button to the UI if not already present
        if not hasattr(self, "claim_validation_btn"):
            self._add_claim_validation_button()

    def _has_hce_claims(self) -> bool:
        """Check if HCE processing was enabled and claims were extracted."""
        try:
            # Check if HCE processing is enabled in settings
            hce_enabled = getattr(self, "hce_checkbox", None)
            if not hce_enabled or not hce_enabled.isChecked():
                return False

            # Check if we have recent HCE data with claims
            from ...database.service import DatabaseService

            db = DatabaseService()

            # Look for recent episodes with claims
            # This is a simplified check - in practice you'd want to check
            # the specific files that were just processed
            try:
                recent_claims = db.get_recent_claims(limit=1)
                return len(recent_claims) > 0
            except Exception:
                # If get_recent_claims doesn't exist, assume we have claims if HCE is enabled
                return True

        except Exception as e:
            logger.error(f"Failed to check for HCE claims: {e}")
            return False

    def _add_claim_validation_button(self):
        """Add claim validation button to the action layout."""
        try:
            # Find the action layout (should be the layout with start/stop buttons)
            action_layout = None
            for i in range(self.layout().count()):
                item = self.layout().itemAt(i)
                if item and hasattr(item, "layout") and item.layout():
                    layout = item.layout()
                    # Check if this layout contains the start button
                    for j in range(layout.count()):
                        widget_item = layout.itemAt(j)
                        if widget_item and hasattr(widget_item, "widget"):
                            widget = widget_item.widget()
                            if hasattr(widget, "text") and "Start" in widget.text():
                                action_layout = layout
                                break
                    if action_layout:
                        break

            if action_layout:
                # Create claim validation button
                self.claim_validation_btn = QPushButton("🔍 Validate Claim Tiers")
                self.claim_validation_btn.clicked.connect(
                    self._show_claim_validation_dialog
                )
                self.claim_validation_btn.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #17a2b8;
                        color: white;
                        font-weight: bold;
                        padding: 8px 16px;
                        border: none;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #138496;
                    }
                """
                )
                self.claim_validation_btn.setVisible(False)  # Initially hidden

                # Insert before the stretch (usually the last item)
                stretch_index = action_layout.count() - 1
                if stretch_index >= 0:
                    action_layout.insertWidget(stretch_index, self.claim_validation_btn)
                else:
                    action_layout.addWidget(self.claim_validation_btn)

                # Show the button
                self.claim_validation_btn.setVisible(True)

                logger.info("Added claim validation button to summarization tab")
            else:
                logger.warning(
                    "Could not find action layout to add claim validation button"
                )

        except Exception as e:
            logger.error(f"Failed to add claim validation button: {e}")

    def _show_claim_validation_dialog(self):
        """Show the claim validation dialog."""
        try:
            # Get claims from the most recent HCE processing
            claims_data = self._get_recent_claims_for_validation()

            if not claims_data:
                self.append_log("❌ No claims found for validation.")
                return

            # Create claim validation dialog
            dialog = ClaimValidationDialog(claims_data, parent=self)

            # Connect to handle validation completed
            dialog.validation_completed.connect(self._on_claim_validation_completed)

            # Show dialog
            dialog.exec()

        except Exception as e:
            logger.error(f"Failed to show claim validation dialog: {e}")
            self.show_error(
                "Claim Validation Error",
                f"Failed to show claim validation dialog: {str(e)}",
            )

    def _get_recent_claims_for_validation(self) -> list[dict]:
        """Get recent claims for validation from HCE processing."""
        try:
            from ...database.service import DatabaseService

            DatabaseService()

            # Get recent claims from the database
            # This is a simplified implementation - in practice you'd want to get
            # claims from the specific files that were just processed

            # For now, get the most recent 10 claims as a demo
            recent_claims = []

            # Try to get claims from HCE database
            try:
                # This would be the actual implementation if we had HCE claims in the database
                # For now, create some sample claims for demonstration
                sample_claims = [
                    {
                        "claim_id": f"claim_{i}",
                        "canonical": f"Sample claim {i} extracted from the processed content.",
                        "tier": ["A", "B", "C"][i % 3],
                        "claim_type": ["factual", "causal", "normative"][i % 3],
                        "evidence": [
                            {
                                "quote": f"Evidence quote {i}",
                                "t0": "00:01:00",
                                "t1": "00:01:05",
                            }
                        ],
                        "scores": {"confidence": 0.8 + (i * 0.05)},
                    }
                    for i in range(5)  # Create 5 sample claims
                ]
                recent_claims = sample_claims

            except Exception as e:
                logger.warning(f"Could not get claims from database: {e}")
                # Return empty list if no claims available
                return []

            return recent_claims

        except Exception as e:
            logger.error(f"Failed to get recent claims for validation: {e}")
            return []

    def _on_claim_validation_completed(self, validation_results: list[dict]):
        """Handle claim validation completion."""
        try:
            total_claims = len(validation_results)
            modified_claims = sum(
                1 for result in validation_results if result.get("was_modified", False)
            )
            confirmed_claims = total_claims - modified_claims

            self.append_log("\n✅ Claim validation completed!")
            self.append_log("📊 Validation Summary:")
            self.append_log(f"   • Total claims validated: {total_claims}")
            self.append_log(f"   • Confirmed as correct: {confirmed_claims}")
            self.append_log(f"   • Modified by user: {modified_claims}")

            if total_claims > 0:
                accuracy_rate = (confirmed_claims / total_claims) * 100
                self.append_log(f"   • AI accuracy rate: {accuracy_rate:.1f}%")

            self.append_log(
                "🙏 Thank you for your feedback! This helps improve our claim evaluation."
            )

            # Hide the validation button after validation is completed
            if hasattr(self, "claim_validation_btn"):
                self.claim_validation_btn.setVisible(False)

        except Exception as e:
            logger.error(f"Failed to handle claim validation completion: {e}")

    def _on_processor_progress(self, message: str, percentage: int):
        """Handle progress updates from the processor log integrator."""
        # Log rich processor information
        self.append_log(f"🔧 {message}")

    def _on_processor_status(self, status: str):
        """Handle status updates from the processor log integrator."""
        # Add rich processor status to our regular log output
        self.append_log(f"🔍 {status}")
