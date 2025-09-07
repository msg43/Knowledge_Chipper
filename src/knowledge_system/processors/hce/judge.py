from pathlib import Path

from ...config import get_settings
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


def judge_claims(
    claims: list[ScoredClaim],
    judge_model_uri: str,
    flagship_claims: list[ScoredClaim] | None = None,
    flagship_model_uri: str | None = None,
) -> list[ScoredClaim]:
    """Compatibility wrapper used by HCEPipeline.

    If flagship_claims and flagship_model_uri are provided, runs a dual pass:
    - claims (minus flagship_claims) judged by judge_model_uri
    - flagship_claims judged by flagship_model_uri
    Returns combined judged list.
    """
    prompt_path = Path(__file__).parent / "prompts" / "judge.txt"

    # Partition claims if flagship set provided
    flagship_set = set(flagship_claims or [])
    local_bucket = [c for c in claims if c not in flagship_set]
    judged: list[ScoredClaim] = []

    if local_bucket:
        j_local = Judge(AnyLLM(judge_model_uri), prompt_path)
        judged.extend(j_local.judge("", local_bucket))

    if flagship_claims and flagship_model_uri:
        j_flag = Judge(AnyLLM(flagship_model_uri), prompt_path)
        judged.extend(j_flag.judge("", flagship_claims))

    return judged
