from .types import CandidateClaim, Segment


class EvidenceLinker:
    def __init__(self, embedder):
        self.embedder = embedder

    def link(
        self, segs: list[Segment], candidates: list[CandidateClaim]
    ) -> list[CandidateClaim]:
        # Placeholder: trust model-provided spans or add nearest-neighbor search via embeddings
        return candidates


def link_evidence(candidates: list[CandidateClaim], segments: list[Segment]) -> list[CandidateClaim]:
    """Compatibility wrapper used by HCEPipeline."""
    # TODO: wire embedder if advanced linking is needed
    return candidates
