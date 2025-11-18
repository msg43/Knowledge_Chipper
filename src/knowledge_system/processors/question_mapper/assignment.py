"""
Claim Assignment - Map claims to questions with relation types.

This module assigns claims to finalized questions, determining how each claim
relates to each question (answers, supports, contradicts, etc.). Claims can be
assigned to multiple questions with different relation types.
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ...core.llm_adapter import LLMAdapter
from .models import ClaimQuestionMapping

logger = logging.getLogger(__name__)


class ClaimAssignment:
    """Assigns claims to questions with relation types using LLM analysis."""

    def __init__(self, llm_adapter: LLMAdapter):
        """Initialize with LLM adapter.

        Args:
            llm_adapter: Configured LLM adapter for API calls
        """
        self.llm = llm_adapter
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Load the assignment prompt template from file."""
        prompt_path = Path(__file__).parent / "prompts" / "assignment.txt"
        with open(prompt_path, "r") as f:
            return f.read()

    def assign_claims(
        self,
        claims: list[dict[str, Any]],
        questions: list[dict[str, Any]],
        min_relevance: float = 0.5,
    ) -> list[ClaimQuestionMapping]:
        """Assign claims to questions with relation types.

        Args:
            claims: List of claim dicts with at least 'claim_id' and 'claim_text'
            questions: List of finalized question dicts with 'question_id' and 'question_text'
            min_relevance: Minimum relevance score for assignments (default: 0.5)

        Returns:
            List of claim-question mappings with relevance >= min_relevance

        Raises:
            ValueError: If claims or questions are empty/malformed
        """
        if not claims:
            raise ValueError("Cannot assign from empty claims list")

        if not questions:
            logger.info("No questions to assign claims to")
            return []

        # Validate structure
        for claim in claims:
            if "claim_id" not in claim or "claim_text" not in claim:
                raise ValueError(
                    f"Claim missing required fields: {claim.keys()}. "
                    "Need 'claim_id' and 'claim_text'"
                )

        for q in questions:
            if "question_id" not in q or "question_text" not in q:
                raise ValueError(
                    f"Question missing required fields: {q.keys()}. "
                    "Need 'question_id' and 'question_text'"
                )

        # Format for prompt
        claims_json = json.dumps(claims, indent=2)
        questions_json = json.dumps(questions, indent=2)

        # Build prompt
        prompt = self.prompt_template.replace(
            "{claims_json}", claims_json
        ).replace("{questions_json}", questions_json)

        logger.info(
            f"Assigning {len(claims)} claims to {len(questions)} questions"
        )

        # Call LLM
        try:
            response = self.llm.generate(
                prompt=prompt,
                temperature=0.2,  # Low temp for consistent assignment logic
                max_tokens=6000,  # Higher limit for many-to-many mappings
                response_format="json",
            )

            # Parse JSON response
            mappings_data = json.loads(response)

            # Validate with Pydantic
            mappings = []
            for m_data in mappings_data:
                try:
                    mapping = ClaimQuestionMapping(**m_data)
                    if mapping.relevance_score >= min_relevance:
                        mappings.append(mapping)
                    else:
                        logger.debug(
                            f"Filtered low-relevance mapping: "
                            f"{mapping.claim_id} -> {mapping.question_id} "
                            f"(relevance={mapping.relevance_score})"
                        )
                except ValidationError as e:
                    logger.warning(f"Invalid mapping data: {e}")
                    continue

            logger.info(
                f"Created {len(mappings)} claim-question mappings "
                f"(relevance >= {min_relevance})"
            )

            # Log relation type summary
            relation_counts = {}
            for m in mappings:
                relation_counts[m.relation_type.value] = (
                    relation_counts.get(m.relation_type.value, 0) + 1
                )
            logger.info(f"Relation type breakdown: {relation_counts}")

            return mappings

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response}")
            return []
        except Exception as e:
            logger.error(f"Claim assignment failed: {e}")
            raise

    def assign_claims_batched(
        self,
        claims: list[dict[str, Any]],
        questions: list[dict[str, Any]],
        claims_per_batch: int = 30,
        min_relevance: float = 0.5,
    ) -> list[ClaimQuestionMapping]:
        """Assign claims to questions using batching for large claim sets.

        Args:
            claims: List of claim dicts
            questions: List of question dicts (not batched - all included each time)
            claims_per_batch: Number of claims per LLM call (default: 30)
            min_relevance: Minimum relevance score

        Returns:
            Combined list of mappings from all batches
        """
        if len(claims) <= claims_per_batch:
            return self.assign_claims(claims, questions, min_relevance)

        logger.info(
            f"Processing {len(claims)} claims in batches of {claims_per_batch}"
        )

        all_mappings = []
        for i in range(0, len(claims), claims_per_batch):
            batch = claims[i : i + claims_per_batch]
            logger.debug(
                f"Processing batch {i // claims_per_batch + 1} "
                f"({len(batch)} claims)"
            )

            batch_mappings = self.assign_claims(batch, questions, min_relevance)
            all_mappings.extend(batch_mappings)

        logger.info(f"Total mappings created: {len(all_mappings)}")
        return all_mappings
