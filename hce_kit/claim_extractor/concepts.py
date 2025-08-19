from pathlib import Path
from typing import List

from .models.llm_any import AnyLLM
from .types import EvidenceSpan, MentalModel, Segment


class ConceptExtractor:
    def __init__(self, llm: AnyLLM, prompt: Path):
        self.llm = llm
        self.template = prompt.read_text()

    def detect(self, episode_id: str, segments: list[Segment]) -> list[MentalModel]:
        out: list[MentalModel] = []
        for seg in segments:
            js = self.llm.generate_json(
                self.template
                + f"\n[segment_id={seg.segment_id} t0={seg.t0} t1={seg.t1}]\n"
                + seg.text
            )
            for i, r in enumerate(js):
                out.append(
                    MentalModel(
                        episode_id=episode_id,
                        model_id=f"mm_{seg.segment_id}_{i}",
                        name=r["name"],
                        definition=r.get("definition"),
                        first_mention_ts=r.get("t0", seg.t0),
                        evidence_spans=[
                            EvidenceSpan(**e) for e in r.get("evidence", [])
                        ],
                        aliases=r.get("aliases", []),
                    )
                )
        return out
