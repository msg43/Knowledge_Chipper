"""End-to-end system tests for HCE implementation."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.knowledge_system.database import DatabaseService
from src.knowledge_system.processors.summarizer import SummarizerProcessor


class TestHCESystemIntegration:
    """System-level tests for HCE functionality."""

    def setup_method(self):
        """Set up test environment."""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_service = DatabaseService(f"sqlite:///{self.temp_db.name}")

        # Create test content
        self.test_content = """
        Artificial Intelligence (AI) is transforming modern society. Dr. Jane Smith,
        a leading AI researcher at MIT, explains that machine learning algorithms
        can process vast amounts of data to identify patterns. However, there are
        concerns about AI bias and ethical implications. Some experts argue that
        AI will create more jobs than it destroys, while others worry about
        widespread unemployment. The technology requires careful regulation to
        ensure beneficial outcomes for humanity.
        """

    def teardown_method(self):
        """Clean up test environment."""
        Path(self.temp_db.name).unlink(missing_ok=True)

    def test_full_hce_pipeline(self):
        """Test the complete HCE processing pipeline."""
        # Mock HCE processing to simulate real behavior
        mock_hce_data = {
            "claims": [
                {
                    "claim_id": "cl1",
                    "canonical": "AI is transforming modern society",
                    "tier": "A",
                    "claim_type": "factual",
                    "evidence": ["AI systems are being deployed across industries"],
                },
                {
                    "claim_id": "cl2",
                    "canonical": "Machine learning algorithms can process vast amounts of data",
                    "tier": "A",
                    "claim_type": "technical",
                    "evidence": ["ML algorithms designed for big data processing"],
                },
                {
                    "claim_id": "cl3",
                    "canonical": "There are concerns about AI bias and ethical implications",
                    "tier": "B",
                    "claim_type": "concern",
                    "evidence": ["Multiple studies highlight AI bias issues"],
                },
                {
                    "claim_id": "cl4",
                    "canonical": "AI will create more jobs than it destroys",
                    "tier": "C",
                    "claim_type": "prediction",
                    "evidence": [],
                },
                {
                    "claim_id": "cl5",
                    "canonical": "AI may cause widespread unemployment",
                    "tier": "C",
                    "claim_type": "prediction",
                    "evidence": [],
                },
            ],
            "people": [
                {
                    "name": "Dr. Jane Smith",
                    "description": "Leading AI researcher at MIT",
                    "role": "expert",
                }
            ],
            "concepts": [
                {
                    "name": "Artificial Intelligence",
                    "description": "Computer systems that can perform tasks requiring human intelligence",
                },
                {
                    "name": "Machine Learning",
                    "description": "AI technique that learns from data",
                },
                {
                    "name": "AI Bias",
                    "description": "Systematic errors in AI decision-making",
                },
            ],
            "relations": [
                {"source": "cl1", "target": "cl2", "type": "supports", "strength": 0.8}
            ],
            "contradictions": [
                {
                    "claim1": {
                        "canonical": "AI will create more jobs than it destroys"
                    },
                    "claim2": {"canonical": "AI may cause widespread unemployment"},
                    "confidence": 0.7,
                }
            ],
        }

        # Create processor
        processor = SummarizerProcessor(
            provider="openai", model="gpt-4o-mini-2024-07-18", max_tokens=2000
        )

        # Mock the HCE processing
        with patch.object(processor, "_process_with_hce") as mock_process:
            mock_result = Mock()
            mock_result.success = True
            mock_result.data = {
                "summary_text": "AI is rapidly transforming society with both opportunities and challenges.",
                "hce_data": mock_hce_data,
                "output_file": "test_ai_analysis.md",
            }
            mock_result.metadata = {
                "provider": "openai",
                "model": "gpt-4o-mini-2024-07-18",
                "processing_time": 15.2,
                "token_usage": 1500,
            }
            mock_result.errors = []
            mock_process.return_value = mock_result

            # Process the content
            result = processor.process(self.test_content, video_id="test_video_ai")

            # Verify processing succeeded
            assert result.success is True
            assert result.data is not None
            assert "hce_data" in result.data

            hce_data = result.data["hce_data"]

            # Verify claim extraction
            assert len(hce_data["claims"]) == 5
            tier_a_claims = [c for c in hce_data["claims"] if c["tier"] == "A"]
            assert len(tier_a_claims) == 2

            # Verify entity extraction
            assert len(hce_data["people"]) == 1
            assert hce_data["people"][0]["name"] == "Dr. Jane Smith"
            assert len(hce_data["concepts"]) == 3

            # Verify relationship detection
            assert len(hce_data["relations"]) == 1
            assert hce_data["relations"][0]["type"] == "supports"

            # Verify contradiction detection
            assert len(hce_data["contradictions"]) == 1
            contradiction = hce_data["contradictions"][0]
            assert "jobs" in contradiction["claim1"]["canonical"].lower()
            assert "unemployment" in contradiction["claim2"]["canonical"].lower()

    def test_database_integration_with_hce(self):
        """Test that HCE data integrates properly with the database."""
        # Add test video
        video_id = "test_db_integration"
        self.db_service.add_video(
            video_id=video_id,
            url=f"https://youtube.com/watch?v={video_id}",
            title="Database Integration Test",
            description="Testing HCE database integration",
            duration_seconds=600,
        )

        # Create test HCE data
        hce_data = {
            "claims": [
                {
                    "claim_id": "cl1",
                    "canonical": "Database integration is working correctly",
                    "tier": "A",
                    "claim_type": "technical",
                    "evidence": ["System successfully stores and retrieves HCE data"],
                }
            ],
            "people": [{"name": "Test Person", "description": "Database tester"}],
            "concepts": [
                {
                    "name": "Database Integration",
                    "description": "Connecting HCE to storage",
                }
            ],
            "relations": [],
            "contradictions": [],
        }

        # Save HCE data
        summary_id = self.db_service.save_hce_data(
            video_id=video_id,
            hce_data=hce_data,
            summary_text="Database integration test summary",
            llm_provider="openai",
            llm_model="gpt-4o-mini-2024-07-18",
            processing_cost=0.02,
            total_tokens=500,
        )

        assert summary_id is not None

        # Retrieve and verify
        summaries = self.db_service.get_summaries_for_video(video_id)
        assert len(summaries) == 1

        summary = summaries[0]
        assert summary.processing_type == "hce"
        assert summary.hce_data_json is not None

        # Parse and validate stored data
        import json

        stored_hce_data = json.loads(summary.hce_data_json)
        assert (
            stored_hce_data["claims"][0]["canonical"]
            == "Database integration is working correctly"
        )
        assert stored_hce_data["claims"][0]["tier"] == "A"

    def test_performance_with_large_content(self):
        """Test HCE performance with larger content."""
        # Create large test content
        large_content = self.test_content * 50  # ~50x larger content

        # Mock HCE data for large content
        large_hce_data = {
            "claims": [
                {
                    "claim_id": f"cl{i}",
                    "canonical": f"Large content claim number {i}",
                    "tier": ["A", "B", "C"][i % 3],
                    "claim_type": "factual",
                    "evidence": [f"Evidence for claim {i}"],
                }
                for i in range(50)  # 50 claims
            ],
            "people": [
                {"name": f"Person {i}", "description": f"Expert {i}"} for i in range(10)
            ],
            "concepts": [
                {"name": f"Concept {i}", "description": f"Important concept {i}"}
                for i in range(20)
            ],
            "relations": [
                {"source": f"cl{i}", "target": f"cl{i+1}", "type": "supports"}
                for i in range(25)
            ],
            "contradictions": [],
        }

        processor = SummarizerProcessor(
            provider="openai", model="gpt-4o-mini-2024-07-18", max_tokens=4000
        )

        with patch.object(processor, "_process_with_hce") as mock_process:
            mock_result = Mock()
            mock_result.success = True
            mock_result.data = {
                "summary_text": "Large content analysis completed",
                "hce_data": large_hce_data,
                "output_file": "large_content_analysis.md",
            }
            mock_result.metadata = {"provider": "openai", "processing_time": 45.0}
            mock_result.errors = []
            mock_process.return_value = mock_result

            # Measure processing time
            import time

            start_time = time.time()
            result = processor.process(large_content)
            processing_time = time.time() - start_time

            # Verify results
            assert result.success is True
            assert len(result.data["hce_data"]["claims"]) == 50
            assert len(result.data["hce_data"]["people"]) == 10
            assert len(result.data["hce_data"]["concepts"]) == 20
            assert len(result.data["hce_data"]["relations"]) == 25

            # Performance assertion (should complete quickly with mocked processing)
            assert processing_time < 1.0  # Should be very fast with mocking

    def test_error_handling_and_recovery(self):
        """Test error handling in the HCE pipeline."""
        processor = SummarizerProcessor(
            provider="openai", model="gpt-4o-mini-2024-07-18", max_tokens=1000
        )

        # Test with processing failure
        with patch.object(processor, "_process_with_hce") as mock_process:
            mock_result = Mock()
            mock_result.success = False
            mock_result.data = None
            mock_result.errors = ["API rate limit exceeded", "Network timeout"]
            mock_process.return_value = mock_result

            result = processor.process(self.test_content)

            # Verify error handling
            assert result.success is False
            assert len(result.errors) == 2
            assert "rate limit" in result.errors[0].lower()

    def test_configuration_validation(self):
        """Test that HCE configuration is properly validated."""
        from src.knowledge_system.config import HCEConfig

        # Test valid configuration
        valid_config = HCEConfig(
            miner_model="gpt-4o-mini-2024-07-18",
            judge_model="gpt-4o-mini-2024-07-18",
            default_min_claim_tier="B",
            max_claims_per_document=100,
            tier_a_threshold=0.85,
            tier_b_threshold=0.65,
        )

        assert valid_config.default_min_claim_tier == "B"
        assert valid_config.tier_a_threshold == 0.85
        assert valid_config.max_claims_per_document == 100

        # Test configuration validation
        with pytest.raises(ValueError):
            # Invalid tier
            HCEConfig(default_min_claim_tier="D")

        with pytest.raises(ValueError):
            # Invalid threshold (out of range)
            HCEConfig(tier_a_threshold=1.5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
