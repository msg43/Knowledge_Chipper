from pathlib import Path
from ...config import get_settings
from .types import EpisodeBundle, ConsolidatedClaim

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


def mine_claims(episode: EpisodeBundle, miner_model_uri: str) -> list[ConsolidatedClaim]:
    """Compatibility wrapper used by HCEPipeline to mine and dedupe claims."""
    from .dedupe import Deduper
    from .models.embedder import Embedder

    # Build LLM from provided miner model URI
    llm = AnyLLM(miner_model_uri)
    prompt_path = Path(__file__).parent / "prompts" / "miner.txt"
    m = Miner(llm, prompt_path)

    # Mine candidates per segment
    candidates = []
    for seg in episode.segments:
        candidates.extend(m.mine_segment(seg))

    # Deduplicate to consolidated claims
    settings = get_settings()
    embedder = Embedder(settings.hce.embedder_model)
    deduper = Deduper(embedder)
    consolidated = deduper.cluster(candidates)
    return consolidated
