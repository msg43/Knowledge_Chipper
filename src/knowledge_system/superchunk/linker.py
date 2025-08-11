from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .retrieval import jaccard


@dataclass
class Linker:
    duplicate_threshold: float = 0.88
    neighbor_threshold: float = 0.70

    def link(self, candidates: Iterable[tuple[str, str, str, str, str]]):
        # candidates: (src_id, src_text, dst_id, dst_text, relation_hint)
        links: list[dict] = []
        for src_id, src_text, dst_id, dst_text, relation_hint in candidates:
            sim = jaccard(src_text, dst_text)
            if sim >= self.duplicate_threshold:
                relation = "duplicate"
                confidence = 0.9
            elif sim >= self.neighbor_threshold:
                relation = (
                    relation_hint
                    if relation_hint in {"support", "contradict", "refine"}
                    else "support"
                )
                confidence = 0.6
            else:
                relation = "none"
                confidence = 0.0
            links.append(
                {
                    "src_id": src_id,
                    "dst_id": dst_id,
                    "relation": relation,
                    "rationale": f"jaccard={sim:.2f}",
                    "confidence": confidence,
                    "semantic_similarity": sim,
                }
            )
        return links
