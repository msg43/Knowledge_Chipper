# Database Schema Fix: Missing user_notes Column

**Date:** November 20, 2025  
**Issue:** Review tab failed to load claims with `sqlite3.OperationalError: no such column: claims.user_notes`

## Problem

The SQLAlchemy `Claim` model in `models.py` included a `user_notes` column (line 737), but the actual database table was missing this column. This caused the Review tab to fail when trying to query claims:

```
sqlite3.OperationalError: no such column: claims.user_notes
[SQL: SELECT claims.claim_id AS claims_claim_id, ..., claims.user_notes AS claims_user_notes, ...]
```

## Root Cause

The `user_notes` column was added to the SQLAlchemy model but the corresponding database migration (`2025_11_16_add_user_notes_to_claims.sql`) was not automatically applied during database initialization. The migration file existed but wasn't being run.

## Solution

### 1. Applied the Migration Manually

Applied the migration to the user's database:

```bash
sqlite3 "/Users/matthewgreer/Library/Application Support/Knowledge Chipper/knowledge_system.db" \
  < "src/knowledge_system/database/migrations/2025_11_16_add_user_notes_to_claims.sql"
```

This added:
- `user_notes TEXT` column to the `claims` table
- Index on `user_notes` for efficient searching

### 2. Added Automatic Migration Application

Updated `DatabaseService.__init__()` to automatically apply incremental migrations on startup:

**File:** `src/knowledge_system/database/service.py`

Added `_apply_incremental_migrations()` method that:
- Runs after `_ensure_unified_hce_schema()`
- Applies a list of incremental SQL migrations
- Each migration is idempotent (safe to re-run)
- Logs which migrations are applied
- Gracefully handles already-applied migrations

Current incremental migrations:
- `2025_11_16_add_user_notes_to_claims.sql` - Adds user_notes column

### 3. Updated Base Schema

Updated `claim_centric_schema.sql` to include `user_notes` in the base schema for fresh installations:

```sql
-- Review workflow
flagged_for_review BOOLEAN DEFAULT 0,
reviewed_by TEXT,
reviewed_at DATETIME,
user_notes TEXT,  -- NEW: User freeform notes

-- Temporality analysis
...
```

Also added the index:
```sql
CREATE INDEX idx_claims_user_notes ON claims(user_notes) WHERE user_notes IS NOT NULL;
```

### 4. Updated verification_status Constraint

While fixing the schema, also updated the `verification_status` CHECK constraint to include 'unverifiable' status (already in the model but missing from SQL):

```sql
verification_status TEXT CHECK (verification_status IN 
  ('unverified', 'verified', 'disputed', 'false', 'unverifiable')) 
  DEFAULT 'unverified',
```

## Files Modified

1. **src/knowledge_system/database/service.py**
   - Added `_apply_incremental_migrations()` method
   - Called from `__init__()` after unified schema setup

2. **src/knowledge_system/database/migrations/claim_centric_schema.sql**
   - Added `user_notes TEXT` column
   - Added index for `user_notes`
   - Updated `verification_status` constraint to include 'unverifiable'

3. **CHANGELOG.md**
   - Documented the fix in [Unreleased] section

## Verification

Tested that:
1. ✅ Database service initializes without errors
2. ✅ Claims can be queried with `user_notes` column using raw SQL
3. ✅ Claims can be loaded using SQLAlchemy ORM (as Review tab does)
4. ✅ `user_notes` field is accessible on Claim objects

```bash
# Test output
✓ Successfully queried claims table with user_notes column
✓ Database service initialized successfully
✓ Successfully loaded 5 claims using ORM
✓ user_notes field accessible: True
```

## Impact

- **Immediate:** Fixes the Review tab crash for existing installations
- **Future:** Prevents this issue from occurring on fresh installations
- **Automatic:** The migration is now applied automatically on startup for any database missing the column

## Prevention

The new `_apply_incremental_migrations()` system ensures that:
1. Schema additions (new columns, indexes) are automatically applied
2. Migrations are idempotent (safe to re-run)
3. Failed migrations don't crash the application
4. New migrations can be easily added to the list

When adding new schema changes in the future:
1. Create an idempotent SQL migration file in `migrations/`
2. Add the filename to the `incremental_migrations` list in `service.py`
3. Update the base schema files for fresh installations

