from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .config import SuperChunkConfig
from .validators import ClaimItem
from .ledger import Ledger


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
    ledger: Ledger

    def verify_top_claims(self, claims: List[tuple[int, ClaimItem]]) -> List[VerificationResult]:
        results: list[VerificationResult] = []
        for claim_id, item in claims:
            excerpt = item.quote[: self.config.max_quote_words * 6]
            res = VerificationResult(
                claim_id=claim_id,
                source_excerpt=excerpt,
                supported_bool=True,
                confidence_delta=0.0,
                reason="stub verifier",
            )
            self.ledger.insert_verification_result(
                claim_id=claim_id,
                source_excerpt=res.source_excerpt,
                supported=res.supported_bool,
                confidence_delta=res.confidence_delta,
                reason=res.reason,
            )
            results.append(res)
        return results
