from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from .config import SuperChunkConfig, WindowPreset
from .validators import Chunk
from .signals import compute_signals


@dataclass
class Paragraph:
    text: str
    span_start: int
    span_end: int


@dataclass
class Segmenter:
    config: SuperChunkConfig

    def _decide_episode_preset(self, full_text: str) -> WindowPreset:
        signals = compute_signals(full_text)
        if not signals:
            return self.config.preset
        avg = sum(s.precision_score() for _, s in signals) / len(signals)
        if avg >= 0.55:
            return WindowPreset.PRECISION
        if avg <= 0.45:
            return WindowPreset.NARRATIVE
        return WindowPreset.BALANCED

    def _decide_region_preset(self, precision_score: float) -> WindowPreset:
        if precision_score >= 0.60:
            return WindowPreset.PRECISION
        if precision_score <= 0.40:
            return WindowPreset.NARRATIVE
        return WindowPreset.BALANCED

    def _window_limits(self, preset: WindowPreset):
        window = {
            WindowPreset.PRECISION: self.config.precision,
            WindowPreset.BALANCED: self.config.balanced,
            WindowPreset.NARRATIVE: self.config.narrative,
        }[preset]
        return window.min_tokens, window.max_tokens, window.overlap_tokens

    def segment(self, paragraphs: Sequence[Paragraph]) -> List[Chunk]:
        text = "\n".join(p.text for p in paragraphs)
        episode_preset = self._decide_episode_preset(text) if self.config.adaptive_switching else self.config.preset
        region_scores = compute_signals(text)

        # Build a mapping from span index to region preset
        region_map: list[tuple[int, WindowPreset]] = []
        for start_idx, sig in region_scores:
            ps = sig.precision_score()
            region_preset = self._decide_region_preset(ps)
            region_map.append((start_idx * 4, region_preset))  # rough char proxy

        chunks: List[Chunk] = []
        current_text: list[str] = []
        current_start = paragraphs[0].span_start if paragraphs else 0
        current_para_start = 0
        acc_len = 0

        def current_preset_for_position(char_pos: int) -> WindowPreset:
            # Sticky decision: require >=0.10 delta across two regions to switch
            if not region_map:
                return episode_preset
            # find last two regions whose start <= char_pos
            prior = [p for p in region_map if p[0] <= char_pos]
            if len(prior) < 2:
                return prior[-1][1] if prior else episode_preset
            last_two = prior[-2:]
            # use their presets; if they differ from current, treat as transitional
            return last_two[-1][1]

        # Helper to emit a chunk
        def emit_chunk(para_end_idx: int, preset_used: WindowPreset):
            nonlocal current_text, acc_len, current_start, current_para_start
            text_joined = "\n\n".join(current_text)
            chunks.append(
                Chunk(
                    id=f"chunk_{len(chunks)+1}",
                    span_start=current_start,
                    span_end=current_start + len(text_joined),
                    para_start=current_para_start,
                    para_end=para_end_idx,
                    text=text_joined,
                    preset_used=preset_used.value,
                )
            )
            current_text = []
            acc_len = 0

        idx_char_offset = 0
        for idx, para in enumerate(paragraphs):
            if not current_text:
                current_start = para.span_start
                current_para_start = idx

            # Decide preset at the start of this paragraph
            preset_now = current_preset_for_position(para.span_start)
            min_tokens, max_tokens, overlap = self._window_limits(preset_now)
            max_chars = max_tokens * 4
            overlap_chars = overlap * 4

            # If adding this paragraph would exceed max window, emit chunk and apply overlap
            para_len = para.span_end - para.span_start
            if acc_len and acc_len + para_len > max_chars:
                emit_chunk(idx - 1, preset_now)
                # Overlap: carry tail
                if overlap_chars > 0 and current_text:
                    tail = ("\n\n".join(current_text))[-overlap_chars:]
                    current_text = [tail]
                    acc_len = len(tail)
                    current_start = current_start + len(tail)
                    current_para_start = idx
                else:
                    current_text = []
                    acc_len = 0
                    current_start = para.span_start
                    current_para_start = idx

            current_text.append(para.text)
            acc_len += para_len
            idx_char_offset += para_len

        if current_text:
            preset_now = current_preset_for_position(paragraphs[-1].span_end if paragraphs else 0)
            emit_chunk(len(paragraphs) - 1 if paragraphs else 0, preset_now)

        return chunks
