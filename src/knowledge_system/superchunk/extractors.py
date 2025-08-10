from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .llm_adapter import SuperChunkLLMAdapter
from .validators import ClaimItem, LocalContradictionItem, JargonItem
from .config import SuperChunkConfig


@dataclass
class Extractors:
    adapter: SuperChunkLLMAdapter
    config: SuperChunkConfig

    @staticmethod
    def create_default() -> "Extractors":
        adapter = SuperChunkLLMAdapter.create_default()
        return Extractors(adapter=adapter, config=adapter.config)

    def _bounds_check(self, items: List[ClaimItem] | List[JargonItem], source: str) -> None:
        n = len(source)
        for it in items:
            if it.span_start < 0 or it.span_end > n or it.span_start >= it.span_end:
                raise ValueError("Invalid span bounds in extractor output")

    def extract_claims(self, chunk_text: str) -> List[ClaimItem]:
        c = self.config.non_obvious_claims_count
        prompt = (
            "You are extracting non-obvious claims from a chunk. "
            f"Return exactly {c} items as JSON array of objects with keys: "
            "text, why_nonobvious, rarity (0..1), confidence (0..1), quote (<= max_quote_words), "
            "span_start, span_end, para_idx, hedges (array). "
            f"max_quote_words={self.config.max_quote_words}.\n\n"
            f"Chunk:\n{chunk_text}"
        )
        items = self.adapter.extract_claims(prompt, count=c)
        self._bounds_check(items, chunk_text)
        return items

    def extract_local_contradictions(self, chunk_text: str) -> List[LocalContradictionItem]:
        c = self.config.max_local_contradictions
        prompt = (
            "Identify up to N local contradictions within this chunk. "
            f"Return exactly {c} items (fill with empty objects if fewer exist) with keys: a_claim, b_claim, rationale.\n\n"
            f"Chunk:\n{chunk_text}"
        )
        return self.adapter.extract_contradictions(prompt, max_count=c)

    def extract_jargon(self, chunk_text: str) -> List[JargonItem]:
        c = self.config.jargon_terms_count
        prompt = (
            "Extract domain-specific jargon. Return exactly N items with keys: term, definition, usage_quote (<= max_quote_words), "
            "span_start, span_end, para_idx.\n\n"
            f"max_quote_words={self.config.max_quote_words}.\n\n"
            f"Chunk:\n{chunk_text}"
        )
        items = self.adapter.extract_jargon(prompt, count=c)
        self._bounds_check(items, chunk_text)
        return items
