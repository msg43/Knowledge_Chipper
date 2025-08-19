"""Caching layer for HCE embeddings to improve performance."""

import hashlib
import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """Cache for storing and retrieving embeddings to avoid recomputation.

    Uses a two-tier caching system:
    1. In-memory cache for fast access
    2. Disk cache for persistence across sessions
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        max_memory_items: int = 10000,
        ttl_hours: int = 24 * 7,  # 1 week default
    ):
        """Initialize the embedding cache.

        Args:
            cache_dir: Directory for disk cache. Defaults to ~/.cache/knowledge_chipper/embeddings
            max_memory_items: Maximum items to keep in memory
            ttl_hours: Time-to-live for cached items in hours
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "knowledge_chipper" / "embeddings"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_memory_items = max_memory_items
        self.ttl_hours = ttl_hours

        # In-memory cache: key -> (embedding, timestamp)
        self._memory_cache: dict[str, tuple[np.ndarray, float]] = {}

        # Track access order for LRU eviction
        self._access_order: list[str] = []

        logger.info(f"Initialized embedding cache at {self.cache_dir}")

    def _generate_key(self, text: str, model_name: str) -> str:
        """Generate a unique cache key for text and model combination."""
        content = f"{model_name}::{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_disk_path(self, key: str) -> Path:
        """Get the disk cache path for a key."""
        # Use subdirectories to avoid too many files in one directory
        subdir = key[:2]
        return self.cache_dir / subdir / f"{key}.pkl"

    def get(self, text: str, model_name: str) -> np.ndarray | None:
        """Retrieve embedding from cache if available.

        Args:
            text: The text that was embedded
            model_name: The model used for embedding

        Returns:
            The cached embedding array or None if not found
        """
        key = self._generate_key(text, model_name)

        # Check memory cache first
        if key in self._memory_cache:
            embedding, timestamp = self._memory_cache[key]
            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            logger.debug(f"Cache hit (memory): {key[:8]}...")
            return embedding

        # Check disk cache
        disk_path = self._get_disk_path(key)
        if disk_path.exists():
            try:
                with open(disk_path, "rb") as f:
                    data = pickle.load(f)

                embedding = data["embedding"]
                timestamp = data["timestamp"]

                # Check TTL
                import time

                age_hours = (time.time() - timestamp) / 3600
                if age_hours > self.ttl_hours:
                    logger.debug(f"Cache expired: {key[:8]}... (age: {age_hours:.1f}h)")
                    disk_path.unlink()
                    return None

                # Add to memory cache
                self._add_to_memory_cache(key, embedding, timestamp)
                logger.debug(f"Cache hit (disk): {key[:8]}...")
                return embedding

            except Exception as e:
                logger.warning(f"Failed to load cached embedding: {e}")
                return None

        logger.debug(f"Cache miss: {key[:8]}...")
        return None

    def put(self, text: str, model_name: str, embedding: np.ndarray) -> None:
        """Store embedding in cache.

        Args:
            text: The text that was embedded
            model_name: The model used for embedding
            embedding: The embedding array to cache
        """
        key = self._generate_key(text, model_name)

        import time

        timestamp = time.time()

        # Add to memory cache
        self._add_to_memory_cache(key, embedding, timestamp)

        # Save to disk
        disk_path = self._get_disk_path(key)
        disk_path.parent.mkdir(exist_ok=True)

        try:
            with open(disk_path, "wb") as f:
                pickle.dump(
                    {
                        "embedding": embedding,
                        "timestamp": timestamp,
                        "text_preview": text[:100],  # For debugging
                        "model_name": model_name,
                    },
                    f,
                )
            logger.debug(f"Cached to disk: {key[:8]}...")
        except Exception as e:
            logger.warning(f"Failed to cache embedding to disk: {e}")

    def _add_to_memory_cache(
        self, key: str, embedding: np.ndarray, timestamp: float
    ) -> None:
        """Add item to memory cache with LRU eviction."""
        # Evict oldest items if at capacity
        while len(self._memory_cache) >= self.max_memory_items:
            if self._access_order:
                oldest_key = self._access_order.pop(0)
                del self._memory_cache[oldest_key]

        self._memory_cache[key] = (embedding, timestamp)
        self._access_order.append(key)

    def get_batch(
        self, texts: list[str], model_name: str
    ) -> tuple[list[np.ndarray | None], list[int]]:
        """Retrieve multiple embeddings from cache.

        Args:
            texts: List of texts to look up
            model_name: The model used for embeddings

        Returns:
            Tuple of (embeddings, missing_indices)
            - embeddings: List with cached embeddings or None for misses
            - missing_indices: Indices of texts that weren't in cache
        """
        embeddings = []
        missing_indices = []

        for i, text in enumerate(texts):
            embedding = self.get(text, model_name)
            embeddings.append(embedding)
            if embedding is None:
                missing_indices.append(i)

        return embeddings, missing_indices

    def put_batch(
        self, texts: list[str], model_name: str, embeddings: list[np.ndarray]
    ) -> None:
        """Store multiple embeddings in cache.

        Args:
            texts: List of texts that were embedded
            model_name: The model used for embeddings
            embeddings: List of embedding arrays
        """
        for text, embedding in zip(texts, embeddings):
            self.put(text, model_name, embedding)

    def clear(self) -> None:
        """Clear all cached embeddings."""
        self._memory_cache.clear()
        self._access_order.clear()

        # Remove disk cache
        import shutil

        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Cleared embedding cache")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        disk_files = sum(1 for _ in self.cache_dir.rglob("*.pkl"))
        disk_size = sum(f.stat().st_size for f in self.cache_dir.rglob("*.pkl"))

        return {
            "memory_items": len(self._memory_cache),
            "memory_capacity": self.max_memory_items,
            "disk_files": disk_files,
            "disk_size_mb": disk_size / (1024 * 1024),
            "cache_dir": str(self.cache_dir),
        }


# Global cache instance
_global_cache: EmbeddingCache | None = None


def get_embedding_cache() -> EmbeddingCache:
    """Get the global embedding cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = EmbeddingCache()
    return _global_cache


def clear_embedding_cache() -> None:
    """Clear the global embedding cache."""
    cache = get_embedding_cache()
    cache.clear()
