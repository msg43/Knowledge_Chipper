from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .config import SuperChunkConfig
from .validators import ClaimItem, VerificationItem
from .ledger import Ledger
from .llm_adapter import SuperChunkLLMAdapter


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
    adapter: SuperChunkLLMAdapter

    @staticmethod
    def create_default(ledger: Ledger, config: SuperChunkConfig) -> "Verifier":
        return Verifier(config=config, ledger=ledger, adapter=SuperChunkLLMAdapter.create_default())

    def _verify_one(self, claim: ClaimItem) -> VerificationItem:
        prompt = (
            "Verify the claim against the provided quote. Return JSON with keys: supported_bool, confidence_delta (-1..1), reason.\n"
            "Use zero temperature reasoning; if quote is insufficient to support, mark unsupported with negative delta.\n\n"
            f"Claim: {claim.text}\n"
            f"Quote: {claim.quote}\n"
        )
        return self.adapter.generate_json(prompt, VerificationItem, estimated_output_tokens=200)

    def verify_top_claims(self, claim_rows: List[tuple[int, ClaimItem]]) -> List[VerificationResult]:
        results: list[VerificationResult] = []
        # Select top N% by confidence (simple proxy)
        claim_rows_sorted = sorted(claim_rows, key=lambda x: x[1].confidence, reverse=True)
        top_n = max(1, int(len(claim_rows_sorted) * self.config.verify_top_percent))
        for claim_id, item in claim_rows_sorted[:top_n]:
            vi = self._verify_one(item)
            res = VerificationResult(
                claim_id=claim_id,
                source_excerpt=item.quote[: self.config.max_quote_words * 6],
                supported_bool=vi.supported_bool,
                confidence_delta=float(vi.confidence_delta),
                reason=vi.reason,
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
