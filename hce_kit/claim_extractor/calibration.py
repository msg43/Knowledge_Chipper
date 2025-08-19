from .types import ScoredClaim


def compute_uncertainty(c: ScoredClaim) -> float:
    """
    Combine multiple signals (if present):
    - self_consistency_var
    - nli_margin
    - rerank_margin
    Fallback to 1 - importance if none present.
    """
    s = c.scores or {}
    if all(k in s for k in ("self_consistency_var", "nli_margin", "rerank_margin")):
        return float(
            min(
                1.0,
                0.4 * s["self_consistency_var"]
                + 0.3 * (1 - s["nli_margin"])
                + 0.3 * (1 - s["rerank_margin"]),
            )
        )
    return float(max(0.0, 1.0 - s.get("importance", 0.0)))
