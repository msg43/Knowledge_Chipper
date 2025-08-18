"""
Model caching utilities for Knowledge Chipper.

This module provides caching for expensive-to-load models like whisper.cpp
and pyannote.audio diarization models, allowing them to be reused across
multiple processing sessions.
"""

import threading
import time
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class ModelType(Enum):
    """Types of models that can be cached."""

    WHISPER_CPP = "whisper_cpp"
    DIARIZATION = "diarization"
    TRANSCRIPTION = "transcription"


@dataclass
class CachedModel:
    """Represents a cached model with metadata."""

    model_id: str
    model_type: ModelType
    model_instance: Any
    load_time: float
    last_used: float
    memory_usage_mb: float
    use_count: int = 0

    def touch(self):
        """Mark model as recently used."""
        self.last_used = time.time()
        self.use_count += 1


class ModelCache:
    """Global model cache with memory management."""

    def __init__(self, max_memory_mb: float = 8192):  # 8GB default limit
        """
        Initialize model cache.

        Args:
            max_memory_mb: Maximum memory usage in MB before evicting models
        """
        self.max_memory_mb = max_memory_mb
        self.cache: dict[str, CachedModel] = {}
        self.lock = threading.RLock()
        self._total_memory_mb = 0.0

        logger.info(f"Model cache initialized with {max_memory_mb}MB limit")

    def _generate_cache_key(
        self, model_type: ModelType, model_name: str, device: str, **kwargs
    ) -> str:
        """Generate a unique cache key for a model configuration."""
        # Sort kwargs for consistent key generation
        sorted_kwargs = sorted(kwargs.items())
        kwargs_str = "_".join(f"{k}={v}" for k, v in sorted_kwargs)

        return f"{model_type.value}:{model_name}:{device}:{kwargs_str}"

    def _estimate_model_memory(self, model_type: ModelType, model_name: str) -> float:
        """Estimate memory usage for a model in MB."""
        if model_type == ModelType.WHISPER_CPP:
            # Whisper model size estimates
            sizes = {
                "tiny": 150,
                "base": 300,
                "small": 500,
                "medium": 1200,
                "large": 2000,
                "large-v3": 2000,
            }
            return sizes.get(model_name, 500)  # Default to 500MB

        elif model_type == ModelType.DIARIZATION:
            # Diarization models are typically around 1GB
            return 1024

        else:
            return 512  # Default estimate

    def _evict_lru_models(self, required_memory_mb: float):
        """Evict least recently used models to free up memory."""
        if not self.cache:
            return

        # Sort by last used time (oldest first)
        sorted_models = sorted(self.cache.values(), key=lambda m: m.last_used)

        memory_to_free = (
            self._total_memory_mb + required_memory_mb
        ) - self.max_memory_mb
        freed_memory = 0.0

        for model in sorted_models:
            if freed_memory >= memory_to_free:
                break

            logger.info(
                f"Evicting model {model.model_id} (used {model.use_count} times, {model.memory_usage_mb:.1f}MB)"
            )

            # Remove from cache
            del self.cache[model.model_id]
            freed_memory += model.memory_usage_mb
            self._total_memory_mb -= model.memory_usage_mb

            # Try to explicitly delete the model (may not work for all model types)
            try:
                del model.model_instance
            except:
                pass

        logger.info(f"Freed {freed_memory:.1f}MB of model cache memory")

    def get_model(
        self,
        model_type: ModelType,
        model_name: str,
        device: str,
        loader_func: Callable[[], Any],
        **kwargs,
    ) -> Any:
        """
        Get a model from cache or load it if not cached.

        Args:
            model_type: Type of model being cached
            model_name: Name/identifier of the model
            device: Device the model should run on
            loader_func: Function to call if model needs to be loaded
            **kwargs: Additional parameters for cache key generation

        Returns:
            The loaded model instance
        """
        cache_key = self._generate_cache_key(model_type, model_name, device, **kwargs)

        with self.lock:
            # Check if model is already cached
            if cache_key in self.cache:
                cached_model = self.cache[cache_key]
                cached_model.touch()
                logger.info(
                    f"Using cached {model_type.value} model: {model_name} (used {cached_model.use_count} times)"
                )
                return cached_model.model_instance

            # Model not cached, need to load it
            logger.info(f"Loading {model_type.value} model: {model_name}")
            load_start = time.time()

            # Estimate memory requirement
            estimated_memory = self._estimate_model_memory(model_type, model_name)

            # Check if we need to evict models to make room
            if self._total_memory_mb + estimated_memory > self.max_memory_mb:
                logger.info(
                    f"Cache memory limit would be exceeded, evicting LRU models"
                )
                self._evict_lru_models(estimated_memory)

            # Load the model
            try:
                model_instance = loader_func()
                load_time = time.time() - load_start

                # Create cache entry
                cached_model = CachedModel(
                    model_id=cache_key,
                    model_type=model_type,
                    model_instance=model_instance,
                    load_time=load_time,
                    last_used=time.time(),
                    memory_usage_mb=estimated_memory,
                    use_count=1,
                )

                # Add to cache
                self.cache[cache_key] = cached_model
                self._total_memory_mb += estimated_memory

                logger.info(
                    f"Loaded and cached {model_type.value} model: {model_name} "
                    f"({load_time:.1f}s, {estimated_memory:.1f}MB)"
                )

                return model_instance

            except Exception as e:
                logger.error(
                    f"Failed to load {model_type.value} model {model_name}: {e}"
                )
                raise

    def clear_cache(self, model_type: ModelType | None = None):
        """
        Clear cached models.

        Args:
            model_type: If specified, only clear models of this type
        """
        with self.lock:
            if model_type is None:
                # Clear all models
                count = len(self.cache)
                memory_freed = self._total_memory_mb
                self.cache.clear()
                self._total_memory_mb = 0.0
                logger.info(
                    f"Cleared all cached models: {count} models, {memory_freed:.1f}MB freed"
                )
            else:
                # Clear only specific model type
                to_remove = [
                    key
                    for key, model in self.cache.items()
                    if model.model_type == model_type
                ]

                memory_freed = 0.0
                for key in to_remove:
                    memory_freed += self.cache[key].memory_usage_mb
                    del self.cache[key]

                self._total_memory_mb -= memory_freed
                logger.info(
                    f"Cleared {len(to_remove)} {model_type.value} models, {memory_freed:.1f}MB freed"
                )

    def get_cache_stats(self) -> dict[str, Any]:
        """Get statistics about the current cache state."""
        with self.lock:
            stats = {
                "total_models": len(self.cache),
                "total_memory_mb": self._total_memory_mb,
                "max_memory_mb": self.max_memory_mb,
                "memory_utilization": self._total_memory_mb / self.max_memory_mb
                if self.max_memory_mb > 0
                else 0,
                "models_by_type": {},
                "oldest_model_age": 0,
                "most_used_count": 0,
            }

            if self.cache:
                now = time.time()
                oldest_time = min(model.last_used for model in self.cache.values())
                most_used = max(model.use_count for model in self.cache.values())

                stats["oldest_model_age"] = now - oldest_time
                stats["most_used_count"] = most_used

                # Count by type
                for model in self.cache.values():
                    model_type = model.model_type.value
                    if model_type not in stats["models_by_type"]:
                        stats["models_by_type"][model_type] = {
                            "count": 0,
                            "memory_mb": 0,
                        }

                    stats["models_by_type"][model_type]["count"] += 1
                    stats["models_by_type"][model_type][
                        "memory_mb"
                    ] += model.memory_usage_mb

            return stats


# Global model cache instance
_global_cache: ModelCache | None = None
_cache_lock = threading.Lock()


def get_model_cache(max_memory_mb: float = 8192) -> ModelCache:
    """Get the global model cache instance."""
    global _global_cache

    with _cache_lock:
        if _global_cache is None:
            _global_cache = ModelCache(max_memory_mb=max_memory_mb)
        return _global_cache


def cache_whisper_model(
    model_name: str, device: str, loader_func: Callable[[], Any], **kwargs
) -> Any:
    """
    Cache a whisper model.

    Args:
        model_name: Name of the whisper model
        device: Device to run on
        loader_func: Function to load the model
        **kwargs: Additional parameters

    Returns:
        The cached model instance
    """
    cache = get_model_cache()
    return cache.get_model(
        ModelType.WHISPER_CPP, model_name, device, loader_func, **kwargs
    )


def cache_diarization_model(
    model_name: str, device: str, loader_func: Callable[[], Any], **kwargs
) -> Any:
    """
    Cache a diarization model.

    Args:
        model_name: Name of the diarization model
        device: Device to run on
        loader_func: Function to load the model
        **kwargs: Additional parameters

    Returns:
        The cached model instance
    """
    cache = get_model_cache()
    return cache.get_model(
        ModelType.DIARIZATION, model_name, device, loader_func, **kwargs
    )


def clear_model_cache(model_type: ModelType | None = None):
    """Clear the global model cache."""
    cache = get_model_cache()
    cache.clear_cache(model_type)


def get_cache_statistics() -> dict[str, Any]:
    """Get statistics about the global model cache."""
    cache = get_model_cache()
    return cache.get_cache_stats()


# Testing and utilities
def test_model_cache():
    """Test the model caching functionality."""
    print("🧠 Model Cache Test")
    print("=" * 20)

    # Test cache creation
    cache = ModelCache(max_memory_mb=2048)  # 2GB limit

    # Mock model loader
    def mock_whisper_loader():
        time.sleep(0.1)  # Simulate loading time
        return {"model": "mock_whisper", "loaded": time.time()}

    def mock_diarization_loader():
        time.sleep(0.2)  # Simulate loading time
        return {"model": "mock_diarization", "loaded": time.time()}

    # Test loading models
    print("Loading whisper model...")
    model1 = cache.get_model(ModelType.WHISPER_CPP, "base", "mps", mock_whisper_loader)

    print("Loading same whisper model again (should be cached)...")
    model2 = cache.get_model(ModelType.WHISPER_CPP, "base", "mps", mock_whisper_loader)

    print(f"✅ Same instance: {model1 is model2}")

    print("Loading diarization model...")
    model3 = cache.get_model(
        ModelType.DIARIZATION,
        "pyannote/speaker-diarization@2023.07",
        "mps",
        mock_diarization_loader,
    )

    # Test cache stats
    stats = cache.get_cache_stats()
    print(
        f"✅ Cache stats: {stats['total_models']} models, {stats['total_memory_mb']:.1f}MB"
    )

    # Test eviction by loading many models
    print("Testing cache eviction...")
    for i in range(5):
        cache.get_model(ModelType.WHISPER_CPP, f"model_{i}", "cpu", mock_whisper_loader)

    final_stats = cache.get_cache_stats()
    print(
        f"✅ After loading many models: {final_stats['total_models']} models, {final_stats['total_memory_mb']:.1f}MB"
    )

    # Test clearing cache
    cache.clear_cache()
    empty_stats = cache.get_cache_stats()
    print(
        f"✅ After clearing: {empty_stats['total_models']} models, {empty_stats['total_memory_mb']:.1f}MB"
    )


if __name__ == "__main__":
    test_model_cache()
