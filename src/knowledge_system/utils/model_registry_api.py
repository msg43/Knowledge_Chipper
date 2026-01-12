"""
Model Registry - Fetches and caches model lists from official APIs.

This module provides functionality to fetch up-to-date model lists from
official sources (Ollama, OpenAI) and cache them locally. Anthropic models
must be manually maintained in the cache file.
"""

import json
from datetime import datetime
from pathlib import Path

from ..config import get_settings
from ..logger import get_logger

logger = get_logger(__name__)

# Cache settings
CACHE_DIR = Path.home() / ".knowledge_chipper" / "cache"
CACHE_FILE = CACHE_DIR / "model_registry.json"
# Cache indefinitely - only update on explicit refresh


class ModelRegistry:
    """Manages fetching and caching of model lists from official sources."""

    def __init__(self):
        """Initialize the model registry."""
        self._ensure_cache_dir()
        self.settings = get_settings()
        # Track validated models for this session
        self._validated_models: set[str] = set()

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
                "source": "Official APIs",
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

    def _fetch_google_models(self) -> list[str]:
        """Fetch available models from Google Gemini API."""
        try:
            api_key = self.settings.api_keys.google_api_key
            if not api_key:
                logger.info("No Google API key, skipping model fetch")
                return []

            from google import genai

            client = genai.Client(api_key=api_key)
            
            # List all available models
            models_list = client.models.list()
            
            # Filter to generative models (chat/completion capable)
            gemini_models = []
            for model in models_list:
                model_name = model.name
                # Extract just the model ID (remove 'models/' prefix if present)
                if model_name.startswith("models/"):
                    model_name = model_name[7:]
                
                # Only include Gemini models that support generateContent
                if model_name.startswith("gemini-") and hasattr(model, 'supported_generation_methods'):
                    if 'generateContent' in model.supported_generation_methods:
                        gemini_models.append(model_name)

            return sorted(gemini_models)

        except Exception as e:
            logger.error(f"Failed to fetch Google models: {e}")
            return []

    def _fetch_anthropic_models(self) -> list[str]:
        """Fetch available models from Anthropic API."""
        # NOTE: Anthropic doesn't have a public models API
        # Return empty list - model_registry.py will provide curated list
        logger.info("Anthropic: Using curated list from model_registry.py (no public API)")
        return []

    def _fetch_from_openrouter(self) -> dict[str, list[str]]:
        """
        Fetch comprehensive model list from OpenRouter.ai.
        
        OpenRouter aggregates 500+ models from 60+ providers including
        OpenAI, Anthropic, Google, Meta, Mistral, and more.
        
        Returns:
            Dictionary mapping provider names to model lists
        """
        try:
            import requests

            url = "https://openrouter.ai/api/v1/models"
            
            logger.info("Fetching models from OpenRouter.ai...")
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"OpenRouter API returned status {response.status_code}")
                return {}

            data = response.json()
            
            if "data" not in data:
                logger.warning("OpenRouter response missing 'data' field")
                return {}

            # Group models by provider
            models_by_provider: dict[str, list[str]] = {}
            
            for model in data["data"]:
                model_id = model.get("id", "")
                if not model_id:
                    continue
                
                # OpenRouter model IDs are in format: "provider/model-name"
                parts = model_id.split("/", 1)
                if len(parts) != 2:
                    continue
                
                provider, model_name = parts
                
                # Normalize provider names to match our conventions
                provider_map = {
                    "openai": "openai",
                    "anthropic": "anthropic",
                    "google": "google",
                    "meta-llama": "meta",
                    "mistralai": "mistral",
                    "deepseek": "deepseek",
                    "qwen": "qwen",
                    "x-ai": "xai",
                }
                
                normalized_provider = provider_map.get(provider, provider)
                
                if normalized_provider not in models_by_provider:
                    models_by_provider[normalized_provider] = []
                
                models_by_provider[normalized_provider].append(model_name)
            
            # Sort each provider's models
            for provider in models_by_provider:
                models_by_provider[provider] = sorted(set(models_by_provider[provider]))
            
            logger.info(
                f"✅ OpenRouter: Fetched {sum(len(m) for m in models_by_provider.values())} models "
                f"from {len(models_by_provider)} providers"
            )
            
            return models_by_provider

        except Exception as e:
            logger.error(f"Failed to fetch from OpenRouter: {e}")
            return {}

    def fetch_models(self, force_refresh: bool = False) -> dict[str, list[str]]:
        """
        Fetch model lists using multi-tier strategy with intelligent fallbacks.
        
        Tier 1: OpenRouter.ai (Primary - 500+ models from 60+ providers)
        Tier 2: Individual Provider APIs (OpenAI, Google, Anthropic)
        Tier 3: Cache (Last successful fetch)
        Tier 4: Hardcoded Fallbacks (Offline mode)

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Dictionary mapping provider names to model lists
        """
        # Use cache if valid and not forcing refresh
        if not force_refresh and self._is_cache_valid():
            logger.info("Using cached model lists")
            return self._load_cache()

        logger.info("🔄 Refreshing model lists using multi-tier strategy...")

        models: dict[str, list[str]] = {}
        
        # ============================================
        # TIER 1: OpenRouter (DISABLED - Returns stale/incorrect models)
        # ============================================
        # OpenRouter returns models without proper date suffixes and includes
        # deprecated models. We use direct provider APIs instead.
        logger.info("Tier 1: OpenRouter disabled - using direct provider APIs")
        
        # ============================================
        # TIER 2: Individual Provider APIs (Backup)
        # ============================================
        logger.info("Tier 2: Falling back to individual provider APIs...")
        
        try:
            # Fetch from each provider's API
            openai_models = self._fetch_openai_models()
            google_models = self._fetch_google_models()
            anthropic_models = self._fetch_anthropic_models()
            local_models = self._fetch_ollama_models()
            
            # Combine results
            if openai_models:
                models["openai"] = openai_models
            if google_models:
                models["google"] = google_models
            if anthropic_models:
                models["anthropic"] = anthropic_models
            if local_models:
                models["local"] = local_models
            
            if models:
                logger.info(f"✅ Tier 2: Fetched from {len(models)} provider APIs")
                self._save_cache(models)
                return models
                
        except Exception as e:
            logger.warning(f"⚠️ Tier 2 failed (Provider APIs): {e}")
        
        # ============================================
        # TIER 3: Cache (Last Successful Fetch)
        # ============================================
        cached = self._load_cache()
        if cached:
            logger.warning("⚠️ Tier 3: Using cached models (all APIs failed)")
            return cached
        
        # ============================================
        # TIER 4: Hardcoded Fallbacks (Offline Mode)
        # ============================================
        logger.error("⚠️ Tier 4: All sources failed, using hardcoded fallbacks")
        
        models = {
            "openai": [
                "gpt-4o-2024-08-06",
                "gpt-4o-mini-2024-07-18",
                "gpt-4-turbo-2024-04-09",
                "gpt-4-0125-preview",
            ],
            "anthropic": [
                # Return empty - let model_registry.py provide curated list
                # Anthropic has no public models API
            ],
            "google": [
                "gemini-2.0-flash-exp",
                "gemini-1.5-pro-latest",
                "gemini-1.5-flash-latest",
            ],
        }
        
        self._save_cache(models)
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

    def validate_model(
        self, provider: str, model: str, deep_check: bool = False
    ) -> tuple[bool, str]:
        """
        Validate that a model exists and is accessible.

        Args:
            provider: Provider name (openai, anthropic, local)
            model: Model name to validate
            deep_check: If True, actually test the model with a probe request

        Returns:
            Tuple of (is_valid, error_message)
        """
        provider = provider.lower()

        # First do basic validation against cached list
        basic_valid, basic_error = self._basic_validate(provider, model)
        if not basic_valid:
            return False, basic_error

        # If deep check requested, actually test the model
        if deep_check:
            return self._deep_validate(provider, model)

        return True, ""

    def validate_model_once_per_session(
        self, provider: str, model: str
    ) -> tuple[bool, str]:
        """
        Validate a model with deep check, but only once per session.

        This is ideal for validating models when actually using them,
        without the overhead of validating on every single call.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Tuple of (is_valid, error_message)
        """
        model_key = f"{provider.lower()}:{model}"

        # If already validated this session, skip deep check
        if model_key in self._validated_models:
            # Still do basic check in case models were uninstalled
            return self._basic_validate(provider, model)

        # First time this session - do deep validation
        is_valid, error_msg = self.validate_model(provider, model, deep_check=True)

        if is_valid:
            # Mark as validated for this session
            self._validated_models.add(model_key)

        return is_valid, error_msg

    def _basic_validate(self, provider: str, model: str) -> tuple[bool, str]:
        """Basic validation against cached model lists."""
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

    def _deep_validate(self, provider: str, model: str) -> tuple[bool, str]:
        """Deep validation by actually testing the model with a minimal request."""
        test_prompt = "Hi"  # Minimal prompt to test connectivity

        try:
            if provider == "openai":
                api_key = (
                    self.settings.api_keys.openai_api_key
                    or self.settings.api_keys.openai
                )
                if not api_key:
                    return False, "No OpenAI API key configured"

                import openai

                client = openai.OpenAI(api_key=api_key)

                # Try a minimal completion
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": test_prompt}],
                    max_tokens=1,
                    temperature=0,
                )
                return True, ""

            elif provider == "anthropic":
                api_key = (
                    self.settings.api_keys.anthropic_api_key
                    or self.settings.api_keys.anthropic
                )
                if not api_key:
                    return False, "No Anthropic API key configured"

                import anthropic

                client = anthropic.Anthropic(api_key=api_key)

                # Try a minimal completion
                response = client.messages.create(
                    model=model,
                    messages=[{"role": "user", "content": test_prompt}],
                    max_tokens=1,
                    temperature=0,
                )
                return True, ""

            elif provider == "local":
                # For Ollama, try to load the model
                import requests

                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": model,
                        "prompt": test_prompt,
                        "options": {"num_predict": 1},
                    },
                    timeout=10,
                )
                if response.status_code == 200:
                    return True, ""
                else:
                    return False, f"Ollama returned status {response.status_code}"

        except Exception as e:
            error_str = str(e)

            # Parse common error types
            if "api_key" in error_str.lower():
                return False, "Invalid or missing API key"
            elif "permission" in error_str.lower() or "access" in error_str.lower():
                return (
                    False,
                    f"No access to model '{model}'. Check your subscription or permissions.",
                )
            elif "rate_limit" in error_str.lower():
                return False, "Rate limit exceeded. Try again later."
            elif "not found" in error_str.lower() or "404" in error_str:
                return False, f"Model '{model}' not found or no longer available"
            elif "connection" in error_str.lower():
                return (
                    False,
                    "Connection error. Check internet connection or service status.",
                )
            else:
                return False, f"Model test failed: {error_str[:100]}..."

        return False, "Unknown error during model validation"


# Example cache file structure (for reference):
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
