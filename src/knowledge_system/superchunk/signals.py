from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _sliding_windows(tokens: list[str], window_size: int, stride: int):
    for start in range(0, max(1, len(tokens) - window_size + 1), stride):
        yield start, tokens[start : start + window_size]


@dataclass
class Signals:
    cohesion: float
    markers: float
    new_terms: float
    numbers: float
    hedges: float
    story: float
    sent_var: float

    def precision_score(self) -> float:
        # 0.25·cohesion + 0.20·markers + 0.20·new_terms + 0.15·numbers + 0.10·hedges − 0.10·story − 0.10·sent_var
        return (
            0.25 * self.cohesion
            + 0.20 * self.markers
            + 0.20 * self.new_terms
            + 0.15 * self.numbers
            + 0.10 * self.hedges
            - 0.10 * self.story
            - 0.10 * self.sent_var
        )


MARKERS = {"however", "therefore", "thus", "hence", "but", "although", "moreover"}
HEDGES = {"perhaps", "maybe", "seems", "appears", "likely", "unlikely", "approximately"}
STORY = {"once", "then", "suddenly", "after", "before", "story", "narrative"}


def _sentence_lengths(text: str) -> list[int]:
    # crude sentence segmentation
    sentences = [
        s.strip()
        for s in text.replace("?", ".").replace("!", ".").split(".")
        if s.strip()
    ]
    return [max(1, len(s.split())) for s in sentences] or [1]


def compute_signals(text: str) -> list[tuple[int, Signals]]:
    # Tokenize naively by words for windows
    words = text.split()
    # 500-token regions, 100-token stride
    window_size = 500
    stride = 100
    results: list[tuple[int, Signals]] = []

    seen_terms: set[str] = set()

    for start, window_tokens in _sliding_windows(words, window_size, stride):
        window_text = " ".join(window_tokens)
        lower_tokens = [t.strip(".,;:!?").lower() for t in window_tokens]
        token_set = set(lower_tokens)
        # cohesion proxy: inverse of unique ratio
        unique_ratio = len(token_set) / max(1, len(lower_tokens))
        cohesion = max(0.0, min(1.0, 1.0 - unique_ratio))
        # discourse markers
        markers = sum(1 for t in lower_tokens if t in MARKERS) / max(
            1, len(lower_tokens)
        )
        markers = min(1.0, markers * 10)
        # new terms rate
        new_count = sum(1 for t in token_set if t not in seen_terms)
        new_terms = new_count / max(1, len(token_set))
        seen_terms.update(token_set)
        # numbers/symbols
        numbers = sum(1 for t in lower_tokens if any(ch.isdigit() for ch in t)) / max(
            1, len(lower_tokens)
        )
        numbers = min(1.0, numbers * 10)
        # hedges
        hedges = sum(1 for t in lower_tokens if t in HEDGES) / max(1, len(lower_tokens))
        hedges = min(1.0, hedges * 10)
        # story cues
        story = sum(1 for t in lower_tokens if t in STORY) / max(1, len(lower_tokens))
        story = min(1.0, story * 10)
        # sentence-length variance (normalized)
        lens = _sentence_lengths(window_text)
        mean_len = sum(lens) / len(lens)
        var = sum((l - mean_len) ** 2 for l in lens) / len(lens)
        sent_var = max(0.0, min(1.0, var / (mean_len**2 + 1e-6)))

        results.append(
            (
                start,
                Signals(cohesion, markers, new_terms, numbers, hedges, story, sent_var),
            )
        )

    return results
