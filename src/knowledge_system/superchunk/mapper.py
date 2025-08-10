from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .validators import GuideMap


@dataclass
class Mapper:
    """Lightweight skim pass to produce a guide map for segmenter cues.

    This stub uses simple heuristics as placeholders for future signals
    (cohesion breaks, discourse markers, new terms, numbers, questions, etc.).
    """

    def map(self, paragraphs: Iterable[str]) -> GuideMap:
        paragraphs = list(paragraphs)
        # Naive heuristics: extract capitalized words as entities; detect tensions by keywords
        entities: set[str] = set()
        tensions: set[str] = set()
        themes: set[str] = set()
        hotspots: list[list[int]] = []

        keywords_tension = {"however", "but", "contradict", "disagree", "vs"}
        keywords_themes = {"economy", "technology", "policy", "science", "market"}

        for idx, p in enumerate(paragraphs):
            tokens = p.split()
            for tok in tokens:
                if tok[:1].isupper() and tok[1:].islower():
                    entities.add(tok.strip(",.?!:;"))
            lower = p.lower()
            if any(k in lower for k in keywords_tension):
                tensions.add("possible_tension")
                # crude hotspot around this paragraph
                hotspots.append([idx, idx])
            for th in keywords_themes:
                if th in lower:
                    themes.add(th)

        return GuideMap(
            themes=sorted(themes)[:10],
            entities=sorted(entities)[:25],
            tensions=sorted(tensions)[:5],
            hotspots=hotspots[:10],
            notes="heuristic skim (stub)",
        )
