from pathlib import Path
from typing import List

from .models.llm_any import AnyLLM
from .types import PersonMention, Segment


class PeopleExtractor:
    def __init__(
        self,
        llm_local: AnyLLM,
        detect_prompt: Path,
        disambig_prompt: Path,
        flagship: AnyLLM | None = None,
    ):
        self.local = llm_local
        self.detect_t = detect_prompt.read_text()
        self.disambig_t = disambig_prompt.read_text()
        self.flagship = flagship

    def detect(self, episode_id: str, segments: list[Segment]) -> list[PersonMention]:
        out: list[PersonMention] = []
        for seg in segments:
            js = self.local.generate_json(
                self.detect_t
                + f"\n[segment_id={seg.segment_id} t0={seg.t0} t1={seg.t1}]\n"
                + seg.text
            )
            for i, r in enumerate(js):
                out.append(
                    PersonMention(
                        episode_id=episode_id,
                        mention_id=f"pm_{seg.segment_id}_{i}",
                        span_segment_id=seg.segment_id,
                        t0=r.get("t0", seg.t0),
                        t1=r.get("t1", seg.t1),
                        surface=r["surface"],
                        normalized=r.get("normalized"),
                        entity_type=r.get("entity_type", "person"),
                        confidence=r.get("confidence", 0.5),
                    )
                )
        return out

    def disambiguate(self, mentions: list[PersonMention]) -> list[PersonMention]:
        if not self.flagship:
            return mentions
        out = []
        for m in mentions:
            if m.normalized:
                out.append(m)
                continue
            js = self.flagship.judge_json(self.disambig_t + "\n" + m.surface)
            m.normalized = js.get("normalized")
            m.external_ids = js.get("external_ids", {})
            out.append(m)
        return out
