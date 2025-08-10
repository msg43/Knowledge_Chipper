from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from .retrieval import jaccard


@dataclass
class Linker:
    duplicate_threshold: float = 0.88
    neighbor_threshold: float = 0.70

    def link(self, candidates: Iterable[tuple[str, str, str]]):
        # candidates: (src_id, dst_id, relation_hint)
        links: list[dict] = []
        for src_id, dst_id, relation_hint in candidates:
            # In a real version, we'd compare texts; here return conservative placeholders
            relation = relation_hint if relation_hint in {"support", "contradict", "refine", "duplicate"} else "none"
            confidence = 0.5 if relation != "none" else 0.0
            links.append(
                {
                    "src_id": src_id,
                    "dst_id": dst_id,
                    "relation": relation,
                    "rationale": "heuristic placeholder",
                    "confidence": confidence,
                }
            )
        return links
