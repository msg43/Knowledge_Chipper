# SuperChunk Smart Chunking Summarization — Remaining Scope (v3)

- [ ] Embeddings Retrieval + Top‑K + Provider Alignment
  - Auto-select embedding endpoint aligned with chosen provider/model; fallback to baseline when unavailable
  - Implement vector store (SQLite-backed now), cosine similarity; batch index/update
  - Provide `topK_linking` and `topK_section` with thresholds; benchmarks on fixtures
  - Acceptance: measurable P/R > baseline on fixtures; deterministic top‑K selection

- [ ] Linking Rationale (Cross‑Chunk)
  - Use embeddings + lexical features to score support/contradict/refine/duplicate; rationale templates
  - Conservative “none” below neighbor threshold; persist links with similarity and rationale
  - Acceptance: link distribution stable; duplicates under dedupe threshold

- [ ] Canonicalization, Novelty, Evolution
  - Canonicalize claims/entities; novelty scoring; mark `included_in_final`
  - Track evolution trajectories across para ranges; persist and expose in artifacts
  - Acceptance: reproducible dedupe; evolution view produced for sample run

- [ ] Quality Gates + Targeted Refine Loop
  - Compute true coverage, rare‑retention, contradictions surfaced, retrieval P/R, verification pass
  - On gate fail: write `refine_plan.json`, re‑read only target chunks, re‑synthesize sections
  - Acceptance: refine loop isolates work to failing targets and improves metrics

- [ ] Full Debug Bundle + Artifacts DB
  - Write: `llm_calls.jsonl`, `decision_log.json`, `verification_log.json`, `evolution_timeline.json`, `link_graph.dot`, `token_trace.csv`
  - Add `artifacts.sqlite` for convenient inspection
  - Acceptance: bundle generated for each run; schema documented

- [ ] Robust Verification Prompts/Policy + Delta Reprompts
  - Design prompts for zero‑temp fact checking; adjust confidence; exclude with policy
  - Ensure delta‑reprompt is applied to all JSON passes consistently
  - Acceptance: verifications recorded; exclusions reflected in final output and scorecard

- [ ] Persistence of Provider/Model Selection (No Hard Defaults)
  - Persist last provider/model in state; load on launch; runtime override wins
  - Acceptance: prior selection pre-populates; no hard-coded fallback

- [ ] Artifacts Path + 90‑Day Retention
  - Output to `<output>/superchunk_runs/<timestamp>/`; scheduled cleanup for >90 days
  - Acceptance: cleanup removes expired runs; retention configurable

- [ ] Tests (Unit + Integration)
  - Fixtures: monologue‑heavy, contradiction‑rich, jargon‑dense; add segmentation/extractor/linker/verify tests
  - End-to-end runs produce artifacts; assert gates and refine loop behavior
  - Acceptance: green tests locally; CI wiring added

- [ ] Invisible UX + Expert Flags
  - Keep existing summarization UX; expose optional flags for window presets, verify percent, quote caps, token budgets
  - Acceptance: default UX unchanged; expert flags documented
