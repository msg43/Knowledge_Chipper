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
    # EMPTY - OpenAI has a public models API, so we fetch directly from there
    # No fallback needed - if API key is not configured, user will see empty list
]


ANTHROPIC_FALLBACK_MODELS = [
    # Claude 4.5 series (May 2025) - Current generation
    "claude-sonnet-4-20250514",   # Sonnet 4.5 - Best balance (DEFAULT)
    "claude-opus-4-20250514",     # Opus 4.5 - Most capable
    # Claude 3.5 series - Previous generation (only working models)
    "claude-3-5-haiku-20241022",  # Haiku 3.5 - Fastest/cheapest
    "claude-3-haiku-20240307",    # Haiku 3 - Legacy fallback
    # Note: Most Claude 3.5 and 3 Opus/Sonnet models have been deprecated
]


GOOGLE_FALLBACK_MODELS = [
    # EMPTY - Google should be fetched from their API
    # No fallback needed - if API key is not configured, user will see empty list
    # Note: Currently we don't have a Google models list API implemented
    # For now, this returns empty until we implement Google's models.list() API
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
    """Get OpenAI models directly from OpenAI API."""
    # Get API key from daemon store (for PyInstaller compatibility)
    import os
    try:
        from daemon.services.api_key_store import get_api_key
        api_key = get_api_key("openai")
        # Also inject into environment for get_settings()
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
    except ImportError:
        # Not running in daemon - try from settings
        settings = get_settings()
        api_key = settings.api_keys.openai_api_key or settings.api_keys.openai

    # Try to get dynamic models from OpenAI API if we have a key
    dynamic: list[str] = []
    if api_key:
        try:
            import openai

            client = openai.OpenAI(api_key=api_key)
            # Models API returns many types; filter to chat models only
            models = client.models.list()
            for m in models.data:
                name = getattr(m, "id", None) or getattr(m, "model", None) or ""
                name = name.strip()
                if name and _is_openai_chat_model(name):
                    dynamic.append(name)
            logger.info(f"Fetched {len(dynamic)} OpenAI models from API")
        except Exception as e:
            logger.info(f"OpenAI API model listing failed: {e}")

    # Get user overrides
    overrides = load_model_overrides().get("openai", [])

    # If we got models from OpenAI API, use those (they're real)
    if dynamic:
        # Use raw API list + user overrides
        # Filter to chat models only (already done in dynamic fetch)
        # Keep only the latest 10 models
        all_models = _dedupe_preserve_order([*dynamic, *overrides])
        logger.info(f"Using {len(all_models)} models from OpenAI API, limiting to latest 10")
        return all_models[:10]
    else:
        # No API key or API failed - return empty list
        # User must configure API key to see models
        logger.info("No OpenAI API key configured - returning empty model list")
        return []


def get_anthropic_models(force_refresh: bool = False) -> list[str]:
    """Get Anthropic models from verified working list."""
    print("=" * 80)
    print("!!! GET_ANTHROPIC_MODELS CALLED - MATT'S NEW CODE !!!")
    print(f"ANTHROPIC_FALLBACK_MODELS = {ANTHROPIC_FALLBACK_MODELS}")
    print("=" * 80)
    
    # NOTE: Anthropic doesn't have a public models API, and the community registry
    # returns outdated models. We use our own verified list instead.
    # All models in ANTHROPIC_FALLBACK_MODELS have been tested via API and confirmed working.
    
    logger.info(f"🔍 NEW CODE: get_anthropic_models called (force_refresh={force_refresh})")
    logger.info(f"📋 NEW CODE: ANTHROPIC_FALLBACK_MODELS has {len(ANTHROPIC_FALLBACK_MODELS)} models: {ANTHROPIC_FALLBACK_MODELS}")
    
    # Get user overrides (if any)
    overrides = load_model_overrides().get("anthropic", [])

    # Use our verified fallback list (not community registry)
    # The community registry returns deprecated models that cause 404 errors
    merged = _dedupe_preserve_order([*ANTHROPIC_FALLBACK_MODELS, *overrides])
    
    logger.info(f"✅ NEW CODE: Returning {len(merged)} Anthropic models: {merged}")
    print(f"!!! RETURNING {len(merged)} MODELS: {merged}")

    return merged


def get_google_models(force_refresh: bool = False) -> list[str]:
    """Get Google Gemini models from Google API."""
    # Get API key from daemon store (for PyInstaller compatibility)
    import os
    try:
        from daemon.services.api_key_store import get_api_key
        api_key = get_api_key("google")
        # Also inject into environment for get_settings()
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
    except ImportError:
        # Not running in daemon - try from settings
        settings = get_settings()
        api_key = settings.api_keys.google_api_key
    
    if api_key:
        try:
            from google import genai
            
            client = genai.Client(api_key=api_key)
            
            # List all available models
            models_list = client.models.list()
            
            # Filter to generative Gemini models
            gemini_models = []
            all_models_count = 0
            for model in models_list:
                all_models_count += 1
                model_name = model.name
                # Extract just the model ID (remove 'models/' prefix if present)
                if model_name.startswith("models/"):
                    model_name = model_name[7:]
                
                # Only include Gemini models that support generateContent
                if model_name.startswith("gemini-"):
                    if hasattr(model, 'supported_generation_methods'):
                        if 'generateContent' in model.supported_generation_methods:
                            gemini_models.append(model_name)
                            logger.debug(f"  ✅ {model_name} supports generateContent")
                        else:
                            logger.debug(f"  ❌ {model_name} doesn't support generateContent: {model.supported_generation_methods}")
                    else:
                        # No supported_generation_methods attribute - include it anyway
                        gemini_models.append(model_name)
                        logger.debug(f"  ⚠️ {model_name} has no supported_generation_methods - including anyway")
            
            logger.info(f"Fetched {len(gemini_models)} Gemini models from Google API (out of {all_models_count} total models)")
            
            # Sort models to prioritize the best ones (January 2026)
            # Priority order: Gemini 3 Pro > 2.5 Pro > 2.5 Flash > 3 Flash > others
            priority_order = [
                "gemini-3-pro-preview",      # Best: Deep reasoning, 2M+ context
                "gemini-2.5-pro",            # Complex coding, creative writing
                "gemini-2.5-flash",          # Speed and throughput
                "gemini-3-flash-preview",    # Fast preview
            ]
            
            # Sort: priority models first, then alphabetically
            def sort_key(model: str) -> tuple[int, str]:
                if model in priority_order:
                    return (priority_order.index(model), model)
                return (len(priority_order), model)
            
            sorted_models = sorted(gemini_models, key=sort_key)
            
            # Get user overrides
            overrides = load_model_overrides().get("google", [])
            
            # Merge sorted API results + overrides
            merged = _dedupe_preserve_order([*sorted_models, *overrides])
            return merged
            
        except Exception as e:
            logger.warning(f"Failed to fetch Google models from API: {e}")
            # Fall through to empty list
    
    # No API key or API failed - return empty list
    # User must configure API key to see models
    logger.info("No Google API key configured - returning empty model list")
    return []


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
    logger.info(f"🎯 get_provider_models called: provider={provider}, force_refresh={force_refresh}")
    
    if p == "openai":
        result = get_openai_models(force_refresh=force_refresh)
        logger.info(f"📊 Returning {len(result)} OpenAI models")
        return result
    if p in {"anthropic", "claude"}:
        result = get_anthropic_models(force_refresh=force_refresh)
        logger.info(f"📊 Returning {len(result)} Anthropic models")
        return result
    if p in {"google", "gemini"}:
        result = get_google_models(force_refresh=force_refresh)
        logger.info(f"📊 Returning {len(result)} Google models")
        return result
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
