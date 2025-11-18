"""
Question Discovery - Extract questions from claims using LLM analysis.

This module analyzes a batch of claims and identifies the key questions they answer.
It uses an LLM to discover questions organically from the content, without bias
toward existing question structures.
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ...core.llm_adapter import LLMAdapter
from .models import DiscoveredQuestion

logger = logging.getLogger(__name__)


class QuestionDiscovery:
    """Discovers questions from claims using LLM analysis."""

    def __init__(self, llm_adapter: LLMAdapter):
        """Initialize with LLM adapter.

        Args:
            llm_adapter: Configured LLM adapter for API calls
        """
        self.llm = llm_adapter
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Load the discovery prompt template from file."""
        prompt_path = Path(__file__).parent / "prompts" / "discovery.txt"
        with open(prompt_path, "r") as f:
            return f.read()

    def discover_questions(
        self,
        claims: list[dict[str, Any]],
        min_confidence: float = 0.6,
    ) -> list[DiscoveredQuestion]:
        """Discover questions from a batch of claims.

        Args:
            claims: List of claim dicts with at least 'claim_id' and 'claim_text'
            min_confidence: Minimum confidence threshold for questions (default: 0.6)

        Returns:
            List of discovered questions with confidence >= min_confidence

        Raises:
            ValueError: If claims list is empty or malformed
        """
        if not claims:
            raise ValueError("Cannot discover questions from empty claims list")

        # Validate claims structure
        for claim in claims:
            if "claim_id" not in claim or "claim_text" not in claim:
                raise ValueError(
                    f"Claim missing required fields: {claim.keys()}. "
                    "Need 'claim_id' and 'claim_text'"
                )

        # Format claims for prompt
        claims_json = json.dumps(claims, indent=2)

        # Build prompt
        prompt = self.prompt_template.replace("{claims_json}", claims_json)

        logger.info(f"Discovering questions from {len(claims)} claims")

        # Call LLM
        try:
            response = self.llm.generate(
                prompt=prompt,
                temperature=0.3,  # Lower temp for more consistent question discovery
                max_tokens=4000,
                response_format="json",
            )

            # Parse JSON response
            questions_data = json.loads(response)

            # Validate with Pydantic
            discovered = []
            for q_data in questions_data:
                try:
                    question = DiscoveredQuestion(**q_data)
                    if question.confidence >= min_confidence:
                        discovered.append(question)
                    else:
                        logger.debug(
                            f"Filtered low-confidence question: "
                            f"{question.question_text} (conf={question.confidence})"
                        )
                except ValidationError as e:
                    logger.warning(f"Invalid question data: {e}")
                    continue

            logger.info(
                f"Discovered {len(discovered)} questions "
                f"(confidence >= {min_confidence})"
            )

            return discovered

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response}")
            return []
        except Exception as e:
            logger.error(f"Question discovery failed: {e}")
            raise

    def discover_questions_batched(
        self,
        claims: list[dict[str, Any]],
        batch_size: int = 50,
        min_confidence: float = 0.6,
    ) -> list[DiscoveredQuestion]:
        """Discover questions from large claim sets using batching.

        Args:
            claims: List of claim dicts
            batch_size: Number of claims per LLM call (default: 50)
            min_confidence: Minimum confidence threshold

        Returns:
            Combined list of discovered questions from all batches
        """
        if len(claims) <= batch_size:
            return self.discover_questions(claims, min_confidence)

        logger.info(
            f"Processing {len(claims)} claims in batches of {batch_size}"
        )

        all_questions = []
        for i in range(0, len(claims), batch_size):
            batch = claims[i : i + batch_size]
            logger.debug(f"Processing batch {i // batch_size + 1}")

            batch_questions = self.discover_questions(batch, min_confidence)
            all_questions.extend(batch_questions)

        logger.info(f"Total questions discovered: {len(all_questions)}")
        return all_questions
