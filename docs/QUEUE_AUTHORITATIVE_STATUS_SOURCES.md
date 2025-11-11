# Queue Authoritative Status Sources

## Overview
This document defines the authoritative sources for each pipeline stage's status, ensuring the Queue Tab displays accurate information while maintaining the claim-centric architecture.

## Pipeline Stages & Status Sources

### 1. Download Stage

**Authoritative Source:** `MediaSource` table
- **Status Field:** `MediaSource.audio_downloaded` (Boolean)
- **Additional Fields:**
  - `audio_file_path` - Path to downloaded file
  - `audio_file_size_bytes` - File size
  - `needs_audio_retry` - Retry needed flag
  - `retry_count` - Number of attempts
  - `failure_reason` - If failed

**Session State:** `~/.knowledge_system/session_state.json`
- Account cooldowns
- Session schedules
- Completed source_ids per account

**Status Mapping:**
- `queued` - URL in scheduler, not yet processed
- `scheduled` - Assigned to session, waiting for start time
- `downloading` - Active download in progress
- `completed` - audio_downloaded=True, file exists
- `failed` - max_retries_exceeded=True
- `blocked` - In cooldown or rate limited

### 2. Transcription Stage

**Authoritative Source:** `Transcript` table
- **Existence Check:** Presence of `Transcript` record with matching source_id
- **Additional Fields:**
  - `transcript_type` - Method used (whisper, diarized, etc.)
  - `processing_time_seconds` - Duration
  - `whisper_model` - Model used
  - `confidence_score` - Quality metric

**Status Mapping:**
- `not_applicable` - No audio file to transcribe
- `queued` - Audio exists, no transcript yet
- `processing` - AudioProcessor.process() running
- `completed` - Transcript record exists
- `failed` - ProcessorResult.success=False logged

### 3. Summarization Stage  

**Authoritative Source:** `Summary` table
- **Existence Check:** Presence of `Summary` record with matching source_id
- **Additional Fields:**
  - `processing_type` - 'hce' or 'hce_unified'
  - `llm_provider`, `llm_model` - Model info
  - `total_tokens`, `processing_cost` - Usage metrics
  - `processing_time_seconds` - Duration

**Secondary Source:** `System2Orchestrator` Job/JobRun for 'mine' job_type
- Provides checkpoint/resume state
- Tracks attempt_number for retries

**Status Mapping:**
- `not_applicable` - No transcript to summarize
- `queued` - Transcript exists, no summary yet
- `processing` - EnhancedSummarizationWorker active
- `completed` - Summary record exists
- `failed` - Worker error or job_run.status='failed'

### 4. HCE Mining Stage

**Authoritative Source:** `Summary.hce_data_json` field
- **Existence Check:** hce_data_json is not null/empty
- **Content:** Structured HCE output (claims, entities, etc.)

**Secondary Source:** `System2Orchestrator` Job/JobRun for 'mine' job_type
- Tracks mining progress within summarization

**Status Mapping:**
- `not_applicable` - Non-HCE summarization mode
- `queued` - HCE mode selected, not started
- `processing` - UnifiedHCEPipeline running
- `completed` - hce_data_json populated
- `failed` - Mining error in pipeline

### 5. Flagship Evaluation Stage

**Authoritative Source:** `Summary.hce_data_json.claims[].tier` field
- **Existence Check:** Claims have tier assignments (A, B, C)
- **Additional Info:** Claims have confidence scores

**Secondary Source:** `System2Orchestrator` Job/JobRun for 'flagship' job_type

**Status Mapping:**
- `not_applicable` - No claims to evaluate
- `queued` - Claims exist without tiers
- `processing` - Flagship evaluation running
- `completed` - All claims have tier assignments
- `failed` - Evaluation error

## Key Principles

1. **Single Source of Truth** - Each stage has ONE authoritative table/field
2. **Existence = Completion** - Presence of records indicates stage completion
3. **Claim-Centric** - All stages serve to extract/refine claims as the end goal
4. **Progressive Enhancement** - Each stage builds on the previous
5. **Optional Stages** - Not all sources go through all stages

## Implementation Notes

- The Queue Tab will query these authoritative sources to build the unified view
- Real-time updates will come from workers writing to these sources
- Historical data can be reconstructed from timestamps in each table
- Failed stages should preserve partial progress for debugging
