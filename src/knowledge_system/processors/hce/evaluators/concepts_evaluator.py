"""Mental models/concepts evaluator with framework deduplication and ranking."""

import json
import logging
from pathlib import Path
from typing import Any

from ..model_uri_parser import parse_model_uri
from ..models.llm_system2 import System2LLM, create_system2_llm
from ..types import MentalModel

logger = logging.getLogger(__name__)


class EvaluatedConcept:
    """A mental model/concept that has been evaluated and deduplicated."""

    def __init__(self, raw_data: dict[str, Any]):
        self.raw = raw_data
        self.canonical_name = raw_data.get("canonical_name", "")
        self.description = raw_data.get("description", "")
        self.decision = raw_data.get("decision", "reject")
        self.rejection_reason = raw_data.get("reason", "")
        self.importance = raw_data.get("importance", 1)
        self.analytical_depth = raw_data.get("analytical_depth", "low")
        self.usage_count = raw_data.get("usage_count", 1)
        self.application_context = raw_data.get("application_context", "")
        self.external_ids = raw_data.get("external_ids", {})

    def is_accepted(self) -> bool:
        """Check if this concept was accepted."""
        return self.decision == "accept"


class ConceptsEvaluationOutput:
    """Output from concepts evaluation."""

    def __init__(self, raw_output: dict[str, Any]):
        self.raw = raw_output

        # Parse evaluated concepts
        self.evaluated_concepts = []
        for concept_data in raw_output.get("concepts", []):
            self.evaluated_concepts.append(EvaluatedConcept(concept_data))

        # Parse summary stats
        stats = raw_output.get("summary_stats", {})
        self.total_concepts_processed = stats.get("total_concepts_processed", 0)
        self.concepts_accepted = stats.get("concepts_accepted", 0)
        self.concepts_rejected = stats.get("concepts_rejected", 0)
        self.frameworks_merged = stats.get("frameworks_merged", 0)

    def get_accepted_concepts(self) -> list[EvaluatedConcept]:
        """Get only accepted concepts."""
        return [c for c in self.evaluated_concepts if c.is_accepted()]


class ConceptsEvaluator:
    """Evaluator for mental models/concepts with framework deduplication."""

    def __init__(self, llm: System2LLM, prompt_path: Path | None = None):
        self.llm = llm

        # Load prompt
        if prompt_path is None:
            prompt_path = (
                Path(__file__).parent.parent / "prompts" / "concepts_evaluator.txt"
            )

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Concepts evaluator prompt not found: {prompt_path}"
            )

        self.template = prompt_path.read_text()

    def evaluate_concepts(
        self, content_summary: str, mental_models: list[dict[str, Any]]
    ) -> ConceptsEvaluationOutput:
        """
        Evaluate and deduplicate mental models/concepts.

        Args:
            content_summary: High-level summary of the content
            mental_models: List of raw mental models from miner

        Returns:
            ConceptsEvaluationOutput with deduplicated, filtered, ranked concepts
        """

        if not mental_models:
            return ConceptsEvaluationOutput(
                {
                    "concepts": [],
                    "summary_stats": {
                        "total_concepts_processed": 0,
                        "concepts_accepted": 0,
                        "concepts_rejected": 0,
                        "frameworks_merged": 0,
                    },
                }
            )

        # Prepare evaluation input
        evaluation_input = {
            "content_summary": content_summary,
            "mental_models": mental_models,
            "total_concepts": len(mental_models),
        }

        # Create full prompt
        full_prompt = f"""{self.template}

## CONTENT SUMMARY
{content_summary}

## MENTAL MODELS/CONCEPTS TO EVALUATE ({len(mental_models)} total)
{json.dumps(mental_models, indent=2)}

---

Review these mental models/concepts and output your evaluation in the specified JSON format.
"""

        try:
            # Generate evaluation
            raw_result = self.llm.generate_json(full_prompt)

            if not raw_result:
                logger.warning("Concepts evaluator returned empty result")
                return self._create_fallback_output(mental_models)

            # Wrap in ConceptsEvaluationOutput
            return ConceptsEvaluationOutput(raw_result)

        except Exception as e:
            logger.error(f"Concepts evaluation failed: {e}")
            return self._create_fallback_output(mental_models)

    def _create_fallback_output(
        self, mental_models: list[dict[str, Any]]
    ) -> ConceptsEvaluationOutput:
        """Create fallback output if evaluation fails (accept all as-is)."""
        fallback_concepts = []
        for model_data in mental_models:
            fallback_concepts.append(
                {
                    "canonical_name": model_data.get("name", ""),
                    "description": model_data.get("description", ""),
                    "decision": "accept",
                    "importance": 5,  # Neutral score
                    "analytical_depth": "medium",
                    "usage_count": 1,
                    "application_context": "Fallback: evaluation failed, accepting as-is",
                }
            )

        return ConceptsEvaluationOutput(
            {
                "concepts": fallback_concepts,
                "summary_stats": {
                    "total_concepts_processed": len(mental_models),
                    "concepts_accepted": len(mental_models),
                    "concepts_rejected": 0,
                    "frameworks_merged": 0,
                },
            }
        )


def evaluate_concepts(
    content_summary: str,
    mental_models: list[dict[str, Any]],
    evaluator_model_uri: str,
) -> ConceptsEvaluationOutput:
    """
    Convenience function for evaluating mental models/concepts.

    Args:
        content_summary: High-level summary of the content
        mental_models: List of raw mental models from miner
        evaluator_model_uri: URI for the evaluator LLM model

    Returns:
        ConceptsEvaluationOutput with deduplicated, filtered, ranked concepts
    """
    provider, model = parse_model_uri(evaluator_model_uri)
    llm = create_system2_llm(provider=provider, model=model, temperature=0.3)

    evaluator = ConceptsEvaluator(llm)
    return evaluator.evaluate_concepts(content_summary, mental_models)
