from .context_expansion import expand_all_evidence_context
from .types import CandidateClaim, Segment


class EvidenceLinker:
    def __init__(self, embedder):
        self.embedder = embedder

    def link(
        self, segs: list[Segment], candidates: list[CandidateClaim]
    ) -> list[CandidateClaim]:
        # Placeholder: trust model-provided spans or add nearest-neighbor search via embeddings
        return candidates


def link_evidence(
    candidates: list[CandidateClaim], segments: list[Segment]
) -> list[CandidateClaim]:
    """
    Link evidence and expand context for all candidate claims.

    This function now also expands evidence spans with conversational context
    using smart boundary detection.
    """
    # Process each candidate claim
    for candidate in candidates:
        # Expand context for all evidence spans in this claim
        candidate.evidence_spans = expand_all_evidence_context(
            candidate.evidence_spans, segments, method="conversational_boundary"
        )

    return candidates
