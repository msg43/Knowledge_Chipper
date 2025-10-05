# ADR-001: System 2 Architecture

## Status
Accepted

## Context
The original Knowledge Chipper system (System 1) had grown organically with:
- In-memory state management limiting reliability
- No systematic error recovery or checkpointing
- Limited observability into processing pipelines
- Resource usage not adapted to hardware capabilities

## Decision
We will implement System 2 architecture with:
1. **SQLite-based job orchestration** for persistent state management
2. **Checkpoint/resume capability** for fault tolerance
3. **Hardware-aware concurrency control** for resource optimization
4. **Structured logging with error codes** for observability

## Consequences

### Positive
- **Reliability**: Jobs can resume after failures
- **Observability**: Full audit trail of all operations
- **Scalability**: Adapts to available hardware resources
- **Maintainability**: Clear separation of concerns

### Negative
- **Complexity**: More moving parts than System 1
- **Storage**: Database grows with job history
- **Migration**: Requires one-time migration step

### Neutral
- Performance impact minimal due to SQLite efficiency
- Learning curve for operators understanding job states

## Implementation
- New tables: `job`, `job_run`, `llm_request`, `llm_response`
- `System2Orchestrator` class manages job lifecycle
- `LLMAdapter` centralizes all model calls
- JSON schemas enforce data contracts
