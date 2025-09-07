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
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ...utils.model_registry import get_provider_models
from ...utils.ollama_manager import get_ollama_manager
from ..components.base_tab import BaseTab
from ..components.rich_log_display import ProcessorLogIntegrator, RichLogDisplay
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

    def run(self) -> None:
        """Run the summarization process."""
        try:
            from datetime import datetime as _dt
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
                hce_options={
                    "use_skim": self.gui_settings.get("use_skim", True),
                    "enable_routing": self.gui_settings.get("enable_routing", True),
                    "routing_threshold": self.gui_settings.get(
                        "routing_threshold", 0.35
                    ),
                    "prompt_driven_mode": self.gui_settings.get(
                        "prompt_driven_mode", False
                    ),
                    "flagship_file_tokens": self.gui_settings.get(
                        "flagship_file_tokens", 0
                    ),
                    "flagship_session_tokens": self.gui_settings.get(
                        "flagship_session_tokens", 0
                    ),
                },
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
                logger.info(
                    f"🔧 DEBUG: template_path from gui_settings: '{template_path}' (type: {type(template_path)})"
                )

                # If no custom template provided, determine template based on analysis type
                if not template_path or not template_path.strip():
                    analysis_type = self.gui_settings.get(
                        "analysis_type", "Document Summary"
                    )

                    # Convert analysis type to template filename dynamically
                    filename = _analysis_type_to_filename(analysis_type)
                    template_path = f"config/prompts/{filename}.txt"
                    logger.info(
                        f"🔧 Auto-determined template for '{analysis_type}': {template_path}"
                    )

                if (
                    template_path and template_path.strip()
                ):  # Check for empty/whitespace strings
                    template_path = Path(template_path)
                    logger.info(f"🔧 DEBUG: template_path as Path: '{template_path}'")
                    logger.info(
                        f"🔧 DEBUG: template_path absolute: '{template_path.absolute()}'"
                    )
                    if not template_path.exists():
                        logger.error(f"❌ Template path does not exist: {template_path}")
                        template_path = None
                    else:
                        logger.info(f"✅ Template path exists: {template_path}")
                else:
                    logger.error("❌ Could not determine template path")
                    template_path = None

                # Create enhanced progress callback with character-based tracking
                def enhanced_progress_callback(p: Any) -> None:
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
                    prompt_template=template_path,
                    progress_callback=enhanced_progress_callback,
                    cancellation_token=self.cancellation_token,
                    prefer_template_summary=self.gui_settings.get(
                        "prompt_driven_mode", False
                    ),
                    allow_llm_fallback=True,  # Enable fallback for better reliability
                )

                if result.success:
                    # File completed successfully - update character counter
                    characters_completed += current_file_size

                    # Extract and emit HCE analytics if available
                    if (
                        hasattr(result, "data")
                        and result.data
                        and isinstance(result.data, dict)
                    ):
                        hce_data = result.data.get("hce_data")
                        if hce_data and isinstance(hce_data, dict):
                            analytics = self._extract_hce_analytics(
                                hce_data, file_path_obj.name
                            )
                            self.hce_analytics_updated.emit(analytics)

                            # Export to GetReceipts if enabled
                            if self.gui_settings.get("export_getreceipts", False):
                                try:
                                    # Import our knowledge_chipper_integration function
                                    import sys
                                    from pathlib import Path as PathLib

                                    # Add the project root to Python path to import our integration
                                    project_root = PathLib(
                                        __file__
                                    ).parent.parent.parent.parent.parent
                                    if str(project_root) not in sys.path:
                                        sys.path.insert(0, str(project_root))

                                    from knowledge_chipper_integration import (
                                        publish_to_getreceipts,
                                    )

                                    # Read file content for transcript
                                    transcript_text = ""
                                    if file_path_obj.exists():
                                        transcript_text = file_path_obj.read_text(
                                            encoding="utf-8"
                                        )

                                    # Convert HCE data to GetReceipts format
                                    claims = []
                                    people = []
                                    jargon = []
                                    mental_models = []

                                    # Extract claims (only high-quality ones)
                                    for claim in hce_data.get("claims", []):
                                        if claim.get("tier") in [
                                            "A",
                                            "B",
                                        ]:  # Only high-quality claims
                                            claims.append(claim.get("canonical", ""))

                                    # Extract people
                                    for person in hce_data.get("people", []):
                                        people.append(
                                            {
                                                "name": person.get(
                                                    "normalized",
                                                    person.get("surface", ""),
                                                ),
                                                "bio": None,  # HCE doesn't provide bio
                                                "expertise": None,  # HCE doesn't provide expertise
                                                "credibility_score": person.get(
                                                    "confidence", 0.5
                                                ),
                                                "sources": [],  # HCE doesn't provide sources
                                            }
                                        )

                                    # Extract jargon terms
                                    for term in hce_data.get("jargon", []):
                                        jargon.append(
                                            {
                                                "term": term.get("term", ""),
                                                "definition": term.get(
                                                    "definition", ""
                                                ),
                                                "domain": term.get("category"),
                                                "related_terms": [],
                                                "examples": [],
                                            }
                                        )

                                    # Extract mental models (concepts)
                                    for concept in hce_data.get("concepts", []):
                                        # Convert HCE relations to GetReceipts format
                                        concept_relations = []
                                        for relation in hce_data.get("relations", []):
                                            if relation.get(
                                                "source_claim_id"
                                            ) == concept.get("model_id"):
                                                rel_type = relation.get("type", "")
                                                # Map HCE relation types to GetReceipts types
                                                if rel_type == "supports":
                                                    gr_type = "enables"
                                                elif rel_type == "depends_on":
                                                    gr_type = "requires"
                                                elif rel_type == "contradicts":
                                                    gr_type = "conflicts_with"
                                                else:
                                                    gr_type = "causes"

                                                concept_relations.append(
                                                    {
                                                        "from": concept.get("name", ""),
                                                        "to": relation.get(
                                                            "target_claim_id", ""
                                                        ),
                                                        "type": gr_type,
                                                    }
                                                )

                                        mental_models.append(
                                            {
                                                "name": concept.get("name", ""),
                                                "description": concept.get(
                                                    "definition", ""
                                                ),
                                                "domain": None,  # HCE doesn't provide domain
                                                "key_concepts": concept.get(
                                                    "aliases", []
                                                ),
                                                "relationships": concept_relations,
                                            }
                                        )

                                    # Determine video URL if available
                                    video_url = f"file://{str(file_path_obj)}"

                                    # Call our GetReceipts integration function
                                    getreceipts_result = publish_to_getreceipts(
                                        transcript=transcript_text[
                                            :5000
                                        ],  # Limit to first 5000 chars
                                        video_url=video_url,
                                        claims=claims,
                                        people=people,
                                        jargon=jargon,
                                        mental_models=mental_models,
                                        topics=[
                                            file_path_obj.stem,
                                            "knowledge_chipper",
                                            "gui_processing",
                                        ],
                                    )

                                    if getreceipts_result["success"]:
                                        claims_exported = getreceipts_result[
                                            "published_claims"
                                        ]
                                        # Update progress with GetReceipts success
                                        progress.current_step = f"✅ Exported {claims_exported} claims to GetReceipts"
                                        self.progress_updated.emit(progress)
                                    else:
                                        errors = getreceipts_result.get(
                                            "errors", ["Unknown error"]
                                        )
                                        # Update progress with GetReceipts error
                                        progress.current_step = f"⚠️ GetReceipts export failed: {'; '.join(errors[:1])}"
                                        self.progress_updated.emit(progress)

                                except Exception as e:
                                    # Update progress with GetReceipts error
                                    progress.current_step = (
                                        f"⚠️ GetReceipts export error: {str(e)}"
                                    )
                                    self.progress_updated.emit(progress)

                    # Save the summary to file(s) based on user selection
                    try:
                        actions_completed = []

                        # Handle in-place update if selected
                        if (
                            self.gui_settings.get("update_in_place", False)
                            and file_path_obj.suffix.lower() == ".md"
                        ):
                            # Generate unified YAML metadata for in-place updates
                            from ...utils.file_io import generate_unified_yaml_metadata

                            template_path = (
                                Path(self.gui_settings.get("template_path"))
                                if self.gui_settings.get("template_path")
                                else None
                            )
                            additional_yaml_fields = generate_unified_yaml_metadata(
                                file_path_obj,
                                result.data,
                                self.gui_settings.get(
                                    "model", "gpt-4o-mini-2024-07-18"
                                ),
                                (result.metadata or {}).get(
                                    "provider",
                                    self.gui_settings.get("provider", "unknown"),
                                ),
                                result.metadata or {},
                                template_path,
                                self.gui_settings.get(
                                    "analysis_type", "document summary"
                                ),
                                existing_file_path=file_path_obj,  # Pass existing file path for duplicate checking
                            )

                            # Update existing .md file in-place with YAML fields
                            overwrite_or_insert_summary_section(
                                file_path_obj, result.data, additional_yaml_fields
                            )
                            actions_completed.append(
                                f"Updated in-place: {file_path_obj.name}"
                            )

                        # Handle separate file creation if selected
                        if self.gui_settings.get("create_separate_file", False):
                            # Create new summary file
                            # Clean filename for filesystem compatibility
                            from ...utils.file_io import safe_filename

                            clean_display_name = file_path_obj.stem.replace(
                                "-", " "
                            ).replace("_", " ")
                            clean_filename = safe_filename(
                                f"{clean_display_name}_summary"
                            )

                            # Get output directory and ensure it's a Path object
                            output_dir_setting = self.gui_settings.get("output_dir")
                            if not output_dir_setting:
                                # Fallback: create summary next to original file
                                output_file = (
                                    file_path_obj.parent / f"{clean_filename}.md"
                                )
                            else:
                                # Convert string path to Path object
                                output_dir_path = Path(output_dir_setting)
                                output_file = output_dir_path / f"{clean_filename}.md"

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

                            # Generate unified YAML metadata for separate file
                            from ...utils.file_io import generate_unified_yaml_metadata

                            template_path = (
                                Path(self.gui_settings.get("template_path"))
                                if self.gui_settings.get("template_path")
                                else None
                            )
                            yaml_fields = generate_unified_yaml_metadata(
                                file_path_obj,
                                result.data,
                                self.gui_settings.get(
                                    "model", "gpt-4o-mini-2024-07-18"
                                ),
                                metadata.get(
                                    "provider",
                                    self.gui_settings.get("provider", "unknown"),
                                ),
                                metadata,
                                template_path,
                                self.gui_settings.get(
                                    "analysis_type", "document summary"
                                ),
                            )

                            with open(output_file, "w", encoding="utf-8") as f:
                                # Write YAML frontmatter using unified metadata
                                f.write("---\n")
                                for field_name, field_value in yaml_fields.items():
                                    # Handle boolean values properly (don't quote them)
                                    if field_value.lower() in ["true", "false"]:
                                        f.write(f"{field_name}: {field_value}\n")
                                    else:
                                        # Escape quotes and other special characters in field values for strings
                                        escaped_value = (
                                            str(field_value)
                                            .replace('"', '\\"')
                                            .replace("\n", "\\n")
                                            .replace("\r", "\\r")
                                        )
                                        # Prevent extremely long field values that could break YAML
                                        if len(escaped_value) > 1000:
                                            escaped_value = escaped_value[:997] + "..."
                                            logger.warning(
                                                f"Truncated long field value for {field_name}"
                                            )
                                        f.write(f'{field_name}: "{escaped_value}"\n')

                                # Add generation timestamp
                                f.write(f'generated: "{_dt.now().isoformat()}"\n')
                                f.write("---\n\n")

                                # Add thumbnail if found
                                if thumbnail_content:
                                    f.write(thumbnail_content + "\n\n")

                                # Add YouTube watch link if this is YouTube content
                                youtube_url = self._extract_youtube_url_from_file(
                                    file_path_obj
                                )
                                if youtube_url:
                                    f.write(
                                        f"**🎥 [Watch on YouTube]({youtube_url})**\n\n"
                                    )

                                # Write the actual summary content
                                # Use the same clean display name for the content title
                                f.write(f"# Summary of {clean_display_name}\n\n")
                                f.write(result.data)

                            actions_completed.append(
                                f"Created separate file: {output_file.name}"
                            )

                        # Emit combined progress message
                        if actions_completed:
                            combined_message = " | ".join(actions_completed)
                            self.progress_updated.emit(
                                SummarizationProgress(
                                    current_file=file_path,
                                    total_files=len(self.files),
                                    completed_files=i + 1,
                                    current_step=f"✅ {combined_message}",
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

        # Connect thread-safe signal for dialog creation
        self.show_ollama_service_dialog_signal.connect(
            self._show_ollama_service_dialog_on_main_thread
        )

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

        # Add supported file types info
        supported_types_label = QLabel(
            "Supported formats: PDF (.pdf), Text (.txt), Markdown (.md), HTML (.html, .htm), JSON (.json)"
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

        # Analysis Type removed - now defaults to "Document Summary" with entity extraction

        # Profile section
        profile_group = QGroupBox("Analysis Profile")
        profile_layout = QHBoxLayout()

        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["Balanced", "Fast", "Quality", "Custom"])
        self.profile_combo.currentTextChanged.connect(self._on_profile_changed)
        self.profile_combo.setMinimumWidth(150)
        self.profile_combo.setToolTip(
            "Choose analysis profile:\n"
            "• Fast: Lightweight models, no routing, skim disabled\n"
            "• Balanced: Default settings with routing enabled\n"
            "• Quality: Flagship models, aggressive routing, all features\n"
            "• Custom: Manual configuration"
        )

        profile_layout.addWidget(QLabel("Profile:"))
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addStretch()

        profile_group.setLayout(profile_layout)
        profile_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(profile_group)

        # Settings section
        settings_group = QGroupBox("Settings")
        settings_layout = QGridLayout()

        # Provider selection (made narrower)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openai", "anthropic", "local"])
        self.provider_combo.currentTextChanged.connect(self._update_models)
        self.provider_combo.currentTextChanged.connect(self._on_setting_changed)
        self.provider_combo.setMinimumWidth(150)  # Make provider field longer
        self.provider_combo.setMaximumWidth(200)  # Allow it to be wider
        self.provider_combo.setMinimumHeight(40)  # Make 100% taller
        # Left-justify the text in the dropdown
        self.provider_combo.setStyleSheet("QComboBox { text-align: left; }")
        self._add_field_with_info(
            settings_layout,
            "Provider:",
            self.provider_combo,
            "Choose AI provider: OpenAI (GPT models), Anthropic (Claude models), or Local (self-hosted models). Requires API keys in Settings.",
            0,
            0,
        )

        # Model selection (made wider)
        self.model_combo = QComboBox()
        # Allow free-text model entry for newly released models
        self.model_combo.setEditable(True)
        self.model_combo.currentTextChanged.connect(self._on_setting_changed)
        self.model_combo.setMinimumWidth(
            300
        )  # Make model field wider to accommodate long model names
        self.model_combo.setMinimumHeight(40)  # Make 100% taller

        # Model selection with custom layout for tooltip positioning
        settings_layout.addWidget(QLabel("Model:"), 0, 2)

        # Create a horizontal layout for model combo + tooltip + refresh button
        model_layout = QHBoxLayout()
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(8)

        model_layout.addWidget(self.model_combo)

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

        # Create container widget for the custom layout
        model_container = QWidget()
        model_container.setLayout(model_layout)
        settings_layout.addWidget(
            model_container, 0, 3, 1, 3
        )  # Span across multiple columns

        # Set tooltips for model combo as well
        self.model_combo.setToolTip(formatted_model_tooltip)

        # Max tokens
        max_tokens_label = QLabel("Max Response Size (Tokens):")
        max_tokens_label.setToolTip(
            "Maximum response size for claim extraction. Higher values allow more detailed analysis but cost more. 1000 tokens ≈ 750 words."
        )
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 100000)
        self.max_tokens_spin.setValue(10000)
        self.max_tokens_spin.setToolTip(
            "Maximum response size for claim extraction. Higher values allow more detailed analysis but cost more. 1000 tokens ≈ 750 words."
        )
        self.max_tokens_spin.valueChanged.connect(self._on_setting_changed)
        self.max_tokens_spin.setMinimumWidth(80)
        self.max_tokens_spin.setToolTip(
            "Maximum response size for claim extraction. Higher values allow more detailed analysis but cost more. 1000 tokens ≈ 750 words."
        )

        settings_layout.addWidget(max_tokens_label, 1, 0)
        settings_layout.addWidget(self.max_tokens_spin, 1, 1)

        # Prompt file
        prompt_label = QLabel("Prompt File:")
        prompt_label.setToolTip(
            "Path to custom prompt template file for claim extraction. Leave empty to use default HCE prompts."
        )
        self.template_path_edit = QLineEdit("")
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

        # Prompt-driven summary mode
        self.prompt_driven_mode_checkbox = QCheckBox(
            "Prompt-Driven Summary (use template structure)"
        )
        self.prompt_driven_mode_checkbox.setToolTip(
            "Uses selected template as authoritative structure.\n"
            "• HCE metadata still extracted but formatting follows template exactly\n"
            "• Useful for consistent output format across documents\n"
            "• Requires a properly formatted template file"
        )
        self.prompt_driven_mode_checkbox.toggled.connect(self._on_setting_changed)
        self.prompt_driven_mode_checkbox.toggled.connect(self._on_template_mode_changed)
        settings_layout.addWidget(self.prompt_driven_mode_checkbox, 1, 5, 1, 1)

        # Options
        self.update_md_checkbox = QCheckBox("Append Summary To Transcript File")
        self.update_md_checkbox.setToolTip(
            "If checked, will update the ## Summary section of existing .md files instead of creating new files"
        )
        self.update_md_checkbox.toggled.connect(self._on_checkbox_changed)
        self.update_md_checkbox.toggled.connect(self._on_setting_changed)
        settings_layout.addWidget(self.update_md_checkbox, 2, 0, 1, 2)

        self.separate_file_checkbox = QCheckBox("Create A Separate Summary File")
        self.separate_file_checkbox.setToolTip(
            "If checked, will create separate summary files instead of updating existing files"
        )
        self.separate_file_checkbox.toggled.connect(self._on_checkbox_changed)
        self.separate_file_checkbox.toggled.connect(self._on_setting_changed)
        settings_layout.addWidget(self.separate_file_checkbox, 3, 0, 1, 2)

        self.progress_checkbox = QCheckBox("Show progress tracking")
        self.progress_checkbox.toggled.connect(self._on_setting_changed)
        self.progress_checkbox.setToolTip(
            "Show detailed progress tracking during summarization.\n"
            "• Displays real-time progress for each file\n"
            "• Shows token usage and processing statistics\n"
            "• Useful for monitoring long-running batch jobs"
        )
        settings_layout.addWidget(self.progress_checkbox, 2, 2, 1, 2)

        self.force_regenerate_checkbox = QCheckBox("Force regenerate all")
        self.force_regenerate_checkbox.setToolTip(
            "If checked, will regenerate all summaries even if they are up-to-date. Otherwise, only modified files will be summarized."
        )
        self.force_regenerate_checkbox.toggled.connect(self._on_setting_changed)
        settings_layout.addWidget(self.force_regenerate_checkbox, 3, 2, 1, 2)

        self.resume_checkbox = QCheckBox("Resume from checkpoint")
        self.resume_checkbox.setToolTip(
            "If a previous summarization was interrupted, resume from where it left off using the checkpoint file"
        )
        self.resume_checkbox.toggled.connect(self._on_setting_changed)
        settings_layout.addWidget(self.resume_checkbox, 2, 4, 1, 2)

        self.export_getreceipts_checkbox = QCheckBox("Export to GetReceipts")
        self.export_getreceipts_checkbox.setToolTip(
            "Export extracted claims to GetReceipts platform (getreceipts-web.vercel.app)\n"
            "• Automatically publishes claims with evidence and timestamps\n"
            "• Includes people, jargon, and mental models as knowledge artifacts\n"
            "• Creates shareable claim pages for community discussion"
        )
        self.export_getreceipts_checkbox.toggled.connect(self._on_setting_changed)
        settings_layout.addWidget(self.export_getreceipts_checkbox, 3, 4, 1, 2)

        # Output folder (only shown when not updating in-place)
        self.output_label = QLabel("Output Directory:")
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

        # Initially hide output selector based on checkbox state
        self._toggle_output_options()

        settings_group.setLayout(settings_layout)
        # Settings should never shrink - use a fixed size policy
        settings_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(settings_group)

        # HCE Claim Analysis Settings
        hce_group = QGroupBox("🔍 Claim Analysis Settings")
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

        # Contradictions (Column 1)
        contradictions_layout = QHBoxLayout()
        self.include_contradictions_checkbox = QCheckBox(
            "Include Contradiction Analysis"
        )
        self.include_contradictions_checkbox.setChecked(True)
        self.include_contradictions_checkbox.setToolTip(
            "Analyze contradictions between claims within and across documents.\n"
            "Helps identify conflicting information and inconsistencies."
        )
        self.include_contradictions_checkbox.toggled.connect(self._on_setting_changed)
        contradictions_layout.addWidget(self.include_contradictions_checkbox)

        contradictions_info = QLabel("ⓘ")
        contradictions_info.setFixedSize(16, 16)
        contradictions_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contradictions_info.setToolTip(
            "<b>Include Contradiction Analysis:</b><br/><br/>"
            "Analyze contradictions between claims within and across documents.<br/>"
            "Helps identify conflicting information and inconsistencies."
        )
        contradictions_info.setStyleSheet(
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
        contradictions_layout.addWidget(contradictions_info)
        contradictions_layout.addStretch()
        contradictions_widget = QWidget()
        contradictions_widget.setLayout(contradictions_layout)
        col1_layout.addWidget(contradictions_widget, 1, 0, 1, 2)

        # Relations (Column 2)
        relations_layout = QHBoxLayout()
        self.include_relations_checkbox = QCheckBox("Include Relationship Mapping")
        self.include_relations_checkbox.setChecked(True)
        self.include_relations_checkbox.setToolTip(
            "Map relationships between claims, entities, and concepts.\n"
            "Creates connections that help understand how ideas relate."
        )
        self.include_relations_checkbox.toggled.connect(self._on_setting_changed)
        relations_layout.addWidget(self.include_relations_checkbox)

        relations_info = QLabel("ⓘ")
        relations_info.setFixedSize(16, 16)
        relations_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        relations_info.setToolTip(
            "<b>Include Relationship Mapping:</b><br/><br/>"
            "Map relationships between claims, entities, and concepts.<br/>"
            "Creates connections that help understand how ideas relate."
        )
        relations_info.setStyleSheet(
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
        relations_layout.addWidget(relations_info)
        relations_layout.addStretch()
        relations_widget = QWidget()
        relations_widget.setLayout(relations_layout)
        col2_layout.addWidget(relations_widget, 1, 0, 1, 2)

        # Thresholds
        self.tier_a_threshold_spin = QSpinBox()
        self.tier_a_threshold_spin.setMaximumWidth(60)
        self._add_field_with_info(
            col1_layout,
            "Tier A Threshold:",
            self.tier_a_threshold_spin,
            "Confidence threshold for Tier A claims (0-100%).\n"
            "Claims above this threshold are considered high-confidence core claims.",
            2,
            0,
        )
        self.tier_a_threshold_spin.setRange(0, 100)
        self.tier_a_threshold_spin.setValue(85)
        self.tier_a_threshold_spin.setSuffix("%")
        self.tier_a_threshold_spin.valueChanged.connect(self._on_setting_changed)

        self.tier_b_threshold_spin = QSpinBox()
        self.tier_b_threshold_spin.setMaximumWidth(60)
        self._add_field_with_info(
            col2_layout,
            "Tier B Threshold:",
            self.tier_b_threshold_spin,
            "Confidence threshold for Tier B claims (0-100%).\n"
            "Claims above this threshold are considered medium-confidence claims.",
            2,
            0,
        )
        self.tier_b_threshold_spin.setRange(0, 100)
        self.tier_b_threshold_spin.setValue(65)
        self.tier_b_threshold_spin.setSuffix("%")
        self.tier_b_threshold_spin.valueChanged.connect(self._on_setting_changed)

        # Column 3 toggles
        self.use_skim_checkbox = QCheckBox("High-level skim (pre-pass)")
        self.use_skim_checkbox.setChecked(True)
        self.use_skim_checkbox.setToolTip(
            "Runs a quick milestone scan before detailed analysis.\n"
            "• Identifies key topics and structure\n"
            "• Guides claim extraction focus\n"
            "• Disabling reduces LLM calls but may miss context"
        )
        self.use_skim_checkbox.toggled.connect(self._on_setting_changed)
        col3_layout.addWidget(self.use_skim_checkbox, 0, 0, 1, 2)

        self.enable_routing_checkbox = QCheckBox("Enable routed judging")
        self.enable_routing_checkbox.setChecked(True)
        self.enable_routing_checkbox.setToolTip(
            "Routes uncertain or important claims to a flagship judge model.\n"
            "• Improves accuracy for complex claims\n"
            "• Increases processing cost\n"
            "• Requires flagship judge model configuration"
        )
        self.enable_routing_checkbox.toggled.connect(self._on_setting_changed)
        self.enable_routing_checkbox.toggled.connect(self._on_routing_toggle_changed)
        col3_layout.addWidget(self.enable_routing_checkbox, 1, 0, 1, 2)

        routing_threshold_label = QLabel("Routing Threshold:")
        routing_threshold_label.setToolTip(
            "Uncertainty threshold for routing claims to flagship judge.\n"
            "Lower values route more claims to flagship (higher cost, better accuracy)."
        )
        self.routing_threshold_spin = QSpinBox()
        self.routing_threshold_spin.setRange(0, 100)
        self.routing_threshold_spin.setValue(35)
        self.routing_threshold_spin.setSuffix("%")
        # Make this input about 90% shorter than default
        self.routing_threshold_spin.setMaximumWidth(50)
        self.routing_threshold_spin.setToolTip(
            "Uncertainty threshold for routing claims to flagship judge.\n"
            "Lower values route more claims to flagship (higher cost, better accuracy)."
        )
        self.routing_threshold_spin.valueChanged.connect(self._on_setting_changed)
        col3_layout.addWidget(routing_threshold_label, 2, 0)
        col3_layout.addWidget(self.routing_threshold_spin, 2, 1)

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

        hce_group.setLayout(hce_layout)
        hce_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(hce_group)

        # Advanced: Per-stage Models (collapsible)
        from PyQt6.QtWidgets import QFrame

        self.advanced_models_group = QGroupBox("🔧 Advanced: Per-stage Models")
        self.advanced_models_group.setCheckable(True)
        self.advanced_models_group.setChecked(True)  # Expanded by default for usability
        self.advanced_models_group.toggled.connect(self._on_setting_changed)
        self.advanced_models_group.setToolTip(
            "Configure different models for each analysis stage.\n"
            "Leave empty to use main model for all stages.\n\n"
            "💡 Tip: Check this box to expand and enable the dropdowns."
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
            provider_combo.setMinimumWidth(120)  # Reasonable width for provider names
            provider_combo.setMaximumWidth(140)  # Prevent it from taking too much space
            provider_combo.currentTextChanged.connect(self._on_setting_changed)
            provider_combo.setToolTip(f"AI provider for {name}")

            model_combo = QComboBox()
            model_combo.setEditable(True)
            model_combo.setMinimumWidth(400)  # Much wider for full model names
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

        # Create model selectors
        self.miner_provider, self.miner_model, self.miner_uri = create_model_selector(
            "Miner Model", "Model for initial claim extraction", 0
        )

        (
            self.heavy_miner_provider,
            self.heavy_miner_model,
            self.heavy_miner_uri,
        ) = create_model_selector(
            "Heavy Miner Model",
            "Model for complex/detailed claim extraction (optional)",
            1,
        )

        self.judge_provider, self.judge_model, self.judge_uri = create_model_selector(
            "Judge Model", "Lightweight model for claim scoring", 2
        )

        (
            self.flagship_judge_provider,
            self.flagship_judge_model,
            self.flagship_judge_uri,
        ) = create_model_selector(
            "Flagship Judge Model", "High-quality model for important claims", 3
        )

        (
            self.embedder_provider,
            self.embedder_model,
            self.embedder_uri,
        ) = create_model_selector(
            "Embedder Model", "Model for claim embeddings and similarity", 4
        )

        (
            self.reranker_provider,
            self.reranker_model,
            self.reranker_uri,
        ) = create_model_selector(
            "Reranker Model", "Model for claim reranking and prioritization", 5
        )

        (
            self.people_provider,
            self.people_model,
            self.people_uri,
        ) = create_model_selector(
            "People Disambiguator", "Model for person name resolution (optional)", 6
        )

        self.nli_provider, self.nli_model, self.nli_uri = create_model_selector(
            "NLI Model", "Natural Language Inference model (optional)", 7
        )

        self.advanced_models_group.setLayout(advanced_layout)
        self.advanced_models_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self.advanced_models_group)

        # Initialize model dropdowns to be empty by default
        for provider_combo, model_combo, _ in [
            (self.miner_provider, self.miner_model, self.miner_uri),
            (self.heavy_miner_provider, self.heavy_miner_model, self.heavy_miner_uri),
            (self.judge_provider, self.judge_model, self.judge_uri),
            (
                self.flagship_judge_provider,
                self.flagship_judge_model,
                self.flagship_judge_uri,
            ),
            (self.embedder_provider, self.embedder_model, self.embedder_uri),
            (self.reranker_provider, self.reranker_model, self.reranker_uri),
            (self.people_provider, self.people_model, self.people_uri),
            (self.nli_provider, self.nli_model, self.nli_uri),
        ]:
            model_combo.clear()
            model_combo.addItems([""])  # Start with empty option

        # Budgets & Limits (collapsible)
        self.budgets_group = QGroupBox("💰 Budgets & Limits")
        self.budgets_group.setCheckable(True)
        self.budgets_group.setChecked(False)  # Collapsed by default
        budgets_layout = QGridLayout()

        # Flagship budget per file
        flagship_file_label = QLabel("Flagship max tokens per file:")
        flagship_file_label.setToolTip(
            "Maximum tokens to spend on flagship judge per file.\n"
            "Set to 0 for unlimited. Helps control costs."
        )
        self.flagship_file_tokens_spin = QSpinBox()
        self.flagship_file_tokens_spin.setRange(0, 100000)
        self.flagship_file_tokens_spin.setValue(0)
        self.flagship_file_tokens_spin.setSpecialValueText("Unlimited")
        self.flagship_file_tokens_spin.valueChanged.connect(self._on_setting_changed)
        budgets_layout.addWidget(flagship_file_label, 0, 0)
        budgets_layout.addWidget(self.flagship_file_tokens_spin, 0, 1)

        # Flagship budget per session
        flagship_session_label = QLabel("Flagship max tokens per session:")
        flagship_session_label.setToolTip(
            "Maximum tokens to spend on flagship judge per entire session.\n"
            "Set to 0 for unlimited. Helps control total costs."
        )
        self.flagship_session_tokens_spin = QSpinBox()
        self.flagship_session_tokens_spin.setRange(0, 1000000)
        self.flagship_session_tokens_spin.setValue(0)
        self.flagship_session_tokens_spin.setSpecialValueText("Unlimited")
        self.flagship_session_tokens_spin.valueChanged.connect(self._on_setting_changed)
        budgets_layout.addWidget(flagship_session_label, 0, 2)
        budgets_layout.addWidget(self.flagship_session_tokens_spin, 0, 3)

        self.budgets_group.setLayout(budgets_layout)
        self.budgets_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self.budgets_group)

        # Action buttons
        action_layout = self._create_action_layout()
        layout.addLayout(action_layout)

        # Rich log display for detailed processor information (like terminal)
        self.rich_log_display = RichLogDisplay()
        self.rich_log_display.setMinimumHeight(150)
        self.rich_log_display.setMaximumHeight(300)
        layout.addWidget(self.rich_log_display)

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
        # Use a timer to ensure this happens after the widget is fully initialized
        QTimer.singleShot(0, self._load_settings)

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

            # Store processing parameters for async model check
            self._pending_files = files
            self._pending_gui_settings = {
                "provider": provider,
                "model": model,
                "max_tokens": self.max_tokens_spin.value(),
                "template_path": self.template_path_edit.text(),
                "output_dir": (
                    self.output_edit.text()
                    if self.separate_file_checkbox.isChecked()
                    else None
                ),
                "update_in_place": self.update_md_checkbox.isChecked(),
                "create_separate_file": self.separate_file_checkbox.isChecked(),
                "force_regenerate": self.force_regenerate_checkbox.isChecked(),
                "analysis_type": "Document Summary",  # Fixed to Document Summary
                "export_getreceipts": self.export_getreceipts_checkbox.isChecked(),
                # New HCE settings
                "profile": self.profile_combo.currentText(),
                "use_skim": self.use_skim_checkbox.isChecked(),
                "enable_routing": self.enable_routing_checkbox.isChecked(),
                "routing_threshold": self.routing_threshold_spin.value()
                / 100.0,  # Convert to 0-1
                "prompt_driven_mode": self.prompt_driven_mode_checkbox.isChecked(),
                "flagship_file_tokens": self.flagship_file_tokens_spin.value(),
                "flagship_session_tokens": self.flagship_session_tokens_spin.value(),
            }

            # Start async model availability check
            self._start_async_model_check(model)
            return  # Exit early, processing will continue after model check

        # Prepare settings
        gui_settings = {
            "provider": provider,
            "model": model,
            "max_tokens": self.max_tokens_spin.value(),
            "template_path": self.template_path_edit.text(),
            "output_dir": (
                self.output_edit.text()
                if self.separate_file_checkbox.isChecked()
                else None
            ),
            "update_in_place": self.update_md_checkbox.isChecked(),
            "create_separate_file": self.separate_file_checkbox.isChecked(),
            "force_regenerate": self.force_regenerate_checkbox.isChecked(),
            "analysis_type": "Document Summary",  # Fixed to Document Summary
            "export_getreceipts": self.export_getreceipts_checkbox.isChecked(),
            # New HCE settings
            "profile": self.profile_combo.currentText(),
            "use_skim": self.use_skim_checkbox.isChecked(),
            "enable_routing": self.enable_routing_checkbox.isChecked(),
            "routing_threshold": self.routing_threshold_spin.value()
            / 100.0,  # Convert to 0-1
            "prompt_driven_mode": self.prompt_driven_mode_checkbox.isChecked(),
            "flagship_file_tokens": self.flagship_file_tokens_spin.value(),
            "flagship_session_tokens": self.flagship_session_tokens_spin.value(),
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

        # Start rich log display to capture detailed processor information
        self.rich_log_display.start_processing("Enhanced Summarization")

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
        append_selected = self.update_md_checkbox.isChecked()
        separate_file_selected = self.separate_file_checkbox.isChecked()

        if not append_selected and not separate_file_selected:
            self.show_warning(
                "No Output Option Selected",
                "Please select at least one output option:\n"
                "• 'Append Summary To Transcript File' to add summary to existing files\n"
                "• 'Create A Separate Summary File' to create new summary files\n"
                "• Or both options to do both actions",
            )
            return False

        # If separate file option is selected, validate output directory
        if separate_file_selected:
            output_dir = self.output_edit.text().strip()
            if not output_dir:
                self.show_warning(
                    "No Output Directory",
                    "Please select an output directory when creating separate summary files.",
                )
                return False

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
        self._model_check_worker = ModelCheckWorker(model)
        self._model_check_worker.check_completed.connect(
            self._handle_model_check_result
        )
        self._model_check_worker.service_check_completed.connect(
            self._handle_service_check_result
        )
        self._model_check_worker.start()

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
        else:
            # Clean up worker if service is running
            if hasattr(self, "_model_check_worker"):
                self._model_check_worker.deleteLater()
                del self._model_check_worker

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
                self.append_log(f"❌ Model download cancelled or failed")

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

        self.active_workers.append(self.summarization_worker)
        self.set_processing_state(True)
        self.clear_log()

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
                f"Please ensure Ollama is properly installed and running.",
            )
            return False

    def _add_files(self) -> None:
        """Add files to the summarization list."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Summarize",
            str(Path.home()),
            "All Supported (*.txt *.md *.pdf *.html *.htm *.json);;Text Files (*.txt);;Markdown Files (*.md);;PDF Files (*.pdf);;HTML Files (*.html *.htm);;JSON Files (*.json);;All Files (*)",
        )

        for file_path in files:
            self.file_list.addItem(file_path)

    def _add_folder(self) -> None:
        """Add all compatible files from a folder."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            folder = Path(folder_path)
            extensions = [".txt", ".md", ".pdf", ".html", ".htm", ".json"]

            for file_path in folder.rglob("*"):
                if file_path.suffix.lower() in extensions:
                    self.file_list.addItem(str(file_path))

    def _clear_files(self) -> None:
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
            self.append_log(f"🔄 Refreshed OpenAI models from API")
        elif provider == "anthropic":
            self.append_log(f"🔄 Anthropic models (manually maintained)")
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
                            "llama3.2:3b (2 GB)",
                            "llama3.1:8b (5 GB)",
                            "qwen2.5:7b (4 GB)",
                            "mistral:7b (4 GB)",
                        ]
                        logger.debug(f"Using fallback models: {models}")

                # Add empty option first, then models
                all_items = [""] + (models if models else [])
                model_combo.addItems(all_items)

                # Try to restore previous selection if it's still valid
                if current_text and current_text in all_items:
                    model_combo.setCurrentText(current_text)

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

    def _toggle_output_options(self):
        """Toggle output directory visibility based on checkbox options."""
        # Show output directory if separate file creation is enabled
        show_output = self.separate_file_checkbox.isChecked()
        self.output_label.setVisible(show_output)
        self.output_edit.setVisible(show_output)
        self.output_btn.setVisible(show_output)

    def _on_checkbox_changed(self):
        """Called when output-related checkboxes change."""
        self._toggle_output_options()

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
    ) -> None:
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

        # Generate session report
        if success_count > 0:
            self._generate_session_report(
                success_count, failure_count, total_count, total_time_text
            )
            self.append_log(
                "📋 Session report generated - click 'View Session Report' to see details"
            )

        # Show claim validation option if summaries were generated with HCE
        if success_count > 0:
            self._show_claim_validation_option()

    def _on_processing_error(self, error: str) -> None:
        """Handle processing errors."""
        self.set_processing_state(False)
        self.append_log(f"Error: {error}")
        self.show_error("Processing Error", error)

    def _on_hce_analytics_updated(self, analytics: dict) -> None:
        """Handle HCE analytics updates to show relations and contradictions."""
        filename = analytics.get("filename", "Unknown file")

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
            if self.enable_routing_checkbox.isChecked():
                flagship_routed = analytics.get("flagship_routed_count", 0)
                local_processed = analytics.get("local_processed_count", 0)
                if flagship_routed > 0 or local_processed > 0:
                    self.append_log(f"   🎯 Routing Analytics:")
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
                    self.append_log(f"         vs. \"{contradiction['claim2']}\"")

            # Show top claims
            top_claims = analytics.get("top_claims", [])
            if top_claims:
                self.append_log(f"   🏆 Top Claims:")
                for i, claim in enumerate(top_claims, 1):
                    tier_icon = "🥇" if claim["tier"] == "A" else "🥈"
                    self.append_log(
                        f"      {tier_icon} {claim['text']} ({claim['type']})"
                    )

            self.append_log("")  # Add blank line for readability

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

    def _load_settings(self) -> None:
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
                self.separate_file_checkbox,
                self.force_regenerate_checkbox,
                self.progress_checkbox,
                self.resume_checkbox,
                self.export_getreceipts_checkbox,
                self.claim_tier_combo,
                self.max_claims_spin,
                self.include_contradictions_checkbox,
                self.include_relations_checkbox,
                self.tier_a_threshold_spin,
                self.tier_b_threshold_spin,
                # New HCE fields
                self.profile_combo,
                self.use_skim_checkbox,
                self.enable_routing_checkbox,
                self.routing_threshold_spin,
                self.prompt_driven_mode_checkbox,
                self.flagship_file_tokens_spin,
                self.flagship_session_tokens_spin,
                # Advanced per-stage provider and model dropdowns
                self.advanced_models_group,
                self.miner_provider,
                self.miner_model,
                self.heavy_miner_provider,
                self.heavy_miner_model,
                self.judge_provider,
                self.judge_model,
                self.flagship_judge_provider,
                self.flagship_judge_model,
                self.embedder_provider,
                self.embedder_model,
                self.reranker_provider,
                self.reranker_model,
                self.people_provider,
                self.people_model,
                self.nli_provider,
                self.nli_model,
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
                self.separate_file_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "separate_file", False
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
                self.export_getreceipts_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "export_getreceipts", False
                    )
                )

                # Load HCE settings
                saved_claim_tier = self.gui_settings.get_combo_selection(
                    self.tab_name, "claim_tier", "All"
                )
                index = self.claim_tier_combo.findText(saved_claim_tier)
                if index >= 0:
                    self.claim_tier_combo.setCurrentIndex(index)

                saved_max_claims = self.gui_settings.get_spinbox_value(
                    self.tab_name, "max_claims", 0
                )
                self.max_claims_spin.setValue(saved_max_claims)

                self.include_contradictions_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "include_contradictions", True
                    )
                )
                self.include_relations_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "include_relations", True
                    )
                )

                saved_tier_a_threshold = self.gui_settings.get_spinbox_value(
                    self.tab_name, "tier_a_threshold", 85
                )
                self.tier_a_threshold_spin.setValue(saved_tier_a_threshold)

                saved_tier_b_threshold = self.gui_settings.get_spinbox_value(
                    self.tab_name, "tier_b_threshold", 65
                )
                self.tier_b_threshold_spin.setValue(saved_tier_b_threshold)

                # Load new HCE settings
                # Profile selection
                saved_profile = self.gui_settings.get_combo_selection(
                    self.tab_name, "profile", "Balanced"
                )
                index = self.profile_combo.findText(saved_profile)
                if index >= 0:
                    self.profile_combo.setCurrentIndex(index)

                # Skim and routing settings
                self.use_skim_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "use_skim", True
                    )
                )
                self.enable_routing_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "enable_routing", True
                    )
                )
                saved_routing_threshold = self.gui_settings.get_spinbox_value(
                    self.tab_name, "routing_threshold", 35
                )
                self.routing_threshold_spin.setValue(saved_routing_threshold)

                # Template mode
                self.prompt_driven_mode_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "prompt_driven_mode", False
                    )
                )

                # Budget settings
                saved_flagship_file_tokens = self.gui_settings.get_spinbox_value(
                    self.tab_name, "flagship_file_tokens", 0
                )
                self.flagship_file_tokens_spin.setValue(saved_flagship_file_tokens)

                saved_flagship_session_tokens = self.gui_settings.get_spinbox_value(
                    self.tab_name, "flagship_session_tokens", 0
                )
                self.flagship_session_tokens_spin.setValue(
                    saved_flagship_session_tokens
                )

                # Load advanced models section state
                saved_advanced_expanded = self.gui_settings.get_checkbox_state(
                    self.tab_name, "advanced_models_expanded", True
                )
                self.advanced_models_group.setChecked(saved_advanced_expanded)

                # Load advanced per-stage provider and model selections
                advanced_dropdowns = [
                    ("miner", self.miner_provider, self.miner_model),
                    ("heavy_miner", self.heavy_miner_provider, self.heavy_miner_model),
                    ("judge", self.judge_provider, self.judge_model),
                    (
                        "flagship_judge",
                        self.flagship_judge_provider,
                        self.flagship_judge_model,
                    ),
                    ("embedder", self.embedder_provider, self.embedder_model),
                    ("reranker", self.reranker_provider, self.reranker_model),
                    ("people", self.people_provider, self.people_model),
                    ("nli", self.nli_provider, self.nli_model),
                ]

                for stage_name, provider_combo, model_combo in advanced_dropdowns:
                    # Load provider selection
                    saved_provider = self.gui_settings.get_combo_selection(
                        self.tab_name, f"{stage_name}_provider", ""
                    )
                    index = provider_combo.findText(saved_provider)
                    if index >= 0:
                        provider_combo.setCurrentIndex(index)
                        # Update models for this provider
                        if saved_provider:
                            self._update_advanced_model_combo(
                                saved_provider, model_combo
                            )

                    # Load model selection
                    saved_model = self.gui_settings.get_combo_selection(
                        self.tab_name, f"{stage_name}_model", ""
                    )
                    index = model_combo.findText(saved_model)
                    if index >= 0:
                        model_combo.setCurrentIndex(index)

                # Update output visibility based on checkbox state
                self._toggle_output_options()

            finally:
                # Always restore signals, even if an exception occurred
                for widget in widgets_to_block:
                    widget.blockSignals(False)

            logger.info(f"✅ Successfully loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")

    def _save_settings(self) -> None:
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
                self.tab_name, "separate_file", self.separate_file_checkbox.isChecked()
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

            # Save HCE settings
            self.gui_settings.set_combo_selection(
                self.tab_name, "claim_tier", self.claim_tier_combo.currentText()
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name, "max_claims", self.max_claims_spin.value()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "include_contradictions",
                self.include_contradictions_checkbox.isChecked(),
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "include_relations",
                self.include_relations_checkbox.isChecked(),
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name, "tier_a_threshold", self.tier_a_threshold_spin.value()
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name, "tier_b_threshold", self.tier_b_threshold_spin.value()
            )

            # Save new HCE settings
            self.gui_settings.set_combo_selection(
                self.tab_name, "profile", self.profile_combo.currentText()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "use_skim", self.use_skim_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "enable_routing",
                self.enable_routing_checkbox.isChecked(),
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name, "routing_threshold", self.routing_threshold_spin.value()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "prompt_driven_mode",
                self.prompt_driven_mode_checkbox.isChecked(),
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name,
                "flagship_file_tokens",
                self.flagship_file_tokens_spin.value(),
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name,
                "flagship_session_tokens",
                self.flagship_session_tokens_spin.value(),
            )

            # Save advanced models section state
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "advanced_models_expanded",
                self.advanced_models_group.isChecked(),
            )

            # Save advanced per-stage provider and model selections
            advanced_dropdowns = [
                ("miner", self.miner_provider, self.miner_model),
                ("heavy_miner", self.heavy_miner_provider, self.heavy_miner_model),
                ("judge", self.judge_provider, self.judge_model),
                (
                    "flagship_judge",
                    self.flagship_judge_provider,
                    self.flagship_judge_model,
                ),
                ("embedder", self.embedder_provider, self.embedder_model),
                ("reranker", self.reranker_provider, self.reranker_model),
                ("people", self.people_provider, self.people_model),
                ("nli", self.nli_provider, self.nli_model),
            ]

            for stage_name, provider_combo, model_combo in advanced_dropdowns:
                # Save provider selection
                self.gui_settings.set_combo_selection(
                    self.tab_name,
                    f"{stage_name}_provider",
                    provider_combo.currentText(),
                )
                # Save model selection
                self.gui_settings.set_combo_selection(
                    self.tab_name, f"{stage_name}_model", model_combo.currentText()
                )

            logger.info(f"✅ Successfully saved settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")

    def _on_setting_changed(self):
        """Called when any setting changes to automatically save."""
        logger.debug(f"🔄 Setting changed in {self.tab_name} tab, triggering save...")
        self._save_settings()

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
                f"To fix this:\n"
                f"1. Create the file '{template_path}'\n"
                f"2. Add your custom prompt template\n"
                f"3. Include {{text}} placeholder where content should go\n\n"
                f"The template path has been cleared. You can manually specify a different template file or create the missing one.",
            )

        # Trigger settings save after template path is updated
        self._on_setting_changed()

    def _on_profile_changed(self, profile: str) -> None:
        """Handle profile selection changes."""
        if profile == "Custom":
            return  # Don't override custom settings

        logger.debug(f"🔄 Profile changed to: {profile}")

        # Apply profile settings
        if profile == "Fast":
            # Fast: skim off, routing off, lightweight only
            self.use_skim_checkbox.setChecked(False)
            self.enable_routing_checkbox.setChecked(False)
            self.routing_threshold_spin.setValue(50)  # Higher threshold = less routing

        elif profile == "Balanced":
            # Balanced: skim on, routing on, default settings
            self.use_skim_checkbox.setChecked(True)
            self.enable_routing_checkbox.setChecked(True)
            self.routing_threshold_spin.setValue(35)  # Default

        elif profile == "Quality":
            # Quality: skim on, aggressive routing, all features
            self.use_skim_checkbox.setChecked(True)
            self.enable_routing_checkbox.setChecked(True)
            self.routing_threshold_spin.setValue(25)  # Lower = more routing

        # Show brief feedback
        self.append_log(f"📋 Applied {profile} profile settings")

        # Trigger settings save
        self._save_settings()

    def _on_routing_toggle_changed(self, enabled: bool) -> None:
        """Handle routing toggle changes."""
        # Enable/disable routing threshold based on toggle
        self.routing_threshold_spin.setEnabled(enabled)

        # Show dependency warning if routing enabled without flagship judge
        if enabled:
            flagship_provider = getattr(self, "flagship_judge_provider", None)
            flagship_model = getattr(self, "flagship_judge_model", None)

            if flagship_provider and flagship_model:
                if (
                    not flagship_provider.currentText()
                    or not flagship_model.currentText()
                ):
                    self.append_log(
                        "⚠️ Routing enabled but no flagship judge model configured"
                    )

    def _on_template_mode_changed(self, enabled: bool) -> None:
        """Handle template mode toggle changes."""
        if enabled:
            self.append_log(
                "📋 Prompt-driven mode enabled - HCE formatting will be bypassed"
            )
            # Could add visual indicators here if needed
        else:
            self.append_log("🔍 Standard HCE analysis mode enabled")

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
                    "profile": self.profile_combo.currentText(),
                    "provider": self.provider_combo.currentText(),
                    "model": self.model_combo.currentText(),
                    "max_tokens": self.max_tokens_spin.value(),
                    "analysis_type": "Document Summary",  # Fixed to Document Summary
                    "use_skim": self.use_skim_checkbox.isChecked(),
                    "enable_routing": self.enable_routing_checkbox.isChecked(),
                    "routing_threshold": self.routing_threshold_spin.value(),
                    "prompt_driven_mode": self.prompt_driven_mode_checkbox.isChecked(),
                    "flagship_file_tokens": self.flagship_file_tokens_spin.value(),
                    "flagship_session_tokens": self.flagship_session_tokens_spin.value(),
                },
                "output_settings": {
                    "update_in_place": self.update_md_checkbox.isChecked(),
                    "create_separate_file": self.separate_file_checkbox.isChecked(),
                    "output_directory": self.output_edit.text(),
                    "force_regenerate": self.force_regenerate_checkbox.isChecked(),
                },
            }

            # Save report to output directory or default location
            output_dir = (
                self.output_edit.text()
                if self.separate_file_checkbox.isChecked()
                else "output/summaries"
            )
            report_path = (
                Path(output_dir)
                / f"session_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            report_path.parent.mkdir(parents=True, exist_ok=True)

            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

            # Store report path for viewing
            self._last_session_report = report_path

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
                        ["start", str(self._last_session_report)], shell=True
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
            except:
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

            db = DatabaseService()

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

            self.append_log(f"\n✅ Claim validation completed!")
            self.append_log(f"📊 Validation Summary:")
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

    def _on_processing_finished(
        self, success_count: int, failure_count: int, total_count: int
    ):
        """Handle summarization completion."""
        # Stop rich log display
        self.rich_log_display.stop_processing()

        self.append_log(f"\n✅ Enhanced summarization completed!")
        self.append_log(f"📊 Final Summary:")
        self.append_log(f"   • Successfully processed: {success_count} files")
        if failure_count > 0:
            self.append_log(f"   • Failed to process: {failure_count} files")
        self.append_log(f"   • Total files: {total_count}")

    def _on_processor_progress(self, message: str, percentage: int):
        """Handle progress updates from the processor log integrator."""
        # Log rich processor information
        self.append_log(f"🔧 {message}")

    def _on_processor_status(self, status: str):
        """Handle status updates from the processor log integrator."""
        # Add rich processor status to our regular log output
        self.append_log(f"🔍 {status}")
