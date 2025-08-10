from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, conlist, confloat, constr


class GuideMap(BaseModel):
    themes: List[str]
    entities: List[str]
    tensions: List[str]
    # Paragraph ranges expressed as inclusive indices: [start, end]
    hotspots: List[conlist(int, min_length=2, max_length=2)] = Field(default_factory=list)
    notes: Optional[str] = None


class Chunk(BaseModel):
    id: str
    span_start: int
    span_end: int
    para_start: int
    para_end: int
    text: str
    preset_used: constr(strip_whitespace=True)


class Landmarks(BaseModel):
    section_title: Optional[str] = None
    key_facts: List[str] = Field(default_factory=list)
    numbered_claims: List[str] = Field(default_factory=list)
    anchors: List[conlist(int, min_length=2, max_length=2)] = Field(
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
    hedges: List[str] = Field(default_factory=list)


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
