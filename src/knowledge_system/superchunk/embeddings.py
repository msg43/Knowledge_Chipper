from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..config import get_settings


@dataclass
class EmbeddingsResult:
    vectors: list[list[float]]
    model: str
    dims: int


class EmbeddingsBackend:
    def embed_texts(
        self, texts: list[str]
    ) -> EmbeddingsResult:  # pragma: no cover (interface)
        raise NotImplementedError


class OpenAIEmbeddings(EmbeddingsBackend):
    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        # Choose a reasonable default small embedding model; align with provider selection later if needed
        self.model = model or "text-embedding-3-small"
        self._api_key = settings.api_keys.openai_api_key or settings.api_keys.openai

    def embed_texts(self, texts: list[str]) -> EmbeddingsResult:
        import openai

        client = openai.OpenAI(api_key=self._api_key)
        resp = client.embeddings.create(model=self.model, input=texts)
        vectors = [d.embedding for d in resp.data]
        dims = len(vectors[0]) if vectors else 0
        return EmbeddingsResult(vectors=vectors, model=self.model, dims=dims)


class FallbackEmbeddings(EmbeddingsBackend):
    def embed_texts(self, texts: list[str]) -> EmbeddingsResult:
        # Return zero vectors to signal unavailability
        return EmbeddingsResult(
            vectors=[[0.0] * 8 for _ in texts], model="none", dims=8
        )
