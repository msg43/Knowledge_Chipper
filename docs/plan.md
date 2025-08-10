# SuperChunk_GPT 3 — Hierarchical RAG for Deep, Nuanced Podcast Analysis

## 0) What changed (summary)
- No timestamps/diarization → use **character spans** and **paragraph indices**.
- Model‑agnostic LLM adapter (GPT‑5 default).
- **Adaptive windows**: default 4–5k tokens with automatic Precision↔Narrative switch.
- **NEW:** Persistent, repo‑backed checklist at `docs/todo.md`. Cursor must read it, do the first unchecked item, check it off, commit, and repeat. This prevents context‑window issues and allows hands‑off runs across sessions.

## 1) Objectives (what “good” looks like)
- Hierarchical **map → weave → synthesize** pipeline.
- Treat system as **RAG** (retrieve slices; never full transcript prompts).
- Highlight **rare‑but‑important** details; track **claim evolution**.
- Auditable outputs: final.md + spans/para idx, ledger + verification logs.
- Reliability: structured outputs, deterministic IDs, caching, verification, **quality gates** + targeted refine loop.
- Cost: adaptive windows, retrieval‑only synthesis, strict token budgets.

**Primary success metrics**
- Rare‑important retention ≥95%; contradiction surfacing ≥80%; guide‑map coverage ≥90%;
- Verification pass (top 20%) ≥70%; Retrieval precision/recall tracked.

## 2) Scope & assumptions
- Input: paragraphs/blocks; no timestamps; no diarization.
- Anchors: quotes with **char spans** + **para idx**.
- Model: GPT‑5 baseline via LLM adapter; schema‑validated JSON.
- Storage: filesystem + **SQLite** (WAL) + ledger (canonical claims/entities).
- Memory: streaming; never load full transcript.

## 3) Strategy (map → weave → synthesize)
- Phase 0 — Guide Map (skim): 500‑token windows, 100‑token stride → themes, entities, tensions, hotspots, paragraph ranges.
- Phase 1 — Precision chunking: **adaptive windows** + 250–300 overlap; meaning boundaries; protect hotspots.
- Phase 2 — Deep extraction: exact‑count, schema‑valid claims/contradictions/jargon with quotes + spans.
- Phase 3 — Cross‑chunk linking: canonicalize, dedupe; link support/contradict/refine/duplicate; novelty; **claim evolution**.
- Phase 4 — Retrieval‑based synthesis: sections from **top‑K retrieved** slices; preserve hedging; enforce quote caps.
- Phase 5 — Source verification: verify top 20%; adjust confidence or exclude.

## 4) Adaptive window selection (Precision vs Narrative)
**Signals** (per ~500‑token region): cohesion breaks, discourse markers, new terms, numbers/symbols, questions/hedges, story cues, sentence‑length variance (normalized 0–1).

**PrecisionScore** = 0.25·cohesion + 0.20·markers + 0.20·new_terms + 0.15·numbers + 0.10·hedges − 0.10·story − 0.10·sent_var

**Decision:**
- Episode preset: ≥0.55 → Precision; ≤0.45 → Narrative; else Balanced.
- Mixed mode (recommended) per region: ≥0.60 Precision; ≤0.40 Narrative; else Balanced.
- Transitional chunk on preset switches; sticky decisions require ≥0.10 delta across two regions.
- Borderline: micro A/B on first segment; pick winner by rare‑retention, contradictions, median confidence, duplicate rate.

**Presets**
- Precision: 2.5–3.5k; overlap 250–300.
- Narrative: 5–8k; overlap 250–300.
- Balanced (default): 4–5k; overlap 250–300.

## 5) Deliverables & artifacts
- Core: `final.md`, `global_context.json`, `ledger.sqlite`, `artifacts.sqlite`, `scorecard.json`, `refine_plan.json`.
- Debug/QA: `llm_calls.jsonl`, `decision_log.json`, `verification_log.json`, `evolution_timeline.json`, `link_graph.dot`, `token_trace.csv`, `chunking_decisions.json`.

## 6) Modules & interface contracts
- mapper → In: paragraphs; Out: {themes[], entities[], tensions[], hotspots[para_ranges], notes}
- segmenter → In: paragraphs + mapper cues; Out: chunks[{id, span, para_range, text, preset_used}]
- landmarks → In: chunk; Out: {section_title, key_facts[], numbered_claims[C1..], anchors(spans/paras)}
- extractors → In: chunk; Out:
  - claims[{text, why_nonobvious, rarity, confidence, quote, span, para_idx, hedges[]}]
  - local_contradictions[{a_claim, b_claim, rationale}]
  - jargon[{term, definition, usage_quote, span/para_idx}]
- ledger → In: extracted items; Out: canonical claims/entities + provenance & versions
- retrieval → In: ledger items; Out: top‑K neighbors (fuzzy baseline; embeddings later)
- linker → In: candidate pairs; Out: links[{src_id, dst_id, relation, rationale, confidence}]
- evolution → In: claims over para ranges; Out: {claim_id → trajectory}
- synth → In: retrieved slices; Out: `final.md`
- verify → In: top claims + source spans; Out: verification_results + confidence deltas
- scorecard → In: ledger + links + final selections; Out: coverage, contradictions surfaced, rare‑retention, verification pass, retrieval precision/recall
- runner → orchestration, caching, idempotency, progress callbacks

All extractor/linker passes return **schema‑validated JSON** (no free text inside JSON).

## 7) Data model (SQLite, key fields)
- runs(id, started_at, config_json, correlation_id)
- guide_map(run_id, themes_json, entities_json, tensions_json, hotspots_json)
- chunks(id, run_id, span_start, span_end, para_start, para_end, text, section_title, key_facts_json, preset_used)
- claims(id, run_id, chunk_id, text, why_nonobvious, rarity, confidence, quote, span_start, span_end, para_idx, hedges_json, novelty_score, included_in_final, evolution_trajectory)
- links(run_id, src_id, dst_id, relation, rationale, confidence, semantic_similarity, included_in_final)
- verification_results(claim_id, source_excerpt, supported_bool, confidence_delta, reason)
- metrics(run_id, key, value), events(timestamp, step, item_id, duration_ms, token_cost, correlation_id)

Indexes: (novelty_score, included_in_final), (relation, semantic_similarity), (para_idx)

## 8) Prompting & structured outputs
- Exact counts: “Return **exactly N** items and STOP.”
- Quote cap: ≤ **config.max_quote_words** (default 50) — present verbatim in prompts.
- Token budgets: checked pre‑call (input/output).
- Temperatures: mapper=0.1, extract=0–0.2, link=0.3, synth=0.5, verify=0.0.
- Few‑shot: ≤2 examples only if needed.

## 9) Quality gates & refine loop
- Coverage ≥90% of high‑novelty claims; Rare‑retention ≥95%; Contradictions surfaced ≥80%.
- Verification (top 20%) required; if confidence_delta < −0.3 → exclude.
- Retrieval precision/recall reported.
- If any gate fails → write `refine_plan.json`, re‑read targets, re‑synthesize.

## 10) Reliability, performance, cost
- Schema validation, retries, backoff, circuit breakers, **delta reprompts**.
- Parallel per‑chunk passes; batched linking; sequential guide map & final synth.
- Strict token caps; cache ledgers; log **cost per run** and **per claim**.

## 11) Failure modes & graceful degradation
- Sparse extraction → nudge toward Narrative window in affected regions and retry.
- Over‑linking → raise duplicate threshold; re‑link top claims only.
- Verification mass‑fail → re‑align spans; exclude weak claims but still publish partial final.md (gaps flagged).

## 12) Testing & evaluation
- Unit: segmentation, overlap, schema adherence, dedupe determinism, evolution trajectories, verification deltas.
- Fixtures: monologue‑heavy, contradiction‑rich, jargon‑dense, hedging‑progression, malformed paras.
- A/B: Precision vs Narrative on same episode; compare rare‑retention, contradictions, duplicate rate, median confidence.

## 13) Anti‑patterns
No full‑transcript prompts; don’t skip guide map; don’t exceed ~8k windows; don’t trust unvalidated JSON; don’t hardcode model names/keys; don’t concatenate SQL; don’t serialize sequentially when parallel is safe; don’t synthesize without ledger.

## 14) Config defaults
- Windows: Precision 2.5–3.5k; Narrative 5–8k; Balanced 4–5k; overlap 250–300
- Extractor counts: non‑obvious=7; contradictions≤3; jargon=5; max_quote_words=50
- Verification: top_percent=0.2; min_conf=0.7; exclude_delta<−0.3
- Retrieval: topK_linking=20; topK_section=10; thresholds split (dedupe ≥0.88; neighbor ≥0.70)
- Performance: max_concurrent_calls=3; batch_size=10; circuit_breaker=3; cooldown=60s
