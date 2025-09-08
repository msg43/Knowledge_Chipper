"""Embedder implementation with caching support."""

import logging
from typing import List, Union

import numpy as np

logger = logging.getLogger(__name__)


class Embedder:
    """Text embedder with automatic caching support."""

    def __init__(self, name: str):
        """Initialize embedder with the specified model.

        Args:
            name: Model name (e.g., 'all-MiniLM-L6-v2')
        """
        self.name = name
        self._model = None
        self._cache = None

    def _ensure_model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.name}")
                self._model = SentenceTransformer(self.name)
            except ImportError:
                logger.error("sentence-transformers not installed")
                raise

    def _ensure_cache(self):
        """Lazy load the embedding cache."""
        if self._cache is None:
            try:
                from ....utils.embedding_cache import get_embedding_cache

                self._cache = get_embedding_cache()
            except ImportError:
                logger.warning(
                    "Embedding cache not available, continuing without cache"
                )
                self._cache = None

    def encode(self, texts: str | list[str], use_cache: bool = True) -> np.ndarray:
        """Encode texts into embeddings with optional caching.

        Args:
            texts: Single text or list of texts to encode
            use_cache: Whether to use the embedding cache

        Returns:
            Embeddings array of shape (n_texts, embedding_dim)
        """
        # Handle single text
        if isinstance(texts, str):
            texts = [texts]
            single_text = True
        else:
            single_text = False

        self._ensure_model()

        # If caching is disabled, encode directly
        if not use_cache:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return embeddings[0] if single_text else embeddings

        # Try to use cache
        self._ensure_cache()

        if self._cache is None:
            # Cache not available, encode directly
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return embeddings[0] if single_text else embeddings

        # Check cache
        cached_embeddings, missing_indices = self._cache.get_batch(texts, self.name)

        # If all found in cache
        if not missing_indices:
            embeddings = np.array([emb for emb in cached_embeddings])
            return embeddings[0] if single_text else embeddings

        # Encode missing texts
        missing_texts = [texts[i] for i in missing_indices]
        new_embeddings = self._model.encode(missing_texts, show_progress_bar=False)

        # Store in cache
        self._cache.put_batch(missing_texts, self.name, new_embeddings)

        # Combine cached and new embeddings
        result = []
        new_idx = 0
        for i, cached_emb in enumerate(cached_embeddings):
            if cached_emb is not None:
                result.append(cached_emb)
            else:
                result.append(new_embeddings[new_idx])
                new_idx += 1

        embeddings = np.array(result)
        return embeddings[0] if single_text else embeddings
