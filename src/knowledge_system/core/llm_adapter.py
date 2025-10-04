"""
LLM Adapter for System 2

Centralizes all LLM calls with hardware-aware concurrency control,
memory management, and exponential backoff per SYSTEM_2_IMPLEMENTATION_GUIDE.md.
"""

import asyncio
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psutil
from sqlalchemy.orm import Session

from ..database import DatabaseService, LLMRequest, LLMResponse
from ..errors import ErrorCode, KnowledgeSystemError
from ..logger import get_logger
from ..utils.hardware_detection import HardwareDetector

logger = get_logger(__name__)


@dataclass
class HardwareTierConfig:
    """Hardware tier configuration from TECHNICAL_SPECIFICATIONS.md"""

    tier: str
    download_workers: int
    mining_workers: int
    evaluation_workers: int
    max_threads: int
    memory_threshold: float = 0.7  # 70% memory threshold
    critical_threshold: float = 0.9  # 90% critical threshold


# Hardware tier configurations from TECHNICAL_SPECIFICATIONS.md §Hardware Tier Configurations
HARDWARE_TIERS = {
    "consumer": HardwareTierConfig(
        tier="consumer",
        download_workers=2,
        mining_workers=2,
        evaluation_workers=1,
        max_threads=4,
    ),
    "prosumer": HardwareTierConfig(
        tier="prosumer",
        download_workers=3,
        mining_workers=4,
        evaluation_workers=2,
        max_threads=8,
    ),
    "professional": HardwareTierConfig(
        tier="professional",
        download_workers=4,
        mining_workers=6,
        evaluation_workers=3,
        max_threads=12,
    ),
    "server": HardwareTierConfig(
        tier="server",
        download_workers=6,
        mining_workers=10,
        evaluation_workers=5,
        max_threads=20,
    ),
}


class MemoryMonitor:
    """Monitors system memory and provides throttling recommendations."""

    def __init__(self, threshold: float = 0.7, critical_threshold: float = 0.9):
        self.threshold = threshold
        self.critical_threshold = critical_threshold
        self._last_check = 0
        self._check_interval = 1.0  # Check every second

    def get_memory_usage(self) -> float:
        """Get current memory usage percentage."""
        return psutil.virtual_memory().percent / 100.0

    def should_throttle(self) -> tuple[bool, float]:
        """
        Check if we should throttle operations.

        Returns:
            Tuple of (should_throttle, current_usage)
        """
        current_time = time.time()
        if current_time - self._last_check < self._check_interval:
            return False, 0.0

        self._last_check = current_time
        usage = self.get_memory_usage()

        return usage > self.threshold, usage

    def is_critical(self) -> bool:
        """Check if memory usage is at critical level."""
        return self.get_memory_usage() > self.critical_threshold


class RateLimiter:
    """Implements exponential backoff with jitter for rate limiting."""

    def __init__(self, initial_delay: float = 1.0, max_delay: float = 60.0):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.current_delay = initial_delay
        self.consecutive_errors = 0

    def reset(self):
        """Reset the rate limiter after successful request."""
        self.current_delay = self.initial_delay
        self.consecutive_errors = 0

    def backoff(self):
        """Calculate and apply backoff with jitter."""
        self.consecutive_errors += 1

        # Exponential backoff: delay = min(initial * 2^errors, max_delay)
        base_delay = min(
            self.initial_delay * (2**self.consecutive_errors), self.max_delay
        )

        # Add jitter (±25% randomization)
        jitter = base_delay * 0.25 * (2 * random.random() - 1)
        self.current_delay = base_delay + jitter

        logger.info(
            f"Rate limit backoff: {self.current_delay:.2f}s (attempt {self.consecutive_errors})"
        )
        time.sleep(self.current_delay)


class LLMAdapter:
    """
    Centralized LLM adapter with concurrency control and memory management.

    Features:
    - Hardware tier-based worker limits
    - Dynamic memory-based throttling
    - Exponential backoff for rate limits
    - Token budget tracking
    - Request/response logging to database
    """

    def __init__(self, db_service: DatabaseService | None = None):
        self.db_service = db_service or DatabaseService()
        self.hardware_detector = HardwareDetector()
        self.hardware_specs = self.hardware_detector.detect_hardware()

        # Determine hardware tier
        self.tier_config = self._determine_tier()
        logger.info(f"LLMAdapter initialized for {self.tier_config.tier} tier")

        # Initialize components
        self.memory_monitor = MemoryMonitor(
            threshold=self.tier_config.memory_threshold,
            critical_threshold=self.tier_config.critical_threshold,
        )
        self.rate_limiters: dict[str, RateLimiter] = {}  # Per-provider rate limiters

        # Worker pools for different job types
        self.mining_executor = ThreadPoolExecutor(
            max_workers=self.tier_config.mining_workers, thread_name_prefix="llm_mining"
        )
        self.evaluation_executor = ThreadPoolExecutor(
            max_workers=self.tier_config.evaluation_workers,
            thread_name_prefix="llm_eval",
        )

        # Metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "memory_throttle_events": 0,
        }

    def _determine_tier(self) -> HardwareTierConfig:
        """Determine hardware tier based on system specs."""
        memory_gb = self.hardware_specs.get("memory_gb", 8)
        cpu_cores = self.hardware_specs.get("cpu_cores", 4)

        if memory_gb >= 64 and cpu_cores >= 16:
            return HARDWARE_TIERS["server"]
        elif memory_gb >= 32 and cpu_cores >= 8:
            return HARDWARE_TIERS["professional"]
        elif memory_gb >= 16 and cpu_cores >= 4:
            return HARDWARE_TIERS["prosumer"]
        else:
            return HARDWARE_TIERS["consumer"]

    def _get_rate_limiter(self, provider: str) -> RateLimiter:
        """Get or create rate limiter for provider."""
        if provider not in self.rate_limiters:
            self.rate_limiters[provider] = RateLimiter()
        return self.rate_limiters[provider]

    def _check_memory_and_throttle(self) -> float | None:
        """
        Check memory usage and throttle if needed.

        Returns:
            Sleep duration if throttling, None otherwise
        """
        should_throttle, usage = self.memory_monitor.should_throttle()

        if self.memory_monitor.is_critical():
            # Critical level - pause new jobs
            logger.warning(f"Critical memory usage: {usage:.1%} - pausing new jobs")
            self.metrics["memory_throttle_events"] += 1
            return 5.0  # Pause for 5 seconds
        elif should_throttle:
            # High usage - reduce parallelization
            logger.info(f"High memory usage: {usage:.1%} - throttling operations")
            self.metrics["memory_throttle_events"] += 1
            return 1.0  # Brief pause

        return None

    async def call_llm_async(
        self,
        provider: str,
        model: str,
        prompt: str,
        job_run_id: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        response_format: str | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Async LLM call with full tracking and retry logic.

        Args:
            provider: LLM provider (openai, anthropic, google)
            model: Model identifier
            prompt: Input prompt
            job_run_id: Optional job run ID for tracking
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            response_format: Expected response format (e.g., "json")
            max_retries: Maximum retry attempts

        Returns:
            Dict with response data and metadata
        """
        request_id = f"llm_{time.time_ns()}"
        rate_limiter = self._get_rate_limiter(provider)

        for attempt in range(max_retries):
            try:
                # Check memory before making request
                throttle_duration = self._check_memory_and_throttle()
                if throttle_duration:
                    await asyncio.sleep(throttle_duration)

                # Track request start
                start_time = time.time()
                self.metrics["total_requests"] += 1

                # Create request record
                if job_run_id:
                    with self.db_service.get_session() as session:
                        llm_request = LLMRequest(
                            request_id=request_id,
                            job_run_id=job_run_id,
                            provider=provider,
                            model=model,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            request_json={
                                "prompt": prompt[:1000],  # Truncate for storage
                                "full_length": len(prompt),
                                "response_format": response_format,
                            },
                        )
                        session.add(llm_request)
                        session.commit()

                # Make actual LLM call (provider-specific)
                response = await self._call_provider_async(
                    provider, model, prompt, max_tokens, temperature, response_format
                )

                # Track success
                latency_ms = (time.time() - start_time) * 1000
                self.metrics["successful_requests"] += 1
                self.metrics["total_tokens"] += response.get("total_tokens", 0)
                self.metrics["total_cost_usd"] += response.get("cost_usd", 0.0)

                # Store response
                if job_run_id:
                    with self.db_service.get_session() as session:
                        llm_response = LLMResponse(
                            response_id=f"resp_{request_id}",
                            request_id=request_id,
                            status_code=200,
                            completion_tokens=response.get("completion_tokens", 0),
                            total_tokens=response.get("total_tokens", 0),
                            latency_ms=latency_ms,
                            cost_usd=response.get("cost_usd", 0.0),
                            response_json=response,
                        )
                        session.add(llm_response)
                        session.commit()

                # Reset rate limiter on success
                rate_limiter.reset()

                return response

            except Exception as e:
                self.metrics["failed_requests"] += 1

                # Check if it's a rate limit error
                if "429" in str(e) or "rate" in str(e).lower():
                    if attempt < max_retries - 1:
                        rate_limiter.backoff()
                        continue
                    else:
                        raise KnowledgeSystemError(
                            f"Rate limit exceeded for {provider} after {max_retries} attempts",
                            error_code=ErrorCode.API_RATE_LIMIT_ERROR_MEDIUM,
                            context={"provider": provider, "model": model},
                        )

                # Log error response
                if job_run_id:
                    with self.db_service.get_session() as session:
                        llm_response = LLMResponse(
                            response_id=f"resp_{request_id}",
                            request_id=request_id,
                            status_code=getattr(e, "status_code", 500),
                            error_message=str(e),
                            response_json={"error": str(e)},
                        )
                        session.add(llm_response)
                        session.commit()

                # Re-raise on last attempt
                if attempt == max_retries - 1:
                    raise

        # Should never reach here, but return error response for type safety
        return {"error": "Max retries exceeded", "provider": provider, "model": model}

    def call_llm(
        self,
        provider: str,
        model: str,
        prompt: str,
        job_run_id: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        response_format: str | None = None,
        job_type: str = "mining",
    ) -> dict[str, Any]:
        """
        Synchronous LLM call with executor-based concurrency control.

        Args:
            provider: LLM provider
            model: Model identifier
            prompt: Input prompt
            job_run_id: Optional job run ID
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            response_format: Expected response format
            job_type: Type of job (mining/evaluation) for executor selection

        Returns:
            Dict with response data
        """
        # Select appropriate executor based on job type
        executor = (
            self.mining_executor if job_type == "mining" else self.evaluation_executor
        )

        # Create async task and run in executor
        async def _async_call():
            return await self.call_llm_async(
                provider,
                model,
                prompt,
                job_run_id,
                max_tokens,
                temperature,
                response_format,
            )

        # Run in thread pool to respect concurrency limits
        future = executor.submit(asyncio.run, _async_call())
        return future.result()

    async def _call_provider_async(
        self,
        provider: str,
        model: str,
        prompt: str,
        max_tokens: int | None,
        temperature: float,
        response_format: str | None,
    ) -> dict[str, Any]:
        """
        Provider-specific LLM call implementation.

        This is a placeholder - actual implementation would use
        provider SDKs (OpenAI, Anthropic, Google, etc.)
        """
        # Simulate API call delay
        await asyncio.sleep(0.5)

        # Mock response
        response_text = f"Mock response for {provider}/{model}"
        if response_format == "json":
            response_text = json.dumps(
                {"claims": [], "jargon": [], "people": [], "mental_models": []}
            )

        return {
            "text": response_text,
            "completion_tokens": len(response_text.split()),
            "prompt_tokens": len(prompt.split()),
            "total_tokens": len(response_text.split()) + len(prompt.split()),
            "cost_usd": 0.001
            * (len(response_text.split()) + len(prompt.split()))
            / 1000,
            "model": model,
            "provider": provider,
        }

    def process_batch(
        self,
        items: list[dict[str, Any]],
        processor_func,
        job_type: str = "mining",
        progress_callback=None,
    ) -> list[Any]:
        """
        Process a batch of items with concurrency control.

        Args:
            items: List of items to process
            processor_func: Function to process each item
            job_type: Type of job for executor selection
            progress_callback: Optional progress callback

        Returns:
            List of results
        """
        executor = (
            self.mining_executor if job_type == "mining" else self.evaluation_executor
        )
        results = []

        # Submit all tasks
        futures = {
            executor.submit(processor_func, item): i for i, item in enumerate(items)
        }

        # Process completions
        completed = 0
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                completed += 1

                if progress_callback:
                    progress_callback(completed, len(items))

            except Exception as e:
                logger.error(f"Batch processing error: {e}")
                results.append(None)

        return results

    def get_metrics(self) -> dict[str, Any]:
        """Get current adapter metrics."""
        return {
            **self.metrics,
            "memory_usage": self.memory_monitor.get_memory_usage(),
            "tier": self.tier_config.tier,
            "active_mining_workers": self.mining_executor._threads.__len__(),
            "active_eval_workers": self.evaluation_executor._threads.__len__(),
        }

    def shutdown(self):
        """Shutdown executor pools."""
        self.mining_executor.shutdown(wait=True)
        self.evaluation_executor.shutdown(wait=True)
