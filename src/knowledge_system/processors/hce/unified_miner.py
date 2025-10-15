"""
Unified Miner for extracting claims, jargon, people, and mental models in a single pass.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, List

from .model_uri_parser import parse_model_uri
from .models.llm_system2 import System2LLM
from .schema_validator import validate_miner_output
from .types import EpisodeBundle, Segment


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

    def __init__(self, llm: System2LLM, prompt_path: Path | None = None):
        self.llm = llm

        # Load prompt
        if prompt_path is None:
            prompt_path = Path(__file__).parent / "prompts" / "unified_miner.txt"

        if not prompt_path.exists():
            raise FileNotFoundError(f"Unified miner prompt not found: {prompt_path}")

        self.template = prompt_path.read_text()

    def mine_segment(self, segment: Segment) -> UnifiedMinerOutput:
        """Extract all entity types from a single segment."""

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
            # Try structured JSON generation first (for Ollama models)
            raw_result = None
            if hasattr(self.llm, "generate_structured_json"):
                try:
                    raw_result = self.llm.generate_structured_json(
                        full_prompt, "miner_output"
                    )
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.info(
                        "🔒 Using structured outputs with schema enforcement for miner"
                    )
                except Exception as e:
                    import logging

                    # Import error classes from the correct location
                    import sys
                    import traceback

                    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
                    from knowledge_system.errors import ErrorCode, KnowledgeSystemError

                    logger = logging.getLogger(__name__)

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

            # Debug logging
            import logging

            logger = logging.getLogger(__name__)
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

            # Validate against schema (still useful for non-Ollama providers)
            is_valid, errors = validate_miner_output(result)
            if not is_valid:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Miner output failed schema validation: {errors}")
                # Continue with basic validation

            # Validate and return
            output = UnifiedMinerOutput(result)
            if not output.is_valid():
                # Return empty structure if invalid
                return UnifiedMinerOutput(
                    {"claims": [], "jargon": [], "people": [], "mental_models": []}
                )

            return output

        except Exception as e:
            import logging
            import traceback

            logger = logging.getLogger(__name__)

            # Safely convert exception to string (handle ErrorCode enums in exception args)
            try:
                error_msg = str(e)
            except Exception as format_error:
                error_msg = f"<exception formatting failed: {type(e).__name__}>"
                logger.debug(f"Exception formatting error: {format_error}")
                logger.debug(f"Exception args: {e.args}")

            logger.warning(
                f"Unified mining failed for segment {segment.segment_id}: {error_msg}"
            )

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

        # If max_workers is 1 or None, use sequential processing
        if max_workers == 1 or max_workers is None:
            outputs = []
            for segment in episode.segments:
                output = self.mine_segment(segment)
                outputs.append(output)
                if progress_callback:
                    progress_callback(f"Processed segment {segment.segment_id}")
            return outputs

        # Use parallel processing for max_workers > 1
        from .parallel_processor import create_parallel_processor

        processor = create_parallel_processor(max_workers=max_workers)

        def process_segment(segment):
            return self.mine_segment(segment)

        return processor.process_parallel(
            items=episode.segments,
            processor_func=process_segment,
            progress_callback=progress_callback,
        )


def mine_episode_unified(
    episode: EpisodeBundle,
    miner_model_uri: str,
    max_workers: int | None = None,
    progress_callback: Callable | None = None,
) -> list[UnifiedMinerOutput]:
    """
    Convenience function for mining an entire episode with the unified miner.

    Args:
        episode: The episode to mine
        miner_model_uri: URI for the miner LLM model (format: "provider:model")
        max_workers: Number of parallel workers (None = auto, 1 = sequential)
        progress_callback: Optional progress reporting function

    Returns:
        List of UnifiedMinerOutput objects, one per segment
    """
    # Parse model URI with proper handling of local:// and other formats
    provider, model = parse_model_uri(miner_model_uri)

    # Create System2LLM instance
    llm = System2LLM(provider=provider, model=model, temperature=0.3)

    # Use simplified prompt for Ollama models
    if provider and provider.lower() == "ollama":
        prompt_path = Path(__file__).parent / "prompts" / "unified_miner_ollama.txt"
        if not prompt_path.exists():
            # Fall back to main prompt if Ollama version doesn't exist
            prompt_path = Path(__file__).parent / "prompts" / "unified_miner.txt"
    else:
        prompt_path = Path(__file__).parent / "prompts" / "unified_miner.txt"

    miner = UnifiedMiner(llm, prompt_path)
    return miner.mine_episode(
        episode, max_workers=max_workers, progress_callback=progress_callback
    )
