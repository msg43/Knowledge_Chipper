# HCE Summarization Upgrades & Fixes TODO

## 1) Skim optionality and ordering
- [ ] Expose skim toggle in CLI
  - Add `--use-skim/--no-skim` (default: on) to `src/knowledge_system/commands/summarize.py` and `commands/process.py`.
  - Pass flag into `SummarizerProcessor` → `HCEPipeline` (`PipelineConfigFlex.use_skim`).
  - Acceptance: session report shows skim on/off; disabling skim reduces LLM calls.
- [ ] Expose skim toggle in GUI
  - Add “High-level skim” checkbox in `src/knowledge_system/gui/tabs/summarization_tab.py`.
  - Persist setting, pass to worker → processor pipeline config.
  - Acceptance: toggle persists; logs show skim disabled when off.
- [ ] Ensure skim runs pre-chunk
  - Keep skim before any heavy/mining steps; document in code comments.
  - Acceptance: no chunk-based calls precede skim; skim can be fully skipped.

## 2) Dual-judge routing (lightweight vs flagship)
- [ ] Implement routed judging
  - Use `router.Router.needs_flagship` to split claims.
  - Judge “keep_local” via lightweight judge; “to_flagship” via flagship judge.
  - Update `src/knowledge_system/processors/hce/judge.py` to support batch judging per model.
  - Acceptance: routed claims are judged by configured flagship model; others use lightweight.
- [ ] Make routing thresholds configurable
  - CLI: `--router-uncertainty-threshold <float>` and optional claim-type rules.
  - GUI: slider/number input; explanatory tooltip.
  - Acceptance: changing threshold changes routed claim count in report.

## 3) Per-stage model configuration (CLI + GUI)
- [ ] Stage model flags in CLI
  - Miner: `--miner-model`, `--heavy-miner-model`
  - Judge: `--judge-model`, `--flagship-judge-model`
  - Embedder/Reranker: `--embedder-model`, `--reranker-model`
  - Entities/NLI: `--people-disambiguator-model`, `--nli-model`
  - Wire into `StageModelConfig` in `hce/config_flex.py`.
  - Acceptance: pipeline uses user-selected models; reflected in report.
- [ ] Stage model selectors in GUI
  - Dropdowns for the above in `summarization_tab.py` (Advanced section).
  - Persist, validate, and show effective URIs in debug logs.
  - Acceptance: chosen models persist and are used.

## 4) Profiles (fast | balanced | quality)
- [ ] CLI profile
  - `--profile fast|balanced|quality` pre-fills flags:
    - fast: skim off, routing off, lightweight judge only.
    - balanced: skim on, routing on (threshold ~0.35), default locals.
    - quality: skim on, routing on (lower threshold), enable NLI & people disambiguation.
  - Acceptance: profile overrides reflected in effective settings output.
- [ ] GUI profile dropdown
  - Apply presets with immediate UI feedback; allow manual override per field.
  - Acceptance: switching profiles updates toggles/dropdowns.

## 5) Prompt-driven summary mode
- [ ] CLI: prefer template over HCE (optional mode)
  - `--prefer-template-summary` (bypass HCE formatting; still allow optional HCE extraction for metadata).
  - Ensure `{text}` substitution; truncation limits; model/provider usage reported.
  - Acceptance: output structure follows template when flag is set.
- [ ] GUI: “Prompt-Driven Summary” toggle
  - Use selected template as authoritative structure; display note about HCE off (or metadata-only).
  - Acceptance: visible mode; summary mirrors prompt sections.

## 6) Session reporting & telemetry
- [ ] Enhance report with routing analytics
  - Counts: total claims, routed to flagship vs kept local; per-judge token/cost/time.
  - Sample routed claims with reason (claim type or uncertainty).
  - Acceptance: report includes new sections and metrics.
- [ ] Log effective config
  - Persist all effective model URIs, thresholds, and toggles per run.
  - Acceptance: reproducibility from report alone.

## 7) Budgets and guardrails
- [ ] Flagship budget per file/session
  - CLI: `--flagship-max-tokens-per-file`, `--flagship-max-tokens-session`.
  - GUI: budget fields with warning when exceeded; best-effort soft cap.
  - Acceptance: routing prunes/defers flagship calls beyond budget and notes it in report.

## 8) Skim improvements (later milestone)
- [ ] Make skim model selectable (default to miner model)
  - Expose `--skim-model`; GUI dropdown (advanced).
  - Acceptance: skim uses chosen model; logged explicitly.
- [ ] Optional: use milestones to guide miner windows
  - Heuristic sampling or priority weighting based on skim milestones.
  - Acceptance: documented experiment flag; measurable effect on claim coverage.

## 9) Documentation
- [ ] README updates
  - Describe skim toggle, profiles, per-stage model selection, routed judging, budgets.
  - Add examples for common workflows.
  - Acceptance: docs align with CLI help/GUI labels.

## 10) Tests
- [ ] Unit/integration tests
  - Routing correctness (thresholds/types), dual-judge dispatch, profile expansion, budget enforcement, skim on/off behavior, prompt-driven mode.
  - Golden report tests for new analytics sections.
  - Acceptance: CI green with coverage for new branches.

## File touchpoints
- `src/knowledge_system/processors/summarizer.py` (wire flags → pipeline config; report metadata)
- `src/knowledge_system/processors/hce/config_flex.py` (stage URIs, rerank policy, `use_skim`)
- `src/knowledge_system/processors/hce/router.py` (threshold param; expose in pipeline)
- `src/knowledge_system/processors/hce/judge.py` (dual-judge paths)
- `src/knowledge_system/processors/hce/skim.py` (model selection)
- `src/knowledge_system/commands/summarize.py` and `commands/process.py` (CLI flags, profiles, report)
- `src/knowledge_system/gui/tabs/summarization_tab.py` (GUI toggles/dropdowns, profiles, budgets)
- `README.md` (docs)
