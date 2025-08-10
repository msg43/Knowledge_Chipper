# SuperChunk Smart Chunking Summarization — Comprehensive TODO (v2)

- [x] Adaptive Chunking Signals + Switching
  - Compute PrecisionScore per ~500-token region from signals (cohesion breaks, discourse markers, new terms, numbers/symbols, questions/hedges, story cues, sentence-length variance)
  - Episode decision: ≥0.55 Precision; ≤0.45 Narrative; else Balanced; Region decision: ≥0.60 Precision; ≤0.40 Narrative; else Balanced
  - Transitional chunk when switching presets; sticky decision requires ≥0.10 delta across two regions
  - Micro A/B for borderline episodes; select by rare-retention, contradictions, median confidence, duplicate rate
  - Write `chunking_decisions.json` with reasons per chunk
  - Acceptance: deterministic decisions on a fixed input; unit tests for thresholds and transitions

- [ ] Boundary-Aware Segmentation
  - Segment by meaning boundaries using mapper hotspots and landmarks anchors
  - Enforce window presets (Precision 2.5–3.5k; Balanced 4–5k; Narrative 5–8k; overlap 250–300)
  - Maintain char spans and para indices; minimize mid-sentence splits
  - Acceptance: segmentation unit tests covering overlap and boundary integrity

- [ ] Robust Landmarks Detection
  - Extract section titles, key facts, numbered claims; produce anchors with char spans
  - Use LLM with JSON schema and delta reprompt if missing fields
  - Acceptance: JSON validation, anchors within text bounds

- [ ] Extractors (Production)
  - Exact-count extraction with quote caps and strict JSON validation
  - Delta reprompts to fill missing items; enforce char spans + para_idx
  - Persist to SQLite with run_id and chunk_id; deterministic IDs
  - Acceptance: schema adherence; quotes ≤ max_quote_words; persistence verified

- [ ] Ledger: Canonicalization, Dedupe, Novelty, Evolution
  - Canonical form of claims/entities; novelty scoring; dedupe threshold ≥0.88
  - Track claim evolution over para ranges; mark included_in_final
  - DB indexes: (novelty_score, included_in_final), (relation, semantic_similarity), (para_idx)
  - Acceptance: deterministic dedupe; evolution trajectories computed

- [ ] Retrieval (Baseline + Pluggable Embeddings)
  - Fuzzy baseline now; interface to swap in embeddings later
  - Provide topK for linking and synthesis; thresholds configurable
  - Acceptance: precision/recall metrics computed on fixtures

- [ ] Linker (Relations with “none” allowed)
  - Create support/contradict/refine/duplicate links with rationale and confidence
  - Conservative “none” when below neighbor threshold (≥0.70)
  - Acceptance: link distribution sane; duplicates reduced by dedupe threshold

- [ ] Synthesis (Retrieval-Only)
  - Build `final.md` sections from top-K retrieved slices; preserve hedging
  - Enforce quote caps; use only retrieved text; never full transcript
  - Acceptance: sections render with spans and para idx references

- [ ] Verification (Top 20%)
  - Verify top claims with source spans; adjust confidence; exclude if delta < −0.3
  - Record results in `verification_results` table and `verification_log.json`
  - Acceptance: excluded claims not present in final selections

- [ ] Scorecard + Gates + Refine Loop
  - Compute coverage, rare-retention, contradictions surfaced, retrieval P/R, verification pass
  - If any gate fails: write `refine_plan.json`, re-read targets only, re-synthesize
  - Acceptance: targeted refine loop modifies only affected regions

- [ ] Observability & Costs
  - Log events, token budgets, costs per run and per claim (`llm_calls.jsonl`, `token_trace.csv`)
  - Add DB indexes and optimize WAL pragmas
  - Acceptance: artifacts written; logs consistent with calls

- [ ] Tests & CLI Integration
  - Unit tests for segmentation, extractors, ledger dedupe, linking, verification
  - Add CLI entry to run SuperChunk pipeline on sample inputs
  - Acceptance: green tests; CLI produces artifacts bundle
