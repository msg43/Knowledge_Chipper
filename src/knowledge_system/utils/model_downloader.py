"""
Model Downloader Utility

Pre-download models to avoid hangs during processing.
"""

import os
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..logger import get_logger

logger = get_logger(__name__)


def pre_download_diarization_model(progress_callback=None) -> bool:
    """
    Pre-download the pyannote diarization model to avoid hangs during processing.

    Args:
        progress_callback: Optional callback for progress updates

    Returns:
        True if model is available (cached or downloaded), False otherwise
    """
    try:
        # Check if already cached (in either location)
        hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
        pyannote_cache = Path.home() / ".cache" / "torch" / "pyannote"
        model_name = "pyannote/speaker-diarization-3.1"
        model_id = model_name.replace("/", "--")

        # Check both possible cache locations
        cached_models = []
        if hf_cache.exists():
            cached_models = list(hf_cache.glob(f"models--{model_id}*"))
        if not cached_models and pyannote_cache.exists():
            cached_models = list(pyannote_cache.glob(f"models--{model_id}*"))

        if cached_models:
            logger.info(f"Diarization model already cached: {model_name}")
            if progress_callback:
                progress_callback("✅ Diarization model already downloaded", 100)
            return True

        # Get HuggingFace token
        settings = get_settings()
        hf_token = getattr(settings.api_keys, "huggingface_token", None)

        if not hf_token:
            logger.warning(
                "No HuggingFace token found. Please set your token in API Keys settings "
                "to download the diarization model."
            )
            if progress_callback:
                progress_callback("❌ No HuggingFace token found", 0)
            return False

        # Try to download the model
        logger.info(f"Pre-downloading diarization model: {model_name}")
        if progress_callback:
            progress_callback("⏬ Downloading diarization model (~400MB)...", 10)

        try:
            # Import pyannote and trigger download
            from pyannote.audio import Pipeline

            # Set token in environment for pyannote
            os.environ["HF_TOKEN"] = hf_token
            os.environ["HUGGINGFACE_HUB_TOKEN"] = hf_token

            if progress_callback:
                progress_callback("🔄 Loading model from HuggingFace...", 50)

            # This will download the model if not cached
            pipeline = Pipeline.from_pretrained(model_name, use_auth_token=hf_token)

            if pipeline:
                logger.info("✅ Diarization model downloaded successfully")
                if progress_callback:
                    progress_callback("✅ Diarization model ready!", 100)
                return True
            else:
                logger.error("Failed to load diarization model")
                if progress_callback:
                    progress_callback("❌ Failed to load model", 0)
                return False

        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "authorization" in error_msg.lower():
                logger.error(
                    "HuggingFace authentication failed. Please check:\n"
                    "1. Your token is valid\n"
                    "2. You've accepted the model license at https://huggingface.co/pyannote/speaker-diarization\n"
                    "3. Your token has read permissions"
                )
                if progress_callback:
                    progress_callback(
                        "❌ Authentication failed - check token and model license", 0
                    )
            else:
                logger.error(f"Failed to download diarization model: {e}")
                if progress_callback:
                    progress_callback(f"❌ Download failed: {error_msg}", 0)
            return False

    except ImportError:
        logger.error(
            "Diarization dependencies not installed. "
            "Install with: pip install -e '.[diarization]'"
        )
        if progress_callback:
            progress_callback("❌ Diarization dependencies not installed", 0)
        return False
    except Exception as e:
        logger.error(f"Unexpected error pre-downloading model: {e}")
        if progress_callback:
            progress_callback(f"❌ Error: {str(e)}", 0)
        return False


def check_diarization_model_status() -> dict[str, Any]:
    """
    Check the status of the diarization model.

    Returns:
        Dict with status information
    """
    try:
        # Check cache
        hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
        model_name = "pyannote/speaker-diarization-3.1"
        model_id = model_name.replace("/", "--")
        cached_models = (
            list(hf_cache.glob(f"models--{model_id}*")) if hf_cache.exists() else []
        )

        # Check dependencies
        try:
            pass

            dependencies_installed = True
        except ImportError:
            dependencies_installed = False

        # Check token
        settings = get_settings()
        has_token = bool(getattr(settings.api_keys, "huggingface_token", None))

        return {
            "model_name": model_name,
            "is_cached": bool(cached_models),
            "cache_path": str(cached_models[0]) if cached_models else None,
            "dependencies_installed": dependencies_installed,
            "has_hf_token": has_token,
            "estimated_size_mb": 400,
        }

    except Exception as e:
        logger.error(f"Error checking model status: {e}")
        return {
            "model_name": "pyannote/speaker-diarization-3.1",
            "is_cached": False,
            "error": str(e),
        }
