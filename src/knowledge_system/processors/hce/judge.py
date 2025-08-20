from pathlib import Path

from .models.llm_any import AnyLLM
from .types import ScoredClaim


class Judge:
    def __init__(self, llm: AnyLLM, prompt_path: Path):
        self.llm = llm
        self.template = prompt_path.read_text()

    def judge(
        self, episode_context: str, claims: list[ScoredClaim]
    ) -> list[ScoredClaim]:
        out: list[ScoredClaim] = []
        for c in claims:
            pack = {
                "claim": c.canonical,
                "evidence": [e.model_dump() for e in c.evidence],
                "context_excerpt": episode_context[:1200],
            }
            raw = self.llm.judge_json(self.template + "\n" + str(pack))
            s = c.scores.copy()
            for k in [
                "importance",
                "novelty",
                "controversy",
                "fragility",
                "confidence_final",
            ]:
                if k in raw:
                    s[k] = float(raw[k])
            if raw.get("decision", "accept") == "reject":
                continue
            c.scores = s
            out.append(c)
        return out
