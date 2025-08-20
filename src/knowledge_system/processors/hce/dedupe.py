import logging

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .types import CandidateClaim, ConsolidatedClaim, EvidenceSpan

logger = logging.getLogger(__name__)


class Deduper:
    def __init__(self, embedder, similarity_threshold: float = 0.85):
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold

    def cluster(self, cands: list[CandidateClaim]) -> list[ConsolidatedClaim]:
        """Cluster candidate claims by semantic similarity to remove duplicates."""
        if not cands:
            return []

        if len(cands) == 1:
            # Single claim, no deduplication needed
            return [self._create_consolidated_claim(cands[0], [cands[0]], 0)]

        try:
            # Extract claim texts for embedding
            claim_texts = [c.claim_text.strip() for c in cands]

            # Get embeddings for all claims
            embeddings = self.embedder.encode(claim_texts, use_cache=True)

            # Compute similarity matrix
            similarity_matrix = cosine_similarity(embeddings)

            # Find clusters using simple threshold-based clustering
            clusters = self._threshold_clustering(
                similarity_matrix, self.similarity_threshold
            )

            # Create consolidated claims from clusters
            consolidated_claims = []
            for i, cluster_indices in enumerate(clusters):
                cluster_claims = [cands[idx] for idx in cluster_indices]
                representative_claim = self._select_representative_claim(
                    cluster_claims, embeddings, cluster_indices
                )
                consolidated_claim = self._create_consolidated_claim(
                    representative_claim, cluster_claims, i
                )
                consolidated_claims.append(consolidated_claim)

            logger.info(
                f"Deduplicated {len(cands)} claims into {len(consolidated_claims)} clusters"
            )
            return consolidated_claims

        except Exception as e:
            logger.warning(f"Deduplication failed, returning original claims: {e}")
            # Fallback: return all claims as separate consolidated claims
            return [
                self._create_consolidated_claim(c, [c], i) for i, c in enumerate(cands)
            ]

    def _threshold_clustering(
        self, similarity_matrix: np.ndarray, threshold: float
    ) -> list[list[int]]:
        """Simple threshold-based clustering algorithm."""
        n = similarity_matrix.shape[0]
        visited = [False] * n
        clusters = []

        for i in range(n):
            if visited[i]:
                continue

            # Start new cluster with current claim
            cluster = [i]
            visited[i] = True

            # Find all similar claims
            for j in range(i + 1, n):
                if not visited[j] and similarity_matrix[i, j] >= threshold:
                    cluster.append(j)
                    visited[j] = True

            clusters.append(cluster)

        return clusters

    def _select_representative_claim(
        self,
        cluster_claims: list[CandidateClaim],
        embeddings: np.ndarray,
        cluster_indices: list[int],
    ) -> CandidateClaim:
        """Select the most representative claim from a cluster."""
        if len(cluster_claims) == 1:
            return cluster_claims[0]

        # Calculate centroid of cluster embeddings
        cluster_embeddings = embeddings[cluster_indices]
        centroid = np.mean(cluster_embeddings, axis=0)

        # Find claim closest to centroid
        similarities_to_centroid = cosine_similarity([centroid], cluster_embeddings)[0]
        best_idx = np.argmax(similarities_to_centroid)

        return cluster_claims[best_idx]

    def _create_consolidated_claim(
        self,
        representative: CandidateClaim,
        cluster_claims: list[CandidateClaim],
        cluster_id: int,
    ) -> ConsolidatedClaim:
        """Create a consolidated claim from a cluster."""
        # Combine evidence from all claims in cluster
        all_evidence = []
        cluster_ids = []

        for claim in cluster_claims:
            cluster_ids.append(claim.candidate_id)
            all_evidence.extend(
                [EvidenceSpan(**e.model_dump()) for e in claim.evidence_spans]
            )

        # Sort evidence by timestamp if available
        all_evidence.sort(key=lambda e: e.t0 if e.t0 is not None else float("inf"))

        return ConsolidatedClaim(
            episode_id=representative.episode_id,
            claim_id=f"cl{cluster_id}",
            consolidated=representative.claim_text.strip(),
            claim_type=representative.claim_type,
            speaker=representative.speaker,
            first_mention_ts=(
                representative.evidence_spans[0].t0
                if representative.evidence_spans
                else None
            ),
            evidence=all_evidence,
            cluster_ids=cluster_ids,
        )
