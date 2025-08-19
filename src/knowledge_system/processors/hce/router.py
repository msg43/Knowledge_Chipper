from .calibration import compute_uncertainty
from .types import ScoredClaim


class Router:
    def __init__(self, uncertainty_threshold: float = 0.35):
        self.uncertainty_threshold = uncertainty_threshold

    def needs_flagship(self, c: ScoredClaim) -> bool:
        u = compute_uncertainty(c)
        hard_type = c.claim_type in {"causal", "forecast"}
        return hard_type or (u >= self.uncertainty_threshold)

    def split(self, claims: list[ScoredClaim]):
        to_flagship, keep_local = [], []
        for c in claims:
            (to_flagship if self.needs_flagship(c) else keep_local).append(c)
        return to_flagship, keep_local
