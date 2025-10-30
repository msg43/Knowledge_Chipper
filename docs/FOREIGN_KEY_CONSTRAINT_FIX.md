# Foreign Key Constraint and Schema Validation Fixes

**Date**: 2025-10-30  
**Issue**: Foreign key constraint failures when storing evidence spans, and schema validation errors for flagship evaluator output

## Problems Identified

### 1. Schema Validation Error
**Error Message**:
```
Schema validation failed for flagship_output: 'good' is not one of ['high', 'medium', 'low']
```

**Root Cause**: The flagship evaluator LLM was returning `'good'` for the `overall_quality` field, but the JSON schema only allows `['high', 'medium', 'low']`.

### 2. Foreign Key Constraint Failure
**Error Message**:
```
(sqlite3.IntegrityError) FOREIGN KEY constraint failed
[SQL: INSERT INTO evidence_spans (claim_id, segment_id, sequence, start_time, end_time, quote, ...) VALUES (?, ?, ?, ?, ?, ?, ...)]
[parameters: ('Steve Bannon_ Silicon Valley Is Turning Us Into 'Digital Serfs'_vvj_J2tB2Ag_claim_0000', 'seg_0051', 0, '00:51', '00:52', ...)]
```

**Root Causes**:
1. **Segments not stored**: The `ClaimStore.upsert_pipeline_outputs` method was storing claims and evidence spans, but segments were never being stored in the database first
2. **Segment ID mismatch**: Evidence spans referenced `segment_id='seg_0051'`, but the segments table uses fully qualified IDs like `episode_id_seg_0051`

## Solutions Implemented

### 1. Fixed Schema Validation (schema_validator.py)

Added automatic repair logic for invalid `overall_quality` values:

```python
# Repair invalid overall_quality values
if "summary_assessment" in repaired and isinstance(repaired["summary_assessment"], dict):
    quality = repaired["summary_assessment"].get("overall_quality")
    valid_qualities = ["high", "medium", "low"]
    
    if quality not in valid_qualities:
        # Map common invalid values to valid ones
        quality_map: dict[str, str] = {
            "good": "high",
            "excellent": "high",
            "great": "high",
            "fair": "medium",
            "average": "medium",
            "moderate": "medium",
            "poor": "low",
            "bad": "low",
            "weak": "low",
            "no_claims": "low",
            "error": "low",
            "unknown": "medium",
        }
        # Ensure quality is a string before using it as a key
        quality_str = str(quality) if quality is not None else "unknown"
        repaired["summary_assessment"]["overall_quality"] = quality_map.get(
            quality_str, "medium"
        )
```

**File**: `src/knowledge_system/processors/hce/schema_validator.py`  
**Lines**: 440-468

### 2. Added Segment Storage (claim_store.py)

Created a new method `store_segments()` that must be called before `upsert_pipeline_outputs()`:

```python
def store_segments(
    self,
    episode_id: str,
    segments: list,
) -> None:
    """
    Store segments for an episode before storing claims.
    
    This must be called before upsert_pipeline_outputs to ensure
    foreign key constraints are satisfied when storing evidence spans.
    """
    with self.db_service.get_session() as session:
        # Delete existing segments for this episode
        session.query(Segment).filter_by(episode_id=episode_id).delete()
        
        # Store new segments
        for i, segment in enumerate(segments):
            # Generate fully qualified segment_id (episode_id + segment_id)
            segment_id = f"{episode_id}_{segment.segment_id}"
            
            db_segment = Segment(
                segment_id=segment_id,
                episode_id=episode_id,
                speaker=segment.speaker,
                start_time=segment.t0,
                end_time=segment.t1,
                text=segment.text,
                topic_guess=getattr(segment, "topic_guess", None),
                sequence=i,
            )
            session.add(db_segment)
        
        session.commit()
```

**File**: `src/knowledge_system/database/claim_store.py`  
**Lines**: 56-94

### 3. Updated Evidence Span Storage (claim_store.py)

Modified evidence span storage to use fully qualified segment IDs:

```python
for seq, evidence in enumerate(claim_data.evidence):
    # Generate fully qualified segment_id (episode_id + segment_id)
    fully_qualified_segment_id = None
    if evidence.segment_id and episode_id:
        fully_qualified_segment_id = f"{episode_id}_{evidence.segment_id}"
    
    evidence_span = EvidenceSpan(
        claim_id=global_claim_id,
        segment_id=fully_qualified_segment_id,
        sequence=seq,
        start_time=evidence.t0,
        end_time=evidence.t1,
        quote=evidence.quote,
        context_start_time=evidence.context_t0,
        context_end_time=evidence.context_t1,
        context_text=evidence.context_text,
        context_type=evidence.context_type,
    )
    session.add(evidence_span)
```

**File**: `src/knowledge_system/database/claim_store.py`  
**Lines**: 297-316

### 4. Updated Mining Orchestrator (system2_orchestrator_mining.py)

Modified the mining orchestrator to store segments before storing claims:

```python
# Use ClaimStore for claim-centric storage
from ..database.claim_store import ClaimStore

claim_store = ClaimStore(orchestrator.db_service)

# CRITICAL: Store segments BEFORE storing claims
# This ensures foreign key constraints are satisfied when storing evidence spans
claim_store.store_segments(episode_id, segments)
logger.info(f"💾 Stored {len(segments)} segments for episode {episode_id}")

claim_store.upsert_pipeline_outputs(
    pipeline_outputs,
    source_id=source_id,
    source_type="episode",
    episode_title=Path(file_path).stem,
)
```

**File**: `src/knowledge_system/core/system2_orchestrator_mining.py`  
**Lines**: 284-296

## Database Schema Context

The `segments` table has the following structure:

```sql
CREATE TABLE IF NOT EXISTS segments (
    segment_id TEXT PRIMARY KEY,  -- Fully qualified: "episode_id_seg_0001"
    episode_id TEXT NOT NULL,
    speaker TEXT,
    start_time TEXT,
    end_time TEXT,
    text TEXT NOT NULL,
    topic_guess TEXT,
    sequence INTEGER,
    created_at DATETIME DEFAULT (datetime('now')),
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);
```

The `evidence_spans` table references segments:

```sql
CREATE TABLE IF NOT EXISTS evidence_spans (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    segment_id TEXT,  -- References segments.segment_id
    sequence INTEGER NOT NULL,
    start_time TEXT,
    end_time TEXT,
    quote TEXT,
    context_start_time TEXT,
    context_end_time TEXT,
    context_text TEXT,
    context_type TEXT DEFAULT 'exact',
    page_number INTEGER,
    paragraph_number INTEGER,
    created_at DATETIME DEFAULT (datetime('now')),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (segment_id) REFERENCES segments(segment_id) ON DELETE SET NULL
);
```

## Testing

The fixes ensure:
1. ✅ Schema validation errors are automatically repaired
2. ✅ Segments are stored before claims
3. ✅ Segment IDs are fully qualified to match database schema
4. ✅ Foreign key constraints are satisfied
5. ✅ Evidence spans correctly reference stored segments

## Impact

- **No breaking changes**: Existing code continues to work
- **Backward compatible**: Old segment IDs are automatically qualified
- **Robust**: Schema validation now handles common LLM output variations
- **Correct**: Foreign key relationships are properly maintained

## Files Modified

1. `src/knowledge_system/processors/hce/schema_validator.py`
2. `src/knowledge_system/database/claim_store.py`
3. `src/knowledge_system/core/system2_orchestrator_mining.py`

## Related Issues

- Schema validation: `flagship_output.v1.json` defines valid enum values
- Segment storage: Previously segments were only created in memory, not persisted
- ID format: Segments need globally unique IDs to support multi-episode databases

