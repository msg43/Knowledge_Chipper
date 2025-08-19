import json
from pathlib import Path

from claim_extractor.concepts import ConceptExtractor
from claim_extractor.config_flex import PipelineConfigFlex
from claim_extractor.dedupe import Deduper
from claim_extractor.evidence import EvidenceLinker
from claim_extractor.export import export_all
from claim_extractor.glossary import GlossaryExtractor
from claim_extractor.judge import Judge
from claim_extractor.miner import Miner
from claim_extractor.models.cross_encoder import CrossEncoder
from claim_extractor.models.embedder import Embedder
from claim_extractor.models.llm_any import AnyLLM
from claim_extractor.people import PeopleExtractor
from claim_extractor.relations import RelationMiner
from claim_extractor.rerank import Reranker
from claim_extractor.rerank_policy import adaptive_keep
from claim_extractor.router import Router
from claim_extractor.skim import Skimmer
from claim_extractor.types import EpisodeBundle, PipelineOutputs

DEF = Path(__file__).parents[1] / "claim_extractor"


def estimate_duration_minutes(segments):
    if not segments:
        return 0.0
    return max(5.0, len(segments) * 0.5)  # placeholder


def main(episode_path: str, outdir: str):
    cfg = PipelineConfigFlex()
    bundle = EpisodeBundle.model_validate_json(Path(episode_path).read_text())
    episode_text = "\n".join(s.text for s in bundle.segments)

    miner_llm = AnyLLM(cfg.models.miner)
    heavy_miner_llm = AnyLLM(cfg.models.heavy_miner) if cfg.models.heavy_miner else None
    judge_llm = AnyLLM(cfg.models.judge)
    embedder = Embedder(cfg.models.embedder)
    cross = CrossEncoder(cfg.models.reranker)

    milestones = []
    if cfg.use_skim:
        skimmer = Skimmer(miner_llm, DEF / "prompts/skim.txt")
        milestones = skimmer.skim(bundle.episode_id, bundle.segments)
        bundle.milestones = milestones

    ppl = PeopleExtractor(
        miner_llm,
        DEF / "prompts/people_detect.txt",
        DEF / "prompts/people_disambiguate.txt",
        judge_llm,
    )
    concepts = ConceptExtractor(miner_llm, DEF / "prompts/concepts_detect.txt")
    glossary = GlossaryExtractor(miner_llm, DEF / "prompts/glossary_detect.txt")

    people_mentions = ppl.disambiguate(ppl.detect(bundle.episode_id, bundle.segments))
    mental_models = concepts.detect(bundle.episode_id, bundle.segments)
    jargon_terms = glossary.detect(bundle.episode_id, bundle.segments)

    miner = Miner(miner_llm, DEF / "prompts/miner.txt")
    cands = []
    for seg in bundle.segments:
        cands.extend(miner.mine_segment(seg))
        if heavy_miner_llm:
            cands.extend(
                Miner(heavy_miner_llm, DEF / "prompts/miner.txt").mine_segment(seg)
            )

    linker = EvidenceLinker(embedder)
    cands = linker.link(bundle.segments, cands)
    deduper = Deduper(embedder)
    consolidated = deduper.cluster(cands)
    reranker = Reranker(cross)
    scored = reranker.score(episode_text, consolidated)

    minutes = estimate_duration_minutes(bundle.segments)
    kept = adaptive_keep(scored, minutes)

    router = Router(uncertainty_threshold=0.35)
    to_flagship, keep_local = router.split(kept)
    judge = Judge(judge_llm, DEF / "prompts/judge.txt")
    judged = judge.judge(episode_text, to_flagship) + keep_local

    relminer = RelationMiner(judge_llm, DEF / "prompts/contradiction.txt")
    relations = relminer.relate(judged)

    out = PipelineOutputs(
        episode_id=bundle.episode_id,
        claims=judged,
        relations=relations,
        milestones=milestones,
        people=people_mentions,
        concepts=mental_models,
        jargon=jargon_terms,
    )

    # Export to files (existing functionality)
    export_all(Path(outdir), out)

    # Persist to SQLite (new functionality)
    from claim_extractor.storage_sqlite import (
        ensure_schema,
        open_db,
        store_segments,
        upsert_pipeline_outputs,
    )

    db_path = Path(outdir) / "hce.db"
    conn = open_db(db_path)
    ensure_schema(conn)

    # Store segments for reference
    store_segments(conn, bundle.episode_id, bundle.segments)

    # Store pipeline outputs
    upsert_pipeline_outputs(
        conn,
        out,
        episode_title=bundle.segments[0].text[:50]
        if bundle.segments
        else None,  # Use first segment as title placeholder
        recorded_at=None,  # Could be extracted from metadata
        video_id=None,  # Could map to existing video_id if available
    )

    conn.close()
    print(f"Results persisted to {db_path}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("episode", help="Path to EpisodeBundle JSON")
    ap.add_argument("--outdir", default="./out")
    a = ap.parse_args()
    main(a.episode, a.outdir)
