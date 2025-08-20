from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .embeddings import EmbeddingsBackend, FallbackEmbeddings, OpenAIEmbeddings
from .vector_store import VectorStore


def _tokenize(text: str) -> set[str]:
    # Normalize tokens by stripping common punctuation and quotes
    return {t.strip(".,;:!?\"'()[]{}").lower() for t in text.split() if t.strip()}


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta and not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


@dataclass
class Retrieval:
    vector_store: VectorStore | None = None
    embeddings: EmbeddingsBackend | None = None

    def ensure_backends(self, vs_path: str | None = None) -> None:
        if self.vector_store is None and vs_path:
            from pathlib import Path

            self.vector_store = VectorStore(Path(vs_path))
        if self.embeddings is None:
            try:
                self.embeddings = OpenAIEmbeddings()
            except Exception:
                self.embeddings = FallbackEmbeddings()

    def index_corpus(self, items: Iterable[tuple[str, str]]) -> None:
        # items: (id, text)
        self.ensure_backends()
        ids, texts = zip(*items)
        vecs = (
            self.embeddings.embed_texts(list(texts)).vectors if self.embeddings else []
        )
        if self.vector_store and vecs:
            self.vector_store.index(ids, texts, vecs)

    def top_k_embeddings(
        self, query_text: str, k: int = 10
    ) -> list[tuple[str, float, str]]:
        self.ensure_backends()
        if not (self.vector_store and self.embeddings):
            return []
        qvec = self.embeddings.embed_texts([query_text]).vectors[0]
        return self.vector_store.top_k(qvec, k)

    def top_k(
        self, query_text: str, corpus: Iterable[tuple[str, str]], k: int = 10
    ) -> list[tuple[str, float]]:
        # Fallback fuzzy
        scored = [(cid, jaccard(query_text, text)) for cid, text in corpus]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
