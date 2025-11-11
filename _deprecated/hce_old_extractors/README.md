# Deprecated HCE Extractors

**Deprecated Date:** November 10, 2025  
**Replaced By:** Unified Pipeline (unified_miner.py + unified_pipeline.py)

## What's Here

This folder contains the **old pre-unified-pipeline architecture** that was replaced in October 2025.

### Old Extraction Modules

- `people.py` - Old standalone person mention extractor
- `glossary.py` - Old standalone jargon/glossary extractor  
- `concepts.py` - Old standalone mental model extractor
- `skim.py` - Old standalone summary generator

### Old Prompts

**Detection Prompts (used by old extractors):**
- `people_detect.txt` - Person detection prompt
- `people_disambiguate.txt` - Person name disambiguation
- `concepts_detect.txt` - Concept detection prompt
- `glossary_detect.txt` - Jargon detection prompt
- `skim.txt` - Quick summary generation prompt
- `contradiction.txt` - Contradiction detection (never implemented)

**Two-Tier Judge Prompts (old evaluation system):**
- `jargon_judge_high.txt` - High-confidence jargon evaluation
- `jargon_judge_low.txt` - Low-confidence jargon evaluation
- `mental_models_judge_high.txt` - High-confidence concept evaluation
- `mental_models_judge_low.txt` - Low-confidence concept evaluation
- `people_judge_high.txt` - High-confidence person evaluation
- `people_judge_low.txt` - Low-confidence person evaluation

## Why Deprecated

### Old Architecture (Sequential, Slow)
```
Episode
  ↓
PeopleExtractor → people_detect.txt
  ↓
GlossaryExtractor → glossary_detect.txt
  ↓
ConceptExtractor → concepts_detect.txt
  ↓
ClaimExtractor → (separate process)
  ↓
Two-Tier Evaluation:
  ├─> judge_high.txt (high confidence)
  └─> judge_low.txt (low confidence)
```

**Problems:**
- 4+ separate LLM calls (sequential)
- Each extractor saw different context
- Inconsistent extraction quality
- Slow processing (no parallelization)
- Complex code with multiple modules

### New Architecture (Parallel, Fast)
```
Episode
  ↓
UnifiedMiner (single pass, parallel)
  └─> unified_miner_*.txt
       ↓
       Extracts ALL simultaneously:
       ├─> Claims
       ├─> People
       ├─> Jargon
       └─> Mental Models
  ↓
Unified Evaluators (parallel)
  ├─> flagship_evaluator.txt (claims)
  ├─> people_evaluator.txt
  ├─> jargon_evaluator.txt
  └─> concepts_evaluator.txt
```

**Benefits:**
- ✅ 70% fewer LLM calls
- ✅ 3-8x faster (parallel processing)
- ✅ More consistent (single context)
- ✅ Simpler codebase
- ✅ Better quality extraction

## Migration Notes

If you need to restore any of this functionality:

1. **Don't use these files directly** - they're outdated
2. **Check the unified pipeline** - it likely already does what you need
3. **Refer to git history** - commit hash when deprecated: [to be filled]
4. **See documentation** - `docs/ARCHITECTURE_UNIFIED.md`

## Related Documentation

- `VESTIGIAL_CODE_ANALYSIS.md` - Full analysis of why this was deprecated
- `docs/ARCHITECTURE_UNIFIED.md` - Current unified architecture
- `docs/API_ENTRY_POINTS.md` - Correct entry points
- `CHANGELOG.md` - Version 3.5.3 deprecation entry

## Can This Be Deleted?

**Yes, eventually.** These files are kept for:
1. Reference during transition period
2. Historical context for architecture decisions
3. Potential prompt ideas for future improvements

After 6 months (May 2026), if no issues arise, these can be permanently deleted.
