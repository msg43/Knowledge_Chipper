# Two-Step System Removal Plan

**Date:** December 22, 2025  
**Checkpoint Tag:** `checkpoint-before-two-step-removal`  
**Commit:** 66371a3

## Executive Summary

Removing the legacy two-step (mining + evaluator) system to eliminate confusion and maintain only the two-pass (extraction + synthesis) system as described in `WHOLE_DOCUMENT_MINING_DETAILED_PLAN.md`.

## What We're Removing

### The Two-Step System (DEPRECATED)
```
Step 1: UnifiedMiner extracts claims from segments
        ↓
Step 2: FlagshipEvaluator scores and filters claims
```

**Problems:**
- Processes segments independently (loses context)
- Two separate LLM calls per video
- Fragments claims across segment boundaries
- Confuses the AI assistant with parallel code paths

### What We're Keeping

### The Two-Pass System (ACTIVE)
```
Pass 1: Extraction Pass - Process entire document, extract ALL entities
        ↓
Pass 2: Synthesis Pass - Generate world-class summary from extracted claims
```

**Benefits:**
- Whole-document processing (preserves context)
- Only 2 API calls total per video
- Complete argument structures preserved
- Single, clear code path

## Files to Remove

### Core Two-Step Implementation
1. `src/knowledge_system/processors/hce/unified_miner.py` - Legacy miner
2. `src/knowledge_system/processors/hce/flagship_evaluator.py` - Legacy evaluator
3. `src/knowledge_system/processors/hce/unified_pipeline.py` - Old pipeline using two-step
4. `src/knowledge_system/core/system2_orchestrator_mining.py` - Integration layer for two-step

### Supporting Files
5. `src/knowledge_system/processors/hce/evaluators/jargon_evaluator.py` - Separate evaluator
6. `src/knowledge_system/processors/hce/evaluators/people_evaluator.py` - Separate evaluator
7. `src/knowledge_system/processors/hce/evaluators/concepts_evaluator.py` - Separate evaluator
8. `src/knowledge_system/core/batch_pipeline.py` - Uses two-step approach

### Test Files
9. `tests/test_unified_miner.py` (if exists)
10. `tests/test_flagship_evaluator.py` (if exists)

### Documentation
11. `EXTRACTION_ARCHITECTURE_ANALYSIS.md` - Compares approaches (archive)
12. `docs/ARCHITECTURE_UNIFIED.md` - Describes two-step architecture (update)

## Files to Keep and Update

### Core Two-Pass Implementation
1. `src/knowledge_system/processors/claims_first/pipeline.py` - Main two-pass pipeline
2. `src/knowledge_system/processors/claims_first/config.py` - Configuration
3. `src/knowledge_system/processors/claims_first/__init__.py` - Exports

### Orchestration
4. `src/knowledge_system/core/system2_orchestrator.py` - Update to use claims_first only

### GUI
5. `src/knowledge_system/gui/tabs/queue_tab.py` - Update to use claims_first

### Documentation
6. `WHOLE_DOCUMENT_MINING_DETAILED_PLAN.md` - Keep as primary architecture doc
7. `CLAUDE.md` - Update to reference only two-pass system
8. `MANIFEST.md` - Update file listings

## Implementation Steps

### Step 1: Verify Two-Pass System is Complete
- [ ] Check `claims_first/pipeline.py` has full extraction pass
- [ ] Check `claims_first/pipeline.py` has full synthesis pass
- [ ] Verify it handles all entity types (claims, jargon, people, concepts)

### Step 2: Update Orchestrator
- [ ] Remove imports of `unified_miner`, `flagship_evaluator`, `unified_pipeline`
- [ ] Remove `_process_mine()` method that uses two-step
- [ ] Remove `_process_flagship()` method
- [ ] Update to use `claims_first.pipeline` exclusively
- [ ] Remove `system2_orchestrator_mining.py` integration

### Step 3: Update GUI
- [ ] Update Queue Tab to use claims_first
- [ ] Remove any references to "mining" and "flagship" stages
- [ ] Update progress reporting to show "extraction" and "synthesis"

### Step 4: Remove Files
- [ ] Delete all files listed in "Files to Remove" section
- [ ] Update imports in any remaining files

### Step 5: Update Documentation
- [ ] Archive `EXTRACTION_ARCHITECTURE_ANALYSIS.md`
- [ ] Update `CLAUDE.md` to reference only two-pass
- [ ] Update `MANIFEST.md`
- [ ] Update `CHANGELOG.md`

### Step 6: Run Tests
- [ ] Run `make test-quick`
- [ ] Fix any import errors
- [ ] Verify GUI launches
- [ ] Test processing a video end-to-end

## Rollback Instructions

If anything goes wrong:

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
git reset --hard checkpoint-before-two-step-removal
```

## Success Criteria

- [ ] No references to `UnifiedMiner` in active code
- [ ] No references to `FlagshipEvaluator` in active code
- [ ] No references to `unified_pipeline` in active code
- [ ] Only `claims_first` pipeline is used
- [ ] All tests pass
- [ ] GUI launches and processes videos successfully
- [ ] Documentation clearly describes only two-pass system

## Notes

This removal simplifies the codebase and eliminates confusion between two parallel approaches. The two-pass system is superior because it:

1. Processes whole documents (no segmentation)
2. Preserves complete context and arguments
3. Uses only 2 API calls per video
4. Extracts all entity types in one pass
5. Generates synthesis from extracted claims

The old two-step system fragmented claims across segments and required separate mining and evaluation stages.

