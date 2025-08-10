from __future__ import annotations

from knowledge_system.superchunk.linker import Linker


def test_linker_similarity_thresholds():
    linker = Linker(duplicate_threshold=0.9, neighbor_threshold=0.2)
    cands = [("a", "alpha beta", "b", "alpha gamma", "support")]
    links = linker.link(cands)
    assert links and links[0]["relation"] in {"support", "duplicate", "none"}
