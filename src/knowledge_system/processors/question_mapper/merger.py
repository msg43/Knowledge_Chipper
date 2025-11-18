"""
Question Merger - Deduplicate and link discovered questions with existing ones.

This module compares newly discovered questions against existing questions in the
database to identify duplicates, subsets, and related questions. It provides
recommendations for merging, linking, or keeping questions distinct.
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ...core.llm_adapter import LLMAdapter
from .models import MergeRecommendation, MergeAction

logger = logging.getLogger(__name__)


class QuestionMerger:
    """Merges and deduplicates questions using LLM analysis."""

    def __init__(self, llm_adapter: LLMAdapter):
        """Initialize with LLM adapter.

        Args:
            llm_adapter: Configured LLM adapter for API calls
        """
        self.llm = llm_adapter
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Load the merger prompt template from file."""
        prompt_path = Path(__file__).parent / "prompts" / "merger.txt"
        with open(prompt_path, "r") as f:
            return f.read()

    def analyze_merges(
        self,
        new_questions: list[dict[str, Any]],
        existing_questions: list[dict[str, Any]],
        min_confidence: float = 0.7,
    ) -> list[MergeRecommendation]:
        """Analyze new questions against existing ones for merge opportunities.

        Args:
            new_questions: List of newly discovered question dicts
                Required fields: 'question_text', 'question_type', 'domain'
            existing_questions: List of existing question dicts from database
                Required fields: 'question_id', 'question_text', 'question_type'
            min_confidence: Minimum confidence threshold for recommendations

        Returns:
            List of merge recommendations with confidence >= min_confidence

        Raises:
            ValueError: If question lists are malformed
        """
        if not new_questions:
            logger.info("No new questions to analyze")
            return []

        # If no existing questions, all new questions are KEEP_DISTINCT
        if not existing_questions:
            logger.info("No existing questions - recommending KEEP_DISTINCT for all")
            return [
                MergeRecommendation(
                    new_question_text=q["question_text"],
                    action=MergeAction.KEEP_DISTINCT,
                    target_question_id=None,
                    target_question_text=None,
                    confidence=1.0,
                    rationale="No existing questions in database",
                )
                for q in new_questions
            ]

        # Validate structure
        for q in new_questions:
            if "question_text" not in q:
                raise ValueError(f"New question missing 'question_text': {q}")

        for q in existing_questions:
            if "question_id" not in q or "question_text" not in q:
                raise ValueError(
                    f"Existing question missing required fields: {q}"
                )

        # Filter existing questions by domain/topic for relevance
        # (helps reduce prompt size and improve accuracy)
        filtered_existing = self._filter_by_domain(
            new_questions, existing_questions
        )

        if not filtered_existing:
            logger.info("No domain-relevant existing questions found")
            return [
                MergeRecommendation(
                    new_question_text=q["question_text"],
                    action=MergeAction.KEEP_DISTINCT,
                    target_question_id=None,
                    target_question_text=None,
                    confidence=0.95,
                    rationale="No existing questions in relevant domain/topic",
                )
                for q in new_questions
            ]

        # Format for prompt
        new_json = json.dumps(new_questions, indent=2)
        existing_json = json.dumps(filtered_existing, indent=2)

        # Build prompt
        prompt = self.prompt_template.replace(
            "{new_questions_json}", new_json
        ).replace("{existing_questions_json}", existing_json)

        logger.info(
            f"Analyzing {len(new_questions)} new questions against "
            f"{len(filtered_existing)} existing questions"
        )

        # Call LLM
        try:
            response = self.llm.generate(
                prompt=prompt,
                temperature=0.2,  # Very low temp for consistent merge logic
                max_tokens=4000,
                response_format="json",
            )

            # Parse JSON response
            recommendations_data = json.loads(response)

            # Validate with Pydantic
            recommendations = []
            for rec_data in recommendations_data:
                try:
                    rec = MergeRecommendation(**rec_data)
                    if rec.confidence >= min_confidence:
                        recommendations.append(rec)
                    else:
                        logger.debug(
                            f"Filtered low-confidence recommendation: "
                            f"{rec.new_question_text} (conf={rec.confidence})"
                        )
                except ValidationError as e:
                    logger.warning(f"Invalid recommendation data: {e}")
                    continue

            logger.info(
                f"Generated {len(recommendations)} merge recommendations "
                f"(confidence >= {min_confidence})"
            )

            # Log merge action summary
            action_counts = {}
            for rec in recommendations:
                action_counts[rec.action.value] = (
                    action_counts.get(rec.action.value, 0) + 1
                )
            logger.info(f"Merge action breakdown: {action_counts}")

            return recommendations

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response}")
            return []
        except Exception as e:
            logger.error(f"Merge analysis failed: {e}")
            raise

    def _filter_by_domain(
        self,
        new_questions: list[dict[str, Any]],
        existing_questions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Filter existing questions to those relevant to new questions' domains.

        This reduces prompt size and improves LLM accuracy by only comparing
        questions in related domains/topics.

        Args:
            new_questions: New questions with optional 'domain' field
            existing_questions: Existing questions with optional 'domain' field

        Returns:
            Filtered list of existing questions in relevant domains
        """
        # Extract domains from new questions
        new_domains = {
            q.get("domain", "").lower()
            for q in new_questions
            if q.get("domain")
        }

        # If no domains specified, return all existing questions
        if not new_domains:
            logger.debug("No domains specified - using all existing questions")
            return existing_questions

        # Filter existing questions by domain overlap
        filtered = [
            q
            for q in existing_questions
            if q.get("domain", "").lower() in new_domains
        ]

        # If no domain matches, return all (conservative approach)
        if not filtered:
            logger.debug(
                "No domain matches found - using all existing questions"
            )
            return existing_questions

        logger.debug(
            f"Filtered {len(existing_questions)} existing questions down to "
            f"{len(filtered)} in relevant domains: {new_domains}"
        )

        return filtered
