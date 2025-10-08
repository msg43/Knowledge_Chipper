# ADR-001: System 2 Architecture

## Status
Accepted

## Context
The Knowledge Chipper has grown from a simple transcription tool to a complex knowledge extraction pipeline. System 1's organic growth led to:
- Inconsistent error handling across components
- No centralized job tracking or resumability
- Uncontrolled LLM API usage leading to rate limits
- Limited observability into processing pipelines
- Schema drift between LLM calls

## Decision
We will implement System 2 architecture with the following core components:

1. **SQLite-first truth layer** with WAL mode for concurrent access
2. **Job orchestration** with checkpoint persistence for resumability
3. **Centralized LLM adapter** with hardware-aware concurrency limits
4. **Structured JSON logging** with error taxonomy
5. **Versioned JSON schemas** for all LLM inputs/outputs

## Consequences

### Positive
- **Improved reliability**: Jobs can resume from checkpoints after failures
- **Better observability**: Structured logs with correlation IDs enable tracing
- **Cost control**: LLM usage tracking and rate limiting prevent bill surprises
- **Consistent validation**: JSON schemas ensure data quality
- **Hardware optimization**: Concurrency tuned to hardware capabilities

### Negative
- **Migration complexity**: Existing data needs schema updates
- **Learning curve**: Developers must understand new patterns
- **Initial overhead**: More boilerplate for simple operations

### Neutral
- GUI reduced from 10+ tabs to exactly 7 focused tabs
- All LLM calls now go through central adapter
- Database becomes the source of truth (not memory)

## Implementation

### Phase 1: Database (Complete)
- Created `job`, `job_run`, `llm_request`, `llm_response` tables
- Added `updated_at` columns for optimistic locking
- Enabled WAL mode for better concurrency

### Phase 2: Orchestration (Complete)
- Implemented `System2Orchestrator` for job management
- Added checkpoint save/restore functionality
- Implemented auto-process chaining

### Phase 3: LLM Management (Complete)
- Created `LLMAdapter` with rate limiting
- Added memory-based throttling
- Implemented exponential backoff

### Phase 4: Observability (Complete)
- Implemented `System2Logger` with JSON output
- Added error code taxonomy
- Created metrics collection

### Phase 5: Validation (Complete)
- Created JSON schemas in `/schemas/`
- Implemented validation with repair
- Added schema versioning support

## Alternatives Considered

1. **Event sourcing**: Too complex for current needs
2. **Microservices**: Overkill for desktop application
3. **GraphQL API**: Not needed for single-user app
4. **NoSQL database**: SQLite sufficient and simpler

## References
- [SYSTEM_2_IMPLEMENTATION_GUIDE.md](../../docs/internal/SYSTEM_2_IMPLEMENTATION_GUIDE.md)
- [TECHNICAL_SPECIFICATIONS.md](../../TECHNICAL_SPECIFICATIONS.md)
- [OPERATIONS.md](../../OPERATIONS.md)
