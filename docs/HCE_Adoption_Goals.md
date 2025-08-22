# HCE Adoption Goals (Guardrails + Acceptance Criteria) — 2025-08-18

## Guardrails
- Additive changes only; legacy pipeline behind a feature flag (`--use_hce` or `USE_HCE=1`).
- Deterministic configs; cache-able; import-safe modules.
- Minimal tests accompany new code; no side effects on import.

## Scope — Phase 1 (Integration + Baseline)
- Add `claim_extractor/` package with skeleton stages.
- Implement ModelURI-backed adapters (local/cloud per stage).
- Consolidated Claims + adaptive rerank (no arbitrary K).
- Side-channels: People, Concepts, Jargon (detect, evidence, optional disambiguation).
- Optional Skim milestones; Markdown + JSONL exports.
- CLI: `scripts/run_episode.py`; smoke test + unit tests.

## Scope — Phase 2 (Upgrades A, B, C, E, G, H, I; D partial)
- **A: NLI truth check** (local NLI) + uncertainty routing to judge.
- **B: Clustering** via HDBSCAN; upgraded cross-encoder reranker.
- **C: Calibration** (self-consistency variance, NLI margin, rerank margin) + learned gate.
- **E: Discourse tags** at sentence/turn level (claim/evidence/anecdote/caveat/hedge).
- **G: Temporal & numeric** normalization + range sanity + conflict flags.
- **H: QA** snapshot tests; miner→judge invariants; telemetry.
- **I: Obsidian UX**: Mermaid relation graph, backlinks, triage lanes.
- **D (partial): Global index** aggregating people/models/terms across episodes.

## Out of Scope (for now)
- **F: Training loop / distillation** (explicitly excluded per request).

## Acceptance Criteria
- `make hce-smoketest` passes on sample data; produces MD+JSONL.
- `pytest -q` passes new tests.
- Feature flag off → legacy behavior unchanged.
- With flag on, pipeline completes with non-empty outputs for claims, people, concepts, jargon.

## Deliverables
- Package code, prompts, rules, docs, tests, PR template.
- `docs/architecture/HCE_Integration_Report.md` authored by Cursor with mapping + plan.
