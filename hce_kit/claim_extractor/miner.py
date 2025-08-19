from pathlib import Path

from .models.llm_any import AnyLLM
from .types import CandidateClaim, EvidenceSpan, Segment


class Miner:
    def __init__(self, llm: AnyLLM, prompt_path: Path):
        self.llm = llm
        self.template = prompt_path.read_text()

    def mine_segment(self, seg: Segment) -> list[CandidateClaim]:
        header = f"[speaker={seg.speaker} t0={seg.t0} t1={seg.t1} segment_id={seg.segment_id}]\n"
        prompt = self.template + "\n" + header + seg.text
        raw = self.llm.generate_json(prompt)
        out = []
        for i, r in enumerate(raw):
            out.append(
                CandidateClaim(
                    episode_id=seg.episode_id,
                    segment_id=seg.segment_id,
                    candidate_id=f"{seg.segment_id}#c{i}",
                    speaker=seg.speaker,
                    claim_text=r["claim_text"],
                    claim_type=r["claim_type"],
                    stance=r.get("stance", "asserts"),
                    evidence_spans=[
                        EvidenceSpan(**e) for e in r.get("evidence_spans", [])
                    ],
                    confidence_local=r.get("confidence", 0.5),
                )
            )
        return out
