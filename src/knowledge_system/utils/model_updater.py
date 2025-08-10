#!/usr/bin/env python3
"""
Model context window updater utility
Model context window updater utility.

This utility helps keep model context windows up to date by:
1. Scanning Ollama for available models
2. Detecting their context windows intelligently
3. Updating the cache
4. Providing manual override capabilities
"""

from typing import Dict, List, Optional

from ..logger import get_logger
from .text_utils import (
    _detect_context_window_from_ollama,
    add_custom_model_context,
    get_cached_models,
    get_model_context_window,
    refresh_model_context_cache,
)

logger = get_logger(__name__)


def scan_and_update_models() -> dict[str, int]:
    """
    Scan Ollama for available models and update context window cache
    Scan Ollama for available models and update context window cache.

    Returns:
        Dictionary of model names to detected context windows
    """
    try:

    try:
        from .ollama_manager import get_ollama_manager

        ollama_manager = get_ollama_manager()
        if not ollama_manager.is_service_running():
            logger.warning("⚠️ Ollama service is not running. Cannot scan for models.")
            return {}

        # Get available models
        available_models = ollama_manager.get_available_models()

        if not available_models:
            logger.info("📭 No models found in Ollama")
            return {}

        logger.info(
            f"🔍 Found {len(available_models)} models in Ollama, detecting context windows..."
        )

        # Clear cache to force fresh detection
        refresh_model_context_cache()

        detected_models = {}

        for model_info in available_models:
            model_name = model_info.name
            context_window = _detect_context_window_from_ollama(model_name)

            if context_window:
                detected_models[model_name] = context_window
                logger.info(f"  📡 {model_name}: {context_window:,} tokens")
            else:
                logger.warning(f"  ❓ {model_name}: Could not detect context window")

        logger.info(
            f"✅ Successfully detected context windows for {len(detected_models)} models"
        )
        return detected_models

    except Exception as e:
        logger.error(f"❌ Failed to scan models: {e}")
        return {}


def list_model_context_windows() -> None:
    """
    List all known model context windows (static + cached)
    List all known model context windows (static + cached).
    """
    from .text_utils import MODEL_CONTEXT_WINDOWS
    from .text_utils import MODEL_CONTEXT_WINDOWS

    print("\n📋 Known Model Context Windows:")
    print("=" * 50)

    # Static models
    print("\n🔧 Static Definitions:")
    for model, context in sorted(MODEL_CONTEXT_WINDOWS.items()):
        if model != "default":
            print(f"  {model}: {context:,} tokens")

    # Cached dynamic models
    cached = get_cached_models()
    dynamic_models = {k: v for k, v in cached.items() if k not in MODEL_CONTEXT_WINDOWS}

    if dynamic_models:
        print("\n📡 Dynamically Detected:")
        for model, context in sorted(dynamic_models.items()):
            print(f"  {model}: {context:,} tokens")

    print(f"\n🔢 Total: {len(MODEL_CONTEXT_WINDOWS) - 1 + len(dynamic_models)} models")


def add_model_override(model_name: str, context_window: int) -> None:
    """
    Add a manual override for a specific model's context window
    Add a manual override for a specific model's context window.

    Args:
        model_name: Name of the model
        context_window: Context window size in tokens
    """
    add_custom_model_context(model_name, context_window)

    add_custom_model_context(model_name, context_window)
    print(
        f"✅ Added custom context window for '{model_name}': {context_window:,} tokens"
    )


def main():
    """ Main CLI interface for model updater."""
    import sys

    if len(sys.argv) < 2:
        print("🤖 Model Context Window Updater")
        print("\nUsage:")
        print(
            "  python -m knowledge_system.utils.model_updater scan       # Scan Ollama for models"
        )
        print(
            "  python -m knowledge_system.utils.model_updater list       # List all known models"
        )
        print(
            "  python -m knowledge_system.utils.model_updater add MODEL TOKENS  # Add custom model"
        )
        print(
            "  python -m knowledge_system.utils.model_updater refresh    # Clear cache"
        )
        return

    command = sys.argv[1].lower()

    if command == "scan":
        print("🔍 Scanning Ollama for available models...")
        detected = scan_and_update_models()
        if detected:
            print(f"\n✅ Successfully detected {len(detected)} models")
            for model, context in detected.items():
                print(f"  {model}: {context:,} tokens")
        else:
            print("\n❓ No models detected. Make sure Ollama is running.")

    elif command == "list":
        list_model_context_windows()

    elif command == "add":
        if len(sys.argv) != 4:
            print("❌ Usage: add MODEL_NAME CONTEXT_TOKENS")
            return

        model_name = sys.argv[2]
        try:
            context_tokens = int(sys.argv[3])
            add_model_override(model_name, context_tokens)
        except ValueError:
            print("❌ Context tokens must be a number")

    elif command == "refresh":
        refresh_model_context_cache()
        print("✅ Model context cache refreshed")

    else:
        print(f"❌ Unknown command: {command}")


if __name__ == "__main__":
    main()
