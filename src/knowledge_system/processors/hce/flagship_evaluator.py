"""
Flagship Evaluator for ranking and filtering extracted claims.
"""

import json
from pathlib import Path
from typing import Any

from .model_uri_parser import parse_model_uri
from .models.llm_system2 import System2LLM
from .schema_validator import repair_and_validate_flagship_output, validate_flagship_output
from .unified_miner import UnifiedMinerOutput


class EvaluatedClaim:
    """A claim that has been evaluated by the flagship model."""

    def __init__(self, raw_data: dict[str, Any]):
        self.raw = raw_data
        self.original_claim_text = raw_data.get("original_claim_text", "")
        self.decision = raw_data.get("decision", "reject")
        self.rejection_reason = raw_data.get("rejection_reason", "")
        self.refined_claim_text = raw_data.get(
            "refined_claim_text", self.original_claim_text
        )
        self.merge_with = raw_data.get("merge_with", [])
        self.split_into = raw_data.get("split_into", [])
        self.importance = raw_data.get("importance", 1)
        self.novelty = raw_data.get("novelty", 1)
        self.confidence_final = raw_data.get("confidence_final", 1)
        self.reasoning = raw_data.get("reasoning", "")
        self.rank = raw_data.get("rank", 999)

    def is_accepted(self) -> bool:
        """Check if this claim was accepted."""
        return self.decision == "accept"

    def get_final_claim_text(self) -> str:
        """Get the final claim text (refined if available, otherwise original)."""
        return (
            self.refined_claim_text
            if self.refined_claim_text
            else self.original_claim_text
        )


class FlagshipEvaluationOutput:
    """Structured output from the flagship evaluator."""

    def __init__(self, raw_output: dict[str, Any]):
        self.raw = raw_output

        # Parse evaluated claims
        self.evaluated_claims = []
        for claim_data in raw_output.get("evaluated_claims", []):
            self.evaluated_claims.append(EvaluatedClaim(claim_data))

        # Parse summary assessment
        summary = raw_output.get("summary_assessment", {})
        self.total_claims_processed = summary.get("total_claims_processed", 0)
        self.claims_accepted = summary.get("claims_accepted", 0)
        self.claims_rejected = summary.get("claims_rejected", 0)
        self.key_themes = summary.get("key_themes", [])
        self.overall_quality = summary.get("overall_quality", "unknown")
        self.recommendations = summary.get("recommendations", "")

    def get_accepted_claims(self) -> list[EvaluatedClaim]:
        """Get only the claims that were accepted."""
        return [claim for claim in self.evaluated_claims if claim.is_accepted()]

    def get_rejected_claims(self) -> list[EvaluatedClaim]:
        """Get only the claims that were rejected."""
        return [claim for claim in self.evaluated_claims if not claim.is_accepted()]

    def get_claims_by_rank(self) -> list[EvaluatedClaim]:
        """Get accepted claims sorted by rank (1 = most important)."""
        accepted = self.get_accepted_claims()
        return sorted(accepted, key=lambda c: c.rank)

    def is_valid(self) -> bool:
        """Check if the output has the expected structure."""
        return (
            "evaluated_claims" in self.raw
            and "summary_assessment" in self.raw
            and isinstance(self.evaluated_claims, list)
        )


class FlagshipEvaluator:
    """
    Flagship evaluator that reviews extracted claims and ranks them by importance.
    """

    def __init__(self, llm: System2LLM, prompt_path: Path | None = None):
        self.llm = llm

        # Load prompt
        if prompt_path is None:
            prompt_path = Path(__file__).parent / "prompts" / "flagship_evaluator.txt"

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Flagship evaluator prompt not found: {prompt_path}"
            )

        self.template = prompt_path.read_text()

    def evaluate_claims(
        self, content_summary: str, miner_outputs: list[UnifiedMinerOutput]
    ) -> FlagshipEvaluationOutput:
        """
        Evaluate and rank claims from unified miner outputs.

        Args:
            content_summary: High-level summary of the content
            miner_outputs: List of outputs from the unified miner

        Returns:
            FlagshipEvaluationOutput with ranked and filtered claims
        """

        # Collect all claims from miner outputs
        all_claims = []
        for output in miner_outputs:
            all_claims.extend(output.claims)

        if not all_claims:
            # No claims to evaluate
            return FlagshipEvaluationOutput(
                {
                    "evaluated_claims": [],
                    "summary_assessment": {
                        "total_claims_processed": 0,
                        "claims_accepted": 0,
                        "claims_rejected": 0,
                        "key_themes": [],
                        "overall_quality": "no_claims",
                        "recommendations": "No claims were extracted from the content.",
                    },
                }
            )

        # Prepare input for the flagship model
        evaluation_input = {
            "content_summary": content_summary,
            "claims_to_evaluate": all_claims,
            "total_claims": len(all_claims),
        }

        # Create the full prompt
        full_prompt = f"{self.template}\n\nEVALUATION INPUT:\n{json.dumps(evaluation_input, indent=2)}"

        try:
            # Try structured JSON generation first (for Ollama models)
            raw_result = None
            if hasattr(self.llm, "generate_structured_json"):
                try:
                    raw_result = self.llm.generate_structured_json(
                        full_prompt, "flagship_output"
                    )
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.debug(
                        "🔒 Using structured outputs with schema enforcement for flagship evaluator"
                    )
                except Exception as e:
                    import logging

                    # Import error classes from the correct location
                    import sys
                    from pathlib import Path

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

                    logger.warning(
                        f"Structured JSON generation failed, falling back: {e}"
                    )

            # Fall back to regular JSON generation if structured failed or not available
            if raw_result is None:
                raw_result = self.llm.generate_json(full_prompt)

            if not raw_result:
                return self._create_fallback_output(all_claims)

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

            # Repair and validate against schema
            # This will add missing required fields if they're absent
            repaired_result, is_valid, errors = repair_and_validate_flagship_output(result)
            if not is_valid:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Flagship output failed schema validation after repair: {errors}")
                # Use repaired result anyway - it will have the required structure
            
            result = repaired_result

            # Validate and return
            output = FlagshipEvaluationOutput(result)
            if not output.is_valid():
                return self._create_fallback_output(all_claims)

            return output

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Flagship evaluation failed: {e}")

            return self._create_fallback_output(all_claims)

    def _create_fallback_output(
        self, all_claims: list[dict[str, Any]]
    ) -> FlagshipEvaluationOutput:
        """Create a fallback output when flagship evaluation fails."""

        # Accept all claims with basic scoring
        evaluated_claims = []
        for i, claim in enumerate(all_claims):
            evaluated_claims.append(
                {
                    "original_claim_text": claim.get("claim_text", ""),
                    "decision": "accept",
                    "refined_claim_text": claim.get("claim_text", ""),
                    "importance": 5,  # Medium importance
                    "novelty": 5,  # Medium novelty
                    "confidence_final": 5,  # Medium confidence
                    "reasoning": "Fallback evaluation - flagship model unavailable",
                    "rank": i + 1,
                }
            )

        return FlagshipEvaluationOutput(
            {
                "evaluated_claims": evaluated_claims,
                "summary_assessment": {
                    "total_claims_processed": len(all_claims),
                    "claims_accepted": len(all_claims),
                    "claims_rejected": 0,
                    "key_themes": ["fallback_processing"],
                    "overall_quality": "unknown",
                    "recommendations": "Claims were processed with fallback evaluation due to flagship model failure.",
                },
            }
        )


def evaluate_claims_flagship(
    content_summary: str,
    miner_outputs: list[UnifiedMinerOutput],
    flagship_model_uri: str,
) -> FlagshipEvaluationOutput:
    """
    Convenience function for evaluating claims with the flagship model.

    Args:
        content_summary: High-level summary of the content
        miner_outputs: List of outputs from the unified miner
        flagship_model_uri: URI for the flagship LLM model (format: "provider:model")

    Returns:
        FlagshipEvaluationOutput with ranked and filtered claims
    """
    # Parse model URI with proper handling of local:// and other formats
    provider, model = parse_model_uri(flagship_model_uri)

    # Create System2LLM instance
    llm = System2LLM(provider=provider, model=model, temperature=0.3)

    # Use simplified prompt for Ollama models
    if provider and provider.lower() == "ollama":
        prompt_path = (
            Path(__file__).parent / "prompts" / "flagship_evaluator_ollama.txt"
        )
        if not prompt_path.exists():
            # Fall back to main prompt if Ollama version doesn't exist
            prompt_path = Path(__file__).parent / "prompts" / "flagship_evaluator.txt"
    else:
        prompt_path = Path(__file__).parent / "prompts" / "flagship_evaluator.txt"

    evaluator = FlagshipEvaluator(llm, prompt_path)
    return evaluator.evaluate_claims(content_summary, miner_outputs)
