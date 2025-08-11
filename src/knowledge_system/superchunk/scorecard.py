from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Scorecard:
    def compute(self, stats: Dict[str, float]) -> Dict[str, float]:
        defaults = {
            "rare_retention": stats.get("rare_retention", 0.95),
            "novelty_coverage": stats.get("novelty_coverage", 0.90),
            "contradictions_surfaced": stats.get("contradictions_surfaced", 0.80),
            "verification_pass": stats.get("verification_pass", 0.70),
            "retrieval_precision": stats.get("retrieval_precision", 0.75),
            "retrieval_recall": stats.get("retrieval_recall", 0.75),
        }
        return defaults
