# ID Unification Testing Checklist

**Date:** November 1, 2025  
**Purpose:** Verify the unified `source_id` architecture works correctly end-to-end

---

## ✅ Pre-Test Setup

- [x] **Step 1:** Delete database ✅ (Database didn't exist yet)
- [x] **Step 2:** Launch app ✅ (Opened via `launch_gui.command`)
- [ ] **Step 3:** Verify app launched successfully (check Terminal window)

---

## 🧪 Test 1: YouTube Download → Transcription Pipeline

### Objective
Verify that YouTube videos use `video_id` as `source_id` and that transcription reuses the existing record.

### Steps

1. **Download a YouTube video:**
   - [ ] Open Transcription Tab
   - [ ] Paste a YouTube URL (e.g., a short Peter Zeihan video)
   - [ ] Click "Download Audio"
   - [ ] Wait for download to complete

2. **Check database after download:**
   ```sql
   -- Open database in SQLite browser or use:
   sqlite3 knowledge_system.db "SELECT source_id, title, source_type, url FROM media_sources;"
   ```
   - [ ] Note the `source_id` (should be the YouTube video ID, e.g., `dQw4w9WgXcQ`)
   - [ ] Verify `source_type` = "youtube"
   - [ ] Verify `title` matches YouTube video title

3. **Transcribe the downloaded audio:**
   - [ ] Select the downloaded audio file in Transcription Tab
   - [ ] Configure transcription settings (use fast model for testing)
   - [ ] Click "Start Transcription"
   - [ ] Wait for transcription to complete

4. **Check transcript markdown file:**
   - [ ] Open the generated `.md` file in `output/`
   - [ ] Verify YAML frontmatter contains `source_id: "VIDEO_ID"`
   - [ ] Verify title does NOT have `[VIDEO_ID]` appended
   - [ ] Verify `source` field says "youtube" (not "Local Audio")
   - [ ] Verify rich YouTube metadata is present (uploader, description, etc.)
   - [ ] Verify thumbnail is embedded
   - [ ] Verify title appears below YAML
   - [ ] Verify description appears below title

5. **Check database after transcription:**
   ```sql
   sqlite3 knowledge_system.db "SELECT source_id, title, source_type FROM media_sources;"
   ```
   - [ ] Verify SAME `source_id` as step 2 (no duplicate record)
   - [ ] Verify only ONE `media_sources` record for this video
   - [ ] Check transcript record:
   ```sql
   sqlite3 knowledge_system.db "SELECT source_id, language, source FROM transcripts WHERE source_id = 'VIDEO_ID';"
   ```
   - [ ] Verify transcript uses same `source_id`

### Expected Results
- ✅ One `MediaSource` record with `source_id = VIDEO_ID`
- ✅ One `Transcript` record referencing same `source_id`
- ✅ Transcript markdown has correct `source_id` in YAML
- ✅ No duplicate records created

---

## 🧪 Test 2: Process Tab → Summarization Pipeline

### Objective
Verify that Process Tab correctly extracts `source_id` from transcript YAML and passes it to summarization.

### Steps

1. **Summarize the transcript:**
   - [ ] Switch to Process Tab
   - [ ] Select the transcript `.md` file from Test 1
   - [ ] Configure summarization settings
   - [ ] Click "Start Processing"
   - [ ] Wait for summarization to complete

2. **Check database after summarization:**
   ```sql
   sqlite3 knowledge_system.db "SELECT source_id, short_summary, long_summary FROM media_sources WHERE source_id = 'VIDEO_ID';"
   ```
   - [ ] Verify summaries are stored in the SAME `MediaSource` record
   - [ ] Verify `short_summary` is populated
   - [ ] Verify `long_summary` is populated
   - [ ] Verify `compression_ratio` is set

3. **Check for duplicates:**
   ```sql
   sqlite3 knowledge_system.db "SELECT COUNT(*) as count FROM media_sources WHERE title LIKE '%VIDEO_TITLE%';"
   ```
   - [ ] Verify count = 1 (no duplicates)

### Expected Results
- ✅ Summaries stored in SAME `MediaSource` record (not a new one)
- ✅ Still only ONE record for this video
- ✅ Process Tab correctly extracted `source_id` from YAML

---

## 🧪 Test 3: Document Processing Pipeline

### Objective
Verify that document processor uses deterministic hash-based IDs and updates on re-processing.

### Steps

1. **Process a PDF document:**
   - [ ] Go to Transcription Tab (or wherever document processing is)
   - [ ] Select a PDF file
   - [ ] Process it
   - [ ] Wait for completion

2. **Check database after first processing:**
   ```sql
   sqlite3 knowledge_system.db "SELECT source_id, title, source_type FROM media_sources WHERE source_type = 'document';"
   ```
   - [ ] Note the `source_id` (should be `doc_filename_HASH`)
   - [ ] Verify format: `doc_{filename}_{8-char-hash}`

3. **Re-process the SAME PDF:**
   - [ ] Select the same PDF file again
   - [ ] Process it again
   - [ ] Wait for completion

4. **Check database after re-processing:**
   ```sql
   sqlite3 knowledge_system.db "SELECT source_id, title, source_type, processed_at FROM media_sources WHERE source_type = 'document';"
   ```
   - [ ] Verify SAME `source_id` as step 2
   - [ ] Verify `processed_at` timestamp is updated
   - [ ] Verify only ONE record exists (no duplicate)

### Expected Results
- ✅ First processing creates record with `source_id = doc_filename_hash`
- ✅ Re-processing uses SAME `source_id`
- ✅ No duplicate record created
- ✅ Existing record is updated

---

## 🧪 Test 4: Local Audio File Pipeline

### Objective
Verify that local audio files use deterministic hash-based IDs.

### Steps

1. **Transcribe a local audio file:**
   - [ ] Go to Transcription Tab
   - [ ] Select a local audio file (not from YouTube)
   - [ ] Start transcription
   - [ ] Wait for completion

2. **Check database:**
   ```sql
   sqlite3 knowledge_system.db "SELECT source_id, title, source_type FROM media_sources WHERE source_id LIKE 'audio_%';"
   ```
   - [ ] Note the `source_id` (should be `audio_filename_HASH`)
   - [ ] Verify format: `audio_{filename}_{8-char-hash}`

3. **Re-transcribe the SAME audio file:**
   - [ ] Select the same audio file again
   - [ ] Start transcription again
   - [ ] Wait for completion

4. **Check database after re-transcription:**
   - [ ] Verify SAME `source_id` as step 2
   - [ ] Verify only ONE record exists (no duplicate)

### Expected Results
- ✅ First transcription creates record with `source_id = audio_filename_hash`
- ✅ Re-transcription uses SAME `source_id`
- ✅ No duplicate record created

---

## 🧪 Test 5: Speaker Attribution with YouTube Metadata

### Objective
Verify that speaker attribution LLM receives YouTube metadata for better name suggestions.

### Steps

1. **Use the YouTube video from Test 1:**
   - [ ] Open the transcript `.md` file
   - [ ] Check speaker names in the transcript

2. **Verify speaker names are correct:**
   - [ ] For Peter Zeihan video: Should say "Peter Zeihan" (not "Peter Zine")
   - [ ] For other videos: Check if speaker names match channel/uploader info

3. **Check logs (if available):**
   - [ ] Look for LLM speaker attribution logs
   - [ ] Verify metadata (title, uploader, description) was passed to LLM

### Expected Results
- ✅ Speaker names are correctly attributed
- ✅ LLM used YouTube metadata for context
- ✅ No fuzzy matching errors

---

## 📊 Final Verification

### Database Integrity Check

Run these SQL queries to verify overall database health:

```sql
-- Count records by source type
SELECT source_type, COUNT(*) as count 
FROM media_sources 
GROUP BY source_type;

-- Check for any duplicate titles (shouldn't be any for same content)
SELECT title, COUNT(*) as count 
FROM media_sources 
GROUP BY title 
HAVING count > 1;

-- Verify all transcripts reference valid sources
SELECT t.source_id, m.title 
FROM transcripts t 
LEFT JOIN media_sources m ON t.source_id = m.source_id 
WHERE m.source_id IS NULL;
-- Should return 0 rows

-- Verify all segments reference valid sources
SELECT DISTINCT s.source_id, m.title 
FROM segments s 
LEFT JOIN media_sources m ON s.source_id = m.source_id 
WHERE m.source_id IS NULL;
-- Should return 0 rows
```

### Checklist
- [ ] No duplicate `MediaSource` records for same content
- [ ] All `Transcript` records reference valid `source_id`
- [ ] All `Segment` records reference valid `source_id`
- [ ] YouTube videos use video ID as `source_id`
- [ ] Local files use hash-based `source_id`
- [ ] Documents use hash-based `source_id`

---

## ✅ Success Criteria

The ID unification is successful if:

1. ✅ **No Duplicates:** Re-processing any media updates existing record (no new record)
2. ✅ **Consistent IDs:** Same file always generates same `source_id`
3. ✅ **Correct Format:** 
   - YouTube: `source_id = video_id`
   - Local audio: `source_id = audio_filename_hash`
   - Documents: `source_id = doc_filename_hash`
4. ✅ **YAML Frontmatter:** Transcripts include `source_id` field
5. ✅ **Process Tab:** Correctly extracts and uses `source_id` for summarization
6. ✅ **Metadata Preservation:** YouTube metadata flows through entire pipeline
7. ✅ **Speaker Attribution:** LLM receives and uses YouTube metadata

---

## 🐛 If Tests Fail

### Duplicate Records Created
- Check if `source_id` is being passed correctly between stages
- Verify YAML frontmatter contains `source_id`
- Check Process Tab's `_get_source_id_from_transcript()` method

### Wrong source_id Format
- Check processor implementation (audio_processor.py, document_processor.py)
- Verify hash generation is deterministic
- Check database service calls

### Missing Metadata
- Check YouTube download metadata extraction
- Verify database record creation includes all fields
- Check transcription tab's `video_metadata` construction

### Speaker Attribution Issues
- Verify `video_metadata` is passed to `AudioProcessor`
- Check `SpeakerProcessor` receives metadata
- Verify LLM prompt includes metadata

---

## 📝 Notes

- Database location: `knowledge_system.db` (in project root)
- Transcript output: `output/` directory
- Logs: `logs/` directory (if enabled)
- SQLite browser: Use DB Browser for SQLite or command line

---

**Happy Testing! 🚀**

Report any issues or unexpected behavior.
