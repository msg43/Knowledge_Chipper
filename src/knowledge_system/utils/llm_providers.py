"""
Shared LLM Provider Utilities

Centralizes API calls to different LLM providers (OpenAI, Anthropic, Local) to eliminate 
duplicate code across processors and provide consistent error handling and response parsing.
"""

import time
import requests
from typing import Dict, Any, Optional, Callable, Union
from pathlib import Path
from dataclasses import dataclass
from abc import ABC, abstractmethod

from ..config import get_settings
from ..logger import get_logger

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Standardized response from LLM providers."""
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    provider: str
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    def __init__(self, model: Optional[str] = None, max_tokens: int = 1000, temperature: float = 0.3):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.settings = get_settings()

    @abstractmethod
    def call(self, prompt: str, progress_callback: Optional[Callable] = None) -> LLMResponse:
        """Make API call to the LLM provider."""
        pass

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Rough approximation: 1 token ≈ 4 characters for English text
        return len(text) // 4


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider."""

    def __init__(self, model: Optional[str] = None, max_tokens: int = 1000, temperature: float = 0.3):
        super().__init__(model, max_tokens, temperature)
        self.model = model or self.settings.llm.model or "gpt-3.5-turbo"

    def call(self, prompt: str, progress_callback: Optional[Callable] = None) -> LLMResponse:
        """Call OpenAI API."""
        try:
            import openai

            client = openai.OpenAI(api_key=self.settings.api_keys.openai_api_key)

            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            # Extract usage statistics with null checks
            usage = response.usage
            content = (
                response.choices[0].message.content.strip()
                if response.choices[0].message.content
                else ""
            )

            return LLMResponse(
                content=content,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                model=self.model,
                provider="openai",
            )

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class AnthropicProvider(BaseLLMProvider):
    """Anthropic API provider."""

    def __init__(self, model: Optional[str] = None, max_tokens: int = 1000, temperature: float = 0.3):
        super().__init__(model, max_tokens, temperature)
        self.model = model or self.settings.llm.model or "claude-3-haiku-20240307"

    def call(self, prompt: str, progress_callback: Optional[Callable] = None) -> LLMResponse:
        """Call Anthropic API."""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.settings.api_keys.anthropic_api_key)

            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract usage statistics
            usage = response.usage
            
            # Get the first text content block - use safe attribute access
            summary_text = ""
            for content in response.content:
                # Check if this is a text block and has text content
                if hasattr(content, "type") and getattr(content, "type", None) == "text":
                    summary_text = getattr(content, "text", "")
                    break
                # Fallback for older anthropic versions
                elif hasattr(content, "text") and getattr(content, "text", None) is not None:
                    summary_text = getattr(content, "text", "")
                    break

            return LLMResponse(
                content=summary_text.strip(),
                prompt_tokens=usage.input_tokens,
                completion_tokens=usage.output_tokens,
                total_tokens=usage.input_tokens + usage.output_tokens,
                model=self.model,
                provider="anthropic",
            )

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


class LocalLLMProvider(BaseLLMProvider):
    """Local LLM provider (Ollama/LM Studio)."""

    def __init__(self, model: Optional[str] = None, max_tokens: int = 1000, temperature: float = 0.3):
        super().__init__(model, max_tokens, temperature)
        self.model = model or self.settings.llm.local_model or "qwen2.5-coder:7b-instruct"
        self.local_config = self.settings.local_config

    def call(self, prompt: str, progress_callback: Optional[Callable] = None) -> LLMResponse:
        """Call local LLM provider."""
        if self.local_config.backend == "ollama":
            return self._call_ollama(prompt, progress_callback)
        elif self.local_config.backend == "lmstudio":
            return self._call_lmstudio(prompt, progress_callback)
        else:
            raise ValueError(f"Unsupported local backend: {self.local_config.backend}")

    def _call_ollama(self, prompt: str, progress_callback: Optional[Callable] = None) -> LLMResponse:
        """Call Ollama API."""
        try:
            url = f"{self.local_config.base_url}/api/generate"

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    "top_k": 40,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                },
            }

            start_time = time.time()
            response = requests.post(url, json=payload, timeout=self.local_config.timeout)
            response.raise_for_status()

            result = response.json()
            
            # Estimate tokens for local models
            prompt_tokens = self._estimate_tokens(prompt)
            completion_tokens = self._estimate_tokens(result.get("response", ""))
            content = result.get("response", "").strip()

            # Update progress if callback provided
            if progress_callback:
                elapsed_time = time.time() - start_time
                speed = completion_tokens / elapsed_time if elapsed_time > 0 else 0
                progress_callback({
                    "status": "post_processing",
                    "current_step": "Processing response...",
                    "percent": 90.0,
                    "tokens_generated": completion_tokens,
                    "speed_tokens_per_sec": speed,
                    "model_name": self.model,
                    "provider": "local"
                })

            return LLMResponse(
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                model=self.model,
                provider="ollama",
            )

        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise

    def _call_lmstudio(self, prompt: str, progress_callback: Optional[Callable] = None) -> LLMResponse:
        """Call LM Studio API."""
        try:
            url = f"{self.local_config.base_url}/v1/chat/completions"

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": False,
            }

            headers = {"Content-Type": "application/json"}

            response = requests.post(
                url, json=payload, headers=headers, timeout=self.local_config.timeout
            )
            response.raise_for_status()

            result = response.json()

            # Extract usage statistics if available
            usage = result.get("usage", {})
            if usage:
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
            else:
                # Estimate tokens for local models
                prompt_tokens = self._estimate_tokens(prompt)
                completion_tokens = self._estimate_tokens(
                    result["choices"][0]["message"]["content"]
                )
                total_tokens = prompt_tokens + completion_tokens

            return LLMResponse(
                content=result["choices"][0]["message"]["content"].strip(),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                model=self.model,
                provider="lmstudio",
            )

        except Exception as e:
            logger.error(f"LM Studio API error: {e}")
            raise


class LLMProviderFactory:
    """Factory for creating LLM providers."""

    @staticmethod
    def create_provider(
        provider: str, 
        model: Optional[str] = None, 
        max_tokens: int = 1000, 
        temperature: float = 0.3
    ) -> BaseLLMProvider:
        """Create an LLM provider instance."""
        if provider == "openai":
            return OpenAIProvider(model, max_tokens, temperature)
        elif provider == "anthropic":
            return AnthropicProvider(model, max_tokens, temperature)
        elif provider == "local":
            return LocalLLMProvider(model, max_tokens, temperature)
        else:
            raise ValueError(f"Unsupported provider: {provider}")


class UnifiedLLMClient:
    """Unified client for all LLM providers with simplified interface."""

    def __init__(
        self, 
        provider: str = "openai", 
        model: Optional[str] = None, 
        max_tokens: int = 1000, 
        temperature: float = 0.3
    ):
        self.provider_name = provider
        self.provider = LLMProviderFactory.create_provider(provider, model, max_tokens, temperature)

    def generate(self, prompt: str, progress_callback: Optional[Callable] = None) -> LLMResponse:
        """Generate text using the configured provider."""
        return self.provider.call(prompt, progress_callback)

    def generate_dict(self, prompt: str, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Generate text and return as dictionary (for backward compatibility)."""
        response = self.generate(prompt, progress_callback)
        return {
            "summary": response.content,  # For backward compatibility with summarizer
            "content": response.content,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens,
            "model": response.model,
            "provider": response.provider,
            **response.metadata
        }

    @property
    def model(self) -> str:
        """Get the current model name."""
        return self.provider.model or "unknown"

    @property
    def max_tokens(self) -> int:
        """Get the current max tokens setting."""
        return self.provider.max_tokens

    @property
    def temperature(self) -> float:
        """Get the current temperature setting."""
        return self.provider.temperature


# Convenience functions for easy migration
def call_llm(
    prompt: str, 
    provider: str = "openai", 
    model: Optional[str] = None, 
    max_tokens: int = 1000,
    temperature: float = 0.3,
    progress_callback: Optional[Callable] = None
) -> LLMResponse:
    """Convenience function to call any LLM provider."""
    client = UnifiedLLMClient(provider, model, max_tokens, temperature)
    return client.generate(prompt, progress_callback)


def call_llm_dict(
    prompt: str, 
    provider: str = "openai", 
    model: Optional[str] = None, 
    max_tokens: int = 1000,
    temperature: float = 0.3,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """Convenience function to call any LLM provider and return dictionary."""
    client = UnifiedLLMClient(provider, model, max_tokens, temperature)
    return client.generate_dict(prompt, progress_callback) 