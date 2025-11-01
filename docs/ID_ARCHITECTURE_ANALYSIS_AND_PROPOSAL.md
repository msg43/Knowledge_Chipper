# ID Architecture Analysis and Unification Proposal

**Date:** November 1, 2025  
**Status:** 🔍 INVESTIGATION COMPLETE → 📋 PROPOSAL READY

---

## Part 1: ID Passing Investigation

### Question: Is ID passing causing duplicate records?

**Answer: ⚠️ POTENTIALLY YES - Found architectural inconsistency**

### Current ID Flow Analysis

#### Scenario 1: YouTube Download → Transcription → Summarization

```
1. YouTube Download (youtube_download.py)
   ├─ Creates: source_id = "VIDEO_ID" (e.g., "83Drzy7t8JQ")
   └─ Stores: MediaSource with full YouTube metadata

2. Transcription (audio_processor.py) ✅ FIXED
   ├─ Looks up by: audio_file_path
   ├─ Finds: existing MediaSource with source_id = "VIDEO_ID"
   └─ Uses: media_id = "VIDEO_ID" (same as source_id)

3. Summarization (summarization_tab.py → system2_orchestrator.py)
   ├─ GUI passes: video_id from "db://VIDEO_ID" format
   ├─ Orchestrator receives: video_id = "VIDEO_ID"
   ├─ Creates: episode_id = "episode_VIDEO_ID"
   └─ Checks: if video_id exists in MediaSource
```

**Result:** ✅ **NO DUPLICATE** - IDs match correctly

#### Scenario 2: Direct File Transcription → Summarization

```
1. User selects local MP3 file (no YouTube download)
   
2. Transcription (audio_processor.py)
   ├─ Looks up by: audio_file_path → NOT FOUND
   ├─ Creates: media_id = "audio_filename_HASH123"
   └─ Stores: MediaSource with minimal metadata

3. Summarization (process_tab.py → system2_orchestrator.py)
   ├─ Process tab passes: episode_id = file_path.stem (e.g., "my_podcast_episode")
   ├─ Orchestrator receives: video_id = ??? (NOT PASSED!)
   ├─ Orchestrator checks: video_exists(video_id)
   └─ Creates: NEW MediaSource with video_id = "my_podcast_episode"
```

**Result:** ⚠️ **POTENTIAL DUPLICATE** - Two records:
- Record 1: `source_id="audio_filename_HASH123"` (from transcription)
- Record 2: `source_id="my_podcast_episode"` (from summarization)

### Root Cause: Inconsistent ID Passing

**Problem:** Different code paths use different ID conventions:

| Source | ID Variable | ID Format | Example |
|--------|-------------|-----------|---------|
| YouTube Download | `source_id` | `VIDEO_ID` | `"83Drzy7t8JQ"` |
| Audio Transcription | `media_id` | `"audio_{stem}_{hash}"` | `"audio_Ukraine_Strikes_abc123"` |
| Summarization (DB) | `video_id` | `VIDEO_ID` | `"83Drzy7t8JQ"` |
| Summarization (File) | `episode_id` | `file_path.stem` | `"my_podcast_episode"` |
| HCE Episodes | `episode_id` | `"episode_{source_id}"` | `"episode_83Drzy7t8JQ"` |

### Verification: Does This Actually Happen?

**Test Case 1:** Process Tab (Transcribe + Summarize)

Looking at `process_tab.py` lines 187-196:

```python
# Step 2: Summarization (if enabled and we have a transcript)
if self.config.get("summarize", False) and transcript_path:
    orchestrator = System2Orchestrator()
    episode_id = file_obj.stem  # <-- Uses filename stem
    
    job_id = orchestrator.create_job(
        job_type="mine",
        input_id=episode_id,  # <-- Passes episode_id, NOT video_id!
        config={
            "source": "process_tab",
            "file_path": str(transcript_path),
            ...
        },
    )
```

**Issue:** The `input_id` becomes `episode_id`, but the orchestrator needs `video_id` to link to the MediaSource created during transcription.

Looking at `system2_orchestrator_mining.py` lines 145-148:

```python
# 3a. Fetch video metadata for evaluator/summary context
video_metadata = None
try:
    source_id = episode_id.replace("episode_", "")  # <-- Strips "episode_" prefix
    video = orchestrator.db_service.get_video(source_id)  # <-- Looks up by source_id
```

**Problem Chain:**
1. Process tab passes `episode_id = "my_podcast_episode"`
2. Orchestrator strips "episode_" → `source_id = "my_podcast_episode"`
3. Looks up `MediaSource` with `source_id = "my_podcast_episode"` → **NOT FOUND**
4. Falls back to creating new record (line 722-727 of `system2_orchestrator.py`)

**Conclusion:** ⚠️ **YES, ID passing CAN cause duplicates** in the Process Tab workflow.

---

## Part 2: ID Naming Architecture Analysis

### Question: Why multiple ID types? Should we have one universal ID?

**Answer: 🎯 YES - Current architecture has unnecessary complexity**

### Current ID Types

#### 1. `source_id` (MediaSource table)
- **Purpose:** Primary key for all media sources
- **Format:** Varies by source type
  - YouTube: `"VIDEO_ID"` (11 chars)
  - Local audio: `"audio_{stem}_{hash}"` (variable)
  - Documents: `"doc_{stem}_{timestamp}"` (variable)
- **Used by:** MediaSource, Claim, Transcript, Summary

#### 2. `video_id` (Legacy naming)
- **Purpose:** Foreign key to MediaSource
- **Format:** Same as `source_id`
- **Used by:** Transcript.video_id, Summary.video_id
- **Problem:** Name implies "video" but used for all media types (audio, PDF, etc.)

#### 3. `media_id` (Code variable)
- **Purpose:** Local variable in audio_processor.py
- **Format:** Same as `source_id`
- **Used by:** Temporarily during transcription, then becomes `source_id`
- **Problem:** Confusing naming - sounds like a different ID type

#### 4. `episode_id` (Episode table)
- **Purpose:** Primary key for HCE episodes
- **Format:** `"episode_{source_id}"`
- **Relationship:** 1-to-1 with MediaSource where `source_type='episode'`
- **Used by:** Episode, Segment, Claim (for episode-based claims)

### The Confusion Matrix

| Table | Primary Key | Foreign Key to MediaSource | Notes |
|-------|-------------|---------------------------|-------|
| MediaSource | `source_id` | N/A | ✅ Good name |
| Episode | `episode_id` | `source_id` | ⚠️ Two IDs for same entity |
| Transcript | `transcript_id` | `video_id` | ❌ "video_id" is misleading |
| Summary | `summary_id` | `video_id` | ❌ "video_id" is misleading |
| Claim | `claim_id` | `source_id` | ✅ Good name |
| Segment | `segment_id` | `episode_id` | ✅ Correct FK |

### Why This Is Confusing

1. **Misleading Names:** `video_id` used for PDFs, audio files, articles
2. **Redundant Prefixes:** `episode_id = "episode_" + source_id` (why the prefix?)
3. **Inconsistent Variables:** Code uses `media_id`, `video_id`, `source_id` interchangeably
4. **No Clear Convention:** Different files use different variable names for the same concept

---

## Part 3: Proposed Solutions

### Solution 1: Standardize ID Naming (High Priority)

**Goal:** One universal ID concept with consistent naming

#### Database Changes

```sql
-- Rename columns for clarity (backward compatible via views)
ALTER TABLE transcripts RENAME COLUMN video_id TO source_id;
ALTER TABLE summaries RENAME COLUMN video_id TO source_id;
ALTER TABLE moc_extractions RENAME COLUMN video_id TO source_id;
ALTER TABLE generated_files RENAME COLUMN video_id TO source_id;

-- Create views for backward compatibility
CREATE VIEW transcripts_legacy AS 
SELECT transcript_id, source_id AS video_id, ... FROM transcripts;
```

#### Code Changes

**1. Standardize variable names:**

```python
# ❌ OLD (Confusing)
video_id = "83Drzy7t8JQ"
media_id = f"audio_{stem}_{hash}"
video_record = db.get_video(video_id)

# ✅ NEW (Clear)
source_id = "83Drzy7t8JQ"
source_id = f"audio_{stem}_{hash}"
source_record = db.get_source(source_id)
```

**2. Update method names:**

```python
# database/service.py
class DatabaseService:
    # ❌ OLD
    def get_video(self, video_id: str) -> MediaSource:
    def create_video(self, video_id: str, ...) -> MediaSource:
    
    # ✅ NEW
    def get_source(self, source_id: str) -> MediaSource:
    def create_source(self, source_id: str, ...) -> MediaSource:
    
    # Keep legacy methods as aliases
    def get_video(self, video_id: str) -> MediaSource:
        """Legacy alias for get_source()."""
        return self.get_source(video_id)
```

**3. Standardize ID passing:**

```python
# ❌ OLD (Process Tab)
episode_id = file_obj.stem
job_id = orchestrator.create_job(
    job_type="mine",
    input_id=episode_id,
    config={"file_path": str(transcript_path)},
)

# ✅ NEW (Process Tab)
source_id = self._get_source_id_from_transcript(transcript_path)
episode_id = f"episode_{source_id}"
job_id = orchestrator.create_job(
    job_type="mine",
    input_id=episode_id,
    config={
        "source_id": source_id,  # <-- EXPLICIT
        "file_path": str(transcript_path)
    },
)
```

#### Benefits

- ✅ **Clarity:** One concept = one name
- ✅ **Consistency:** All code uses same variable names
- ✅ **Maintainability:** No confusion about which ID to use
- ✅ **Backward Compatible:** Legacy methods/views for gradual migration

#### Migration Path

1. **Phase 1:** Add new methods alongside old ones (aliases)
2. **Phase 2:** Update all new code to use new names
3. **Phase 3:** Gradually refactor old code (low priority)
4. **Phase 4:** Deprecate old methods (far future)

---

### Solution 2: Fix ID Passing in Process Tab (High Priority)

**Goal:** Ensure Process Tab passes correct source_id to summarization

#### Current Problem

```python
# process_tab.py (line 187)
episode_id = file_obj.stem  # <-- Wrong! Uses filename, not source_id
```

#### Proposed Fix

```python
# process_tab.py
def _get_source_id_from_transcript(self, transcript_path: Path) -> str:
    """
    Extract source_id from transcript file.
    
    Transcripts are named: {source_id}_transcript.md
    Or contain source_id in YAML frontmatter.
    """
    # Strategy 1: Parse YAML frontmatter
    try:
        with open(transcript_path, 'r') as f:
            content = f.read()
            if content.startswith('---'):
                yaml_end = content.find('---', 3)
                if yaml_end > 0:
                    yaml_content = content[3:yaml_end]
                    import yaml
                    metadata = yaml.safe_load(yaml_content)
                    if 'source_id' in metadata:
                        return metadata['source_id']
                    # Fallback: video_id in YAML
                    if 'video_id' in metadata:
                        return metadata['video_id']
    except Exception as e:
        logger.warning(f"Could not parse transcript YAML: {e}")
    
    # Strategy 2: Extract from filename pattern
    # Transcripts are named: {title}_{source_id}_transcript.md
    stem = transcript_path.stem
    if '_transcript' in stem:
        # Try to extract video ID pattern [11 chars]
        import re
        match = re.search(r'[a-zA-Z0-9_-]{11}', stem)
        if match:
            return match.group(0)
    
    # Strategy 3: Look up in database by transcript file path
    db = DatabaseService()
    transcript_record = db.get_transcript_by_file_path(str(transcript_path))
    if transcript_record:
        return transcript_record.video_id  # Will be source_id after rename
    
    # Fallback: Use filename stem (creates new record)
    logger.warning(f"Could not determine source_id for {transcript_path}, using filename")
    return transcript_path.stem

def _process_audio_video(self, file_path: str) -> bool:
    # ... transcription code ...
    
    # Step 2: Summarization (if enabled and we have a transcript)
    if self.config.get("summarize", False) and transcript_path:
        # Get the source_id from the transcript
        source_id = self._get_source_id_from_transcript(transcript_path)
        episode_id = f"episode_{source_id}"
        
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "source": "process_tab",
                "source_id": source_id,  # <-- EXPLICIT
                "file_path": str(transcript_path),
                ...
            },
        )
```

#### Benefits

- ✅ **No Duplicates:** Summarization uses correct source_id
- ✅ **Robust:** Multiple fallback strategies
- ✅ **Traceable:** Clear logging when fallback is used

---

### Solution 3: Simplify Episode ID Convention (Medium Priority)

**Goal:** Remove redundant "episode_" prefix

#### Current Problem

```python
source_id = "83Drzy7t8JQ"
episode_id = f"episode_{source_id}"  # Why the prefix?
```

**Issues:**
- Redundant: Episode table already has `source_id` FK
- Confusing: Two IDs for the same entity
- Verbose: `episode_83Drzy7t8JQ` vs `83Drzy7t8JQ`

#### Proposed Change

**Option A: Use source_id directly as episode_id**

```sql
-- Episodes table
CREATE TABLE episodes (
    episode_id TEXT PRIMARY KEY,  -- Same as source_id
    source_id TEXT NOT NULL UNIQUE,  -- FK to media_sources
    ...
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id)
);

-- Constraint: episode_id MUST equal source_id
CREATE TRIGGER enforce_episode_id_equals_source_id
BEFORE INSERT ON episodes
BEGIN
    SELECT RAISE(ABORT, 'episode_id must equal source_id')
    WHERE NEW.episode_id != NEW.source_id;
END;
```

**Benefits:**
- ✅ Simpler: One ID per entity
- ✅ Clearer: No confusion about which ID to use
- ✅ Shorter: Less verbose

**Drawbacks:**
- ⚠️ Breaking change: All episode_id references need updating
- ⚠️ Migration needed: Existing data needs conversion

**Option B: Keep prefix but document the reason**

If there's a technical reason for the prefix (e.g., avoiding collisions with non-episode sources), document it clearly:

```python
# Why episode_id has "episode_" prefix:
# - Ensures global uniqueness across all ID types
# - Allows distinguishing episode IDs from source IDs in logs
# - Prevents accidental FK constraint violations
episode_id = f"episode_{source_id}"
```

#### Recommendation

**Use Option A** if no technical reason for prefix exists.  
**Use Option B** if prefix serves a purpose (document it!).

---

### Solution 4: Add source_id to Transcript YAML (Low Priority)

**Goal:** Make source_id traceable from transcript files

#### Current Transcript YAML

```yaml
---
title: "Ukraine Strikes Russia's Druzhba Oil Pipeline"
transcription_type: "YouTube"
source: "youtube"
uploader: "Peter Zeihan"
upload_date: "20241031"
---
```

#### Proposed Addition

```yaml
---
source_id: "83Drzy7t8JQ"  # <-- ADD THIS
title: "Ukraine Strikes Russia's Druzhba Oil Pipeline"
transcription_type: "YouTube"
source: "youtube"
uploader: "Peter Zeihan"
upload_date: "20241031"
---
```

#### Benefits

- ✅ **Traceable:** Can extract source_id from transcript file
- ✅ **Robust:** Process Tab can reliably link transcript → source
- ✅ **Debuggable:** Easy to see which source a transcript came from

#### Implementation

```python
# audio_processor.py - _create_markdown()
def _create_markdown(self, ...):
    lines = ["---"]
    
    # Add source_id first (for easy extraction)
    if video_metadata and video_metadata.get("video_id"):
        lines.append(f'source_id: "{video_metadata["video_id"]}"')
    elif kwargs.get("media_id"):
        lines.append(f'source_id: "{kwargs["media_id"]}"')
    
    # ... rest of YAML ...
```

---

## Part 4: Implementation Priority

### Phase 1: Critical Fixes (Do Now)

1. ✅ **Fix Process Tab ID Passing** (Solution 2)
   - Add `_get_source_id_from_transcript()` method
   - Pass `source_id` explicitly to orchestrator
   - **Impact:** Prevents duplicate records
   - **Effort:** 2-3 hours

2. ✅ **Add source_id to Transcript YAML** (Solution 4)
   - Modify `_create_markdown()` to include `source_id`
   - **Impact:** Makes source_id traceable
   - **Effort:** 30 minutes

### Phase 2: Naming Standardization (Do Soon)

3. 🔄 **Standardize Variable Names** (Solution 1 - Code Only)
   - Update all new code to use `source_id` consistently
   - Add `get_source()` / `create_source()` methods
   - Keep legacy methods as aliases
   - **Impact:** Improves code clarity
   - **Effort:** 4-6 hours (spread over time)

### Phase 3: Schema Refactoring (Do Eventually)

4. 🔮 **Rename Database Columns** (Solution 1 - Database)
   - Rename `video_id` → `source_id` in all tables
   - Create backward-compatible views
   - **Impact:** Eliminates confusion
   - **Effort:** 8-12 hours + testing

5. 🔮 **Simplify Episode ID** (Solution 3)
   - Decide on prefix convention
   - Document reasoning
   - Migrate if removing prefix
   - **Impact:** Simplifies architecture
   - **Effort:** 4-8 hours + migration

---

## Part 5: Summary

### Investigation Results

1. **ID Passing Issue:** ⚠️ **YES** - Process Tab can create duplicate records
2. **ID Naming Issue:** ⚠️ **YES** - Multiple names for same concept causes confusion

### Root Causes

1. **Inconsistent ID passing** between transcription and summarization
2. **Legacy naming** (`video_id`) used for all media types
3. **No standard convention** for variable names across codebase
4. **Redundant episode_id prefix** without clear documentation

### Recommended Actions

**Immediate (This Week):**
- Fix Process Tab ID passing
- Add source_id to transcript YAML

**Short Term (This Month):**
- Standardize variable names in new code
- Add `get_source()` / `create_source()` methods

**Long Term (Next Quarter):**
- Rename database columns
- Simplify episode_id convention

### Expected Benefits

- ✅ **No Duplicate Records:** Correct ID passing prevents duplicates
- ✅ **Clear Code:** Consistent naming improves maintainability
- ✅ **Easy Debugging:** Traceable IDs from files to database
- ✅ **Reduced Confusion:** One concept = one name

---

## Appendix: ID Flow Diagrams

### Current Flow (Confusing)

```
YouTube Download
  ↓ creates
MediaSource (source_id="VIDEO_ID")
  ↓ transcribes
Audio Processor (media_id="VIDEO_ID")
  ↓ saves
Transcript (video_id="VIDEO_ID")  ← Different name!
  ↓ summarizes
Process Tab (episode_id="filename")  ← Wrong ID!
  ↓ creates
Summary (video_id="filename")  ← Duplicate!
```

### Proposed Flow (Clear)

```
YouTube Download
  ↓ creates
MediaSource (source_id="VIDEO_ID")
  ↓ transcribes
Audio Processor (source_id="VIDEO_ID")  ← Same name
  ↓ saves
Transcript (source_id="VIDEO_ID")  ← Same name
  ↓ summarizes
Process Tab (source_id="VIDEO_ID")  ← Correct ID
  ↓ updates
Summary (source_id="VIDEO_ID")  ← No duplicate!
```

---

**Next Steps:** Implement Phase 1 fixes and test with full pipeline.
