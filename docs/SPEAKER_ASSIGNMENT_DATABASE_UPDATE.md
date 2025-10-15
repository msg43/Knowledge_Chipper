# Speaker Assignment and Database Updates

## Question
**When user overrides speaker attributions, does the app go back and amend the entire SQLite DB entry for that episode to match the corrected attribution?**

## Answer: NO - But It Depends on Timing

The system has **different behavior** depending on **when** the speaker assignment happens relative to HCE processing.

---

## Scenario 1: Speaker Assignment BEFORE HCE Processing ✅

**Status**: Speaker names are correctly saved to HCE database

### Workflow:
1. User transcribes audio with diarization
2. Speaker assignment dialog appears
3. User accepts/edits speaker names
4. `SpeakerProcessor.apply_speaker_assignments()` updates transcript segments
5. **HCE processing hasn't happened yet**
6. Later: User runs summarization (HCE pipeline)
7. HCE processes segments **with correct speaker names**
8. `store_segments()` saves segments to HCE database with real names

### Code Flow:
```python
# In speaker_processor.py
def apply_speaker_assignments(transcript_data, assignments):
    # Update segments with assigned names
    for segment in transcript_data["segments"]:
        speaker_id = segment.get("speaker")
        if speaker_id in assignments:
            segment["speaker"] = assignments[speaker_id]  # ✅ Updated
```

```python
# Later, in hce/storage_sqlite.py
def store_segments(conn, episode_id, segments):
    for segment in segments:
        cur.execute("""
            INSERT INTO segments(episode_id, segment_id, speaker, t0, t1, text, topic_guess)
            VALUES(?, ?, ?, ?, ?, ?, ?)
        """, (
            episode_id,
            segment.segment_id,
            segment.speaker,  # ✅ Contains real name like "Jeff Snider"
            segment.t0,
            segment.t1,
            segment.text,
            getattr(segment, "topic_guess", None),
        ))
```

**Result**: HCE `segments` table contains correct speaker names

---

## Scenario 2: Speaker Assignment AFTER HCE Processing ❌

**Status**: Speaker names in HCE database are NOT automatically updated

### Workflow:
1. User transcribes audio with diarization
2. User **skips or cancels** speaker assignment dialog
3. Transcript has generic labels: `SPEAKER_0`, `SPEAKER_1`
4. User runs summarization (HCE pipeline)
5. HCE processes segments **with generic labels**
6. `store_segments()` saves segments to HCE database with `SPEAKER_0`, `SPEAKER_1`
7. **Later**: User realizes mistake and assigns names in speaker attribution tab
8. `apply_speaker_assignments()` updates the **transcript JSON file**
9. **HCE database is NOT updated** ❌

### Problem:
There is **no mechanism** to retroactively update the HCE segments table when speaker assignments change after HCE processing.

### Code Evidence:
Looking at `store_segments()` in `hce/storage_sqlite.py`:

```python
def store_segments(conn: sqlite3.Connection, episode_id: str, segments: list) -> None:
    """Store episode segments for reference."""
    cur = conn.cursor()
    
    try:
        cur.execute("BEGIN")
        
        # Clear existing segments
        cur.execute("DELETE FROM segments WHERE episode_id = ?", (episode_id,))
        
        # Insert new segments
        for segment in segments:
            cur.execute("""
                INSERT INTO segments(episode_id, segment_id, speaker, t0, t1, text, topic_guess)
                VALUES(?, ?, ?, ?, ?, ?, ?)
            """, (...))
```

This function is **only called during HCE processing**, not when speaker assignments change.

---

## What Gets Updated When Speaker Assignments Change

### ✅ DOES Get Updated:
1. **Transcript JSON files** - `apply_speaker_assignments()` updates in-memory data
2. **Speaker assignments database** (`speaker_assignments` table) - Stores mappings
3. **Speaker voice fingerprints** (`speaker_voices` table) - Voice profiles
4. **Future transcripts** - New files will use database assignments

### ❌ DOES NOT Get Updated:
1. **HCE segments table** - No UPDATE query exists
2. **HCE claims with speaker context** - Already extracted with wrong names
3. **HCE evidence spans** - Already reference segments with old speaker IDs
4. **Previously generated markdown outputs** - Static files

---

## Impact Analysis

### Minor Impact:
The HCE `segments` table is primarily used for **reference lookups**, not for critical analysis. The actual HCE analysis (claims, jargon, people, mental models) is stored separately and doesn't heavily rely on segment speaker names.

### Where It Matters:
1. **Querying segments by speaker** - Will use old labels
   ```sql
   SELECT * FROM segments WHERE speaker = 'Jeff Snider';  -- Won't find anything if stored as SPEAKER_0
   ```

2. **Segment context in UI** - If UI displays segments, shows generic labels

3. **Cross-episode speaker analysis** - Can't track speakers across episodes if labels inconsistent

---

## Recommended Solutions

### Option 1: Force HCE Reprocessing (Current Workaround)
**Pros**: Guarantees correct data
**Cons**: Expensive, requires re-running entire HCE pipeline

**Implementation**: User must delete HCE outputs and re-summarize

### Option 2: Add UPDATE Mechanism (Enhancement Needed)
Add a function to update speaker names in existing HCE data:

```python
def update_speaker_names_in_hce(
    conn: sqlite3.Connection,
    episode_id: str, 
    speaker_mappings: dict[str, str]
) -> None:
    """Update speaker names in existing HCE segments."""
    cur = conn.cursor()
    
    for old_speaker, new_speaker in speaker_mappings.items():
        cur.execute("""
            UPDATE segments 
            SET speaker = ? 
            WHERE episode_id = ? AND speaker = ?
        """, (new_speaker, episode_id, old_speaker))
    
    conn.commit()
```

**Call this function** when user updates speaker assignments in the GUI.

### Option 3: Prevent Issue (Best Practice)
**Strongly encourage speaker assignment BEFORE HCE processing**:
- Make speaker assignment dialog **mandatory** (not skippable)
- Show warning if user tries to skip: "Speaker identification is required for accurate analysis"
- Auto-run speaker assignment after transcription before allowing summarization

---

## Current System Behavior Summary

| Database | Updated on Speaker Assignment? | Notes |
|----------|-------------------------------|-------|
| `speaker_assignments` | ✅ Yes | Stores user-corrected mappings |
| `speaker_voices` | ✅ Yes | Stores voice fingerprints |
| HCE `segments` | ❌ No | Only updated during HCE processing |
| HCE `claims` | ❌ No | Already extracted with old context |
| HCE `evidence_spans` | ❌ No | References segments by ID, not speaker |
| Transcript JSON files | ✅ Yes | In-memory updates applied |

---

## Code Locations

### Speaker Assignment:
- `src/knowledge_system/processors/speaker_processor.py`
  - `apply_speaker_assignments()` - Updates transcript data (lines 1361-1412)

### HCE Storage:
- `src/knowledge_system/processors/hce/storage_sqlite.py`
  - `store_segments()` - Writes segments to database (lines 315-347)
  - `upsert_pipeline_outputs()` - Main HCE write (lines 37-312)

### Speaker Database:
- `src/knowledge_system/database/speaker_models.py`
  - SQLAlchemy models for speaker assignments and voices

---

## Recommendation

**Add the UPDATE mechanism** (Option 2) to ensure data consistency when users correct speaker assignments after HCE processing. This should be a small enhancement that calls:

1. `update_speaker_names_in_hce()` after `apply_speaker_assignments()`
2. Check if HCE data exists for this episode
3. If yes, update the segments table
4. Optionally offer to reprocess claims/analysis with correct speaker context

This gives users the best of both worlds: fast correction without full reprocessing, but with the option to reprocess if needed.
