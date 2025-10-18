# YouTube Metadata and Speaker Attribution Fix

## Issues Fixed

### 1. YouTube Metadata Not Written to Markdown

**Problem**: When transcribing YouTube videos locally (after downloading audio), the generated markdown files were missing important metadata like tags, uploader, upload date, view count, etc. Only basic file info was included.

**Root Cause**: The `AudioProcessor._create_markdown()` method only supported local audio files and didn't handle YouTube video metadata even when available in the database.

**Solution**:
1. **Modified `AudioProcessor._create_markdown()`** to accept an optional `video_metadata` parameter
2. **Added conditional logic** to generate rich YouTube frontmatter when `video_metadata` is provided:
   - Title, URL, video_id
   - Uploader information
   - Upload date (formatted nicely)
   - Duration, view count
   - **Tags** (full list in YAML array format)
   - Transcription type indicator
3. **Updated `AudioProcessor.save_transcript_to_markdown()`** to accept and pass `video_metadata`
4. **Modified `TranscriptionTab` worker** to:
   - Extract `video_id` from downloaded file names (format: "Title [video_id].webm")
   - Query database for video metadata using `DatabaseService.get_video()`
   - Pass metadata to audio processor via `video_metadata` kwarg

**Files Changed**:
- `src/knowledge_system/processors/audio_processor.py`
- `src/knowledge_system/gui/tabs/transcription_tab.py`

### 2. Speaker Attribution Not Updating Markdown Files

**Problem**: Speaker diarization worked and speaker attribution dialog appeared, but after users assigned real names to speakers, the markdown files still showed generic "SPEAKER_00", "SPEAKER_01" etc. instead of the actual names.

**Root Cause**: The speaker assignment queue (`SpeakerAssignmentQueue.complete_task()`) was updating the database with speaker assignments but **never regenerated the markdown files**. The markdown was created once with generic IDs and never updated.

**Solution**:
1. **Added markdown regeneration** to `SpeakerAssignmentQueue.complete_task()`:
   - After updating database with speaker assignments
   - Retrieve updated transcript data with real speaker names
   - Reconstruct `ProcessorResult` with updated segments
   - Call `AudioProcessor.save_transcript_to_markdown()` to overwrite existing file
   - Include video metadata if this is a YouTube video
2. **Ensured `output_dir` is available** in task metadata:
   - Modified `AudioProcessor._handle_speaker_assignment()` to store `output_dir` in metadata
   - Falls back to searching common output locations if not in metadata
3. **Database speaker assignments** were already working correctly (verified as part of this fix)

**Files Changed**:
- `src/knowledge_system/utils/speaker_assignment_queue.py`
- `src/knowledge_system/processors/audio_processor.py`

## How It Works Now

### YouTube Video Transcription Flow:

1. **Download Phase**: YouTube video audio downloaded, metadata saved to database
2. **Transcription Phase**: 
   - Worker extracts `video_id` from filename
   - Queries database for full metadata (tags, uploader, etc.)
   - Passes metadata to audio processor
   - Markdown created with **rich YouTube metadata** including tags
3. **Diarization Phase** (if enabled):
   - Speakers detected and assigned generic IDs (SPEAKER_00, etc.)
   - Markdown saved with generic speaker IDs
4. **Speaker Attribution Phase**:
   - Task queued for user to assign real names
   - User completes dialog with real names
   - Database updated with assignments
   - **Markdown file regenerated with real speaker names**
   - Final markdown has both YouTube metadata AND real speaker names

### Result:

The final markdown file now includes:
- ✅ Complete YouTube metadata (title, URL, tags, uploader, etc.)
- ✅ Real speaker names instead of generic IDs
- ✅ Both stored in database for persistence
- ✅ Re-runs overwrite properly

## Testing Recommendations

1. **Test YouTube video with diarization**:
   - Download and transcribe a YouTube video with multiple speakers
   - Check markdown has all YouTube metadata including tags
   - Complete speaker attribution dialog
   - Verify markdown updates with real speaker names

2. **Test local audio file**:
   - Ensure non-YouTube files still work with basic metadata
   - Speaker attribution should still work for local files

3. **Test re-runs**:
   - Re-transcribe same video
   - Verify metadata and speaker assignments persist/overwrite correctly

## Notes

- Speaker assignment is **non-blocking** - transcription completes immediately with generic IDs
- Markdown regeneration happens automatically when user completes speaker dialog
- Database is the source of truth for both metadata and speaker assignments
- System gracefully handles missing metadata (falls back to basic file info)

