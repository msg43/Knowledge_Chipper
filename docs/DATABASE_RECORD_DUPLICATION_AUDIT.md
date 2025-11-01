# Database Record Duplication Audit

**Date:** November 1, 2025  
**Status:** ✅ COMPREHENSIVE AUDIT COMPLETE

## Executive Summary

Audited all transcription and summarization processes to identify where duplicate database records might be created when they should share a single record. Found **3 potential issues** and **1 confirmed good pattern**.

---

## 1. ✅ FIXED: Audio Transcription (YouTube Downloads)

**Location:** `src/knowledge_system/processors/audio_processor.py` (lines 1907-1950)

### Problem (FIXED)
When transcribing a YouTube-downloaded audio file, the system was creating a **NEW** `MediaSource` record based on the local filename instead of finding and using the **EXISTING** YouTube metadata record.

**Result:** Two records for the same video:
- Record 1: `source_id="83Drzy7t8JQ"` (from YouTube download) ✓ Full metadata
- Record 2: `source_id="audio_Ukraine_Strikes_abc123"` (from transcription) ✗ Minimal metadata

### Solution (IMPLEMENTED)
Modified `audio_processor.py` to:
1. **First:** Look up existing record by `audio_file_path` (Strategy 1)
2. **If found:** Use that record's `source_id` and metadata
3. **If not found:** Create new record with path-based hash (Strategy 2 - for truly local files)

```python
# Strategy 1: Check if this file was downloaded from YouTube
existing_video = db_service.get_video_by_file_path(str(path.absolute()))
if existing_video:
    media_id = existing_video.source_id  # Use YouTube video_id!
    logger.info(f"✅ Found existing YouTube record for {path.name}")
else:
    # Strategy 2: Create new ID for truly local audio files
    media_id = f"audio_{path.stem}_{path_hash}"
```

**Status:** ✅ FIXED (November 1, 2025)

---

## 2. ⚠️ POTENTIAL ISSUE: Document Processing

**Location:** `src/knowledge_system/processors/document_processor.py` (lines 271-291)

### Problem
Every time a document is processed, a **NEW** `media_id` is created with a timestamp:

```python
media_id = f"doc_{file_path.stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
```

**Result:** Re-processing the same PDF creates multiple records:
- `doc_research_paper_20251101120000`
- `doc_research_paper_20251101130000`
- `doc_research_paper_20251101140000`

### Why This Matters
- Duplicate records in database
- Transcripts not overwritten (violates user memory #8391555)
- No way to track "this is a re-run of the same document"

### Recommended Fix
Use a **deterministic ID** based on file path hash (like audio processor):

```python
# Use hash of absolute path for consistent ID across re-runs
path_hash = hashlib.md5(
    str(file_path.absolute()).encode(), usedforsecurity=False
).hexdigest()[:8]
media_id = f"doc_{file_path.stem}_{path_hash}"

# Check if record already exists
existing_record = db.get_media_source(media_id)
if existing_record:
    # Update existing record
    db.update_media_source(media_id, ...)
else:
    # Create new record
    db.create_media_source(media_id, ...)
```

**Status:** ⚠️ NEEDS FIX

---

## 3. ⚠️ CONFIRMED ISSUE: Process Tab ID Passing

**Location:** `src/knowledge_system/gui/tabs/process_tab.py` (lines 187-196)

### Problem
When the Process Tab runs transcription + summarization together, it passes the **filename stem** as the `episode_id` instead of the `source_id` from the transcription:

```python
# Step 2: Summarization (if enabled and we have a transcript)
if self.config.get("summarize", False) and transcript_path:
    orchestrator = System2Orchestrator()
    episode_id = file_obj.stem  # <-- Wrong! Uses filename, not source_id
    
    job_id = orchestrator.create_job(
        job_type="mine",
        input_id=episode_id,  # <-- Passes filename as episode_id
        config={"file_path": str(transcript_path)},
    )
```

### Why This Creates Duplicates
**Scenario:**
1. YouTube download: Creates `source_id="83Drzy7t8JQ"` with full metadata
2. Transcription: Uses `source_id="83Drzy7t8JQ"` (correct after fix #1)
3. Process Tab: Passes `episode_id="Ukraine_Strikes_Russias_Druzhba"` (filename stem)
4. Orchestrator: Strips "episode_" → `source_id="Ukraine_Strikes_Russias_Druzhba"`
5. Orchestrator: Looks up MediaSource → **NOT FOUND**
6. Orchestrator: Creates NEW record with minimal metadata (lines 720-727)

**Result:** Two records:
- Record 1: `source_id="83Drzy7t8JQ"` (from YouTube download/transcription)
- Record 2: `source_id="Ukraine_Strikes_Russias_Druzhba"` (from summarization)

### Root Cause
The Process Tab doesn't extract the `source_id` from the transcript file before passing it to summarization.

### Recommended Fix
Add a method to extract `source_id` from transcript file:

```python
def _get_source_id_from_transcript(self, transcript_path: Path) -> str:
    """Extract source_id from transcript YAML frontmatter or filename."""
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
    except Exception as e:
        logger.warning(f"Could not parse transcript YAML: {e}")
    
    # Strategy 2: Extract video ID from filename pattern
    stem = transcript_path.stem
    import re
    match = re.search(r'[a-zA-Z0-9_-]{11}', stem)
    if match:
        return match.group(0)
    
    # Fallback: Use filename stem (will create new record)
    logger.warning(f"Could not determine source_id for {transcript_path}")
    return transcript_path.stem

def _process_audio_video(self, file_path: str) -> bool:
    # ... transcription code ...
    
    # Step 2: Summarization
    if self.config.get("summarize", False) and transcript_path:
        source_id = self._get_source_id_from_transcript(transcript_path)
        episode_id = f"episode_{source_id}"
        
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "source_id": source_id,  # <-- EXPLICIT
                "file_path": str(transcript_path),
                ...
            },
        )
```

**Status:** ⚠️ NEEDS FIX (High Priority)

---

## 4. ✅ GOOD PATTERN: HCE Episode Storage (ClaimStore)

**Location:** `src/knowledge_system/database/claim_store.py` (lines 155-252)

### How It Works
The `ClaimStore.upsert_pipeline_outputs()` method correctly handles episode records:

1. **Check if source exists** (lines 177-232)
   - If not, create minimal `MediaSource` record
   - Uses `INSERT OR IGNORE` to prevent duplicates

2. **Check if episode exists** (lines 238-252)
   - If not, create new `Episode` record linked to source
   - If exists, update with new data

3. **Upsert claims, evidence, relations** (lines 254+)
   - All use `ON CONFLICT DO UPDATE` for idempotency

### Why This Is Good
- **Idempotent:** Re-running HCE on same episode updates existing records
- **No duplicates:** Uses proper UPSERT patterns
- **Maintains relationships:** Episode → MediaSource FK is preserved

**Status:** ✅ GOOD PATTERN - No changes needed

---

## 5. ⚠️ EDGE CASE: Transcription Tab Retry Logic

**Location:** `src/knowledge_system/gui/tabs/transcription_tab.py` (lines 530-540)

### Problem
When retrying a failed YouTube download, the tab creates a **NEW** record:

```python
# Create new record for retry tracking
db_service.create_video(
    video_id=video_id,
    title=f"Retry: {url[:50]}",
    source_url=url,
    source_type="youtube",
    status="failed",
    ...
)
```

### Why This Could Be a Problem
If `video_id` already exists from a previous attempt, this will:
- Fail with a duplicate key error, OR
- Overwrite the existing record with "Retry: ..." title

### Recommended Fix
Use `get_or_create` pattern:

```python
# Get or create record for retry tracking
existing_video = db_service.get_video(video_id)
if existing_video:
    # Update existing record
    existing_video.failure_reason = error
    existing_video.needs_metadata_retry = True
    db_service.update_video(existing_video)
else:
    # Create new record
    db_service.create_video(...)
```

**Status:** ⚠️ NEEDS FIX (minor - only affects retry logic)

---

## Summary Table

| Process | Location | Issue | Status |
|---------|----------|-------|--------|
| Audio Transcription (YouTube) | `audio_processor.py:1907-1950` | Created new record instead of using existing YouTube metadata | ✅ FIXED |
| Document Processing | `document_processor.py:271-291` | Creates new record with timestamp on every re-run | ⚠️ NEEDS FIX |
| Process Tab ID Passing | `process_tab.py:187-196` | Passes filename stem instead of source_id to summarization | ⚠️ NEEDS FIX (high priority) |
| HCE Episode Storage | `claim_store.py:155-252` | None - uses proper UPSERT pattern | ✅ GOOD PATTERN |
| Transcription Retry | `transcription_tab.py:530-540` | May create duplicate on retry | ⚠️ NEEDS FIX (minor) |

---

## Recommendations

### High Priority
1. ✅ **DONE:** Fix audio transcription to use existing YouTube records
2. **TODO:** Fix Process Tab to pass source_id (not filename) to summarization
3. **TODO:** Add source_id to transcript YAML frontmatter for traceability
4. **TODO:** Fix document processing to use deterministic IDs

### Medium Priority
4. **TODO:** Fix transcription tab retry logic to update instead of create

### Low Priority
5. **CONSIDER:** Add database constraint to prevent duplicate `audio_file_path` entries
6. **CONSIDER:** Add logging to track when records are created vs. updated

---

## Testing Recommendations

### Test Case 1: YouTube Download + Transcription
1. Download YouTube video → Check `source_id` in DB
2. Transcribe downloaded file → Verify same `source_id` is used
3. Check that only ONE record exists with full metadata

### Test Case 2: Document Re-processing
1. Process PDF → Note `media_id` in DB
2. Re-process same PDF → Verify same `media_id` is updated (not new record)

### Test Case 3: Full Pipeline (Download → Transcribe → Summarize)
1. Download YouTube video → `source_id="VIDEO_ID"`
2. Transcribe → Verify uses `media_id="VIDEO_ID"`
3. Summarize → Verify uses `video_id="VIDEO_ID"`
4. Check that only ONE `MediaSource` record exists

---

## Related Files

- `src/knowledge_system/processors/audio_processor.py` - Audio transcription
- `src/knowledge_system/processors/document_processor.py` - Document processing
- `src/knowledge_system/processors/youtube_download.py` - YouTube downloads
- `src/knowledge_system/core/system2_orchestrator.py` - HCE summarization
- `src/knowledge_system/database/claim_store.py` - HCE episode storage
- `src/knowledge_system/gui/tabs/transcription_tab.py` - GUI transcription
- `src/knowledge_system/database/service.py` - Database service layer

---

## Related Documentation

- `docs/METADATA_LOOKUP_FIX_2025.md` - Fix for audio transcription issue
- `docs/TRANSCRIPT_ARCHITECTURE_CLARIFICATION.md` - System architecture
- `docs/DATABASE_CENTRIC_ARCHITECTURE.md` - Database design principles
- `docs/ID_ARCHITECTURE_ANALYSIS_AND_PROPOSAL.md` - Comprehensive ID naming analysis and unification proposal
