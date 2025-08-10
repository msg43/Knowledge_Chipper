from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from .config import SuperChunkConfig, WindowPreset
from .validators import Chunk


@dataclass
class Paragraph:
    text: str
    span_start: int
    span_end: int


@dataclass
class Segmenter:
    config: SuperChunkConfig

    def _choose_preset(self) -> WindowPreset:
        # Balanced by default; adaptive switching hooks to be implemented with mapper cues
        return self.config.preset

    def _window_limits(self):
        window = self.config.get_window()
        return window.min_tokens, window.max_tokens, window.overlap_tokens

    def segment(self, paragraphs: Sequence[Paragraph]) -> List[Chunk]:
        # Simple balanced windowing by character count proxy (~4 chars per token)
        min_tokens, max_tokens, overlap = self._window_limits()
        # min_chars not strictly used now; could gate small final chunk later if needed
        _min_chars = min_tokens * 4
        max_chars = max_tokens * 4
        overlap_chars = overlap * 4

        chunks: List[Chunk] = []
        current_text: list[str] = []
        current_start = paragraphs[0].span_start if paragraphs else 0
        current_para_start = 0

        acc_len = 0
        for idx, para in enumerate(paragraphs):
            if not current_text:
                current_start = para.span_start
                current_para_start = idx

            # If adding this paragraph would exceed max window, emit chunk
            if acc_len and acc_len + (para.span_end - para.span_start) > max_chars:
                text = "\n\n".join(current_text)
                chunks.append(
                    Chunk(
                        id=f"chunk_{len(chunks)+1}",
                        span_start=current_start,
                        span_end=current_start + len(text),
                        para_start=current_para_start,
                        para_end=idx - 1,
                        text=text,
                        preset_used=str(self._choose_preset().value),
                    )
                )
                # Start new window with overlap by trimming from end
                if overlap_chars > 0 and text:
                    keep_chars = min(overlap_chars, len(text))
                    # Reconstruct overlap tail as starting buffer (approximate)
                    current_text = [text[-keep_chars:]]
                    acc_len = keep_chars
                    current_start = current_start + len(text) - keep_chars
                    current_para_start = idx  # para index for new start
                else:
                    current_text = []
                    acc_len = 0
                    current_start = para.span_start
                    current_para_start = idx

            # Add paragraph
            current_text.append(para.text)
            acc_len += para.span_end - para.span_start

        # Emit final chunk
        if current_text:
            text = "\n\n".join(current_text)
            chunks.append(
                Chunk(
                    id=f"chunk_{len(chunks)+1}",
                    span_start=current_start,
                    span_end=current_start + len(text),
                    para_start=current_para_start,
                    para_end=len(paragraphs) - 1 if paragraphs else 0,
                    text=text,
                    preset_used=str(self._choose_preset().value),
                )
            )

        return chunks
