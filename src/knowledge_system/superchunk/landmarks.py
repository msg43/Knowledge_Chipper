from __future__ import annotations

from dataclasses import dataclass

from .llm_adapter import SuperChunkLLMAdapter
from .validators import Landmarks


@dataclass
class LandmarksDetector:
    adapter: SuperChunkLLMAdapter

    @staticmethod
    def create_default() -> LandmarksDetector:
        return LandmarksDetector(adapter=SuperChunkLLMAdapter.create_default())

    def detect(self, chunk_text: str) -> Landmarks:
        prompt = (
            "Extract landmarks from the chunk. Return JSON with keys: "
            "section_title (string or null), key_facts (array of strings), numbered_claims (array of strings), "
            "anchors (array of [span_start, span_end] for each bullet/numbered line). Ensure spans are within text bounds.\n\n"
            f"Chunk:\n{chunk_text}"
        )
        return self.adapter.generate_json(
            prompt, Landmarks, estimated_output_tokens=400
        )
