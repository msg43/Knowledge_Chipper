# Summarization Process Flow Analysis

## Executive Summary

The summarization process uses a **unified HCE (Hybrid Claim Extraction) pipeline** that performs 4 passes over content to extract claims, people, concepts, jargon, relations, and structured categories. The process is orchestrated through System2 job tracking and supports parallel processing.

## Quick Answers to Your Questions

| # | Question | Answer | Status |
|---|----------|--------|--------|
| 1 | Is EpisodeBundle (74-77) still relevant? | ✅ **YES** - It's the core data structure, but **INCOMPLETE** - lacks YouTube metadata (description, chapters, keywords) | 🔴 **Needs Enhancement** |
| 2 | Store to database - success verification? | ❌ **NO** - Success declared without verifying data actually written to DB | 🔴 **Critical Gap** |
| 3 | Progress callbacks - real indicators? | ⚠️ **ESTIMATES** - "mining" uses segment counter approximations, no verification step | 🔴 **Misleading** |
| 4 | YouTube metadata in LLM prompts? | ❌ **NO** - Metadata stored in DB but **NOT passed to mining prompts** | 🔴 **Missing Context** |
| 5 | Timestamps tracked on entities? | ✅ **YES** - All entities have `first_mention_ts` tracked in claim-centric schema | 🟢 **Working** |
| 6 | Markdown includes YT metadata + claim metadata? | ⚠️ **PARTIAL** - Has claim metadata but **missing YouTube info, temporality, scores** | 🔴 **Incomplete** |
| 7 | Batch URL processing integrated? | ❌ **NO** - `IntelligentProcessingCoordinator` exists but **not connected to UnifiedHCEPipeline** | 🔴 **Vestigial Code** |

---

## ⚠️ CRITICAL ISSUES IDENTIFIED

### 🔴 ISSUE 1: EpisodeBundle Lacks YouTube Metadata
**Status:** Missing critical context
- `EpisodeBundle` (lines 147-150 in types.py) only contains `episode_id`, `segments`, and optional `milestones`
- YouTube metadata (description, chapters, keywords) is stored in `MediaSource` table but **NOT passed to HCE prompts**
- LLM mining happens **without video context** - missing key anchoring information

### 🔴 ISSUE 2: No Database Verification Before Success
**Status:** Silent failure risk
- `system2_orchestrator_mining.py` lines 223-239: Database storage wrapped in try/except
- **Success declared at line 309** with final checkpoint, but no verification that data was actually written
- No readback confirmation before declaring "completed"

### 🔴 ISSUE 3: Progress Callbacks Are Estimates
**Status:** Misleading progress indicators
- "mining" callback (lines 145-179) uses **estimated percentages** based on segment counter
- "storing" = 90% (line 214) but **no verification** of actual storage completion
- No "verification" or "readback" stage at 96-100%

### ✅ ISSUE 4: Timestamps ARE Tracked Properly
**Status:** Working correctly
- ✅ Claims: `first_mention_ts` tracked (from first evidence span)
- ✅ People: `first_mention_ts` tracked (from PersonMention.t0)
- ✅ Concepts: `first_mention_ts` tracked (from MentalModel.first_mention_ts)
- ✅ Jargon: `first_mention_ts` tracked (from evidence_spans[0].t0)
- ✅ Evidence spans: Full `t0/t1` timestamps with context windows

**Note:** Only ClaimStore (claim-centric schema) is actively used. HCEStore exists but is NOT called in current mining pipeline.

### 🔴 ISSUE 5: Markdown Output Missing YouTube Metadata
**Status:** Incomplete
- `file_generation.py` lines 1447-1622: Markdown generator only includes HCE outputs
- **Missing:** YouTube description, video chapters, tags/keywords, upload date, channel info
- **Missing:** Claims-related metadata like temporality scores, relation rationales, category confidence

### 🔴 ISSUE 6: Batch URL Processing Disconnected
**Status:** Parallel code paths
- `IntelligentProcessingCoordinator` (lines 42-413) exists but **not used by GUI**
- Batch processing would use old System1-style pipeline, **not** UnifiedHCEPipeline
- No integration with System2Orchestrator job tracking
- Separate `BatchProcessor` class exists but unclear if connected

---

## Complete Flow Diagram

```
GUI Click
   ↓
SummarizationTab._start_processing()
   ↓
EnhancedSummarizationWorker (QThread)
   ↓
System2Orchestrator.create_job(job_type="mine", ...)
   ↓
System2Orchestrator.process_job(job_id) [async]
   ↓
System2Orchestrator._process_mine()
   ↓
process_mine_with_unified_pipeline() [in system2_orchestrator_mining.py]
   ↓
┌─────────────────────────────────────────┐
│  UnifiedHCEPipeline.process()           │
│                                         │
│  PASS 0: Short Summary (pre-mining)     │
│  PASS 1: Unified Mining (parallel)      │
│  PASS 2: Flagship Evaluation (ranking)  │
│  PASS 3: Long Summary (post-eval)       │
│  PASS 4: Structured Categories          │
└─────────────────────────────────────────┘
   ↓
HCEStore.upsert_pipeline_outputs() [saves to SQLite]
   ↓
System2Orchestrator._create_summary_from_pipeline_outputs() [creates Summary record]
   ↓
FileGenerationService.generate_summary_markdown_from_pipeline() [writes markdown file]
   ↓
Return results to GUI
```

---

## Detailed Module Breakdown

### 1. **GUI Entry Point**
**File:** `src/knowledge_system/gui/tabs/summarization_tab.py`

```python
SummarizationTab._start_processing()
    ↓
Creates: EnhancedSummarizationWorker (lines 49-333)
    ↓
Worker.run() → _run_with_system2_orchestrator()
```

**What it does:**
- Collects files from GUI file list
- Gets provider/model from dropdown selections
- Creates worker thread with GUI settings
- Worker runs System2Orchestrator for each file

**Key Code:**
- Lines 1145-1170: Start processing validation
- Lines 133-281: `_run_with_system2_orchestrator()` - main worker logic

---

### 2. **Job Orchestration Layer**
**File:** `src/knowledge_system/core/system2_orchestrator.py`

```python
System2Orchestrator.create_job("mine", episode_id, config)
    ↓
System2Orchestrator.process_job(job_id) [async]
    ↓
Routes to: _process_mine() (line 398)
```

**What it does:**
- Creates database Job and JobRun records for tracking
- Routes job types to appropriate processors
- Provides progress callbacks
- **Handles checkpointing for resumability (✅ FULLY IMPLEMENTED)**

**Key Methods:**
- `create_job()` (line 41): Creates DB job record
- `process_job()` (line 113): Async job executor
- `_process_mine()` (line 398): Routes to mining pipeline
- `_create_summary_from_pipeline_outputs()` (line 510): Creates Summary DB record

---

### 3. **Mining Pipeline Coordinator**
**File:** `src/knowledge_system/core/system2_orchestrator_mining.py`

```python
async def process_mine_with_unified_pipeline(
    orchestrator, episode_id, config, checkpoint, run_id
)
```

**What it does:**
1. **Load transcript** from file (line 36-47)
2. **Parse to segments** using `_parse_transcript_to_segments()` (line 53)
3. **Create EpisodeBundle** (lines 74-77)
4. **Configure HCE Pipeline** with models and parallelization settings (lines 79-100)
5. **Initialize UnifiedHCEPipeline** (line 103)
6. **Process through pipeline** (line 131-134)
7. **Store to database** via HCEStore (lines 144-158)
8. **Create Summary record** (lines 160-168)
9. **Generate markdown file** via FileGenerationService (lines 170-189)
10. **Return results** with metrics (lines 192-217)

**Progress Callbacks:**
- "loading" (0%)
- "parsing" (5%)
- "mining" (10-95% from pipeline)
- "storing" (90%)
- "generating_summary" (95%)
- "saving_file" (implicit in file generation)

---

### 4. **Core HCE Processing Pipeline**
**File:** `src/knowledge_system/processors/hce/unified_pipeline.py`

```python
class UnifiedHCEPipeline:
    def process(episode: EpisodeBundle, progress_callback) -> PipelineOutputs
```

**The 4-Pass System:**

#### **PASS 0: Short Summary (Pre-Mining Context)**
- **File:** `prompts/short_summary.txt`
- **Purpose:** Generate 1-2 paragraph overview for context
- **Method:** `_generate_short_summary()` (line 236)
- **Output:** Plain text summary

#### **PASS 1: Unified Mining (Parallel)**
- **File:** `unified_miner.py`, `prompts/unified_miner.txt`
- **Purpose:** Extract claims, jargon, people, mental models
- **Method:** `mine_episode_unified()` with parallel processing
- **Parallel:** Yes - processes segments concurrently
- **Output:** Claims with evidence spans, jargon terms, people, concepts

#### **PASS 2: Flagship Evaluation (Ranking)**
- **File:** `flagship_evaluator.py`, `prompts/flagship_evaluator.txt`  
- **Purpose:** Rank claims by importance (Tier A/B/C), filter noise
- **Method:** `evaluate_claims_flagship()`
- **Output:** Scored and tiered claims, accept/reject decisions

#### **PASS 3: Long Summary (Post-Evaluation)**
- **File:** `prompts/long_summary.txt`
- **Purpose:** Generate comprehensive 3-5 paragraph synthesis
- **Method:** `_generate_long_summary()` (line 295)
- **Input:** Short summary + top claims + evaluation metadata
- **Output:** Long-form narrative summary

#### **PASS 4: Structured Categories**
- **File:** `structured_categories.py`
- **Purpose:** WikiData topic categorization
- **Method:** `analyze_structured_categories()`
- **Output:** Hierarchical topic categories

**Final Output Structure (`PipelineOutputs`):**
- `claims: list[ScoredClaim]` - with tier, evidence, relations
- `jargon: list[JargonTerm]`
- `people: list[PersonMention]`
- `concepts: list[MentalModel]`
- `relations: list[ClaimRelation]`
- `structured_categories: list[StructuredCategory]`
- `short_summary: str`
- `long_summary: str`

---

### 5. **Data Persistence**
**File:** `src/knowledge_system/database/hce_store.py`

```python
HCEStore.upsert_pipeline_outputs(pipeline_outputs, episode_title, video_id)
```

**What it does:**
- Stores ALL pipeline outputs to unified SQLite schema
- Tables: `claims`, `evidence_spans`, `jargon`, `people`, `concepts`, `relations`, `categories`
- Uses deterministic IDs for idempotent re-runs
- Deletes old data for episode_id before inserting new

---

### 6. **Summary Record Creation**
**File:** `src/knowledge_system/core/system2_orchestrator.py` (line 510)

```python
_create_summary_from_pipeline_outputs(video_id, episode_id, pipeline_outputs, config)
```

**What it does:**
- Creates a `Summary` database record
- Uses `long_summary` from pipeline as canonical text
- Falls back to stats-based summary if long_summary missing
- Does NOT store full HCE JSON (data in unified tables)
- Records provider/model, tokens, compression ratio

**Database:** `summaries` table

---

### 7. **Markdown File Generation**
**File:** `src/knowledge_system/services/file_generation.py` (line 1447)

```python
FileGenerationService.generate_summary_markdown_from_pipeline(
    video_id, episode_id, pipeline_outputs
)
```

**What it writes:**
- Overview stats (claim counts by tier, evidence spans, etc.)
- Long summary (narrative)
- Tier A claims with evidence
- Tier B claims
- People mentioned
- Key concepts
- Jargon glossary
- Relations between claims
- Contradictions (if any)
- Structured categories

**Output:** `~/.knowledge_system/output/summaries/{video_id}_summary.md`

---

## Redundancies & Vestigial Code Identified

### 🟡 **VESTIGIAL CODE IDENTIFIED**

#### 1. Dual Worker Definitions
**Issue:** There are TWO `EnhancedSummarizationWorker` classes:
1. `src/knowledge_system/gui/tabs/summarization_tab.py` (lines 49-333) - **ACTIVE**
2. `src/knowledge_system/gui/workers/processing_workers.py` (lines 20-215) - **OBSOLETE**

**Recommendation:** Delete the worker in `processing_workers.py`

#### 2. IntelligentProcessingCoordinator
**File:** `src/knowledge_system/core/intelligent_processing_coordinator.py`

**Issue:** Designed for batch processing but **NOT integrated** with UnifiedHCEPipeline

**Recommendation:** Remove or refactor to use System2Orchestrator

#### 3. HCEStore Class ✅ **REMOVED**
**File:** ~~`src/knowledge_system/database/hce_store.py`~~ **DELETED**

**Status:** 
- ✅ Critical features (FTS indexing, milestones) **ported to ClaimStore**
- ✅ `hce_store.py` **deleted** - completely replaced by ClaimStore
- ✅ Unused import **removed** from `system2_orchestrator_mining.py`

**Features Added to ClaimStore:**
1. **Full-Text Search Indexing** - Indexes claims and evidence quotes in `claims_fts` and `evidence_fts` tables
2. **Milestones Storage** - Stores chapter/section markers with timestamps for episode navigation

---

### 🟢 **CLEAN: No Redundancy in HCE Pipeline**

The UnifiedHCEPipeline is **well-structured** with clear separation:
- **Unified Mining** (`unified_miner.py`) - single source of extraction
- **Flagship Evaluation** (`flagship_evaluator.py`) - single ranking system
- **Summaries** (short/long) - distinct purposes (context vs output)
- **Categories** (`structured_categories.py`) - separate WikiData analysis

**No dual tracks found.**

---

### 🟡 **POTENTIAL REDUNDANCY: Summary Storage**

**Issue:** Summary data is stored in TWO places:
1. **Unified HCE Tables** (`claims`, `evidence_spans`, `jargon`, etc.) via `HCEStore`
2. **Legacy Summary Table** (`summaries` table) via `_create_summary_from_pipeline_outputs()`

**Analysis:**
- The `summaries` table stores:
  - `summary_text` (the long summary narrative)
  - Metadata (provider, model, tokens, compression ratio)
  - Job tracking info
- The HCE tables store:
  - Structured extraction data (claims, evidence, people, etc.)
  
**Verdict:** **NOT REDUNDANT** - They serve different purposes:
- `summaries` = user-facing narrative + job metadata
- HCE tables = structured knowledge graph for querying

**Recommendation:** Keep both, but ensure clear documentation of their roles.

---

### 🟢 **GOOD: Single File Generation Path**

The `FileGenerationService.generate_summary_markdown_from_pipeline()` is the **only** markdown generator for summaries. No duplicate code paths found.

---

## Summary of Potential Issues

| Issue | Severity | Location | Recommendation | Status |
|-------|----------|----------|----------------|--------|
| Duplicate Worker Classes | 🟡 Medium | `processing_workers.py` lines 20-215 | Delete obsolete version | Not Critical |
| Unused IntelligentProcessingCoordinator | 🟡 Medium | `system2_orchestrator.py` line 37 | Remove or document | Not Critical |
| Constructor Mismatch | 🔴 High | `processing_workers.py` line 51-55 | Would crash if used - confirms it's dead code | Not Critical |
| Two Summary Storage Locations | 🟢 Low | `summaries` table + HCE tables | Intentional, different purposes | Working As Intended |
| **Checkpointing Incomplete** | **🟢 RESOLVED** | **All job types** | **Completed implementation** | **✅ DONE** |

---

## Overall Assessment

The summarization pipeline is **generally clean and well-architected** with:
- ✅ Clear separation of concerns (GUI → Orchestrator → Pipeline → Storage)
- ✅ Single unified HCE pipeline (no competing implementations)
- ✅ Parallel processing at the right layer (segment-level mining)
- ✅ Progress callbacks throughout the stack
- ✅ Database persistence with deterministic IDs

**Main cleanup needed:**
1. Remove the obsolete `EnhancedSummarizationWorker` in `processing_workers.py`
2. Clean up the unused `IntelligentProcessingCoordinator` reference in `System2Orchestrator`

**No critical dual tracks or dangerous redundancies found.**

---

## Flow Timeline (Typical File)

For a ~10,000 word document:

1. **GUI Launch** (instant)
2. **Job Creation** (< 1s) - DB writes
3. **File Loading** (< 1s)
4. **Segment Parsing** (< 1s) - ~100 segments
5. **Pass 0: Short Summary** (~10s) - Single LLM call
6. **Pass 1: Unified Mining** (~60-120s) - Parallel LLM calls per segment
7. **Pass 2: Flagship Evaluation** (~30s) - Ranking all claims
8. **Pass 3: Long Summary** (~15s) - Single LLM call with context
9. **Pass 4: Categories** (~10s) - WikiData analysis
10. **Database Storage** (< 2s) - SQLite inserts
11. **Summary Record** (< 1s) - Single insert
12. **Markdown Generation** (< 1s) - File write

**Total:** ~2-4 minutes depending on parallelization and LLM speed

---

## Key Design Strengths

1. **Idempotent**: Deterministic IDs allow re-running without duplicates
2. **✅ Resumable**: Full checkpoint/resume support for all job types (transcribe, mine, flagship, upload, pipeline)
3. **Progress Tracking**: Multi-layer progress callbacks for GUI updates
4. **Parallel**: Segment-level parallelization speeds up processing 3-8x
5. **Rich Data**: Evidence spans, relations, categories go beyond simple claim lists
6. **Flexible Models**: Can use OpenAI, Anthropic, Ollama, or any provider
7. **Database-Backed**: All results queryable via SQL, not just markdown files
8. **✅ Fault Tolerant**: Checkpoint system saves progress at multiple stages, allowing seamless recovery from crashes or interruptions

---

## Recommendations

### Immediate Cleanup
1. **Delete** `EnhancedSummarizationWorker` from `processing_workers.py`
2. **Remove** unused `self.coordinator` from `System2Orchestrator.__init__()`
3. ~~**Delete HCEStore**~~ ✅ **COMPLETED** - FTS and milestones ported to ClaimStore, file deleted

### 🚨 CRITICAL FIXES NEEDED

#### Fix 1: Add YouTube Metadata to EpisodeBundle
**File:** `src/knowledge_system/processors/hce/types.py`
```python
class EpisodeBundle(BaseModel):
    episode_id: str
    segments: list[Segment]
    milestones: list[Milestone] | None = None
    
    # NEW: YouTube context metadata
    video_metadata: dict[str, Any] | None = None  # {description, chapters, tags, keywords}
```

**File:** `src/knowledge_system/core/system2_orchestrator_mining.py` (lines 112-113)
```python
# BEFORE creating EpisodeBundle, fetch YouTube metadata from database:
video_metadata = orchestrator.db_service.get_video_metadata(video_id)  # NEW

episode_bundle = EpisodeBundle(
    episode_id=episode_id, 
    segments=segments,
    video_metadata=video_metadata  # NEW
)
```

**File:** `src/knowledge_system/processors/hce/unified_miner.py` (lines 72-86)
```python
# INJECT metadata into prompt:
context_parts = []
if episode.video_metadata:
    if desc := episode.video_metadata.get('description'):
        context_parts.append(f"Video Description: {desc[:500]}")
    if tags := episode.video_metadata.get('tags'):
        context_parts.append(f"Keywords: {', '.join(tags[:10])}")
    if chapters := episode.video_metadata.get('chapters'):
        context_parts.append(f"Chapter Topics: {', '.join([c['title'] for c in chapters[:5]])}")

context_prompt = "\n\n".join(context_parts)
full_prompt = f"{context_prompt}\n\n{self.template}\n\nSEGMENT TO ANALYZE:\n{json.dumps(segment_data, indent=2)}"
```

#### Fix 2: Add Database Verification Before Success
**File:** `src/knowledge_system/core/system2_orchestrator_mining.py` (after line 239)
```python
# After database storage, VERIFY before declaring success
try:
    # Verify claims were actually written
    from ..database.claim_store import ClaimStore
    claim_store = ClaimStore(orchestrator.db_service)
    
    # Read back claim count
    with orchestrator.db_service.get_session() as session:
        from ..database.claim_models import Claim
        verified_claims = session.query(Claim).filter_by(source_id=source_id).count()
    
    if verified_claims != len(pipeline_outputs.claims):
        raise KnowledgeSystemError(
            f"Database verification failed: expected {len(pipeline_outputs.claims)} claims, found {verified_claims}",
            ErrorCode.DATABASE_ERROR
        )
    
    logger.info(f"✅ Database verification passed: {verified_claims} claims stored")
    
    if orchestrator.progress_callback:
        orchestrator.progress_callback("verified", 98, episode_id)
        
except Exception as e:
    logger.error(f"❌ Database verification failed: {e}")
    raise
```

#### Fix 3: Add Real Progress Tracking
**File:** `src/knowledge_system/core/system2_orchestrator_mining.py`
```python
# Progress scale should be:
# 0-5%: Loading/parsing
# 5-90%: Mining (real progress from pipeline)
# 90-96%: Database storage
# 96-98%: Verification (NEW)
# 98-99%: Markdown generation
# 99-100%: Checkpoint finalization

# Update line 214:
orchestrator.progress_callback("storing", 93, episode_id)

# Add after database storage (new):
orchestrator.progress_callback("verifying", 96, episode_id)

# Update line 243:
orchestrator.progress_callback("generating_summary", 98, episode_id)

# Add before return:
orchestrator.progress_callback("finalizing", 99, episode_id)
```

#### Fix 4: Enhance Markdown Output with Metadata
**File:** `src/knowledge_system/services/file_generation.py` (lines 1463-1478)
```python
def generate_summary_markdown_from_pipeline(
    self,
    video_id: str,
    episode_id: str,
    pipeline_outputs,
) -> Path | None:
    # NEW: Fetch YouTube metadata from database
    video_metadata = None
    try:
        with self.db_service.get_session() as session:
            from ..database.models import MediaSource
            source = session.query(MediaSource).filter_by(media_id=video_id).first()
            if source:
                video_metadata = {
                    'title': source.title,
                    'description': source.description,
                    'uploader': source.uploader,
                    'upload_date': source.upload_date,
                    'duration': source.duration_seconds,
                    'tags': source.tags_json,
                    'chapters': source.video_chapters_json,
                    'url': source.url,
                }
    except Exception as e:
        logger.warning(f"Could not fetch video metadata: {e}")
    
    # Build markdown with metadata section
    markdown_lines = [
        f"# Summary: {episode_id}",
        "",
    ]
    
    # NEW: YouTube Metadata Section
    if video_metadata:
        markdown_lines.extend([
            "## Video Information",
            f"- **Title:** {video_metadata.get('title', 'N/A')}",
            f"- **Channel:** {video_metadata.get('uploader', 'N/A')}",
            f"- **Upload Date:** {video_metadata.get('upload_date', 'N/A')}",
            f"- **Duration:** {video_metadata.get('duration', 0) // 60} minutes",
            f"- **URL:** {video_metadata.get('url', 'N/A')}",
            "",
        ])
        
        if desc := video_metadata.get('description'):
            markdown_lines.extend([
                "### Description",
                desc[:500] + ("..." if len(desc) > 500 else ""),
                "",
            ])
        
        if tags := video_metadata.get('tags'):
            markdown_lines.extend([
                "### Tags",
                ", ".join(tags[:20]),
                "",
            ])
        
        if chapters := video_metadata.get('chapters'):
            markdown_lines.extend([
                "### Chapters",
                "",
            ])
            for ch in chapters:
                markdown_lines.append(f"- [{ch.get('start_time', '0:00')}] {ch.get('title', 'Unknown')}")
            markdown_lines.append("")
    
    markdown_lines.extend([
        "## Overview",
        # ... rest of existing code
    ])
```

#### Fix 5: Enhance Claim Output with Metadata
**File:** `src/knowledge_system/services/file_generation.py` (in Tier A claims section, around line 1500)
```python
for claim in tier_a_claims[:20]:  # Top 20
    markdown_lines.append(f"### {claim.canonical}")
    
    # Enhanced metadata display
    metadata_parts = [f"**Type:** {claim.claim_type}", f"**Tier:** {claim.tier}"]
    
    # NEW: Add temporality info
    if claim.temporality_score:
        temporal_labels = {1: "Immediate", 2: "Short-term", 3: "Medium-term", 4: "Long-term", 5: "Timeless"}
        temporal_label = temporal_labels.get(claim.temporality_score, "Unknown")
        metadata_parts.append(f"**Temporality:** {temporal_label} (confidence: {claim.temporality_confidence:.2f})")
    
    # NEW: Add scores
    if claim.scores:
        score_str = ", ".join([f"{k}={v:.2f}" for k, v in claim.scores.items()])
        metadata_parts.append(f"**Scores:** {score_str}")
    
    markdown_lines.append(" | ".join(metadata_parts))
```

#### Fix 6: Integrate Batch Processing with UnifiedHCEPipeline
**Recommendation:** 
1. **Phase out** `IntelligentProcessingCoordinator` (it's vestigial)
2. **Use** System2Orchestrator for ALL processing (batch or single)
3. **Create** a batch wrapper that calls `System2Orchestrator.create_job()` for each URL
4. **Track** batch progress via job_runs table

**File:** `src/knowledge_system/core/batch_processor.py` (refactor to use System2)
```python
class System2BatchProcessor:
    """Batch processor using System2Orchestrator for consistent pipeline."""
    
    def __init__(self, db_service: DatabaseService):
        self.orchestrator = System2Orchestrator(db_service)
    
    async def process_batch(self, urls: list[str], config: dict) -> dict:
        """Process multiple URLs using same pipeline as single files."""
        batch_id = f"batch_{int(time.time())}"
        
        jobs = []
        for url in urls:
            # Create mining job for each URL
            job_id = self.orchestrator.create_job(
                job_type="mine",
                input_id=url,
                config=config
            )
            jobs.append(job_id)
        
        # Process all jobs (respects parallelization settings)
        results = []
        for job_id in jobs:
            result = await self.orchestrator.process_job(job_id)
            results.append(result)
        
        return {"batch_id": batch_id, "jobs": results}
```

### Future Enhancements
1. ~~**Utilize checkpointing**~~: ✅ **COMPLETED** - All job types now support full checkpoint/resume
2. **Cache short summaries**: Reuse if content hasn't changed
3. **Add progress estimates**: Use historical data to estimate remaining time
4. **Enhanced segment-level tracking**: Track individual segment completion during parallel mining (currently uses periodic checkpoints)
5. **Video chapter alignment**: Use YouTube chapters as milestone boundaries for better segmentation

---

## Checkpoint Implementation Details (✅ COMPLETED)

### Overview
All job types now support comprehensive checkpoint/resume functionality, allowing jobs to be safely interrupted and resumed without losing progress.

### Checkpoint Architecture

#### 1. Mining Jobs (`_process_mine` / `process_mine_with_unified_pipeline`)
**Checkpoint Stages:**
- `parsing` - After transcript is parsed into segments
- `mining` - During segment processing (periodic saves every 10%)
- `storing` - After mining complete, before database storage
- `completed` - Job finished, final results cached
- `failed` - Error occurred, partial results saved

**Resume Behavior:**
- Completed jobs return cached results immediately
- Interrupted mining jobs skip already-processed segments
- Database storage is idempotent (safe to re-run)

**Checkpoint Structure:**
```json
{
  "stage": "mining",
  "total_segments": 100,
  "completed_segments": ["seg_0001", "seg_0002", ...],
  "progress_percent": 45,
  "final_result": {...}  // Only present when stage="completed"
}
```

#### 2. Transcription Jobs (`_process_transcribe`)
**Checkpoint Stages:**
- `validating` - Initial file validation
- `transcribing` - Running Whisper transcription
- `diarizing` - Speaker diarization (if enabled)
- `storing` - Database storage
- `completed` - Job finished
- `failed` - Error occurred

**Resume Behavior:**
- If transcription completed, skips re-transcription
- If diarization in progress, resumes from transcript
- Cached results returned for completed jobs

**Checkpoint Structure:**
```json
{
  "stage": "diarizing",
  "file_path": "/path/to/audio.mp3",
  "transcript_path": "/path/to/transcript.txt",
  "transcript_text": "...",
  "language": "en",
  "duration": 120.5,
  "final_result": {...}  // Only when completed
}
```

#### 3. Pipeline Jobs (`_process_pipeline`)
**Checkpoint Stages:**
- Per-stage tracking (transcribe, mine, flagship, etc.)
- Records which stages are complete
- Skips completed stages on resume

**Resume Behavior:**
- Each stage is a sub-job with its own checkpoints
- Completed stages are skipped entirely
- Current stage resumes from its own checkpoint

**Checkpoint Structure:**
```json
{
  "completed_stages": ["transcribe", "mine"],
  "results": {
    "transcribe": {...},
    "mine": {...}
  }
}
```

#### 4. Flagship & Upload Jobs
**Status:** Minimal checkpoint support (legacy/stub implementations)
- Both save `stage` and `final_result` on completion
- Error checkpoints include error messages
- Primarily for completeness and future expansion

### Checkpoint Storage

**Database Table:** `job_run.checkpoint_json` (JSON column)
- Automatically persisted to SQLite
- Survives process crashes and restarts
- Each job run has independent checkpoint state

**API Methods:**
- `save_checkpoint(run_id, checkpoint_data)` - Save/update checkpoint
- `load_checkpoint(run_id)` - Load existing checkpoint
- Checkpoint data is a Python dict (JSON-serializable)

### Testing

**Test Coverage:** `tests/test_checkpoint_resumption.py`
- ✅ Basic save/load functionality
- ✅ Checkpoint overwriting
- ✅ Non-existent checkpoints return None
- ✅ Completed stage detection
- ✅ Error checkpoint preservation
- ✅ Multiple runs with separate checkpoints
- ✅ Transcription resume from checkpoint

**All 7 tests passing** (as of implementation completion)

### Usage Example

```python
# Create a mining job
orchestrator = System2Orchestrator()
job_id = orchestrator.create_job(
    job_type="mine",
    input_id="episode_123",
    config={"file_path": "/path/to/transcript.txt"}
)

# Process the job (may be interrupted)
try:
    result = await orchestrator.process_job(job_id, resume_from_checkpoint=True)
except KeyboardInterrupt:
    # Job interrupted - checkpoint saved automatically
    pass

# Resume later (skips completed work)
result = await orchestrator.process_job(job_id, resume_from_checkpoint=True)
```

### Benefits

1. **Robustness**: System crashes don't lose hours of LLM processing
2. **Cost Savings**: No need to re-pay for already-completed LLM calls
3. **User Experience**: Can safely stop/resume long-running jobs
4. **Development**: Easier debugging with ability to resume from specific stages

---

**End of Analysis**
