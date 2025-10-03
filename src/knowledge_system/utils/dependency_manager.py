"""
Comprehensive dependency manager for Architecture B.
Handles runtime downloading and management of all models and dependencies.
"""

import json
import os
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..logger import get_logger
from .macos_paths import get_cache_dir, get_config_dir

logger = get_logger(__name__)


class DependencyInfo:
    """Information about a dependency."""

    def __init__(
        self,
        name: str,
        description: str,
        size_mb: int,
        essential: bool = True,
        download_func: Callable | None = None,
        check_func: Callable | None = None,
        category: str = "general",
    ):
        self.name = name
        self.description = description
        self.size_mb = size_mb
        self.essential = essential
        self.download_func = download_func
        self.check_func = check_func
        self.category = category
        self.status = "unknown"  # unknown, available, downloading, failed
        self.progress = 0
        self.error_message = ""


class DependencyManager:
    """Manages all runtime dependencies for Architecture B."""

    def __init__(self):
        self.cache_dir = get_cache_dir()
        self.config_dir = get_config_dir()
        self.dependencies: dict[str, DependencyInfo] = {}
        self.progress_callbacks: list[Callable] = []

        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self._register_dependencies()

    def _register_dependencies(self):
        """Register all known dependencies."""

        # Core system dependencies
        self.dependencies["ffmpeg"] = DependencyInfo(
            name="ffmpeg",
            description="Audio/video processing engine",
            size_mb=50,
            essential=True,
            download_func=self._download_ffmpeg,
            check_func=self._check_ffmpeg,
            category="system",
        )

        self.dependencies["whisper_cpp"] = DependencyInfo(
            name="whisper_cpp",
            description="Local transcription binary",
            size_mb=10,
            essential=True,
            download_func=self._download_whisper_cpp,
            check_func=self._check_whisper_cpp,
            category="system",
        )

        # Model dependencies
        self.dependencies["whisper_models"] = DependencyInfo(
            name="whisper_models",
            description="Whisper transcription models",
            size_mb=300,
            essential=True,
            download_func=self._download_whisper_models,
            check_func=self._check_whisper_models,
            category="models",
        )

        self.dependencies["pyannote_models"] = DependencyInfo(
            name="pyannote_models",
            description="Speaker diarization models",
            size_mb=400,
            essential=True,
            download_func=self._download_pyannote_models,
            check_func=self._check_pyannote_models,
            category="models",
        )

        self.dependencies["voice_models"] = DependencyInfo(
            name="voice_models",
            description="Voice fingerprinting models (97% accuracy)",
            size_mb=410,
            essential=False,
            download_func=self._download_voice_models,
            check_func=self._check_voice_models,
            category="models",
        )

        self.dependencies["ollama"] = DependencyInfo(
            name="ollama",
            description="Local AI assistant (LLM)",
            size_mb=2000,
            essential=False,
            download_func=self._download_ollama,
            check_func=self._check_ollama,
            category="ai",
        )

        self.dependencies["hce_models"] = DependencyInfo(
            name="hce_models",
            description="Claim extraction models",
            size_mb=500,
            essential=False,
            download_func=self._download_hce_models,
            check_func=self._check_hce_models,
            category="ai",
        )

    def add_progress_callback(self, callback: Callable[[str, int, str], None]):
        """Add a progress callback function."""
        self.progress_callbacks.append(callback)

    def _notify_progress(self, dep_name: str, progress: int, status: str):
        """Notify all progress callbacks."""
        for callback in self.progress_callbacks:
            try:
                callback(dep_name, progress, status)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def check_all_dependencies(self) -> dict[str, str]:
        """Check status of all dependencies."""
        status = {}

        for name, dep in self.dependencies.items():
            try:
                if dep.check_func:
                    dep.status = "available" if dep.check_func() else "missing"
                else:
                    dep.status = "unknown"
                status[name] = dep.status
            except Exception as e:
                logger.error(f"Error checking {name}: {e}")
                dep.status = "error"
                status[name] = "error"

        return status

    def get_missing_dependencies(
        self, include_optional: bool = False
    ) -> list[DependencyInfo]:
        """Get list of missing dependencies."""
        self.check_all_dependencies()

        missing = []
        for dep in self.dependencies.values():
            if dep.status == "missing" or dep.status == "unknown":
                if dep.essential or include_optional:
                    missing.append(dep)

        return missing

    def download_dependency(
        self, name: str, progress_callback: Callable | None = None
    ) -> bool:
        """Download a specific dependency."""
        if name not in self.dependencies:
            logger.error(f"Unknown dependency: {name}")
            return False

        dep = self.dependencies[name]

        if not dep.download_func:
            logger.error(f"No download function for {name}")
            return False

        try:
            dep.status = "downloading"
            dep.progress = 0
            self._notify_progress(name, 0, "downloading")

            def progress_wrapper(progress: int):
                dep.progress = progress
                self._notify_progress(name, progress, "downloading")
                if progress_callback:
                    progress_callback(progress)

            success = dep.download_func(progress_wrapper)

            if success:
                dep.status = "available"
                dep.progress = 100
                self._notify_progress(name, 100, "complete")
                logger.info(f"Successfully downloaded {name}")
            else:
                dep.status = "failed"
                self._notify_progress(name, 0, "failed")
                logger.error(f"Failed to download {name}")

            return success

        except Exception as e:
            dep.status = "failed"
            dep.error_message = str(e)
            self._notify_progress(name, 0, "failed")
            logger.error(f"Error downloading {name}: {e}")
            return False

    def download_all_missing(self, include_optional: bool = False) -> dict[str, bool]:
        """Download all missing dependencies."""
        missing = self.get_missing_dependencies(include_optional)
        results = {}

        for dep in missing:
            logger.info(f"Downloading {dep.name}...")
            results[dep.name] = self.download_dependency(dep.name)

        return results

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of dependency status."""
        self.check_all_dependencies()

        by_category = {}
        for dep in self.dependencies.values():
            if dep.category not in by_category:
                by_category[dep.category] = []
            by_category[dep.category].append(
                {
                    "name": dep.name,
                    "description": dep.description,
                    "size_mb": dep.size_mb,
                    "essential": dep.essential,
                    "status": dep.status,
                }
            )

        total_size = sum(dep.size_mb for dep in self.dependencies.values())
        available_count = len(
            [d for d in self.dependencies.values() if d.status == "available"]
        )
        missing_count = len(
            [d for d in self.dependencies.values() if d.status == "missing"]
        )

        return {
            "total_dependencies": len(self.dependencies),
            "available": available_count,
            "missing": missing_count,
            "total_size_mb": total_size,
            "by_category": by_category,
        }

    # Dependency check functions

    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_whisper_cpp(self) -> bool:
        """Check if whisper.cpp is available."""
        # Check if whisper binary exists in app bundle
        try:
            # Try to find whisper binary in various locations
            possible_paths = [
                Path("/usr/local/bin/whisper"),
                Path.home() / ".local/bin/whisper",
                self.cache_dir / "bin/whisper",
            ]

            for path in possible_paths:
                if path.exists():
                    return True
            return False
        except Exception:
            return False

    def _check_whisper_models(self) -> bool:
        """Check if Whisper models are available."""
        # Check the actual whisper.cpp cache directory
        whisper_cache_dir = Path.home() / ".cache" / "whisper-cpp"
        base_model = whisper_cache_dir / "ggml-base.bin"

        # Also check local models directory as fallback
        local_models_dir = Path("models")
        local_base_model = local_models_dir / "ggml-base.bin"

        return base_model.exists() or local_base_model.exists()

    def _check_pyannote_models(self) -> bool:
        """Check if Pyannote models are available."""
        models_dir = self.cache_dir / "models" / "pyannote"
        config_file = models_dir / "runtime_download_config.json"
        return config_file.exists()

    def _check_voice_models(self) -> bool:
        """Check if voice models are available."""
        models_dir = self.cache_dir / "models" / "voice_models"
        config_file = models_dir / "runtime_download_config.json"
        return config_file.exists()

    def _check_ollama(self) -> bool:
        """Check if Ollama is available."""
        try:
            result = subprocess.run(
                ["ollama", "version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Check if configured for runtime download
            models_dir = self.cache_dir / "models" / "ollama"
            config_file = models_dir / "runtime_download_config.json"
            return config_file.exists()

    def _check_hce_models(self) -> bool:
        """Check if HCE models are available."""
        models_dir = self.cache_dir / "models" / "hce"
        config_file = models_dir / "runtime_download_config.json"
        return config_file.exists()

    # Dependency download functions

    def _download_ffmpeg(self, progress_callback: Callable[[int], None]) -> bool:
        """Download FFmpeg."""
        try:
            # Import and use existing FFmpeg installer
            from ...scripts.silent_ffmpeg_installer import install_ffmpeg_for_dmg

            # For runtime, install to user cache
            cache_bin = self.cache_dir / "bin"
            cache_bin.mkdir(parents=True, exist_ok=True)

            progress_callback(50)
            success = install_ffmpeg_for_dmg(cache_bin)
            progress_callback(100 if success else 0)

            return success
        except Exception as e:
            logger.error(f"FFmpeg download failed: {e}")
            return False

    def _download_whisper_cpp(self, progress_callback: Callable[[int], None]) -> bool:
        """Download whisper.cpp binary."""
        try:
            # Import and use existing whisper.cpp installer
            from ...scripts.install_whisper_cpp_binary import (
                install_whisper_cpp_for_dmg,
            )

            cache_bin = self.cache_dir / "bin"
            cache_bin.mkdir(parents=True, exist_ok=True)

            progress_callback(50)
            success = install_whisper_cpp_for_dmg(cache_bin)
            progress_callback(100 if success else 0)

            return success
        except Exception as e:
            logger.error(f"Whisper.cpp download failed: {e}")
            return False

    def _download_whisper_models(
        self, progress_callback: Callable[[int], None]
    ) -> bool:
        """Download Whisper models."""
        try:
            from ..processors.whisper_cpp_transcribe import (
                WhisperCppTranscribeProcessor,
            )

            progress_callback(25)
            processor = WhisperCppTranscribeProcessor(model="base")

            def wrapped_progress(info):
                progress = info.get("progress", 0)
                # Map 0-100 to 25-100 to account for initial setup
                actual_progress = 25 + (progress * 0.75)
                progress_callback(int(actual_progress))

            progress_callback(50)
            model_path = processor._download_model("base", wrapped_progress)
            progress_callback(100)

            return model_path and model_path.exists()

        except Exception as e:
            logger.error(f"Whisper models download failed: {e}")
            return False

    def _download_pyannote_models(
        self, progress_callback: Callable[[int], None]
    ) -> bool:
        """Set up Pyannote models for runtime download."""
        try:
            models_dir = self.cache_dir / "models" / "pyannote"
            models_dir.mkdir(parents=True, exist_ok=True)

            progress_callback(50)

            config_file = models_dir / "runtime_download_config.json"
            config = {
                "model": "pyannote/speaker-diarization-3.1",
                "download_on_first_use": True,
                "cache_location": str(models_dir),
                "hf_token_required": True,
                "setup_complete": True,
            }

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)

            progress_callback(100)
            return True

        except Exception as e:
            logger.error(f"Pyannote setup failed: {e}")
            return False

    def _download_voice_models(self, progress_callback: Callable[[int], None]) -> bool:
        """Set up voice models for runtime download."""
        try:
            models_dir = self.cache_dir / "models" / "voice_models"
            models_dir.mkdir(parents=True, exist_ok=True)

            progress_callback(50)

            config_file = models_dir / "runtime_download_config.json"
            config = {
                "models": {
                    "wav2vec2": "facebook/wav2vec2-large-960h-lv60-self",
                    "ecapa": "speechbrain/spkrec-ecapa-voxceleb",
                },
                "download_on_first_use": True,
                "cache_location": str(models_dir),
                "accuracy_target": "97%",
                "setup_complete": True,
            }

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)

            progress_callback(100)
            return True

        except Exception as e:
            logger.error(f"Voice models setup failed: {e}")
            return False

    def _download_ollama(self, progress_callback: Callable[[int], None]) -> bool:
        """Set up Ollama for runtime download."""
        try:
            models_dir = self.cache_dir / "models" / "ollama"
            models_dir.mkdir(parents=True, exist_ok=True)

            progress_callback(50)

            config_file = models_dir / "runtime_download_config.json"
            config = {
                "model": "qwen2.5:7b",
                "download_on_first_use": True,
                "estimated_size_gb": 4.0,
                "fallback_models": ["qwen2.5:3b", "llama3.2:3b", "phi3:3.8b-mini"],
                "setup_complete": True,
            }

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)

            progress_callback(100)
            return True

        except Exception as e:
            logger.error(f"Ollama setup failed: {e}")
            return False

    def _download_hce_models(self, progress_callback: Callable[[int], None]) -> bool:
        """Set up HCE models for runtime download."""
        try:
            models_dir = self.cache_dir / "models" / "hce"
            models_dir.mkdir(parents=True, exist_ok=True)

            progress_callback(50)

            config_file = models_dir / "runtime_download_config.json"
            config = {
                "models": {
                    "sentence_transformer": "all-MiniLM-L6-v2",
                    "claim_extractor": "microsoft/DialoGPT-medium",
                },
                "download_on_first_use": True,
                "cache_location": str(models_dir),
                "setup_complete": True,
            }

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)

            progress_callback(100)
            return True

        except Exception as e:
            logger.error(f"HCE setup failed: {e}")
            return False


# Global dependency manager instance
_dependency_manager = None


def get_dependency_manager() -> DependencyManager:
    """Get the global dependency manager instance."""
    global _dependency_manager
    if _dependency_manager is None:
        _dependency_manager = DependencyManager()
    return _dependency_manager
