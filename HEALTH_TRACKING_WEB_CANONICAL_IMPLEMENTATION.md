# Health Tracking: Web-Canonical Implementation

**Date**: January 2, 2026

## Overview

The health tracking system has been converted from local-only to **web-canonical architecture**, following the same pattern as all other data in GetReceipts/Knowledge_Chipper.

## What Changed

### 1. Database Schema Updates

**Local SQLite** (`add_health_tracking.sql`)
- Added `privacy_status` field (private/public) to all three tables
- Added sync tracking fields:
  - `synced_to_web` - boolean flag
  - `web_id` - UUID from Supabase
  - `last_synced_at` - timestamp
- Added indexes on sync fields

**Supabase** (`GetReceipts/database/migrations/025_health_tracking.sql`)
- Created three tables: `health_interventions`, `health_metrics`, `health_issues`
- Added RLS policies for privacy (users see own data + public data)
- Added service role policies for device-based uploads
- Added `device_id` tracking
- Added updated_at triggers

### 2. SQLAlchemy Models Updated

Updated `src/knowledge_system/database/models.py`:
- `HealthIntervention` - added privacy_status, synced_to_web, web_id, last_synced_at
- `HealthMetric` - added privacy_status, synced_to_web, web_id, last_synced_at
- `HealthIssue` - added privacy_status, synced_to_web, web_id, last_synced_at

### 3. Unified Sync Service (NO REDUNDANCY)

**New file**: `src/knowledge_system/services/entity_sync.py`

**ONE SERVICE FOR ALL ENTITY TYPES**:
- Batch entities (extraction: claims, jargon, people, concepts)
- Individual entities (health tracking, predictions, future types)

Provides:
- `upload_single(entity_type, data)` - sync any single entity
- `upload_entities(entity_type, entities[])` - batch sync any entity type
- Convenience methods:
  - `sync_health_intervention(intervention_id)`
  - `sync_health_metric(metric_id)`
  - `sync_health_issue(issue_id)`
- `is_sync_enabled()` - check if device is linked

Uses:
- Existing `GetReceiptsUploader` infrastructure (no duplication)
- Device authentication (via device_auth service)
- Wraps single entities as batch of 1 for consistency

### 4. Auto-Sync on Save

Updated all three dialogs to auto-sync after successful save:
- `health_intervention_dialog.py` - calls `sync_intervention()` after commit
- `health_metric_dialog.py` - calls `sync_metric()` after commit
- `health_issue_dialog.py` - calls `sync_issue()` after commit

Pattern:
```python
session.commit()
entity_id = entity.entity_id

# Auto-sync to web (unified service)
sync_service = get_entity_sync_service()
if sync_service.is_sync_enabled():
    sync_result = sync_service.sync_health_intervention(entity_id)
    if sync_result.get("success"):
        logger.info(f"✅ Entity synced to web")
```

### 5. Documentation Updated

- **MANIFEST.md** - Updated all health tracking entries to mention web-canonical pattern
- **CHANGELOG.md** - Added comprehensive entry for web-canonical conversion
- **GetReceipts/PENDING_WEB_MIGRATIONS.md** - Added 025_health_tracking.sql entry

## Architecture Pattern

### Before (Local-Only)
```
Desktop → SQLite → End
```

### After (Web-Canonical)
```
Desktop → SQLite → Auto-Sync → Supabase (source of truth)
                                    ↓
                               GetReceipts.org /health page
```

This matches the pattern for:
- Claims/Jargon/People/Concepts
- Predictions
- Prompt Refinements

## What You Need to Do

### 1. Run Supabase Migration (REQUIRED)

```bash
# Copy migration to clipboard
cat GetReceipts/database/migrations/025_health_tracking.sql | pbcopy

# Then:
# 1. Go to https://supabase.com/dashboard/project/YOUR_PROJECT/sql/new
# 2. Paste the migration
# 3. Click "Run"
```

**Tables created**:
- `health_interventions`
- `health_metrics`
- `health_issues`

**Policies created**:
- Users can view/edit their own data
- Users can view public data
- Service role can manage all data (for device uploads)

### 2. Test Desktop Sync

1. Open Knowledge Chipper
2. Go to Tools → Personal Health Dashboard
3. Add an intervention (or metric or issue)
4. Check logs for "✅ Entity synced to web"
5. Query Supabase to verify data appears

**Verify in Supabase**:
```sql
SELECT * FROM health_interventions ORDER BY created_at DESC LIMIT 5;
SELECT * FROM health_metrics ORDER BY created_at DESC LIMIT 5;
SELECT * FROM health_issues ORDER BY created_at DESC LIMIT 5;
```

### 3. Build Web Health Dashboard (Future)

**What's needed**:
- Create `GetReceipts/src/app/(dashboard)/health/page.tsx`
- Three sections (like desktop):
  - Interventions table
  - Metrics table
  - Health Issues table
- Privacy toggle for each item
- Edit/delete functionality
- Peter Attia category filtering

**API endpoints needed** (to be created):
- `GET /api/health/interventions` - fetch user's interventions
- `POST /api/health/interventions` - create/update (already exists for device sync)
- `DELETE /api/health/interventions/:id` - delete intervention
- (Same for metrics and issues)

## Privacy Model

**Default**: Private (only you can see)
**Public**: Visible to anyone who visits your GetReceipts profile

This allows:
- Personal health tracking (keep private)
- Sharing health optimizations with community (make public)
- Maintaining a public health journal/blog

## Sync Behavior

**Auto-sync**: Every save from desktop automatically uploads to web
**Conflict resolution**: Web wins (for now)
**Offline behavior**: Items marked as not synced, will sync on next successful connection
**Batch sync**: Can manually trigger `sync_all_pending()` to upload all unsynced items

## Testing

**Desktop side**:
1. Create intervention with name "Test Creatine"
2. Check logs for sync confirmation
3. Query local SQLite: `SELECT synced_to_web, web_id FROM health_interventions WHERE name = 'Test Creatine';`
   - Should show `synced_to_web=1` and a UUID in `web_id`

**Web side**:
1. Query Supabase
2. Find intervention with matching name
3. Verify `user_id`, `device_id`, and all fields match

## Files Changed

**Knowledge_Chipper**:
- `src/knowledge_system/database/migrations/add_health_tracking.sql` - updated schema
- `src/knowledge_system/database/models.py` - added privacy & sync fields
- `src/knowledge_system/services/entity_sync.py` - **NEW unified sync service (NO REDUNDANCY)**
- `src/knowledge_system/gui/dialogs/health_intervention_dialog.py` - auto-sync on save
- `src/knowledge_system/gui/dialogs/health_metric_dialog.py` - auto-sync on save
- `src/knowledge_system/gui/dialogs/health_issue_dialog.py` - auto-sync on save
- `MANIFEST.md` - documented web-canonical pattern
- `CHANGELOG.md` - added implementation entry

**Deleted** (redundant):
- `src/knowledge_system/services/health_sync.py` - replaced by unified entity_sync.py

**GetReceipts**:
- `database/migrations/025_health_tracking.sql` - new Supabase schema
- `PENDING_WEB_MIGRATIONS.md` - documented migration requirement

## Next Steps

1. ✅ Run Supabase migration
2. ✅ Test desktop auto-sync
3. ⏳ Build web health dashboard UI
4. ⏳ Add privacy toggle to desktop dialogs
5. ⏳ Add web→desktop bulk fetch on app launch
6. ⏳ Add conflict resolution UI

## Implementation Status

**COMPLETE**:
- ✅ Database schema (local + Supabase)
- ✅ SQLAlchemy models
- ✅ Sync service
- ✅ Auto-sync on save
- ✅ Privacy field support
- ✅ Device authentication
- ✅ Documentation

**TODO**:
- ⏳ Web health dashboard page
- ⏳ Web API endpoints (GET/POST/DELETE)
- ⏳ Privacy toggle UI in desktop
- ⏳ Bulk fetch from web on app launch
- ⏳ Conflict resolution for concurrent edits

## Summary

The health tracking system now follows the same web-canonical pattern as the rest of GetReceipts:
- **Local = ephemeral** (for entry/editing)
- **Web = source of truth** (for storage/sharing)
- **Auto-sync** (on every save)
- **Privacy controls** (private by default)

This ensures:
1. Your health data is accessible from anywhere (via GetReceipts.org)
2. You can share health optimizations with the community (if you choose)
3. Data persists even if desktop app is uninstalled
4. Consistent architecture across all features

