from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .validators import Landmarks


@dataclass
class LandmarksDetector:
    def detect(self, chunk_text: str) -> Landmarks:
        lines = [ln.strip() for ln in chunk_text.splitlines() if ln.strip()]
        section_title = lines[0] if lines else None
        key_facts: list[str] = []
        numbered_claims: list[str] = []
        anchors: list[list[int]] = []

        # Simple heuristics: bullets and numbered lines
        offset = 0
        for ln in chunk_text.splitlines(True):  # keep line breaks for span accounting
            stripped = ln.strip()
            start = offset
            end = start + len(ln)
            if stripped.startswith(('-', '*')):
                key_facts.append(stripped.lstrip('-* ').strip())
                anchors.append([start, end])
            elif stripped[:2].isdigit() and stripped[1:2] == '.':
                numbered_claims.append(stripped)
                anchors.append([start, end])
            offset = end

        return Landmarks(
            section_title=section_title,
            key_facts=key_facts,
            numbered_claims=numbered_claims,
            anchors=anchors,
        )
