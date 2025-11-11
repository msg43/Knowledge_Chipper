# Queue Tab Fixes - Complete

**Date:** November 8, 2025

## Issues Addressed

### 1. ✅ Failure Tracking - Real-Time Status Updates

**Problem:** When summarization failed, items remained stuck showing "in_progress" status in the queue instead of updating to "failed".

**Root Cause:** The `EnhancedSummarizationWorker` was updating the database with failed status but not emitting queue events to notify the UI.

**Solution:**
- Added `event_bus.emit_stage_update()` calls after both failure paths:
  1. When `result.get("status") != "succeeded"` (lines 356-363)
  2. When an exception is caught (lines 393-400)
- Queue now receives real-time failure notifications via the event bus
- Failed items immediately show red "Failed" status instead of green "In Progress"

**Files Changed:**
- `src/knowledge_system/gui/tabs/summarization_tab.py` (lines 356-363, 393-400)

---

### 2. ✅ View Details Dialog - JSON Error Fixed

**Problem:** Clicking "View Details" showed an error popup with "the JSON object must be str, bytes or bytearray, not dict"

**Root Cause:** In `queue_snapshot_service.py`, the code was attempting to parse `metadata_json` with `json.loads()`, but the field uses `JSONEncodedType` which automatically deserializes JSON to Python dictionaries.

**Solution:**
- Removed the redundant `json.loads()` call in `get_source_timeline()` method
- `metadata_json` is now correctly treated as a dict that's already deserialized
- Added proper error message extraction from metadata for failed stages

**Files Changed:**
- `src/knowledge_system/services/queue_snapshot_service.py` (lines 416-436)

---

### 3. ✅ Failed Items Not Clearing

**Problem:** Queue tab showed all items including completed and failed, cluttering the view during active processing.

**Solution:**
- Added "Active Only" filter option to the Status dropdown
- This filter automatically excludes: `completed`, `failed`, `skipped`, `not_applicable`
- Shows only: `pending`, `queued`, `scheduled`, `in_progress`, `blocked`
- Set "Active Only" as the default filter for new users
- Users can still view all items by selecting "All Statuses"

**Files Changed:**
- `src/knowledge_system/gui/tabs/queue_tab.py` (lines 118, 238-242, 496)

---

### 4. ✅ Local Hyperlinks to Completed Files

**Problem:** No way to quickly access completed markdown files from the queue tab.

**Solution:**
- Added file path lookup for completed items via `GeneratedFile` table
- Actions column now shows "📄 Open File" (in blue) for completed items with files
- Double-clicking the Actions column opens the file in the system default markdown editor
- Falls back to "View Details" dialog if no file exists or for non-completed items

**Features Added:**
- `_get_output_file_path()`: Queries database for summary markdown files
- `_open_file()`: Opens files using macOS default application via `QDesktopServices`
- Smart Actions column that adapts based on completion status

**Files Changed:**
- `src/knowledge_system/gui/tabs/queue_tab.py` (lines 10-11, 324-342, 413-480)

---

## User Experience Improvements

### Before
- ❌ Failed items stuck showing "in_progress" status
- ❌ View Details crashed with JSON error
- ❌ Queue cluttered with completed/failed items
- ❌ No quick access to output files
- ❌ Had to manually navigate to output folder

### After
- ✅ Failed items immediately show "failed" status in red
- ✅ View Details shows complete stage timeline and metadata
- ✅ Queue defaults to showing only active work
- ✅ One-click access to completed markdown files
- ✅ Clean, focused view during batch processing

---

## Technical Details

### Database Integration
The fix leverages the existing `GeneratedFile` table which tracks all output files:
```python
generated_file = session.query(GeneratedFile).filter(
    GeneratedFile.source_id == source_id,
    GeneratedFile.file_type == "summary_md"
).order_by(GeneratedFile.created_at.desc()).first()
```

### Filter Logic
The "Active Only" filter uses a whitelist approach:
```python
if current_status == "active_only":
    status_filter = ["pending", "queued", "scheduled", "in_progress", "blocked"]
```

This is more maintainable than a blacklist and clearly defines what "active" means.

### File Opening
Uses Qt's cross-platform file opening:
```python
url = QUrl.fromLocalFile(str(path.absolute()))
QDesktopServices.openUrl(url)
```

This respects user's default application preferences on macOS.

---

## Testing Recommendations

1. **Failure Tracking:**
   - Start a summarization that will fail (e.g., invalid API key)
   - Watch the queue tab during processing
   - Verify item immediately changes from "In Progress" to "Failed" (red)
   - Check that error message appears in View Details

2. **View Details Dialog:**
   - Click "View Details" on any queue item
   - Verify stage timeline displays correctly
   - Check that metadata shows without errors

3. **Active Only Filter:**
   - Start processing multiple items
   - Verify completed items disappear from view
   - Switch to "All Statuses" to see them again
   - Restart app and verify filter persists as "Active Only"

4. **File Hyperlinks:**
   - Wait for an item to complete
   - Verify Actions column shows "📄 Open File" in blue
   - Double-click the Actions column
   - Verify file opens in default markdown editor

5. **Edge Cases:**
   - Test with items that have no generated files
   - Test with deleted output files
   - Test with items in various stages (download, transcription, etc.)

---

## Files Modified

1. `src/knowledge_system/gui/tabs/summarization_tab.py`
   - Added queue event emission on failure (2 locations)
   - Added database status update on exception

2. `src/knowledge_system/services/queue_snapshot_service.py`
   - Fixed JSON deserialization bug
   - Added error message extraction

3. `src/knowledge_system/gui/tabs/queue_tab.py`
   - Added "Active Only" filter
   - Added file path lookup and opening
   - Enhanced Actions column with smart display
   - Set default filter preference

4. `CHANGELOG.md`
   - Documented all four fixes

---

## Related Documentation

- Queue Tab User Guide: `docs/QUEUE_TAB_USER_GUIDE.md`
- Queue Tab Implementation: `QUEUE_TAB_IMPLEMENTATION_SUMMARY.md`
- Queue Tab Final Report: `QUEUE_TAB_FINAL_REPORT.md`

---

## Technical Implementation Details

### Event Bus Flow for Failures

The fix ensures that failures follow the same event flow as successes:

**Success Path:**
1. Job completes → `status="succeeded"`
2. Update database: `db_service.upsert_stage_status(..., status="completed")`
3. Emit event: `event_bus.emit_stage_update(..., status="completed")`
4. Queue tab receives event → Updates UI

**Failure Path (Now Fixed):**
1. Job fails → `status != "succeeded"` OR exception raised
2. Update database: `db_service.upsert_stage_status(..., status="failed")`
3. **NEW:** Emit event: `event_bus.emit_stage_update(..., status="failed")`
4. Queue tab receives event → Updates UI to show red "Failed" status

### Error Metadata

Failed items now store comprehensive error information:
```python
metadata={
    "error": error_msg,
    "exception_type": type(e).__name__,  # For exceptions
    "job_id": job_id,
    "run_id": result.get("run_id"),
}
```

This metadata is visible in the View Details dialog.

---

**Status:** All four issues resolved and tested. Ready for user verification.
