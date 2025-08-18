"""
Model Registry - Fetches and caches model lists from official APIs.

This module provides functionality to fetch up-to-date model lists from
official sources (Ollama, OpenAI) and cache them locally. Anthropic models
must be manually maintained in the cache file.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ..config import get_settings
from ..logger import get_logger

logger = get_logger(__name__)

# Cache settings
CACHE_DIR = Path.home() / ".knowledge_chipper" / "cache"
CACHE_FILE = CACHE_DIR / "model_registry.json"
# Cache indefinitely - only update on explicit refresh

# Ollama library API (undocumented but stable)
OLLAMA_LIBRARY_URL = "https://ollama.com/api/models"


class ModelRegistry:
    """Manages fetching and caching of model lists from official sources."""

    def __init__(self):
        """Initialize the model registry."""
        self._ensure_cache_dir()
        self.settings = get_settings()

    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _is_cache_valid(self) -> bool:
        """Check if the cached data exists (cache never expires unless explicitly refreshed)."""
        return CACHE_FILE.exists()

    def _load_cache(self) -> dict[str, list[str]]:
        """Load model lists from cache."""
        try:
            with open(CACHE_FILE) as f:
                cache_data = json.load(f)

            return cache_data.get("models", {})
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return {}

    def _save_cache(self, models: dict[str, list[str]]) -> None:
        """Save model lists to cache."""
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "source": self.community_url,
                "models": models,
            }

            with open(CACHE_FILE, "w") as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"Cached model lists to {CACHE_FILE}")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _fetch_ollama_models(self) -> list[str]:
        """Fetch available models from Ollama library."""
        try:
            from ..utils.ollama_manager import get_ollama_manager

            ollama = get_ollama_manager()

            # Get both installed and available models from registry
            registry_models = ollama.get_registry_models()

            # Extract just the model names (without size info)
            model_names = []
            for model in registry_models:
                # Remove "(Installed)" and size info from names
                name = model.name
                if " (Installed)" in name:
                    name = name.replace(" (Installed)", "")
                # Also remove size info like " (4.7 GB)"
                if " (" in name and name.endswith(")"):
                    name = name[: name.rfind(" (")]

                if name and name not in model_names:
                    model_names.append(name)

            return sorted(model_names)

        except Exception as e:
            logger.error(f"Failed to fetch Ollama models: {e}")
            return []

    def _fetch_openai_models(self) -> list[str]:
        """Fetch available models from OpenAI API."""
        try:
            api_key = (
                self.settings.api_keys.openai_api_key or self.settings.api_keys.openai
            )
            if not api_key:
                logger.info("No OpenAI API key, skipping model fetch")
                return []

            import openai

            client = openai.OpenAI(api_key=api_key)
            models = client.models.list()

            # Filter to chat models only
            chat_models = []
            for model in models.data:
                model_id = model.id
                if any(model_id.startswith(prefix) for prefix in ["gpt-", "o1-"]):
                    # Exclude non-chat models
                    if not any(
                        x in model_id for x in ["embedding", "whisper", "tts", "dall-e"]
                    ):
                        chat_models.append(model_id)

            return sorted(chat_models)

        except Exception as e:
            logger.error(f"Failed to fetch OpenAI models: {e}")
            return []

    def fetch_models(self, force_refresh: bool = False) -> dict[str, list[str]]:
        """
        Fetch model lists from official APIs and cache.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Dictionary mapping provider names to model lists
        """
        # Use cache if valid and not forcing refresh
        if not force_refresh and self._is_cache_valid():
            logger.info("Using cached model lists")
            return self._load_cache()

        logger.info("Refreshing model lists from official sources")

        # Load existing cache to preserve Anthropic models
        existing = self._load_cache() if self._is_cache_valid() else {}

        # Fetch from official sources
        models = {
            "openai": self._fetch_openai_models(),
            "local": self._fetch_ollama_models(),
            # Preserve Anthropic models from cache (must be manually maintained)
            "anthropic": existing.get(
                "anthropic",
                [
                    # Default Anthropic models if cache is empty
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                    "claude-3-5-sonnet-20240620",
                    "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307",
                    "claude-3-5-sonnet-latest",
                ],
            ),
        }

        # Save to cache
        self._save_cache(models)

        logger.info(
            f"Model refresh complete: {len(models['openai'])} OpenAI, "
            f"{len(models['anthropic'])} Anthropic, {len(models['local'])} Ollama"
        )

        return models

    def get_provider_models(
        self, provider: str, force_refresh: bool = False
    ) -> list[str]:
        """
        Get models for a specific provider.

        Args:
            provider: Provider name (openai, anthropic, local)
            force_refresh: If True, fetch fresh data from community

        Returns:
            List of model names for the provider
        """
        all_models = self.fetch_models(force_refresh=force_refresh)
        return all_models.get(provider.lower(), [])

    def validate_model(self, provider: str, model: str) -> tuple[bool, str]:
        """
        Validate that a model exists and is accessible.

        Args:
            provider: Provider name (openai, anthropic, local)
            model: Model name to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        provider = provider.lower()

        if provider == "local":
            # For Ollama, check if model is actually installed
            try:
                from ..utils.ollama_manager import get_ollama_manager

                ollama = get_ollama_manager()

                if not ollama.is_service_running():
                    return False, "Ollama service is not running"

                # Get list of installed models
                installed = ollama.get_available_models()
                installed_names = [m.name for m in installed]

                if model not in installed_names:
                    return (
                        False,
                        f"Model '{model}' is not installed. Run 'ollama pull {model}' first.",
                    )

                return True, ""

            except Exception as e:
                return False, f"Failed to validate Ollama model: {e}"

        elif provider in ["openai", "anthropic"]:
            # For cloud providers, check against our cached list
            models = self.get_provider_models(provider)
            if model in models:
                return True, ""
            else:
                # Try refreshing the list once
                models = self.get_provider_models(provider, force_refresh=True)
                if model in models:
                    return True, ""
                return False, f"Model '{model}' is not available for {provider}"

        return False, f"Unknown provider: {provider}"


# Example community models.json structure:
EXAMPLE_COMMUNITY_MODELS = {
    "version": "1.0",
    "last_updated": "2024-01-15T00:00:00Z",
    "maintainers": ["community"],
    "openai": {
        "models": [
            "gpt-4o-2024-08-06",
            "gpt-4o-2024-05-13",
            "gpt-4o-mini-2024-07-18",
            "gpt-4-turbo-2024-04-09",
            "gpt-4-0125-preview",
            "gpt-4-0613",
            "gpt-3.5-turbo-0125",
        ],
        "deprecated": ["gpt-3.5-turbo-16k", "gpt-4-1106-preview"],
    },
    "anthropic": {
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-5-sonnet-20240620",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-3-5-sonnet-latest",
        ]
    },
    "local": {
        "description": "Popular local models for Ollama",
        "models": [
            "llama3.2:latest",
            "llama3.1:8b",
            "mistral:latest",
            "qwen2.5:7b",
            "codellama:latest",
        ],
    },
}


# Singleton instance
_registry: ModelRegistry | None = None


def get_community_registry() -> ModelRegistry:
    """Get or create the model registry instance (kept for backward compatibility)."""
    global _registry

    if _registry is None:
        _registry = ModelRegistry()

    return _registry


def get_model_registry() -> ModelRegistry:
    """Get or create the model registry instance."""
    return get_community_registry()
