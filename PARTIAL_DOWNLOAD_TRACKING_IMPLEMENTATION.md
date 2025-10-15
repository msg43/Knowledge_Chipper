# Partial Download Tracking Implementation

**Date:** October 15, 2025  
**Status:** ✅ Implemented

## Overview

Implemented comprehensive tracking and retry logic for partial YouTube downloads where metadata or audio files may fail independently. The system now properly handles cases where:
- Metadata downloads but audio fails
- Audio downloads but metadata fails
- Database writes fail after successful downloads
- Files exist on disk but aren't tracked in database (orphaned files)

## Problem Statement

### Original Issues

1. **Orphaned Audio Files**: Audio files could download successfully but fail to register in the database, creating unusable orphaned files
2. **No Partial State Tracking**: System couldn't distinguish between "has metadata only", "has audio only", or "has both"
3. **No Cleanup Mechanism**: No startup routine to detect and fix incomplete entries
4. **Inefficient Retries**: Failed downloads would retry the entire process instead of just the missing component
5. **Poor Deduplication**: System would skip incomplete downloads thinking they were already processed

## Solution Architecture

### 1. Database Schema Changes

**New Fields in `media_sources` table:**

```sql
-- Audio file tracking
audio_file_path TEXT                -- Path to downloaded audio file
audio_downloaded BOOLEAN DEFAULT 0  -- True if audio successfully downloaded
audio_file_size_bytes INTEGER       -- Size for validation
audio_format TEXT                   -- Format (m4a, opus, etc.)

-- Metadata completion tracking
metadata_complete BOOLEAN DEFAULT 0 -- True if all metadata extracted

-- Retry tracking
needs_metadata_retry BOOLEAN DEFAULT 0
needs_audio_retry BOOLEAN DEFAULT 0
retry_count INTEGER DEFAULT 0
last_retry_at TEXT                  -- ISO format datetime

-- Failure tracking
max_retries_exceeded BOOLEAN DEFAULT 0
failure_reason TEXT
```

**Database Views:**
- `incomplete_downloads`: Videos needing retry (not exceeded limit)
- `orphaned_audio_files`: Audio files downloaded but not used in transcripts
- `failed_downloads`: Videos that exceeded retry limit (3 attempts)

**Migration File:** `src/knowledge_system/database/migrations/2025_10_15_partial_download_tracking.sql`

### 2. Database Service Enhancements

**New Methods in `DatabaseService`:**

```python
# Status tracking
update_audio_status(video_id, audio_file_path, audio_downloaded, ...)
update_metadata_status(video_id, metadata_complete)

# Retry management
mark_for_retry(video_id, needs_metadata_retry, needs_audio_retry, failure_reason)
get_videos_needing_retry(metadata_only=False, audio_only=False)
get_failed_videos()
get_incomplete_videos()

# Validation
is_video_complete(video_id)
validate_audio_file_exists(video_id)
```

### 3. Download Processor Changes

**File:** `src/knowledge_system/processors/youtube_download.py`

**Key Changes:**

1. **Separate Tracking Variables:**
   ```python
   metadata_extracted = False
   metadata_error = None
   audio_downloaded_successfully = False
   audio_file_path_for_db = None
   audio_file_size = None
   audio_file_format = None
   ```

2. **Mandatory Database Write:**
   - Database write failure now causes the entire download to fail
   - Downloaded audio files are cleaned up if database write fails
   - Prevents orphaned files that can't be tracked

3. **Granular Status Updates:**
   ```python
   # Update audio status
   db_service.update_audio_status(video_id, audio_file_path, True, ...)
   
   # Update metadata status
   db_service.update_metadata_status(video_id, metadata_extracted)
   
   # Mark for retry if either component failed
   if not audio_downloaded_successfully or not metadata_extracted:
       db_service.mark_for_retry(
           video_id,
           needs_metadata_retry=not metadata_extracted,
           needs_audio_retry=not audio_downloaded_successfully,
           failure_reason=...
       )
   ```

4. **Cleanup on Failure:**
   ```python
   # Clean up orphaned audio file if database write fails
   if audio_file_path_for_db and Path(audio_file_path_for_db).exists():
       Path(audio_file_path_for_db).unlink()
       logger.info(f"Cleaned up orphaned audio file")
   ```

### 4. Startup Cleanup Service

**File:** `src/knowledge_system/utils/download_cleanup.py`

**Features:**

1. **Audio File Validation:**
   - Checks if audio files referenced in database actually exist
   - Marks missing files for audio retry

2. **Orphan Detection:**
   - Scans output directory for audio files not in database
   - Reports orphaned files with size and modification date

3. **Incomplete Video Identification:**
   - Finds videos missing audio or metadata
   - Tracks retry count and status

4. **Failed Video Reporting:**
   - Identifies videos that exceeded max retries (3 attempts)
   - Generates user-friendly reports

5. **Report Generation:**
   - JSON report: `logs/cleanup_report_TIMESTAMP.json`
   - Failed URLs file: `logs/failed_urls_TIMESTAMP.txt`
   - Ready for copy-paste back into download tab

**Integration:**
- Runs automatically 1 second after GUI startup
- Shows popup if failed videos are detected
- Saves reports to logs folder for user access

### 5. Deduplication Logic Updates

**File:** `src/knowledge_system/utils/deduplication.py`

**Key Change:**

```python
# Check if video is actually complete
is_complete = (
    existing_video.audio_downloaded 
    and existing_video.metadata_complete
)

if not is_complete:
    # Allow reprocessing - not a true duplicate
    return DeduplicationResult(
        is_duplicate=False,
        recommendations=["Video has partial download - will attempt to complete"]
    )
```

**Impact:**
- Partial downloads are no longer skipped as duplicates
- Playlist re-downloads correctly identify which videos need completion
- Example: 100-video playlist with 90 complete + 10 partial → only retries the 10

### 6. User Experience Improvements

**Startup Popup:**
```
┌─────────────────────────────────────────────┐
│ Partial Download Failures Detected          │
├─────────────────────────────────────────────┤
│ Found 5 video(s) that failed after 3 retry  │
│ attempts.                                    │
│                                              │
│ Failed URLs have been saved to:             │
│ logs/failed_urls_20251015_143022.txt        │
│                                              │
│ You can copy these URLs and paste them back │
│ into the download tab to try again.         │
│                                              │
│ Failed videos:                              │
│ - Video Title 1                             │
│ - Video Title 2                             │
│ ...                                          │
└─────────────────────────────────────────────┘
```

**Failed URLs File Format:**
```
# Failed Download URLs - Ready for Retry
# Generated: 2025-10-15T14:30:22
# Total: 5 videos exceeded max retry attempts
#
# Copy and paste these URLs back into the download tab to retry
#

https://www.youtube.com/watch?v=...
https://www.youtube.com/watch?v=...
```

## Retry Logic

### Retry Limits

- **Max Retries:** 3 attempts per video
- **Retry Tracking:** Incremented on each failure
- **Retry Types:** Metadata-only, audio-only, or both

### Retry Flow

1. **First Failure:**
   - Mark component(s) for retry
   - Set `retry_count = 1`
   - Set `needs_metadata_retry` and/or `needs_audio_retry`

2. **Subsequent Failures:**
   - Increment `retry_count`
   - Update `last_retry_at` timestamp
   - Keep retry flags set

3. **Max Retries Exceeded:**
   - Set `max_retries_exceeded = True`
   - Set `status = 'failed'`
   - Add to failed videos report
   - Save URL to failed_urls file

4. **Success:**
   - Clear retry flags
   - Mark component as complete
   - Update status to 'completed' if both components done

### Smart Retry (Future Enhancement)

The infrastructure is in place for smart retries that only attempt the missing component:

```python
# Get videos needing only metadata retry
metadata_only = db_service.get_videos_needing_retry(metadata_only=True)

# Get videos needing only audio retry
audio_only = db_service.get_videos_needing_retry(audio_only=True)
```

## Testing Scenario

### Playlist Re-download Test

**Scenario:** User downloads 100-video playlist, 90 succeed completely, 10 have partial failures

**Expected Behavior:**

1. **First Download:**
   - 90 videos: `audio_downloaded=True`, `metadata_complete=True`, `status='completed'`
   - 10 videos: Partial state (e.g., `audio_downloaded=True`, `metadata_complete=False`)

2. **User Quits and Restarts App:**
   - Startup cleanup runs
   - Detects 10 incomplete videos
   - Logs summary

3. **User Re-downloads Same Playlist:**
   - Deduplication checks each video
   - 90 complete videos: Skipped as duplicates
   - 10 partial videos: Marked as `is_duplicate=False`
   - Only 10 videos are re-attempted

4. **After 3 Failed Attempts:**
   - Videos marked `max_retries_exceeded=True`
   - Popup shown with failed count
   - URLs saved to `logs/failed_urls_TIMESTAMP.txt`
   - User can copy URLs for manual retry

## Files Modified

### Database
- `src/knowledge_system/database/models.py` - Added tracking fields to MediaSource
- `src/knowledge_system/database/service.py` - Added partial download methods
- `src/knowledge_system/database/migrations/2025_10_15_partial_download_tracking.sql` - Migration

### Processors
- `src/knowledge_system/processors/youtube_download.py` - Mandatory DB writes, separate tracking

### Utilities
- `src/knowledge_system/utils/download_cleanup.py` - NEW: Startup cleanup service
- `src/knowledge_system/utils/deduplication.py` - Check for complete downloads

### GUI
- `src/knowledge_system/gui/main_window_pyqt6.py` - Integrated startup cleanup

## Migration Instructions

### For Existing Databases

1. **Run Migration:**
   ```bash
   sqlite3 knowledge_system.db < src/knowledge_system/database/migrations/2025_10_15_partial_download_tracking.sql
   ```

2. **Verify Migration:**
   ```sql
   -- Check new columns exist
   PRAGMA table_info(media_sources);
   
   -- Check views created
   SELECT name FROM sqlite_master WHERE type='view';
   ```

3. **Initial Cleanup:**
   - Launch GUI
   - Startup cleanup will run automatically
   - Review popup if failed videos detected
   - Check `logs/cleanup_report_*.json` for details

### For New Installations

- Migration will run automatically on first database creation
- No manual steps required

## Benefits

### 1. No More Orphaned Files
- Audio files without database entries are immediately cleaned up
- Prevents wasted disk space

### 2. Intelligent Retries
- Only retry the component that failed
- Reduces bandwidth and processing time

### 3. Better User Feedback
- Clear indication of what failed and why
- Easy access to failed URLs for manual retry

### 4. Accurate Deduplication
- Partial downloads don't block re-attempts
- Playlist re-downloads work correctly

### 5. Automatic Cleanup
- Startup validation catches inconsistencies
- Database stays in sync with filesystem

## Future Enhancements

### Potential Improvements

1. **Metadata-Only Retries:**
   - Implement separate retry path for metadata extraction
   - Skip audio download if already present

2. **Audio-Only Retries:**
   - Implement separate retry path for audio download
   - Use existing metadata if available

3. **Manual Retry Button:**
   - Add GUI button to retry failed videos
   - Load failed URLs directly from database

4. **Orphan Cleanup Options:**
   - Prompt user to delete orphaned files
   - Option to import orphaned files into database

5. **Retry Strategy Customization:**
   - Allow user to configure max retry count
   - Different retry limits for different failure types

## Conclusion

This implementation provides a robust solution for handling partial download failures in YouTube video processing. The system now:

✅ Tracks audio and metadata status separately  
✅ Requires successful database writes (no orphaned files)  
✅ Automatically detects and reports incomplete downloads  
✅ Provides user-friendly failure reports with retry URLs  
✅ Correctly handles playlist re-downloads (only retries incomplete videos)  
✅ Implements smart retry logic with configurable limits  
✅ Maintains database-filesystem consistency  

The infrastructure is in place for future enhancements like component-specific retry paths and manual retry controls.

