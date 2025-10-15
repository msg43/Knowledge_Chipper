# Claim Deletion Feature - Review Tab

## Overview

Added the ability to delete claims directly from the database in the Review Tab (System 2). Users can now select one or more claims and permanently delete them using a dedicated delete button.

## Implementation Details

### User Interface Changes

1. **Delete Button**: Added a "🗑️ Delete Selected" button to the review tab action bar
   - Initially disabled when no claims are selected
   - Automatically enables when one or more claims are selected
   - Positioned before the export buttons for easy access

2. **Selection Handling**: 
   - The table view supports multi-row selection (Ctrl/Cmd + Click for multiple selections)
   - Selection state is tracked and the delete button updates accordingly
   - Clear visual feedback on which claims are selected

### Functionality

1. **Delete Operation**:
   - Permanently deletes selected claims from the SQLite database
   - Deletes claims by their composite primary key (episode_id, claim_id)
   - Cascading deletes handle related data (evidence spans, relations, etc.)

2. **Safety Features**:
   - Confirmation dialog before deletion
   - Clear warning that the action cannot be undone
   - Shows count of claims to be deleted
   - Success/error messages after operation

3. **Database Integration**:
   - Uses SQLAlchemy ORM for safe deletion
   - Proper transaction handling with commit/rollback
   - Automatically refreshes the view after deletion
   - Maintains data integrity with foreign key constraints

### Code Changes

**File**: `src/knowledge_system/gui/tabs/review_tab_system2.py`

- Added `delete_btn` QPushButton to the UI
- Added `_on_selection_changed()` method to track selection state
- Added `_delete_selected_claims()` method to handle deletion logic
- Connected selection model signals to update button state

### Testing

**File**: `tests/gui_comprehensive/test_review_tab_system2.py`

Added tests for:
- Delete button existence
- Initial disabled state
- Enable on selection
- Disable on deselection

## Usage

1. Open the Review Tab in the GUI
2. Select one or more claims by clicking on rows (use Ctrl/Cmd for multiple)
3. Click the "🗑️ Delete Selected" button
4. Confirm the deletion in the dialog
5. The claims are permanently removed from the database

## Technical Notes

- Claims are identified by composite primary key: (episode_id, claim_id)
- Database foreign keys ensure related data is handled properly
- The operation is atomic - either all selected claims are deleted or none
- The view automatically refreshes after successful deletion
- Error handling includes logging and user-friendly error messages

## Future Enhancements

Potential improvements for future versions:
- Undo functionality (would require a deleted_claims table)
- Bulk operations with progress indicator
- Export deleted claims before removal
- Soft delete option (mark as deleted instead of removing)
- Audit trail for deletions

