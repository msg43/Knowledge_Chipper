from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QualityGates:
    def evaluate(self, metrics: dict[str, float]) -> tuple[bool, dict[str, float]]:
        # Expected keys: rare_retention, novelty_coverage, contradictions_surfaced, verification_pass, retrieval_precision, retrieval_recall
        ok = (
            metrics.get("rare_retention", 0.0) >= 0.95
            and metrics.get("contradictions_surfaced", 0.0) >= 0.80
        )
        return ok, metrics

    def refine_plan(self, failing_targets: list[str]) -> dict:
        return {
            "reason": "Quality gates unmet",
            "targets": failing_targets,
            "actions": [
                "re-read targets",
                "increase window for low coverage regions",
                "re-synthesize",
            ],
        }
