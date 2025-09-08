"""Temporality Analysis for Claims.

This module analyzes claims to determine whether they are:
- Timeless: Universal truths, principles, or facts that remain valid indefinitely
- Timely: Claims tied to specific current events or short-term predictions
- Dated: Claims with explicit temporal boundaries or expiration dates
- Uncertain: Claims where temporality cannot be reliably determined
"""

import logging
from pathlib import Path

from .models.llm_any import AnyLLM
from .types import ScoredClaim, TemporalityScore, TemporalityType

logger = logging.getLogger(__name__)


class TemporalityAnalyzer:
    """Analyzes claims for temporal characteristics using LLM reasoning."""

    def __init__(self, llm: AnyLLM, prompt_path: Path):
        """Initialize the temporality analyzer."""
        self.llm = llm
        self.template = prompt_path.read_text()

    def analyze_claim_temporality(
        self, claim: ScoredClaim
    ) -> tuple[TemporalityScore, float, str]:
        """Analyze a single claim for its temporal characteristics.

        Args:
            claim: The claim to analyze

        Returns:
            tuple of (temporality_score, confidence, rationale)
        """
        try:
            # Prepare prompt with claim text and evidence
            evidence_text = "\n".join(
                [ev.quote for ev in claim.evidence[:3]]
            )  # Limit to first 3 pieces of evidence

            prompt_text = self.template.format(
                claim_text=claim.canonical,
                claim_type=claim.claim_type,
                evidence_text=evidence_text,
            )

            # Get LLM analysis
            result = self.llm.generate_json(prompt_text)

            if result and isinstance(result, list) and len(result) > 0:
                analysis = result[0]

                temporality_score = analysis.get("temporality_score", 3)
                confidence = min(
                    max(analysis.get("confidence", 0.5), 0.0), 1.0
                )  # Clamp between 0-1
                rationale = analysis.get("rationale", "Unable to determine temporality")

                # Validate temporality score
                if temporality_score not in [1, 2, 3, 4, 5]:
                    temporality_score = 3  # Default to medium-term
                    confidence = 0.3
                    rationale = (
                        f"Invalid temporality score returned: {temporality_score}"
                    )

                return temporality_score, confidence, rationale
            else:
                return 3, 0.3, "LLM returned no valid analysis"

        except Exception as e:
            logger.warning(f"Failed to analyze claim temporality: {e}")
            return 3, 0.1, f"Analysis failed: {str(e)}"

    def analyze_claims_batch(self, claims: list[ScoredClaim]) -> list[ScoredClaim]:
        """Analyze temporality for a batch of claims.

        Args:
            claims: List of claims to analyze

        Returns:
            List of claims with temporality fields populated
        """
        for claim in claims:
            temporality_score, confidence, rationale = self.analyze_claim_temporality(
                claim
            )

            # Update claim with temporality analysis
            claim.temporality_score = temporality_score
            claim.temporality_confidence = confidence
            claim.temporality_rationale = rationale

            logger.debug(
                f"Claim '{claim.canonical[:50]}...' classified as {temporality_score} (confidence: {confidence:.2f})"
            )

        return claims


def analyze_temporality(claims: list[ScoredClaim], model_uri: str) -> list[ScoredClaim]:
    """Analyze temporality for all claims in a list.

    Args:
        claims: List of claims to analyze
        model_uri: URI for the LLM model to use

    Returns:
        List of claims with temporality populated
    """

    # Currently disabled - return claims unchanged until prompt template is created
    # TODO: Create temporality analysis prompt template
    logger.info("Temporality analysis disabled - no prompt template available")
    return claims

    # Future implementation:
    # settings = get_settings()
    # prompt_path = settings.prompts_dir / "temporality.txt"
    #
    # if not prompt_path.exists():
    #     logger.warning("Temporality prompt template not found, skipping analysis")
    #     return claims
    #
    # llm = AnyLLM(model_uri)
    # analyzer = TemporalityAnalyzer(llm, prompt_path)
    # return analyzer.analyze_claims_batch(claims)


# Utility functions for temporality classification


def is_timeless_claim(claim_text: str) -> bool:
    """Quick heuristic to identify potentially timeless claims."""
    timeless_indicators = [
        "always",
        "never",
        "fundamental",
        "principle",
        "law o",
        "theorem",
        "mathematical",
        "physical law",
        "human nature",
        "universal",
        "eternal",
        "inherent",
        "intrinsic",
        "by definition",
        "axiom",
    ]

    claim_lower = claim_text.lower()
    return any(indicator in claim_lower for indicator in timeless_indicators)


def is_timely_claim(claim_text: str) -> bool:
    """Quick heuristic to identify potentially timely claims."""
    timely_indicators = [
        "next week",
        "this month",
        "current",
        "recent",
        "trending",
        "now",
        "today",
        "tomorrow",
        "this year",
        "breaking",
        "latest",
        "ongoing",
        "immediate",
        "short-term",
        "temporary",
        "will win",
        "will lose",
    ]

    claim_lower = claim_text.lower()
    return any(indicator in claim_lower for indicator in timely_indicators)


def estimate_claim_half_life(temporality: TemporalityType, claim_text: str) -> str:
    """Estimate how long a claim will remain relevant.

    Args:
        temporality: The temporal classification
        claim_text: The claim text for additional context

    Returns:
        Human-readable half-life estimate
    """
    if temporality == "timeless":
        return "Indefinite (universal truth)"
    elif temporality == "timely":
        if any(
            term in claim_text.lower() for term in ["next week", "tomorrow", "today"]
        ):
            return "Days to weeks"
        elif any(term in claim_text.lower() for term in ["this month", "current"]):
            return "Weeks to months"
        else:
            return "Months to a year"
    elif temporality == "dated":
        return "Until specified date/event"
    else:
        return "Unknown"
