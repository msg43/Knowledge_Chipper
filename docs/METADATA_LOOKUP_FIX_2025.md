# Critical Fix: YouTube Metadata Lookup (November 2025)

## The Problem You Found

When transcribing a YouTube-downloaded file, the metadata (title, uploader, description) wasn't appearing in:
1. The speaker attribution LLM prompt
2. The final markdown file
3. This meant it wasn't being retrieved from the database

## Root Cause

The issue was in `audio_processor.py` lines 1897-1932:

**What was happening:**
1. YouTube downloads create a database record with `source_id = video_id` (e.g., "83Drzy7t8JQ")
2. Transcription creates a DIFFERENT `media_id` based on file path hash (e.g., "audio_Ukraine_Strikes_abc123")
3. These IDs don't match, so transcription doesn't find the YouTube record
4. It creates a NEW record with just the filename as title
5. All YouTube metadata (uploader, description, etc.) is lost!

**The broken flow:**
```
YouTube Download:
  source_id: "83Drzy7t8JQ"
  title: "Ukraine Strikes Russia's Druzhba Oil Pipeline || Peter Zeihan"
  uploader: "Peter Zeihan"
  audio_file_path: "/path/to/Ukraine_Strikes...mp4"
  ↓
Transcription:
  media_id: "audio_Ukraine_Strikes_abc123" (NEW ID, doesn't match!)
  title: "Ukraine Strikes Russias Druzhba Oil Pipeline Peter Zeihan" (from filename)
  uploader: NULL
  description: "Audio file: Ukraine_Strikes...mp4"
  ↓
Result: YouTube metadata LOST!
```

## The Fix

Changed the database lookup strategy to check `audio_file_path` FIRST:

```python
# Strategy 1: Look up by audio_file_path (finds YouTube records)
existing_video = db_service.get_video_by_file_path(str(path.absolute()))
if existing_video:
    media_id = existing_video.source_id  # Use YouTube's video ID
    # Now we have: title, uploader, description, etc.!

# Strategy 2: Only create new record if no YouTube record exists
if not existing_video:
    media_id = f"audio_{path.stem}_{path_hash}"  # For true local files
    # Create minimal record from filename
```

**The fixed flow:**
```
YouTube Download:
  source_id: "83Drzy7t8JQ"
  title: "Ukraine Strikes Russia's Druzhba Oil Pipeline || Peter Zeihan"
  uploader: "Peter Zeihan"
  description: "..."
  audio_file_path: "/path/to/Ukraine_Strikes...mp4"
  ↓
Transcription:
  ✅ Looks up by audio_file_path
  ✅ Finds existing record with source_id "83Drzy7t8JQ"
  ✅ Uses that record's metadata
  ↓
Speaker Attribution:
  ✅ LLM receives: title="...Peter Zeihan", uploader="Peter Zeihan"
  ✅ LLM suggests: "Peter Zeihan" (not "Peter Zine")
  ↓
Markdown Output:
  ✅ Full YouTube metadata in YAML
  ✅ Correct speaker names
```

## Impact

This fix ensures:

1. **YouTube metadata flows correctly:**
   - Title with correct spelling
   - Uploader/channel name
   - Full description
   - Tags and categories
   - All other YouTube fields

2. **Speaker attribution works properly:**
   - LLM receives metadata in prompt
   - Can see "Peter Zeihan" in title and uploader
   - Chooses correct spelling over transcript errors

3. **Markdown output is complete:**
   - Rich YAML frontmatter with all YouTube metadata
   - Correct speaker names in transcript
   - Thumbnail and description sections

## Testing

To verify the fix works:

1. **Download a YouTube video:**
   ```bash
   # Use GUI Download tab or CLI
   ```

2. **Check database has metadata:**
   ```python
   from knowledge_system.database.service import DatabaseService
   db = DatabaseService()
   video = db.get_video_by_file_path("/path/to/downloaded/file.mp4")
   print(video.title, video.uploader, video.description)
   ```

3. **Transcribe the file:**
   ```bash
   # Use GUI Transcription tab with diarization enabled
   ```

4. **Verify in logs:**
   ```
   ✅ Found existing YouTube record for file.mp4: 
      Title (source_type: youtube)
   ```

5. **Check markdown output:**
   - YAML should have: title, uploader, description, tags, etc.
   - Speaker names should be correct (not transcript errors)

## Files Modified

- `src/knowledge_system/processors/audio_processor.py` (lines 1897-1932)
  - Added lookup by `audio_file_path` before creating new records
  - Preserves YouTube metadata for transcription

## Related Issues

This fix resolves:
- Missing YouTube metadata in markdown
- Speaker attribution using only transcript (with errors)
- Duplicate database records for the same video
- Loss of rich metadata on re-transcription

## Architecture Notes

The correct data flow is now:

```
YouTube Download → DB Record (with audio_file_path)
                      ↓
Transcription → Lookup by audio_file_path → Find existing record
                      ↓
Use existing metadata → Pass to speaker attribution
                      ↓
LLM sees full context → Correct speaker names
                      ↓
Markdown with rich metadata
```

This is the **database-centric architecture** working as designed!
