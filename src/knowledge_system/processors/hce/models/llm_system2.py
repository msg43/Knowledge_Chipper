"""
System 2 LLM wrapper that uses the centralized LLM adapter.

This provides a drop-in replacement for AnyLLM that routes all requests
through the System 2 LLM adapter for proper tracking and rate limiting.
"""

import asyncio
import json
import logging
from typing import Any

from ....core.llm_adapter import get_llm_adapter
from ....errors import ErrorCode, KnowledgeSystemError

logger = logging.getLogger(__name__)


class System2LLM:
    """
    System 2 compliant LLM interface that wraps the centralized adapter.

    Compatible with the AnyLLM interface but routes through System 2 infrastructure.
    """

    def __init__(
        self,
        provider: str = "ollama",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        """
        Initialize System 2 LLM wrapper.

        Args:
            provider: LLM provider (ollama, openai, anthropic, google)
            model: Model name (defaults based on provider)
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
        """
        self.provider = provider
        self.model = model or self._get_default_model(provider)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.adapter = get_llm_adapter()

        # For compatibility with structured output
        self.supports_structured = provider == "ollama"

    def _get_default_model(self, provider: str) -> str:
        """Get default model for provider."""
        defaults = {
            "ollama": "qwen2.5:7b-instruct",
            "openai": "gpt-3.5-turbo",
            "anthropic": "claude-3-sonnet",
            "google": "gemini-pro",
        }
        return defaults.get(provider, "gpt-3.5-turbo")

    def set_job_run_id(self, job_run_id: str):
        """Set the current job run ID for tracking."""
        self.adapter.set_job_run_id(job_run_id)

    async def _complete_async(self, prompt: str, **kwargs) -> str:
        """Async completion through the adapter."""
        messages = [{"role": "user", "content": prompt}]

        response = await self.adapter.complete_with_retry(
            provider=self.provider,
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **kwargs,
        )

        return response.get("content", "")

    def complete(self, prompt: str, **kwargs) -> str:
        """
        Generate a completion for the given prompt.

        Synchronous wrapper for compatibility with existing code.
        """
        try:
            # Check if we're already in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context - create a task and run it
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run, 
                        self._complete_async(prompt, **kwargs)
                    )
                    return future.result()
            except RuntimeError:
                # No running loop - safe to use asyncio.run()
                return asyncio.run(self._complete_async(prompt, **kwargs))
        except Exception as e:
            logger.error(f"Completion failed: {e}")
            raise KnowledgeSystemError(
                f"Failed to generate completion: {e}", ErrorCode.LLM_API_ERROR
            ) from e

    async def _generate_json_async(self, prompt: str, **kwargs) -> dict[str, Any]:
        """Async JSON generation through the adapter."""
        # Add JSON instruction to prompt
        json_prompt = f"{prompt}\n\nRespond with valid JSON only."

        response_text = await self._complete_async(json_prompt, **kwargs)

        # Try to parse JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            # Try to extract JSON from the response
            import re

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            logger.error(f"Failed to parse JSON response: {response_text[:200]}")
            raise KnowledgeSystemError(
                f"Invalid JSON response: {e}", ErrorCode.LLM_PARSE_ERROR
            ) from e

    def generate_json(self, prompt: str, **kwargs) -> dict[str, Any]:
        """
        Generate a JSON response for the given prompt.

        Synchronous wrapper for compatibility.
        """
        try:
            # Check if we're already in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context - create a task and run it
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run, 
                        self._generate_json_async(prompt, **kwargs)
                    )
                    return future.result()
            except RuntimeError:
                # No running loop - safe to use asyncio.run()
                return asyncio.run(self._generate_json_async(prompt, **kwargs))
        except Exception as e:
            logger.error(f"JSON generation failed: {e}")
            raise

    async def _generate_structured_json_async(
        self, prompt: str, schema_name: str, **kwargs
    ) -> dict[str, Any]:
        """Async structured JSON generation (Ollama only)."""
        if not self.supports_structured:
            # Fall back to regular JSON generation
            return await self._generate_json_async(prompt, **kwargs)

        # For Ollama, add schema enforcement hint
        structured_prompt = (
            f"{prompt}\n\n"
            f"Respond with valid JSON following the {schema_name} schema."
        )

        # Add format parameter for Ollama
        kwargs["format"] = "json"

        return await self._generate_json_async(structured_prompt, **kwargs)

    def generate_structured_json(
        self, prompt: str, schema_name: str, **kwargs
    ) -> dict[str, Any]:
        """
        Generate structured JSON following a schema (Ollama only).

        Falls back to regular JSON generation for other providers.
        """
        try:
            # Check if we're already in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context - create a task and run it
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self._generate_structured_json_async(prompt, schema_name, **kwargs)
                    )
                    return future.result()
            except RuntimeError:
                # No running loop - safe to use asyncio.run()
                return asyncio.run(
                    self._generate_structured_json_async(prompt, schema_name, **kwargs)
                )
        except Exception as e:
            logger.error(f"Structured JSON generation failed: {e}")
            raise

    def get_stats(self) -> dict[str, Any]:
        """Get LLM usage statistics."""
        return self.adapter.get_stats()


def create_system2_llm(
    provider: str = "ollama", model: str | None = None, **kwargs
) -> System2LLM:
    """Factory function to create a System 2 LLM instance."""
    return System2LLM(provider=provider, model=model, **kwargs)
