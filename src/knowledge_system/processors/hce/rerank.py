from .models.cross_encoder import CrossEncoder
from .types import ConsolidatedClaim, ScoredClaim


class Reranker:
    def __init__(self, cross_encoder: CrossEncoder):
        self.ce = cross_encoder

    def score(
        self, episode_text: str, claims: list[ConsolidatedClaim]
    ) -> list[ScoredClaim]:
        pairs = [(episode_text, c.consolidated) for c in claims]
        scores = self.ce.score(pairs)
        out = []
        for c, s in zip(claims, scores):
            out.append(
                ScoredClaim(
                    episode_id=c.episode_id,
                    claim_id=c.claim_id,
                    canonical=c.consolidated,
                    claim_type=c.claim_type,
                    evidence=c.evidence,
                    scores={"importance": float(s)},
                )
            )
        return out
