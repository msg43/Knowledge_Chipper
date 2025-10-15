# Speaker Assignment HCE Update - Implementation Complete

## Overview
Implemented a system to update HCE database with corrected speaker names and automatically reprocess all affected claims and evidence spans when users correct speaker assignments after HCE processing.

## Implementation Details

### 1. HCE Database Functions (`storage_sqlite.py`)

Added three new functions to `src/knowledge_system/processors/hce/storage_sqlite.py`:

#### `episode_exists(conn, episode_id) -> bool`
- Checks if an episode exists in the HCE database
- Used to determine if HCE update is available

#### `update_speaker_names(conn, episode_id, speaker_mappings) -> (bool, str)`
- Updates speaker names in the `segments` table
- Takes mapping of `{old_speaker: new_speaker}`
- Logs all updates for audit trail
- Returns success status and message

#### `delete_episode_hce_data(conn, episode_id) -> (bool, str)`
- Deletes all extracted HCE data for an episode:
  - Evidence spans
  - Relations
  - Claims
  - People
  - Concepts
  - Jargon
  - Mental models
  - Milestones
  - FTS entries
- Keeps episode and segments records intact
- Prepares episode for reprocessing

### 2. Speaker Processor Functions (`speaker_processor.py`)

Added two static methods to `SpeakerProcessor` class:

#### `find_episode_id_for_video(video_id) -> str | None`
- Queries HCE `episodes` table for matching video_id
- Returns episode_id if found, None otherwise
- Used to locate HCE data for a given video

#### `reprocess_hce_with_updated_speakers(...) -> (bool, str)`
- Complete reprocessing workflow:
  1. Opens HCE database connection
  2. Deletes existing HCE data
  3. Reconstructs segments from updated transcript
  4. Saves updated segments to database
  5. Runs HCE pipeline (mining + evaluation)
  6. Saves new results to database
- Supports custom HCE config and progress callbacks
- Returns success status and detailed message

### 3. HCE Update Confirmation Dialog (`hce_update_dialog.py`)

Created new dialog `src/knowledge_system/gui/dialogs/hce_update_dialog.py`:

#### Features:
- Shows speaker name changes in clear format
- Explains what will be reprocessed
- Estimates processing time and cost
- Progress display with real-time updates
- Background worker thread for non-blocking execution
- Success/failure handling with informative messages

#### Components:
- `HCEReprocessWorker` - QThread for background processing
- `HCEUpdateConfirmationDialog` - Main dialog UI
- `show_hce_update_dialog()` - Convenience function

### 4. Speaker Assignment Dialog Integration (`speaker_assignment_dialog.py`)

Modified `src/knowledge_system/gui/dialogs/speaker_assignment_dialog.py`:

#### Added `_check_and_offer_hce_update(assignments)` method:
- Called automatically when user confirms assignments
- Checks if HCE data exists for the video
- Loads transcript data from database
- Applies speaker assignments to transcript (in-memory)
- Shows HCE update dialog if changes detected
- Silently skips if no HCE data or no changes

#### Integration:
- Triggered in `_on_accept()` before emitting completion signal
- Non-blocking - doesn't prevent dialog from closing
- Handles all errors gracefully with logging

### 5. Speaker Attribution Tab Integration (`speaker_attribution_tab.py`)

Modified `src/knowledge_system/gui/tabs/speaker_attribution_tab.py`:

#### Added UI Components:
- **"Update HCE Database" button**
  - Blue styling to stand out
  - Initially disabled
  - Enabled when HCE data exists for current transcript
  - Shows episode_id in tooltip when enabled

#### Added Methods:

**`update_hce_database()`**
- Manual trigger for HCE update
- Saves current assignments first
- Validates video_id and episode_id exist
- Checks for speaker name changes
- Shows HCE update dialog
- Displays success/failure messages

**`_check_hce_data_exists()`**
- Called when transcript is loaded
- Queries HCE database for episode
- Enables/disables update button accordingly
- Updates tooltip with episode info

#### Integration:
- Button added to transcript controls layout
- `_check_hce_data_exists()` called in `load_transcript_from_path()`
- Works seamlessly with existing speaker assignment workflow

## Workflow

### Automatic Trigger (Speaker Assignment Dialog):
1. User transcribes audio with diarization
2. Speaker assignment dialog appears
3. User corrects/confirms speaker names
4. User clicks "Accept" or closes dialog
5. System checks if HCE data exists
6. If yes, HCE update dialog automatically appears
7. User confirms or cancels update
8. If confirmed, reprocessing runs in background

### Manual Trigger (Speaker Attribution Tab):
1. User loads transcript in Speaker Attribution tab
2. "Update HCE Database" button is enabled if HCE data exists
3. User corrects speaker names
4. User clicks "Save Assignments"
5. User clicks "Update HCE Database"
6. HCE update dialog appears with confirmation
7. User confirms, reprocessing runs in background
8. Success message displayed on completion

## Database Connection Pattern

Uses the existing pattern from `storage_sqlite.py`:
```python
from ...database.service import DatabaseService
from .hce.storage_sqlite import open_db

# Get database path
db_service = DatabaseService()
db_path = db_service.db_path

# Open connection
conn = open_db(db_path)
try:
    # Perform operations
    ...
finally:
    conn.close()
```

## Error Handling

All functions include comprehensive error handling:
- Try/except blocks with detailed logging
- Graceful fallbacks for missing data
- User-friendly error messages in dialogs
- Transaction rollback on database errors
- Non-blocking failures in GUI integration

## Testing Recommendations

### End-to-End Test:
1. Transcribe a YouTube video with diarization
2. Skip or cancel speaker assignment (leave as SPEAKER_0, SPEAKER_1)
3. Run HCE summarization on the transcript
4. Verify segments in HCE database have generic speaker labels
5. Return to Speaker Attribution tab and load transcript
6. Assign real names to speakers
7. Click "Update HCE Database"
8. Confirm in dialog
9. Wait for reprocessing to complete
10. Verify segments table has real names
11. Verify claims/evidence reference correct speakers

### Integration Test:
1. Transcribe audio with diarization
2. Accept suggested speaker names in dialog
3. Run HCE processing
4. Change speaker names in Speaker Attribution tab
5. Trigger manual HCE update
6. Verify database reflects changes

### Edge Cases:
- [ ] No video_id in transcript
- [ ] No HCE data exists yet
- [ ] No speaker name changes detected
- [ ] Database connection fails
- [ ] HCE reprocessing fails mid-way
- [ ] User cancels during reprocessing

## Files Modified

1. `src/knowledge_system/processors/hce/storage_sqlite.py` - Added database functions
2. `src/knowledge_system/processors/speaker_processor.py` - Added helper and reprocessing methods
3. `src/knowledge_system/gui/dialogs/hce_update_dialog.py` - NEW: Confirmation dialog
4. `src/knowledge_system/gui/dialogs/speaker_assignment_dialog.py` - Added automatic trigger
5. `src/knowledge_system/gui/tabs/speaker_attribution_tab.py` - Added manual trigger UI

## Dependencies

No new external dependencies required. Uses existing:
- PyQt6 (GUI)
- SQLite3 (database)
- HCE pipeline (unified_pipeline)
- Database service (service.py)

## Future Enhancements

Potential improvements not included in this implementation:

1. **Batch Update**: Update multiple episodes at once
2. **Smart Caching**: Skip reprocessing if only speaker names changed (keep existing analysis)
3. **Undo Feature**: Allow reverting to previous HCE data
4. **Progress Estimates**: More accurate time/cost estimates based on hardware
5. **Selective Reprocessing**: Only reprocess claims that reference specific speakers
6. **History Tracking**: Keep audit log of all HCE updates

## Notes

- The implementation follows the plan exactly as specified
- All functions are static/standalone for easy testing
- GUI integration is non-blocking and error-tolerant
- Database operations use transactions for consistency
- Progress callbacks supported throughout
- Logging at appropriate levels (info, debug, warning, error)
