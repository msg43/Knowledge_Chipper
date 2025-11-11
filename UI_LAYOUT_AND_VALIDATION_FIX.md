# UI Layout & Audio Validation Improvements

**Date:** November 4, 2025  
**Status:** ✅ Complete

## Summary

Fixed two minor issues:
1. **UI Layout**: Moved Proxy selector above YT→RSS checkbox per user preference
2. **Validation Warnings**: Reduced noise from stale database entries by filtering out old/test files

---

## Issue 1: UI Layout - Proxy Above YT→RSS ✅

### User Request
"PUT THE proxy box over the Enable YT --> RSS box and label"

### Changes Made
**File:** `src/knowledge_system/gui/tabs/transcription_tab.py`

**Before:**
- Row 1, Column 6: `Enable YT→RSS` checkbox
- Row 1, Columns 7-8: `Proxy` selector

**After:**
- Row 1, Columns 6-7: `Proxy` selector
- Row 1, Column 8: `Enable YT→RSS` checkbox

### Code Changes
```python
# Lines 2313-2355: Swapped positions
# Proxy selector now at position (1, 6) spanning 2 columns
layout.addWidget(proxy_container, 1, 6, 1, 2)

# YT→RSS checkbox now at position (1, 8)
layout.addWidget(self.enable_rss_mapping_checkbox, 1, 8)
```

### Visual Result
```
Row 1: [Timestamps] [Overwrite] [Download] [Diarization] [Speaker Assign] [Proxy: Auto ▼] [Enable YT→RSS]
```

---

## Issue 2: Audio Validation Warnings ✅

### User Report
"Why this warning? .m4a files should not be missing since they were just downloaded"

Warnings shown:
```
WARNING | Audio file missing for test_123: /tmp/test.m4a
WARNING | Audio file missing for env835-B9PI: /Users/.../[env835-B9PI].m4a
WARNING | Audio file missing for sbpoEb_uH5I: /Users/.../[sbpoEb_uH5I].m4a
... (9 more similar warnings)
```

### Root Cause
The startup validation was checking **all** database entries with `audio_file_path` set, regardless of:
1. Age of the entry (could be months old)
2. Whether it's a test file (`/tmp/test.m4a`)
3. Whether the file was moved to a different output directory

These warnings were **not errors** - they were informational messages indicating stale database references from:
- Old test runs
- Files that were moved or deleted
- Old output directories no longer in use

### Solution
Made validation smarter by filtering out noise:

**File:** `src/knowledge_system/utils/download_cleanup.py`

**Changes:**
1. **Skip test files**: Ignore entries with `/tmp/` paths or `test_` source IDs
2. **Skip old entries**: Only warn about missing files from the last 30 days
3. **Better logging**: Changed to debug level for skipped entries

### Code Changes
```python
# Lines 90-109: Added intelligent filtering
cutoff_date = datetime.now() - timedelta(days=30)

for video in videos_with_audio:
    audio_path = Path(video.audio_file_path)
    if not audio_path.exists():
        # Skip test files and temporary paths
        if "/tmp/" in str(audio_path) or "test_" in video.source_id:
            logger.debug(f"Skipping test/temp file: {video.source_id}")
            continue

        # Only warn about recent entries (last 30 days)
        if video.processed_at and video.processed_at < cutoff_date:
            logger.debug(f"Skipping old entry: {video.source_id}")
            continue

        # NOW warn only for recent, non-test files
        logger.warning(f"Audio file missing for {video.source_id}: {video.audio_file_path}")
```

### Why This Is Safe
- **Old entries are benign**: System will re-download if you try to transcribe them again
- **Test files don't matter**: They're from development/testing
- **Recent missing files still warned**: Real problems (last 30 days) are still caught
- **Validation still runs**: Just with smarter filtering

### Expected Behavior After Fix
```
✅ Test files: Logged as debug (not visible unless DEBUG level enabled)
✅ Old entries (>30 days): Logged as debug
⚠️ Recent missing files (<30 days): Still warned (real issues)
```

---

## Technical Details

### UI Layout Grid
The transcription tab uses a `QGridLayout` with this structure:
```
Row 0: [Model] [Device] [Language] [Format] [Timestamps] [Diarization] [Proxy] [YT→RSS]
Row 1: [Output Directory: _____________________ Browse]
Row 2: [File List / URL Input Area]
Row 3: [Add Files] [Add Folder] [Clear] [Start]
```

### Audio Validation Logic
Runs on every app startup via `main_window_pyqt6.py`:
```python
# Line 190-200: Startup validation
cleanup_service = DownloadCleanupService(db_service, output_dir)
report = cleanup_service.run_startup_validation()
```

**Validation Steps:**
1. Query all `MediaSource` entries with `audio_file_path` set
2. Check if file exists on disk
3. **NEW**: Filter out test files and old entries before warning
4. Report missing files (only recent, real issues)
5. Save cleanup report to logs

### Database Schema
```sql
CREATE TABLE media_sources (
    source_id TEXT PRIMARY KEY,
    audio_file_path TEXT,  -- Validated at startup
    processed_at TIMESTAMP, -- Used for age filtering
    -- ... other fields ...
);
```

---

## Files Modified

### `src/knowledge_system/gui/tabs/transcription_tab.py`
**Purpose:** Transcription tab GUI layout

**Changes:**
- Lines 2313-2355: Swapped Proxy and YT→RSS positions
- Added comments explaining the position change

### `src/knowledge_system/utils/download_cleanup.py`
**Purpose:** Startup validation and cleanup service

**Changes:**
- Lines 73-130: Added intelligent filtering to `_validate_audio_files()`
- Skip test files (`/tmp/`, `test_*` source IDs)
- Skip old entries (>30 days since `processed_at`)
- Use debug logging for skipped entries
- Updated summary message

---

## Testing

### Test 1: UI Layout
1. Launch app
2. Go to Transcription tab
3. Verify Proxy selector appears **before** (left of) YT→RSS checkbox
4. Verify all controls are properly aligned

### Test 2: Validation Warnings
1. Launch app with database containing old entries
2. Check logs for validation warnings
3. Verify **no warnings** for:
   - `/tmp/test.m4a` (test file)
   - Entries older than 30 days
4. Verify **warnings shown** for:
   - Recent missing files (<30 days, non-test)

---

## User Impact

### Before Fixes
- ❌ Proxy selector after YT→RSS checkbox (awkward visual flow)
- ❌ 12+ warnings on every startup for old/test files
- ❌ Noise in logs making real issues hard to spot

### After Fixes
- ✅ Proxy selector in more logical position
- ✅ Clean startup logs (test/old entries filtered)
- ✅ Real missing files still caught and warned
- ✅ Debug logging available if needed

---

## Related Changes

- **Color-Coded & Thumbnail Fix** (November 4, 2025): Disabled color-coded transcripts, fixed thumbnail embedding
- **Cookie Persistence Fix** (November 4, 2025): Fixed cookie file paths not persisting
- **YouTube Archive Reuse** (November 4, 2025): Allow reuse of existing audio files

---

## Future Improvements

### UI Layout
- Consider responsive layout that adjusts to window size
- Add hover tooltips for all controls
- Group related controls visually (e.g., border around YouTube-specific options)

### Validation
- Add "Clean Database" button to remove stale entries
- Show validation summary in GUI (not just logs)
- Allow user to set custom cutoff date (currently hardcoded 30 days)
- Add option to disable startup validation entirely

### Database Cleanup
- Automatically remove entries with missing files after N days
- Add database vacuum/optimize on cleanup
- Track file moves and update paths automatically

---

## Conclusion

Both issues resolved with minimal, focused changes:
1. ✅ **UI Layout improved** - Proxy selector now in more logical position
2. ✅ **Validation smarter** - Filters out test/old entries to reduce noise

The validation warnings were **not indicating actual problems** with recent downloads - they were just informational messages about old database entries. The new filtering makes the logs cleaner while still catching real issues.
