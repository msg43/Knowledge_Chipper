from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .config import SuperChunkConfig, WindowPreset
from .signals import compute_signals
from .validators import Chunk


@dataclass
class Paragraph:
    text: str
    span_start: int
    span_end: int


def _sentence_end_positions(text: str, offset: int) -> list[int]:
    ends: list[int] = []
    for idx, ch in enumerate(text):
        if ch in ".!?":
            ends.append(offset + idx + 1)
    return ends


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

    def segment(
        self,
        paragraphs: Sequence[Paragraph],
        hotspots: list[list[int]] | None = None,
    ) -> list[Chunk]:
        text = "\n".join(p.text for p in paragraphs)
        episode_preset = (
            self._decide_episode_preset(text)
            if self.config.adaptive_switching
            else self.config.preset
        )
        region_scores = compute_signals(text)

        # Build a mapping from span index to region preset
        region_map: list[tuple[int, WindowPreset]] = []
        for start_idx, sig in region_scores:
            ps = sig.precision_score()
            region_preset = self._decide_region_preset(ps)
            region_map.append((start_idx * 4, region_preset))  # rough char proxy

        # Precompute sentence ends per paragraph for snapping
        para_sentence_ends: list[list[int]] = []
        for p in paragraphs:
            para_sentence_ends.append(_sentence_end_positions(p.text, p.span_start))

        # Helper: snap a desired end char position to nearest sentence end within tolerance
        def snap_to_sentence_end(
            desired_end_char: int, para_idx: int, tolerance: int = 200
        ) -> tuple[int, str]:
            ends = para_sentence_ends[para_idx]
            if not ends:
                return desired_end_char, "no_sentence_end"
            # choose sentence end <= desired_end_char within tolerance; else nearest above within tolerance
            candidates = [
                e
                for e in ends
                if e <= desired_end_char and desired_end_char - e <= tolerance
            ]
            if candidates:
                return max(candidates), "snapped_to_sentence_end"
            candidates_above = [
                e
                for e in ends
                if e >= desired_end_char and e - desired_end_char <= tolerance
            ]
            if candidates_above:
                return min(candidates_above), "snapped_to_sentence_end"
            return desired_end_char, "no_sentence_end_within_tolerance"

        # Helper: adjust para_end to respect hotspots ranges
        def respect_hotspots(
            current_para_start: int, candidate_para_end: int
        ) -> tuple[int, str]:
            if not hotspots:
                return candidate_para_end, "no_hotspots"
            reason = "no_hotspot_overlap"
            start = current_para_start
            end = candidate_para_end
            for hs_start, hs_end in hotspots:
                # if boundary would cut inside a hotspot, extend to hotspot end
                if hs_start <= end <= hs_end and end != hs_end:
                    end = hs_end
                    reason = "extended_for_hotspot"
            return end, reason

        chunks: list[Chunk] = []
        current_text: list[str] = []
        current_start = paragraphs[0].span_start if paragraphs else 0
        current_para_start = 0
        acc_len = 0

        def current_preset_for_position(char_pos: int) -> WindowPreset:
            if not region_map:
                return episode_preset
            prior = [p for p in region_map if p[0] <= char_pos]
            if len(prior) < 2:
                return prior[-1][1] if prior else episode_preset
            last_two = prior[-2:]
            return last_two[-1][1]

        def emit_chunk(para_end_idx: int, preset_used: WindowPreset):
            nonlocal current_text, acc_len
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

        for idx, para in enumerate(paragraphs):
            if not current_text:
                current_start = para.span_start
                current_para_start = idx

            preset_now = current_preset_for_position(para.span_start)
            min_tokens, max_tokens, overlap = self._window_limits(preset_now)
            max_chars = max_tokens * 4
            overlap_chars = overlap * 4

            para_len = para.span_end - para.span_start

            # If a single paragraph is too large, we need to split it
            if para_len > max_chars:
                print(
                    f"🚨 Large paragraph detected: {para_len} chars > {max_chars} max_chars"
                )
                # Split the large paragraph into sentence-based chunks
                sentences = []
                current_sentence = []

                # Simple sentence splitting (can be improved)
                for word in para.text.split():
                    current_sentence.append(word)
                    if word.endswith((".", "!", "?")):
                        sentences.append(" ".join(current_sentence))
                        current_sentence = []

                # Add any remaining words as a sentence
                if current_sentence:
                    sentences.append(" ".join(current_sentence))

                # Group sentences into chunks that fit within max_chars
                temp_chunk = []
                temp_len = 0

                for sentence in sentences:
                    sentence_len = len(sentence)

                    # If adding this sentence would exceed limit, emit current chunk
                    if temp_len > 0 and temp_len + sentence_len + 1 > max_chars:
                        # Emit the accumulated sentences as a chunk
                        chunk_text = " ".join(temp_chunk)
                        if current_text:
                            current_text.append(chunk_text)
                        else:
                            current_text = [chunk_text]
                            current_start = para.span_start
                            current_para_start = idx

                        acc_len += len(chunk_text)

                        # Check if we need to emit this chunk
                        if acc_len > max_chars:
                            emit_chunk(idx, preset_now)
                            current_start = para.span_start + len(chunk_text)
                            current_para_start = idx

                        # Start new temp chunk
                        temp_chunk = [sentence]
                        temp_len = sentence_len
                    else:
                        # Add sentence to current chunk
                        temp_chunk.append(sentence)
                        temp_len += sentence_len + 1

                # Add any remaining sentences
                if temp_chunk:
                    chunk_text = " ".join(temp_chunk)
                    current_text.append(chunk_text)
                    acc_len += len(chunk_text)

                # Continue to next paragraph
                continue

            # Normal processing for reasonably-sized paragraphs
            if acc_len and acc_len + para_len > max_chars:
                # propose boundary at previous paragraph
                candidate_para_end = idx - 1
                # respect hotspots
                candidate_para_end, hotspot_reason = respect_hotspots(
                    current_para_start, candidate_para_end
                )
                # snap to sentence end within candidate para
                desired_end_char = paragraphs[candidate_para_end].span_end
                snapped_char, snap_reason = snap_to_sentence_end(
                    desired_end_char, candidate_para_end
                )
                # adjust text by chopping to snapped_char if necessary
                # rebuild current_text up to snapped_char
                full_text = "\n\n".join(current_text)
                keep_len = snapped_char - current_start
                if 0 < keep_len < len(full_text):
                    full_text = full_text[:keep_len]
                # emit chunk with rebuilt text
                chunks.append(
                    Chunk(
                        id=f"chunk_{len(chunks)+1}",
                        span_start=current_start,
                        span_end=current_start + len(full_text),
                        para_start=current_para_start,
                        para_end=candidate_para_end,
                        text=full_text,
                        preset_used=preset_now.value,
                    )
                )
                # Start new window with overlap
                if overlap_chars > 0 and full_text:
                    tail = full_text[-overlap_chars:]
                    current_text = [tail]
                    acc_len = len(tail)
                    current_start = current_start + len(full_text) - len(tail)
                    current_para_start = candidate_para_end + 1
                else:
                    current_text = []
                    acc_len = 0
                    current_start = para.span_start
                    current_para_start = idx

            current_text.append(para.text)
            acc_len += para_len

        if current_text:
            preset_now = current_preset_for_position(
                paragraphs[-1].span_end if paragraphs else 0
            )
            emit_chunk(len(paragraphs) - 1 if paragraphs else 0, preset_now)

        return chunks
