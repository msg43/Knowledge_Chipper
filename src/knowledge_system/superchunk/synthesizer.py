from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from .config import SuperChunkConfig


@dataclass
class Synthesizer:
    config: SuperChunkConfig

    def synthesize_section(self, title: str, retrieved_slices: Iterable[tuple[str, str]]) -> str:
        # retrieved_slices: iterable of (id, text)
        cap = self.config.max_quote_words
        lines = [f"## {title}"]
        for cid, text in retrieved_slices:
            words = text.split()
            quote = " ".join(words[:cap])
            lines.append(f"> {quote}")
            lines.append("")
        return "\n".join(lines)
