# Deprecated References Removed from Documentation

**Date:** January 17, 2026

## Summary

Removed all references to deprecated workflows and files (HCE and unified miner) from `readmekc.md` and `MANIFEST.md` to reflect the current two-pass extraction architecture.

## Background

The Knowledge Chipper system migrated from a segment-based extraction approach (HCE/unified miner) to a whole-document two-pass extraction system in December 2025. However, the main documentation files still contained numerous references to the deprecated architecture, causing confusion about the current system.

## Changes Made

### readmekc.md

**1. Updated Processing Pipeline Diagram**
- **Before:** Referenced "UnifiedMiner" and "Flagship Evaluator" as separate stages
- **After:** Shows "Pass 1: Extract" and "Pass 2: Synthesize" as the two-pass architecture

**2. Updated Processing Features**
- **Before:** "6-stage pipeline" with separate mining, evaluation, and attribution stages
- **After:** "Two-pass pipeline" with extraction and synthesis

**3. Updated Processing Description**
- **Before:** "Extract claims, people, concepts (claims-first mode)"
- **After:** "Extract claims, people, concepts (two-pass whole-document extraction)"

**4. Replaced "Hybrid Claim Extraction (HCE)" Section**
- **Before:** Detailed 4-stage HCE pipeline (Mining → Evaluation → Categorization → Storage)
- **After:** "Two-Pass Extraction System" with Pass 1 (extraction & scoring) and Pass 2 (synthesis)

**5. Updated Database Documentation**
- **Before:** Referenced "HCE pipeline" and "speaker_fingerprints" table
- **After:** References "two-pass pipeline" and removed deprecated table reference

### MANIFEST.md

**1. Removed HCE-Specific Build Files**
- Removed reference to `Makefile.hce` (no longer exists)

**2. Updated Workflow Descriptions**
- Changed "no GUI/HCE/diarization" to "no GUI or deprecated features"

**3. Updated Documentation References**
- Changed "HCE segment-based prompts" to "segment-based prompts"
- Changed "HCE (Hybrid Claim Extraction) system fixes" to "extraction system fixes (legacy document)"
- Changed "HCE system architecture" to "Legacy extraction system architecture (deprecated)"

**4. Updated Core Module Descriptions**
- `enhanced_hce_pipeline.py`: Changed to "Legacy extraction pipeline (deprecated)"
- `system2_orchestrator_mining.py`: Changed to "Legacy mining integration (deprecated)"
- `claim_store.py`: Removed "HCE system" reference
- `apply_hce_migrations.py`: Changed to "Apply legacy database migrations (deprecated)"

**5. Updated Database Migration Files**
- `2025_08_18_hce_columns.sql`: Changed to "Legacy extraction system columns (deprecated)"
- `2025_08_18_hce_compat.sql`: Changed to "Legacy compatibility layer (deprecated)"

**6. Updated GUI Component Descriptions**
- `hce_adapter.py`: Changed to "Legacy adapter (deprecated)"
- `hce_update_dialog.py`: Changed to "Legacy update dialog (deprecated)"
- `prompts_tab.py`: Updated to note it's legacy (two-pass uses fixed prompts)

**7. Completely Rewrote PROCESSORS/HCE/ Section**
- Added clear deprecation warning at the top
- Marked all files as "(legacy)" or "DEPRECATED"
- Noted `unified_miner.py` is "replaced by extraction_pass.py"
- Noted `unified_pipeline.py` is "replaced by TwoPassPipeline"
- Consolidated HCE/EVALUATORS/, HCE/MODELS/, and HCE/PROMPTS/ sections with deprecation warnings
- Added note directing readers to PROCESSORS/TWO_PASS/ for the active system

**8. Updated Question Mapper Integration**
- `hce_integration.py`: Changed to "Legacy integration (deprecated)"

## Architecture Comparison

### Old Architecture (Deprecated)
```
Segment-Based HCE Pipeline:
1. Break transcript into segments
2. UnifiedMiner extracts from each segment
3. Flagship Evaluator scores claims
4. Categorization assigns domains
5. Storage saves results
```

### New Architecture (Current)
```
Two-Pass Whole-Document Pipeline:
1. Pass 1: Extract & score all entities (single API call)
   - Processes entire transcript
   - Extracts claims, jargon, people, concepts
   - Scores with 6-dimension system
   - Infers speakers from context
   
2. Pass 2: Synthesize summary (single API call)
   - Generates world-class long summary
   - Integrates high-importance claims
   - Dynamic length based on complexity
```

## Benefits of This Update

1. **Accuracy**: Documentation now matches the actual codebase
2. **Clarity**: Users understand the current two-pass system, not deprecated HCE
3. **Maintenance**: Easier to maintain when docs reflect reality
4. **Onboarding**: New developers won't be confused by references to non-existent systems

## Files Modified

- `/Users/matthewgreer/Projects/Knowledge_Chipper/readmekc.md`
- `/Users/matthewgreer/Projects/Knowledge_Chipper/MANIFEST.md`

## Verification

✅ No linter errors introduced
✅ All references to "HCE" and "unified miner" updated or marked as deprecated
✅ Documentation now accurately reflects the two-pass architecture

## Related Documents

- `PROMPT_INVENTORY.md` - Complete prompt catalog showing active vs deprecated prompts
- `TWO_PASS_MIGRATION_COMPLETE.md` - Details of the migration to two-pass architecture
- `VESTIGIAL_CODE_ANALYSIS.md` - Analysis of deprecated code modules

## Next Steps

Consider:
1. Moving `PROCESSORS/HCE/` directory to `_deprecated/hce/` to match the deprecation status
2. Updating any remaining documentation files that reference HCE or unified miner
3. Adding a migration guide for users transitioning from old to new architecture
