"""Performance benchmarks for HCE (Hybrid Claim Extractor) system."""

import time
from unittest.mock import Mock, patch

import pytest

from src.knowledge_system.processors.hce.dedupe import Deduper
from src.knowledge_system.processors.hce.types import CandidateClaim, EvidenceSpan


class TestHCEPerformance:
    """Performance benchmarks for HCE components."""

    def test_deduplication_performance(self):
        """Benchmark claim deduplication performance."""
        # Mock embedder for consistent results
        mock_embedder = Mock()

        # Create embeddings for different similarity patterns
        def mock_encode(texts, use_cache=True):
            # Generate embeddings that create realistic similarity patterns
            import numpy as np

            embeddings = []
            for i, text in enumerate(texts):
                # Create some similar clusters
                cluster_id = i // 3  # Groups of 3 similar claims
                base_embedding = np.random.random(384) * 0.1  # Small random variation
                base_embedding[cluster_id % 10] += 0.5  # Make clusters distinct
                embeddings.append(base_embedding)
            return np.array(embeddings)

        mock_embedder.encode.side_effect = mock_encode

        deduper = Deduper(mock_embedder, similarity_threshold=0.8)

        # Test with different numbers of claims
        test_sizes = [10, 50, 100, 200]

        for size in test_sizes:
            # Create test claims
            claims = []
            for i in range(size):
                claims.append(
                    CandidateClaim(
                        episode_id="ep1",
                        candidate_id=f"c{i}",
                        claim_text=f"Test claim {i} about topic {i // 3}",
                        claim_type="factual",
                        speaker="narrator",
                        evidence_spans=[
                            EvidenceSpan(
                                t0=str(i * 10),
                                t1=str((i + 1) * 10),
                                quote=f"evidence {i}",
                            )
                        ],
                    )
                )

            # Benchmark deduplication
            start_time = time.time()
            consolidated = deduper.cluster(claims)
            end_time = time.time()

            processing_time = end_time - start_time
            claims_per_second = (
                size / processing_time if processing_time > 0 else float("inf")
            )

            print(
                f"Deduplication: {size} claims -> {len(consolidated)} clusters in {processing_time:.3f}s ({claims_per_second:.1f} claims/sec)"
            )

            # Performance assertions
            assert processing_time < size * 0.01  # Should be faster than 10ms per claim
            assert len(consolidated) <= size  # Should reduce or maintain claim count
            assert len(consolidated) > 0  # Should produce some output

    def test_embedding_cache_performance(self):
        """Benchmark embedding cache performance."""
        import tempfile
        from pathlib import Path

        import numpy as np

        from src.knowledge_system.utils.embedding_cache import EmbeddingCache

        with tempfile.TemporaryDirectory() as temp_dir:
            cache = EmbeddingCache(
                cache_dir=Path(temp_dir), max_memory_items=1000, ttl_hours=24
            )

            # Test texts
            test_texts = [f"This is test sentence number {i}" for i in range(100)]
            test_embeddings = [np.random.random(384) for _ in test_texts]

            # Benchmark cache writes
            start_time = time.time()
            for text, embedding in zip(test_texts, test_embeddings):
                cache.put(text, "test-model", embedding)
            write_time = time.time() - start_time

            # Benchmark cache reads (hits)
            start_time = time.time()
            hits = 0
            for text in test_texts:
                result = cache.get(text, "test-model")
                if result is not None:
                    hits += 1
            read_time = time.time() - start_time

            # Benchmark cache reads (misses)
            start_time = time.time()
            misses = 0
            for i in range(50):
                result = cache.get(f"missing text {i}", "test-model")
                if result is None:
                    misses += 1
            miss_time = time.time() - start_time

            print(
                f"Cache writes: {len(test_texts)} items in {write_time:.3f}s ({len(test_texts)/write_time:.1f} items/sec)"
            )
            print(
                f"Cache hits: {hits}/{len(test_texts)} in {read_time:.3f}s ({hits/read_time:.1f} items/sec)"
            )
            print(
                f"Cache misses: {misses}/50 in {miss_time:.3f}s ({misses/miss_time:.1f} items/sec)"
            )

            # Performance assertions
            assert hits == len(test_texts)  # All items should be cached
            assert misses == 50  # All lookups should miss
            assert write_time < 1.0  # Should write 100 items in under 1 second
            assert read_time < 0.1  # Should read 100 items in under 0.1 second
            assert read_time < write_time  # Reads should be faster than writes

    def test_hce_analytics_performance(self):
        """Benchmark HCE analytics extraction performance."""
        from src.knowledge_system.gui.tabs.summarization_tab import (
            EnhancedSummarizationWorker,
        )

        worker = EnhancedSummarizationWorker([], {}, {})

        # Create large HCE dataset
        large_hce_data = {
            "claims": [
                {
                    "canonical": f"Test claim number {i} about topic {i % 10}",
                    "tier": ["A", "B", "C"][i % 3],
                    "claim_type": ["factual", "opinion", "causal"][i % 3],
                    "evidence": [f"Evidence {j} for claim {i}" for j in range(3)],
                }
                for i in range(1000)  # 1000 claims
            ],
            "people": [{"name": f"Person {i}"} for i in range(100)],
            "concepts": [{"name": f"Concept {i}"} for i in range(200)],
            "relations": [
                {"source": f"cl{i}", "target": f"cl{i+1}", "type": "supports"}
                for i in range(500)
            ],
            "contradictions": [
                {
                    "claim1": {"canonical": f"Claim {i} is true"},
                    "claim2": {"canonical": f"Claim {i} is false"},
                }
                for i in range(50)
            ],
        }

        # Benchmark analytics extraction
        start_time = time.time()
        analytics = worker._extract_hce_analytics(large_hce_data, "large_test_file.md")
        end_time = time.time()

        processing_time = end_time - start_time
        items_processed = (
            len(large_hce_data["claims"])
            + len(large_hce_data["people"])
            + len(large_hce_data["concepts"])
            + len(large_hce_data["relations"])
            + len(large_hce_data["contradictions"])
        )
        items_per_second = (
            items_processed / processing_time if processing_time > 0 else float("inf")
        )

        print(
            f"Analytics extraction: {items_processed} items in {processing_time:.3f}s ({items_per_second:.1f} items/sec)"
        )

        # Verify results
        assert analytics["total_claims"] == 1000
        assert (
            analytics["tier_a_count"]
            + analytics["tier_b_count"]
            + analytics["tier_c_count"]
            == 1000
        )
        assert analytics["people_count"] == 100
        assert analytics["concepts_count"] == 200
        assert analytics["relations_count"] == 500
        assert analytics["contradictions_count"] == 50

        # Performance assertions
        assert processing_time < 1.0  # Should process large dataset in under 1 second
        assert len(analytics["top_claims"]) <= 3  # Should limit output size
        assert len(analytics["top_people"]) <= 5  # Should limit output size
        assert len(analytics["sample_contradictions"]) <= 2  # Should limit output size

    def test_memory_usage_during_processing(self):
        """Test memory usage during HCE processing."""
        import os

        import psutil

        process = psutil.Process(os.getpid())

        # Get baseline memory usage
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Simulate processing large amounts of data
        from src.knowledge_system.processors.hce.dedupe import Deduper

        mock_embedder = Mock()
        mock_embedder.encode.return_value = [
            [0.1] * 384 for _ in range(1000)
        ]  # 1000 embeddings

        deduper = Deduper(mock_embedder)

        # Create many claims to test memory usage
        large_claim_set = []
        for i in range(1000):
            large_claim_set.append(
                CandidateClaim(
                    episode_id="ep1",
                    candidate_id=f"c{i}",
                    claim_text=f"This is a longer test claim number {i} that contains more text to simulate real-world usage patterns and memory consumption during processing",
                    claim_type="factual",
                    speaker="narrator",
                    evidence_spans=[
                        EvidenceSpan(
                            t0=str(i * 10),
                            t1=str((i + 1) * 10),
                            quote=f"This is evidence span {j} for claim {i} with additional context and details",
                        )
                        for j in range(5)  # 5 evidence spans per claim
                    ],
                )
            )

        # Process and measure memory
        with patch(
            "src.knowledge_system.processors.hce.dedupe.cosine_similarity"
        ) as mock_similarity:
            # Mock similarity matrix (avoid actual computation for memory test)
            mock_similarity.return_value = [[0.5] * 1000 for _ in range(1000)]

            peak_memory = baseline_memory

            # Process in chunks to monitor memory usage
            for chunk_start in range(0, len(large_claim_set), 100):
                chunk = large_claim_set[chunk_start : chunk_start + 100]
                deduper.cluster(chunk)

                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                peak_memory = max(peak_memory, current_memory)

            memory_increase = peak_memory - baseline_memory

            print(
                f"Memory usage: baseline {baseline_memory:.1f}MB, peak {peak_memory:.1f}MB, increase {memory_increase:.1f}MB"
            )

            # Memory usage should be reasonable
            assert (
                memory_increase < 500
            )  # Should not use more than 500MB additional memory
            assert peak_memory < 2000  # Should not exceed 2GB total memory


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to see print output
