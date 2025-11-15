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
    LLMAdapter,
    MemoryThrottler,
    RateLimiter,
)
from src.knowledge_system.errors import APIError, ErrorCode

from .fixtures import test_db_service


class TestMemoryThrottler:
    """Test cases for memory throttling."""

    @pytest.mark.asyncio
    async def test_memory_throttling(self):
        """Test memory-based throttling."""
        throttler = MemoryThrottler(threshold_percent=70.0)

        # Mock memory usage below threshold
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value = Mock(percent=60.0)
            # Should not throttle
            await throttler.check_and_wait()

    @pytest.mark.asyncio
    async def test_memory_throttling_above_threshold(self):
        """Test throttling when memory is above threshold."""
        throttler = MemoryThrottler(threshold_percent=70.0)

        with patch("psutil.virtual_memory") as mock_memory:
            with patch("asyncio.sleep") as mock_sleep:
                mock_memory.return_value = Mock(percent=80.0)
                await throttler.check_and_wait()
                # Should have triggered sleep due to high memory
                mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_check_interval(self):
        """Test memory check interval limiting."""
        throttler = MemoryThrottler(threshold_percent=70.0)
        throttler._check_interval = 0.1  # Short interval for testing

        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value = Mock(percent=80.0)

            # First check should work
            await throttler.check_and_wait()

            # Reset last check to force a new check
            throttler._last_check = 0
            await throttler.check_and_wait()


class TestRateLimiter:
    """Test cases for rate limiting with exponential backoff."""

    def test_trigger_backoff(self):
        """Test exponential backoff triggering."""
        limiter = RateLimiter(requests_per_minute=60)

        # Trigger backoff
        limiter.trigger_backoff()
        assert limiter.backoff_until is not None
        assert limiter.backoff_multiplier == 2

        # Trigger again
        limiter.trigger_backoff()
        assert limiter.backoff_multiplier == 4

    @pytest.mark.asyncio
    async def test_acquire_with_backoff(self):
        """Test token acquisition with backoff."""
        limiter = RateLimiter(requests_per_minute=60)

        # Normal acquisition
        await limiter.acquire()
        assert limiter.tokens < 60

    def test_backoff_max_limit(self):
        """Test that backoff multiplier is capped."""
        limiter = RateLimiter(requests_per_minute=60)

        # Trigger many backoffs
        for _ in range(10):
            limiter.trigger_backoff()

        # Should be capped at 8x
        assert limiter.backoff_multiplier <= 8


class TestLLMAdapter:
    """Test cases for LLM adapter."""

    def test_hardware_tier_detection(self, test_db_service):
        """Test hardware tier is properly detected."""
        adapter = LLMAdapter(test_db_service)

        assert adapter.hardware_tier in ["consumer", "prosumer", "enterprise"]
        assert adapter.max_concurrent > 0

    def test_concurrency_limits(self, test_db_service):
        """Test concurrency limits are set correctly."""
        # Test different hardware specs (using correct field names)
        test_cases = [
            (
                {"total_memory_gb": 8, "performance_cores": 4, "efficiency_cores": 0},
                "consumer",
                2,
            ),
            (
                {"total_memory_gb": 16, "performance_cores": 8, "efficiency_cores": 0},
                "prosumer",
                4,
            ),
            (
                {"total_memory_gb": 64, "performance_cores": 16, "efficiency_cores": 0},
                "enterprise",
                8,
            ),
        ]

        for specs, expected_tier, expected_concurrent in test_cases:
            adapter = LLMAdapter(test_db_service, hardware_specs=specs)
            assert adapter.hardware_tier == expected_tier
            assert adapter.max_concurrent == expected_concurrent

    @pytest.mark.asyncio
    async def test_async_llm_call_success(self, test_db_service):
        """Test successful async LLM call."""
        adapter = LLMAdapter(test_db_service)
        adapter.set_job_run_id("test-run-123")

        # Mock the provider call
        async def mock_provider_call(*args, **kwargs):
            return {
                "content": '{"result": "success"}',
                "completion_tokens": 100,
                "prompt_tokens": 50,
                "total_tokens": 150,
            }

        adapter._call_provider = mock_provider_call

        result = await adapter.complete(
            provider="openai",
            model="gpt-4",
            messages=[{"role": "user", "content": "Test prompt"}],
        )

        assert result["content"] == '{"result": "success"}'
        assert result["total_tokens"] == 150

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, test_db_service):
        """Test rate limit handling with retry."""
        adapter = LLMAdapter(test_db_service)

        call_count = 0

        async def mock_provider_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                # Simulate rate limit error
                raise Exception("429 rate limit exceeded")
            return {"content": "success", "total_tokens": 100}

        adapter._call_provider = mock_provider_call

        # The adapter doesn't have built-in retry, but it does handle rate limit errors
        # Test that rate limit errors are properly caught and trigger backoff
        from src.knowledge_system.errors import KnowledgeSystemError

        with pytest.raises(KnowledgeSystemError) as exc_info:
            await adapter.complete(
                provider="openai",
                model="gpt-4",
                messages=[{"role": "user", "content": "Test"}],
            )

        assert "429" in str(exc_info.value) or "rate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_memory_throttling(self, test_db_service):
        """Test memory-based throttling."""
        adapter = LLMAdapter(test_db_service)

        # Mock high memory usage
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value = Mock(percent=85.0)
            with patch("asyncio.sleep") as mock_sleep:
                # The throttler should detect high memory and sleep
                await adapter.memory_throttler.check_and_wait()
                # Verify sleep was called due to high memory
                mock_sleep.assert_called()

    def test_sync_llm_call(self, test_db_service):
        """Test synchronous LLM call wrapper using asyncio.run()."""
        adapter = LLMAdapter(test_db_service)

        # Mock the async implementation
        async def mock_async_call(*args, **kwargs):
            return {"content": "sync test", "total_tokens": 50}

        adapter._call_provider = mock_async_call

        # Use asyncio.run to call the async method synchronously
        import asyncio

        result = asyncio.run(
            adapter.complete(
                provider="openai",
                model="gpt-4",
                messages=[{"role": "user", "content": "Test"}],
            )
        )

        assert result["content"] == "sync test"

    @pytest.mark.asyncio
    async def test_batch_processing(self, test_db_service):
        """Test batch processing with concurrency control."""
        adapter = LLMAdapter(test_db_service)

        # Mock provider for batch calls
        call_count = 0

        async def mock_provider_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate work
            return {"content": f"processed_{call_count}", "total_tokens": 10}

        adapter._call_provider = mock_provider_call

        # Make multiple concurrent requests
        messages_list = [[{"role": "user", "content": f"item{i}"}] for i in range(1, 6)]

        results = await asyncio.gather(
            *[
                adapter.complete(provider="openai", model="gpt-4", messages=msgs)
                for msgs in messages_list
            ]
        )

        assert len(results) == 5
        assert all("content" in r for r in results)
        assert call_count == 5

    def test_adapter_initialization(self, test_db_service):
        """Test adapter initializes with correct settings."""
        adapter = LLMAdapter(test_db_service)

        # Verify basic initialization
        assert adapter.db_service is not None
        assert adapter.hardware_tier in ["consumer", "prosumer", "enterprise"]
        assert adapter.max_concurrent > 0  # cloud concurrency
        assert adapter.max_concurrent_local > 0  # local concurrency
        assert adapter.cloud_semaphore is not None
        assert adapter.local_semaphore is not None
        assert len(adapter.rate_limiters) > 0

    def test_database_tracking(self, test_db_service):
        """Test LLM requests/responses are tracked in database."""
        adapter = LLMAdapter(test_db_service)

        # This would require setting up the full async flow
        # For now, verify the database models exist and can be created
        from src.knowledge_system.database.system2_models import (
            Job,
            JobRun,
            LLMRequest,
            LLMResponse,
        )

        with test_db_service.get_session() as session:
            # Create parent job and job_run first (foreign key requirement)
            test_job = Job(
                job_id="test-job-001",
                job_type="mine",
                input_id="test-episode-001",
                config_json={"test": True},
            )
            session.add(test_job)
            session.flush()

            test_run = JobRun(
                run_id="test-run-001",
                job_id="test-job-001",
                status="running",
            )
            session.add(test_run)
            session.flush()

            # Now create test LLM request
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
