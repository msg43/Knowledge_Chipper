# Transcript Metadata Improvements - October 2025

## Issues Identified

Analysis of transcript file: `Ukraine_And_Everyone_Else_Develops_Glide_Bombs__Peter_Zeihan_7puZUPjOoOI_transcript.md`

### Problems Found:

1. **Title includes video ID in YAML frontmatter** ❌
   - Current: `title: "Ukraine (And Everyone Else) Develops Glide Bombs ｜｜ Peter Zeihan [7puZUPjOoOI]"`
   - Should be: `title: "Ukraine (And Everyone Else) Develops Glide Bombs ｜｜ Peter Zeihan"`
   
2. **Wrong source type** ❌
   - Current: `source: "Local Audio"` and `transcription_type: "Local Audio"`
   - Should be: `source: "YouTube"` (or RSS, etc. based on actual source)

3. **Missing YouTube metadata** ❌
   - No `uploader`, `upload_date`, `view_count`, `tags`, `categories`, `description` fields
   - These should be populated from YouTube/RSS metadata

4. **No thumbnail** ❌
   - Thumbnail should be downloaded and referenced in markdown
   - Should appear as: `![Thumbnail](path/to/thumbnail.jpg)`

5. **No title heading below YAML** ❌
   - Should have `# Title` heading after YAML frontmatter for better readability

6. **No description section** ❌
   - Should have `## Description` section with YouTube video description

7. **Incorrect speaker attribution** ❌
   - Current: `(Peter Zine):`
   - Should be: `(Peter Zeihan):`

## Root Cause

When YouTube videos are transcribed **directly from downloaded files** (not through the integrated download+transcribe pipeline), the system treated them as generic "Local Audio" files and didn't lookup their metadata from the database.

The database contains all YouTube metadata (title, uploader, description, tags, thumbnail path, etc.), but it wasn't being retrieved when transcribing existing audio files.

## Solutions Implemented

### 1. Database Metadata Lookup (audio_processor.py)

Added automatic database lookup for YouTube/RSS metadata when transcribing files:

```python
# If no video_metadata provided, check database for YouTube/RSS metadata
# This handles cases where files are transcribed directly (not through download pipeline)
if not video_metadata and db_service:
    try:
        # Try to find video record by audio file path
        from sqlalchemy import select
        from ..database.models import MediaSource
        
        with db_service.get_session() as session:
            # Look for media source with this audio file path
            stmt = select(MediaSource).where(
                MediaSource.audio_file_path == str(path.absolute())
            )
            video_record = session.execute(stmt).scalar_one_or_none()
            
            if video_record and video_record.source_type in ["youtube", "rss", "podcast"]:
                # Found YouTube/RSS metadata - use it
                video_metadata = {
                    "video_id": video_record.source_id,
                    "title": video_record.title,  # Clean title without video ID
                    "url": video_record.url,
                    "uploader": video_record.uploader,
                    "upload_date": video_record.upload_date,
                    "view_count": video_record.view_count,
                    "tags": tags,
                    "categories": categories,
                    "description": video_record.description,
                    "source_type": video_record.source_type,
                    "thumbnail_local_path": video_record.thumbnail_local_path,
                }
```

**Key Points:**
- Looks up video by `audio_file_path` in database
- Only applies to `youtube`, `rss`, `podcast` source types
- Falls back gracefully if no metadata found
- Uses clean title from database (without video ID appended)

### 2. Title Heading Below YAML (audio_processor.py)

Added title heading after YAML frontmatter:

```python
# Add title heading below YAML frontmatter
if video_metadata is not None:
    # Use clean title without video ID for heading
    title_for_heading = video_metadata.get("title", "Unknown")
    lines.append(f"# {title_for_heading}")
    lines.append("")
```

### 3. Channel Mapping for Speaker Attribution (speaker_attribution.yaml)

**Root Cause:** Channel "Zeihan on Geopolitics" was not in channel mappings, so multi-tier speaker attribution system had no known host context.

**Solution:** Added channel mapping:

```yaml
"Zeihan on Geopolitics":
  hosts:
    - full_name: "Peter Zeihan"
      partial_names: ["Peter", "Zeihan"]
      role: "host"
```

**How the system works** (when properly configured):
1. Diarization identifies speakers as SPEAKER_00, SPEAKER_01, etc.
2. `_get_known_hosts_from_channel()` looks up channel → Returns `["Peter Zeihan"]`
3. LLM receives known hosts as context + transcript segments
4. LLM follows rule: "METADATA NAMES WIN: Title/description names ALWAYS beat speech transcription variants"
5. Even if Whisper transcribes "Peter Zine", LLM sees title says "Peter Zeihan" and uses that
6. Confidence boosted to 0.95 when LLM matches speaker to known host

**Why this is the right solution:**
- ✅ Uses the existing multi-tier speaker attribution system as designed
- ✅ Channel mapping is the **intended** way to handle this
- ✅ No additional complexity or fragility added
- ✅ System was just missing the channel configuration

**Lesson learned:** When a sophisticated multi-tier system exists, check if it's fully configured before adding new layers!

## Expected Output Format

After fixes, YouTube video transcripts should look like:

```markdown
---
title: "Ukraine (And Everyone Else) Develops Glide Bombs ｜｜ Peter Zeihan"
source: "https://www.youtube.com/watch?v=7puZUPjOoOI"
video_id: "7puZUPjOoOI"
uploader: "Zeihan on Geopolitics"
upload_date: "October 31, 2025"
duration: "05:03"
view_count: 42357
tags: ["geopolitics", "ukraine", "military technology", "glide bombs"]
youtube_categories: ["News & Politics"]
transcription_date: "October 31, 2025"
transcription_type: "YouTube"
file_format: "mp4"
file_size_mb: 26.12
language: "en"
transcription_model: "large"
text_length: 5895
segments_count: 70
diarization_enabled: true
include_timestamps: False
---

# Ukraine (And Everyone Else) Develops Glide Bombs ｜｜ Peter Zeihan

![Thumbnail](downloads/Thumbnails/Ukraine_And_Everyone_Else_Develops_Glide_Bombs__Peter_Zeihan_7puZUPjOoOI.jpg)

## Description

Analysis of Ukraine's development of glide bomb technology and its implications for global military strategy...

## Full Transcript

(Peter Zeihan): Hey all, Peter Zeihan here coming to you from Colorado...
```

## Benefits

1. **Accurate source attribution** - Properly identifies YouTube/RSS/podcast sources
2. **Rich metadata** - Includes uploader, tags, categories, description, view counts
3. **Better organization** - Clean title headings and descriptions
4. **Correct speaker names** - Proper attribution through channel-based matching
5. **Visual context** - Embedded thumbnails
6. **Database-centric** - Single source of truth for all metadata

## Compatibility

These changes are **backward compatible**:
- Existing transcripts are not affected
- New transcriptions automatically use enhanced metadata
- Re-transcribing existing files will upgrade their metadata
- Falls back gracefully when metadata not available

## Testing

To test the fixes:

1. **Re-transcribe an existing YouTube video:**
   ```bash
   # GUI: Select the downloaded MP4 file in Transcription tab
   # CLI: python -m knowledge_system.cli transcribe <video_file>
   ```

2. **Check the generated markdown:**
   - Title should NOT include video ID
   - Source should be "YouTube" not "Local Audio"
   - Should have uploader, upload_date, view_count, tags
   - Should have thumbnail embedded
   - Should have `# Title` heading below YAML
   - Should have `## Description` section
   - Speakers should have correct names (e.g., "Peter Zeihan")

3. **Verify database lookup:**
   - Check logs for: `✅ Retrieved YOUTUBE metadata from database for...`
   - If missing, check that database has the video record with audio_file_path set

## Related Files Changed

- `src/knowledge_system/processors/audio_processor.py` - Database metadata lookup + title heading
- `config/speaker_attribution.yaml` - Added "Zeihan on Geopolitics" channel mapping

## Future Enhancements

Potential improvements:
1. Auto-detect video ID from filename and lookup metadata
2. Batch re-processing tool to upgrade old transcripts
3. GUI indicator showing metadata richness (basic vs. full)
4. Metadata validation and cleanup utilities
