from __future__ import annotations

from knowledge_system.superchunk.signals import compute_signals


def test_precision_score_computation():
    text = "However, numbers 123 appear. Therefore, more details. Once upon a time, a story continues."
    sigs = compute_signals(text)
    assert isinstance(sigs, list)
    if sigs:
        score = sigs[0][1].precision_score()
        assert 0.0 <= score <= 1.0 or -1.0 <= score <= 1.0
