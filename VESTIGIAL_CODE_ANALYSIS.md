# Vestigial Code Analysis - HCE Summarization

## Summary

Investigation triggered by discovering "Relations mapped: 0" and "Contradictions detected: 0" statistics in the GUI revealed **multiple layers of vestigial code** from pre-unified-pipeline architecture.

## Findings

### 1. ✅ FIXED: Vestigial Statistics Display

**Issue:** GUI displayed statistics for unimplemented features
- "Relations mapped: 0"
- "Contradictions detected: 0"

**Evidence:**
- `unified_pipeline.py` line 840: `relations=[],  # Relations not implemented in unified pipeline yet`
- `relations.py` line 68: `# Currently disabled - return empty list`
- `RelationMiner` class exists but is never invoked

**Resolution:** 
- Removed from `summarization_tab.py` statistics display
- Removed from `batch_processing.py` aggregation
- Updated CHANGELOG.md

**Files Changed:**
- `src/knowledge_system/gui/tabs/summarization_tab.py`
- `src/knowledge_system/utils/batch_processing.py`
- `CHANGELOG.md`

---

### 2. ⚠️ IDENTIFIED: Unused Old Extraction Modules

**Pre-Unified Pipeline Architecture:**
The system previously had separate, single-purpose extractors that have been replaced by the unified pipeline:

| Old Module | Purpose | Status |
|------------|---------|--------|
| `people.py` | Extract person mentions | **Not imported anywhere** |
| `glossary.py` | Extract jargon/glossary | **Not imported anywhere** |
| `concepts.py` | Extract mental models | **Not imported anywhere** |
| `skim.py` | Generate quick summaries | **Not imported anywhere** |

**Current Architecture:**
All these functions are now handled by:
- `unified_miner.py` - Single-pass extraction of ALL entity types
- `unified_pipeline.py` - Orchestrates mining + evaluation + summarization

**Evidence:**
```bash
# These modules are exported in __init__.py but never imported:
grep -r "from.*hce import people" src/  # No results
grep -r "from.*hce import glossary" src/  # No results
grep -r "from.*hce import concepts" src/  # No results
grep -r "from.*hce import skim" src/  # No results
```

**Verification:**
- ✅ Only self-references found (within their own files)
- ✅ Not imported by `System2Orchestrator`
- ✅ Not imported by `UnifiedHCEPipeline`
- ✅ Not imported by any GUI tabs
- ✅ Not used in any tests

---

### 3. ⚠️ IDENTIFIED: Unused Prompt Files

**Old Two-Tier Evaluation System:**
These prompt files suggest a previous architecture with separate "high" and "low" quality evaluators:

```
prompts/jargon_judge_high.txt       # Not referenced in code
prompts/jargon_judge_low.txt        # Not referenced in code
prompts/mental_models_judge_high.txt # Not referenced in code
prompts/mental_models_judge_low.txt  # Not referenced in code
prompts/people_judge_high.txt        # Not referenced in code
prompts/people_judge_low.txt         # Not referenced in code
```

**Current Architecture:**
Single unified evaluators:
- `prompts/jargon_evaluator.txt` - Used by `evaluators/jargon_evaluator.py`
- `prompts/concepts_evaluator.txt` - Used by `evaluators/concepts_evaluator.py`
- `prompts/people_evaluator.txt` - Used by `evaluators/people_evaluator.py`
- `prompts/flagship_evaluator.txt` - Used by `flagship_evaluator.py`

**Evidence:**
```bash
grep -r "judge_high\|judge_low" src/knowledge_system/processors/hce/
# No matches found
```

---

### 4. ⚠️ IDENTIFIED: Unused Standalone Detection Prompts

These prompts were used by the old standalone extractors:

```
prompts/people_detect.txt       # Used by people.py (unused module)
prompts/people_disambiguate.txt # Used by people.py (unused module)
prompts/concepts_detect.txt     # Used by concepts.py (unused module)
prompts/glossary_detect.txt     # Used by glossary.py (unused module)
prompts/skim.txt                # Used by skim.py (unused module)
prompts/contradiction.txt       # Not referenced anywhere
```

**Current Architecture:**
All detection is handled by unified miner prompts:
- `prompts/unified_miner.txt`
- `prompts/unified_miner_moderate.txt`
- `prompts/unified_miner_liberal.txt`
- `prompts/unified_miner_conservative.txt`
- `prompts/unified_miner_transcript_own.txt`
- `prompts/unified_miner_transcript_third_party.txt`
- `prompts/unified_miner_document.txt`

---

## Architecture Evolution

### Old Architecture (Pre-2025-10)
```
Episode
  ↓
Separate Extractors (sequential):
  ├─> PeopleExtractor → people_detect.txt
  ├─> GlossaryExtractor → glossary_detect.txt
  ├─> ConceptExtractor → concepts_detect.txt
  └─> ClaimExtractor → (separate process)
       ↓
Two-Tier Evaluation:
  ├─> judge_high.txt (for high-confidence items)
  └─> judge_low.txt (for low-confidence items)
       ↓
Separate Relation Mining:
  └─> RelationMiner → contradiction.txt
```

### Current Architecture (Post-2025-10)
```
Episode
  ↓
UnifiedMiner (single pass, parallel):
  └─> unified_miner_*.txt
       ↓
       Extracts ALL entity types simultaneously:
       ├─> Claims
       ├─> People
       ├─> Jargon
       └─> Mental Models
       ↓
Unified Evaluators (parallel):
  ├─> flagship_evaluator.txt (claims)
  ├─> people_evaluator.txt
  ├─> jargon_evaluator.txt
  └─> concepts_evaluator.txt
       ↓
Relations: NOT IMPLEMENTED (explicitly disabled)
```

**Benefits:**
- ✅ 70% fewer LLM calls
- ✅ 3-8x faster (parallel processing)
- ✅ More consistent extraction (single context)
- ✅ Simpler codebase (one pipeline)

---

## Recommendations

### Option 1: Clean Removal (Recommended)
**Move to `_deprecated/` folder:**
```bash
# Old extraction modules
src/knowledge_system/processors/hce/people.py
src/knowledge_system/processors/hce/glossary.py
src/knowledge_system/processors/hce/concepts.py
src/knowledge_system/processors/hce/skim.py

# Unused prompts
src/knowledge_system/processors/hce/prompts/people_detect.txt
src/knowledge_system/processors/hce/prompts/people_disambiguate.txt
src/knowledge_system/processors/hce/prompts/concepts_detect.txt
src/knowledge_system/processors/hce/prompts/glossary_detect.txt
src/knowledge_system/processors/hce/prompts/skim.txt
src/knowledge_system/processors/hce/prompts/contradiction.txt
src/knowledge_system/processors/hce/prompts/*_judge_high.txt
src/knowledge_system/processors/hce/prompts/*_judge_low.txt
```

**Update:**
- `src/knowledge_system/processors/hce/__init__.py` - Remove exports
- `MANIFEST.md` - Document deprecation

**Rationale:**
- Not imported by any active code
- Replaced by unified pipeline
- Keeping them creates confusion
- Can be restored from git history if needed

### Option 2: Document and Keep
Add clear deprecation notices:
```python
# people.py
"""
DEPRECATED: This module is no longer used.
Use unified_miner.py instead, which extracts all entity types in a single pass.
Kept for reference only.
"""
```

### Option 3: Hybrid Approach
- Move unused prompts to `_deprecated/prompts/`
- Keep module files with deprecation warnings
- Update `__init__.py` to not export them

---

## Impact Assessment

### Safety: ✅ SAFE TO REMOVE
- ✅ No active imports found
- ✅ Not used by System2Orchestrator
- ✅ Not used by GUI
- ✅ Not used in tests
- ✅ Unified pipeline is fully functional replacement

### Risk: 🟢 LOW
- All functionality replaced by unified pipeline
- Unified pipeline is tested and in production
- Old code can be restored from git history

### Benefits of Removal:
1. **Clarity** - Eliminates confusion about which code path is active
2. **Maintainability** - Fewer files to maintain
3. **Performance** - No risk of accidentally invoking old slow path
4. **Documentation** - Clearer architecture for new developers

---

## Related Documentation

- `docs/ARCHITECTURE_UNIFIED.md` - Current unified architecture
- `docs/API_ENTRY_POINTS.md` - Correct entry points post-refactoring
- `BATCH_PROCESSING_CLEANUP_SUMMARY.md` - Previous cleanup work
- `CHANGELOG.md` - Version 3.5.0 removed CLI, unified code paths

---

## Next Steps

1. **Decision Required:** Choose removal strategy (Option 1, 2, or 3)
2. **If removing:** Create deprecation PR with:
   - Move files to `_deprecated/`
   - Update `__init__.py`
   - Update `MANIFEST.md`
   - Add entry to `CHANGELOG.md`
3. **Testing:** Verify all tests still pass
4. **Documentation:** Update architecture docs if needed

---

## Questions for User

1. Do you want to remove these vestigial modules now, or keep them with deprecation warnings?
2. Should we also audit for other unused code in the codebase?
3. Are there any use cases where the old extractors might be needed (e.g., for very specific extraction tasks)?
