"""Integration tests for HCE (Hybrid Claim Extractor) system."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.knowledge_system.database import DatabaseService
from src.knowledge_system.processors.summarizer import SummarizerProcessor


class TestHCEIntegration:
    """Test HCE integration with the Knowledge System."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db_service = DatabaseService(
            "sqlite:///:memory:"
        )  # In-memory database for testing

    def test_hce_summarizer_basic_functionality(self):
        """Test that HCE summarizer can process text and return structured data."""
        # Create a test processor
        processor = SummarizerProcessor(
            provider="openai", model="gpt-4o-mini-2024-07-18", max_tokens=1000
        )

        # Mock the HCE processing to avoid API calls
        mock_hce_data = {
            "claims": [
                {
                    "claim_id": "cl1",
                    "canonical": "The sky is blue during clear weather",
                    "tier": "A",
                    "claim_type": "factual",
                    "evidence": ["Clear skies appear blue due to light scattering"],
                },
                {
                    "claim_id": "cl2",
                    "canonical": "Weather patterns affect visibility",
                    "tier": "B",
                    "claim_type": "causal",
                    "evidence": [],
                },
            ],
            "people": [{"name": "John Smith", "description": "Weather researcher"}],
            "concepts": [
                {
                    "name": "atmospheric scattering",
                    "description": "Light scattering in atmosphere",
                }
            ],
            "relations": [{"source": "cl1", "target": "cl2", "type": "supports"}],
            "contradictions": [],
        }

        # Test text input
        test_text = "The sky appears blue on clear days. John Smith, a weather researcher, explains that atmospheric scattering causes this phenomenon. Weather patterns can affect how clearly we see the sky."

        with patch.object(processor, "_process_with_hce") as mock_process:
            mock_result = Mock()
            mock_result.success = True
            mock_result.data = {
                "summary_text": "Test summary",
                "hce_data": mock_hce_data,
                "output_file": "test_output.md",
            }
            mock_result.metadata = {
                "provider": "openai",
                "model": "gpt-4o-mini-2024-07-18",
            }
            mock_result.errors = []
            mock_process.return_value = mock_result

            # Process the text
            result = processor.process(test_text)

            # Verify the result structure
            assert result.success is True
            assert "hce_data" in result.data
            assert "claims" in result.data["hce_data"]
            assert len(result.data["hce_data"]["claims"]) == 2

            # Verify claim structure
            claims = result.data["hce_data"]["claims"]
            assert claims[0]["tier"] == "A"
            assert claims[0]["canonical"] == "The sky is blue during clear weather"
            assert claims[1]["tier"] == "B"

            # Verify people and concepts
            assert len(result.data["hce_data"]["people"]) == 1
            assert result.data["hce_data"]["people"][0]["name"] == "John Smith"
            assert len(result.data["hce_data"]["concepts"]) == 1

            # Verify relations
            assert len(result.data["hce_data"]["relations"]) == 1
            assert result.data["hce_data"]["relations"][0]["type"] == "supports"

    def test_hce_database_integration(self):
        """Test that HCE data is properly stored in the database."""
        # Create test video and summary data
        video_id = "test_video_123"

        # Add a test video to the database
        self.db_service.add_video(
            video_id=video_id,
            url=f"https://youtube.com/watch?v={video_id}",
            title="Test Video",
            description="A test video for HCE integration",
            duration_seconds=300,
        )

        # Create mock HCE data
        hce_data = {
            "claims": [
                {
                    "claim_id": "cl1",
                    "canonical": "Test claim about artificial intelligence",
                    "tier": "A",
                    "claim_type": "definition",
                    "evidence": ["AI systems process information"],
                }
            ],
            "people": [{"name": "Alan Turing", "description": "Computer scientist"}],
            "concepts": [
                {
                    "name": "artificial intelligence",
                    "description": "Machine intelligence",
                }
            ],
            "relations": [],
            "contradictions": [],
        }

        # Test saving HCE data
        summary_id = self.db_service.save_hce_data(
            video_id=video_id,
            hce_data=hce_data,
            summary_text="Test summary text",
            llm_provider="openai",
            llm_model="gpt-4o-mini-2024-07-18",
            processing_cost=0.05,
            total_tokens=1000,
        )

        assert summary_id is not None

        # Retrieve and verify the data
        summaries = self.db_service.get_summaries_for_video(video_id)
        assert len(summaries) == 1

        summary = summaries[0]
        assert summary.processing_type == "hce"
        assert summary.hce_data_json is not None

        # Parse and verify HCE data
        import json

        stored_hce_data = json.loads(summary.hce_data_json)
        assert len(stored_hce_data["claims"]) == 1
        assert (
            stored_hce_data["claims"][0]["canonical"]
            == "Test claim about artificial intelligence"
        )
        assert stored_hce_data["claims"][0]["tier"] == "A"

    def test_hce_claim_deduplication(self):
        """Test that claim deduplication works correctly."""
        from src.knowledge_system.processors.hce.dedupe import Deduper
        from src.knowledge_system.processors.hce.types import (
            CandidateClaim,
            EvidenceSpan,
        )

        # Mock embedder for testing
        mock_embedder = Mock()
        mock_embedder.encode.return_value = [
            [0.1, 0.2, 0.3],  # Similar to next one
            [0.15, 0.25, 0.35],  # Similar to previous one
            [0.8, 0.9, 0.7],  # Different from others
        ]

        deduper = Deduper(mock_embedder, similarity_threshold=0.85)

        # Create test candidate claims
        claims = [
            CandidateClaim(
                episode_id="ep1",
                candidate_id="c1",
                claim_text="The sky is blue",
                claim_type="factual",
                speaker="narrator",
                evidence_spans=[EvidenceSpan(t0="0", t1="10", quote="sky blue")],
            ),
            CandidateClaim(
                episode_id="ep1",
                candidate_id="c2",
                claim_text="The sky appears blue in color",
                claim_type="factual",
                speaker="narrator",
                evidence_spans=[EvidenceSpan(t0="15", t1="25", quote="sky blue color")],
            ),
            CandidateClaim(
                episode_id="ep1",
                candidate_id="c3",
                claim_text="Water is wet",
                claim_type="factual",
                speaker="narrator",
                evidence_spans=[EvidenceSpan(t0="30", t1="40", quote="water wet")],
            ),
        ]

        # Mock cosine similarity to return high similarity for first two claims
        with patch(
            "src.knowledge_system.processors.hce.dedupe.cosine_similarity"
        ) as mock_similarity:
            mock_similarity.return_value = [
                [1.0, 0.9, 0.3],  # Claim 1 similarities
                [0.9, 1.0, 0.2],  # Claim 2 similarities
                [0.3, 0.2, 1.0],  # Claim 3 similarities
            ]

            consolidated = deduper.cluster(claims)

            # Should have 2 clusters: one for similar claims, one for different claim
            assert len(consolidated) == 2

            # Verify cluster consolidation
            cluster_sizes = [len(claim.cluster_ids) for claim in consolidated]
            assert 2 in cluster_sizes  # One cluster with 2 claims
            assert 1 in cluster_sizes  # One cluster with 1 claim

    def test_hce_analytics_extraction(self):
        """Test that HCE analytics are correctly extracted for display."""
        from src.knowledge_system.gui.tabs.summarization_tab import (
            EnhancedSummarizationWorker,
        )

        worker = EnhancedSummarizationWorker([], {}, {})

        # Mock HCE data with various claim tiers
        hce_data = {
            "claims": [
                {
                    "canonical": "High confidence claim",
                    "tier": "A",
                    "claim_type": "factual",
                },
                {
                    "canonical": "Medium confidence claim",
                    "tier": "B",
                    "claim_type": "opinion",
                },
                {
                    "canonical": "Low confidence claim",
                    "tier": "C",
                    "claim_type": "speculation",
                },
                {
                    "canonical": "Another high confidence claim",
                    "tier": "A",
                    "claim_type": "causal",
                },
            ],
            "people": [{"name": "Alice Smith"}, {"name": "Bob Johnson"}],
            "concepts": [{"name": "machine learning"}, {"name": "data science"}],
            "relations": [{"source": "cl1", "target": "cl2", "type": "supports"}],
            "contradictions": [
                {
                    "claim1": {"canonical": "AI is beneficial"},
                    "claim2": {"canonical": "AI is harmful"},
                }
            ],
        }

        analytics = worker._extract_hce_analytics(hce_data, "test_file.md")

        # Verify analytics structure
        assert analytics["filename"] == "test_file.md"
        assert analytics["total_claims"] == 4
        assert analytics["tier_a_count"] == 2
        assert analytics["tier_b_count"] == 1
        assert analytics["tier_c_count"] == 1
        assert analytics["people_count"] == 2
        assert analytics["concepts_count"] == 2
        assert analytics["relations_count"] == 1
        assert analytics["contradictions_count"] == 1

        # Verify top claims (should prioritize A and B tier)
        assert len(analytics["top_claims"]) <= 3
        assert any(claim["tier"] == "A" for claim in analytics["top_claims"])

        # Verify sample data
        assert len(analytics["top_people"]) == 2
        assert "Alice Smith" in analytics["top_people"]
        assert len(analytics["sample_contradictions"]) == 1


if __name__ == "__main__":
    pytest.main([__file__])
