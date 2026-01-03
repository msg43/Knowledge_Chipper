"""
Model registry utilities for provider model discovery and user overrides.

Provides dynamic model lists for OpenAI and Anthropic with safe fallbacks,
and merges optional user overrides from `config/model_overrides.yaml`.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from ..config import get_settings
from ..logger import get_logger
from .model_registry_api import get_community_registry

logger = get_logger(__name__)


DEFAULT_OVERRIDES_PATH = Path("config/model_overrides.yaml")


OPENAI_FALLBACK_MODELS = [
    "gpt-4o-2024-08-06",
    "gpt-4o-2024-05-13",
    "gpt-4o-mini-2024-07-18",
    "gpt-4-turbo-2024-04-09",
    "gpt-4-0125-preview",  # Updated from gpt-4-1106-preview
    "gpt-4-0613",
    "gpt-3.5-turbo-0125",  # Current model, removed deprecated variants
]


ANTHROPIC_FALLBACK_MODELS = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-5-sonnet-20240620",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    # Convenience alias that Anthropic commonly supports
    "claude-3-5-sonnet-latest",
]


GOOGLE_FALLBACK_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-pro",
]


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load model overrides from {path}: {e}")
        return {}


def _save_yaml(path: Path, data: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=True, allow_unicode=True)
    except Exception as e:
        logger.error(f"Failed to save model overrides to {path}: {e}")


def load_model_overrides(overrides_path: Path | None = None) -> dict[str, list[str]]:
    path = overrides_path or DEFAULT_OVERRIDES_PATH
    data = _load_yaml(path)
    result: dict[str, list[str]] = {
        "openai": [],
        "anthropic": [],
    }
    for provider in result:
        values = data.get(provider) or []
        if isinstance(values, list):
            result[provider] = [str(v).strip() for v in values if str(v).strip()]
    return result


def save_model_overrides(
    provider: str, models: list[str], overrides_path: Path | None = None
) -> None:
    path = overrides_path or DEFAULT_OVERRIDES_PATH
    data = _load_yaml(path)
    existing = [str(m).strip() for m in (data.get(provider) or [])]
    merged = _dedupe_preserve_order([*existing, *(m.strip() for m in models)])
    data[provider] = merged
    _save_yaml(path, data)


def _is_openai_chat_model(name: str) -> bool:
    n = name.lower()
    if not n.startswith("gpt-"):
        return False
    excluded = ["embedding", "whisper", "audio", "tts", "transcribe"]
    return not any(x in n for x in excluded)


def get_openai_models(force_refresh: bool = False) -> list[str]:
    """Get OpenAI models from community list, API (if available), and overrides."""
    settings = get_settings()
    api_key = settings.api_keys.openai_api_key or settings.api_keys.openai

    # Start with community list as the base
    community_registry = get_community_registry()
    community_models = community_registry.get_provider_models(
        "openai", force_refresh=force_refresh
    )

    # Try to get dynamic models from API if we have a key
    dynamic: list[str] = []
    if api_key:
        try:
            import openai

            client = openai.OpenAI(api_key=api_key)
            # Models API returns many types; filter to chat models
            models = client.models.list()
            for m in models.data:
                name = getattr(m, "id", None) or getattr(m, "model", None) or ""
                name = name.strip()
                if name and _is_openai_chat_model(name):
                    dynamic.append(name)
        except Exception as e:
            logger.info(f"OpenAI API model listing failed: {e}")

    # Get user overrides
    overrides = load_model_overrides().get("openai", [])

    # Merge all sources: community + dynamic + overrides
    # If community list is empty, fall back to hardcoded list
    base_models = community_models if community_models else OPENAI_FALLBACK_MODELS
    merged = _dedupe_preserve_order([*base_models, *dynamic, *overrides])

    return merged


def get_anthropic_models(force_refresh: bool = False) -> list[str]:
    """Get Anthropic models from API and overrides."""
    # Get from API via community registry (now supports dynamic fetching!)
    community_registry = get_community_registry()
    api_models = community_registry.get_provider_models(
        "anthropic", force_refresh=force_refresh
    )

    # Get user overrides
    overrides = load_model_overrides().get("anthropic", [])

    # Merge API + overrides
    # If API list is empty, fall back to hardcoded list
    base_models = api_models if api_models else ANTHROPIC_FALLBACK_MODELS
    merged = _dedupe_preserve_order([*base_models, *overrides])

    return merged


def get_google_models(force_refresh: bool = False) -> list[str]:
    """Get Google Gemini models from API and overrides."""
    # Get from API via community registry
    community_registry = get_community_registry()
    api_models = community_registry.get_provider_models(
        "google", force_refresh=force_refresh
    )

    # Get user overrides
    overrides = load_model_overrides().get("google", [])

    # Merge API + overrides
    # If API list is empty, fall back to hardcoded list
    base_models = api_models if api_models else GOOGLE_FALLBACK_MODELS
    merged = _dedupe_preserve_order([*base_models, *overrides])

    return merged


def get_local_models(force_refresh: bool = False) -> list[str]:
    """Get local Ollama models from installed instances and registry."""
    try:
        from .ollama_manager import get_ollama_manager

        ollama_manager = get_ollama_manager()
        registry_models = ollama_manager.get_registry_models(
            use_cache=not force_refresh
        )

        models = []
        for model_info in registry_models:
            # Extract base model name without status/size info
            name = model_info.name
            if " (Installed)" in name:
                name = name.replace(" (Installed)", "")
            # Also remove size info like " (4.7 GB)"
            if " (" in name and name.endswith(")"):
                name = name[: name.rfind(" (")]

            if name and name not in models:
                models.append(name)

        # Get user overrides
        overrides = load_model_overrides().get("local", [])

        # Merge and deduplicate
        merged = _dedupe_preserve_order([*models, *overrides])

        return merged

    except Exception as e:
        logger.warning(f"Failed to fetch local models: {e}")
        # Return some common fallback models
        # NOTE: Qwen3-4B-Instruct-2507 not yet in Ollama (only base/thinking variants available)
        return [
            "qwen2.5:7b-instruct",
            "llama3.1:8b-instruct",
            "qwen2.5:3b-instruct",
            "llama3.2:3b-instruct",
            "mistral:7b-instruct",
        ]


def get_provider_models(provider: str, force_refresh: bool = False) -> list[str]:
    """Get models for a provider, optionally forcing a refresh from community source."""
    p = provider.lower().strip()
    if p == "openai":
        return get_openai_models(force_refresh=force_refresh)
    if p in {"anthropic", "claude"}:
        return get_anthropic_models(force_refresh=force_refresh)
    if p in {"google", "gemini"}:
        return get_google_models(force_refresh=force_refresh)
    if p == "local":
        return get_local_models(force_refresh=force_refresh)
    return []


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    """Remove duplicates while preserving first occurrence; trims whitespace."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        name = str(raw).strip()
        key = name.lower()  # case-insensitive dedupe for safety
        if name and key not in seen:
            seen.add(key)
            out.append(name)
    return out


def validate_model_name(provider: str, model: str) -> tuple[bool, str | None]:
    """
    Validate if a model name is available for the given provider.

    Args:
        provider: The LLM provider (openai, anthropic, local)
        model: The model name to validate

    Returns:
        Tuple of (is_valid, suggested_model_name_if_different)
    """
    if not model or not provider:
        return False, None

    available_models = get_provider_models(provider)
    if not available_models:
        return True, None  # Can't validate, assume it's OK

    # Direct match
    if model in available_models:
        return True, None

    # Case-insensitive match
    model_lower = model.lower()
    for available in available_models:
        if available.lower() == model_lower:
            return True, available  # Return the correct casing

    # Check for common deprecations
    if provider == "openai":
        # Map deprecated models to replacements
        deprecation_map = {
            "gpt-3.5-turbo-16k": "gpt-3.5-turbo-0125",
            "gpt-4-1106-preview": "gpt-4-0125-preview",
            "gpt-4.1": "gpt-4o-2024-08-06",  # Assuming gpt-4.1 was meant to be gpt-4o
        }
        if model in deprecation_map:
            replacement = deprecation_map[model]
            if replacement in available_models:
                logger.warning(
                    f"Model '{model}' is deprecated, suggesting '{replacement}'"
                )
                return False, replacement

    return False, None
