"""
Tests for Claims-First Pipeline

Comprehensive test suite for the claims-first architecture including:
- TranscriptFetcher
- TimestampMatcher
- LazySpeakerAttributor
- ClaimsFirstPipeline
- Integration tests
- A/B comparison tests vs speaker-first
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.processors.claims_first.config import (
    ClaimsFirstConfig,
    TranscriptSource,
    EvaluatorModel,
)
from knowledge_system.processors.claims_first.transcript_fetcher import (
    TranscriptFetcher,
    TranscriptResult,
    TranscriptSegment,
    TranscriptWord,
    TranscriptSourceType,
)
from knowledge_system.processors.claims_first.timestamp_matcher import (
    TimestampMatcher,
    TimestampResult,
)
from knowledge_system.processors.claims_first.lazy_speaker_attribution import (
    LazySpeakerAttributor,
    SpeakerAttribution,
)
from knowledge_system.processors.claims_first.pipeline import (
    ClaimsFirstPipeline,
    ClaimsFirstResult,
    ClaimWithMetadata,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_transcript_result():
    """Create a sample TranscriptResult for testing."""
    segments = [
        TranscriptSegment(text="Hello and welcome to the show.", start=0.0, duration=3.0),
        TranscriptSegment(text="Today we're talking about AI.", start=3.0, duration=2.5),
        TranscriptSegment(text="I think AI will transform everything.", start=5.5, duration=3.0),
        TranscriptSegment(text="That's a bold claim.", start=8.5, duration=2.0),
        TranscriptSegment(text="The evidence shows that 80% of jobs will change.", start=10.5, duration=4.0),
        TranscriptSegment(text="Where does that number come from?", start=14.5, duration=2.0),
        TranscriptSegment(text="It's from a recent McKinsey study.", start=16.5, duration=2.5),
    ]
    
    words = [
        TranscriptWord(word="Hello", start=0.0, end=0.3),
        TranscriptWord(word="and", start=0.3, end=0.4),
        TranscriptWord(word="welcome", start=0.4, end=0.8),
        TranscriptWord(word="to", start=0.8, end=0.9),
        TranscriptWord(word="the", start=0.9, end=1.0),
        TranscriptWord(word="show", start=1.0, end=1.3),
        TranscriptWord(word="Today", start=3.0, end=3.3),
        TranscriptWord(word="we're", start=3.3, end=3.5),
        TranscriptWord(word="talking", start=3.5, end=3.8),
        TranscriptWord(word="about", start=3.8, end=4.0),
        TranscriptWord(word="AI", start=4.0, end=4.3),
    ]
    
    return TranscriptResult(
        text="Hello and welcome to the show. Today we're talking about AI. I think AI will transform everything. That's a bold claim. The evidence shows that 80% of jobs will change. Where does that number come from? It's from a recent McKinsey study.",
        segments=segments,
        words=words,
        source_type=TranscriptSourceType.WHISPER,
        video_id="test123",
        quality_score=0.95,
        processing_time_seconds=120.0,
        timestamp_precision="word",
    )


@pytest.fixture
def sample_claims():
    """Create sample claims for testing."""
    return [
        {
            "canonical": "AI will transform 80% of jobs",
            "evidence": "The evidence shows that 80% of jobs will change",
            "importance": 8,
            "tier": "A",
            "timestamp_start": 10.5,
        },
        {
            "canonical": "AI is a transformative technology",
            "evidence": "I think AI will transform everything",
            "importance": 6,
            "tier": "B",
            "timestamp_start": 5.5,
        },
        {
            "canonical": "McKinsey conducted research on AI job impact",
            "evidence": "It's from a recent McKinsey study",
            "importance": 5,
            "tier": "C",
            "timestamp_start": 16.5,
        },
    ]


@pytest.fixture
def sample_metadata():
    """Create sample episode metadata."""
    return {
        "title": "The Future of AI - Interview with Dr. Smith",
        "description": "In this episode, host John interviews Dr. Jane Smith, AI researcher at MIT, about the future of artificial intelligence.",
        "channel_name": "Tech Insights Podcast",
        "participants": ["John Host", "Dr. Jane Smith"],
    }


# =============================================================================
# ClaimsFirstConfig Tests
# =============================================================================


class TestClaimsFirstConfig:
    """Tests for ClaimsFirstConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ClaimsFirstConfig()
        
        assert config.enabled is False
        assert config.transcript_source == TranscriptSource.AUTO
        assert config.youtube_quality_threshold == 0.7
        assert config.evaluator_model == EvaluatorModel.CONFIGURABLE
        assert config.lazy_attribution_min_importance == 7
        assert config.store_candidates is True
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = ClaimsFirstConfig(youtube_quality_threshold=0.5)
        assert config.youtube_quality_threshold == 0.5
        
        # Invalid threshold
        with pytest.raises(ValueError):
            ClaimsFirstConfig(youtube_quality_threshold=1.5)
        
        # Invalid importance
        with pytest.raises(ValueError):
            ClaimsFirstConfig(lazy_attribution_min_importance=15)
    
    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            "enabled": True,
            "transcript_source": "youtube",
            "evaluator_model": "claude",
            "lazy_attribution_min_importance": 8,
        }
        
        config = ClaimsFirstConfig.from_dict(config_dict)
        
        assert config.enabled is True
        assert config.transcript_source == TranscriptSource.YOUTUBE
        assert config.evaluator_model == EvaluatorModel.CLAUDE
        assert config.lazy_attribution_min_importance == 8
    
    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config = ClaimsFirstConfig(enabled=True)
        config_dict = config.to_dict()
        
        assert config_dict["enabled"] is True
        assert config_dict["transcript_source"] == "auto"
        assert "miner_model" in config_dict
    
    def test_get_evaluator_model_name(self):
        """Test evaluator model name resolution."""
        # Gemini config
        config = ClaimsFirstConfig(evaluator_model=EvaluatorModel.GEMINI)
        assert "gemini" in config.get_evaluator_model_name()
        
        # Claude config
        config = ClaimsFirstConfig(evaluator_model=EvaluatorModel.CLAUDE)
        assert "claude" in config.get_evaluator_model_name()


# =============================================================================
# TranscriptFetcher Tests
# =============================================================================


class TestTranscriptFetcher:
    """Tests for TranscriptFetcher."""
    
    def test_extract_youtube_video_id(self):
        """Test YouTube video ID extraction from various URL formats."""
        fetcher = TranscriptFetcher()
        
        # Standard watch URL
        assert fetcher._extract_youtube_video_id(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ) == "dQw4w9WgXcQ"
        
        # Short URL
        assert fetcher._extract_youtube_video_id(
            "https://youtu.be/dQw4w9WgXcQ"
        ) == "dQw4w9WgXcQ"
        
        # Embed URL
        assert fetcher._extract_youtube_video_id(
            "https://www.youtube.com/embed/dQw4w9WgXcQ"
        ) == "dQw4w9WgXcQ"
        
        # Non-YouTube URL
        assert fetcher._extract_youtube_video_id(
            "https://vimeo.com/12345"
        ) is None
        
        # Empty string
        assert fetcher._extract_youtube_video_id("") is None
    
    def test_estimate_youtube_quality(self):
        """Test YouTube transcript quality estimation."""
        fetcher = TranscriptFetcher()
        
        # Good quality transcript
        good_segments = [
            TranscriptSegment(text="This is a normal sentence with good content.", start=0, duration=3),
            TranscriptSegment(text="Another sentence that makes sense.", start=3, duration=2),
        ]
        good_text = " ".join(s.text for s in good_segments)
        quality = fetcher._estimate_youtube_quality(good_segments, good_text)
        assert quality >= 0.8
        
        # Poor quality with many markers
        poor_segments = [
            TranscriptSegment(text="[Music] [Music] [Music]", start=0, duration=10),
            TranscriptSegment(text="[Inaudible] something [Music]", start=10, duration=5),
        ]
        poor_text = " ".join(s.text for s in poor_segments)
        quality = fetcher._estimate_youtube_quality(poor_segments, poor_text)
        assert quality < 0.8
    
    def test_transcript_result_properties(self, sample_transcript_result):
        """Test TranscriptResult properties."""
        result = sample_transcript_result
        
        assert result.has_word_timestamps is True
        assert len(result.segments) == 7
        assert result.source_type == TranscriptSourceType.WHISPER


# =============================================================================
# TimestampMatcher Tests
# =============================================================================


class TestTimestampMatcher:
    """Tests for TimestampMatcher."""
    
    def test_exact_match(self, sample_transcript_result):
        """Test exact matching of evidence quote."""
        matcher = TimestampMatcher()
        
        claim = {
            "evidence": "The evidence shows that 80% of jobs will change"
        }
        
        result = matcher.match_claim_to_timestamps(claim, sample_transcript_result)
        
        assert result is not None
        assert result.confidence >= 0.8
        assert result.timestamp_start >= 10.0
    
    def test_fuzzy_match(self, sample_transcript_result):
        """Test fuzzy matching with paraphrased quote."""
        matcher = TimestampMatcher()
        
        # Slightly different wording
        claim = {
            "evidence": "evidence shows 80% of jobs are changing"
        }
        
        result = matcher.match_claim_to_timestamps(
            claim, sample_transcript_result, threshold=0.5
        )
        
        # Should still find a match, though with lower confidence
        assert result is not None
        assert result.match_method in ["fuzzy", "fallback"]
    
    def test_no_evidence(self, sample_transcript_result):
        """Test handling of claim without evidence."""
        matcher = TimestampMatcher()
        
        claim = {"canonical": "Some claim"}  # No evidence field
        
        result = matcher.match_claim_to_timestamps(claim, sample_transcript_result)
        assert result is None
    
    def test_normalize_text(self):
        """Test text normalization."""
        matcher = TimestampMatcher()
        
        text = "Hello, World! How's it going?"
        normalized = matcher._normalize_text(text)
        
        assert normalized == "hello world how's it going"
    
    def test_match_multiple_claims(self, sample_transcript_result, sample_claims):
        """Test matching multiple claims."""
        matcher = TimestampMatcher()
        
        results = matcher.match_multiple_claims(
            sample_claims, sample_transcript_result
        )
        
        assert len(results) == len(sample_claims)
        
        # Check that at least some matches were found
        matched = sum(1 for _, result in results if result is not None)
        assert matched > 0


# =============================================================================
# LazySpeakerAttributor Tests
# =============================================================================


class TestLazySpeakerAttributor:
    """Tests for LazySpeakerAttributor."""
    
    def test_extract_participants_from_description(self):
        """Test participant extraction from description."""
        attributor = LazySpeakerAttributor()
        
        description = "Guest: Dr. Jane Smith, PhD. Host: John Doe interviews about AI."
        participants = attributor._extract_participants_from_description(description)
        
        assert len(participants) > 0
        # Should find at least one name
        names = [p.lower() for p in participants]
        assert any("smith" in n or "doe" in n for n in names)
    
    def test_extract_context_window(self):
        """Test context window extraction."""
        attributor = LazySpeakerAttributor(context_window_seconds=30)
        
        transcript = "Start of transcript. " * 50 + "Middle content here. " * 50 + "End of transcript."
        
        context = attributor._extract_context_window(transcript, timestamp=60.0)
        
        # Should return some content
        assert len(context) > 0
        assert len(context) < len(transcript)
    
    def test_parse_attribution_response(self):
        """Test parsing LLM response."""
        attributor = LazySpeakerAttributor()
        
        claim = {"id": "test123"}
        
        # Valid JSON response
        response = '{"speaker_name": "Dr. Jane Smith", "confidence": 0.85, "is_host": false, "reasoning": ["Expert content"]}'
        
        result = attributor._parse_attribution_response(response, claim)
        
        assert result.speaker_name == "Dr. Jane Smith"
        assert result.confidence == 0.85
        assert result.is_host is False
    
    def test_speaker_attribution_properties(self):
        """Test SpeakerAttribution properties."""
        attr = SpeakerAttribution(
            speaker_name="Dr. Jane Smith",
            confidence=0.85,
            reasoning=["Expert content"],
            is_host=False,
        )
        
        assert attr.is_confident is True
        assert attr.is_unknown is False
        
        # Unknown speaker
        unknown = SpeakerAttribution(speaker_name="Unknown", confidence=0.3)
        assert unknown.is_confident is False
        assert unknown.is_unknown is True
    
    def test_batch_attribution_filters_by_importance(self, sample_claims, sample_metadata):
        """Test that batch attribution skips low-importance claims."""
        attributor = LazySpeakerAttributor()
        
        transcript = "Some transcript text about AI and jobs."
        
        # Mock the LLM call to avoid actual API calls
        with patch.object(attributor, 'attribute_speaker') as mock_attr:
            mock_attr.return_value = SpeakerAttribution(
                speaker_name="Dr. Jane Smith",
                confidence=0.8,
            )
            
            results = attributor.attribute_speakers_batch(
                sample_claims, transcript, sample_metadata, min_importance=7
            )
        
        # Only importance >= 7 claims should have attribution attempted
        attributed = [r for _, r in results if r is not None]
        skipped = [r for _, r in results if r is None]
        
        # Our sample has 1 claim with importance >= 7 and 2 below
        assert len(attributed) == 1
        assert len(skipped) == 2


# =============================================================================
# ClaimsFirstPipeline Tests
# =============================================================================


class TestClaimsFirstPipeline:
    """Tests for ClaimsFirstPipeline."""
    
    def test_pipeline_initialization(self):
        """Test pipeline initialization with default config."""
        pipeline = ClaimsFirstPipeline()
        
        assert pipeline.config.enabled is False
        assert pipeline.transcript_fetcher is not None
        assert pipeline.timestamp_matcher is not None
        assert pipeline.speaker_attributor is not None
    
    def test_pipeline_initialization_with_config(self):
        """Test pipeline initialization with custom config."""
        config = ClaimsFirstConfig(
            enabled=True,
            lazy_attribution_min_importance=8,
        )
        
        pipeline = ClaimsFirstPipeline(config=config)
        
        assert pipeline.config.enabled is True
        assert pipeline.config.lazy_attribution_min_importance == 8
    
    def test_pipeline_info(self):
        """Test get_pipeline_info."""
        config = ClaimsFirstConfig(enabled=True, evaluator_model=EvaluatorModel.CLAUDE)
        pipeline = ClaimsFirstPipeline(config=config)
        
        info = pipeline.get_pipeline_info()
        
        assert info["enabled"] is True
        assert info["evaluator_model"] == "claude"
        assert "miner_model" in info
    
    def test_claim_with_metadata(self, sample_claims):
        """Test ClaimWithMetadata properties."""
        claim = sample_claims[0]  # importance = 8
        
        cwm = ClaimWithMetadata(claim=claim)
        
        assert cwm.canonical == "AI will transform 80% of jobs"
        assert cwm.importance == 8
        assert cwm.tier == "A"
    
    def test_claim_tiers(self):
        """Test tier calculation for different importance levels."""
        # A tier (8-10)
        cwm = ClaimWithMetadata(claim={"importance": 9})
        assert cwm.tier == "A"
        
        # B tier (6-7)
        cwm = ClaimWithMetadata(claim={"importance": 7})
        assert cwm.tier == "B"
        
        # C tier (4-5)
        cwm = ClaimWithMetadata(claim={"importance": 5})
        assert cwm.tier == "C"
        
        # D tier (0-3)
        cwm = ClaimWithMetadata(claim={"importance": 2})
        assert cwm.tier == "D"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for claims-first pipeline."""
    
    @pytest.mark.integration
    def test_full_pipeline_with_mocks(self, sample_transcript_result, sample_claims, sample_metadata):
        """Test full pipeline with mocked LLM calls."""
        config = ClaimsFirstConfig(
            enabled=True,
            transcript_source=TranscriptSource.WHISPER,
        )
        
        pipeline = ClaimsFirstPipeline(config=config)
        
        # Mock the components
        with patch.object(pipeline.transcript_fetcher, 'get_transcript') as mock_transcript, \
             patch.object(pipeline, '_get_unified_miner') as mock_get_miner, \
             patch.object(pipeline, '_get_flagship_evaluator') as mock_get_evaluator:
            
            # Setup mocks
            mock_transcript.return_value = sample_transcript_result
            
            mock_miner = MagicMock()
            mock_miner.mine.return_value = MagicMock(claims=sample_claims)
            mock_get_miner.return_value = mock_miner
            
            mock_evaluator = MagicMock()
            mock_evaluator.evaluate.return_value = sample_claims
            mock_get_evaluator.return_value = mock_evaluator
            
            # Run pipeline
            result = pipeline.process(
                source_url="https://youtube.com/watch?v=test123",
                audio_path=Path("/tmp/test.mp3"),
                metadata=sample_metadata,
            )
            
            # Verify result
            assert isinstance(result, ClaimsFirstResult)
            assert len(result.claims) > 0
            assert result.transcript is not None


# =============================================================================
# Comparison Tests (A/B vs Speaker-First)
# =============================================================================


class TestComparisonWithSpeakerFirst:
    """Tests comparing claims-first with speaker-first approach."""
    
    def test_claims_first_skips_diarization(self):
        """Test that claims-first mode disables diarization."""
        from knowledge_system.processors.audio_processor import AudioProcessor
        
        # Claims-first mode
        processor = AudioProcessor(use_claims_first=True)
        
        assert processor.use_claims_first is True
        assert processor.enable_diarization is False
        assert processor.require_diarization is False
    
    def test_speaker_first_uses_diarization(self):
        """Test that speaker-first mode can enable diarization."""
        from knowledge_system.processors.audio_processor import AudioProcessor
        
        # Speaker-first mode with diarization
        processor = AudioProcessor(
            use_claims_first=False,
            enable_diarization=True,
        )
        
        assert processor.use_claims_first is False
        assert processor.enable_diarization is True


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

