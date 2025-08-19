## Summary
Hybrid Claim Extractor (HCE) Phase 1 + Upgrades (A,B,C,D-partial,E,G,H,I).

## What’s included
- [ ] `claim_extractor/` package (modules + prompts)
- [ ] Flexible ModelURI backends (local/cloud) per stage
- [ ] Consolidated Claims + adaptive rerank
- [ ] Side-channels: People, Concepts, Jargon; optional Skim
- [ ] Upgrades: NLI check, HDBSCAN clustering, calibration gate, global index, discourse tags, temporal/numeric checks
- [ ] Obsidian UX: Mermaid graphs, backlinks, triage lanes
- [ ] CLI + tests + docs

## Verification
- [ ] `make hce-smoketest` passes
- [ ] `pytest -q` passes
- [ ] `scripts/run_episode.py sample.json --outdir out/` produces MD + JSONL

## Risks / Rollback
- Feature flag: set `USE_HCE=0` or omit `--use_hce`
- No legacy deletions; additive changes only
