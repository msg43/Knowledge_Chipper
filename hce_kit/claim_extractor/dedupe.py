from typing import List

from .types import CandidateClaim, ConsolidatedClaim, EvidenceSpan


class Deduper:
    def __init__(self, embedder):
        self.embedder = embedder

    def cluster(self, cands: list[CandidateClaim]) -> list[ConsolidatedClaim]:
        # TODO: implement HDBSCAN over embeddings; pick representative phrasing
        out: list[ConsolidatedClaim] = []
        for i, c in enumerate(cands):
            out.append(
                ConsolidatedClaim(
                    episode_id=c.episode_id,
                    claim_id=f"cl{i}",
                    consolidated=c.claim_text.strip(),
                    claim_type=c.claim_type,
                    speaker=c.speaker,
                    first_mention_ts=(
                        c.evidence_spans[0].t0 if c.evidence_spans else None
                    ),
                    evidence=[EvidenceSpan(**e.model_dump()) for e in c.evidence_spans],
                    cluster_ids=[c.candidate_id],
                )
            )
        return out
