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


def rerank_claims(
    consolidated: list[ConsolidatedClaim], policy, reranker_model: str
) -> list[ScoredClaim]:
    """Compatibility wrapper used by HCEPipeline: score then apply policy."""
    # Minimal scoring: importance based on length as placeholder
    pairs = [("", c.consolidated) for c in consolidated]
    # Fallback CrossEncoder scoring
    try:
        # Fix reranker model name if it's a local:// scheme
        if reranker_model.startswith("local://"):
            reranker_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ce = CrossEncoder(reranker_model)
        scores = ce.score(pairs)
    except Exception:
        scores = [min(1.0, max(0.0, len(c.consolidated) / 400.0)) for c in consolidated]

    scored = []
    for c, s in zip(consolidated, scores):
        scored.append(
            ScoredClaim(
                episode_id=c.episode_id,
                claim_id=c.claim_id,
                canonical=c.consolidated,
                claim_type=c.claim_type,
                evidence=c.evidence,
                scores={"importance": float(s)},
            )
        )

    # Apply policy to assign tiers and filter
    try:
        from .rerank_policy import adaptive_keep

        duration_minutes = max(5.0, len(pairs) / 12.0)
        kept = adaptive_keep(scored, duration_minutes)
        return kept
    except Exception:
        return scored
