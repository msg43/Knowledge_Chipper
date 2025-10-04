"""
Pydantic models for structured outputs that match existing JSON schemas.
These models are used for schema enforcement with Ollama's structured outputs feature.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceSpan(BaseModel):
    """Evidence span with quote and timestamps."""

    quote: str = Field(description="Verbatim text supporting the claim")
    t0: str = Field(description="Start timestamp")
    t1: str = Field(description="End timestamp")


class Claim(BaseModel):
    """Individual claim extracted from content."""

    claim_text: str = Field(
        description="The exact claim being made (precise and concise)"
    )
    claim_type: str = Field(description="Type of claim")
    stance: str = Field(description="How the speaker presents the claim")
    evidence_spans: list[EvidenceSpan] = Field(
        description="Supporting quotes with timestamps"
    )


class Jargon(BaseModel):
    """Technical term or domain-specific language."""

    term: str = Field(description="The jargon term or phrase")
    definition: str = Field(description="Explanation of the term in context")
    context_quote: str = Field(description="Quote showing how the term is used")
    timestamp: str = Field(description="When the term appears")


class Person(BaseModel):
    """Person mentioned in the content."""

    name: str = Field(description="Person's name as mentioned")
    role_or_description: str = Field(description="How they're described or their role")
    context_quote: str = Field(description="Quote mentioning the person")
    timestamp: str = Field(description="When they're mentioned")


class MentalModel(BaseModel):
    """Conceptual framework, model, or way of thinking."""

    name: str = Field(description="Name or title of the mental model")
    description: str = Field(description="Explanation of the mental model or framework")
    context_quote: str = Field(description="Quote illustrating the mental model")
    timestamp: str = Field(description="When it's discussed")


class UnifiedMinerOutput(BaseModel):
    """Unified miner output matching the JSON schema."""

    claims: list[Claim] = Field(description="Extracted claims from the content")
    jargon: list[Jargon] = Field(
        description="Technical terms and domain-specific language"
    )
    people: list[Person] = Field(description="People mentioned in the content")
    mental_models: list[MentalModel] = Field(
        description="Conceptual frameworks, models, or ways of thinking"
    )


class EvaluatedClaim(BaseModel):
    """Claim after flagship evaluation and ranking."""

    original_claim_text: str = Field(description="Original claim text from miner")
    decision: str = Field(description="What to do with this claim")
    rejection_reason: str | None = Field(
        description="Why claim was rejected (if decision=reject)", default=None
    )
    refined_claim_text: str | None = Field(
        description="Improved/refined version of claim (if different from original)",
        default=None,
    )
    merge_with: list[str] | None = Field(
        description="Other claims to merge with (if decision=merge)", default=None
    )
    split_into: list[str] | None = Field(
        description="Multiple claims to split into (if decision=split)", default=None
    )
    importance: int = Field(
        description="How important/significant this claim is (1-10 scale)", ge=1, le=10
    )
    novelty: int = Field(
        description="How novel or surprising this claim is (1-10 scale)", ge=1, le=10
    )
    confidence_final: int = Field(
        description="Overall confidence in this claim (1-10 scale)", ge=1, le=10
    )
    reasoning: str = Field(description="Explanation of the evaluation and scoring")
    rank: int = Field(description="Final importance ranking (1 = most important)", ge=1)


class SummaryAssessment(BaseModel):
    """Overall assessment of the content and extracted claims."""

    total_claims_processed: int = Field(description="Number of claims evaluated")
    claims_accepted: int = Field(description="Number of claims accepted")
    claims_rejected: int = Field(description="Number of claims rejected")
    key_themes: list[str] = Field(description="Main themes or topics identified")
    overall_quality: str = Field(description="Overall quality of the extracted claims")
    recommendations: str | None = Field(
        description="Suggestions for improving claim extraction or content analysis",
        default=None,
    )


class FlagshipEvaluationOutput(BaseModel):
    """Flagship evaluation output matching the JSON schema."""

    evaluated_claims: list[EvaluatedClaim] = Field(
        description="Claims after flagship evaluation and ranking"
    )
    summary_assessment: SummaryAssessment = Field(
        description="Overall assessment of the content and extracted claims"
    )


# Registry of available Pydantic models for schema enforcement
PYDANTIC_MODELS = {
    "miner_output": UnifiedMinerOutput,
    "flagship_output": FlagshipEvaluationOutput,
}


def get_pydantic_model(schema_name: str) -> type[BaseModel]:
    """Get Pydantic model by schema name."""
    if schema_name not in PYDANTIC_MODELS:
        raise ValueError(
            f"Unknown schema: {schema_name}. Available: {list(PYDANTIC_MODELS.keys())}"
        )
    return PYDANTIC_MODELS[schema_name]


def get_schema_json(schema_name: str) -> dict[str, Any]:
    """Get JSON schema for a Pydantic model."""
    model_class = get_pydantic_model(schema_name)
    return model_class.model_json_schema()
