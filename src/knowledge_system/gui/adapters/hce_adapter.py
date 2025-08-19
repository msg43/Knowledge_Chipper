"""
HCE Adapter for GUI Components

Provides a compatibility layer between HCE processors and existing GUI components.
Maintains backward compatibility while enabling HCE features.
"""

from collections.abc import Callable
from typing import Any, Dict, Optional

from ...logger import get_logger
from ...processors.moc import MOCProcessor
from ...processors.summarizer import SummarizerProcessor
from ...utils.progress import SummarizationProgress

logger = get_logger(__name__)


class HCEAdapter:
    """Adapter to integrate HCE processors with existing GUI components."""

    def __init__(self):
        self.current_processor = None
        self.progress_callback = None

    def create_summarizer(
        self,
        provider: str = "openai",
        model: str = None,
        max_tokens: int = 500,
        **kwargs,
    ) -> SummarizerProcessor:
        """
        Create an HCE-based summarizer that maintains legacy API.

        The returned processor extracts claims instead of generating summaries,
        but formats output to match expected interface.
        """
        processor = SummarizerProcessor(
            provider=provider, model=model, max_tokens=max_tokens
        )
        self.current_processor = processor
        return processor

    def create_moc_processor(self, **kwargs) -> MOCProcessor:
        """
        Create an HCE-based MOC processor that maintains legacy API.

        Uses HCE entity extraction instead of regex patterns.
        """
        processor = MOCProcessor()
        self.current_processor = processor
        return processor

    def process_with_progress(
        self,
        processor: Any,
        input_data: Any,
        progress_callback: Callable[[Any], None],
        **kwargs,
    ) -> Any:
        """
        Process data with progress tracking adapted for HCE stages.

        Maps HCE pipeline stages to legacy progress updates.
        """
        self.progress_callback = progress_callback

        # Map HCE stages to progress updates
        def hce_progress_wrapper(stage: str, progress: float):
            if progress_callback:
                if isinstance(processor, SummarizerProcessor):
                    # Map HCE stages to summarization progress
                    stage_mapping = {
                        "skim": "Analyzing document structure...",
                        "mine": "Extracting claims...",
                        "evidence": "Linking evidence...",
                        "dedupe": "Deduplicating claims...",
                        "rerank": "Ranking claims...",
                        "judge": "Validating claims...",
                        "export": "Formatting output...",
                    }

                    status = stage_mapping.get(stage, f"Processing {stage}...")

                    progress_obj = SummarizationProgress(
                        current_chunk=int(progress * 100),
                        total_chunks=100,
                        status=status,
                        current_operation=f"HCE: {stage}",
                    )
                    progress_callback(progress_obj)

        # Inject progress wrapper if possible
        original_process = processor.process

        def process_with_hce_progress(*args, **process_kwargs):
            # Add progress tracking
            process_kwargs["hce_progress_callback"] = hce_progress_wrapper
            return original_process(*args, **process_kwargs)

        # Temporarily replace process method
        processor.process = process_with_hce_progress

        try:
            # Process with enhanced progress tracking
            result = processor.process(input_data, **kwargs)
            return result
        finally:
            # Restore original method
            processor.process = original_process

    def adapt_output_for_gui(self, result: Any, output_type: str) -> dict[str, Any]:
        """
        Adapt HCE output to match GUI expectations.

        Args:
            result: HCE processor result
            output_type: Type of output ('summary', 'moc', etc.)

        Returns:
            Dictionary with GUI-compatible fields
        """
        if output_type == "summary":
            # Extract key information for GUI display
            metadata = result.metadata if hasattr(result, "metadata") else {}

            return {
                "text": result.data if hasattr(result, "data") else str(result),
                "claim_count": metadata.get("claims_extracted", 0),
                "people_count": metadata.get("people_found", 0),
                "concept_count": metadata.get("concepts_found", 0),
                "tier_a_claims": self._extract_tier_claims(metadata, "A"),
                "tier_b_claims": self._extract_tier_claims(metadata, "B"),
                "processing_type": "hce",
            }

        elif output_type == "moc":
            # Format MOC data for GUI
            data = result.data if hasattr(result, "data") else {}
            metadata = result.metadata if hasattr(result, "metadata") else {}

            return {
                "files": data,
                "people_found": metadata.get("people_found", 0),
                "tags_found": metadata.get("tags_found", 0),
                "models_found": metadata.get("mental_models_found", 0),
                "jargon_found": metadata.get("jargon_found", 0),
                "processing_type": "hce",
            }

        return {"data": result, "processing_type": "hce"}

    def _extract_tier_claims(self, metadata: dict, tier: str) -> list:
        """Extract claims of a specific tier from metadata."""
        hce_data = metadata.get("hce_data", {})
        claims = hce_data.get("claims", [])

        return [claim for claim in claims if claim.get("tier") == tier]

    def get_stage_descriptions(self) -> dict[str, str]:
        """Get human-readable descriptions of HCE pipeline stages."""
        return {
            "skim": "Analyzing document structure and identifying key sections",
            "mine": "Extracting candidate claims and statements",
            "evidence": "Linking claims to supporting evidence",
            "dedupe": "Removing duplicate and redundant claims",
            "rerank": "Ranking claims by importance and relevance",
            "judge": "Validating claims and assigning confidence scores",
            "entities": "Extracting people, concepts, and terminology",
            "relations": "Identifying relationships between claims",
            "export": "Formatting results for display",
        }

    def estimate_processing_time(self, input_size: int, processor_type: str) -> float:
        """
        Estimate processing time for HCE pipeline.

        Args:
            input_size: Size of input in characters
            processor_type: Type of processor ('summarizer' or 'moc')

        Returns:
            Estimated time in seconds
        """
        # Base estimate: ~1 second per 1000 characters
        base_time = input_size / 1000

        if processor_type == "summarizer":
            # HCE pipeline is more thorough, multiply by factor
            return base_time * 2.5
        elif processor_type == "moc":
            # MOC is faster with HCE entity extraction
            return base_time * 1.5

        return base_time


# Global adapter instance
_adapter = HCEAdapter()


def get_hce_adapter() -> HCEAdapter:
    """Get the global HCE adapter instance."""
    return _adapter
