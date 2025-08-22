# Hybrid Claim Extractor (HCE) — Starter Kit

This is a Cursor-ready scaffold for a multi-pass **claim extraction + summarization** pipeline that mixes local and cloud models. It uses diarized, timestamped transcripts and produces:
- Consolidated Claims (clustered + merged evidence)
- Relations (supports / contradicts / depends / refines)
- People / Mental Models / Jargon catalogs
- Milestones (optional skim)
- Markdown and JSONL exports with timestamps for auditability

## Key Principles
- **High recall → High precision**: Over-generate locally, then tighten via rerank + (optional) flagship judge.
- **Selective spend**: Route only hard/ambiguous items to a flagship model.
- **Provenance**: Every claim has verbatim quotes and timestamps.
- **Flexible backends**: Each stage can run local or cloud via ModelURIs.

## Stages
1. (Optional) **Skim** milestones for chapter-like anchors.
2. **Mine** candidate claims per segment (model-configurable).
3. **Link** evidence spans to quotes + timestamps.
4. **Consolidate** near-duplicates into **Consolidated Claims**.
5. **Rerank** with cross-encoder; **adaptive keep** (no fixed K).
6. **Calibrate & Route** via uncertainty; send tricky items to judge.
7. **Judge** (flagship) accept/reject + score: importance, novelty, controversy, fragility.
8. **Relations**: detect supports/contradicts/refines.
9. **Side-channels**: People, Concepts (mental models), Jargon.
10. **Temporal & numeric checks**; **Discourse tags**.
11. **Global index** across episodes; **Obsidian-friendly exports**.

## Flexible Models
All stages accept **ModelURIs** (`ollama://`, `local://`, `openai://`, `anthropic://`, `vllm://`, etc.). Users can choose local/cloud per stage.

## A–I Upgrades (F excluded)
A) NLI truth/entailment pre-check + targeted flagship review.  
B) Better clustering (HDBSCAN) + stronger cross-encoder rerank.  
C) Calibration & uncertainty metrics (+ logistic gate) for routing.  
D) Cross-episode global indexes for people/models/terms.  
E) Discourse tagging (claim/evidence/anecdote/caveat/hedge).  
G) Temporal normalization and numeric consistency checks.  
H) QA: invariants, snapshot tests, telemetry.  
I) Obsidian UX polish: backlinks, Mermaid graphs, triage lanes.

See `.cursor/rules` and `docs/architecture/HCE_Adoption_Goals.md` for adoption plan.
