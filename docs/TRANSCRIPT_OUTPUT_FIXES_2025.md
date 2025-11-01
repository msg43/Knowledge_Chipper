# Transcript Output Fixes - November 2025

## Summary

Fixed 7 major issues with transcript markdown output for YouTube videos:

1. ✅ **Filename Generation**: Removed video ID from markdown filenames
2. ✅ **Source Type Display**: Ensured "YouTube" shows instead of "Local Audio" in YAML
3. ✅ **Rich Metadata**: Verified YouTube metadata appears in YAML frontmatter
4. ✅ **Thumbnail Embedding**: Fixed thumbnail embedding in markdown output
5. ✅ **Title Heading**: Added title heading below YAML (without video ID)
6. ✅ **Description Section**: Added full description below title
7. ✅ **Speaker Attribution**: Implemented fuzzy matching to correct speaker names

## Changes Made

### 1. Filename Generation (`audio_processor.py`)

**Problem**: Markdown files were named with video IDs appended (e.g., `Ukraine_Strikes_Russias_Druzhba_Oil_Pipeline__Peter_Zeihan_83Drzy7t8JQ_transcript.md`)

**Solution**: Modified `save_transcript_to_markdown()` to:
- Use clean title from `video_metadata` when available
- Strip video ID pattern `[videoID]` from titles
- Fall back to audio filename for local files

**Code Location**: Lines 1149-1171

### 2. Title Cleaning (`audio_processor.py`)

**Problem**: Video titles in YAML included video IDs (e.g., `"Ukraine... [83Drzy7t8JQ]"`)

**Solution**: Modified `_create_markdown()` to:
- Extract raw title from metadata
- Remove video ID pattern using regex: `r'\s*\[[a-zA-Z0-9_-]{11}\]\s*$'`
- Clean and sanitize title before adding to YAML

**Code Location**: Lines 973-977

### 3. Title Heading and Description (`audio_processor.py`)

**Problem**: No title heading or description appeared below YAML frontmatter

**Solution**: Added after YAML closing `---`:
- Title heading (H1) with cleaned title
- Description section (H2) with full YouTube description
- Proper spacing and formatting

**Code Location**: Lines 1078-1119

### 4. Thumbnail Embedding (`audio_processor.py`)

**Problem**: Thumbnails were not consistently embedded

**Solution**: Enhanced thumbnail handling to:
- Always include thumbnail link when path exists in metadata
- Log warnings if file doesn't exist yet
- Support both absolute and relative paths

**Code Location**: Lines 1087-1106

### 5. Source Type Detection (`audio_processor.py`)

**Problem**: Files showed "Local Audio" even when downloaded from YouTube

**Solution**: The code was already correct (lines 952-969), but the issue was that:
- Old files were transcribed before metadata was saved
- Files need to be re-transcribed to get updated output
- The fix ensures future transcriptions work correctly

### 6. Speaker Name Correction (`audio_processor.py`)

**Problem**: LLM suggestions had transcription errors (e.g., "Peter Zine" instead of "Peter Zeihan")

**Solution**: Implemented fuzzy matching correction system:
- Added `_correct_speaker_name_fuzzy()` method
- Uses `difflib.SequenceMatcher` for similarity matching
- Loads known hosts from `config/channel_hosts.csv`
- Corrects names with >0.8 similarity ratio
- Logs corrections for transparency

**Code Location**: 
- Function definition: Lines 789-835
- Integration: Lines 746-751

### 7. Channel Hosts Database (`config/channel_hosts.csv`)

**Addition**: Added Peter Zeihan to channel hosts database:
```csv
Peter Zeihan,Peter Zeihan,Peter Zeihan
```

## Testing

To test these fixes:

1. **Download a YouTube video**:
   ```bash
   # Use the GUI Download tab or CLI
   ```

2. **Transcribe the downloaded audio**:
   ```bash
   # Use the GUI Transcription tab
   # Ensure diarization is enabled for speaker attribution
   ```

3. **Verify the output markdown file**:
   - Filename should NOT have video ID
   - YAML should show `source_type: "YouTube"`
   - Title should be clean (no video ID)
   - Title heading should appear below YAML
   - Thumbnail should be embedded
   - Description should appear
   - Speaker names should be corrected

## Example Output

### Before:
```yaml
---
title: "Ukraine Strikes Russia's Druzhba Oil Pipeline ｜｜ Peter Zeihan [83Drzy7t8JQ]"
source_file: "Ukraine Strikes Russia's Druzhba Oil Pipeline ｜｜ Peter Zeihan [83Drzy7t8JQ].mp4"
source: "Local Audio"
transcription_type: "Local Audio"
---

## Full Transcript

**00:00** (Peter Zine): Hey all, Peter Zine here...
```

### After:
```yaml
---
title: "Ukraine Strikes Russia's Druzhba Oil Pipeline ｜｜ Peter Zeihan"
source: "https://www.youtube.com/watch?v=83Drzy7t8JQ"
video_id: "83Drzy7t8JQ"
uploader: "Peter Zeihan"
upload_date: "October 30, 2025"
duration: "03:17"
view_count: 45123
tags: ["geopolitics", "energy", "russia", "ukraine"]
youtube_categories: ["News & Politics"]
transcription_date: "October 31, 2025"
transcription_type: "YouTube"
---

# Ukraine Strikes Russia's Druzhba Oil Pipeline ｜｜ Peter Zeihan

![Thumbnail](/path/to/thumbnail.jpg)

## Description

In this video, I discuss the recent Ukrainian strikes on Russia's Druzhba oil pipeline...

## Full Transcript

**00:00** (Peter Zeihan): Hey all, Peter Zeihan here...
```

## Files Modified

1. `src/knowledge_system/processors/audio_processor.py`
   - Added title cleaning logic
   - Added title heading and description sections
   - Enhanced thumbnail embedding
   - Added fuzzy matching speaker correction

2. `src/knowledge_system/processors/youtube_download.py`
   - No changes needed (already saving correct metadata)

3. `config/channel_hosts.csv`
   - Added Peter Zeihan entry

## Notes

- **Existing files**: Old transcript files need to be re-transcribed to get the updated format
- **Database-centric**: The system relies on metadata being in the database during transcription
- **Speaker correction**: Requires `channel_hosts.csv` to be populated with known hosts
- **Fuzzy matching**: Uses 0.8 similarity threshold (80% match) for corrections

## Future Improvements

1. **Batch re-transcription**: Add tool to regenerate all transcript markdowns from database
2. **Speaker learning**: Store corrected names in database for future reference
3. **Channel auto-detection**: Automatically populate channel_hosts.csv from YouTube API
4. **Thumbnail relative paths**: Convert absolute paths to relative for portability

## Related Documentation

- `docs/guides/CODEBASE_STRUCTURE.md` - Database schema
- `config/channel_hosts.csv` - Known podcast hosts
- `src/knowledge_system/services/file_generation.py` - File generation service
