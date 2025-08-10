from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .config import SuperChunkConfig
from .validators import ClaimItem


@dataclass
class VerificationResult:
    claim_id: int
    source_excerpt: str
    supported_bool: bool
    confidence_delta: float
    reason: str


@dataclass
class Verifier:
    config: SuperChunkConfig

    def verify_top_claims(self, claims: List[tuple[int, ClaimItem]]) -> List[VerificationResult]:
        # claims: list of (claim_id, ClaimItem)
        # Stub: mark all as supported with zero delta
        results: list[VerificationResult] = []
        for claim_id, item in claims:
            excerpt = item.quote[: self.config.max_quote_words * 6]  # approximate words to chars
            results.append(
                VerificationResult(
                    claim_id=claim_id,
                    source_excerpt=excerpt,
                    supported_bool=True,
                    confidence_delta=0.0,
                    reason="stub verifier",
                )
            )
        return results
