"""
Tests for Batch Pipeline with Prompt Caching

Verifies:
1. ProcessingMode configuration
2. Batch client request building
3. Mode detection logic (realtime/batch/auto)
4. Cache-optimized request sorting
5. Flagship evaluation segment flagging
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import the modules we're testing
from knowledge_system.config import BatchProcessingConfig, ProcessingMode
from knowledge_system.core.batch_client import (
    BaseBatchClient,
    BatchJob,
    BatchPipelineResult,
    BatchRequest,
    BatchResult,
    BatchStatus,
)


class TestBatchProcessingConfig:
    """Test BatchProcessingConfig from config.py"""
    
    def test_default_values(self):
        """Test default configuration values."""
        from pydantic import ValidationError
        
        # Create a settings object to test the BatchProcessingConfig
        from knowledge_system.config import BatchProcessingConfig
        
        # Test that we can create an instance
        config = BatchProcessingConfig()
        
        # Verify defaults
        assert config.mode == "realtime"
        assert config.auto_batch_threshold == 100
        assert config.batch_provider == "openai"
        assert config.batch_mining_model == "gpt-5-mini"
        assert config.batch_remine_model == "claude-3.7-sonnet"
        assert config.remine_enabled is True
        assert config.remine_confidence_threshold == 4.0
        assert config.enable_cache_optimization is True
        assert config.sequential_batch_submission is True
    
    def test_mode_validation(self):
        """Test that mode validation works."""
        from pydantic import ValidationError
        
        # Valid modes
        for mode in ["realtime", "batch", "auto"]:
            config = BatchProcessingConfig(mode=mode)
            assert config.mode == mode
        
        # Invalid mode should raise validation error
        with pytest.raises(ValidationError):
            BatchProcessingConfig(mode="invalid")
    
    def test_provider_validation(self):
        """Test provider validation."""
        from pydantic import ValidationError
        
        # Valid providers
        for provider in ["openai", "anthropic"]:
            config = BatchProcessingConfig(batch_provider=provider)
            assert config.batch_provider == provider
        
        # Invalid provider
        with pytest.raises(ValidationError):
            BatchProcessingConfig(batch_provider="invalid")


class TestBatchRequest:
    """Test BatchRequest data class."""
    
    def test_openai_format(self):
        """Test conversion to OpenAI batch format."""
        req = BatchRequest(
            custom_id="test:001",
            messages=[{"role": "user", "content": "Extract claims from this."}],
            model="gpt-5-mini",
            temperature=0.1,
            max_tokens=4000
        )
        
        openai_format = req.to_openai_format()
        
        assert openai_format["custom_id"] == "test:001"
        assert openai_format["method"] == "POST"
        assert openai_format["url"] == "/v1/chat/completions"
        assert openai_format["body"]["model"] == "gpt-5-mini"
        assert openai_format["body"]["temperature"] == 0.1
        assert openai_format["body"]["max_tokens"] == 4000
    
    def test_anthropic_format(self):
        """Test conversion to Anthropic batch format."""
        req = BatchRequest(
            custom_id="test:002",
            messages=[{"role": "user", "content": "Evaluate this claim."}],
            model="claude-3.7-sonnet",
            temperature=0.2,
            max_tokens=6000
        )
        
        anthropic_format = req.to_anthropic_format()
        
        assert anthropic_format["custom_id"] == "test:002"
        assert anthropic_format["params"]["model"] == "claude-3.7-sonnet"
        assert anthropic_format["params"]["temperature"] == 0.2
        assert anthropic_format["params"]["max_tokens"] == 6000


class TestBatchResult:
    """Test BatchResult data class."""
    
    def test_token_extraction(self):
        """Test token count extraction from usage."""
        result = BatchResult(
            custom_id="test:001",
            success=True,
            content='{"claims": []}',
            usage={
                "prompt_tokens": 3000,
                "completion_tokens": 500,
                "cached_tokens": 2500
            }
        )
        
        assert result.tokens_input == 3000
        assert result.tokens_output == 500
        assert result.tokens_cached == 2500
    
    def test_json_parsing(self):
        """Test JSON content parsing."""
        result = BatchResult(
            custom_id="test:001",
            success=True,
            content='{"claims": [{"text": "Test claim"}]}'
        )
        
        parsed = result.parse_json_content()
        assert parsed is not None
        assert "claims" in parsed
        assert len(parsed["claims"]) == 1
    
    def test_invalid_json_parsing(self):
        """Test handling of invalid JSON."""
        result = BatchResult(
            custom_id="test:001",
            success=True,
            content="This is not valid JSON"
        )
        
        parsed = result.parse_json_content()
        assert parsed is None


class TestBatchJob:
    """Test BatchJob data class."""
    
    def test_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        job = BatchJob(
            batch_id="batch_001",
            provider="openai",
            status=BatchStatus.COMPLETED,
            created_at=MagicMock(),
            request_count=100,
            total_input_tokens=10000,
            cached_tokens=7500
        )
        
        assert job.cache_hit_rate == 0.75
    
    def test_cache_hit_rate_zero_tokens(self):
        """Test cache hit rate with zero tokens."""
        job = BatchJob(
            batch_id="batch_001",
            provider="openai",
            status=BatchStatus.COMPLETED,
            created_at=MagicMock(),
            request_count=0,
            total_input_tokens=0,
            cached_tokens=0
        )
        
        assert job.cache_hit_rate == 0.0
    
    def test_is_complete(self):
        """Test completion status detection."""
        for status in [BatchStatus.COMPLETED, BatchStatus.FAILED, 
                       BatchStatus.EXPIRED, BatchStatus.CANCELLED]:
            job = BatchJob(
                batch_id="batch_001",
                provider="openai",
                status=status,
                created_at=MagicMock(),
                request_count=10
            )
            assert job.is_complete is True
        
        for status in [BatchStatus.PENDING, BatchStatus.IN_PROGRESS,
                       BatchStatus.VALIDATING, BatchStatus.FINALIZING]:
            job = BatchJob(
                batch_id="batch_001",
                provider="openai",
                status=status,
                created_at=MagicMock(),
                request_count=10
            )
            assert job.is_complete is False


class TestFlagshipEvaluationSegmentFlagging:
    """Test flagship evaluator segment flagging methods."""
    
    def test_get_low_confidence_segment_ids(self):
        """Test identification of low-confidence segments."""
        from knowledge_system.processors.hce.flagship_evaluator import (
            FlagshipEvaluationOutput
        )
        
        raw_output = {
            "evaluated_claims": [
                {
                    "original_claim_text": "Claim 1",
                    "decision": "accept",
                    "confidence_final": 8,
                    "evidence_spans": [{"segment_id": "seg_001"}]
                },
                {
                    "original_claim_text": "Claim 2",
                    "decision": "accept",
                    "confidence_final": 3,  # Low confidence
                    "evidence_spans": [{"segment_id": "seg_002"}]
                },
                {
                    "original_claim_text": "Claim 3",
                    "decision": "accept",
                    "confidence_final": 2,  # Low confidence
                    "evidence_spans": [{"segment_id": "seg_003"}]
                },
            ],
            "summary_assessment": {}
        }
        
        output = FlagshipEvaluationOutput(raw_output)
        
        # With default threshold of 4.0
        low_conf = output.get_low_confidence_segment_ids(threshold=4.0)
        
        assert "seg_002" in low_conf
        assert "seg_003" in low_conf
        assert "seg_001" not in low_conf
    
    def test_get_empty_segment_ids(self):
        """Test identification of empty segments."""
        from knowledge_system.processors.hce.flagship_evaluator import (
            FlagshipEvaluationOutput
        )
        
        raw_output = {
            "evaluated_claims": [
                {
                    "original_claim_text": "Claim 1",
                    "decision": "accept",
                    "confidence_final": 8,
                    "evidence_spans": [{"segment_id": "seg_001"}]
                }
            ],
            "summary_assessment": {}
        }
        
        output = FlagshipEvaluationOutput(raw_output)
        
        # Check for empty segments
        all_segments = {"seg_001", "seg_002", "seg_003", "seg_004"}
        empty = output.get_empty_segment_ids(all_segments)
        
        assert "seg_002" in empty
        assert "seg_003" in empty
        assert "seg_004" in empty
        assert "seg_001" not in empty
    
    def test_get_segments_for_remine(self):
        """Test combined segment flagging for re-mining."""
        from knowledge_system.processors.hce.flagship_evaluator import (
            FlagshipEvaluationOutput
        )
        
        raw_output = {
            "evaluated_claims": [
                {
                    "original_claim_text": "Claim 1",
                    "decision": "accept",
                    "confidence_final": 8,
                    "evidence_spans": [{"segment_id": "seg_001"}]
                },
                {
                    "original_claim_text": "Claim 2",
                    "decision": "accept",
                    "confidence_final": 2,
                    "evidence_spans": [{"segment_id": "seg_002"}]
                }
            ],
            "summary_assessment": {}
        }
        
        output = FlagshipEvaluationOutput(raw_output)
        
        all_segments = {"seg_001", "seg_002", "seg_003", "seg_004", "seg_005"}
        
        # Get segments for remine with 15% max
        flagged = output.get_segments_for_remine(
            all_segments,
            confidence_threshold=4.0,
            include_empty=True,
            max_percent=100  # No limit for test
        )
        
        # Should include seg_002 (low confidence) and seg_003, seg_004, seg_005 (empty)
        assert "seg_002" in flagged
        assert "seg_003" in flagged
        assert "seg_004" in flagged
        assert "seg_005" in flagged
        assert "seg_001" not in flagged  # High confidence, not empty


class TestModeDetection:
    """Test processing mode detection logic."""
    
    def test_realtime_mode_forced(self):
        """Test that realtime mode is used when configured."""
        # This tests the config's influence on mode selection
        config = BatchProcessingConfig(mode="realtime")
        assert config.mode == "realtime"
    
    def test_batch_mode_forced(self):
        """Test that batch mode is used when configured."""
        config = BatchProcessingConfig(mode="batch")
        assert config.mode == "batch"
    
    def test_auto_threshold(self):
        """Test auto mode threshold configuration."""
        config = BatchProcessingConfig(
            mode="auto",
            auto_batch_threshold=50
        )
        assert config.auto_batch_threshold == 50


class TestCacheOptimization:
    """Test cache optimization features."""
    
    def test_request_sorting(self):
        """Test that requests are sorted for cache optimization."""
        from knowledge_system.core.batch_pipeline import BatchPipeline, BatchPipelineConfig
        
        config = BatchPipelineConfig(enable_cache_optimization=True)
        pipeline = BatchPipeline(config)
        
        # Create requests from different sources
        requests = [
            BatchRequest(custom_id="source_b:seg_1", messages=[], model="gpt-5-mini"),
            BatchRequest(custom_id="source_a:seg_1", messages=[], model="gpt-5-mini"),
            BatchRequest(custom_id="source_b:seg_2", messages=[], model="gpt-5-mini"),
            BatchRequest(custom_id="source_a:seg_2", messages=[], model="gpt-5-mini"),
        ]
        
        sorted_requests = pipeline._sort_for_cache_hits(requests)
        
        # Should be grouped by source_id for better caching
        assert sorted_requests[0].custom_id.startswith("source_a")
        assert sorted_requests[1].custom_id.startswith("source_a")
        assert sorted_requests[2].custom_id.startswith("source_b")
        assert sorted_requests[3].custom_id.startswith("source_b")
    
    def test_cache_stats_tracking(self):
        """Test that cache stats are properly accumulated."""
        from knowledge_system.core.batch_pipeline import BatchPipeline, BatchPipelineConfig
        
        config = BatchPipelineConfig()
        pipeline = BatchPipeline(config)
        
        # Simulate adding cache stats
        pipeline._cache_stats["total_input_tokens"] = 10000
        pipeline._cache_stats["cached_tokens"] = 7500
        
        stats = pipeline.get_cache_stats()
        
        assert stats["total_input_tokens"] == 10000
        assert stats["cached_tokens"] == 7500
        assert stats["cache_hit_rate"] == 0.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

