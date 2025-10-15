"""Model validation and compatibility checking utilities."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ModelValidator:
    """Validates and checks compatibility of installed models."""

    # Model families and their compatibility groups
    MODEL_FAMILIES = {
        "whisper": {
            "tiny": ["tiny", "tiny.en"],
            "base": ["base", "base.en"],
            "small": ["small", "small.en"],
            "medium": ["medium", "medium.en"],
            "large": ["large", "large-v1", "large-v2", "large-v3"],
        },
        "llm": {
            # Qwen family models (preferred)
            "qwen_small": ["qwen2.5:0.5b", "qwen2.5:1.5b", "qwen2.5:3b"],
            "qwen_medium": ["qwen2.5:7b", "qwen2.5:14b"],
            "qwen_large": ["qwen2.5:32b", "qwen2.5:72b", "qwen3-next:80b"],
            # Llama family
            "llama_small": ["llama3.2:1b", "llama3.2:3b"],
            "llama_medium": ["llama3.1:8b", "llama3:8b"],
            "llama_large": ["llama3.1:70b", "llama3:70b"],
            # Mistral family
            "mistral_small": ["mistral:7b", "mistral-nemo:12b"],
            "mistral_large": ["mixtral:8x7b", "mixtral:8x22b"],
            # Other capable models
            "other_small": ["phi3:mini", "gemma2:2b", "gemma2:9b"],
            "other_medium": ["solar:10.7b", "command-r:35b"],
            "other_large": ["command-r-plus:104b", "deepseek-v2:236b"],
        },
    }

    # Minimum requirements for each component
    REQUIREMENTS = {
        "whisper": "base",  # Minimum whisper model needed
        "llm": "qwen_medium",  # Preferred LLM capability level
    }

    def __init__(self):
        self.whisper_cache_dir = Path.home() / ".cache" / "whisper-cpp"
        self.settings_dir = Path.home() / ".knowledge_chipper" / "settings"
        self.settings_dir.mkdir(parents=True, exist_ok=True)

        # Cache for model checks to avoid redundant filesystem operations
        self._whisper_models_cache: dict[str, bool] | None = None
        self._llm_models_cache: dict[str, list[str]] | None = None
        self._cache_timestamp: float | None = None
        self._cache_ttl = 5.0  # Cache for 5 seconds to cover startup checks

    def check_whisper_models(self, use_cache: bool = True) -> dict[str, bool]:
        """
        Check which Whisper models are installed.

        Args:
            use_cache: If True, use cached results if available and fresh
        """
        # Check if we have a valid cache
        if (
            use_cache
            and self._whisper_models_cache is not None
            and self._cache_timestamp is not None
        ):
            import time

            if time.time() - self._cache_timestamp < self._cache_ttl:
                return self._whisper_models_cache

        installed = {}

        # Check both cache and local models directory
        check_dirs = [
            self.whisper_cache_dir,
            Path("models"),
        ]

        for model_size in self.MODEL_FAMILIES["whisper"]:
            found = False
            for model_variant in self.MODEL_FAMILIES["whisper"][model_size]:
                for check_dir in check_dirs:
                    if check_dir.exists():
                        model_file = check_dir / f"ggml-{model_variant}.bin"
                        if model_file.exists():
                            found = True
                            logger.info(
                                f"Found Whisper model: {model_variant} at {model_file}"
                            )
                            break
                if found:
                    break
            installed[model_size] = found

        # Update cache
        import time

        self._whisper_models_cache = installed
        self._cache_timestamp = time.time()

        return installed

    def check_llm_models(self, use_cache: bool = True) -> dict[str, list[str]]:
        """
        Check which LLM models are installed via Ollama.

        Args:
            use_cache: If True, use cached results if available and fresh
        """
        # Check if we have a valid cache
        if (
            use_cache
            and self._llm_models_cache is not None
            and self._cache_timestamp is not None
        ):
            import time

            if time.time() - self._cache_timestamp < self._cache_ttl:
                return self._llm_models_cache

        installed = {}

        try:
            from .ollama_manager import get_ollama_manager

            ollama = get_ollama_manager()
            if not ollama.is_service_running():
                logger.warning("Ollama service not running - cannot check LLM models")
                return {}

            # Get all installed models
            models = ollama.get_available_models()
            installed_names = [m.name for m in models]

            # Categorize by family
            for family, variants in self.MODEL_FAMILIES["llm"].items():
                installed[family] = []
                for variant in variants:
                    # Check exact match or version match
                    for installed_model in installed_names:
                        if installed_model == variant or installed_model.startswith(
                            variant.split(":")[0]
                        ):
                            installed[family].append(installed_model)

        except Exception as e:
            logger.error(f"Failed to check LLM models: {e}")

        # Update cache
        import time

        self._llm_models_cache = installed
        self._cache_timestamp = time.time()

        return installed

    def has_valid_whisper_model(self) -> bool:
        """Check if any valid Whisper model is installed."""
        installed = self.check_whisper_models()

        # Check if we have at least the minimum required model
        min_model = self.REQUIREMENTS["whisper"]
        if installed.get(min_model, False):
            return True

        # Check if we have any better model
        model_hierarchy = ["tiny", "base", "small", "medium", "large"]
        min_index = model_hierarchy.index(min_model)

        for i in range(min_index, len(model_hierarchy)):
            if installed.get(model_hierarchy[i], False):
                return True

        return False

    def has_valid_llm_model(self) -> bool:
        """Check if any valid LLM model is installed."""
        installed = self.check_llm_models()

        # Any installed model from any family is valid
        for family, models in installed.items():
            if models:
                logger.info(f"Found valid LLM models in {family} family: {models}")
                return True

        return False

    def get_missing_models(self) -> dict[str, str]:
        """Get list of missing essential models."""
        missing = {}

        if not self.has_valid_whisper_model():
            missing["whisper"] = "base"  # Default model to download

        if not self.has_valid_llm_model():
            missing["llm"] = "qwen2.5:7b"  # Default model to download

        return missing

    def invalidate_cache(self) -> None:
        """Invalidate the model cache to force a fresh check."""
        self._whisper_models_cache = None
        self._llm_models_cache = None
        self._cache_timestamp = None

    def should_download_model(self, model_type: str, model_name: str) -> bool:
        """Check if a specific model should be downloaded."""
        if model_type == "whisper":
            # Don't download if we already have a valid whisper model
            return not self.has_valid_whisper_model()

        elif model_type == "llm":
            # Don't download if we already have any valid LLM
            return not self.has_valid_llm_model()

        return True

    def save_validation_state(self):
        """Save current validation state for startup checks."""
        state = {
            "whisper_models": self.check_whisper_models(),
            "llm_models": self.check_llm_models(),
            "has_valid_whisper": self.has_valid_whisper_model(),
            "has_valid_llm": self.has_valid_llm_model(),
            "missing": self.get_missing_models(),
            "timestamp": datetime.now().isoformat(),
        }

        state_file = self.settings_dir / "model_validation_state.json"
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)

        return state

    def get_model_status_report(self) -> str:
        """Generate human-readable model status report."""
        whisper_models = self.check_whisper_models()
        llm_models = self.check_llm_models()

        report = ["Model Status Report", "=" * 50, ""]

        # Whisper models
        report.append("Whisper Models:")
        for model, installed in whisper_models.items():
            status = "✅ Installed" if installed else "❌ Not installed"
            report.append(f"  {model}: {status}")

        report.append("")

        # LLM models
        report.append("LLM Models:")
        if not llm_models:
            report.append("  ❌ No LLM models found (Ollama may not be running)")
        else:
            for family, models in llm_models.items():
                if models:
                    report.append(f"  {family}:")
                    for model in models:
                        report.append(f"    ✅ {model}")

        report.append("")

        # Overall status
        report.append("Overall Status:")
        report.append(
            f"  Whisper: {'✅ Ready' if self.has_valid_whisper_model() else '❌ Missing'}"
        )
        report.append(
            f"  LLM: {'✅ Ready' if self.has_valid_llm_model() else '❌ Missing'}"
        )

        return "\n".join(report)


# Singleton instance
_validator_instance: ModelValidator | None = None


def get_model_validator() -> ModelValidator:
    """Get or create the model validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ModelValidator()
    return _validator_instance
