# Architecture Clarification: Current vs. Proposed

**Date:** December 22, 2025  
**Status:** IMPORTANT - Read before making changes

## The Confusion

There are THREE different architectures being discussed:

### 1. Legacy Two-Step (Segment-Based) ❌ DEPRECATED
**Location:** `unified_pipeline.py`, `system2_orchestrator_mining.py`

```
Transcript → Split into segments → UnifiedMiner per segment → FlagshipEvaluator → Store
```

**Problems:**
- Fragments claims across segment boundaries
- Loses context
- Multiple LLM calls per video

### 2. Claims-First Two-Step (Whole-Document) ✅ CURRENTLY IMPLEMENTED
**Location:** `claims_first/pipeline.py`

```
Transcript (whole) → UnifiedMiner (extract all) → FlagshipEvaluator (score) → Store
```

**Status:** This is what's ACTUALLY running in the codebase
**Benefits:**
- Processes whole document (no segmentation)
- Still uses two separate LLM calls (mining, then evaluation)
- Already implemented and working

### 3. Two-Pass (Extraction + Synthesis) 📋 PROPOSED BUT NOT IMPLEMENTED
**Location:** `WHOLE_DOCUMENT_MINING_DETAILED_PLAN.md` (design doc only)

```
Pass 1: Extract ALL entities + score in ONE call
Pass 2: Synthesize summary from extracted claims
```

**Status:** This is a DESIGN DOCUMENT, not implemented code
**Benefits:**
- Only 2 API calls total (not per-entity-type)
- Pass 1 does extraction AND scoring together
- Pass 2 generates synthesis

## What Actually Exists in Code

### Active Implementation
- `claims_first/pipeline.py` - Uses UnifiedMiner + FlagshipEvaluator (two-step, whole-document)
- `unified_pipeline.py` - Uses UnifiedMiner + FlagshipEvaluator (two-step, segment-based)
- `system2_orchestrator_mining.py` - Calls `unified_pipeline.py`

### Design Documents
- `WHOLE_DOCUMENT_MINING_DETAILED_PLAN.md` - Proposes two-pass system (NOT IMPLEMENTED)
- `EXTRACTION_ARCHITECTURE_ANALYSIS.md` - Analyzes different approaches

## The Question

You said: "Let's remove the two-step (mining and evaluator) system and leave the two-pass (extraction and synthesis) system as the only one."

**But the two-pass system doesn't exist yet!**

## Options

### Option A: Remove Segment-Based, Keep Claims-First Two-Step
**Remove:**
- `unified_pipeline.py` (segment-based two-step)
- `system2_orchestrator_mining.py` (calls segment-based)

**Keep:**
- `claims_first/pipeline.py` (whole-document two-step)

**Result:** Single clear path using whole-document processing with two-step (mine + evaluate)

### Option B: Implement Two-Pass, Remove Both Two-Step Systems
**Remove:**
- `unified_pipeline.py` (segment-based two-step)
- `system2_orchestrator_mining.py` (calls segment-based)
- `unified_miner.py` (separate mining step)
- `flagship_evaluator.py` (separate evaluation step)
- `claims_first/pipeline.py` (uses two-step)

**Implement:**
- New `extraction_pass.py` - Single LLM call extracts AND scores
- New `synthesis_pass.py` - Single LLM call generates summary
- New `two_pass_pipeline.py` - Orchestrates both passes

**Result:** Brand new architecture, requires significant implementation work

### Option C: Hybrid Approach
**Remove:**
- `unified_pipeline.py` (segment-based)
- `system2_orchestrator_mining.py` (segment-based integration)

**Keep:**
- `claims_first/pipeline.py` (rename to clarify it's the main path)
- `unified_miner.py` and `flagship_evaluator.py` (used by claims_first)

**Implement Later:**
- Two-pass system as a future enhancement

**Result:** Clean up now, implement two-pass later

## Recommendation

I recommend **Option C** because:

1. **Claims-first is working** - It already does whole-document processing
2. **Two-pass is not implemented** - Would require significant new code
3. **Segment-based is the real problem** - That's what fragments claims
4. **Incremental is safer** - Remove the bad stuff, keep the working stuff

## What to Do

Please clarify which option you prefer:

- **Option A**: Remove segment-based, keep claims-first two-step (safest)
- **Option B**: Implement brand new two-pass system (most work)
- **Option C**: Clean up segment-based, implement two-pass later (balanced)

Or describe your own preferred approach!

