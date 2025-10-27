# HCE Store Cleanup - Completed

**Date:** October 27, 2025

## Summary

Successfully removed vestigial `hce_store.py` after porting all critical functionality to `ClaimStore`.

---

## Changes Made

### 1. ✅ Added FTS (Full-Text Search) Indexing to ClaimStore

**Location:** `src/knowledge_system/database/claim_store.py` (lines 139-171, 232-275)

**Features:**
- **Cleanup FTS indexes** before re-indexing (prevents duplicates)
- **Index claims** in `claims_fts` table for fast search
- **Index evidence quotes** in `evidence_fts` table for quote search
- **Support both episode and non-episode sources** (different cleanup strategies)

**Implementation:**
```python
# Clear old FTS entries for clean re-indexing
conn = self.db_service.engine.raw_connection()
cur = conn.cursor()

if source_type == 'episode':
    cur.execute("DELETE FROM claims_fts WHERE episode_id = ?", (episode_id,))
    cur.execute("DELETE FROM evidence_fts WHERE episode_id = ?", (episode_id,))
else:
    cur.execute("DELETE FROM claims_fts WHERE source_id = ?", (source_id,))
    cur.execute("DELETE FROM evidence_fts WHERE source_id = ?", (source_id,))

# Index claim text
cur.execute(
    "INSERT INTO claims_fts(claim_id, source_id, episode_id, canonical, claim_type) VALUES(?, ?, ?, ?, ?)",
    (global_claim_id, source_id, episode_id, claim_data.canonical, claim_data.claim_type)
)

# Index evidence quotes
for evidence in claim_data.evidence:
    cur.execute(
        "INSERT INTO evidence_fts(claim_id, source_id, episode_id, quote) VALUES(?, ?, ?, ?)",
        (global_claim_id, source_id, episode_id, evidence.quote)
    )
```

---

### 2. ✅ Added Milestones Storage to ClaimStore

**Location:** `src/knowledge_system/database/claim_store.py` (lines 112-137)

**Features:**
- **Store chapter/section markers** with timestamps
- **Upsert logic** - creates new or updates existing milestones
- **Episode navigation** - provides structure for long-form content

**Implementation:**
```python
if hasattr(outputs, 'milestones') and outputs.milestones:
    for milestone_data in outputs.milestones:
        milestone = session.query(Milestone).filter_by(
            episode_id=episode_id,
            milestone_id=milestone_data.milestone_id,
        ).first()
        
        if not milestone:
            milestone = Milestone(
                episode_id=episode_id,
                milestone_id=milestone_data.milestone_id,
                start_time=milestone_data.t0,
                end_time=milestone_data.t1,
                summary=milestone_data.summary,
            )
            session.add(milestone)
        else:
            # Update existing
            milestone.start_time = milestone_data.t0
            milestone.end_time = milestone_data.t1
            milestone.summary = milestone_data.summary
```

---

### 3. ✅ Deleted hce_store.py

**File Removed:** `src/knowledge_system/database/hce_store.py` (331 lines)

**Reason:** Completely superseded by `ClaimStore` with enhanced features:
- Better normalization (no JSON fields for external_ids, aliases)
- Global claim IDs (claim-first architecture)
- Source attribution (claims reference sources, not vice versa)
- Now includes FTS and milestones support

---

### 4. ✅ Removed Unused Import

**File:** `src/knowledge_system/core/system2_orchestrator_mining.py`

**Change:** Removed `from ..database.hce_store import HCEStore` (line 8)

**Status:** No remaining references to `HCEStore` in codebase

---

## Verification

✅ **No linter errors** in modified files  
✅ **No remaining imports** of `hce_store` anywhere  
✅ **All functionality preserved** in ClaimStore  
✅ **Documentation updated** in SUMMARIZATION_FLOW_ANALYSIS.md

---

## Benefits

1. **Cleaner codebase** - One storage layer instead of two
2. **No duplicate code** - Single source of truth for HCE storage
3. **Better maintainability** - All storage logic in one well-structured class
4. **Enhanced features** - FTS and milestones now in the claim-centric schema
5. **Future-proof** - Claim-first architecture ready for cross-source claim linking

---

## Impact on Existing Functionality

**None.** The ClaimStore was already being used exclusively by the mining pipeline. This change only:
- Removes dead code
- Adds missing features to the active code path
- Improves code organization

---

## Next Steps (from SUMMARIZATION_FLOW_ANALYSIS.md)

Remaining vestigial code to clean up:
1. Remove duplicate `EnhancedSummarizationWorker` from `processing_workers.py`
2. Remove unused `self.coordinator` from `System2Orchestrator.__init__()`
3. Refactor or remove `IntelligentProcessingCoordinator` (batch processing)

Critical enhancements needed:
1. Add YouTube metadata to `EpisodeBundle` and HCE prompts
2. Add database verification before declaring success
3. Fix progress indicators to show real verification step
4. Enhance markdown output with YouTube metadata and claim scores

