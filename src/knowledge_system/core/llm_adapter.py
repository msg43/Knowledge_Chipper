"""
System 2 LLM Adapter

Centralizes all LLM API calls with:
- Hardware tier-specific concurrency limits
- Memory-aware throttling (80% threshold)
- Exponential backoff for rate limits
- Request/response tracking
- Cost estimation
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import psutil

from ..database import DatabaseService
from ..errors import ErrorCode, KnowledgeSystemError
from ..utils.hardware_detection import detect_hardware_specs

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter with exponential backoff."""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.tokens = float(requests_per_minute)
        self.last_update = time.time()
        self.backoff_until = None
        self.backoff_multiplier = 1

    async def acquire(self):
        """Acquire a token, waiting if necessary."""
        while True:
            # Check if we're in backoff
            if self.backoff_until and datetime.now() < self.backoff_until:
                wait_seconds = (self.backoff_until - datetime.now()).total_seconds()
                logger.info(f"Rate limit backoff, waiting {wait_seconds:.1f}s")
                await asyncio.sleep(wait_seconds)
                self.backoff_until = None

            # Update token bucket
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.rpm, self.tokens + elapsed * (self.rpm / 60))
            self.last_update = now

            # Check if we have tokens
            if self.tokens >= 1:
                self.tokens -= 1
                self.backoff_multiplier = 1  # Reset on success
                return

            # Wait for tokens
            wait_time = (1 - self.tokens) / (self.rpm / 60)
            await asyncio.sleep(wait_time)

    def trigger_backoff(self):
        """Trigger exponential backoff on rate limit error."""
        backoff_seconds = min(60 * self.backoff_multiplier, 300)  # Max 5 min
        self.backoff_until = datetime.now() + timedelta(seconds=backoff_seconds)
        self.backoff_multiplier = min(self.backoff_multiplier * 2, 8)
        logger.warning(f"Rate limit hit, backing off for {backoff_seconds}s")


class MemoryThrottler:
    """Throttles requests when memory usage exceeds threshold."""

    def __init__(self, threshold_percent: float = 70.0):
        self.threshold = threshold_percent
        self._last_check = 0
        self._check_interval = 1.0  # Check every second

    async def check_and_wait(self):
        """Check memory and wait if above threshold."""
        now = time.time()
        if now - self._last_check < self._check_interval:
            return

        self._last_check = now
        memory_percent = psutil.virtual_memory().percent

        if memory_percent > self.threshold:
            logger.warning(
                f"Memory usage at {memory_percent:.1f}%, throttling LLM requests"
            )
            # Wait proportionally to how far over threshold we are
            over_threshold = memory_percent - self.threshold
            wait_time = min(over_threshold / 10, 5.0)  # Max 5s wait
            await asyncio.sleep(wait_time)


class LLMAdapter:
    """
    Centralized adapter for all LLM API calls with System 2 features.

    Features:
    - Hardware-aware concurrency limits
    - Memory-based throttling
    - Rate limiting with exponential backoff
    - Request/response tracking in database
    - Cost estimation
    """

    # Hardware tier concurrency limits for CLOUD APIs (OpenAI, Anthropic, etc)
    CLOUD_CONCURRENCY_LIMITS = {
        "consumer": 2,  # M1/M2 base models
        "prosumer": 4,  # M1/M2 Pro/Max
        "enterprise": 8,  # M1/M2 Ultra, high-end x86
    }

    # Hardware tier concurrency limits for LOCAL APIs (Ollama)
    # Each Ollama request spawns ~5 threads for Metal backend
    # To avoid thread oversubscription: limit based on physical_cores / threads_per_request
    LOCAL_CONCURRENCY_LIMITS = {
        "consumer": 3,  # M1/M2 base (8 cores / ~3 = 2-3 workers)
        "prosumer": 5,  # M1/M2 Pro/Max (12-16 cores / ~3 = 4-5 workers)
        "enterprise": 8,  # M1/M2 Ultra (24 cores / 5 = ~5 workers, cap at 8 for safety)
    }

    def __init__(
        self,
        db_service: DatabaseService | None = None,
        hardware_specs: dict[str, Any] | None = None,
        provider: str | None = None,  # New: allow specifying primary provider
    ):
        """Initialize the LLM adapter."""
        self.db_service = db_service or DatabaseService()

        # Load settings for timeout configuration
        from ..config import get_settings

        settings = get_settings()
        self.local_timeout = settings.local_config.timeout  # Get from config (600s)
        self.cloud_timeout = 300  # 5 minutes for cloud APIs

        # Detect hardware tier
        if hardware_specs is None:
            hardware_specs = detect_hardware_specs()

        self.hardware_tier = self._determine_hardware_tier(hardware_specs)

        # Choose concurrency limit based on primary provider (default to cloud for safety)
        # This can be overridden per-request using provider-specific semaphores
        self.max_concurrent = self.CLOUD_CONCURRENCY_LIMITS.get(self.hardware_tier, 2)
        self.max_concurrent_local = self.LOCAL_CONCURRENCY_LIMITS.get(
            self.hardware_tier, 4
        )

        # Respect server/app caps for local concurrency
        try:
            import os

            ollama_parallel = int(os.environ.get("OLLAMA_NUM_PARALLEL", "0"))
            hce_effective = int(os.environ.get("HCE_EFFECTIVE_MAX_WORKERS", "0"))
        except Exception:
            ollama_parallel = 0
            hce_effective = 0

        effective_local = self.max_concurrent_local
        if ollama_parallel > 0:
            effective_local = min(effective_local, ollama_parallel)
        if hce_effective > 0:
            effective_local = min(effective_local, hce_effective)

        logger.info(
            f"LLM Adapter initialized for {self.hardware_tier} tier "
            f"(max {self.max_concurrent} concurrent cloud / {effective_local} local requests, "
            f"local timeout: {self.local_timeout}s)"
        )

        # Concurrency control - separate semaphores for cloud and local
        self.cloud_semaphore = threading.Semaphore(self.max_concurrent)
        self.local_semaphore = threading.Semaphore(effective_local)
        self._active_lock = threading.Lock()
        self.active_requests = 0

        # Rate limiters per provider
        self.rate_limiters = {
            "openai": RateLimiter(60),  # 60 RPM default
            "anthropic": RateLimiter(50),  # 50 RPM default
            "google": RateLimiter(60),  # 60 RPM default
            "ollama": RateLimiter(1000),  # Local, no real limit
        }

        # Memory throttler
        self.memory_throttler = MemoryThrottler(80.0)

        # Cost tracking
        self.cost_per_1k_tokens = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "gemini-pro": {"input": 0.001, "output": 0.002},
        }

        # Request tracking
        self._current_job_run_id: str | None = None

    def set_job_run_id(self, job_run_id: str):
        """Set the current job run ID for request tracking."""
        self._current_job_run_id = job_run_id

    def _determine_hardware_tier(self, specs: dict[str, Any]) -> str:
        """Determine hardware tier from specs."""
        # Check for Apple Silicon
        chip_type = specs.get("chip_type", "").lower()
        chip_variant = specs.get("chip_variant", "").lower()

        if (
            "apple" in chip_type
            or "m1" in chip_type
            or "m2" in chip_type
            or "m3" in chip_type
        ):
            # Check both chip_type and chip_variant for tier indicators
            combined = f"{chip_type} {chip_variant}".lower()
            if "ultra" in combined:
                return "enterprise"
            elif "pro" in combined or "max" in combined:
                return "prosumer"
            else:
                return "consumer"

        # Check x86 by core count and memory
        cores = specs.get("cpu_cores", 0)
        if cores == 0:  # Fallback to alternative field names
            cores = specs.get("performance_cores", 0) + specs.get("efficiency_cores", 0)
        memory_gb = specs.get("memory_gb", 0)
        if memory_gb == 0:  # Fallback
            memory_gb = specs.get("total_memory_gb", 0)

        if cores >= 16 and memory_gb >= 32:
            return "enterprise"
        elif cores >= 8 and memory_gb >= 16:
            return "prosumer"
        else:
            return "consumer"

    async def complete(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Make an LLM completion request with all System 2 features.

        Args:
            provider: LLM provider (openai, anthropic, google, ollama)
            model: Model name
            messages: Chat messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Response dictionary with 'content' and metadata
        """
        start_time = time.time()

        # Validate provider
        if provider not in self.rate_limiters:
            raise KnowledgeSystemError(
                f"Unknown provider: {provider}", ErrorCode.INVALID_INPUT
            )

        # Wait for rate limiter
        rate_limiter = self.rate_limiters[provider]
        await rate_limiter.acquire()

        # Check memory throttling
        await self.memory_throttler.check_and_wait()

        # Choose semaphore based on provider type (local vs cloud)
        is_local = provider in ["ollama", "local"]
        semaphore = self.local_semaphore if is_local else self.cloud_semaphore
        max_concurrent = self.max_concurrent_local if is_local else self.max_concurrent

        # Acquire concurrency slot using thread-based semaphore to allow cross-event-loop usage
        await asyncio.to_thread(semaphore.acquire)
        with self._active_lock:
            self.active_requests += 1
            active_requests = self.active_requests

        provider_type = "local" if is_local else "cloud"
        logger.debug(
            f"LLM request starting ({active_requests} active, {max_concurrent} max {provider_type})"
        )

        try:
            # Build request payload
            request_payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }

            # Track request in database
            request_id = self._track_request(provider, model, request_payload)

            # Make the actual API call
            response = await self._call_provider(provider, model, request_payload)

            # Track response
            response_time_ms = int((time.time() - start_time) * 1000)
            self._track_response(request_id, response, response_time_ms)

            # Estimate cost
            cost = self._estimate_cost(provider, model, response)
            if cost > 0:
                logger.debug(f"Estimated cost: ${cost:.4f}")

            return response

        except Exception as e:
            # Handle rate limit errors
            if "rate" in str(e).lower() or "429" in str(e):
                rate_limiter.trigger_backoff()

            raise KnowledgeSystemError(
                f"LLM request failed: {e}", ErrorCode.LLM_API_ERROR
            ) from e

        finally:
            with self._active_lock:
                self.active_requests -= 1
            semaphore.release()

    async def _call_provider(
        self, provider: str, model: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Make the actual API call to the provider."""
        if provider == "ollama":
            return await self._call_ollama(model, payload)
        elif provider == "openai":
            return await self._call_openai(model, payload)
        elif provider == "anthropic":
            return await self._call_anthropic(model, payload)
        elif provider == "google":
            return await self._call_google(model, payload)
        else:
            raise KnowledgeSystemError(
                f"Provider {provider} not implemented yet", ErrorCode.INVALID_INPUT
            )

    async def _call_ollama(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Call Ollama local API."""
        import aiohttp

        url = "http://localhost:11434/api/chat"

        request_payload = {
            "model": model,
            "messages": payload["messages"],
            "stream": False,
            "options": {
                "temperature": payload.get("temperature", 0.7),
            },
        }

        # Handle both "json" string and schema dict formats
        format_param = payload.get("format")
        if format_param == "json":
            request_payload["format"] = "json"
        elif isinstance(format_param, dict):
            # Full schema object for structured outputs
            request_payload["format"] = format_param

        try:
            async with aiohttp.ClientSession() as session:
                # Use configurable timeout from settings (default 600s for local)
                async with session.post(
                    url,
                    json=request_payload,
                    timeout=aiohttp.ClientTimeout(total=self.local_timeout),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise KnowledgeSystemError(
                            f"Ollama API error: {error_text}", ErrorCode.LLM_API_ERROR
                        )
                    result = await response.json()

            content = result["message"]["content"]

            # Warn if content is empty (might indicate schema is too restrictive)
            if not content or not content.strip():
                logger.warning(
                    f"⚠️ Ollama returned empty content for model {model}. "
                    f"This may indicate the schema is too restrictive or the prompt is unclear."
                )
                # Log more details for debugging
                logger.debug(
                    f"Empty response details - model: {model}, format: {type(format_param)}"
                )

            prompt_tokens = (
                sum(len(m["content"].split()) for m in payload["messages"]) * 1.3
            )
            completion_tokens = len(content.split()) * 1.3 if content else 0

            return {
                "content": content,
                "usage": {
                    "prompt_tokens": int(prompt_tokens),
                    "completion_tokens": int(completion_tokens),
                    "total_tokens": int(prompt_tokens + completion_tokens),
                },
                "model": model,
                "provider": "ollama",
            }
        except aiohttp.ClientError as e:
            raise KnowledgeSystemError(
                f"Ollama connection failed: {e}. Is Ollama running?",
                ErrorCode.LLM_API_ERROR,
            ) from e
        except KeyError as e:
            raise KnowledgeSystemError(
                f"Unexpected Ollama response format: {e}", ErrorCode.LLM_API_ERROR
            ) from e

    async def _call_openai(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Call OpenAI API."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise KnowledgeSystemError(
                "OpenAI package not installed. Run: pip install openai",
                ErrorCode.CONFIGURATION_ERROR,
            )

        try:
            # Get API key from settings
            from ..config import get_settings

            settings = get_settings()
            api_key = settings.api_keys.openai_api_key

            if not api_key:
                raise KnowledgeSystemError(
                    "OpenAI API key not configured in settings.yaml",
                    ErrorCode.CONFIGURATION_ERROR,
                )

            # Create async client with proper cleanup
            async with AsyncOpenAI(api_key=api_key) as client:
                # Make API call
                response = await client.chat.completions.create(
                    model=model,
                    messages=payload["messages"],
                    temperature=payload.get("temperature", 0.7),
                    max_tokens=payload.get("max_tokens"),
                )

                # Extract response
                content = response.choices[0].message.content
                usage = response.usage

                return {
                    "content": content,
                    "usage": {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    },
                    "model": response.model,
                    "provider": "openai",
                }

        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise  # Let the retry logic handle rate limits
            raise KnowledgeSystemError(
                f"OpenAI API error: {e}", ErrorCode.LLM_API_ERROR
            ) from e

    async def _call_anthropic(
        self, model: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Call Anthropic API."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise KnowledgeSystemError(
                "Anthropic package not installed. Run: pip install anthropic",
                ErrorCode.CONFIGURATION_ERROR,
            )

        try:
            # Get API key from settings
            from ..config import get_settings

            settings = get_settings()
            api_key = settings.api_keys.anthropic_api_key

            if not api_key:
                raise KnowledgeSystemError(
                    "Anthropic API key not configured in settings.yaml",
                    ErrorCode.CONFIGURATION_ERROR,
                )

            # Create async client with proper cleanup
            async with AsyncAnthropic(api_key=api_key) as client:
                # Make API call
                response = await client.messages.create(
                    model=model,
                    max_tokens=payload.get("max_tokens", 4000),
                    temperature=payload.get("temperature", 0.7),
                    messages=payload["messages"],
                )

                # Extract text from response
                content = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        content += block.text

                # Extract usage
                usage = response.usage

                return {
                    "content": content,
                    "usage": {
                        "prompt_tokens": usage.input_tokens,
                        "completion_tokens": usage.output_tokens,
                        "total_tokens": usage.input_tokens + usage.output_tokens,
                    },
                    "model": response.model,
                    "provider": "anthropic",
                }

        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise  # Let the retry logic handle rate limits
            raise KnowledgeSystemError(
                f"Anthropic API error: {e}", ErrorCode.LLM_API_ERROR
            ) from e

    async def _call_google(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Call Google Gemini API."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise KnowledgeSystemError(
                "Google AI package not installed. Run: pip install google-generativeai",
                ErrorCode.CONFIGURATION_ERROR,
            )

        try:
            # Get API key from settings
            from ..config import get_settings

            settings = get_settings()
            api_key = settings.api_keys.google_api_key

            if not api_key:
                raise KnowledgeSystemError(
                    "Google API key not configured in settings.yaml",
                    ErrorCode.CONFIGURATION_ERROR,
                )

            # Configure API
            genai.configure(api_key=api_key)

            # Create model
            generation_config = {
                "temperature": payload.get("temperature", 0.7),
                "max_output_tokens": payload.get("max_tokens"),
            }
            model_instance = genai.GenerativeModel(
                model_name=model, generation_config=generation_config
            )

            # Convert messages to Gemini format (concatenate for simplicity)
            prompt = "\n\n".join([msg["content"] for msg in payload["messages"]])

            # Make API call
            response = await model_instance.generate_content_async(prompt)

            # Extract content
            content = response.text

            # Estimate tokens (Gemini doesn't always provide usage)
            prompt_tokens = len(prompt.split()) * 1.3
            completion_tokens = len(content.split()) * 1.3

            return {
                "content": content,
                "usage": {
                    "prompt_tokens": int(prompt_tokens),
                    "completion_tokens": int(completion_tokens),
                    "total_tokens": int(prompt_tokens + completion_tokens),
                },
                "model": model,
                "provider": "google",
            }

        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise  # Let the retry logic handle rate limits
            raise KnowledgeSystemError(
                f"Google API error: {e}", ErrorCode.LLM_API_ERROR
            ) from e

    def _track_request(self, provider: str, model: str, payload: dict[str, Any]) -> str:
        """Track request in database."""
        if not self._current_job_run_id:
            return ""

        try:
            import uuid

            from ..database.system2_models import LLMRequest

            request_id = f"llm_req_{uuid.uuid4().hex[:8]}"

            with self.db_service.get_session() as session:
                llm_request = LLMRequest(
                    request_id=request_id,
                    job_run_id=self._current_job_run_id,
                    provider=provider,
                    model=model,
                    endpoint=None,
                    request_json=payload,
                    prompt_tokens=payload.get("prompt_tokens"),
                    max_tokens=payload.get("max_tokens"),
                    temperature=payload.get("temperature"),
                )
                session.add(llm_request)
                session.commit()

            return request_id
        except Exception as e:
            logger.warning(f"Failed to track LLM request: {e}")
            return ""

    def _track_response(
        self, request_id: str, response: dict[str, Any], response_time_ms: int
    ):
        """Track response in database."""
        if not request_id:
            return

        try:
            import uuid

            from ..database.system2_models import LLMResponse

            usage = response.get("usage", {})
            response_id = f"llm_resp_{uuid.uuid4().hex[:8]}"

            with self.db_service.get_session() as session:
                llm_response = LLMResponse(
                    response_id=response_id,
                    request_id=request_id,
                    response_json=response,
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    latency_ms=response_time_ms,
                )
                session.add(llm_response)
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to track LLM response: {e}")

    def _estimate_cost(
        self, provider: str, model: str, response: dict[str, Any]
    ) -> float:
        """Estimate cost of the request."""
        usage = response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # Get cost rates
        model_key = None
        if "gpt-4" in model:
            model_key = "gpt-4"
        elif "gpt-3.5" in model:
            model_key = "gpt-3.5-turbo"
        elif "claude-3-opus" in model:
            model_key = "claude-3-opus"
        elif "claude-3-sonnet" in model:
            model_key = "claude-3-sonnet"
        elif "gemini" in model:
            model_key = "gemini-pro"

        if not model_key or model_key not in self.cost_per_1k_tokens:
            return 0.0

        rates = self.cost_per_1k_tokens[model_key]
        input_cost = (input_tokens / 1000) * rates["input"]
        output_cost = (output_tokens / 1000) * rates["output"]

        return input_cost + output_cost

    async def complete_with_retry(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        max_retries: int = 3,
        **kwargs,
    ) -> dict[str, Any]:
        """Complete with automatic retry on transient failures."""
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.complete(provider, model, messages, **kwargs)
            except KnowledgeSystemError as e:
                last_error = e
                if (
                    e.error_code == ErrorCode.LLM_API_ERROR.value
                    and attempt < max_retries - 1
                ):
                    wait_time = 2**attempt  # Exponential backoff
                    logger.warning(
                        f"LLM request failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise

        raise last_error

    def get_stats(self) -> dict[str, Any]:
        """Get adapter statistics."""
        return {
            "hardware_tier": self.hardware_tier,
            "max_concurrent": self.max_concurrent,
            "active_requests": self.active_requests,
            "memory_usage": psutil.virtual_memory().percent,
        }


# Singleton instance
_adapter: LLMAdapter | None = None


def get_llm_adapter(
    db_service: DatabaseService | None = None,
    hardware_specs: dict[str, Any] | None = None,
) -> LLMAdapter:
    """Get the singleton LLM adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = LLMAdapter(db_service, hardware_specs)
    return _adapter
