from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Scorecard:
    def compute(self, stats: Dict[str, float]) -> Dict[str, float]:
        # Placeholder passthrough; real implementation will compute gates
        defaults = {
            "rare_retention": 0.95,
            "novelty_coverage": 0.90,
            "contradictions_surfaced": 0.80,
            "verification_pass": 0.70,
            "retrieval_precision": 0.75,
            "retrieval_recall": 0.75,
        }
        defaults.update(stats)
        return defaults
