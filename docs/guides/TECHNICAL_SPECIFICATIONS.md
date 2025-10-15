# Knowledge System Technical Specifications

## ID Format Specifications

### Preferred ID Flavor: **Custom Hybrid Format**

The system uses a **hybrid ID approach** combining deterministic and UUID elements:

#### **Primary ID Patterns**
```python
# Media Sources (YouTube videos)
media_id = video_id  # 11-character YouTube video ID (e.g., "dQw4w9WgXcQ")

# Episodes (HCE processing)
episode_id = f"ep_{video_id}_{timestamp}"  # e.g., "ep_dQw4w9WgXcQ_20250115"

# Transcripts
transcript_id = f"trans_{video_id}_{model}_{timestamp}"  # e.g., "trans_dQw4w9WgXcQ_whisper_large_20250115"

# Claims (HCE)
claim_id = f"claim_{episode_id}_{claim_hash}"  # e.g., "claim_ep_dQw4w9WgXcQ_20250115_abc123"

# Segments
segment_id = f"seg_{i:04d}"  # e.g., "seg_0001", "seg_0002"

# Files
file_id = f"{file_type}_{source_id}_{format}_{hash[:8]}"  # e.g., "transcript_dQw4w9WgXcQ_md_a1b2c3d4"

# Batch Jobs
job_id = f"{batch_id}_job_{i:04d}"  # e.g., "batch_20250115_job_0001"
batch_id = f"batch_{timestamp}_{hash[:8]}"  # e.g., "batch_20250115_a1b2c3d4"
```

#### **ID Generation Strategy**
- **Deterministic**: Same input → same ID (enables idempotent operations)
- **Hierarchical**: IDs contain relationship information
- **Collision-resistant**: Includes timestamps and hashes
- **Human-readable**: Contains meaningful prefixes and structure

#### **UUID Usage (Limited)**
```python
# Only for temporary/session IDs
session_id = str(uuid.uuid4())  # Bright Data sessions, validation sessions
correlation_id = str(uuid.uuid4())  # Cross-system correlation
```

## Batch Upsert Endpoint Specifications

### **Primary Endpoint**: `/api/v1/batch/upsert`

#### **Request Format**
```json
{
  "batch_id": "string",                    // Required: Batch identifier
  "operation_type": "string",              // Required: "episode", "claim", "evidence", "person", "concept", "jargon"
  "items": [                              // Required: Array of items to upsert
    {
      "id": "string",                     // Required: Item identifier
      "data": "object",                   // Required: Item data
      "metadata": {                       // Optional: Additional metadata
        "source": "string",               // Source system identifier
        "timestamp": "string",            // ISO8601 timestamp
        "version": "string"               // Data version
      }
    }
  ],
  "options": {                           // Optional: Processing options
    "validate_only": "boolean",          // Default: false
    "allow_partial": "boolean",          // Default: false
    "conflict_resolution": "string"      // "last_wins", "merge", "error" - Default: "last_wins"
  }
}
```

#### **Response Format**
```json
{
  "success": "boolean",
  "batch_id": "string",
  "processed_count": "integer",
  "created_count": "integer", 
  "updated_count": "integer",
  "skipped_count": "integer",
  "error_count": "integer",
  "errors": [                           // Array of error objects
    {
      "item_id": "string",
      "error_code": "string",
      "message": "string",
      "details": "object"
    }
  ],
  "results": [                          // Array of processed items
    {
      "id": "string",
      "status": "string",               // "created", "updated", "skipped", "error"
      "operation": "string"             // "insert", "update", "skip"
    }
  ],
  "processing_time_ms": "integer",
  "timestamp": "string"                 // ISO8601 timestamp
}
```

#### **HTTP Status Codes**
- **200 OK**: Batch processed successfully (may include individual errors)
- **400 Bad Request**: Invalid request format or validation errors
- **401 Unauthorized**: Authentication required
- **403 Forbidden**: Insufficient permissions
- **413 Payload Too Large**: Batch size exceeds limits
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server processing error
- **503 Service Unavailable**: Service temporarily unavailable

#### **Field-Specific Validation Rules**

##### **Episode Items**
```json
{
  "id": "string",                       // Required: episode_id format
  "data": {
    "episode_id": "string",            // Required: Must match id
    "video_id": "string",              // Required: 11-char YouTube ID
    "title": "string",                 // Required: Max 500 chars
    "recorded_at": "string",           // Required: ISO8601 timestamp
    "inserted_at": "string"            // Optional: ISO8601 timestamp
  }
}
```

##### **Claim Items**
```json
{
  "id": "string",                       // Required: claim_id format
  "data": {
    "episode_id": "string",            // Required: Valid episode_id
    "claim_id": "string",              // Required: Must match id
    "canonical": "string",             // Required: Non-empty claim text
    "claim_type": "string",            // Required: "factual", "causal", "normative", "forecast", "definition"
    "tier": "string",                  // Required: "A", "B", "C"
    "scores_json": "object",           // Required: {"importance": 0.0-10.0, "novelty": 0.0-10.0, "confidence": 0.0-10.0}
    "first_mention_ts": "string",      // Optional: ISO8601 timestamp
    "temporality_score": "integer",    // Optional: 1-5
    "temporality_confidence": "float", // Optional: 0.0-1.0
    "structured_categories_json": "array", // Optional: Array of category objects
    "upload_status": "string"          // Optional: "pending", "uploaded", "failed"
  }
}
```

##### **Evidence Span Items**
```json
{
  "id": "string",                       // Required: evidence span ID
  "data": {
    "episode_id": "string",            // Required: Valid episode_id
    "claim_id": "string",              // Required: Valid claim_id
    "span_id": "string",               // Required: Must match id
    "quote": "string",                 // Required: Non-empty evidence text
    "t0": "string",                    // Required: Start timestamp
    "t1": "string",                    // Required: End timestamp
    "segment_id": "string",            // Optional: Segment reference
    "immediate_context": "string",     // Optional: Immediate context
    "broader_context": "string",       // Optional: Broader context
    "relevance_score": "float",        // Optional: 0.0-1.0
    "confidence": "float"              // Optional: 0.0-1.0
  }
}
```

## Review Grid Column Specifications

### **Claim Review Grid**

#### **Core Columns**
| Column | Field | Type | Validation | Description |
|--------|-------|------|------------|-------------|
| **ID** | `claim_id` | String | Required, Format: `claim_*` | Unique claim identifier |
| **Episode** | `episode_id` | String | Required, Valid episode_id | Source episode |
| **Claim Text** | `canonical` | Text | Required, Min 10 chars, Max 5000 chars | The actual claim content |
| **Type** | `claim_type` | Enum | Required, One of: factual, causal, normative, forecast, definition | Classification of claim type |
| **Tier** | `tier` | Enum | Required, One of: A, B, C | Quality tier assignment |
| **Importance** | `scores_json.importance` | Float | Required, Range: 1.0-10.0 | Importance score |
| **Novelty** | `scores_json.novelty` | Float | Required, Range: 1.0-10.0 | Novelty score |
| **Confidence** | `scores_json.confidence` | Float | Required, Range: 1.0-10.0 | Confidence score |
| **Temporality** | `temporality_score` | Integer | Optional, Range: 1-5 | Time relevance score |
| **First Mention** | `first_mention_ts` | DateTime | Optional, ISO8601 format | When claim first appears |
| **Evidence Count** | `evidence_count` | Integer | Computed | Number of supporting evidence spans |
| **Upload Status** | `upload_status` | Enum | Optional, One of: pending, uploaded, failed | Cloud sync status |

#### **Validation Rules**
```yaml
claim_text:
  min_length: 10
  max_length: 5000
  required: true
  forbidden_patterns: ["[Error]", "[Failed]", "TODO", "FIXME"]

scores:
  importance:
    type: float
    range: [1.0, 10.0]
    required: true
  novelty:
    type: float
    range: [1.0, 10.0]
    required: true
  confidence:
    type: float
    range: [1.0, 10.0]
    required: true

temporality_score:
  type: integer
  range: [1, 5]
  enum: [1, 2, 3, 4, 5]
  meanings:
    1: "Immediate (hours/days)"
    2: "Short-term (weeks/months)"
    3: "Medium-term (months/years)"
    4: "Long-term (years/decades)"
    5: "Timeless (permanent truth)"
```

#### **Filtering & Sorting**
```yaml
filterable_columns:
  - claim_type
  - tier
  - upload_status
  - temporality_score

sortable_columns:
  - importance (descending default)
  - novelty (descending)
  - confidence (descending)
  - first_mention_ts (ascending)
  - claim_text (alphabetical)

searchable_columns:
  - canonical (full-text search)
  - claim_type
  - structured_categories_json
```

## Hardware Tier Specifications

### **Memory Pressure Setpoints**

#### **Target Memory Utilization**
```yaml
memory_pressure_thresholds:
  critical: 0.90    # 90% - Emergency stop processing
  warning: 0.80     # 80% - Reduce parallelization
  optimal: 0.70     # 70% - Target operating point
  safe: 0.60        # 60% - Normal operations
```

#### **Hardware Tier Configurations**

##### **Tier 1: M2/M3 Ultra (64GB+ RAM)**
```yaml
hardware_tier: "ultra"
memory_gb: 64
cpu_cores: 24
chip_type: "M2_Ultra" | "M3_Ultra"

model_config:
  primary_model: "qwen2.5:14b-instruct"
  model_ram_gb: 32.0
  optimization: "fp16"

worker_limits:
  max_parallel_downloads: 4
  max_parallel_mining: 8
  max_parallel_evaluation: 6
  max_parallel_transcription: 3
  max_parallel_voice_fingerprinting: 4

thread_limits:
  max_total_inference_threads: 36
  max_threads_per_worker: 6
  os_reserve_cores: 6

kv_cache_budget:
  stage_a_max_ctx: 4000
  stage_b_max_ctx: 8000
  kv_cache_4k_ctx_gb: 0.9
  kv_cache_8k_ctx_gb: 1.8
  max_concurrent_requests: 26  # Stage-A
  max_concurrent_requests: 13  # Stage-B

memory_allocation:
  model_weights: 32.0
  kv_cache_budget: 24.0
  system_overhead: 2.0
  available_headroom: 6.0
```

##### **Tier 2: M2/M3 Max (32GB+ RAM)**
```yaml
hardware_tier: "max"
memory_gb: 32
cpu_cores: 20
chip_type: "M2_Max" | "M3_Max"

model_config:
  primary_model: "qwen2.5:14b-instruct"
  model_ram_gb: 32.0
  optimization: "fp16"

worker_limits:
  max_parallel_downloads: 3
  max_parallel_mining: 6
  max_parallel_evaluation: 4
  max_parallel_transcription: 2
  max_parallel_voice_fingerprinting: 3

thread_limits:
  max_total_inference_threads: 30
  max_threads_per_worker: 5
  os_reserve_cores: 5

kv_cache_budget:
  stage_a_max_ctx: 4000
  stage_b_max_ctx: 6000
  kv_cache_4k_ctx_gb: 0.9
  kv_cache_6k_ctx_gb: 1.3
  max_concurrent_requests: 12  # Stage-A
  max_concurrent_requests: 8   # Stage-B

memory_allocation:
  model_weights: 32.0
  kv_cache_budget: 12.0
  system_overhead: 2.0
  available_headroom: 2.0
```

##### **Tier 3: M2/M3 Pro (16GB+ RAM)**
```yaml
hardware_tier: "pro"
memory_gb: 16
cpu_cores: 12
chip_type: "M2_Pro" | "M3_Pro"

model_config:
  primary_model: "qwen2.5:7b-instruct"
  model_ram_gb: 8.0
  optimization: "fp16"

worker_limits:
  max_parallel_downloads: 2
  max_parallel_mining: 4
  max_parallel_evaluation: 3
  max_parallel_transcription: 2
  max_parallel_voice_fingerprinting: 2

thread_limits:
  max_total_inference_threads: 20
  max_threads_per_worker: 4
  os_reserve_cores: 4

kv_cache_budget:
  stage_a_max_ctx: 3000
  stage_b_max_ctx: 4000
  kv_cache_3k_ctx_gb: 0.6
  kv_cache_4k_ctx_gb: 0.8
  max_concurrent_requests: 8   # Stage-A
  max_concurrent_requests: 6   # Stage-B

memory_allocation:
  model_weights: 8.0
  kv_cache_budget: 6.0
  system_overhead: 2.0
  available_headroom: 2.0
```

##### **Tier 4: Base Systems (<16GB RAM)**
```yaml
hardware_tier: "base"
memory_gb: 8
cpu_cores: 8
chip_type: "M2" | "M3"

model_config:
  primary_model: "qwen2.5:3b-instruct"
  model_ram_gb: 4.0
  optimization: "fp16"

worker_limits:
  max_parallel_downloads: 1
  max_parallel_mining: 2
  max_parallel_evaluation: 2
  max_parallel_transcription: 1
  max_parallel_voice_fingerprinting: 1

thread_limits:
  max_total_inference_threads: 12
  max_threads_per_worker: 3
  os_reserve_cores: 3

kv_cache_budget:
  stage_a_max_ctx: 2000
  stage_b_max_ctx: 3000
  kv_cache_2k_ctx_gb: 0.4
  kv_cache_3k_ctx_gb: 0.6
  max_concurrent_requests: 4   # Stage-A
  max_concurrent_requests: 3   # Stage-B

memory_allocation:
  model_weights: 4.0
  kv_cache_budget: 3.0
  system_overhead: 1.0
  available_headroom: 1.0
```

## Error Code Taxonomy

### **Error Code Structure**
```
{COMPONENT}_{OPERATION}_{TYPE}_{SEVERITY}

Components: CONFIG, FILE, PROCESS, API, DB, VALIDATION, NETWORK, RESOURCE
Operations: CREATE, READ, UPDATE, DELETE, VALIDATE, EXTRACT, TRANSFORM, LOAD
Types: ERROR, WARNING, INFO, DEBUG
Severity: CRITICAL, HIGH, MEDIUM, LOW
```

### **Primary Error Codes**

#### **Configuration Errors**
```yaml
CONFIG_LOAD_ERROR_CRITICAL:
  code: "CONFIG_LOAD_ERROR_CRITICAL"
  message: "Critical configuration file cannot be loaded"
  severity: "critical"
  resolution: "Check file permissions and syntax"

CONFIG_VALIDATE_ERROR_HIGH:
  code: "CONFIG_VALIDATE_ERROR_HIGH"
  message: "Configuration validation failed"
  severity: "high"
  resolution: "Fix configuration values per schema"

CONFIG_MISSING_ERROR_HIGH:
  code: "CONFIG_MISSING_ERROR_HIGH"
  message: "Required configuration missing"
  severity: "high"
  resolution: "Provide required configuration values"
```

#### **Processing Errors**
```yaml
PROCESS_TRANSCRIPTION_ERROR_HIGH:
  code: "PROCESS_TRANSCRIPTION_ERROR_HIGH"
  message: "Audio transcription failed"
  severity: "high"
  resolution: "Check audio file format and quality"

PROCESS_SUMMARIZATION_ERROR_HIGH:
  code: "PROCESS_SUMMARIZATION_ERROR_HIGH"
  message: "Text summarization failed"
  severity: "high"
  resolution: "Check input text and LLM configuration"

PROCESS_HCE_MINING_ERROR_HIGH:
  code: "PROCESS_HCE_MINING_ERROR_HIGH"
  message: "HCE mining stage failed"
  severity: "high"
  resolution: "Check input format and model availability"

PROCESS_HCE_EVALUATION_ERROR_HIGH:
  code: "PROCESS_HCE_EVALUATION_ERROR_HIGH"
  message: "HCE evaluation stage failed"
  severity: "high"
  resolution: "Check mining results and model configuration"

PROCESS_VOICE_FINGERPRINTING_ERROR_MEDIUM:
  code: "PROCESS_VOICE_FINGERPRINTING_ERROR_MEDIUM"
  message: "Voice fingerprinting failed"
  severity: "medium"
  resolution: "Check audio quality and speaker separation"
```

#### **API Errors**
```yaml
API_LLM_ERROR_HIGH:
  code: "API_LLM_ERROR_HIGH"
  message: "LLM API call failed"
  severity: "high"
  resolution: "Check API key and model availability"

API_YOUTUBE_ERROR_HIGH:
  code: "API_YOUTUBE_ERROR_HIGH"
  message: "YouTube API call failed"
  severity: "high"
  resolution: "Check URL validity and API quotas"

API_RATE_LIMIT_ERROR_MEDIUM:
  code: "API_RATE_LIMIT_ERROR_MEDIUM"
  message: "API rate limit exceeded"
  severity: "medium"
  resolution: "Wait for rate limit reset or reduce request frequency"

API_AUTH_ERROR_HIGH:
  code: "API_AUTH_ERROR_HIGH"
  message: "API authentication failed"
  severity: "high"
  resolution: "Check API credentials and permissions"
```

#### **Validation Errors**
```yaml
VALIDATION_INPUT_ERROR_MEDIUM:
  code: "VALIDATION_INPUT_ERROR_MEDIUM"
  message: "Input validation failed"
  severity: "medium"
  resolution: "Check input format and required fields"

VALIDATION_SCHEMA_ERROR_HIGH:
  code: "VALIDATION_SCHEMA_ERROR_HIGH"
  message: "JSON schema validation failed"
  severity: "high"
  resolution: "Fix data structure per schema requirements"

VALIDATION_URL_ERROR_LOW:
  code: "VALIDATION_URL_ERROR_LOW"
  message: "URL format validation failed"
  severity: "low"
  resolution: "Check URL format and accessibility"
```

#### **Resource Errors**
```yaml
RESOURCE_MEMORY_ERROR_CRITICAL:
  code: "RESOURCE_MEMORY_ERROR_CRITICAL"
  message: "Insufficient memory for operation"
  severity: "critical"
  resolution: "Reduce parallelization or upgrade hardware"

RESOURCE_DISK_ERROR_HIGH:
  code: "RESOURCE_DISK_ERROR_HIGH"
  message: "Insufficient disk space"
  severity: "high"
  resolution: "Free up disk space or change storage location"

RESOURCE_GPU_ERROR_MEDIUM:
  code: "RESOURCE_GPU_ERROR_MEDIUM"
  message: "GPU operation failed"
  severity: "medium"
  resolution: "Check GPU drivers or fallback to CPU"
```

#### **Database Errors**
```yaml
DB_CONNECTION_ERROR_HIGH:
  code: "DB_CONNECTION_ERROR_HIGH"
  message: "Database connection failed"
  severity: "high"
  resolution: "Check database file and permissions"

DB_QUERY_ERROR_MEDIUM:
  code: "DB_QUERY_ERROR_MEDIUM"
  message: "Database query failed"
  severity: "medium"
  resolution: "Check query syntax and data integrity"

DB_MIGRATION_ERROR_HIGH:
  code: "DB_MIGRATION_ERROR_HIGH"
  message: "Database migration failed"
  severity: "high"
  resolution: "Check migration scripts and database state"
```

### **Error Response Format**
```json
{
  "error": {
    "code": "string",                    // Machine-readable error code
    "message": "string",                 // Human-readable error message
    "severity": "string",                // "critical", "high", "medium", "low"
    "component": "string",               // Component where error occurred
    "operation": "string",               // Operation being performed
    "context": {                         // Additional context information
      "timestamp": "string",             // ISO8601 timestamp
      "request_id": "string",            // Request correlation ID
      "user_id": "string",               // User identifier (if applicable)
      "resource_id": "string",           // Resource identifier (if applicable)
      "details": "object"                // Component-specific details
    },
    "resolution": "string",              // Suggested resolution steps
    "retry_after": "integer",            // Seconds to wait before retry (if applicable)
    "documentation_url": "string"        // Link to relevant documentation
  }
}
```

### **Logging Patterns**
```yaml
log_format: "{timestamp} [{level}] {component}.{operation} - {message} [{error_code}] {context}"

log_levels:
  CRITICAL: "System cannot continue operation"
  ERROR: "Operation failed but system can continue"
  WARNING: "Potential issue detected"
  INFO: "Normal operation information"
  DEBUG: "Detailed debugging information"

structured_logging:
  enabled: true
  fields:
    - timestamp
    - level
    - component
    - operation
    - error_code
    - message
    - context
    - duration
    - user_id
    - request_id
```

This comprehensive technical specification provides the exact requirements for ID formats, API endpoints, validation rules, hardware configurations, and error handling that will ensure tight alignment across the Knowledge System implementation.
