from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Tuple


def _tokenize(text: str) -> set[str]:
    return set(t.strip('.,;:!?""""'"""()).lower() for t in text.split() if t.strip())


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta and not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


@dataclass
class Retrieval:
    def top_k(self, query_text: str, corpus: Iterable[tuple[str, str]], k: int = 10) -> List[Tuple[str, float]]:
        # corpus: iterable of (id, text)
        scored = [(cid, jaccard(query_text, text)) for cid, text in corpus]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
