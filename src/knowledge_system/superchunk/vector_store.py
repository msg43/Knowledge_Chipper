from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class VectorStore:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            c = conn.cursor()
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                  id TEXT PRIMARY KEY,
                  text TEXT NOT NULL,
                  embedding BLOB NOT NULL
                );
                """
            )
            conn.commit()

    def index(self, ids: Iterable[str], texts: Iterable[str], embeddings: Iterable[list[float]]) -> None:
        with sqlite3.connect(self.path) as conn:
            rows = []
            for vid, txt, vec in zip(ids, texts, embeddings):
                rows.append((vid, txt, sqlite3.Binary(memoryview(bytearray(float(x).hex().encode() for x in vec)))))
            # Simpler: store as JSON string for portability
            rows = []
            import json

            for vid, txt, vec in zip(ids, texts, embeddings):
                rows.append((vid, txt, json.dumps(vec)))
            conn.executemany("INSERT OR REPLACE INTO vectors (id, text, embedding) VALUES (?, ?, ?)", rows)
            conn.commit()

    def top_k(self, query_vec: list[float], k: int = 10) -> List[Tuple[str, float, str]]:
        import json
        with sqlite3.connect(self.path) as conn:
            c = conn.cursor()
            c.execute("SELECT id, text, embedding FROM vectors")
            rows = c.fetchall()
            scored: list[tuple[str, float, str]] = []
            for vid, txt, emb_json in rows:
                vec = json.loads(emb_json)
                score = cosine(query_vec, vec)
                scored.append((vid, score, txt))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:k]
