from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import SuperChunkConfig
from .extractors import Extractors
from .ledger import Ledger
from .mapper import Mapper
from .segmenter import Segmenter, Paragraph
from .synthesizer import Synthesizer
from .scorecard import Scorecard
from .gates import QualityGates
from .retrieval import Retrieval


@dataclass
class Runner:
    config: SuperChunkConfig
    artifacts_dir: Path

    def run(self, paragraphs: Iterable[str]) -> None:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        decision_log = []
        llm_calls_log = []

        # Phase 0: guide map
        mapper = Mapper()
        guide = mapper.map(paragraphs)
        (self.artifacts_dir / "global_context.json").write_text(
            json.dumps(guide.model_dump(), indent=2), encoding="utf-8"
        )

        # Phase 1: segment
        paras = list(paragraphs)
        cursor = 0
        para_objs: list[Paragraph] = []
        for p in paras:
            start = cursor
            end = start + len(p)
            para_objs.append(Paragraph(text=p, span_start=start, span_end=end))
            cursor = end + 1

        segmenter = Segmenter(config=self.config)
        chunks = segmenter.segment(para_objs, hotspots=guide.hotspots)
        (self.artifacts_dir / "chunking_decisions.json").write_text(
            json.dumps(
                [
                    {
                        "id": c.id,
                        "span": [c.span_start, c.span_end],
                        "para_range": [c.para_start, c.para_end],
                        "preset_used": c.preset_used,
                    }
                    for c in chunks
                ],
                indent=2,
            ),
            encoding="utf-8",
        )

        # Phase 2: extraction
        extractors = Extractors.create_default()
        ledger = Ledger(self.artifacts_dir / "ledger.sqlite")
        # Ensure we only store JSON-serializable config
        run_id = ledger.start_run(config=self.config.to_json_dict())

        for c in chunks:
            claims = extractors.extract_claims(c.text)
            ledger.insert_claims(run_id, c.id, claims)

        # Phase 3/4: retrieval (embeddings) + synth (retrieval-only)
        retrieval = Retrieval()
        retrieval.index_corpus([(c.id, c.text) for c in chunks])
        top_slices = []
        # Use first chunk as query for demo; in real flow, select by section/topic
        if chunks:
            results = retrieval.top_k_embeddings(chunks[0].text, k=min(10, len(chunks)))
            for cid, score, txt in results:
                ch = next(cc for cc in chunks if cc.id == cid)
                top_slices.append((cid, txt, ch.span_start, ch.span_end, ch.para_start))
        synth = Synthesizer(config=self.config)
        final_sections = [synth.synthesize_section("Summary", top_slices)]
        (self.artifacts_dir / "final.md").write_text("\n\n".join(final_sections), encoding="utf-8")

        # Phase 6: scorecard
        score = Scorecard().compute({})
        (self.artifacts_dir / "scorecard.json").write_text(
            json.dumps(score, indent=2), encoding="utf-8"
        )

        # Debug bundle placeholders
        (self.artifacts_dir / "llm_calls.jsonl").write_text("", encoding="utf-8")
        (self.artifacts_dir / "decision_log.json").write_text(
            json.dumps(decision_log, indent=2), encoding="utf-8"
        )
        (self.artifacts_dir / "verification_log.json").write_text("[]", encoding="utf-8")
        (self.artifacts_dir / "evolution_timeline.json").write_text("{}", encoding="utf-8")
        (self.artifacts_dir / "link_graph.dot").write_text("digraph G {}\n", encoding="utf-8")
        (self.artifacts_dir / "token_trace.csv").write_text("step,tokens\n", encoding="utf-8")

        # Quality gates
        gates = QualityGates()
        ok, _ = gates.evaluate(score)
        if not ok:
            refine = gates.refine_plan([chunks[0].id] if chunks else [])
            (self.artifacts_dir / "refine_plan.json").write_text(
                json.dumps(refine, indent=2), encoding="utf-8"
            )
