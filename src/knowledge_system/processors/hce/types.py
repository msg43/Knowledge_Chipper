from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ClaimType = Literal["factual", "causal", "normative", "forecast", "definition"]
RelationType = Literal["supports", "contradicts", "depends_on", "refines"]
ContextType = Literal["exact", "extended", "segment"]
TemporalityScore = Literal[
    1, 2, 3, 4, 5
]  # 1=Immediate, 2=Short-term, 3=Medium-term, 4=Long-term, 5=Timeless
TemporalityType = Literal[
    "timeless", "timely", "dated", "uncertain"
]  # Temporal classification categories


class EvidenceSpan(BaseModel):
    # Core precise quote (existing)
    t0: str  # Exact start of quote
    t1: str  # Exact end of quote
    quote: str  # Precise verbatim quote
    segment_id: str | None = None

    # Extended context (new)
    context_t0: str | None = None  # Extended window start
    context_t1: str | None = None  # Extended window end
    context_text: str | None = None  # 30-60 second context around quote

    # Metadata
    context_type: ContextType = "exact"


class Segment(BaseModel):
    source_id: str
    segment_id: str
    speaker: str
    t0: str
    t1: str
    text: str
    topic_guess: str | None = None


class Milestone(BaseModel):
    milestone_id: str
    t0: str
    t1: str
    summary: str


class CandidateClaim(BaseModel):
    source_id: str
    segment_id: str
    candidate_id: str
    speaker: str | None = None
    claim_text: str
    claim_type: ClaimType
    stance: Literal["asserts", "supports", "disputes", "neutral"] = "asserts"
    evidence_spans: list[EvidenceSpan] = []
    confidence_local: float = Field(ge=0, le=1, default=0.5)


class ConsolidatedClaim(BaseModel):
    source_id: str
    claim_id: str
    consolidated: str
    claim_type: ClaimType
    speaker: str | None = None
    first_mention_ts: str | None = None
    evidence: list[EvidenceSpan]
    cluster_ids: list[str] = []


class ScoredClaim(BaseModel):
    source_id: str
    claim_id: str
    canonical: str
    claim_type: ClaimType
    evidence: list[EvidenceSpan]
    tier: Literal["A", "B", "C"] | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    temporality_score: TemporalityScore = 3  # Default to medium-term
    temporality_confidence: float = Field(ge=0, le=1, default=0.5)
    temporality_rationale: str | None = None

    # Structured categories (copied from episode-level analysis)
    structured_categories: list[str] = []  # Category names this claim contributes to
    category_relevance_scores: dict[str, float] = Field(
        default_factory=dict
    )  # How much this claim supports each category


class Relation(BaseModel):
    source_id: str
    source_claim_id: str
    target_claim_id: str
    type: RelationType
    strength: float = Field(ge=0, le=1, default=0.5)
    rationale: str | None = None


class PersonMention(BaseModel):
    source_id: str
    mention_id: str
    span_segment_id: str
    t0: str
    t1: str
    surface: str
    normalized: str | None = None
    entity_type: Literal["person", "org"] = "person"
    external_ids: dict[str, str] = {}
    confidence: float = 0.5


class MentalModel(BaseModel):
    source_id: str
    model_id: str
    name: str
    definition: str | None = None
    first_mention_ts: str | None = None
    evidence_spans: list[EvidenceSpan] = []
    aliases: list[str] = []


class JargonTerm(BaseModel):
    source_id: str
    term_id: str
    term: str
    category: str | None = None
    definition: str | None = None
    evidence_spans: list[EvidenceSpan] = []


class StructuredCategory(BaseModel):
    """Represents a Wikidata-style structured category coverage for an episode."""

    category_id: str
    category_name: str
    wikidata_qid: str | None = None
    coverage_confidence: float = Field(ge=0, le=1, default=0.5)
    supporting_evidence: list[str] = []  # Claim IDs that support this categorization
    frequency_score: float = Field(
        ge=0, le=1, default=0.0
    )  # How often this category appears


class EpisodeBundle(BaseModel):
    source_id: str
    segments: list[Segment]
    milestones: list[Milestone] | None = None

    # Source metadata (for evaluator and summary generation context)
    # NOT used by miner (which extracts atomic claims from segments)
    # Used by: evaluator (contextual ranking), long_summary (informed synthesis)
    video_metadata: dict[str, Any] | None = None


class PipelineOutputs(BaseModel):
    source_id: str
    claims: list[ScoredClaim]
    relations: list[Relation] = []
    milestones: list[Milestone] = []
    people: list[PersonMention] = []
    concepts: list[MentalModel] = []
    jargon: list[JargonTerm] = []
    structured_categories: list[StructuredCategory] = []

    # Summary fields (new)
    short_summary: str | None = None  # Pre-mining overview (1-2 paragraphs)
    long_summary: str | None = (
        None  # Post-evaluation comprehensive analysis (3-5 paragraphs)
    )
