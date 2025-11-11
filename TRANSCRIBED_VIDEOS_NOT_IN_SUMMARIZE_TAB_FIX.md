# Transcribed YouTube Videos Not Appearing in Summarize Tab - Fix

## Problem

When transcribing a YouTube URL in the Transcription tab, the resulting transcript did not appear in the Summarize tab's database browser, even though the transcription completed successfully and the transcript was saved to the database.

## Root Cause

The issue was caused by a **source_id mismatch** between the `MediaSource` record and the `Transcript` record:

1. **Download Phase**: When a YouTube URL is downloaded, the `YouTubeDownloadProcessor` creates a `MediaSource` record with `source_id = video_id` (e.g., `"dQw4w9WgXcQ"`)

2. **Transcription Phase**: When the downloaded audio file is transcribed, the `AudioProcessor` was **ALWAYS** generating a NEW `source_id` based on the file path hash:
   ```python
   source_id = f"audio_{path.stem}_{path_hash}"  # e.g., "audio_filename_a1b2c3d4"
   ```

3. **Result**: The `Transcript` record was created with a DIFFERENT `source_id` than the `MediaSource` record, creating an "orphaned transcript" that wasn't linked to any media source.

4. **Summarize Tab Query**: The Summarize tab's `_refresh_database_list()` method performs a JOIN query:
   ```python
   query = (
       session.query(MediaSource)
       .join(Transcript, MediaSource.source_id == Transcript.source_id)
       .filter(Transcript.transcript_id.isnot(None))
   )
   ```
   This query requires BOTH a `MediaSource` record AND a `Transcript` record with **matching source_ids**. Since the IDs didn't match, the transcript never appeared in the list.

## Solution

Modified `AudioProcessor._transcribe_with_retry()` to check for an existing `source_id` in the `source_metadata` before generating a new one:

```python
# Check if source_id is provided (e.g., from YouTube download)
source_metadata = kwargs.get("source_metadata")
source_id = None
if source_metadata and source_metadata.get("source_id"):
    source_id = source_metadata["source_id"]
    logger.info(f"Using existing source_id from metadata: {source_id}")

# If no source_id provided, generate one from file path
if not source_id:
    # Use hash of absolute path for consistent ID across re-runs
    path_hash = hashlib.md5(
        str(path.absolute()).encode(), usedforsecurity=False
    ).hexdigest()[:8]
    source_id = f"audio_{path.stem}_{path_hash}"
    logger.info(f"Generated new source_id from file path: {source_id}")
```

## Flow After Fix

### YouTube URL Transcription:
1. User enters YouTube URL in Transcription tab
2. `YouTubeDownloadProcessor` downloads video and creates `MediaSource` with `source_id = "dQw4w9WgXcQ"`
3. Transcription worker calls `_ensure_source_record_has_file_path()` to link audio file to source
4. `AudioProcessor` receives `source_metadata` containing `source_id = "dQw4w9WgXcQ"`
5. `AudioProcessor` uses existing `source_id` instead of generating new one
6. `Transcript` record is created with `source_id = "dQw4w9WgXcQ"` (matches MediaSource!)
7. Summarize tab query finds the matching MediaSource + Transcript pair ✅

### Local File Transcription:
1. User adds local audio file to Transcription tab
2. No download phase, so no existing `MediaSource` record
3. `AudioProcessor` receives NO `source_metadata`
4. `AudioProcessor` generates `source_id = "audio_filename_a1b2c3d4"` from file path
5. `AudioProcessor` creates NEW `MediaSource` record with generated `source_id`
6. `Transcript` record is created with same `source_id`
7. Summarize tab query finds the matching MediaSource + Transcript pair ✅

## Files Modified

- `src/knowledge_system/processors/audio_processor.py`:
  - Modified `_transcribe_with_retry()` to check for existing `source_id` in `source_metadata` before generating new one
  - Updated MediaSource creation logic to use metadata from `source_metadata` if available
  - Added logging to show whether existing or generated `source_id` is being used

## Testing

To verify the fix:

1. **Test YouTube URL Transcription**:
   - Go to Transcription tab
   - Enter a YouTube URL
   - Click "Start Transcription"
   - After completion, switch to Summarize tab
   - Click "Database" button
   - Verify the video appears in the list ✅

2. **Test Local File Transcription**:
   - Go to Transcription tab
   - Add a local audio/video file
   - Click "Start Transcription"
   - After completion, switch to Summarize tab
   - Click "Database" button
   - Verify the file appears in the list ✅

3. **Check Logs**:
   - Look for messages like:
     - `"Using existing source_id from metadata: dQw4w9WgXcQ"` (YouTube videos)
     - `"Generated new source_id from file path: audio_filename_a1b2c3d4"` (local files)

## Related Issues

This fix also resolves the "orphaned transcripts" warning that appeared in logs:
```
WARNING: Found 5 transcripts without MediaSource records. Source IDs: ['audio_video1_abc123', ...]
```

These orphaned transcripts were created by the old buggy behavior. They can be safely ignored or cleaned up with a database maintenance script if desired.

## Architecture Notes

This fix reinforces the **database-centric architecture** where:
- The download processor creates the canonical `MediaSource` record
- The transcription processor REUSES the existing `source_id` instead of creating a duplicate
- All downstream operations (summarization, claim extraction) reference the same `source_id`

This ensures referential integrity across the entire knowledge pipeline.
