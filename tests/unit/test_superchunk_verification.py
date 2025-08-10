from __future__ import annotations

from knowledge_system.superchunk.verifier import Verifier
from knowledge_system.superchunk.config import SuperChunkConfig
from knowledge_system.superchunk.validators import ClaimItem, VerificationItem
from knowledge_system.superchunk.ledger import Ledger

from pathlib import Path


def test_verifier_monkeypatched(tmp_path, monkeypatch):
    cfg = SuperChunkConfig.from_global_settings()
    ledger = Ledger(tmp_path / "ledger.sqlite")
    verifier = Verifier.create_default(ledger, cfg)

    # Monkeypatch adapter to return a fixed VerificationItem
    def fake_generate_json(prompt, schema, estimated_output_tokens=200):
        return VerificationItem(supported_bool=True, confidence_delta=0.0, reason="ok")

    monkeypatch.setattr(verifier.adapter, "generate_json", fake_generate_json)

    items = [
        (
            1,
            ClaimItem(
                text="Claim", why_nonobvious="Because", rarity=0.5, confidence=0.9,
                quote="quoted text", span_start=0, span_end=5, para_idx=0, hedges=[]
            ),
        )
    ]

    results = verifier.verify_top_claims(items)
    assert results and results[0].supported_bool is True
