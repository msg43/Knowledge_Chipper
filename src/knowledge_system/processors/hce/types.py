from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ClaimType = Literal["factual", "causal", "normative", "forecast", "definition"]
RelationType = Literal["supports", "contradicts", "depends_on", "refines"]


class EvidenceSpan(BaseModel):
    t0: str
    t1: str
    quote: str
    segment_id: str | None = None


class Segment(BaseModel):
    episode_id: str
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
    episode_id: str
    segment_id: str
    candidate_id: str
    speaker: str | None = None
    claim_text: str
    claim_type: ClaimType
    stance: Literal["asserts", "supports", "disputes", "neutral"] = "asserts"
    evidence_spans: list[EvidenceSpan] = []
    confidence_local: float = Field(ge=0, le=1, default=0.5)


class ConsolidatedClaim(BaseModel):
    episode_id: str
    claim_id: str
    consolidated: str
    claim_type: ClaimType
    speaker: str | None = None
    first_mention_ts: str | None = None
    evidence: list[EvidenceSpan]
    cluster_ids: list[str] = []


class ScoredClaim(BaseModel):
    episode_id: str
    claim_id: str
    canonical: str
    claim_type: ClaimType
    evidence: list[EvidenceSpan]
    tier: Literal["A", "B", "C"] | None = None
    scores: dict[str, float] = Field(default_factory=dict)


class Relation(BaseModel):
    episode_id: str
    source_claim_id: str
    target_claim_id: str
    type: RelationType
    strength: float = Field(ge=0, le=1, default=0.5)
    rationale: str | None = None


class PersonMention(BaseModel):
    episode_id: str
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
    episode_id: str
    model_id: str
    name: str
    definition: str | None = None
    first_mention_ts: str | None = None
    evidence_spans: list[EvidenceSpan] = []
    aliases: list[str] = []


class JargonTerm(BaseModel):
    episode_id: str
    term_id: str
    term: str
    category: str | None = None
    definition: str | None = None
    evidence_spans: list[EvidenceSpan] = []


class EpisodeBundle(BaseModel):
    episode_id: str
    segments: list[Segment]
    milestones: list[Milestone] | None = None


class PipelineOutputs(BaseModel):
    episode_id: str
    claims: list[ScoredClaim]
    relations: list[Relation] = []
    milestones: list[Milestone] = []
    people: list[PersonMention] = []
    concepts: list[MentalModel] = []
    jargon: list[JargonTerm] = []
