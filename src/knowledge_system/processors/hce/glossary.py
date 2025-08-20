from pathlib import Path

from .models.llm_any import AnyLLM
from .types import EvidenceSpan, JargonTerm, Segment


class GlossaryExtractor:
    def __init__(self, llm: AnyLLM, prompt: Path):
        self.llm = llm
        self.template = prompt.read_text()

    def detect(self, episode_id: str, segments: list[Segment]) -> list[JargonTerm]:
        out: list[JargonTerm] = []
        for seg in segments:
            js = self.llm.generate_json(
                self.template
                + f"\n[segment_id={seg.segment_id} t0={seg.t0} t1={seg.t1}]\n"
                + seg.text
            )
            for i, r in enumerate(js):
                out.append(
                    JargonTerm(
                        episode_id=episode_id,
                        term_id=f"jt_{seg.segment_id}_{i}",
                        term=r["term"],
                        category=r.get("category"),
                        definition=r.get("definition"),
                        evidence_spans=[
                            EvidenceSpan(**e) for e in r.get("evidence", [])
                        ],
                    )
                )
        return out
