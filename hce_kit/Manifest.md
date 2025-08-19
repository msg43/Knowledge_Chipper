HCE Kit – File Manifest
Top-level

README.md — overview, setup instructions.

Makefile — quick targets (test, hce-smoketest).

pyproject.toml — package metadata & dependencies.

📂 docs/architecture

HCE_StarterKit.md — architecture overview & principles.

HCE_Adoption_Goals.md — guardrails, scope, acceptance criteria.

HCE_Integration_Report.md — placeholder; Cursor populates integration notes.

sample_episode.json — tiny test transcript for smoke runs.

📂 .github

PULL_REQUEST_TEMPLATE.md — PR checklist for HCE integration.

📂 .cursor
rules/

hce-integration.mdc — Cursor integration plan (adds HCE modules + upgrades A–I except F).

hce-workflow.mdc — stepwise workflow for integration.

prompts/

hce-master.txt — master prompt to launch Cursor integration.

hce-iter-fix.txt — iteration/fix prompt for follow-ups.

📂 claim_extractor

init.py — package exports.

config_flex.py — config with flexible ModelURIs & rerank policy.

types.py — Pydantic schemas (Segments, Claims, ConsolidatedClaims, etc.).

io_utils.py — JSON/MD load & save helpers.

skim.py — milestone extraction (episode “chapters”).

miner.py — candidate claim mining.

evidence.py — evidence linking.

dedupe.py — clustering into Consolidated Claims.

rerank.py — rerank claims with cross-encoder.

rerank_policy.py — adaptive keep (no fixed K).

router.py — routes uncertain/hard claims to flagship judge.

judge.py — flagship judging (accept/reject + scoring).

export.py — Markdown/JSONL/Mermaid exports.

people.py — detect & disambiguate people/org mentions.

concepts.py — detect mental models.

glossary.py — detect jargon/key terms.

nli.py — entailment scaffolding (Upgrade A).

calibration.py — compute uncertainty from multiple signals (Upgrade C).

global_index.py — cross-episode rollup of people/models/jargon (Upgrade D).

discourse.py — discourse tagging (claim/evidence/anecdote/hedge) (Upgrade E).

temporal_numeric.py — temporal normalization & numeric sanity checks (Upgrade G).

relations.py — detect supports/contradicts/refines between claims.

storage_sqlite.py — SQLite persistence with FTS5 search and idempotent upserts.

sqlite_schema.sql — Comprehensive database schema for claims, relations, and entities.

📂 claim_extractor/models

llm_any.py — generic ModelURI wrapper (local/cloud).

embedder.py — embedding model wrapper.

cross_encoder.py — reranker model wrapper.

📂 claim_extractor/prompts

skim.txt — milestone extraction prompt.

miner.txt — claim mining prompt.

judge.txt — claim judging prompt.

contradiction.txt — relation prompt (supports/contradicts/refines).

people_detect.txt — people/org mention detection prompt.

people_disambiguate.txt — canonicalization/disambiguation prompt.

concepts_detect.txt — mental model detection prompt.

glossary_detect.txt — jargon/term detection prompt.

📂 scripts

run_episode.py — CLI: run full HCE pipeline on one transcript.

batch_run.py — CLI: batch process a folder of transcripts.

📂 tests/claim_extractor

test_imports.py — sanity import test.

test_schema_roundtrip.py — schema validation test (EpisodeBundle).
