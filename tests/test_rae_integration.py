"""
End-to-End Test for RAE Integration

Tests the complete RAE system:
1. Channel history API endpoint
2. RAE service fetching
3. Prompt injection
4. Evolution detection
5. Contradiction flagging

Run with: pytest tests/test_rae_integration.py -v
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.services.rae_service import RAEService, get_rae_service
from knowledge_system.processors.claim_evolution_detector import ClaimEvolutionDetector, get_claim_evolution_detector
from knowledge_system.processors.two_pass.extraction_pass import ExtractionPass


class TestRAEService:
    """Test RAE service functionality."""
    
    def test_rae_service_initialization(self):
        """Test that RAE service initializes correctly."""
        service = RAEService(use_production=False)
        assert service.api_url == "http://localhost:3000/api"
        
        service_prod = RAEService(use_production=True)
        assert service_prod.api_url == "https://getreceipts.org/api"
    
    def test_rae_service_singleton(self):
        """Test that get_rae_service returns singleton."""
        service1 = get_rae_service()
        service2 = get_rae_service()
        assert service1 is service2
    
    @pytest.mark.asyncio
    async def test_fetch_channel_history_no_channel_id(self):
        """Test that empty channel_id returns empty history."""
        service = RAEService(use_production=False)
        history = await service.fetch_channel_history("")
        
        assert history == {"jargon_registry": [], "top_claims": {}, "metadata": {}}
    
    def test_build_jargon_registry_section_empty(self):
        """Test that empty jargon list returns empty string."""
        service = RAEService()
        section = service.build_jargon_registry_section([])
        assert section == ""
    
    def test_build_jargon_registry_section_with_terms(self):
        """Test jargon registry section formatting."""
        service = RAEService()
        jargon_terms = [
            {
                "term": "quantitative easing",
                "definition": "Central bank policy of buying assets",
                "domain": "economics",
                "episode_id": "ep_001"
            },
            {
                "term": "backpropagation",
                "definition": "Algorithm for training neural networks",
                "domain": "technology",
                "episode_id": "ep_002"
            }
        ]
        
        section = service.build_jargon_registry_section(jargon_terms)
        
        assert "JARGON REGISTRY" in section
        assert "STRICT CONSISTENCY REQUIRED" in section
        assert "quantitative easing" in section
        assert "backpropagation" in section
        assert "Central bank policy" in section
        assert "Economics Terms:" in section
        assert "Technology Terms:" in section
    
    def test_build_claims_context_section_empty(self):
        """Test that empty claims dict returns empty string."""
        service = RAEService()
        section = service.build_claims_context_section({})
        assert section == ""
    
    def test_build_claims_context_section_with_claims(self):
        """Test claims context section formatting."""
        service = RAEService()
        claims_by_topic = {
            "economics": [
                {
                    "claim_id": "claim_001",
                    "canonical": "Inflation is caused by money supply growth",
                    "episode_id": "ep_001",
                    "created_at": "2024-01-15T00:00:00Z"
                }
            ],
            "technology": [
                {
                    "claim_id": "claim_002",
                    "canonical": "AI will transform software development",
                    "episode_id": "ep_002",
                    "created_at": "2024-02-20T00:00:00Z"
                }
            ]
        }
        
        section = service.build_claims_context_section(claims_by_topic)
        
        assert "PREVIOUS CLAIMS FROM THIS CHANNEL" in section
        assert "Inflation is caused by money supply growth" in section
        assert "AI will transform software development" in section
        assert "Economics Claims:" in section
        assert "Technology Claims:" in section
        assert "We WANT to expose contradictions" in section


class TestClaimEvolutionDetector:
    """Test claim evolution detection."""
    
    def test_detector_initialization(self):
        """Test that detector initializes correctly."""
        detector = ClaimEvolutionDetector()
        assert detector.rae_service is not None
        assert detector.taste_engine is not None
    
    def test_detector_singleton(self):
        """Test that get_claim_evolution_detector returns singleton."""
        detector1 = get_claim_evolution_detector()
        detector2 = get_claim_evolution_detector()
        assert detector1 is detector2
    
    @pytest.mark.asyncio
    async def test_analyze_claims_no_channel_id(self):
        """Test that claims without channel_id are marked as novel."""
        detector = ClaimEvolutionDetector()
        
        claims = [
            {"canonical": "Test claim 1"},
            {"canonical": "Test claim 2"}
        ]
        
        result = await detector.analyze_claims(claims, "", "2024-01-01")
        
        assert len(result) == 2
        assert all(c['evolution_status'] == 'novel' for c in result)
    
    def test_calculate_similarity_identical(self):
        """Test similarity calculation for identical texts."""
        detector = ClaimEvolutionDetector()
        
        text = "Dopamine regulates motivation, not pleasure"
        similarity = detector._calculate_similarity(text, text)
        
        # Should be very close to 1.0 (allowing for floating point precision)
        assert similarity > 0.99
    
    def test_calculate_similarity_different(self):
        """Test similarity calculation for different texts."""
        detector = ClaimEvolutionDetector()
        
        text1 = "Dopamine regulates motivation"
        text2 = "Serotonin affects mood and happiness"
        
        similarity = detector._calculate_similarity(text1, text2)
        
        # Should be low (different topics)
        assert similarity < 0.5
    
    def test_calculate_similarity_similar(self):
        """Test similarity calculation for similar but different texts."""
        detector = ClaimEvolutionDetector()
        
        text1 = "Dopamine is primarily a reward molecule"
        text2 = "Dopamine regulates motivation and anticipation, not reward itself"
        
        similarity = detector._calculate_similarity(text1, text2)
        
        # Should be moderate (same topic, different assertion)
        assert 0.4 < similarity < 0.9
    
    @pytest.mark.asyncio
    async def test_check_contradiction_with_negation(self):
        """Test contradiction detection with negation words."""
        detector = ClaimEvolutionDetector()
        
        old_claim = "Dopamine is a reward molecule"
        new_claim = "Dopamine is not a reward molecule, but rather a motivation signal"
        
        is_contradiction = await detector._check_contradiction(new_claim, old_claim)
        
        assert is_contradiction is True
    
    @pytest.mark.asyncio
    async def test_check_contradiction_compatible(self):
        """Test that compatible claims are not flagged as contradictions."""
        detector = ClaimEvolutionDetector()
        
        old_claim = "Dopamine affects motivation"
        new_claim = "Dopamine also influences learning and memory"
        
        is_contradiction = await detector._check_contradiction(new_claim, old_claim)
        
        assert is_contradiction is False


class TestPromptInjection:
    """Test RAE prompt injection in extraction pass."""
    
    def test_inject_rae_context_no_channel_id(self):
        """Test that RAE injection is skipped without channel_id."""
        # Mock LLM adapter
        class MockLLM:
            def complete(self, prompt):
                return '{"claims": [], "jargon": [], "people": [], "mental_models": []}'
        
        extraction_pass = ExtractionPass(MockLLM())
        
        base_prompt = "# EXTRACTION INSTRUCTIONS\nExtract claims..."
        metadata = {}  # No channel_id
        
        result = extraction_pass._inject_rae_context(base_prompt, metadata)
        
        # Should return unchanged prompt
        assert result == base_prompt
    
    def test_inject_rae_context_with_empty_history(self):
        """Test RAE injection with empty history."""
        class MockLLM:
            def complete(self, prompt):
                return '{"claims": [], "jargon": [], "people": [], "mental_models": []}'
        
        extraction_pass = ExtractionPass(MockLLM())
        
        base_prompt = "# EXTRACTION INSTRUCTIONS\nExtract claims..."
        metadata = {"channel_id": "UC_test123"}
        
        # This will try to fetch from API (will fail in test environment)
        result = extraction_pass._inject_rae_context(base_prompt, metadata)
        
        # Should handle error gracefully and return original prompt
        assert "# EXTRACTION INSTRUCTIONS" in result


class TestEndToEnd:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_rae_pipeline_simulation(self):
        """
        Simulate full RAE pipeline with mock data.
        
        Scenario: Processing 3 episodes from same channel
        - Episode 1: Novel claim about dopamine
        - Episode 2: Duplicate claim (same assertion)
        - Episode 3: Contradiction (opposite assertion)
        """
        detector = ClaimEvolutionDetector()
        
        # Episode 1: Novel claim
        episode1_claims = [
            {"canonical": "Dopamine is primarily a reward molecule", "importance": 8.5}
        ]
        
        result1 = await detector.analyze_claims(
            episode1_claims,
            channel_id="",  # No history yet
            episode_date="2024-01-01"
        )
        
        assert len(result1) == 1
        assert result1[0]['evolution_status'] == 'novel'
        
        # Episode 2: Duplicate (would need actual API call)
        # Episode 3: Contradiction (would need actual API call)
        # These require GetReceipts API to be running
        
        print("✅ Basic RAE pipeline simulation passed")
        print("   For full integration test, run with GetReceipts API running")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
