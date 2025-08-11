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

logger = get_logger(__name__)


DEFAULT_OVERRIDES_PATH = Path("config/model_overrides.yaml")


OPENAI_FALLBACK_MODELS = [
    "gpt-5",
    "gpt-4o-2024-08-06",
    "gpt-4o-2024-05-13",
    "gpt-4o-mini-2024-07-18",
    "gpt-4-turbo-2024-04-09",
    "gpt-4-1106-preview",
    "gpt-4-0613",
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-0125",
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


def get_openai_models() -> list[str]:
    settings = get_settings()
    api_key = settings.api_keys.openai_api_key or settings.api_keys.openai
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
            logger.info(f"OpenAI model listing failed, using fallbacks: {e}")

    # Merge dynamic + fallbacks + overrides
    overrides = load_model_overrides().get("openai", [])
    merged = _dedupe_preserve_order([*OPENAI_FALLBACK_MODELS, *dynamic, *overrides])
    return merged


def get_anthropic_models() -> list[str]:
    # No official public list endpoint; use curated + overrides
    overrides = load_model_overrides().get("anthropic", [])
    merged = _dedupe_preserve_order([*ANTHROPIC_FALLBACK_MODELS, *overrides])
    return merged


def get_provider_models(provider: str) -> list[str]:
    p = provider.lower().strip()
    if p == "openai":
        return get_openai_models()
    if p in {"anthropic", "claude"}:
        return get_anthropic_models()
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
