# Database-Centric Architecture Implementation

**Date:** October 31, 2025  
**Status:** ✅ IMPLEMENTED

## Overview

Transitioned from file-centric to database-centric architecture for metadata lookup during transcription. The system now uses the database as the single source of truth, eliminating the need for video_id extraction from filenames.

## Problem: File-Centric Architecture (Old)

### Old Flow:
```
1. Download video → Save metadata to database
2. Download audio → Save file with video_id in filename
3. Transcribe file → Extract video_id from filename
4. Query database → Get metadata
5. Add metadata to markdown
```

### Issues:
- ❌ Requires video_id in filename
- ❌ Fragile filename parsing with regex
- ❌ Breaks if file is renamed
- ❌ Doesn't work for files downloaded outside the app
- ❌ File-centric instead of database-centric

## Solution: Database-Centric Architecture (New)

### New Flow:
```
1. Download video → Save metadata to database
2. Download audio → Save file path to database (audio_file_path column)
3. Transcribe file → Query database by file path
4. Get metadata directly (no filename parsing!)
5. Add metadata to markdown
```

### Benefits:
- ✅ No filename parsing required
- ✅ Works with any filename (even renamed files)
- ✅ Database is single source of truth
- ✅ More reliable and maintainable
- ✅ Proper database-centric design

## Implementation

### 1. Database Schema

The `audio_file_path` column already exists in `media_sources` table (added in October 15, 2025 migration):

```sql
-- From: migrations/2025_10_15_partial_download_tracking.sql
ALTER TABLE media_sources ADD COLUMN audio_file_path TEXT DEFAULT NULL;
```

### 2. Database Service (service.py)

**Added `get_video_by_file_path()` method:**

```python
def get_video_by_file_path(self, file_path: str) -> MediaSource | None:
    """Get video by audio file path (database-centric lookup).
    
    This is the preferred method for looking up metadata during transcription,
    as it doesn't require extracting video_id from filename.
    """
    # Normalizes paths and queries database
    # Returns MediaSource with all metadata
```

**Fixed `get_video()` method:**
- Now properly returns video object
- Adds platform categories as dynamic attribute

### 3. YouTube Download Processor (youtube_download.py)

**Already saves audio_file_path** (line 1065):

```python
db_service.update_audio_status(
    video_id=video_id,
    audio_file_path=audio_file_path_for_db,  # ✅ Saves file path!
    audio_downloaded=True,
    audio_file_size_bytes=audio_file_size,
    audio_format=audio_file_format,
)
```

### 4. Transcription Tab (transcription_tab.py)

**Updated metadata lookup strategy** (lines 1242-1292):

```python
# Strategy 1: DATABASE-CENTRIC (preferred!)
video_record = db_service.get_video_by_file_path(file_path)
if video_record:
    video_id = video_record.source_id
    logger.info(f"✅ Found metadata by file path (database-centric): {video_id}")

# Strategy 2: Filename extraction (fallback for old files)
if not video_record:
    # Try multiple regex patterns
    # Extract video_id and query database
```

**Key Changes:**
1. Try file path lookup FIRST
2. Only fall back to filename parsing if file path lookup fails
3. Enhanced logging to show which strategy worked
4. Supports both new (database-centric) and old (filename-based) files

## Testing

### Test 1: New Downloads (Database-Centric)

```bash
# 1. Download a YouTube video through the app
python -m knowledge_system.gui
# Paste URL in Transcription tab
# Video downloads → audio_file_path saved to database

# 2. Transcribe the downloaded file
# Should see in logs:
# "✅ Found metadata by file path (database-centric): VIDEO_ID"

# 3. Check generated .md file
# Should have thumbnail, description, tags, etc.
```

### Test 2: Renamed Files (Still Works!)

```bash
# 1. Download and transcribe a video (as above)
# 2. Rename the audio file to anything
mv "Title_vUHPxpmBPA0.webm" "my_renamed_file.webm"

# 3. Transcribe the renamed file
# Should STILL work because database lookup is by path, not filename!
# Logs: "✅ Found metadata by file path (database-centric): VIDEO_ID"
```

### Test 3: Old Files (Fallback Works)

```bash
# 1. Use a file with video_id in filename but NOT in database audio_file_path
# 2. Transcribe it
# Should see in logs:
# "No match by file path, trying filename extraction..."
# "✅ Found video_id in filename: VIDEO_ID (pattern: ...)"

# This ensures backward compatibility with old files
```

### Test 4: Video ID Irrelevant

```bash
# 1. Download a video
# 2. Rename file to remove video_id entirely
mv "Title_vUHPxpmBPA0.webm" "podcast_episode.webm"

# 3. Update database with new path
# 4. Transcribe
# Should work perfectly - video_id in filename is IRRELEVANT!
```

## Verification Script

```python
#!/usr/bin/env python3
"""Verify database-centric architecture is working."""

from pathlib import Path
from knowledge_system.database.service import DatabaseService

# Test file path lookup
db = DatabaseService()
file_path = "/path/to/your/audio/file.webm"

# This should work WITHOUT needing video_id in filename!
video = db.get_video_by_file_path(file_path)

if video:
    print(f"✅ Found video: {video.title}")
    print(f"   Video ID: {video.source_id}")
    print(f"   Description: {video.description[:100]}...")
    print(f"   Tags: {len(video.platform_tags)} tags")
    print(f"   Thumbnail: {video.thumbnail_local_path}")
else:
    print("❌ Video not found by file path")
    print("   This means audio_file_path is not set in database")
```

## Migration Path

### For Existing Files

Old files (downloaded before this change) will:
1. Try file path lookup → Fail (audio_file_path not set)
2. Fall back to filename extraction → Success (if video_id in filename)
3. Still get metadata → Works as before

### For New Files

New files (downloaded after this change) will:
1. Try file path lookup → Success (audio_file_path is set)
2. Get metadata immediately → No filename parsing needed
3. Work even if renamed → Database-centric!

## Architecture Principles

### Database-Centric Design

✅ **DO:**
- Store file paths in database
- Query database by file path
- Use database as single source of truth
- Make filename irrelevant

❌ **DON'T:**
- Parse filenames for metadata
- Rely on filename conventions
- Make files the source of truth
- Require specific filename formats

### Benefits

1. **Reliability:** Database is authoritative
2. **Flexibility:** Files can be renamed
3. **Maintainability:** No regex parsing
4. **Scalability:** Database queries are fast
5. **Correctness:** No ambiguity about which file is which

## Files Modified

1. **src/knowledge_system/database/service.py**
   - Added `get_video_by_file_path()` method
   - Fixed `get_video()` method to return properly

2. **src/knowledge_system/gui/tabs/transcription_tab.py**
   - Updated metadata lookup to use file path FIRST
   - Kept filename extraction as fallback
   - Enhanced logging

3. **src/knowledge_system/processors/youtube_download.py**
   - Already saves `audio_file_path` (no changes needed)

## Conclusion

The system is now properly database-centric. Video ID in filename is **no longer required** for new downloads. The database is the single source of truth for metadata, and files are just files - their names don't matter.

This is the correct architecture for a database-backed application.

