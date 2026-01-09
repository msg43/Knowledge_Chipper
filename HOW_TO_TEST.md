# How to Test the ID Unification - Step by Step

⚠️ **DEPRECATED (January 2026)** - This document describes GUI testing which has been replaced by web-first architecture.

**For current testing procedures:**
- Visit [GetReceipts.org/contribute](https://getreceipts.org/contribute)
- Install daemon: See README.md installation section
- Test via web interface instead of desktop GUI

**Status:** All code changes complete, GUI deprecated in favor of web interface

---

## ⚠️ Legacy GUI Testing Instructions (Deprecated)

**Note:** The desktop GUI has been moved to `_deprecated/gui/`. These instructions are preserved for historical reference only.

### Step 1: Launch the Application (DEPRECATED)

The desktop GUI is no longer the recommended interface. Use the web UI at GetReceipts.org/contribute instead.

**If you need to test legacy GUI code:**
```bash
# GUI files moved to _deprecated/gui/
# Launcher scripts moved to _deprecated/
# Not recommended for production use
```

---

## Step 2: Test YouTube Download → Transcription

### 2.1 Download a YouTube Video

1. **Go to Transcription Tab**
2. **Paste a YouTube URL** (use a short video for quick testing):
   ```
   Example: https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```
3. **Click "Download Audio"**
4. **Wait for download to complete**

### 2.2 Check Database After Download

Open a new terminal and run:
```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT source_id, title, source_type FROM media_sources;"
```

**Expected Result:**
```
VIDEO_ID|Video Title Here|youtube
```

**Key Check:** The `source_id` should be the YouTube video ID (e.g., `dQw4w9WgXcQ`), NOT something like `audio_filename_hash`.

### 2.3 Transcribe the Downloaded Audio

1. **Select the downloaded audio file** in the Transcription Tab
2. **Configure transcription settings** (use a fast model like "tiny" or "base" for testing)
3. **Click "Start Transcription"**
4. **Wait for transcription to complete**

### 2.4 Check the Transcript File

The transcript will be in the `output/` directory. Open it and check:

**YAML Frontmatter Should Include:**
```yaml
---
source_id: "VIDEO_ID"
title: "Video Title Here"
source: "YouTube"
uploader: "Channel Name"
description: "Full video description..."
---
```

**Critical Checks:**
- ✅ `source_id` field is present and matches the video ID
- ✅ Title does NOT have `[VIDEO_ID]` appended to it
- ✅ `source` says "YouTube" (not "Local Audio")
- ✅ Rich metadata is present (uploader, description)
- ✅ Thumbnail is embedded (if available)
- ✅ Title appears below YAML
- ✅ Description appears below title

### 2.5 Check Database After Transcription

```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT source_id, title, source_type FROM media_sources;"
```

**Expected Result:**
- ✅ SAME `source_id` as before (no duplicate record)
- ✅ Only ONE record for this video

**Check for duplicates:**
```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT title, COUNT(*) as count FROM media_sources GROUP BY title HAVING count > 1;"
```

**Expected Result:** No output (no duplicates)

---

## Step 3: Test Process Tab → Summarization

### 3.1 Summarize the Transcript

1. **Go to Process Tab**
2. **Select the transcript `.md` file** from Step 2
3. **Configure summarization settings**
4. **Click "Start Processing"**
5. **Wait for summarization to complete**

### 3.2 Check Database After Summarization

```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT source_id, LENGTH(short_summary) as short_len, LENGTH(long_summary) as long_len 
   FROM media_sources WHERE source_id = 'VIDEO_ID';"
```

Replace `VIDEO_ID` with the actual video ID.

**Expected Result:**
```
VIDEO_ID|150|500
```
(Numbers will vary, but both summaries should have content)

**Critical Check:**
```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT COUNT(*) FROM media_sources WHERE title LIKE '%Video Title%';"
```

**Expected Result:** `1` (still only one record, not two)

---

## Step 4: Test Document Processing

### 4.1 Process a PDF Document

1. **Go to Transcription Tab** (or wherever document processing is)
2. **Select a PDF file**
3. **Process it**
4. **Wait for completion**

### 4.2 Check Database After First Processing

```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT source_id, title, source_type FROM media_sources WHERE source_type = 'document';"
```

**Expected Result:**
```
doc_filename_HASH|Document Title|document
```

**Key Check:** The `source_id` format should be `doc_{filename}_{8-char-hash}`.

**Note the exact `source_id`** for the next step.

### 4.3 Re-process the SAME PDF

1. **Select the same PDF file again**
2. **Process it again**
3. **Wait for completion**

### 4.4 Check Database After Re-processing

```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT source_id, title, source_type, processed_at FROM media_sources WHERE source_type = 'document';"
```

**Expected Result:**
- ✅ SAME `source_id` as before
- ✅ `processed_at` timestamp is updated
- ✅ Only ONE record (no duplicate)

---

## Step 5: Quick Database Health Check

### Run the Status Script

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
./scripts/check_database_status.sh
```

This will show:
- Record counts by source type
- Recent media sources
- Potential duplicates
- Orphaned records

**Expected Results:**
- ✅ No duplicates
- ✅ No orphaned records
- ✅ All source_id formats are correct

---

## Success Criteria

The ID unification is successful if:

1. ✅ **YouTube videos** use video ID as `source_id`
2. ✅ **Local audio files** use hash-based `source_id` (format: `audio_filename_hash`)
3. ✅ **Documents** use hash-based `source_id` (format: `doc_filename_hash`)
4. ✅ **Re-processing** updates existing record (no duplicates)
5. ✅ **Transcript YAML** includes `source_id` field
6. ✅ **Process Tab** correctly extracts and uses `source_id` for summarization
7. ✅ **No duplicate records** for the same content

---

## If You Find Issues

Share with me:
1. **Error messages** from the terminal
2. **Database query results** that don't match expectations
3. **Screenshots** of unexpected behavior
4. **Transcript file contents** if YAML is wrong

I can then:
- ✅ Diagnose the problem
- ✅ Fix the code
- ✅ Create debugging scripts
- ✅ Provide SQL queries to investigate

---

## Quick Reference Commands

### Check Database Location
```bash
ls -lh ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db
```

### View All Sources
```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT source_id, source_type, title FROM media_sources;"
```

### Check for Duplicates
```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT title, COUNT(*) as count FROM media_sources GROUP BY title HAVING count > 1;"
```

### View Recent Records
```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT source_id, source_type, title FROM media_sources ORDER BY created_at DESC LIMIT 10;"
```

### Count Records by Type
```bash
sqlite3 ~/Library/Application\ Support/Knowledge\ Chipper/knowledge_system.db \
  "SELECT source_type, COUNT(*) as count FROM media_sources GROUP BY source_type;"
```

---

**Good luck with testing! Let me know what you find.** 🚀
