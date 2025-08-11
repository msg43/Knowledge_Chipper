from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, confloat, conlist, constr


class GuideMap(BaseModel):
    themes: list[str]
    entities: list[str]
    tensions: list[str]
    # Paragraph ranges expressed as inclusive indices: [start, end]
    hotspots: list[conlist(int, min_length=2, max_length=2)] = Field(
        default_factory=list
    )
    notes: str | None = None


class Chunk(BaseModel):
    id: str
    span_start: int
    span_end: int
    para_start: int
    para_end: int
    text: str
    preset_used: constr(strip_whitespace=True)


class Landmarks(BaseModel):
    section_title: str | None = None
    key_facts: list[str] = Field(default_factory=list)
    numbered_claims: list[str] = Field(default_factory=list)
    anchors: list[conlist(int, min_length=2, max_length=2)] = Field(
        default_factory=list, description="List of [span_start, span_end] for anchors"
    )


class ClaimItem(BaseModel):
    text: str
    why_nonobvious: str
    rarity: confloat(ge=0.0, le=1.0)
    confidence: confloat(ge=0.0, le=1.0)
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
    confidence_delta: confloat(ge=-1.0, le=1.0)
    reason: str
