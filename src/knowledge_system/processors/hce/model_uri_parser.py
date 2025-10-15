"""
Utility for parsing model URIs with support for various formats.

Handles formats like:
- "local://qwen2.5:7b-instruct" → provider="ollama", model="qwen2.5:7b-instruct"
- "openai:gpt-4o-mini" → provider="openai", model="gpt-4o-mini"
- "gpt-4o-mini" → provider="openai", model="gpt-4o-mini"
- "local://qwen2.5:7b (Installed)" → provider="ollama", model="qwen2.5:7b"
"""

import re
from typing import Tuple


def parse_model_uri(model_uri: str) -> tuple[str, str]:
    """
    Parse a model URI into provider and model components.

    Args:
        model_uri: Model URI string in various formats

    Returns:
        Tuple of (provider, model)

    Examples:
        >>> parse_model_uri("local://qwen2.5:7b-instruct")
        ("ollama", "qwen2.5:7b-instruct")

        >>> parse_model_uri("openai:gpt-4o-mini")
        ("openai", "gpt-4o-mini")

        >>> parse_model_uri("gpt-4o-mini")
        ("openai", "gpt-4o-mini")

        >>> parse_model_uri("local://qwen2.5:7b (Installed)")
        ("ollama", "qwen2.5:7b")
    """
    if not model_uri:
        return ("openai", "gpt-3.5-turbo")  # Default fallback

    # Strip whitespace and display suffixes like " (Installed)"
    model_uri = model_uri.strip()
    model_uri = re.sub(r"\s*\([^)]*\)\s*$", "", model_uri)

    # Handle local:// protocol (map to ollama)
    if model_uri.startswith("local://"):
        model = model_uri[8:]  # Strip "local://"
        return ("ollama", model)

    # Handle provider:model format
    if ":" in model_uri:
        parts = model_uri.split(":", 1)
        provider = parts[0].lower()
        model = parts[1]

        # Map common aliases
        if provider == "local":
            provider = "ollama"

        return (provider, model)

    # No provider specified, assume OpenAI
    return ("openai", model_uri)


def clean_model_uri(model_uri: str | None) -> str | None:
    """
    Clean a model URI by removing display suffixes.

    Args:
        model_uri: Model URI string or None

    Returns:
        Cleaned URI or None

    Examples:
        >>> clean_model_uri("local://qwen2.5:7b (Installed)")
        "local://qwen2.5:7b"

        >>> clean_model_uri(None)
        None
    """
    if not model_uri:
        return None

    # Strip whitespace and display suffixes
    model_uri = model_uri.strip()
    model_uri = re.sub(r"\s*\([^)]*\)\s*$", "", model_uri)

    return model_uri
