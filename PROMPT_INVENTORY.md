# Prompt Inventory - All Prompts in Knowledge_Chipper

This document catalogs all prompts currently used in the Knowledge_Chipper/SkipThePodcast system.

## Current Active Prompts (Two-Pass Architecture)

### ACTIVE SYSTEM: Only 2 Prompts ✅

The system uses whole-document processing with only **2 API calls per video**:

#### 1. Pass 1: Extraction Pass Prompt
**Purpose:** Extract and score ALL entities from complete transcript in single API call  
**Location:** `src/knowledge_system/processors/two_pass/prompts/extraction_pass.txt`  
**Status:** ✅ **ACTIVE AND WIRED UP**  
**Used by:** `src/knowledge_system/processors/two_pass/extraction_pass.py`  
**Key Features:**
- Processes entire transcript (no segmentation)
- Extracts claims, jargon, people, mental models in one pass
- Scores each claim on 6 dimensions (epistemic_value, actionability, novelty, verifiability, understandability, temporal_stability)
- Calculates absolute importance score (0-10, globally comparable) using weighted formula
- Infers speakers from context (no diarization needed)
- Provides speaker confidence (0-10) and rationale
- Flags low-confidence attributions for review (< 7)
- Proposes rejections for trivial/redundant claims
- Includes evidence spans for ALL entities
- 5 comprehensive worked examples

**What it extracts:**
- **Claims**: With full evidence spans, timestamps, speaker attribution, 6-dimension scores, importance
- **Jargon**: Technical terms with definitions, domains, evidence spans
- **People**: Individuals mentioned with roles, context, evidence spans
- **Mental Models**: Conceptual frameworks with implications, evidence spans

**What it does NOT do:**
- No segmentation (processes complete document)
- No separate evaluation pass (scoring happens in extraction)
- No tiers (A/B/C) - just absolute importance scores
- No episode-level ranking - claims are globally comparable

#### 2. Pass 2: Synthesis Pass Prompt
**Purpose:** Generate world-class 3-5 paragraph summary from Pass 1 results  
**Location:** `src/knowledge_system/processors/two_pass/prompts/synthesis_pass.txt`  
**Status:** ✅ **ACTIVE AND WIRED UP**  
**Used by:** `src/knowledge_system/processors/two_pass/synthesis_pass.py`  
**Key Features:**
- Synthesizes from high-importance claims (importance ≥ 7.0)
- Integrates all entity types (claims, jargon, people, mental models)
- Uses YouTube AI summary as additional context
- Creates thematic narrative (not sequential listing)
- 5-paragraph structure: Context → Core Insights → Tensions → Contribution

**Inputs:**
- Top-ranked claims from Pass 1
- All jargon terms with definitions
- All people mentioned with roles
- All mental models with implications
- Evaluation statistics
- YouTube AI summary

---

## System Integration

### Pipeline Architecture

```
User Action (GUI)
    ↓
System2Orchestrator
    ↓
system2_orchestrator_two_pass.py
    ↓
TwoPassPipeline (processors/two_pass/pipeline.py)
    ├─> ExtractionPass (loads extraction_pass.txt)
    │   └─> 1 API call → ExtractionResult
    └─> SynthesisPass (loads synthesis_pass.txt)
        └─> 1 API call → SynthesisResult
    ↓
Store to Database (summaries, claims tables)
    ↓
Display in GUI
```

### Total: 2 API Calls Per Video

**Old Architecture:** N+1 API calls (N segments + 1 evaluation)  
**New Architecture:** 2 API calls (1 extraction + 1 synthesis)

---

## Legacy Prompts (DEPRECATED - Old Segmented Architecture)

The following prompts are part of the old two-step segmented architecture and are **NO LONGER USED** in the active two-pass system:

### Old HCE Mining Stage Prompts (Segment-Based)

**Location:** `src/knowledge_system/processors/hce/prompts/`

#### ~~unified_miner_transcript_own_V3.txt~~ ❌ DEPRECATED
**Purpose:** Extract entities from transcript segments (our own transcripts)  
**Status:** Superseded by two-pass extraction_pass.txt  
**Why deprecated:** Caused claim fragmentation across segment boundaries

#### ~~unified_miner_transcript_third_party.txt~~ ❌ DEPRECATED
**Purpose:** Extract entities from third-party transcript segments  
**Status:** Superseded by two-pass extraction_pass.txt  
**Why deprecated:** Segmentation prevented capturing complete arguments

#### ~~unified_miner_document.txt~~ ❌ DEPRECATED
**Purpose:** Extract entities from document segments  
**Status:** Superseded by two-pass extraction_pass.txt  
**Why deprecated:** Lost context across document sections

#### ~~unified_miner.txt~~ ❌ DEPRECATED
**Purpose:** Generic segment mining (fallback)  
**Status:** Superseded by two-pass extraction_pass.txt

#### ~~unified_miner_liberal.txt~~ ❌ DEPRECATED
**Purpose:** Liberal extraction variant (high recall)  
**Status:** No longer needed - extraction_pass.txt handles selectivity

#### ~~unified_miner_moderate.txt~~ ❌ DEPRECATED
**Purpose:** Moderate extraction variant (balanced)  
**Status:** No longer needed

#### ~~unified_miner_conservative.txt~~ ❌ DEPRECATED
**Purpose:** Conservative extraction variant (high precision)  
**Status:** No longer needed

#### ~~unified_miner_transcript_own.txt~~ ❌ DEPRECATED
**Purpose:** V1 of transcript mining  
**Status:** Superseded by V3, then by two-pass

#### ~~unified_miner_transcript_own_V2.txt~~ ❌ DEPRECATED
**Purpose:** V2 of transcript mining  
**Status:** Superseded by V3, then by two-pass

### Old HCE Evaluation Stage Prompts

**Location:** `src/knowledge_system/processors/hce/prompts/`

#### ~~flagship_evaluator.txt~~ ❌ DEPRECATED
**Purpose:** Review and rank extracted claims in separate pass  
**Status:** Functionality merged into extraction_pass.txt  
**Why deprecated:** Scoring now happens during extraction, not after

#### ~~concepts_evaluator.txt~~ ❌ DEPRECATED
**Purpose:** Post-process mental models  
**Status:** No longer needed - extraction and scoring happen together

#### ~~jargon_evaluator.txt~~ ❌ DEPRECATED
**Purpose:** Post-process jargon terms  
**Status:** No longer needed

#### ~~people_evaluator.txt~~ ❌ DEPRECATED
**Purpose:** Post-process person mentions  
**Status:** No longer needed

### Old Summary Generation Prompts

**Location:** `src/knowledge_system/processors/hce/prompts/`

#### ~~short_summary.txt~~ ❌ DEPRECATED
**Purpose:** Generate 1-2 paragraph overview  
**Status:** No longer needed - synthesis_pass.txt generates comprehensive summary directly

#### ~~long_summary.txt~~ ❌ DEPRECATED
**Purpose:** Generate long summary from flagship evaluation  
**Status:** Superseded by synthesis_pass.txt (different input structure)

---

## Other System Prompts (Status Unclear)

### Speaker Attribution Prompts

**Location:** Inline in Python files

#### LLM Speaker Suggester Prompt
**Location:** `src/knowledge_system/utils/llm_speaker_suggester.py`  
**Status:** ⚠️ **LIKELY DEPRECATED** - extraction_pass.txt now handles speaker inference  
**Note:** May still be used for Whisper transcripts with diarization

#### LLM Speaker Validator Prompt
**Location:** `src/knowledge_system/utils/llm_speaker_validator.py`  
**Status:** ⚠️ **LIKELY DEPRECATED** - extraction_pass.txt includes confidence scoring and flagging

### Question Mapper Prompts (Optional Feature)

**Location:** `src/knowledge_system/processors/question_mapper/prompts/`

#### Question Discovery Prompt
**File:** `discovery.txt`  
**Status:** ✅ **ACTIVE** - Optional post-processing feature  
**Purpose:** Identify key questions that extracted claims answer

#### Question Assignment Prompt
**File:** `assignment.txt`  
**Status:** ✅ **ACTIVE** - Optional post-processing feature  
**Purpose:** Assign claims to questions with relation types

#### Question Merger Prompt
**File:** `merger.txt`  
**Status:** ✅ **ACTIVE** - Optional post-processing feature  
**Purpose:** Deduplicate and merge similar questions

---

## Architecture Comparison

### Old Architecture (Deprecated)
```
Transcript → Split into Segments → Mine Each Segment (N API calls)
  → Collect Claims → Evaluate All Claims (1 API call)
  → Store to Database

Total: N+1 API calls
Problems: Fragmentation, lost context, complex coordination
```

### New Architecture (Current)
```
Complete Transcript → Pass 1: Extract & Score Everything (1 API call)
  → Pass 2: Generate Summary (1 API call)
  → Store to Database

Total: 2 API calls
Benefits: Whole context, simpler, faster, better quality
```

---

## Summary

### Active Prompts: 2 Core + 3 Optional

**Core (Required):**
1. ✅ `extraction_pass.txt` - Pass 1 extraction and scoring
2. ✅ `synthesis_pass.txt` - Pass 2 summary generation

**Optional (Post-Processing):**
3. ✅ `discovery.txt` - Question discovery
4. ✅ `assignment.txt` - Question assignment
5. ✅ `merger.txt` - Question merging

### Deprecated Prompts: 12+

**To Be Removed:**
- 9 segment-based mining prompts (unified_miner_*.txt)
- 4 separate evaluation prompts (*_evaluator.txt)
- 2 old summary prompts (short_summary.txt, long_summary.txt)

**Total:** 2 active core prompts vs 12+ deprecated prompts

This represents a **radical simplification** of the system architecture while improving quality through whole-document context preservation.

---

## Key Design Decisions

### Why Only 2 Core Prompts?

1. **Whole-Document Processing**: No segmentation means no need for segment-specific prompts
2. **Unified Extraction**: All entity types extracted together, not separately
3. **Integrated Scoring**: Scoring happens during extraction, not after
4. **Absolute Importance**: No tiers or episode-level ranking needed
5. **Speaker Inference Built-In**: No separate speaker attribution pass

### Why This Is Better

- **Simpler**: Single clear path, no parallel systems
- **Faster**: 2 API calls vs N+1 calls
- **Better Quality**: Complete context preserved, no fragmentation
- **Lower Cost**: Fewer tokens, fewer API calls
- **Easier to Maintain**: Only 2 core prompts to optimize

---

## Migration Status

### Completed ✅
- ✅ Two-pass pipeline implemented
- ✅ Extraction pass prompt enhanced
- ✅ Synthesis pass prompt active
- ✅ Integration with System2Orchestrator
- ✅ Database storage layer
- ✅ Validation and repair logic

### To Do 🔨
- Move deprecated prompts to `_deprecated/` folder
- Update GUI to use two-pass by default
- Add configuration toggle for architecture selection
- Comprehensive testing with sample videos
- Performance benchmarking vs old system
- Documentation updates

---

## Notes

- The two-pass architecture is **fully implemented and functional**
- All processing flows through `TwoPassPipeline`
- The system is **claim-centric** with absolute importance scoring
- Claims are **globally comparable** across all episodes
- User curation is built-in with accept/reject decisions
- Speaker inference is integrated, not a separate step
- The old segment-based HCE approach is being phased out
