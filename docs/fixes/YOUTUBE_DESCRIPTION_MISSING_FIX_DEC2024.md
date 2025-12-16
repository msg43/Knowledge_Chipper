# Fix: Missing YouTube Description in Transcripts

**Date:** December 9, 2024
**Issue:** YouTube description section missing from transcript markdown files
**Status:** ✅ Fixed

## Problem

Transcripts were being generated without the "## YouTube Description" section, even though:
1. The code was correctly configured to include descriptions
2. YouTube downloads were extracting descriptions properly
3. The markdown generation function expected descriptions in `source_metadata`

## Root Cause

The `media_sources` table in the database was empty (0 records). This caused:

1. When transcription occurred, the code tried to retrieve video metadata from the database
2. Since no records existed, `source_record` was `None`
3. Without `source_record`, no `source_metadata` was created or passed to the markdown generator
4. The markdown was generated without YouTube URL, uploader, description, tags, or other metadata

**File:** `src/knowledge_system/gui/tabs/transcription_tab.py`
**Lines:** 1328-1332 (before fix)

```python
if not source_record:
    logger.debug(f"⚠️ No metadata found for file: {filename}")
    logger.debug(
        f"   This is normal for local files or files downloaded outside the app"
    )
```

The code would simply log a warning and continue without metadata.

## Solution

Added automatic YouTube metadata fetching when database is empty.

**Modified File:** `src/knowledge_system/gui/tabs/transcription_tab.py`
**Lines:** 1328-1385 (after fix)

### How It Works

1. **Detection:** When transcribing a file, if no `source_record` is found in database but a `source_id` is extracted from filename
2. **Fetch:** Use `yt_dlp` to fetch video metadata directly from YouTube (without downloading)
3. **Save:** Store the metadata in the database for future use
4. **Use:** Pass the metadata to the markdown generator

### Code Changes

```python
if not source_record:
    logger.debug(f"⚠️ No metadata found for file: {filename}")
    logger.debug(
        f"   This is normal for local files or files downloaded outside the app"
    )
    
    # 🔧 FIX: If this is a YouTube video with no metadata in database,
    # try to fetch it from YouTube so we can include description in markdown
    if source_id:
        logger.info(f"🔍 Attempting to fetch YouTube metadata for {source_id}...")
        try:
            import yt_dlp
            
            video_url = f"https://www.youtube.com/watch?v={source_id}"
            
            # Fetch metadata only (no download)
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                if info:
                    # Create source_record in database with metadata
                    tags = info.get("tags", []) or []
                    video_metadata = {
                        "uploader": info.get("uploader", ""),
                        "uploader_id": info.get("uploader_id", ""),
                        "upload_date": info.get("upload_date", ""),
                        "description": info.get("description", ""),
                        "duration_seconds": info.get("duration"),
                        "view_count": info.get("view_count"),
                        "like_count": info.get("like_count"),
                        "comment_count": info.get("comment_count"),
                        "tags_json": tags,
                        "categories_json": info.get("categories", []),
                        "thumbnail_url": info.get("thumbnail", ""),
                        "source_type": "youtube",
                        "status": "metadata_only",
                    }
                    
                    # Save to database
                    source_record = db_service.create_source(
                        source_id=source_id,
                        title=info.get("title", f"YouTube Video {source_id}"),
                        url=video_url,
                        **video_metadata,
                    )
                    
                    if source_record:
                        logger.info(f"✅ Successfully fetched and saved YouTube metadata for {source_id}")
                    else:
                        logger.warning(f"⚠️ Failed to save metadata to database for {source_id}")
                else:
                    logger.warning(f"⚠️ Could not fetch YouTube info for {source_id}")
                    
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch YouTube metadata for {source_id}: {e}")
            logger.debug(f"   Error details: {e}", exc_info=True)
```

## Benefits

1. **Automatic Recovery:** No manual intervention needed when database is empty
2. **Complete Metadata:** Transcripts now include:
   - YouTube Description
   - Video URL
   - Uploader information
   - Upload date
   - Duration
   - View count
   - Tags and categories
3. **Database Population:** Metadata is saved to database for future use
4. **Backward Compatible:** Works with existing transcription workflow

## Testing

To test the fix:

1. Ensure `media_sources` table is empty: `DELETE FROM media_sources;`
2. Transcribe a YouTube video audio file (with video ID in filename)
3. Check the generated markdown file for:
   - Complete YAML frontmatter with metadata
   - `## YouTube Description` section with full description

## Related Files

- `src/knowledge_system/gui/tabs/transcription_tab.py` - Main fix location
- `src/knowledge_system/processors/audio_processor.py` - Markdown generation (lines 1528-1541)
- `src/knowledge_system/processors/youtube_download.py` - Download process that normally saves metadata
- `CHANGELOG.md` - Documented in Unreleased section

## Notes

- The fix only activates when a `source_id` can be extracted from the filename
- For local audio files without YouTube IDs, normal behavior continues (no metadata)
- Requires internet connection to fetch metadata from YouTube
- Uses `yt_dlp` for YouTube API interaction (same library used for downloads)
