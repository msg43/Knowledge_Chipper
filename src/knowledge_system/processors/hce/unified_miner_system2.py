"""
System 2 Unified Miner

Modified version of UnifiedMiner that uses the centralized LLM adapter
for all model calls with proper concurrency control and tracking.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ...core.llm_adapter import LLMAdapter
from ...logger import get_logger
from .schema_validator import repair_and_validate_miner_output
from .types import Segment
from .unified_miner import UnifiedMinerOutput

logger = get_logger(__name__)


class UnifiedMinerSystem2:
    """
    System 2 version of UnifiedMiner that uses centralized LLM adapter.

    This version:
    - Uses LLMAdapter for all LLM calls
    - Tracks requests/responses in database
    - Respects hardware tier concurrency limits
    - Implements proper error handling and retries
    """

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        provider: str = "openai",
        model: str = "gpt-4",
        prompt_path: Path | None = None,
    ):
        """
        Initialize the System 2 unified miner.

        Args:
            llm_adapter: Centralized LLM adapter instance
            provider: LLM provider name
            model: Model identifier
            prompt_path: Optional custom prompt path
        """
        self.llm_adapter = llm_adapter
        self.provider = provider
        self.model = model

        # Load prompt
        if prompt_path is None:
            prompt_path = Path(__file__).parent / "prompts" / "unified_miner.txt"

        if not prompt_path.exists():
            raise FileNotFoundError(f"Unified miner prompt not found: {prompt_path}")

        self.template = prompt_path.read_text()

    def mine_segment(
        self, segment: Segment, job_run_id: str | None = None
    ) -> UnifiedMinerOutput:
        """
        Extract all entity types from a single segment.

        Args:
            segment: Segment to process
            job_run_id: Optional job run ID for tracking

        Returns:
            UnifiedMinerOutput with extracted entities
        """
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
            # Use LLM adapter for centralized call
            response = self.llm_adapter.call_llm(
                provider=self.provider,
                model=self.model,
                prompt=full_prompt,
                job_run_id=job_run_id,
                response_format="json",
                job_type="mining",
                temperature=0.3,  # Lower temperature for more consistent extraction
            )

            # Extract the actual response text
            if "text" in response:
                raw_result = json.loads(response["text"])
            elif "error" in response:
                logger.error(
                    f"LLM error for segment {segment.segment_id}: {response['error']}"
                )
                return UnifiedMinerOutput(
                    {"claims": [], "jargon": [], "people": [], "mental_models": []}
                )
            else:
                raw_result = response

            # Validate and repair if needed
            repaired_result, is_valid, errors = repair_and_validate_miner_output(
                raw_result
            )

            if not is_valid:
                logger.warning(
                    f"Miner output validation failed for segment {segment.segment_id}: {errors}"
                )

            return UnifiedMinerOutput(repaired_result)

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON response for segment {segment.segment_id}: {e}"
            )
            return UnifiedMinerOutput(
                {"claims": [], "jargon": [], "people": [], "mental_models": []}
            )
        except Exception as e:
            logger.error(f"Failed to mine segment {segment.segment_id}: {e}")
            return UnifiedMinerOutput(
                {"claims": [], "jargon": [], "people": [], "mental_models": []}
            )

    def process_segments_batch(
        self,
        segments: list[Segment],
        job_run_id: str | None = None,
        progress_callback=None,
    ) -> list[UnifiedMinerOutput]:
        """
        Process multiple segments using the LLM adapter's batch processing.

        Args:
            segments: List of segments to process
            job_run_id: Optional job run ID for tracking
            progress_callback: Optional progress callback

        Returns:
            List of UnifiedMinerOutput objects
        """

        def process_single(segment):
            return self.mine_segment(segment, job_run_id)

        return self.llm_adapter.process_batch(
            items=segments,
            processor_func=process_single,
            job_type="mining",
            progress_callback=progress_callback,
        )
