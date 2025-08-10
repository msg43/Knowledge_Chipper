# SuperChunk Implementation To-Dos

See `docs/superchunk-plan.mdc` and `docs/superchunk-workflow.mdc` for rules/specs.

- [x] Create config + validators + model‑agnostic LLM adapter
- [x] Implement mapper (skim) and segmenter (adaptive windows) + write `chunking_decisions.json`
- [ ] Implement landmarks (section titles, key facts, numbered claims)
- [x] Implement extractors (schema validation + exact counts) and persist to SQLite
- [x] Implement ledger (canonicalization, dedupe, novelty) + retrieval (fuzzy baseline)
- [x] Implement linker (support/contradict/refine/duplicate) with conservative "none"
- [x] Implement synthesis (retrieval‑only) with quote caps + char spans/para idx
- [x] Implement verification (top 20%) and adjust confidence/exclusions
- [x] Implement scorecard (coverage, rare‑retention, contradictions, retrieval P/R, verification pass)
- [ ] Implement refine loop (write `refine_plan.json`, re‑read targets, re‑synthesize)
- [x] Add observability: events, token/cost logging; DB indexes; finalize artifacts bundle
