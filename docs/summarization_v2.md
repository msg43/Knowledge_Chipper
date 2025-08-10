# Summarization System – Branch: summarizer-V2

This document describes the summarization-related functionality that exists on the current branch (`summarizer-V2`) and how it is wired through the CLI and GUI.

## Entry Points

- CLI command `knowledge-system summarize`
  - File: `src/knowledge_system/commands/summarize.py`
  - Key options: `--model`, `--provider`, `--max-tokens`, `--template`, `--update-md`, `--recursive/--no-recursive`, `--patterns`, `--checkpoint`, `--resume`, `--force`, `--progress`, `--dry-run`
  - Default prompt template: `config/prompts/document summary.txt` if `--template` not provided
  - Builds a session report `summarization_report_YYYYMMDD_HHMMSS.md` with token/cost/time stats
  - Index optimization: builds and consults a summary index to skip unchanged files (unless `--force`)

- CLI command `knowledge-system process`
  - File: `src/knowledge_system/commands/process.py`
  - Pipeline: optional transcription → summarization → optional MOC generation
  - Summarization step calls `SummarizerProcessor.process(input_for_summary, style="structured")` (note: `style` kwarg is currently ignored by processor; see Vestiges below)

- GUI tab: Content Analysis (Summarization)
  - File: `src/knowledge_system/gui/tabs/summarization_tab.py`
  - Uses `EnhancedSummarizationWorker` (QThread) to run `SummarizerProcessor` with progress, cancellation, and batch ETAs
  - Lets users select provider/model, max tokens, and a prompt template (either user-specified path or auto-chosen by “Analysis Type” → file in `config/prompts/`)
  - Supports two output modes: update markdown in place or create separate summary files

## Core Processor

- Class: `SummarizerProcessor`
  - File: `src/knowledge_system/processors/summarizer.py`
  - Responsibilities:
    - Read input text from `.txt`, `.md`, `.json`, `.html/.htm`, `.pdf` (PDF/HTML via helper processors)
    - Generate a summarization prompt from template (file path or string) with `{text}` and `{MAX_TOKENS}` substitution; fall back to a default prompt when template missing
    - Intelligent chunking for large inputs using model-aware thresholds (95% context utilization):
      - Computes context window via `get_model_context_window(model)`
      - Estimates prompt token overhead and reserves `max_tokens` for output + 5% safety margin
      - `calculate_chunking_config(...)` and `create_intelligent_chunks(...)`
      - Per-chunk prompts via `generate_chunk_summary_prompt(...)`
      - Final reassembly via `reassemble_chunk_summaries(...)` when multiple chunks
    - Unified LLM call through `UnifiedLLMClient` with optional progress callback and cancellation token
    - Character-based progress reporting at file and batch levels (`SummarizationProgress`), including dynamic heartbeats during LLM generation
    - Returns `ProcessorResult` with `summary`, token stats, speed, compression ratio, and chunking summary
    - Summary index helpers to detect unchanged sources and skip work

- Important methods:
  - `_generate_prompt(text, template)` – Builds prompt from template (path or raw string) with safe substitutions
  - `_calculate_smart_chunking_threshold(text, template)` – Model-aware decision for chunking
  - `_process_with_chunking(...)` – Full chunking flow (prompt → LLM per chunk → reassembly)
  - `_call_llm_provider(prompt, progress_cb, cancellation_token)` – Unified LLM call + heartbeats
  - `_build_summary_index(output_dir)`, `_check_needs_summarization(source, index)`, `_save_index_to_file(...)`, `_update_index_file(...)`

## Provider Architecture

- File: `src/knowledge_system/utils/llm_providers.py`
  - `UnifiedLLMClient` encapsulates provider differences
  - Providers: `OpenAIProvider`, `AnthropicProvider`, `LocalLLMProvider` (Ollama/LM Studio)
  - Normalizes responses to `LLMResponse` with token usage and metadata
  - Local/Ollama integration includes health checks and basic token estimates

## Configuration

- File: `config/settings.example.yaml`
  - `llm`: default provider/model/max_tokens/temperature
  - `summarization`: overrides for summarization; GUI also sets `max_tokens`, provider, model
  - `local_config`: base URL and defaults for local backends

## Outputs

- CLI summarize:
  - If `--update-md`: in-place update of `## Summary` section for `.md`
  - Else: writes `<name>_summary.md` with metadata (source, model, provider, tokens, speed, cost, compression) and links (YouTube/transcript when applicable)
- GUI:
  - In-place update option for `.md`
  - Separate file creation with YAML frontmatter built by `generate_unified_yaml_metadata`

## Progress and Cancellation

- Character-based progress and ETAs for both single and batch workflows
- Heartbeat thread during LLM generation with dynamic percent and ETA adjustments
- Full cancellation support via `CancellationToken` (checked at multiple stages)

## Vestiges and Notes

- `process.py` passes `style="structured"` into `SummarizerProcessor.process(...)`, but the processor ignores `style` (it uses templates instead). `_get_style_template(...)` exists but is not part of the active flow.
- Tests and docs may reference a `--style` CLI flag, but the current `summarize.py` does not expose it; the system is template/prompt-controlled.

## High-level Data Flow

1) Input file(s) enumerated (CLI/GUI)
2) Optional index check to skip unchanged
3) Read text and analyze size; compute chunking threshold
4) If large → chunk, summarize per-chunk, reassemble; else → single prompt and summarize
5) Emit progress throughout with ETAs; support cancellation
6) Persist outputs (in-place update or separate files), update index, and generate session report (CLI)
