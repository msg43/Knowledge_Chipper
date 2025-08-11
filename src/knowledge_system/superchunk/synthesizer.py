from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .config import SuperChunkConfig


@dataclass
class Synthesizer:
    config: SuperChunkConfig

    def synthesize_section(
        self, title: str, retrieved_slices: Iterable[tuple[str, str, int, int, int]]
    ) -> str:
        # retrieved_slices: iterable of (id, text, span_start, span_end, para_idx)
        cap = self.config.max_quote_words
        lines = [f"## {title}"]
        for cid, text, span_start, span_end, para_idx in retrieved_slices:
            words = text.split()
            quote = " ".join(words[:cap])
            lines.append(f"> {quote}")
            lines.append(
                f"[source: {cid} span=({span_start},{span_end}) para={para_idx}]"
            )
            lines.append("")
        return "\n".join(lines)
