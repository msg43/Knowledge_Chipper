"""
Unified Miner for extracting claims, jargon, people, and mental models in a single pass.

Supports prompt refinements synced from GetReceipts.org - these are bad_example entries
that get injected into extraction prompts to prevent previously-identified classes of mistakes.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...logger import get_logger
from .model_uri_parser import parse_model_uri
from .models.llm_system2 import System2LLM
from .schema_validator import repair_and_validate_miner_output, validate_miner_output
from .types import EpisodeBundle, Segment

logger = get_logger(__name__)


def _inject_refinements_into_template(template: str, refinements: dict[str, str]) -> str:
    """
    Inject synced refinements into the prompt template.
    
    Refinements are inserted just before the closing tags for each entity type:
    - </bad_people> for person refinements
    - </bad_jargon> for jargon refinements  
    - </bad_mental_models> for concept refinements
    
    Args:
        template: The original prompt template
        refinements: Dict mapping entity_type to refinements XML content
        
    Returns:
        Template with refinements injected
    """
    modified_template = template
    
    # Mapping from entity type to the closing tag where we inject
    injection_points = {
        "person": "</bad_people>",
        "jargon": "</bad_jargon>",
        "concept": "</bad_mental_models>",
    }
    
    injection_count = 0
    for entity_type, closing_tag in injection_points.items():
        refinement_content = refinements.get(entity_type, "").strip()
        if refinement_content and closing_tag in modified_template:
            # Insert refinements before the closing tag
            # Add a comment indicating these are synced refinements
            injection = f"\n  <!-- Synced refinements from GetReceipts.org -->\n{refinement_content}\n  "
            modified_template = modified_template.replace(
                closing_tag,
                f"{injection}{closing_tag}"
            )
            injection_count += 1
            logger.debug(f"Injected {entity_type} refinements into prompt")
    
    if injection_count > 0:
        logger.info(f"📝 Injected refinements for {injection_count} entity types into prompt")
    
    return modified_template


def _load_refinements() -> dict[str, str]:
    """
    Load refinements from the prompt sync service.
    
    Returns:
        Dict mapping entity_type to refinements content, or empty dict if unavailable
    """
    try:
        from ...services.prompt_sync import get_prompt_sync_service
        sync_service = get_prompt_sync_service()
        
        if sync_service.has_refinements():
            refinements = sync_service.get_all_refinements()
            total = sum(1 for v in refinements.values() if v.strip())
            if total > 0:
                logger.debug(f"Loaded refinements for {total} entity types")
            return refinements
    except Exception as e:
        logger.debug(f"Could not load refinements (non-fatal): {e}")
    
    return {}


class UnifiedMinerOutput:
    """Structured output from the unified miner."""

    def __init__(self, raw_output: dict[str, Any]):
        self.raw = raw_output
        self.claims = raw_output.get("claims", [])
        self.jargon = raw_output.get("jargon", [])
        self.people = raw_output.get("people", [])
        self.mental_models = raw_output.get("mental_models", [])

    def is_valid(self) -> bool:
        """Check if the output has the expected structure."""
        required_keys = ["claims", "jargon", "people", "mental_models"]
        return all(key in self.raw for key in required_keys)

    def total_extractions(self) -> int:
        """Total number of items extracted across all categories."""
        return (
            len(self.claims)
            + len(self.jargon)
            + len(self.people)
            + len(self.mental_models)
        )


class UnifiedMiner:
    """
    Unified miner that extracts claims, jargon, people, and mental models
    from content segments in a single LLM call per segment.
    """

    def __init__(
        self,
        llm: System2LLM,
        prompt_path: Path | None = None,
        selectivity: str = "moderate",
        content_type: str | None = None,
    ):
        self.llm = llm
        self.selectivity = selectivity
        self.content_type = content_type

        # Load prompt based on selectivity if path not explicitly provided
        if prompt_path is None:
            # If content_type is specified, use content-specific prompt
            if content_type:
                content_type_files = {
                    "transcript_own": "unified_miner_transcript_own_V3.txt",
                    "transcript_third_party": "unified_miner_transcript_third_party.txt",
                    "document_pdf": "unified_miner_document.txt",
                    "document_whitepaper": "unified_miner_document.txt",  # Uses same as document_pdf
                }
                prompt_file = content_type_files.get(content_type)

                if prompt_file:
                    prompt_path = Path(__file__).parent / "prompts" / prompt_file
                    # Check if content-specific prompt exists
                    if not prompt_path.exists():
                        logger.warning(
                            f"Content-specific prompt not found: {prompt_path}, falling back to default"
                        )
                        prompt_path = None

            # Fall back to selectivity-based prompts
            if prompt_path is None:
                prompt_files = {
                    "liberal": "unified_miner_liberal.txt",
                    "moderate": "unified_miner_moderate.txt",
                    "conservative": "unified_miner_conservative.txt",
                }
                prompt_file = prompt_files.get(
                    selectivity, "unified_miner_moderate.txt"
                )
                prompt_path = Path(__file__).parent / "prompts" / prompt_file

        if not prompt_path.exists():
            # Final fallback to unified_miner.txt
            prompt_path = Path(__file__).parent / "prompts" / "unified_miner.txt"
            if not prompt_path.exists():
                raise FileNotFoundError(f"No unified miner prompt found")

        self.template = prompt_path.read_text()
        
        # Load and inject synced refinements from GetReceipts.org
        # These are bad_example entries that prevent previously-identified mistakes
        refinements = _load_refinements()
        if refinements:
            self.template = _inject_refinements_into_template(self.template, refinements)
        
        logger.info(
            f"UnifiedMiner initialized with {selectivity} selectivity"
            + (f" and {content_type} content type" if content_type else "")
        )

    def mine_segment(self, segment: Segment) -> UnifiedMinerOutput:
        """Extract all entity types from a single segment."""

        logger.debug(
            f"🔍 Starting mining for segment {segment.segment_id} ({segment.t0}-{segment.t1})"
        )

        # Prepare segment data for the prompt
        segment_data = {
            "segment_id": segment.segment_id,
            "speaker": segment.speaker,
            "timestamp_start": segment.t0,
            "timestamp_end": segment.t1,
            "text": segment.text,
        }

        # Create the full prompt
        full_prompt = f"{self.template}\n\nSEGMENT TO ANALYZE:\n{json.dumps(segment_data, indent=2)}"

        try:
            # Notify user that LLM processing is starting (helps explain the long wait)
            logger.info(f"⏳ Requesting LLM analysis for segment {segment.segment_id}...")
            logger.debug(f"📤 Sending LLM request for segment {segment.segment_id}")
            # Try structured JSON generation first (for Ollama models)
            raw_result = None
            if hasattr(self.llm, "generate_structured_json"):
                try:
                    raw_result = self.llm.generate_structured_json(
                        full_prompt, "miner_output"
                    )
                    logger.debug(
                        "🔒 Using structured outputs with schema enforcement for miner"
                    )
                except Exception as e:
                    # Import error classes from the correct location
                    import sys
                    import traceback

                    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
                    from knowledge_system.errors import ErrorCode, KnowledgeSystemError

                    # If this is a critical error (like invalid provider), don't fall back - re-raise
                    if (
                        isinstance(e, KnowledgeSystemError)
                        and hasattr(e, "error_code")
                        and e.error_code == ErrorCode.INVALID_INPUT
                    ):
                        logger.error(
                            f"Critical error in structured JSON generation: {e}"
                        )
                        raise

                    # Safely convert exception to string (handle ErrorCode enums in exception args)
                    try:
                        error_msg = str(e)
                    except Exception as format_error:
                        # If even str(e) fails, use repr
                        error_msg = f"<exception formatting failed: {type(e).__name__}>"
                        logger.debug(f"Exception formatting error: {format_error}")
                        logger.debug(f"Exception args: {e.args}")
                        logger.debug(f"Full traceback: {traceback.format_exc()}")

                    logger.warning(
                        f"Structured JSON generation failed, falling back: {error_msg}"
                    )

            # Fall back to regular JSON generation if structured failed or not available
            if raw_result is None:
                raw_result = self.llm.generate_json(full_prompt)

            logger.info(f"📥 Received LLM response for segment {segment.segment_id}")

            # Debug logging
            logger.debug(f"🔍 MINER DEBUG: raw_result type: {type(raw_result)}")
            logger.debug(f"🔍 MINER DEBUG: raw_result value: {raw_result}")

            if not raw_result:
                logger.warning(
                    f"🔍 MINER DEBUG: Empty raw_result, returning empty output"
                )
                return UnifiedMinerOutput(
                    {"claims": [], "jargon": [], "people": [], "mental_models": []}
                )

            # Handle both list and dict responses
            if isinstance(raw_result, list):
                result = raw_result[0] if raw_result else {}
            elif isinstance(raw_result, dict):
                result = raw_result
            else:
                result = {}

            # Ensure result is a dictionary
            if not isinstance(result, dict):
                result = {}

            # Repair and validate against schema (v2 with full evidence structure)
            # This will add missing required fields (claims, jargon, people, mental_models)
            # and migrate v1 flat structure to v2 nested structure if needed
            repaired_result, is_valid, errors = repair_and_validate_miner_output(result)
            if not is_valid:
                logger.warning(
                    f"Miner output failed schema validation after repair: {errors}"
                )
                # Use repaired result anyway - it will have the required structure
                # The repair function will have migrated v1→v2 format

            result = repaired_result

            # Validate and return
            output = UnifiedMinerOutput(result)
            if not output.is_valid():
                # Return empty structure if invalid
                logger.warning(
                    f"⚠️  Segment {segment.segment_id} output invalid, returning empty"
                )
                return UnifiedMinerOutput(
                    {"claims": [], "jargon": [], "people": [], "mental_models": []}
                )

            # More user-friendly logging (segment_id can be technical like "chunk_0000")
            logger.info(
                f"✅ Segment mining complete: "
                f"{len(output.claims)} claims, {len(output.jargon)} jargon, "
                f"{len(output.people)} people, {len(output.mental_models)} concepts"
            )

            return output

        except Exception as e:
            import traceback

            # Safely convert exception to string (handle ErrorCode enums in exception args)
            try:
                error_msg = str(e)
            except Exception as format_error:
                error_msg = f"<exception formatting failed: {type(e).__name__}>"
                logger.debug(f"Exception formatting error: {format_error}")
                logger.debug(f"Exception args: {e.args}")

            logger.error(
                f"❌ Unified mining failed for segment {segment.segment_id}: {error_msg}"
            )
            logger.debug(f"Full traceback:\n{traceback.format_exc()}")

            # Return empty structure on failure
            return UnifiedMinerOutput(
                {"claims": [], "jargon": [], "people": [], "mental_models": []}
            )

    def mine_episode(
        self,
        episode: EpisodeBundle,
        max_workers: int | None = None,
        progress_callback: Callable | None = None,
    ) -> list[UnifiedMinerOutput]:
        """Extract all entity types from all segments in an episode."""

        # If max_workers is 1, use sequential processing
        # If max_workers is None, auto-calculate optimal workers
        if max_workers == 1:
            outputs = []
            total_segments = len(episode.segments)
            for i, segment in enumerate(episode.segments, 1):
                output = self.mine_segment(segment)
                outputs.append(output)
                if progress_callback:
                    progress_callback(f"Processed segment {i} of {total_segments}")
            return outputs

        # Use parallel processing (max_workers=None means auto-calculate)
        from .parallel_processor import create_parallel_processor

        processor = create_parallel_processor(max_workers=max_workers)

        def process_segment(segment):
            return self.mine_segment(segment)

        return processor.process_parallel(
            items=episode.segments,
            processor_func=process_segment,
            progress_callback=progress_callback,
        )

    def mine(
        self,
        input_data: str | EpisodeBundle,
        metadata: dict | None = None,
        chunk_size: int = 15000,
        overlap: int = 1000,
    ) -> UnifiedMinerOutput:
        """
        Extract entities from text or episode (claims-first compatible).
        
        This method supports both:
        1. Plain text input (claims-first mode) - creates virtual segments
        2. EpisodeBundle input (legacy mode) - uses existing segments
        
        Args:
            input_data: Either plain text string or EpisodeBundle
            metadata: Optional metadata dict for context
            chunk_size: Maximum characters per chunk (for plain text)
            overlap: Character overlap between chunks
        
        Returns:
            Merged UnifiedMinerOutput with all extracted entities
        """
        if isinstance(input_data, str):
            # Claims-first mode: plain text without speaker labels
            return self._mine_text(input_data, metadata, chunk_size, overlap)
        elif isinstance(input_data, EpisodeBundle):
            # Legacy mode: process as episode with segments
            outputs = self.mine_episode(input_data)
            return self._merge_outputs(outputs)
        else:
            raise TypeError(
                f"input_data must be str or EpisodeBundle, got {type(input_data)}"
            )

    def _mine_text(
        self,
        text: str,
        metadata: dict | None = None,
        chunk_size: int = 15000,
        overlap: int = 1000,
    ) -> UnifiedMinerOutput:
        """
        Mine entities from plain text (internal method).
        
        Creates virtual segments from text and processes them.
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to mine()")
            return UnifiedMinerOutput(
                {"claims": [], "jargon": [], "people": [], "mental_models": []}
            )
        
        # Create virtual segments from text
        source_id = metadata.get("source_id", "claims_first") if metadata else "claims_first"
        segments = self._create_segments_from_text(text, chunk_size, overlap, source_id=source_id)
        
        logger.info(f"Created {len(segments)} virtual segments from text ({len(text)} chars)")
        
        # Process each segment
        outputs = []
        for i, segment in enumerate(segments, 1):
            logger.info(f"Mining segment {i}/{len(segments)}")
            output = self.mine_segment(segment)
            outputs.append(output)
        
        # Merge all outputs
        return self._merge_outputs(outputs)

    def _create_segments_from_text(
        self,
        text: str,
        chunk_size: int = 15000,
        overlap: int = 1000,
        source_id: str = "claims_first",
    ) -> list[Segment]:
        """
        Create virtual Segment objects from plain text.
        
        Splits text into chunks respecting paragraph boundaries.
        """
        segments = []
        text_length = len(text)
        
        # If text is short enough, use single segment
        if text_length <= chunk_size:
            segment = Segment(
                source_id=source_id,
                segment_id="chunk_0000",
                speaker="UNKNOWN",  # Claims-first: speaker assigned later
                t0="0.0",
                t1="0.0",  # Timestamps will be matched later
                text=text.strip(),
            )
            return [segment]
        
        # Split into chunks at paragraph boundaries
        start = 0
        segment_idx = 0
        
        while start < text_length:
            end = min(start + chunk_size, text_length)
            
            # Try to find paragraph boundary near end
            if end < text_length:
                # Look for paragraph break in last 20% of chunk
                search_start = start + int(chunk_size * 0.8)
                paragraph_break = text.rfind('\n\n', search_start, end)
                if paragraph_break > search_start:
                    end = paragraph_break
                else:
                    # Fall back to sentence boundary
                    sentence_break = text.rfind('. ', search_start, end)
                    if sentence_break > search_start:
                        end = sentence_break + 1
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                segment = Segment(
                    source_id=source_id,
                    segment_id=f"chunk_{segment_idx:04d}",
                    speaker="UNKNOWN",  # Claims-first: speaker assigned later
                    t0="0.0",  # Timestamps as strings
                    t1="0.0",  # Will be refined by timestamp matcher
                    text=chunk_text,
                )
                segments.append(segment)
                segment_idx += 1
            
            # Move start, accounting for overlap
            start = max(end - overlap, end)
            if start >= text_length:
                break
        
        return segments

    def _merge_outputs(self, outputs: list[UnifiedMinerOutput]) -> UnifiedMinerOutput:
        """
        Merge multiple outputs into a single UnifiedMinerOutput.
        
        Deduplicates entities that appear in overlapping chunks.
        """
        merged = {
            "claims": [],
            "jargon": [],
            "people": [],
            "mental_models": [],
        }
        
        seen_claims = set()
        seen_jargon = set()
        seen_people = set()
        seen_models = set()
        
        for output in outputs:
            # Merge claims (deduplicate by claim_text or canonical)
            for claim in output.claims:
                # Handle both claim_text (from miner) and canonical (normalized)
                claim_text = claim.get("claim_text") or claim.get("canonical") or ""
                if claim_text and claim_text not in seen_claims:
                    seen_claims.add(claim_text)
                    merged["claims"].append(claim)
            
            # Merge jargon (deduplicate by term)
            for term in output.jargon:
                term_text = term.get("term", "")
                if term_text and term_text.lower() not in seen_jargon:
                    seen_jargon.add(term_text.lower())
                    merged["jargon"].append(term)
            
            # Merge people (deduplicate by name)
            for person in output.people:
                name = person.get("name", "")
                if name and name.lower() not in seen_people:
                    seen_people.add(name.lower())
                    merged["people"].append(person)
            
            # Merge mental models (deduplicate by name)
            for model in output.mental_models:
                name = model.get("name", "")
                if name and name.lower() not in seen_models:
                    seen_models.add(name.lower())
                    merged["mental_models"].append(model)
        
        logger.info(
            f"Merged outputs: {len(merged['claims'])} claims, "
            f"{len(merged['jargon'])} jargon, {len(merged['people'])} people, "
            f"{len(merged['mental_models'])} concepts"
        )
        
        return UnifiedMinerOutput(merged)


def mine_text(
    text: str,
    miner_model_uri: str,
    metadata: dict | None = None,
    chunk_size: int = 15000,
    overlap: int = 1000,
    selectivity: str = "moderate",
    content_type: str | None = None,
) -> UnifiedMinerOutput:
    """
    Mine entities from plain text (claims-first mode).
    
    This is the primary entry point for claims-first pipeline, where we
    extract claims from undiarized transcripts without speaker labels.
    
    Args:
        text: Plain transcript text to mine
        miner_model_uri: URI for the miner LLM model (format: "provider:model")
        metadata: Optional metadata dict for context
        chunk_size: Maximum characters per chunk (for long transcripts)
        overlap: Character overlap between chunks
        selectivity: Miner selectivity ("liberal" | "moderate" | "conservative")
        content_type: Content type for specialized prompts
    
    Returns:
        Merged UnifiedMinerOutput with all extracted entities
    """
    # Parse model URI
    provider, model = parse_model_uri(miner_model_uri)
    
    # Create System2LLM instance
    llm = System2LLM(provider=provider, model=model, temperature=0.3)
    
    # Create miner
    miner = UnifiedMiner(
        llm, 
        prompt_path=None, 
        selectivity=selectivity, 
        content_type=content_type
    )
    
    # Use the new mine() method for plain text
    return miner.mine(text, metadata)


def mine_episode_unified(
    episode: EpisodeBundle,
    miner_model_uri: str,
    max_workers: int | None = None,
    progress_callback: Callable | None = None,
    selectivity: str = "moderate",  # NEW: Miner selectivity level
    content_type: str | None = None,  # Content type for specialized prompts
) -> list[UnifiedMinerOutput]:
    """
    Convenience function for mining an entire episode with the unified miner.

    Args:
        episode: The episode to mine
        miner_model_uri: URI for the miner LLM model (format: "provider:model")
        max_workers: Number of parallel workers (None = auto, 1 = sequential)
        progress_callback: Optional progress reporting function
        selectivity: Miner selectivity ("liberal" | "moderate" | "conservative")

    Returns:
        List of UnifiedMinerOutput objects, one per segment
    """
    # Parse model URI with proper handling of local:// and other formats
    provider, model = parse_model_uri(miner_model_uri)

    # Create System2LLM instance
    llm = System2LLM(provider=provider, model=model, temperature=0.3)

    # Select prompt based on selectivity (replaces Ollama-specific logic)
    prompt_files = {
        "liberal": "unified_miner_liberal.txt",
        "moderate": "unified_miner_moderate.txt",
        "conservative": "unified_miner_conservative.txt",
    }
    prompt_file = prompt_files.get(selectivity, "unified_miner_moderate.txt")
    prompt_path = Path(__file__).parent / "prompts" / prompt_file

    if not prompt_path.exists():
        # Fall back to moderate if selected variant doesn't exist
        prompt_path = Path(__file__).parent / "prompts" / "unified_miner_moderate.txt"

    miner = UnifiedMiner(
        llm, prompt_path, selectivity=selectivity, content_type=content_type
    )
    return miner.mine_episode(
        episode, max_workers=max_workers, progress_callback=progress_callback
    )
