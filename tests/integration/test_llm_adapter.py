"""
Integration tests for System 2 LLM Adapter.

Tests concurrency control, rate limiting, and memory throttling.
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from knowledge_system.core.llm_adapter import (
    LLMAdapter,
    MemoryThrottler,
    RateLimiter,
    get_llm_adapter,
)
from knowledge_system.database import DatabaseService
from knowledge_system.errors import ErrorCode, KnowledgeSystemError


class TestRateLimiter:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self):
        """Test basic rate limiting."""
        limiter = RateLimiter(requests_per_minute=60)

        # Should allow immediate request
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        assert elapsed < 0.1

        # Drain tokens
        for _ in range(59):
            await limiter.acquire()

        # Next request should wait
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        assert elapsed > 0.5  # Should wait ~1 second

    @pytest.mark.asyncio
    async def test_rate_limiter_backoff(self):
        """Test exponential backoff."""
        limiter = RateLimiter(requests_per_minute=60)

        # Trigger backoff
        limiter.trigger_backoff()
        assert limiter.backoff_until is not None

        # Should wait during backoff
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        assert elapsed > 0.5  # At least some backoff time

        # Multiple backoffs should increase wait time
        limiter.trigger_backoff()
        assert limiter.backoff_multiplier == 2


class TestMemoryThrottler:
    """Test memory-based throttling."""

    @pytest.mark.asyncio
    async def test_memory_throttler_normal(self):
        """Test throttler when memory is normal."""
        throttler = MemoryThrottler(threshold_percent=95.0)  # High threshold

        start = time.time()
        await throttler.check_and_wait()
        elapsed = time.time() - start
        assert elapsed < 0.1  # Should not wait

    @pytest.mark.asyncio
    async def test_memory_throttler_high_usage(self):
        """Test throttler when memory is high."""
        throttler = MemoryThrottler(threshold_percent=1.0)  # Very low threshold

        start = time.time()
        await throttler.check_and_wait()
        elapsed = time.time() - start
        # Should wait when over threshold
        # Note: Actual wait depends on system memory usage


class TestLLMAdapter:
    """Test LLM adapter functionality."""

    @pytest.fixture
    def adapter(self, test_database: DatabaseService) -> LLMAdapter:
        """Create adapter with test database."""
        hardware_specs = {
            "chip_type": "Apple M1",
            "chip_variant": "base",
            "performance_cores": 4,
            "efficiency_cores": 4,
            "total_memory_gb": 16,
        }
        return LLMAdapter(test_database, hardware_specs)

    def test_hardware_tier_detection(self):
        """Test hardware tier detection."""
        adapter = LLMAdapter()

        # Test Apple Silicon tiers
        assert (
            adapter._determine_hardware_tier(
                {"chip_type": "Apple M1", "chip_variant": "base"}
            )
            == "consumer"
        )
        assert (
            adapter._determine_hardware_tier(
                {"chip_type": "Apple M1", "chip_variant": "Pro"}
            )
            == "prosumer"
        )
        assert (
            adapter._determine_hardware_tier(
                {"chip_type": "Apple M2", "chip_variant": "Ultra"}
            )
            == "enterprise"
        )

        # Test x86 tiers
        assert (
            adapter._determine_hardware_tier(
                {"chip_type": "Intel", "performance_cores": 4, "total_memory_gb": 8}
            )
            == "consumer"
        )
        assert (
            adapter._determine_hardware_tier(
                {"chip_type": "AMD", "performance_cores": 8, "total_memory_gb": 16}
            )
            == "prosumer"
        )
        assert (
            adapter._determine_hardware_tier(
                {"chip_type": "Intel", "performance_cores": 16, "total_memory_gb": 64}
            )
            == "enterprise"
        )

    @pytest.mark.asyncio
    async def test_complete_basic(self, adapter: LLMAdapter):
        """Test basic completion."""
        with patch.object(adapter, "_call_provider") as mock_call:
            mock_call.return_value = {
                "content": "Test response",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            }

            result = await adapter.complete(
                provider="openai",
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello"}],
            )

            assert result["content"] == "Test response"
            assert mock_call.called

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, adapter: LLMAdapter):
        """Test concurrent request limiting."""
        adapter.max_concurrent = 2  # Limit to 2 concurrent

        call_times = []

        async def mock_call(*args, **kwargs):
            call_times.append(time.time())
            await asyncio.sleep(0.5)  # Simulate API delay
            return {"content": "Test", "usage": {}}

        with patch.object(adapter, "_call_provider", side_effect=mock_call):
            # Start 4 requests
            tasks = [
                adapter.complete(
                    "openai", "gpt-3.5", [{"role": "user", "content": f"Test {i}"}]
                )
                for i in range(4)
            ]

            await asyncio.gather(*tasks)

            # Check that requests were throttled
            # First 2 should start immediately, next 2 should wait
            assert len(call_times) == 4
            assert call_times[1] - call_times[0] < 0.1  # First 2 start together
            assert call_times[2] - call_times[0] > 0.4  # 3rd waits for 1st to finish

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, adapter: LLMAdapter):
        """Test handling of rate limit errors."""

        async def mock_call(*args, **kwargs):
            raise Exception("Rate limit exceeded (429)")

        with patch.object(adapter, "_call_provider", side_effect=mock_call):
            with pytest.raises(KnowledgeSystemError) as exc_info:
                await adapter.complete(
                    "openai", "gpt-3.5", [{"role": "user", "content": "Test"}]
                )

            assert exc_info.value.error_code == ErrorCode.LLM_API_ERROR.value

            # Check that backoff was triggered
            limiter = adapter.rate_limiters["openai"]
            assert limiter.backoff_until is not None

    @pytest.mark.asyncio
    async def test_complete_with_retry(self, adapter: LLMAdapter):
        """Test completion with retry on failure."""
        call_count = 0

        async def mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise KnowledgeSystemError("Transient error", error_code=ErrorCode.LLM_API_ERROR)
            return {"content": "Success", "usage": {}}

        with patch.object(adapter, "_call_provider", side_effect=mock_call):
            result = await adapter.complete_with_retry(
                "openai",
                "gpt-3.5",
                [{"role": "user", "content": "Test"}],
                max_retries=3,
            )

            assert result["content"] == "Success"
            assert call_count == 3

    def test_cost_estimation(self, adapter: LLMAdapter):
        """Test cost estimation."""
        # Test GPT-4
        cost = adapter._estimate_cost(
            "openai",
            "gpt-4",
            {"usage": {"prompt_tokens": 1000, "completion_tokens": 500}},
        )
        expected = (1000 / 1000 * 0.03) + (500 / 1000 * 0.06)
        assert abs(cost - expected) < 0.001

        # Test GPT-3.5
        cost = adapter._estimate_cost(
            "openai",
            "gpt-3.5-turbo",
            {"usage": {"prompt_tokens": 1000, "completion_tokens": 500}},
        )
        expected = (1000 / 1000 * 0.001) + (500 / 1000 * 0.002)
        assert abs(cost - expected) < 0.0001

        # Test unknown model
        cost = adapter._estimate_cost("openai", "unknown-model", {"usage": {}})
        assert cost == 0.0

    def test_stats(self, adapter: LLMAdapter):
        """Test adapter statistics."""
        stats = adapter.get_stats()

        assert stats["hardware_tier"] == "consumer"
        assert stats["max_concurrent"] == 2
        assert stats["active_requests"] == 0
        assert "memory_usage" in stats


class TestSingleton:
    """Test singleton behavior."""

    def test_get_llm_adapter_singleton(self, test_database: DatabaseService):
        """Test adapter singleton."""
        adapter1 = get_llm_adapter(test_database)
        adapter2 = get_llm_adapter(test_database)

        assert adapter1 is adapter2
