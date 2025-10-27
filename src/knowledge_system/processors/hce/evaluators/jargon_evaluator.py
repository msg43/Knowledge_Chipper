"""Jargon term evaluator with deduplication and ranking."""

import json
import logging
from pathlib import Path
from typing import Any

from ..model_uri_parser import parse_model_uri
from ..models.llm_system2 import System2LLM, create_system2_llm
from ..types import EvidenceSpan, JargonTerm

logger = logging.getLogger(__name__)


class EvaluatedJargon:
    """A jargon term that has been evaluated and deduplicated."""

    def __init__(self, raw_data: dict[str, Any]):
        self.raw = raw_data
        self.canonical_term = raw_data.get("canonical_term", "")
        self.aliases = raw_data.get("aliases", [])
        self.definition = raw_data.get("definition", "")
        self.decision = raw_data.get("decision", "reject")
        self.rejection_reason = raw_data.get("reason", "")
        self.importance = raw_data.get("importance", 1)
        self.usage_count = raw_data.get("usage_count", 1)
        self.category = raw_data.get("category", "")
        self.reasoning = raw_data.get("reasoning", "")

    def is_accepted(self) -> bool:
        """Check if this jargon term was accepted."""
        return self.decision == "accept"


class JargonEvaluationOutput:
    """Output from jargon evaluation."""

    def __init__(self, raw_output: dict[str, Any]):
        self.raw = raw_output

        # Parse evaluated jargon
        self.evaluated_jargon = []
        for jargon_data in raw_output.get("jargon", []):
            self.evaluated_jargon.append(EvaluatedJargon(jargon_data))

        # Parse summary stats
        stats = raw_output.get("summary_stats", {})
        self.total_terms_processed = stats.get("total_terms_processed", 0)
        self.terms_accepted = stats.get("terms_accepted", 0)
        self.terms_rejected = stats.get("terms_rejected", 0)
        self.duplicates_merged = stats.get("duplicates_merged", 0)

    def get_accepted_jargon(self) -> list[EvaluatedJargon]:
        """Get only accepted jargon terms."""
        return [j for j in self.evaluated_jargon if j.is_accepted()]


class JargonEvaluator:
    """Evaluator for jargon terms with deduplication and filtering."""

    def __init__(self, llm: System2LLM, prompt_path: Path | None = None):
        self.llm = llm

        # Load prompt
        if prompt_path is None:
            prompt_path = (
                Path(__file__).parent.parent / "prompts" / "jargon_evaluator.txt"
            )

        if not prompt_path.exists():
            raise FileNotFoundError(f"Jargon evaluator prompt not found: {prompt_path}")

        self.template = prompt_path.read_text()

    def evaluate_jargon(
        self, content_summary: str, jargon_terms: list[dict[str, Any]]
    ) -> JargonEvaluationOutput:
        """
        Evaluate and deduplicate jargon terms.

        Args:
            content_summary: High-level summary of the content
            jargon_terms: List of raw jargon terms from miner

        Returns:
            JargonEvaluationOutput with deduplicated, filtered, ranked terms
        """

        if not jargon_terms:
            return JargonEvaluationOutput(
                {
                    "jargon": [],
                    "summary_stats": {
                        "total_terms_processed": 0,
                        "terms_accepted": 0,
                        "terms_rejected": 0,
                        "duplicates_merged": 0,
                    },
                }
            )

        # Prepare evaluation input
        evaluation_input = {
            "content_summary": content_summary,
            "jargon_terms": jargon_terms,
            "total_terms": len(jargon_terms),
        }

        # Create full prompt
        full_prompt = f"""{self.template}

## CONTENT SUMMARY
{content_summary}

## JARGON TERMS TO EVALUATE ({len(jargon_terms)} total)
{json.dumps(jargon_terms, indent=2)}

---

Review these jargon terms and output your evaluation in the specified JSON format.
"""

        try:
            # Generate evaluation
            raw_result = self.llm.generate_json(full_prompt)

            if not raw_result:
                logger.warning("Jargon evaluator returned empty result")
                return self._create_fallback_output(jargon_terms)

            # Wrap in JargonEvaluationOutput
            return JargonEvaluationOutput(raw_result)

        except Exception as e:
            logger.error(f"Jargon evaluation failed: {e}")
            return self._create_fallback_output(jargon_terms)

    def _create_fallback_output(
        self, jargon_terms: list[dict[str, Any]]
    ) -> JargonEvaluationOutput:
        """Create fallback output if evaluation fails (accept all as-is)."""
        fallback_jargon = []
        for term_data in jargon_terms:
            fallback_jargon.append(
                {
                    "canonical_term": term_data.get("term", ""),
                    "aliases": [],
                    "definition": term_data.get("definition", ""),
                    "decision": "accept",
                    "importance": 5,  # Neutral score
                    "usage_count": 1,
                    "reasoning": "Fallback: evaluation failed, accepting as-is",
                }
            )

        return JargonEvaluationOutput(
            {
                "jargon": fallback_jargon,
                "summary_stats": {
                    "total_terms_processed": len(jargon_terms),
                    "terms_accepted": len(jargon_terms),
                    "terms_rejected": 0,
                    "duplicates_merged": 0,
                },
            }
        )


def evaluate_jargon(
    content_summary: str,
    jargon_terms: list[dict[str, Any]],
    evaluator_model_uri: str,
) -> JargonEvaluationOutput:
    """
    Convenience function for evaluating jargon terms.

    Args:
        content_summary: High-level summary of the content
        jargon_terms: List of raw jargon terms from miner
        evaluator_model_uri: URI for the evaluator LLM model

    Returns:
        JargonEvaluationOutput with deduplicated, filtered, ranked terms
    """
    provider, model = parse_model_uri(evaluator_model_uri)
    llm = create_system2_llm(provider=provider, model=model, temperature=0.3)

    evaluator = JargonEvaluator(llm)
    return evaluator.evaluate_jargon(content_summary, jargon_terms)
