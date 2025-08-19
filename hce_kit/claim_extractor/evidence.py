from typing import List

from .types import CandidateClaim, Segment


class EvidenceLinker:
    def __init__(self, embedder):
        self.embedder = embedder

    def link(
        self, segs: list[Segment], candidates: list[CandidateClaim]
    ) -> list[CandidateClaim]:
        # Placeholder: trust model-provided spans or add nearest-neighbor search via embeddings
        return candidates
