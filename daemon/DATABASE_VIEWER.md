# Database Admin Viewer

**Non-public localhost-only web interface for viewing SQLite database contents.**

## Overview

The Database Admin Viewer provides a clean, interactive interface to browse your local `knowledge_system.db` without needing a separate SQLite client.

## Features

✅ **Visual Table Browsing** - See all tables with formatted data  
✅ **Smart Sorting** - Automatically sorts by most recent records first  
✅ **Pagination** - Shows 100 records per table with "Load More" button  
✅ **Database Summary** - File size, table count, last modified  
✅ **Read-Only** - No write operations, safe for inspection  
✅ **Collapsible Tables** - Click headers to expand/collapse  
✅ **Manual Refresh** - Reload all data with one click  
✅ **Dark Theme** - Clean, modern interface

## Access

### 1. Start the Daemon

```bash
# From project root
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python -m daemon.main
```

The daemon will start on `http://127.0.0.1:8765`

### 2. Open Database Viewer

Open your browser to:

```
http://localhost:8765/api/admin/database
```

## Security

- **Localhost Only**: Bound to `127.0.0.1`, not accessible from network
- **Read-Only**: Uses SQLite read-only connection mode
- **No Auth Required**: Since it's localhost-only and read-only

## Interface

### Header
- Shows last refresh time
- Manual refresh button (🔄)

### Database Summary
- Database file size (MB)
- Total number of tables
- Database file path
- Last modified timestamp

### Table Sections
Each table shows:
- **Table name** and row count
- **Collapsible content** - Click header to expand/collapse
- **100 records** per page (sorted by most recent)
- **Load More button** - Appends next 100 records to existing view
- **Column headers** - Sticky headers that stay visible while scrolling
- **Formatted values** - Null values shown in gray, timestamps formatted

## Main Tables

The viewer shows all tables, but these are the most useful:

### `media_sources`
YouTube videos, podcasts, PDFs with metadata and processing status

### `claims`
Extracted knowledge claims with importance scores and tiers (A/B/C/D)

### `transcripts`
Transcription data with quality scores and speaker labels

### `segments`
Transcript segments with timestamps and speaker attribution

### `review_queue_items`
Pending/accepted/rejected items for bulk review workflow

### `summaries`
Generated summaries with metrics and model information

## Usage Tips

1. **Find Recent Additions**: Tables auto-sort by most recent (created_at, updated_at, etc.)
2. **Load More Data**: Click "Load More" at bottom of each table to see next 100 records
3. **Collapse Unused Tables**: Click table headers to hide sections you don't need
4. **Manual Refresh**: Click 🔄 button to reload all data from database
5. **Long Values**: Hover over table cells to see full content in tooltip

## API Endpoints

If you want to query programmatically:

### Get Database Summary
```bash
curl http://localhost:8765/api/admin/database/summary
```

Returns:
```json
{
  "database_path": "~/Library/Application Support/Knowledge_Chipper/knowledge_system.db",
  "database_size_mb": 45.23,
  "last_modified": "2025-12-28 10:30:00",
  "table_count": 25,
  "tables": [
    {"name": "claims", "row_count": 1234, "column_count": 20},
    ...
  ]
}
```

### Get Table Data
```bash
curl "http://localhost:8765/api/admin/database/table/claims?limit=100&offset=0"
```

Returns:
```json
{
  "table_name": "claims",
  "columns": ["source_id", "claim_id", "canonical", "tier", ...],
  "records": [...],
  "total_count": 1234,
  "limit": 100,
  "offset": 0,
  "has_more": true
}
```

## Troubleshooting

### "Database not found"
- Check that `knowledge_system.db` exists at:
  ```
  ~/Library/Application Support/Knowledge_Chipper/knowledge_system.db
  ```
- Run the main GUI at least once to create the database

### "Connection refused"
- Make sure the daemon is running: `python -m daemon.main`
- Check that port 8765 is not in use by another service

### "Table is empty"
- Process some content first (transcribe videos, extract claims)
- The database starts empty until you add content

## When to Use This

**Good for**:
- ✅ Debugging processing issues
- ✅ Verifying database state
- ✅ Checking what content exists
- ✅ Finding recent additions
- ✅ Quick data inspection without SQL

**Not good for**:
- ❌ Complex SQL queries (use sqlite3 CLI instead)
- ❌ Modifying data (read-only by design)
- ❌ Exporting large datasets (use SQL export tools)
- ❌ Remote access (localhost only)

## Related Tools

For more advanced database operations, use:

```bash
# SQLite command line
sqlite3 ~/Library/Application\ Support/Knowledge_Chipper/knowledge_system.db

# DB Browser for SQLite (GUI app)
brew install --cask db-browser-for-sqlite

# Export to CSV
sqlite3 knowledge_system.db -csv -header "SELECT * FROM claims" > claims.csv
```

---

**Version**: Added December 28, 2025  
**Daemon Version**: 0.1.0+  
**Port**: 8765 (configurable via KC_PORT environment variable)

