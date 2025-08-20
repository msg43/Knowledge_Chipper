from __future__ import annotations

from dataclasses import dataclass

from ..logger import get_logger
from .config import SuperChunkConfig
from .llm_adapter import SuperChunkLLMAdapter
from .validators import ClaimItem, JargonItem, LocalContradictionItem


@dataclass
class Extractors:
    adapter: SuperChunkLLMAdapter
    config: SuperChunkConfig

    logger = get_logger(__name__)

    @staticmethod
    def create_default(
        provider: str | None = None, model: str | None = None
    ) -> Extractors:
        adapter = SuperChunkLLMAdapter.create_default(provider=provider, model=model)
        return Extractors(adapter=adapter, config=adapter.config)

    def _bounds_check(
        self, items: list[ClaimItem] | list[JargonItem], source: str
    ) -> None:
        """Validate and repair span bounds where possible.

        Root cause: LLMs sometimes emit out-of-range or inverted spans. Prefer
        repair over hard failure when we can reliably fix using the provided
        quote. As a last resort, clamp indices to be valid and ensure non-empty
        spans.
        """
        n = len(source)
        if n <= 0:
            # Nothing to align against; drop all spans silently
            items[:] = []
            return

        valid_items: list[ClaimItem | JargonItem] = []
        for it in items:
            # Normalize to ints
            try:
                start = int(it.span_start)
                end = int(it.span_end)
            except Exception:
                start, end = 0, 0

            # First, try direct clamp
            if start < 0:
                start = 0
            if end > n:
                end = n

            # If we have a quote, prefer aligning spans to the quote location
            quote = getattr(it, "quote", None) or getattr(it, "usage_quote", None)
            if isinstance(quote, str) and quote.strip():
                q = quote.strip()
                idx = source.find(q)
                if idx != -1:
                    start = idx
                    end = idx + len(q)
                # If not found, keep clamped indices but ensure non-empty below

            # Ensure non-empty and ordered span
            if start >= end:
                # Make minimal non-empty span. Handle start clamped to n.
                if start >= n:
                    start = max(0, n - 1)
                    end = n
                else:
                    end = min(n, max(start + 1, 1))

            # Final guard: indices must be within [0, n]
            start = max(0, min(start, n))
            end = max(0, min(end, n))

            # Assign back to item
            it.span_start = start
            it.span_end = end

            # If still invalid, drop this item rather than failing the run
            if it.span_start < 0 or it.span_end > n or it.span_start >= it.span_end:
                try:
                    self.logger.warning(
                        "Dropping item due to unrecoverable span bounds: start=%s end=%s n=%s",
                        start,
                        end,
                        n,
                    )
                except Exception:
                    pass
                continue

            valid_items.append(it)

        # Replace contents in-place so callers see only valid items
        if len(valid_items) != len(items):
            items[:] = valid_items

    def extract_claims(self, chunk_text: str) -> list[ClaimItem]:
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

    def extract_local_contradictions(
        self, chunk_text: str
    ) -> list[LocalContradictionItem]:
        c = self.config.max_local_contradictions
        prompt = (
            "Identify up to N local contradictions within this chunk. "
            f"Return exactly {c} items (fill with empty objects if fewer exist) with keys: a_claim, b_claim, rationale.\n\n"
            f"Chunk:\n{chunk_text}"
        )
        return self.adapter.extract_contradictions(prompt, max_count=c)

    def extract_jargon(self, chunk_text: str) -> list[JargonItem]:
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
