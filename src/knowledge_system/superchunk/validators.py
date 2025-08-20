from __future__ import annotations

from pydantic import BaseModel, Field


class GuideMap(BaseModel):
    themes: list[str]
    entities: list[str]
    tensions: list[str]
    # Paragraph ranges expressed as inclusive indices: [start, end]
    hotspots: list[list[int]] = Field(
        default_factory=list, description="List of [start, end] pairs"
    )
    notes: str | None = None


class Chunk(BaseModel):
    id: str
    span_start: int
    span_end: int
    para_start: int
    para_end: int
    text: str
    preset_used: str


class Landmarks(BaseModel):
    section_title: str | None = None
    key_facts: list[str] = Field(default_factory=list)
    numbered_claims: list[str] = Field(default_factory=list)
    anchors: list[list[int]] = Field(
        default_factory=list, description="List of [span_start, span_end] for anchors"
    )


class ClaimItem(BaseModel):
    text: str
    why_nonobvious: str
    rarity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    quote: str
    span_start: int
    span_end: int
    para_idx: int
    hedges: list[str] = Field(default_factory=list)


class LocalContradictionItem(BaseModel):
    a_claim: str
    b_claim: str
    rationale: str


class JargonItem(BaseModel):
    term: str
    definition: str
    usage_quote: str
    span_start: int
    span_end: int
    para_idx: int


class VerificationItem(BaseModel):
    supported_bool: bool
    confidence_delta: float = Field(ge=-1.0, le=1.0)
    reason: str
