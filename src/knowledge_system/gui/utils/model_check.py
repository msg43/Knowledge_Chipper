"""Utility to check model availability before feature use."""
from typing import Optional, Tuple

from ...logger import get_logger
from ...utils.model_validator import get_model_validator

logger = get_logger(__name__)


def check_model_before_use(
    feature: str, model_type: str = "whisper"
) -> tuple[bool, str | None]:
    """
    Check if required model is available before using a feature.

    Args:
        feature: Name of the feature being used (for user messages)
        model_type: Type of model required ("whisper" or "llm")

    Returns:
        Tuple of (is_available, error_message)
    """
    try:
        validator = get_model_validator()

        if model_type == "whisper":
            if validator.has_valid_whisper_model():
                return True, None
            else:
                return False, f"{feature} requires a Whisper model for transcription"

        elif model_type == "llm":
            if validator.has_valid_llm_model():
                return True, None
            else:
                return False, f"{feature} requires an LLM model for processing"

        else:
            return False, f"Unknown model type: {model_type}"

    except Exception as e:
        logger.error(f"Error checking model availability: {e}")
        return False, f"Error checking model: {e}"


def ensure_models_ready(main_window, feature: str, required_models: list) -> bool:
    """
    Ensure required models are ready, showing notification if not.

    Args:
        main_window: Reference to main window for notifications
        feature: Name of the feature
        required_models: List of model types required

    Returns:
        True if all models are ready, False otherwise
    """
    try:
        validator = get_model_validator()
        missing = []

        for model_type in required_models:
            if model_type == "whisper" and not validator.has_valid_whisper_model():
                missing.append("whisper")
            elif model_type == "llm" and not validator.has_valid_llm_model():
                missing.append("llm")

        if missing:
            # Show notification
            if hasattr(main_window, "model_notification"):
                main_window.model_notification.show_feature_blocked(
                    feature, " and ".join(missing)
                )

            # Start download if not already running
            missing_dict = validator.get_missing_models()
            if missing_dict and hasattr(
                main_window, "_start_background_model_download"
            ):
                main_window._start_background_model_download(missing_dict)

            return False

        return True

    except Exception as e:
        logger.error(f"Error ensuring models ready: {e}")
        return False
