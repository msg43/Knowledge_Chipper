# Queue Tab Migration Guide

## Overview
This guide covers the migration steps to enable the new Queue tab feature that provides real-time visualization of the processing pipeline.

## Migration Steps

### 1. Database Migration

Run the SQL migration to create the new `source_stage_statuses` table:

```bash
# Navigate to project root
cd /path/to/Knowledge_Chipper

# Apply the migration
sqlite3 data/knowledge_system.db < src/knowledge_system/database/migrations/2025_11_05_source_stage_status.sql
```

### 2. Verify Migration

Check that the table was created successfully:

```bash
sqlite3 data/knowledge_system.db "SELECT name FROM sqlite_master WHERE type='table' AND name='source_stage_statuses';"
```

Expected output:
```
source_stage_statuses
```

### 3. Feature Flag (Optional Soft Launch)

To enable/disable the Queue tab without rebuilding:

```python
# In src/knowledge_system/gui/main_window_pyqt6.py, add after line 351:
if self.settings.get("enable_queue_tab", True):
    self.queue_tab = QueueTab(self)
    self.tabs.addTab(self.queue_tab, "Queue")
```

Then users can disable via settings:
```python
settings["enable_queue_tab"] = False  # Disable queue tab
```

### 4. Initial Data Population

For existing sources without stage status records, run this one-time script:

```python
from knowledge_system.database.service import DatabaseService

db = DatabaseService()

# Get all sources
sources = db.get_all_sources()

for source in sources:
    # Check current state and create appropriate stage records
    if source.audio_downloaded:
        db.upsert_stage_status(
            source_id=source.source_id,
            stage="download",
            status="completed",
            progress_percent=100.0
        )
    
    if source.transcripts:
        db.upsert_stage_status(
            source_id=source.source_id,
            stage="transcription", 
            status="completed",
            progress_percent=100.0
        )
        
    if source.summaries:
        db.upsert_stage_status(
            source_id=source.source_id,
            stage="summarization",
            status="completed", 
            progress_percent=100.0
        )
```

### 5. Performance Considerations

The Queue tab refreshes every 5 seconds by default. For large databases:

1. **Increase refresh interval** - Edit line 170 in `queue_tab.py`:
   ```python
   self.refresh_timer.start(10000)  # 10 seconds instead of 5
   ```

2. **Reduce page size** - Edit line 62 in `queue_tab.py`:
   ```python
   self.page_size = 25  # Show 25 items instead of 50
   ```

3. **Add database indexes** (if not created by migration):
   ```sql
   CREATE INDEX idx_stage_status ON source_stage_statuses(stage, status);
   CREATE INDEX idx_source_stage ON source_stage_statuses(source_id, stage);
   ```

### 6. Rollback Instructions

To remove the Queue tab feature:

1. **Remove the tab from UI:**
   ```bash
   # Comment out or remove these lines from main_window_pyqt6.py
   # Lines 349-351
   ```

2. **Drop the table (optional):**
   ```sql
   DROP TABLE IF EXISTS source_stage_statuses;
   ```

3. **Remove imports:**
   - Remove line 52 from `main_window_pyqt6.py`
   - Remove "QueueTab" from `tabs/__init__.py`

## Testing the Migration

1. **Verify tab appears:**
   - Launch the GUI
   - Confirm "Queue" tab appears between "Summarize" and "Review"

2. **Test basic functionality:**
   - Click on Queue tab
   - Verify empty table displays with column headers
   - Check that stats show "Total: 0"

3. **Test with data:**
   - Start a transcription job
   - Switch to Queue tab
   - Verify the item appears with status "in_progress"
   - Wait for completion
   - Verify status changes to "completed"

## Troubleshooting

### Queue tab doesn't appear
- Check that migration was applied
- Verify imports in `main_window_pyqt6.py`
- Check for errors in console log

### No data in queue
- Verify `source_stage_statuses` table exists
- Check that instrumentation code is active in processors
- Run initial data population script

### Performance issues
- Increase refresh interval
- Reduce page size
- Add database indexes
- Check `~/.knowledge_system/logs/` for slow query warnings

## Future Enhancements

The following features are planned but not yet implemented:

1. **Worker instrumentation** - Emit real-time events from processors
2. **Detail modal** - Click row to see full stage timeline
3. **Persistence** - Save filter/sort preferences
4. **Export** - Download queue snapshot as CSV
5. **Notifications** - Alert on failures or completion
