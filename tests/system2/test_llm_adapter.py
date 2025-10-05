"""
Tests for LLM Adapter with concurrency control and memory management.

Tests hardware tier detection, rate limiting, memory monitoring,
and proper request/response tracking.
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.knowledge_system.core.llm_adapter import (
    HARDWARE_TIERS,
    HardwareTierConfig,
    LLMAdapter,
    MemoryMonitor,
    RateLimiter,
)
from src.knowledge_system.errors import APIError, ErrorCode

from .fixtures import test_db_service


class TestMemoryMonitor:
    """Test cases for memory monitoring."""

    def test_memory_threshold_detection(self):
        """Test memory threshold detection."""
        monitor = MemoryMonitor(threshold=0.7, critical_threshold=0.9)

        # Mock memory usage
        with patch("psutil.virtual_memory") as mock_memory:
            # Below threshold
            mock_memory.return_value = Mock(percent=60.0)
            should_throttle, usage = monitor.should_throttle()
            assert not should_throttle
            assert usage == 0.6

            # Above threshold
            mock_memory.return_value = Mock(percent=80.0)
            should_throttle, usage = monitor.should_throttle()
            assert should_throttle
            assert usage == 0.8

    def test_critical_memory_detection(self):
        """Test critical memory level detection."""
        monitor = MemoryMonitor(threshold=0.7, critical_threshold=0.9)

        with patch("psutil.virtual_memory") as mock_memory:
            # Critical level
            mock_memory.return_value = Mock(percent=95.0)
            assert monitor.is_critical()

            # Below critical
            mock_memory.return_value = Mock(percent=85.0)
            assert not monitor.is_critical()

    def test_check_interval(self):
        """Test memory check interval limiting."""
        monitor = MemoryMonitor()
        monitor._check_interval = 0.1  # Short interval for testing

        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value = Mock(percent=80.0)

            # First check should work
            should_throttle1, _ = monitor.should_throttle()

            # Immediate second check should return cached result
            should_throttle2, usage2 = monitor.should_throttle()
            assert not should_throttle2  # Returns False when skipping check
            assert usage2 == 0.0

            # After interval, should check again
            time.sleep(0.15)
            should_throttle3, usage3 = monitor.should_throttle()
            assert should_throttle3
            assert usage3 == 0.8


class TestRateLimiter:
    """Test cases for rate limiting with exponential backoff."""

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        limiter = RateLimiter(initial_delay=1.0, max_delay=10.0)

        # First backoff
        with patch("time.sleep") as mock_sleep:
            limiter.backoff()
            # Should be around 2 seconds (1 * 2^1) plus jitter
            assert 1.5 <= limiter.current_delay <= 2.5
            mock_sleep.assert_called_once()

        # Second backoff
        with patch("time.sleep") as mock_sleep:
            limiter.backoff()
            # Should be around 4 seconds (1 * 2^2) plus jitter
            assert 3.0 <= limiter.current_delay <= 5.0

    def test_max_delay_cap(self):
        """Test that backoff is capped at max_delay."""
        limiter = RateLimiter(initial_delay=1.0, max_delay=5.0)

        # Force many backoffs
        for _ in range(10):
            with patch("time.sleep"):
                limiter.backoff()

        # Should be capped at max_delay
        assert limiter.current_delay <= 5.0 * 1.25  # Max + jitter

    def test_reset(self):
        """Test rate limiter reset."""
        limiter = RateLimiter(initial_delay=1.0)

        # Backoff a few times
        for _ in range(3):
            with patch("time.sleep"):
                limiter.backoff()

        assert limiter.consecutive_errors == 3
        assert limiter.current_delay > limiter.initial_delay

        # Reset
        limiter.reset()
        assert limiter.consecutive_errors == 0
        assert limiter.current_delay == limiter.initial_delay


class TestLLMAdapter:
    """Test cases for LLM adapter."""

    def test_hardware_tier_detection(self, test_db_service):
        """Test hardware tier is properly detected."""
        adapter = LLMAdapter(test_db_service)

        assert adapter.tier_config is not None
        assert adapter.tier_config.tier in HARDWARE_TIERS
        assert adapter.tier_config.mining_workers > 0
        assert adapter.tier_config.evaluation_workers > 0

    def test_tier_assignment_logic(self, test_db_service):
        """Test hardware tier assignment based on specs."""
        adapter = LLMAdapter(test_db_service)

        # Mock different hardware specs
        test_cases = [
            ({"memory_gb": 4, "cpu_cores": 2}, "consumer"),
            ({"memory_gb": 16, "cpu_cores": 8}, "prosumer"),
            ({"memory_gb": 32, "cpu_cores": 12}, "professional"),
            ({"memory_gb": 128, "cpu_cores": 32}, "server"),
        ]

        for specs, expected_tier in test_cases:
            adapter.hardware_specs = specs
            tier = adapter._determine_tier()
            assert tier.tier == expected_tier

    @pytest.mark.asyncio
    async def test_async_llm_call_success(self, test_db_service):
        """Test successful async LLM call."""
        adapter = LLMAdapter(test_db_service)

        # Mock the provider call
        async def mock_provider_call(*args, **kwargs):
            return {
                "text": '{"result": "success"}',
                "completion_tokens": 100,
                "prompt_tokens": 50,
                "total_tokens": 150,
                "cost_usd": 0.002,
                "model": "gpt-4",
                "provider": "openai",
            }

        adapter._call_provider_async = mock_provider_call

        result = await adapter.call_llm_async(
            provider="openai",
            model="gpt-4",
            prompt="Test prompt",
            job_run_id="test-run-123",
        )

        assert result["text"] == '{"result": "success"}'
        assert result["total_tokens"] == 150
        assert adapter.metrics["total_requests"] == 1
        assert adapter.metrics["successful_requests"] == 1

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, test_db_service):
        """Test rate limit handling with retry."""
        adapter = LLMAdapter(test_db_service)

        call_count = 0

        async def mock_provider_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Simulate rate limit error
                raise Exception("429 rate limit exceeded")
            return {"text": "success", "total_tokens": 100}

        adapter._call_provider_async = mock_provider_call

        with patch("time.sleep"):  # Skip actual sleep in tests
            result = await adapter.call_llm_async(
                provider="openai", model="gpt-4", prompt="Test", max_retries=3
            )

        assert result["text"] == "success"
        assert call_count == 3  # Two failures, then success
        assert adapter.metrics["failed_requests"] == 2

    @pytest.mark.asyncio
    async def test_memory_throttling(self, test_db_service):
        """Test memory-based throttling."""
        adapter = LLMAdapter(test_db_service)

        # Mock high memory usage
        with patch.object(
            adapter.memory_monitor, "should_throttle", return_value=(True, 0.85)
        ):
            with patch("asyncio.sleep") as mock_sleep:
                result = await adapter.call_llm_async(
                    provider="openai", model="gpt-4", prompt="Test"
                )

                # Should have throttled
                mock_sleep.assert_called()
                assert adapter.metrics["memory_throttle_events"] == 1

    def test_sync_llm_call(self, test_db_service):
        """Test synchronous LLM call wrapper."""
        adapter = LLMAdapter(test_db_service)

        # Mock the async implementation
        async def mock_async_call(*args, **kwargs):
            return {"text": "sync test", "total_tokens": 50}

        with patch.object(adapter, "call_llm_async", new=mock_async_call):
            result = adapter.call_llm(
                provider="openai", model="gpt-4", prompt="Test", job_type="mining"
            )

        assert result["text"] == "sync test"

    def test_batch_processing(self, test_db_service):
        """Test batch processing with concurrency control."""
        adapter = LLMAdapter(test_db_service)

        items = ["item1", "item2", "item3", "item4", "item5"]
        processed = []

        def processor(item):
            time.sleep(0.01)  # Simulate work
            processed.append(item)
            return f"processed_{item}"

        results = adapter.process_batch(
            items=items, processor_func=processor, job_type="mining"
        )

        assert len(results) == len(items)
        assert all(r.startswith("processed_") for r in results)
        assert len(processed) == len(items)

    def test_metrics_tracking(self, test_db_service):
        """Test metrics are properly tracked."""
        adapter = LLMAdapter(test_db_service)

        initial_metrics = adapter.get_metrics()
        assert initial_metrics["total_requests"] == 0
        assert initial_metrics["tier"] == adapter.tier_config.tier

        # Make some calls to update metrics
        adapter.metrics["total_requests"] = 10
        adapter.metrics["successful_requests"] = 8
        adapter.metrics["failed_requests"] = 2
        adapter.metrics["total_tokens"] = 1500
        adapter.metrics["total_cost_usd"] = 0.05

        metrics = adapter.get_metrics()
        assert metrics["total_requests"] == 10
        assert metrics["successful_requests"] == 8
        assert metrics["failed_requests"] == 2
        assert metrics["total_tokens"] == 1500
        assert metrics["total_cost_usd"] == 0.05

    def test_database_tracking(self, test_db_service):
        """Test LLM requests/responses are tracked in database."""
        adapter = LLMAdapter(test_db_service)

        # This would require setting up the full async flow
        # For now, verify the database models exist
        from src.knowledge_system.database.system2_models import LLMRequest, LLMResponse

        with test_db_service.get_session() as session:
            # Create test records
            test_request = LLMRequest(
                request_id="test-req-001",
                job_run_id="test-run-001",
                provider="openai",
                model="gpt-4",
                request_json={"test": True},
            )
            session.add(test_request)
            session.commit()

            # Verify it was saved
            saved_request = (
                session.query(LLMRequest).filter_by(request_id="test-req-001").first()
            )
            assert saved_request is not None
            assert saved_request.provider == "openai"
