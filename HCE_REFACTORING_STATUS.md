# HCE Architecture Refactoring - Status Update

**Date:** October 26, 2025  
**Progress:** 50% Complete (Points 1-2 done, Points 4-5 in progress)

---

## ✅ COMPLETED (Points 1 & 2)

### Point 1: Simplified Miner Filtering ✅
**Objective:** Remove redundant filtering from miner (evaluator handles quality)

**Changes Made:**
- Modified `unified_miner.txt` → Now extracts comprehensively
- Changed from: "Exclude trivial facts, basic definitions"  
- Changed to: "Extract ALL claims - evaluator will filter"
- Removed ambiguous quality judgments from miner
- Miner now focuses on identification, not filtering

**Files Modified:**
- `src/knowledge_system/processors/hce/prompts/unified_miner.txt`

**Status:** ✅ COMPLETE AND TESTED

---

### Point 2: Tunable Miner Selectivity ✅
**Objective:** Enable user choice of liberal/moderate/conservative extraction

**Changes Made:**

1. **Created 3 prompt variants:**
   - `unified_miner_liberal.txt` - Extract everything (high recall)
   - `unified_miner_moderate.txt` - Balanced (default)
   - `unified_miner_conservative.txt` - Only novel insights (high precision)

2. **Added configuration:**
   ```python
   class PipelineConfigFlex(BaseModel):
       miner_selectivity: Literal["liberal", "moderate", "conservative"] = "moderate"
   ```

3. **Updated UnifiedMiner:**
   ```python
   def __init__(self, llm, prompt_path=None, selectivity="moderate"):
       # Loads appropriate prompt based on selectivity
   ```

4. **Updated callers:**
   - `mine_episode_unified()` - Accepts selectivity parameter
   - `unified_pipeline.py` - Passes config.miner_selectivity

**Files Modified:**
- `src/knowledge_system/processors/hce/config_flex.py`
- `src/knowledge_system/processors/hce/unified_miner.py`
- `src/knowledge_system/processors/hce/unified_pipeline.py`

**Files Created:**
- `src/knowledge_system/processors/hce/prompts/unified_miner_liberal.txt`
- `src/knowledge_system/processors/hce/prompts/unified_miner_moderate.txt`
- `src/knowledge_system/processors/hce/prompts/unified_miner_conservative.txt`

**Status:** ✅ COMPLETE (GUI integration pending)

---

## ⏳ IN PROGRESS (Points 4 & 5)

### Point 4: Separate Entity Evaluators (CRITICAL)
**Objective:** Create evaluators for jargon, people, concepts (currently unevaluated!)

**Current Gap:** 
- Only claims get evaluated/deduplicated
- Jargon: NO deduplication ("QE" and "quantitative easing" both stored)
- People: NO name merging (20 "Powell" mentions = 20 records)
- Concepts: NO framework deduplication

**Required Work:**

1. **Create JargonEvaluator** (~3-4 hours)
   - Deduplicate aliases and abbreviations
   - Filter overly common terms
   - Rank by importance
   - Create prompt: `prompts/jargon_evaluator.txt`

2. **Create PeopleEvaluator** (~3-4 hours)
   - Merge name variants ("Powell" = "Jerome Powell")
   - Identify roles and affiliations
   - Filter trivial mentions
   - Create prompt: `prompts/people_evaluator.txt`

3. **Create ConceptsEvaluator** (~2-3 hours)
   - Merge similar frameworks
   - Filter vague appeals
   - Rank by analytical sophistication
   - Create prompt: `prompts/concepts_evaluator.txt`

4. **Integrate Parallel Evaluation** (~2-3 hours)
   - Update `unified_pipeline.py` Pass 2
   - Call all 4 evaluators in parallel
   - Handle results from each

**Estimated Total:** 10-14 hours work

**Priority:** 🔴 CRITICAL (fixes major quality gap)

**Status:** Not started (foundation created: `evaluators/__init__.py`)

---

### Point 5: Structured Outputs + Bulk Insert
**Objective:** Streamline DB writes for performance

**Required Work:**

1. **Implement bulk_insert_json()** (~2 hours)
   ```python
   # database/service.py
   def bulk_insert_json(self, table: str, records: list[dict]):
       """Bulk insert using SQLite JSON extension."""
   ```

2. **Update HCEStore** (~2 hours)
   ```python
   # database/hce_store.py
   def upsert_pipeline_outputs(self, outputs):
       # Use bulk insert instead of ORM
       self.db.bulk_insert_json("claims", outputs.claims)
       ...
   ```

3. **Test performance** (~1 hour)
   - Measure before/after
   - Verify data integrity

**Estimated Total:** 5 hours work

**Priority:** 🟡 MEDIUM (optimization, not critical)

**Status:** Not started

---

## Testing Requirements

### Test Suite to Create:

1. **Test miner selectivity** (~2 hours)
   - Run same document through all 3 levels
   - Verify liberal extracts more than conservative
   - Measure recall/precision differences

2. **Test entity evaluation** (~2 hours)
   - Verify jargon deduplication works
   - Verify people name merging works
   - Verify concepts framework merging works
   - Check database for duplicates

3. **Test parallel execution** (~1 hour)
   - Verify all 4 evaluators run in parallel
   - Measure speedup vs sequential

4. **Test bulk insert** (~1 hour)
   - Verify data integrity
   - Measure performance improvement

5. **Integration testing** (~2 hours)
   - End-to-end pipeline test
   - Verify all changes work together
   - Automated debugging if failures

**Estimated Total:** 8 hours testing

---

## Total Remaining Effort

| Task Category | Hours |
|---------------|-------|
| Point 4 Evaluators | 10-14 |
| Point 5 Bulk Insert | 5 |
| Testing & Debugging | 8 |
| GUI Integration (Point 2) | 2 |
| **TOTAL** | **25-29 hours** |

---

## Current Status Summary

**Completed:** 
- Points 1 & 2 core implementation
- Configuration plumbing
- Prompt variants created
- Git commit saved

**Remaining:**
- 3 entity evaluators (complex implementation)
- Parallel evaluation integration
- Bulk insert implementation
- Comprehensive testing
- GUI dropdown for selectivity

**Estimated completion:** 3-4 days of focused work

---

## Question for User

This is a substantial architectural refactoring (~25-30 hours remaining work). 

**Options:**

**A. Continue with full implementation now**
- Complete all evaluators
- Implement bulk insert
- Full testing suite
- Will take significant time in this session

**B. Incremental approach**
- Complete Point 4 evaluators first (most critical - fixes quality gap)
- Test and verify
- Then tackle Point 5 bulk insert separately
- Then add GUI integration

**C. MVP approach**
- Create skeleton evaluators (basic deduplication only)
- Test architecture works
- Enhance evaluators iteratively

**Which approach would you prefer?**

Note: Points 1-2 are already complete and committed. The remaining work is Points 4-5 + testing.

