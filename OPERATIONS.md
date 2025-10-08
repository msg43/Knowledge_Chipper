# System 2 Operations Guide

## Overview

System 2 represents a major architectural evolution of the Knowledge Chipper, introducing:
- SQLite-first truth layer with WAL enabled
- Job orchestration with checkpoint persistence  
- Centralized LLM adapter with hardware-aware concurrency
- Structured logging with error taxonomy
- Versioned JSON schemas for all LLM I/O

## Key Components

### 1. Database Layer

**Tables Added:**
- `job` - Top-level job records
- `job_run` - Individual execution attempts
- `llm_request` - All LLM API calls
- `llm_response` - LLM responses with metrics

**Enhanced Tables:**
- All HCE tables now have `updated_at` columns for optimistic concurrency

**Configuration:**
```sql
PRAGMA journal_mode=WAL;  -- Write-Ahead Logging enabled
```

### 2. Job Orchestration

The `System2Orchestrator` manages all processing jobs:

```python
from knowledge_system.core.system2_orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# Create a job
job_id = orchestrator.create_job(
    job_type="mine",  # or "transcribe", "flagship", "upload", "pipeline"
    input_id="episode_001",
    config={"model": "gpt-3.5-turbo"},
    auto_process=True  # Chain to next stage automatically
)

# Process the job
result = await orchestrator.process_job(job_id)
```

**Job Types:**
- `transcribe` - Audio/video to transcript
- `mine` - Extract claims, jargon, people, mental models
- `flagship` - Evaluate and rank claims
- `upload` - Upload to cloud storage
- `pipeline` - Complete end-to-end processing

### 3. LLM Adapter

Centralized LLM management with hardware-aware limits:

```python
from knowledge_system.core.llm_adapter import get_llm_adapter

adapter = get_llm_adapter()

# Make LLM call with automatic rate limiting and retries
response = await adapter.complete_with_retry(
    provider="openai",
    model="gpt-3.5-turbo", 
    messages=[{"role": "user", "content": "Extract claims..."}],
    temperature=0.7
)
```

**Hardware Tiers:**
- Consumer (M1/M2 base): 2 concurrent requests
- Prosumer (M1/M2 Pro/Max): 4 concurrent requests  
- Enterprise (M1/M2 Ultra): 8 concurrent requests

### 4. Structured Logging

System 2 introduces JSON-structured logs with correlation IDs:

```python
from knowledge_system.core.system2_logger import get_system2_logger

logger = get_system2_logger(__name__)
logger.set_job_run_id("run_123")

# Log with metrics
logger.log_operation(
    "mining",
    duration_ms=1500,
    status="success",
    segments_processed=10
)

# Log with error code
logger.error(
    "Processing failed",
    error_code=ErrorCode.LLM_API_ERROR,
    exc_info=True
)
```

### 5. Schema Validation

All LLM inputs/outputs are validated against JSON schemas:

```python
from knowledge_system.processors.hce.schema_validator import get_validator

validator = get_validator()

# Validate miner output
is_valid, errors = validator.validate_miner_output(result)

# Repair and validate
repaired, is_valid, errors = validator.repair_and_validate(
    result, "miner_output"
)
```

## GUI Updates

### Tab Structure (7 tabs only)
1. **Introduction** - Getting started
2. **Transcribe** - With "Process automatically through entire pipeline" checkbox
3. **Summarize** - LLM summarization 
4. **Review** - SQLite-backed claim editor
5. **Upload** - Cloud storage management
6. **Monitor** - Directory watching (renamed from Watcher)
7. **Settings** - Configuration

### Review Tab Features
- Direct SQLite integration
- Real-time validation
- Tier-based color coding (A=green, B=blue, C=red)
- Auto-save option
- CSV export

## Monitoring & Observability

### Metrics Collection
```python
from knowledge_system.core.system2_logger import get_metrics_collector

metrics = get_metrics_collector()
metrics.start_timer("processing")
# ... do work ...
duration = metrics.stop_timer("processing")
metrics.increment("claims_extracted", 42)
```

### Log Aggregation
All logs are JSON-formatted for easy parsing:
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "logger": "knowledge_system.core.orchestrator",
  "message": "Job completed",
  "job_run_id": "run_123",
  "metrics": {
    "duration_ms": 5000,
    "claims_extracted": 42
  }
}
```

### Error Taxonomy
- **HIGH severity**: `DATABASE_CONNECTION_ERROR_HIGH`, `MEMORY_EXCEEDED_ERROR_HIGH`
- **MEDIUM severity**: `API_RATE_LIMIT_ERROR_MEDIUM`, `TRANSCRIPTION_PARTIAL_ERROR_MEDIUM`
- **LOW severity**: `CACHE_MISS_LOW`, `OPTIONAL_FEATURE_UNAVAILABLE_LOW`

## Common Operations

### Resume Failed Jobs
```python
# Resume all failed mining jobs
resumed_count = await orchestrator.resume_failed_jobs(job_type="mine")
```

### List Recent Jobs
```python
# Get last 50 jobs with status
jobs = await orchestrator.list_jobs(limit=50)
for job in jobs:
    print(f"{job['job_id']}: {job['latest_run']['status']}")
```

### Check LLM Usage
```python
stats = adapter.get_stats()
print(f"Active requests: {stats['active_requests']}/{stats['max_concurrent']}")
print(f"Memory usage: {stats['memory_usage']}%")
```

## Troubleshooting

### Database Issues
1. Check WAL mode is enabled: `PRAGMA journal_mode;`
2. Verify tables exist: `SELECT name FROM sqlite_master WHERE type='table';`
3. Check for lock contention in logs

### LLM Rate Limits
1. Check backoff status in logs
2. Reduce concurrency if needed
3. Monitor with `adapter.get_stats()`

### Memory Throttling
1. Check memory usage when throttled
2. Adjust threshold if needed (default 70%)
3. Close other applications

### Schema Validation Failures
1. Check error details in logs
2. Use repair functionality
3. Update schemas if structure changed

## Performance Tuning

### Concurrency Settings
Adjust based on your hardware:
```python
# Override auto-detection
adapter.max_concurrent = 6  # Custom limit
```

### Database Optimization
```sql
-- Ensure indexes exist
CREATE INDEX IF NOT EXISTS idx_job_run_status ON job_run(status);
CREATE INDEX IF NOT EXISTS idx_llm_request_job_run ON llm_request(job_run_id);
```

### Memory Management
- Monitor with `psutil.virtual_memory().percent`
- Adjust throttle threshold as needed
- Use checkpoint persistence for large jobs

## Migration from System 1

1. Run database migration:
   ```python
   python src/knowledge_system/database/migrations/system2_migration.py
   ```

2. Update imports:
   - Use `System2LLM` instead of `AnyLLM`
   - Use `System2Orchestrator` for job management
   - Use `get_system2_logger` for logging

3. Test with small batches first

4. Monitor logs for any issues

## Best Practices

1. **Always use job orchestration** for processing
2. **Set job_run_id** in logs for correlation
3. **Handle checkpoints** for long-running jobs
4. **Monitor metrics** for performance insights
5. **Use auto_process** for pipeline chaining
6. **Validate schemas** before LLM calls
7. **Check hardware tier** for concurrency tuning
