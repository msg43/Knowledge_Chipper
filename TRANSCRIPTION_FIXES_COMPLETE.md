# Transcription Fixes Complete

## Summary of Fixes Applied

### 1. YouTube Metadata in Markdown Files ✅

**Previous Issue**: YouTube videos downloaded and transcribed locally were missing metadata (tags, uploader, etc.) in the markdown files.

**Root Causes Found**:
1. YouTube downloads were saving files as `Title.webm` without the video_id
2. Transcription tab couldn't extract video_id from filenames to query metadata
3. Audio processor wasn't set up to use YouTube metadata even if available

**Fixes Applied**:
1. **Updated YouTube Download Processor** (`youtube_download.py`):
   - Changed filename template from `%(title)s.%(ext)s` to `%(title)s [%(id)s].%(ext)s`
   - Now downloads save as: `Video Title [videoId123].webm`
   - This enables video_id extraction from filenames

2. **Enhanced Transcription Tab** (`transcription_tab.py`):
   - Added video_id extraction logic from filenames
   - Queries database for YouTube metadata when video_id found
   - Passes `video_metadata` to audio processor in kwargs

3. **Enhanced Audio Processor** (`audio_processor.py`):
   - Added `video_metadata` parameter to `_create_markdown()` and `save_transcript_to_markdown()`
   - When YouTube metadata present, generates rich YAML frontmatter with:
     - Title, URL, video_id
     - Uploader and upload date
     - Duration and view count
     - **Full tags list** (all tags preserved)
     - Transcription type indicator

### 2. Speaker Attribution Not Updating Markdown ✅

**Previous Issue**: Speaker names were assigned but markdown files still showed generic SPEAKER_00, SPEAKER_01 IDs.

**Root Causes Found**:
1. Speaker assignment queue wasn't regenerating markdown after completion
2. Transcription tab had removed speaker assignment signal/handler
3. No connection between dialog completion and markdown update

**Fixes Applied**:
1. **Enhanced Speaker Assignment Queue** (`speaker_assignment_queue.py`):
   - Added markdown regeneration after database update
   - Retrieves video metadata if YouTube video
   - Calls `AudioProcessor.save_transcript_to_markdown()` to overwrite file
   - Stores `output_dir` in task metadata for file location

2. **Fixed Transcription Tab** (`transcription_tab.py`):
   - Re-added `speaker_assignment_requested` signal
   - Re-added `_speaker_assignment_callback()` method
   - Added `_handle_speaker_assignment_request()` handler
   - Connected signal to handler
   - Passed callback to AudioProcessor

3. **Updated Audio Processor** (`audio_processor.py`):
   - Stores `output_dir` in metadata for speaker assignment queue
   - Ensures speaker assignment can find where to save updated markdown

## How It Works Now

### YouTube Video Transcription Flow:

1. **Download**: `Video Title [abc123def].webm` (includes video_id)
2. **Transcription Start**:
   - Extracts video_id from filename: `abc123def`
   - Queries database for full metadata
   - Passes metadata to audio processor
3. **Markdown Creation**:
   - Initial markdown has YouTube metadata (tags, uploader, etc.)
   - If diarization enabled, has generic speaker IDs initially
4. **Speaker Assignment** (if enabled):
   - Dialog shown non-blocking
   - User assigns real names
   - Queue completes task → regenerates markdown
5. **Final Result**:
   - Markdown has both YouTube metadata AND real speaker names
   - Database updated with assignments

### Key Improvements:

- ✅ YouTube metadata (including all tags) preserved in markdown
- ✅ Speaker names replace generic IDs automatically
- ✅ Non-blocking workflow - transcription continues while assigning speakers
- ✅ Re-runs properly overwrite existing files
- ✅ Works for both YouTube videos and local audio files

## Testing the Fixes

1. **Test YouTube video transcription**:
   ```
   - Download and transcribe a YouTube video
   - Check markdown has all metadata including tags
   - Enable diarization
   - Complete speaker assignment
   - Verify markdown updates with real names
   ```

2. **Test local audio file**:
   ```
   - Transcribe local audio with diarization
   - Verify speaker assignment still works
   - Check markdown has appropriate local file metadata
   ```

## Files Modified

1. `src/knowledge_system/processors/youtube_download.py` - Filename format
2. `src/knowledge_system/processors/audio_processor.py` - YouTube metadata support
3. `src/knowledge_system/gui/tabs/transcription_tab.py` - Metadata retrieval & speaker handling
4. `src/knowledge_system/utils/speaker_assignment_queue.py` - Markdown regeneration

## Notes

- The fix ensures backward compatibility - old files without video_id still work
- Local audio files get appropriate metadata (no YouTube fields)
- Speaker assignment is optional and non-blocking
- All YouTube tags are preserved (not truncated)
