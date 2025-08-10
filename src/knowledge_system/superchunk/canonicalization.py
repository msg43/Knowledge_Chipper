from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from .validators import ClaimItem


def _canonical_text(text: str) -> str:
    return " ".join(text.lower().split())


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass
class Canonicalizer:
    dedupe_threshold: float = 0.88

    def canonicalize(self, claims: Iterable[ClaimItem]) -> List[tuple[str, ClaimItem]]:
        # Return (canonical_id, claim)
        out: list[tuple[str, ClaimItem]] = []
        for c in claims:
            canon = _canonical_text(c.text)
            cid = _hash(canon)
            out.append((cid, c))
        return out

    def compute_novelty(self, ordered_claims: Iterable[ClaimItem]) -> List[float]:
        # Simple novelty: earlier claims get higher novelty; duplicates share lower
        seen: set[str] = set()
        novelty: list[float] = []
        for c in ordered_claims:
            key = _canonical_text(c.text)
            if key in seen:
                novelty.append(0.2)
            else:
                novelty.append(1.0)
                seen.add(key)
        return novelty

    def track_evolution(self, claims_with_para: Iterable[tuple[ClaimItem, int]]) -> dict[str, list[int]]:
        # Map canonical_id to list of paragraph indices where it appears
        trajectory: dict[str, list[int]] = {}
        for c, para_idx in claims_with_para:
            cid = _hash(_canonical_text(c.text))
            trajectory.setdefault(cid, []).append(para_idx)
        return trajectory
