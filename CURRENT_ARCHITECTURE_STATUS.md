# Current Architecture Status - ACTUAL CODE PATHS

**Date:** December 22, 2025  
**Analysis:** What's actually running in production

## Two Parallel Code Paths Currently Active

### Path 1: Segment-Based Two-Step (Legacy HCE)
**Entry Point:** `System2Orchestrator._process_mine()` → `system2_orchestrator_mining.py`

**Flow:**
```
GUI Summarize Tab
  ↓
System2Orchestrator.create_job("mine")
  ↓
_process_mine()
  ↓
process_mine_with_unified_pipeline()
  ↓
UnifiedHCEPipeline.process()
  ├─> Splits transcript into segments
  ├─> UnifiedMiner mines each segment
  ├─> FlagshipEvaluator scores all claims
  └─> Stores to database
```

**Files:**
- `src/knowledge_system/core/system2_orchestrator.py` (lines 545-556)
- `src/knowledge_system/core/system2_orchestrator_mining.py`
- `src/knowledge_system/processors/hce/unified_pipeline.py`
- `src/knowledge_system/processors/hce/unified_miner.py`
- `src/knowledge_system/processors/hce/flagship_evaluator.py`

**Used By:** Summarize Tab (main GUI workflow)

**Problems:**
- Segments transcript (loses context across boundaries)
- Fragments claims
- Multiple LLM calls per video

### Path 2: Whole-Document Two-Step (Claims-First)
**Entry Point:** `ClaimsFirstWorker` in GUI

**Flow:**
```
GUI Transcription Tab (Claims-First mode)
  ↓
ClaimsFirstWorker.run()
  ↓
ClaimsFirstPipeline.process()
  ├─> Gets whole transcript (YouTube or Whisper)
  ├─> UnifiedMiner extracts from WHOLE document
  ├─> FlagshipEvaluator scores claims
  ├─> TimestampMatcher matches claims to transcript
  └─> LazySpeakerAttributor attributes speakers
```

**Files:**
- `src/knowledge_system/gui/workers/processing_workers.py` (ClaimsFirstWorker)
- `src/knowledge_system/gui/tabs/transcription_tab.py`
- `src/knowledge_system/processors/claims_first/pipeline.py`
- `src/knowledge_system/processors/claims_first/config.py`
- Uses same `unified_miner.py` and `flagship_evaluator.py` as Path 1

**Used By:** Transcription Tab (alternative workflow)

**Benefits:**
- Processes whole document (no segmentation)
- Preserves context
- Still uses two-step (mine + evaluate)

## The Confusion

Both paths use the **same underlying components**:
- `UnifiedMiner` - Extracts claims
- `FlagshipEvaluator` - Scores claims

The difference is:
- **Path 1** segments first, then mines each segment
- **Path 2** mines the whole document at once

## The Proposed Two-Pass System

`WHOLE_DOCUMENT_MINING_DETAILED_PLAN.md` describes a **third approach** that doesn't exist yet:

```
Pass 1: Single LLM call extracts AND scores everything
Pass 2: Single LLM call synthesizes summary
```

This would require:
- New extraction prompt that does mining + evaluation in one call
- New synthesis prompt that generates summary from claims
- Replacing both UnifiedMiner and FlagshipEvaluator

## Recommendation

Based on the actual code, here's what I recommend:

### Phase 1: Remove Segment-Based Path (SAFE)
**Remove:**
- `src/knowledge_system/processors/hce/unified_pipeline.py` (segment-based)
- `src/knowledge_system/core/system2_orchestrator_mining.py` (integration)
- Update `System2Orchestrator._process_mine()` to use Claims-First instead

**Keep:**
- `claims_first/pipeline.py` (whole-document)
- `unified_miner.py` and `flagship_evaluator.py` (used by claims-first)

**Result:** Single code path using whole-document processing

### Phase 2: Implement Two-Pass System (FUTURE)
**After Phase 1 is stable**, implement the two-pass system:
- Create `extraction_pass.py` - Combines mining + evaluation
- Create `synthesis_pass.py` - Generates summary
- Create `two_pass_pipeline.py` - Orchestrates both
- Replace `claims_first/pipeline.py` with new two-pass system

## What Should We Do?

**Option 1:** Just do Phase 1 (remove segment-based, unify on claims-first)
- Safest, quickest
- Eliminates the main source of confusion
- Keeps working code

**Option 2:** Do both phases (remove segment-based AND implement two-pass)
- More ambitious
- Requires writing new extraction/synthesis prompts
- Higher risk but cleaner final architecture

**Your call!** Which approach do you prefer?

