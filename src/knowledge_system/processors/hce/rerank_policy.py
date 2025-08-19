import numpy as np

from .types import ScoredClaim


def adaptive_keep(
    scored: list[ScoredClaim],
    duration_minutes: float,
    base_density: float = 1.2,
    min_keep: int = 25,
    max_keep: int = 400,
    percentile_floor: float = 0.55,
) -> list[ScoredClaim]:
    if not scored:
        return []
    scores = np.array([c.scores.get("importance", 0.0) for c in scored])
    n_target = int(
        np.clip(base_density * max(duration_minutes, 5.0), min_keep, max_keep)
    )
    thr = float(np.quantile(scores, percentile_floor))
    filtered = [c for c in scored if c.scores.get("importance", 0.0) >= thr]
    filtered.sort(key=lambda x: x.scores.get("importance", 0.0), reverse=True)
    for i, c in enumerate(filtered):
        c.tier = "A" if i < max(10, n_target // 3) else ("B" if i < n_target else "C")
    return filtered[:n_target]
