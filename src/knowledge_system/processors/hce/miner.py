from pathlib import Path

from ...config import get_settings
from .models.llm_any import AnyLLM
from .types import (
    CandidateClaim,
    ConsolidatedClaim,
    EpisodeBundle,
    EvidenceSpan,
    Segment,
)


class Miner:
    def __init__(self, llm: AnyLLM, prompt_path: Path):
        self.llm = llm
        self.template = prompt_path.read_text()

    def _normalize_stance(self, stance: str | None) -> str:
        """Normalize stance to valid values."""
        if not stance:
            return "asserts"
        stance_lower = str(stance).lower().strip()

        # Map common variations to valid values
        stance_mapping = {
            "affirmative": "asserts",
            "affirms": "asserts",
            "positive": "asserts",
            "agrees": "asserts",
            "negative": "disputes",
            "disagrees": "disputes",
            "opposes": "disputes",
            "support": "supports",
            "supports": "supports",
            "backing": "supports",
            "endorses": "supports",
            "neutral": "neutral",
            "asserts": "asserts",
            "disputes": "disputes",
        }

        return stance_mapping.get(stance_lower, "asserts")

    def _normalize_evidence_span(self, evidence_data: dict) -> "EvidenceSpan":
        """Normalize evidence span data to match expected schema."""
        from .types import EvidenceSpan

        # Handle different field name variations
        quote = (
            evidence_data.get("quote")
            or evidence_data.get("verbatim_quote")
            or evidence_data.get("text", "")
        )
        t0 = evidence_data.get("t0", "0:00")
        t1 = evidence_data.get("t1", "0:30")
        segment_id = evidence_data.get("segment_id")

        return EvidenceSpan(
            quote=quote,
            t0=str(t0),
            t1=str(t1),
            segment_id=segment_id,
        )

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
                    stance=self._normalize_stance(r.get("stance", "asserts")),
                    evidence_spans=[
                        self._normalize_evidence_span(e)
                        for e in r.get("evidence_spans", [])
                    ],
                    confidence_local=r.get("confidence", 0.5),
                )
            )
        return out


def mine_claims(
    episode: EpisodeBundle, miner_model_uri: str
) -> list[ConsolidatedClaim]:
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
