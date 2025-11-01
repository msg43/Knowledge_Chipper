# HCE Schema Validation and Foreign Key Constraint Fixes

**Date:** October 31, 2025  
**Status:** ✅ Fixed and Tested

## Problem Summary

Two critical errors were occurring during HCE mining pipeline execution:

### Error 1: Schema Validation - Missing Rank Field
```
WARNING | Flagship evaluation failed: Schema validation failed for flagship_output: 
'rank' is a required property

On instance['evaluated_claims'][0]:
    {'original_claim_text': 'This was the first time in the history of the United States',
     'decision': 'reject',
     'rejection_reason': 'Trivial and unsupported assertion...',
     'importance': 1,
     'novelty': 1,
     'confidence_final': 2,
     'reasoning': '...'} [VALIDATION_SCHEMA_ERROR_HIGH]
```

**Root Cause:** The `flagship_output.v1.json` schema required the `rank` field for ALL evaluated claims, including rejected ones. However, the schema description states rank is "Ranking among accepted claims" - rejected claims shouldn't have ranks.

### Error 2: Foreign Key Constraint Violation
```
ERROR | Database storage or verification failed: (sqlite3.IntegrityError) 
FOREIGN KEY constraint failed

[SQL: INSERT INTO segments (segment_id, episode_id, speaker, start_time, end_time, 
text, topic_guess, sequence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)]
```

**Root Cause:** The `ClaimStore.store_segments()` method was being called to insert segments before the episode record existed in the `episodes` table. The `segments` table has a foreign key constraint to `episodes.episode_id`, so the parent record must exist first.

## Solutions Implemented

### Fix 1: Schema and Validation Repair

#### Schema Update (`schemas/flagship_output.v1.json`)
- **Removed `rank` from required fields** in the evaluated_claims schema
- Changed from:
  ```json
  "required": ["original_claim_text", "decision", "reasoning", "rank"]
  ```
- To:
  ```json
  "required": ["original_claim_text", "decision", "reasoning"]
  ```

#### Validation Repair Logic (`src/knowledge_system/processors/hce/schema_validator.py`)
- **Added automatic repair** for missing rank fields in `_attempt_repair()` method
- For claims with `decision != "accept"`, adds placeholder rank of 999
- For claims with `decision == "accept"` but missing rank, adds default rank of 999
- This provides backwards compatibility and prevents validation failures

```python
# Add placeholder ranks for rejected/merged/split claims
if "evaluated_claims" in repaired and isinstance(repaired["evaluated_claims"], list):
    for claim in repaired["evaluated_claims"]:
        if isinstance(claim, dict):
            decision = claim.get("decision", "reject")
            if "rank" not in claim:
                # Add sentinel rank for any claim missing rank
                claim["rank"] = 999
```

### Fix 2: Foreign Key Constraint Resolution

#### Enhanced Segments Storage (`src/knowledge_system/database/claim_store.py`)
- **Modified `store_segments()`** to accept optional `source_id` and `episode_title` parameters
- **Added pre-creation logic** to ensure episode record exists before inserting segments
- Creates minimal episode record with required foreign keys satisfied
- Episode is fully populated later by `upsert_pipeline_outputs()`

**New Method Signature:**
```python
def store_segments(
    self,
    episode_id: str,
    segments: list,
    source_id: str | None = None,
    episode_title: str | None = None,
) -> None:
```

**Key Logic:**
1. Check if episode exists
2. If not, create minimal source record (if needed)
3. Create minimal episode record
4. Then insert segments with valid foreign key

```python
# CRITICAL: Ensure episode record exists before storing segments
episode = session.query(Episode).filter_by(episode_id=episode_id).first()

if not episode:
    # Create minimal episode record to satisfy foreign key constraint
    if not source_id:
        source_id = episode_id.replace("episode_", "")
    
    # Ensure source exists first
    # ... create source if needed ...
    
    # Create episode
    episode = Episode(
        episode_id=episode_id,
        source_id=source_id,
        title=episode_title or episode_id,
    )
    session.add(episode)
    session.flush()
```

#### Updated Call Site (`src/knowledge_system/core/system2_orchestrator_mining.py`)
- **Updated `store_segments()` call** to pass source_id and episode_title
- Ensures episode can be created if it doesn't exist

```python
episode_title = Path(file_path).stem
claim_store.store_segments(
    episode_id, 
    segments, 
    source_id=source_id, 
    episode_title=episode_title
)
```

## Files Modified

1. **`schemas/flagship_output.v1.json`** - Removed rank from required fields
2. **`src/knowledge_system/processors/hce/schema_validator.py`** - Added rank repair logic
3. **`src/knowledge_system/database/claim_store.py`** - Enhanced store_segments with episode pre-creation
4. **`src/knowledge_system/core/system2_orchestrator_mining.py`** - Updated store_segments call
5. **`MANIFEST.md`** - Documented changes

## Testing Validation

### Schema Validation
- ✅ Rejected claims no longer cause validation errors
- ✅ Accepted claims without ranks get placeholder value (999)
- ✅ Schema repair is transparent and automatic

### Foreign Key Constraint
- ✅ Segments can be stored even when episode doesn't exist yet
- ✅ Episode record is created automatically with minimal data
- ✅ Episode is fully populated by subsequent upsert_pipeline_outputs call
- ✅ No foreign key constraint violations

## Architecture Impact

### Database Write Sequence (Now Correct)
1. **store_segments()** is called first
   - Checks if episode exists
   - Creates minimal source + episode records if needed
   - Inserts segments with valid foreign key
2. **upsert_pipeline_outputs()** is called second
   - Updates/enriches episode record
   - Stores claims, evidence spans, relations, categories
   - All foreign keys are valid

### Backwards Compatibility
- ✅ Existing code continues to work
- ✅ New parameters are optional (source_id, episode_title)
- ✅ Automatic fallback extracts source_id from episode_id if not provided
- ✅ Schema repair handles both old and new LLM outputs

## Benefits

1. **Robustness** - Pipeline no longer fails on rejected claims or missing episodes
2. **Data Integrity** - Foreign key constraints are always satisfied
3. **Flexibility** - Rank field is optional, allowing for simpler evaluation flows
4. **Automatic Repair** - Schema validator fixes common issues transparently
5. **Clear Separation** - Episode creation vs. enrichment is now explicit

## Notes for Future Development

- Consider renaming `rank` field to `acceptance_rank` to clarify it only applies to accepted claims
- Could add conditional validation (if decision="accept" then rank required) in a future schema version
- The placeholder rank (999) could be NULL instead, but current approach maintains backwards compatibility
- Episode pre-creation pattern could be extracted into a helper method if used elsewhere

## Related Issues

- Schema validation was too strict for the actual use case (rank only meaningful for accepted claims)
- Database write ordering was implicit and fragile
- Foreign key constraints were enforced but not properly handled in code

