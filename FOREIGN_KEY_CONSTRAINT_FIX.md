# Foreign Key Constraint Fix

## Issue

The system was encountering a `FOREIGN KEY constraint failed` error when trying to insert stage status records:

```
ERROR | knowledge_system.database.service:upsert_stage_status:2568 | 
Failed to upsert stage status for hyIgB-xFQzQ/download: 
(sqlite3.IntegrityError) FOREIGN KEY constraint failed

[SQL: INSERT INTO source_stage_statuses (source_id, stage, status, priority, ...) 
VALUES (?, ?, ?, ?, ...)]
```

## Root Cause

The `source_stage_statuses` table has a foreign key constraint to the `media_sources` table:

```sql
FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE
```

The error occurred when `upsert_stage_status()` was called **before** a corresponding `MediaSource` record existed in the database. This happened in the download orchestration flow:

1. `UnifiedDownloadOrchestrator.process_all()` calls `upsert_stage_status()` to mark downloads as "queued"
2. At this point, the `MediaSource` record doesn't exist yet (it's created during/after download)
3. The foreign key constraint fails because there's no parent record

## Solution

Modified `DatabaseService.upsert_stage_status()` to automatically ensure a `MediaSource` record exists before creating stage status records:

```python
def upsert_stage_status(self, source_id: str, stage: str, status: str, ...):
    # Ensure MediaSource exists before creating stage status
    media_source = session.query(MediaSource).filter(...).first()
    
    if not media_source:
        # Create a minimal MediaSource record
        url = metadata.get("url", f"youtube://{source_id}") if metadata else f"youtube://{source_id}"
        
        media_source = MediaSource(
            source_id=source_id,
            source_type="youtube",
            title=f"Queued: {source_id}",
            url=url,
        )
        session.add(media_source)
        session.flush()  # Ensure it's written before stage status
```

## Benefits

1. **Prevents Foreign Key Errors**: Automatically creates placeholder `MediaSource` records when needed
2. **Maintains Data Integrity**: Foreign key constraints remain enforced
3. **Graceful Degradation**: Placeholder records get updated with full metadata during actual download
4. **No Breaking Changes**: Existing code continues to work without modification

## Testing

Verified the fix works correctly:

```bash
✅ Stage status upserted successfully for hyIgB-xFQzQ: True
✅ MediaSource: hyIgB-xFQzQ - Markets Drop After Fed Rate Cut || Peter Zeihan
✅ Stage status: stage=download, status=queued
```

## Files Modified

- `src/knowledge_system/database/service.py` - Added MediaSource existence check in `upsert_stage_status()`

## Related Components

- `UnifiedDownloadOrchestrator` - Calls `upsert_stage_status()` early in the download flow
- `SessionBasedScheduler` - Updates stage status during session scheduling
- `source_stage_statuses` table - Queue visibility tracking
- `media_sources` table - Source attribution records
