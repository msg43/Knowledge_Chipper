"""
MVP LLM Setup System

Automatically sets up a local LLM (via Ollama) for core features like speaker attribution.
This is the core AI that ships with the app and works out-of-the-box.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from ..config import get_settings
from ..logger import get_logger
from .ollama_manager import InstallationProgress, get_ollama_manager

logger = get_logger(__name__)

# Recommended model for speaker attribution (small, fast, good at text analysis)
FALLBACK_MODEL = "llama3.2:3b"  # 3B model, ~2GB download, good for text tasks

# Alternative models in order of preference
FALLBACK_MODEL_ALTERNATIVES = [
    "llama3.2:3b",  # 3B, 2GB - best balance
    "phi3:3.8b-mini",  # 3.8B, 2.3GB - very good at text
    "llama3.2:1b",  # 1B, 1.3GB - smallest option
    "qwen2.5:3b",  # 3B, 2GB - good alternative
]
MVP_MODEL = "llama3.2:3b"  # 3B model, ~2GB download, good for text tasks

# Alternative models in order of preference
MVP_MODEL_ALTERNATIVES = [
    "llama3.2:3b",  # 3B, 2GB - best balance
    "phi3:3.8b-mini",  # 3.8B, 2.3GB - very good at text
    "llama3.2:1b",  # 1B, 1.3GB - smallest option
    "qwen2.5:3b",  # 3B, 2GB - good alternative
]


class FallbackLLMSetup:
    """Manages automatic setup of MVP LLM for core features."""

    def __init__(self):
        self.ollama_manager = get_ollama_manager()
        self.settings = get_settings()

    def is_fallback_ready(self) -> bool:
        """Check if fallback LLM is ready to use."""
        try:
            # Check if Ollama is running
            if not self.ollama_manager.is_service_running():
                return False

            # Check if fallback model is available
            installed_models = self.ollama_manager.get_installed_models()
            model_names = [model.name for model in installed_models]

            return any(model in model_names for model in FALLBACK_MODEL_ALTERNATIVES)

        except Exception as e:
            logger.debug(f"Error checking fallback LLM status: {e}")
            return False

    def get_available_fallback_model(self) -> str | None:
        """Get the best available fallback model."""
        try:
            installed_models = self.ollama_manager.get_installed_models()
            model_names = [model.name for model in installed_models]

            # Return first available model from preferences
            for model in FALLBACK_MODEL_ALTERNATIVES:
                if model in model_names:
                    return model

            return None

        except Exception:
            return None

    def should_auto_setup(self) -> bool:
        """Check if we should automatically set up fallback LLM."""
        try:
            # Don't auto-setup if user has configured cloud LLM
            if (
                self.settings.llm.provider in ["openai", "anthropic"]
                and self.settings.api_keys.openai_api_key
            ):
                return False

            # Don't auto-setup if user explicitly chose local with different model
            if (
                self.settings.llm.provider == "local"
                and self.settings.llm.local_model not in FALLBACK_MODEL_ALTERNATIVES
            ):
                return False

            # Auto-setup if no LLM configured or fallback not ready
            return not self.is_fallback_ready()

        except Exception:
            return True  # Default to trying setup

    async def setup_fallback_llm(
        self, progress_callback: Callable[[dict[str, Any]], None] | None = None
    ) -> tuple[bool, str]:
        """
        Set up fallback LLM system for speaker attribution.

        Returns:
            (success, status_message)
        """
        try:

            def report_progress(step: str, percent: float, detail: str = ""):
                if progress_callback:
                    progress_callback(
                        {
                            "step": step,
                            "percent": percent,
                            "detail": detail,
                            "stage": "fallback_llm_setup",
                        }
                    )

            report_progress("checking", 5, "Checking Ollama installation...")

            # Step 1: Check/Install Ollama
            is_installed, ollama_path = self.ollama_manager.is_installed()

            if not is_installed:
                report_progress("installing_ollama", 10, "Installing Ollama...")

                def ollama_progress(progress: InstallationProgress):
                    percent = 10 + (progress.percent * 0.3)  # 10-40% for Ollama install
                    report_progress("installing_ollama", percent, progress.current_step)

                success, message = self.ollama_manager.install_ollama_macos(
                    ollama_progress
                )
                if not success:
                    return False, f"Failed to install Ollama: {message}"

            report_progress("starting_service", 45, "Starting Ollama service...")

            # Step 2: Start Ollama service
            if not self.ollama_manager.is_service_running():
                success, message = self.ollama_manager.start_service()
                if not success:
                    return False, f"Failed to start Ollama service: {message}"

                # Wait for service to be ready
                for i in range(10):
                    if self.ollama_manager.is_service_running():
                        break
                    await asyncio.sleep(1)
                    report_progress(
                        "starting_service", 45 + i * 2, "Waiting for service..."
                    )

            report_progress("downloading_model", 60, f"Downloading {FALLBACK_MODEL}...")

            # Step 3: Download fallback model
            available_model = self.get_available_fallback_model()

            if not available_model:
                # Download the preferred model
                def download_progress(percent: float, status: str):
                    adjusted_percent = 60 + (
                        percent * 0.35
                    )  # 60-95% for model download
                    report_progress("downloading_model", adjusted_percent, status)

                success, message = await self._download_model_async(
                    FALLBACK_MODEL, download_progress
                )

                if not success:
                    # Try alternative models
                    for alt_model in FALLBACK_MODEL_ALTERNATIVES[1:]:
                        report_progress(
                            "downloading_model", 60, f"Trying {alt_model}..."
                        )
                        success, message = await self._download_model_async(
                            alt_model, download_progress
                        )
                        if success:
                            available_model = alt_model
                            break

                    if not success:
                        return False, f"Failed to download fallback model: {message}"
                else:
                    available_model = FALLBACK_MODEL

            report_progress("configuring", 95, "Configuring fallback LLM...")

            # Step 4: Update configuration to use fallback LLM
            self._configure_fallback(available_model)

            report_progress("complete", 100, f"Fallback LLM ready: {available_model}")

            logger.info(f"Fallback LLM setup completed successfully: {available_model}")
            return True, f"Fallback LLM ready: {available_model}"

        except Exception as e:
            logger.error(f"Error setting up fallback LLM: {e}")
            return False, f"Setup failed: {str(e)}"

    async def _download_model_async(
        self, model_name: str, progress_callback: Callable[[float, str], None]
    ) -> tuple[bool, str]:
        """Download model asynchronously with progress tracking."""
        try:

            def sync_progress(progress_info):
                if isinstance(progress_info, dict):
                    percent = progress_info.get("percent", 0)
                    status = progress_info.get("status", f"Downloading {model_name}")
                    progress_callback(percent, status)

            # Run download in thread to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.ollama_manager.download_model(model_name, sync_progress),
            )

            return result

        except Exception as e:
            logger.error(f"Error downloading model {model_name}: {e}")
            return False, str(e)

    def _configure_fallback(self, model_name: str):
        """Configure settings to use fallback LLM."""
        try:
            # Update settings to use local provider with fallback model
            from ..utils.state import get_state_manager

            state_manager = get_state_manager()
            state_manager.update_preferences(
                last_llm_provider="local", last_llm_model=model_name
            )

            logger.info(f"Configured fallback LLM: local/{model_name}")

        except Exception as e:
            logger.warning(f"Could not update LLM configuration: {e}")


# Global instance
_fallback_setup: FallbackLLMSetup | None = None


def get_fallback_llm_setup() -> FallbackLLMSetup:
    """Get global fallback LLM setup instance."""
    global _fallback_setup
    if _fallback_setup is None:
        _fallback_setup = FallbackLLMSetup()
    return _fallback_setup


async def ensure_fallback_llm_ready(progress_callback: Callable | None = None) -> bool:
    """
    Ensure fallback LLM is ready for speaker attribution.
    Call this before using speaker attribution features.

    Returns:
        True if fallback LLM is ready, False otherwise
    """
    setup = get_fallback_llm_setup()

    # Check if already ready
    if setup.is_fallback_ready():
        logger.debug("Fallback LLM already ready")
        return True

    # Check if we should auto-setup
    if not setup.should_auto_setup():
        logger.debug("Auto-setup not needed (user has cloud LLM configured)")
        return False

    # Perform setup
    logger.info("Setting up fallback LLM for speaker attribution...")
    success, message = await setup.setup_fallback_llm(progress_callback)

    if success:
        logger.info("Fallback LLM setup completed successfully")
    else:
        logger.error(f"Fallback LLM setup failed: {message}")

    return success


def is_fallback_llm_available() -> bool:
    """Quick check if fallback LLM is available."""
    try:
        setup = get_fallback_llm_setup()
        return setup.is_fallback_ready()
    except Exception:
        return False
