# System 2 Operations Guide

This guide covers operational aspects of the Knowledge Chipper System 2 implementation.

## Table of Contents
1. [System Overview](#system-overview)
2. [Job Management](#job-management)
3. [Database Operations](#database-operations)
4. [Monitoring and Observability](#monitoring-and-observability)
5. [Troubleshooting](#troubleshooting)
6. [Performance Tuning](#performance-tuning)

## System Overview

System 2 introduces a job-based orchestration system with:
- **Database-backed state management**: All operations create persistent job records
- **Checkpoint/resume capability**: Jobs can be resumed from their last checkpoint
- **Hardware-aware concurrency**: System adapts to available resources
- **Structured error handling**: Error codes following severity taxonomy

### Key Components

1. **System2Orchestrator**: Central job execution engine
2. **LLMAdapter**: Manages all LLM API calls with concurrency control
3. **Job/JobRun tables**: Track job state and metrics
4. **Schema Validator**: Ensures data integrity with automatic repair

## Job Management

### Job Types

- `download`: Download media files from URLs
- `transcribe`: Generate transcripts from audio/video
- `mine`: Extract claims, people, jargon, and concepts
- `flagship`: Evaluate and rank extracted claims
- `upload`: Upload results to cloud storage
- `pipeline`: Full end-to-end processing

### Creating Jobs

```python
from knowledge_system.core.system2_orchestrator import System2Orchestrator, JobType

orchestrator = System2Orchestrator()

# Create a single job
job_id = orchestrator.create_job(
    JobType.TRANSCRIBE,
    input_id="video_123",
    config={"source": "youtube"},
    auto_process=True  # Chain to next stage automatically
)

# Execute the job
result = orchestrator.execute_job(job_id)
```

### Job States

Jobs progress through these states:
1. `queued`: Job created but not started
2. `running`: Job execution in progress (via JobRun)
3. `completed`: Job finished successfully
4. `failed`: Job encountered an error
5. `cancelled`: Job was cancelled by user

### Resuming Failed Jobs

```python
# Resume a job from its last checkpoint
result = orchestrator.resume_job(job_id)
```

## Database Operations

### Enable WAL Mode

System 2 uses SQLite with Write-Ahead Logging (WAL) for better concurrency:

```sql
PRAGMA journal_mode=WAL;
```

### Key Tables

1. **job**: High-level job records
   - `job_id`: Unique identifier
   - `job_type`: Type of processing
   - `status`: Current job state
   - `auto_process`: Whether to chain next job

2. **job_run**: Individual execution attempts
   - `run_id`: Unique run identifier
   - `job_id`: Parent job reference
   - `checkpoint_json`: Resume point data
   - `metrics_json`: Performance metrics

3. **llm_request/llm_response**: LLM API tracking
   - Full request/response logging
   - Token usage and costs
   - Latency measurements

### Database Queries

Monitor active jobs:
```sql
SELECT job_id, job_type, status, created_at 
FROM job 
WHERE status IN ('queued', 'running')
ORDER BY created_at DESC;
```

Check job metrics:
```sql
SELECT jr.run_id, jr.status, jr.metrics_json
FROM job_run jr
JOIN job j ON jr.job_id = j.job_id
WHERE j.job_type = 'mine'
AND jr.completed_at > datetime('now', '-1 day');
```

## Monitoring and Observability

### Structured Logging

System 2 uses structured logging with the `System2Logger`:

```python
from knowledge_system.logger_system2 import get_system2_logger

logger = get_system2_logger(__name__)
logger.set_context(
    job_run_id="run_123",
    component="miner",
    operation="extract_claims"
)

# Log with error code
logger.error(
    "Validation failed",
    error_code=ErrorCode.VALIDATION_SCHEMA_ERROR_HIGH,
    context={"schema": "miner_output.v1", "field": "claims"}
)

# Log metrics
logger.log_metric("claims_extracted", 42, tags={"tier": "A"})
```

### Log Files

- **Main log**: `logs/knowledge_system_s2.log`
- **Metrics log**: `logs/metrics.jsonl` (filtered for METRIC: and JOB_EVENT:)

### Error Codes

Error severity levels:
- **HIGH**: Immediate attention required (e.g., `DATABASE_CONNECTION_ERROR_HIGH`)
- **MEDIUM**: Degraded functionality (e.g., `API_RATE_LIMIT_ERROR_MEDIUM`)
- **LOW**: Minor issues (e.g., `CACHE_MISS_LOW`)

### Monitoring Queries

Active memory usage:
```python
# Check LLM adapter metrics
adapter = orchestrator.llm_adapter
metrics = adapter.get_metrics()
print(f"Total requests: {metrics['total_requests']}")
print(f"Memory throttle events: {metrics['memory_throttle_events']}")
```

## Troubleshooting

### Common Issues

1. **Job Stuck in Running State**
   - Check for zombie job runs
   - Verify the process is still active
   - Consider cancelling and resuming

2. **Memory Throttling**
   - Check system memory usage
   - Reduce concurrent worker count
   - Enable more aggressive throttling

3. **Schema Validation Failures**
   - Enable repair mode
   - Check schema version compatibility
   - Review error messages for specific fields

### Debug Mode

Enable debug logging:
```python
from knowledge_system.logger_system2 import setup_system2_logging

setup_system2_logging(
    log_level="DEBUG",
    enable_json=True  # For machine parsing
)
```

### Recovery Procedures

1. **Corrupt Database**
   ```bash
   # Backup current database
   cp knowledge_system.db knowledge_system.db.backup
   
   # Run integrity check
   sqlite3 knowledge_system.db "PRAGMA integrity_check;"
   
   # If needed, export and reimport
   sqlite3 knowledge_system.db .dump > backup.sql
   sqlite3 knowledge_system_new.db < backup.sql
   ```

2. **Failed Migration**
   ```python
   # Re-run migration manually
   from knowledge_system.database.migrations.system2_migration import migrate_to_system2
   from knowledge_system.database import DatabaseService
   
   db = DatabaseService()
   with db.get_session() as session:
       migrate_to_system2(session)
   ```

## Performance Tuning

### Hardware Tiers

System automatically detects hardware tier:
- **Consumer**: 2-4 cores, <8GB RAM
- **Prosumer**: 8 cores, 16GB RAM
- **Professional**: 12+ cores, 32GB RAM
- **Server**: 16+ cores, 64GB+ RAM

### Concurrency Settings

Adjust worker counts per tier:
```python
# Override hardware detection
from knowledge_system.core.llm_adapter import HARDWARE_TIERS

custom_tier = HARDWARE_TIERS["prosumer"]
custom_tier.mining_workers = 6  # Increase mining concurrency
```

### Memory Management

Configure memory thresholds:
```python
adapter.memory_monitor.threshold = 0.6  # Start throttling at 60%
adapter.memory_monitor.critical_threshold = 0.85  # Critical at 85%
```

### Batch Processing

Optimize batch sizes:
```python
# In orchestrator._process_mine()
batch_size = 10  # Process 10 segments at a time
```

### Database Optimization

1. **Enable auto-vacuum**:
   ```sql
   PRAGMA auto_vacuum = INCREMENTAL;
   ```

2. **Optimize queries**:
   ```sql
   ANALYZE;  -- Update query planner statistics
   ```

3. **Monitor database size**:
   ```bash
   # Check database file size
   ls -lh knowledge_system.db*
   
   # Vacuum if needed
   sqlite3 knowledge_system.db "VACUUM;"
   ```

## Best Practices

1. **Always use auto_process for pipelines** to ensure proper chaining
2. **Monitor checkpoint sizes** - large checkpoints can slow resume
3. **Set appropriate job timeouts** to prevent resource exhaustion
4. **Use structured logging** for better observability
5. **Regular database maintenance** - vacuum and analyze periodically
6. **Test recovery procedures** before production issues arise

## Emergency Procedures

### Stop All Processing
```python
# Cancel all running jobs
with db.get_session() as session:
    running_jobs = session.query(Job).filter_by(status="running").all()
    for job in running_jobs:
        job.status = "cancelled"
    session.commit()
```

### Reset System State
```python
# Clear all job history (careful!)
with db.get_session() as session:
    session.query(JobRun).delete()
    session.query(Job).delete()
    session.commit()
```

### Export Critical Data
```python
# Export claims before maintenance
import csv
with db.get_session() as session:
    claims = session.query(Claim).all()
    with open('claims_backup.csv', 'w') as f:
        writer = csv.writer(f)
        for claim in claims:
            writer.writerow([claim.claim_id, claim.canonical, claim.tier])
```
