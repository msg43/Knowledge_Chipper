"""People/person mention evaluator with name merging and ranking."""

import json
import logging
from pathlib import Path
from typing import Any

from ..model_uri_parser import parse_model_uri
from ..models.llm_system2 import System2LLM, create_system2_llm
from ..types import PersonMention

logger = logging.getLogger(__name__)


class EvaluatedPerson:
    """A person that has been evaluated and deduplicated."""

    def __init__(self, raw_data: dict[str, Any]):
        self.raw = raw_data
        self.canonical_name = raw_data.get("canonical_name", "")
        self.name_variants = raw_data.get("name_variants", [])
        self.role = raw_data.get("role", "")
        self.decision = raw_data.get("decision", "reject")
        self.rejection_reason = raw_data.get("reason", "")
        self.importance = raw_data.get("importance", 1)
        self.mention_count = raw_data.get("mention_count", 1)
        self.context = raw_data.get("context", "")
        self.external_ids = raw_data.get("external_ids", {})

    def is_accepted(self) -> bool:
        """Check if this person was accepted."""
        return self.decision == "accept"


class PeopleEvaluationOutput:
    """Output from people evaluation."""

    def __init__(self, raw_output: dict[str, Any]):
        self.raw = raw_output

        # Parse evaluated people
        self.evaluated_people = []
        for person_data in raw_output.get("people", []):
            self.evaluated_people.append(EvaluatedPerson(person_data))

        # Parse summary stats
        stats = raw_output.get("summary_stats", {})
        self.total_mentions_processed = stats.get("total_mentions_processed", 0)
        self.people_accepted = stats.get("people_accepted", 0)
        self.people_rejected = stats.get("people_rejected", 0)
        self.name_variants_merged = stats.get("name_variants_merged", 0)

    def get_accepted_people(self) -> list[EvaluatedPerson]:
        """Get only accepted people."""
        return [p for p in self.evaluated_people if p.is_accepted()]


class PeopleEvaluator:
    """Evaluator for people mentions with name merging and filtering."""

    def __init__(self, llm: System2LLM, prompt_path: Path | None = None):
        self.llm = llm

        # Load prompt
        if prompt_path is None:
            prompt_path = Path(__file__).parent.parent / "prompts" / "people_evaluator.txt"

        if not prompt_path.exists():
            raise FileNotFoundError(f"People evaluator prompt not found: {prompt_path}")

        self.template = prompt_path.read_text()

    def evaluate_people(
        self, content_summary: str, people_mentions: list[dict[str, Any]]
    ) -> PeopleEvaluationOutput:
        """
        Evaluate and deduplicate person mentions.

        Args:
            content_summary: High-level summary of the content
            people_mentions: List of raw person mentions from miner

        Returns:
            PeopleEvaluationOutput with deduplicated, filtered, ranked people
        """

        if not people_mentions:
            return PeopleEvaluationOutput(
                {
                    "people": [],
                    "summary_stats": {
                        "total_mentions_processed": 0,
                        "people_accepted": 0,
                        "people_rejected": 0,
                        "name_variants_merged": 0,
                    },
                }
            )

        # Prepare evaluation input
        evaluation_input = {
            "content_summary": content_summary,
            "people_mentions": people_mentions,
            "total_mentions": len(people_mentions),
        }

        # Create full prompt
        full_prompt = f"""{self.template}

## CONTENT SUMMARY
{content_summary}

## PERSON MENTIONS TO EVALUATE ({len(people_mentions)} total)
{json.dumps(people_mentions, indent=2)}

---

Review these person mentions and output your evaluation in the specified JSON format.
"""

        try:
            # Generate evaluation
            raw_result = self.llm.generate_json(full_prompt)

            if not raw_result:
                logger.warning("People evaluator returned empty result")
                return self._create_fallback_output(people_mentions)

            # Wrap in PeopleEvaluationOutput
            return PeopleEvaluationOutput(raw_result)

        except Exception as e:
            logger.error(f"People evaluation failed: {e}")
            return self._create_fallback_output(people_mentions)

    def _create_fallback_output(
        self, people_mentions: list[dict[str, Any]]
    ) -> PeopleEvaluationOutput:
        """Create fallback output if evaluation fails (accept all as-is)."""
        fallback_people = []
        for mention_data in people_mentions:
            fallback_people.append(
                {
                    "canonical_name": mention_data.get("name", ""),
                    "name_variants": [],
                    "role": mention_data.get("role_or_description", ""),
                    "decision": "accept",
                    "importance": 5,  # Neutral score
                    "mention_count": 1,
                    "context": "Fallback: evaluation failed, accepting as-is",
                }
            )

        return PeopleEvaluationOutput(
            {
                "people": fallback_people,
                "summary_stats": {
                    "total_mentions_processed": len(people_mentions),
                    "people_accepted": len(people_mentions),
                    "people_rejected": 0,
                    "name_variants_merged": 0,
                },
            }
        )


def evaluate_people(
    content_summary: str,
    people_mentions: list[dict[str, Any]],
    evaluator_model_uri: str,
) -> PeopleEvaluationOutput:
    """
    Convenience function for evaluating people mentions.

    Args:
        content_summary: High-level summary of the content
        people_mentions: List of raw person mentions from miner
        evaluator_model_uri: URI for the evaluator LLM model

    Returns:
        PeopleEvaluationOutput with deduplicated, filtered, ranked people
    """
    provider, model = parse_model_uri(evaluator_model_uri)
    llm = create_system2_llm(provider=provider, model=model, temperature=0.3)

    evaluator = PeopleEvaluator(llm)
    return evaluator.evaluate_people(content_summary, people_mentions)
