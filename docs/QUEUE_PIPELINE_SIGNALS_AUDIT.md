# Queue Pipeline Signals Audit

## Overview
This document catalogues existing pipeline signals in the Knowledge Chipper codebase that can be leveraged for the Queue Tab implementation.

## 1. MediaSource Model Lifecycle Fields

The `MediaSource` model in `database/models.py` contains several fields tracking processing state:

### Status Fields
- `status` (String, default="pending") - Values: 'pending', 'processing', 'completed', 'failed'
- `processed_at` (DateTime) - When processing completed

### Download Tracking
- `audio_downloaded` (Boolean, default=False) - Whether audio file downloaded
- `audio_file_path` (String) - Path to downloaded audio
- `audio_file_size_bytes` (Integer) - Size of downloaded file
- `audio_format` (String) - Audio format
- `metadata_complete` (Boolean, default=False) - Whether metadata fetched

### Retry/Failure Tracking
- `needs_metadata_retry` (Boolean, default=False)
- `needs_audio_retry` (Boolean, default=False) 
- `retry_count` (Integer, default=0)
- `last_retry_at` (DateTime)
- `first_failure_at` (DateTime)
- `max_retries_exceeded` (Boolean, default=False)
- `failure_reason` (Text)

### Summary Tracking
- `summary_generated_at` (DateTime)
- `summary_generated_by_model` (String)

## 2. ProcessingJob Model

The `ProcessingJob` model tracks batch processing:

### Job Types
- 'transcription'
- 'summarization'  
- 'moc_generation'

### Status Tracking
- `status` (String) - Values: 'pending', 'running', 'completed', 'failed', 'cancelled'
- `created_at`, `started_at`, `completed_at` (DateTime)

### Progress Tracking
- `total_items` (Integer)
- `completed_items` (Integer, default=0)
- `failed_items` (Integer, default=0)
- `skipped_items` (Integer, default=0)

### Resource Usage
- `total_cost` (Float)
- `total_tokens_consumed` (Integer)
- `total_processing_time_seconds` (Float)

## 3. System2 Models (Job & JobRun)

### Job Model
- `job_type` - Values: 'transcribe', 'mine', 'flagship', 'upload', 'pipeline'
- `input_id` - source_id reference
- `auto_process` - Whether to chain to next stage

### JobRun Model  
- `status` - Values: 'queued', 'running', 'succeeded', 'failed', 'cancelled'
- `attempt_number` - Retry tracking
- `checkpoint_json` - Resume state
- `metrics_json` - Performance metrics
- `error_code`, `error_message` - Failure tracking

## 4. Session-Based Scheduler State

The `SessionBasedScheduler` maintains state in `~/.knowledge_system/session_state.json`:

### Account State
- `sessions_completed`
- `next_session_idx`
- `cooldown_until`
- `total_downloads`
- `completed_source_ids`

### Schedule State
- Session start times
- Duration and max downloads per session
- Session status ('pending', 'completed')

## 5. Transcript Model

The `Transcript` model tracks transcription details:
- `transcript_type` - 'youtube_api', 'diarized', 'whisper'
- `whisper_model` - Model used
- `processing_time_seconds`
- `speaker_assignment_completed` (Boolean)

## 6. Summary Model

The `Summary` model tracks summarization:
- `processing_type` - 'hce', 'hce_unified'
- `llm_provider`, `llm_model`
- `processing_time_seconds`
- `total_tokens`, `processing_cost`

## Key Findings

1. **MediaSource is the central tracking entity** - It already has download status, retry tracking, and high-level processing status.

2. **ProcessingJob provides batch tracking** - Good for aggregating multiple items in a single operation.

3. **System2 models (Job/JobRun) provide pipeline orchestration** - They track individual pipeline stages with detailed metrics.

4. **Session state JSON provides scheduler-specific state** - Download scheduling, cooldowns, and account management.

## Gaps for Queue Tab

1. **No unified stage status** - Status is scattered across MediaSource.status, ProcessingJob.status, and JobRun.status
2. **No progress percentage** - Only item counts, not progress within a single item
3. **No stage-specific metadata** - Need to aggregate from multiple sources
4. **No real-time event system** - Updates require polling database

## Recommendations

1. Create `SourceStageStatus` as a unified view of all pipeline stages
2. Use existing models as authoritative sources but aggregate into queue view
3. Leverage session state JSON for download scheduling visibility
4. Add event bus for real-time updates without constant polling
