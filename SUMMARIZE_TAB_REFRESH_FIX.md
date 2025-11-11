# Summarize Tab Database List Refresh Fix

**Date**: November 10, 2025  
**Issue**: Newly transcribed YouTube URLs not appearing in Summarize tab's database browser

## Problem

When users transcribed a new YouTube URL in the Transcription tab and then navigated to the Summarize tab, the newly transcribed content would not appear in the "Summarize from Database" list, even though:
1. The transcription completed successfully
2. The transcript was saved to the database
3. A MediaSource record was created
4. The data was queryable from the database

The user had to manually click the "🔄 Refresh" button to see the new transcript.

## Root Cause

The Summarize tab's database browser was only refreshed in two scenarios:
1. When explicitly clicking the "🔄 Refresh" button
2. When switching from "Summarize from Files" to "Summarize from Database" view

There was no automatic refresh when:
- The tab became visible after being hidden
- New transcripts were added to the database from other tabs
- The user navigated to the Summarize tab from another tab

## Solution

### 1. Added `showEvent()` Handler

Added a `showEvent()` method to the `SummarizationTab` class that:
- Triggers when the tab becomes visible
- Checks if the database view is currently active (not the file view)
- Automatically refreshes the database list with a small delay to ensure UI is ready

```python
def showEvent(self, a0) -> None:  # type: ignore[override]
    """Handle tab becoming visible - refresh database list if on database view."""
    super().showEvent(a0)
    
    # Only refresh if we're on the database view (not file view)
    if hasattr(self, 'source_stack') and self.source_stack.currentIndex() == 1:
        # Small delay to ensure UI is ready
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._refresh_database_list)
    
    self._tab_was_visible = True
```

### 2. Enhanced Diagnostic Logging

Added comprehensive logging to help diagnose database issues:

```python
# Log total transcripts in database
total_transcripts = session.query(Transcript).count()
logger.debug(f"Total transcripts in database: {total_transcripts}")

# Log matched records
videos = query.all()
logger.debug(f"Found {len(videos)} MediaSource records with transcripts")

# Check for orphaned transcripts (transcripts without MediaSource records)
if total_transcripts > len(videos):
    orphaned_transcripts = (
        session.query(Transcript)
        .outerjoin(MediaSource, Transcript.source_id == MediaSource.source_id)
        .filter(MediaSource.source_id.is_(None))
        .all()
    )
    if orphaned_transcripts:
        logger.warning(
            f"Found {len(orphaned_transcripts)} transcripts without MediaSource records. "
            f"Source IDs: {[t.source_id for t in orphaned_transcripts[:5]]}"
        )
```

## Technical Details

### Database Query

The existing query was correct and uses a proper join:

```python
query = (
    session.query(MediaSource)
    .join(
        Transcript,
        MediaSource.source_id == Transcript.source_id,
        isouter=True,
    )
    .filter(Transcript.transcript_id.isnot(None))
)
```

This query:
1. Starts with MediaSource records
2. Joins with Transcript table on source_id
3. Filters to only show MediaSource records that have at least one Transcript

### MediaSource Record Creation

When transcribing a YouTube URL, the system:
1. Downloads the video using `UnifiedDownloadOrchestrator`
2. Creates a MediaSource record via `YouTubeDownloadProcessor.process()`
3. Ensures the audio_file_path is set via `_ensure_source_record_has_file_path()`
4. Creates a Transcript record via `AudioProcessor.process()` → `DatabaseService.create_transcript()`

The foreign key constraint on `Transcript.source_id` ensures that transcripts can only be created if a MediaSource record exists.

### Fallback Protection

The transcription worker includes a fallback to create minimal MediaSource records if they don't exist:

```python
def _ensure_source_record_has_file_path(self, audio_file: Path, source_id: str) -> None:
    source = db_service.get_source(source_id)
    if source:
        # Update existing record
        db_service.update_source(source_id=source_id, audio_file_path=str(audio_file))
    else:
        # Create minimal record as fallback
        logger.warning(f"Source {source_id} not found, creating minimal record")
        db_service.create_source(
            source_id=source_id,
            title=audio_file.stem,
            url="",
            source_type="unknown",
            audio_file_path=str(audio_file),
        )
```

## User Experience Improvements

### Before Fix
1. User transcribes a YouTube URL
2. User switches to Summarize tab
3. User switches to "Summarize from Database" view
4. **New transcript is not visible**
5. User must manually click "🔄 Refresh" button
6. New transcript appears

### After Fix
1. User transcribes a YouTube URL
2. User switches to Summarize tab
3. User switches to "Summarize from Database" view
4. **New transcript automatically appears** (refreshed on tab visibility)
5. No manual refresh needed

## Testing

To verify the fix:

1. **Test automatic refresh on tab switch:**
   - Transcribe a new YouTube URL
   - Switch to Summarize tab
   - Verify the new transcript appears in the database list

2. **Test refresh on view switch:**
   - Start on "Summarize from Files" view
   - Transcribe a new YouTube URL (in another tab or window)
   - Switch to "Summarize from Database" view
   - Verify the new transcript appears

3. **Test manual refresh still works:**
   - Click "🔄 Refresh" button
   - Verify list updates correctly

4. **Check logs for diagnostics:**
   - Look for "Total transcripts in database: N"
   - Look for "Found N MediaSource records with transcripts"
   - Look for any warnings about orphaned transcripts

## Files Modified

- `src/knowledge_system/gui/tabs/summarization_tab.py`:
  - Added `showEvent()` method for automatic refresh
  - Added `_tab_was_visible` tracking variable
  - Enhanced `_refresh_database_list()` with diagnostic logging
  - Added orphaned transcript detection

## Related Issues

This fix addresses the user experience issue where the database view felt "stale" or "disconnected" from the rest of the application. The automatic refresh ensures that the Summarize tab always shows the current state of the database when it becomes visible.

## Future Enhancements

Potential improvements for even better UX:

1. **Real-time updates via signals**: Connect transcription completion signals to trigger refresh
2. **Database change notifications**: Use SQLite triggers or polling to detect changes
3. **Incremental updates**: Only add new rows instead of full refresh
4. **Background refresh**: Periodically refresh in background (like Queue tab's 5-second refresh)

However, the current solution (refresh on tab visibility) provides a good balance between responsiveness and performance without adding complexity.
