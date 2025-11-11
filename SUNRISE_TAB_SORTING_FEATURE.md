# Sunrise Tab Sorting Feature

## Overview
Enhanced the Sunrise (Summarization) tab's database browser with sortable columns and a new "Date Added" column.

## Changes Made

### 1. Added Date Added Column
- New column displays `created_at` timestamp from `MediaSource` table
- Format: `YYYY-MM-DD HH:MM` for easy readability
- Shows when each source was first added to the database

### 2. Enabled Column Sorting
- All columns in the database browser are now sortable
- Click any column header to sort by that column
- Click again to reverse the sort order
- Proper data types used for sorting:
  - **Title**: Alphabetical (text)
  - **Duration**: Numeric (seconds)
  - **Has Summary**: Boolean (✓ before ✗)
  - **Token Count**: Numeric (token count)
  - **Date Added**: Chronological (timestamp)

### 3. Implementation Details

#### File Modified
- `src/knowledge_system/gui/tabs/summarization_tab.py`

#### Key Changes

**Column Setup** (lines 1865-1884):
- Increased column count from 5 to 6
- Added "Date Added" to header labels
- Set column width to 120px for Date Added
- Enabled `setSortingEnabled(True)` on the table

**Data Population** (_refresh_database_list method, lines 1901-2024):
- Temporarily disable sorting during population for performance
- Store numeric/timestamp values in `UserRole` for proper sorting
- Duration: Store seconds as integer
- Has Summary: Store 1 or 0 for boolean sorting
- Token Count: Store raw token count
- Date Added: Store Unix timestamp for chronological sorting
- Re-enable sorting after population complete

## User Experience

### Before
- 5 columns: Select, Title, Duration, Has Summary, Token Count
- No sorting capability
- No way to see when sources were added

### After
- 6 columns: Select, Title, Duration, Has Summary, Token Count, **Date Added**
- Click any column header to sort
- Find newest/oldest sources easily
- Sort by duration, token count, or summary status
- All sorting uses proper data types (not just alphabetical)

## Testing

Verified with automated test that:
- Column count is 6
- Sorting is enabled
- All headers are correct
- Table initializes properly

## Database Schema
Uses existing `created_at` field from `media_sources` table:
```sql
created_at DATETIME DEFAULT (datetime('now'))
```

No database migrations required.

## Compatibility
- Fully backward compatible
- No breaking changes
- Works with existing database
- No configuration changes needed
