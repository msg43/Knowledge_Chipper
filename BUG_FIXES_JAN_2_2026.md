# Bug Fixes - January 2, 2026

## Issues Reported

1. **GetReceipts Web**: `/explore/questions` endpoint returns "Failed to fetch question web"
2. **Knowledge_Chipper Desktop**: Health tab not showing
3. **Knowledge_Chipper Desktop**: Predictions tab not showing

## Root Causes

### 1. Questions API Failure (GetReceipts Web)

**Location**: `GetReceipts/src/app/api/paradigms/question-web/route.ts`

**Root Cause**: The questions system database migration has not been run on the Supabase instance. The API is trying to query tables (`questions`, `question_claims`, `question_relations`) that don't exist yet.

**Evidence**: API error at line 240-244 returns:
```typescript
return NextResponse.json(
  { success: false, error: 'Failed to fetch question web' },
  { status: 500 }
);
```

This happens when the Supabase query at lines 61-87 fails because the tables don't exist.

**Solution**: Run the migration file on Supabase

### 2. Health Tab Not Showing (Knowledge_Chipper)

**Location**: `Knowledge_Chipper/src/knowledge_system/gui/tabs/__init__.py`

**Root Cause**: The `HealthClaimsTab` class is imported in `main_window_pyqt6.py` (line 56) and instantiated (lines 378-379), BUT it's not exported in the tabs package `__init__.py`. This causes Python to fail silently when trying to create the tab.

**Files Affected**:
- ✅ File exists: `src/knowledge_system/gui/tabs/health_claims_tab.py`
- ✅ Imported in main window: `from .tabs.health_claims_tab import HealthClaimsTab`
- ❌ Missing from package exports: Not in `__init__.py`

**Solution Applied**: Added to `__init__.py`:
```python
from .health_claims_tab import HealthClaimsTab
```

And added to `__all__` list:
```python
"HealthClaimsTab",  # Health Claims tab
```

### 3. Predictions Tab Not Showing (Knowledge_Chipper)

**Location**: `Knowledge_Chipper/src/knowledge_system/gui/tabs/__init__.py`

**Root Cause**: Same as Health tab - `PredictionsTab` is imported and instantiated but not exported from the package.

**Files Affected**:
- ✅ File exists: `src/knowledge_system/gui/tabs/predictions_tab.py`
- ✅ Imported in main window: `from .tabs.predictions_tab import PredictionsTab`
- ❌ Missing from package exports: Not in `__init__.py`

**Solution Applied**: Added to `__init__.py`:
```python
from .predictions_tab import PredictionsTab
```

And added to `__all__` list:
```python
"PredictionsTab",  # Predictions tab
```

## Fixes Applied

### Knowledge_Chipper Desktop (FIXED ✅)

**File**: `src/knowledge_system/gui/tabs/__init__.py`

**Changes**:
1. Added import: `from .health_claims_tab import HealthClaimsTab`
2. Added import: `from .predictions_tab import PredictionsTab`
3. Added to `__all__`: `"HealthClaimsTab"` and `"PredictionsTab"`

**Expected Result**: Both tabs will now appear in the GUI after restart.

### GetReceipts Web (NOT FIXED - REQUIRES DATABASE MIGRATION ⚠️)

**Migration File**: `GetReceipts/database/migrations/010_add_questions_system_clean.sql`

**Steps to Fix**:

1. **Open Supabase SQL Editor**:
   - Go to: https://sdkxuiqcwlmbpjvjdpkj.supabase.co
   - Navigate to: **SQL Editor** (left sidebar)
   - Click: **New Query**

2. **Run the Migration**:
   ```bash
   # Copy migration to clipboard:
   cat /Users/matthewgreer/Projects/GetReceipts/database/migrations/010_add_questions_system_clean.sql | pbcopy
   ```
   
   Then paste into Supabase SQL Editor and click **Run**.

3. **Verify Tables Were Created**:
   ```sql
   SELECT tablename
   FROM pg_tables
   WHERE schemaname = 'public'
   AND tablename IN ('questions', 'question_claims', 'question_relations')
   ORDER BY tablename;
   ```
   
   Expected result:
   ```
   question_claims
   question_relations
   questions
   ```

4. **Test the API**:
   - Restart the Next.js dev server:
     ```bash
     cd /Users/matthewgreer/Projects/GetReceipts
     npm run dev
     ```
   - Navigate to: http://localhost:3000/explore/questions
   - Should see empty graph instead of error

## Testing Checklist

### Knowledge_Chipper Desktop

- [ ] Restart the desktop app
- [ ] Navigate through all tabs
- [ ] Verify "Health" tab appears (after Queue tab)
- [ ] Verify "Predictions" tab appears (after Queue tab)
- [ ] Both tabs should be functional

### GetReceipts Web (After Migration)

- [ ] Run the Supabase migration
- [ ] Restart Next.js dev server
- [ ] Navigate to http://localhost:3000/explore/questions
- [ ] Should see empty graph or questions if any exist
- [ ] No "Failed to fetch question web" error

## Files Modified

### Knowledge_Chipper
1. `src/knowledge_system/gui/tabs/__init__.py` - Added missing imports and exports

### GetReceipts
- No code changes needed - just needs database migration

## Notes

- The Health and Predictions tabs were implemented in January 2026 according to the manifest
- The question system was implemented in November 2025 according to the docs
- Both features exist in code but have deployment/configuration issues
- Desktop fixes are complete - just restart the app
- Web fix requires database admin access to run migration

## Related Documentation

- `Knowledge_Chipper/MANIFEST.md` - Lines 772-778 (Health Claims tab)
- `Knowledge_Chipper/MANIFEST.md` - Lines 776-777 (Predictions tab)
- `GetReceipts/Docs/QUESTIONS_AND_PEOPLE_ENHANCEMENTS.md` - Questions system architecture
- `GetReceipts/database/migrations/010_RUN_THIS.md` - Migration instructions
- `GetReceipts/database/migrations/010_MIGRATION_NOTES.md` - Schema explanation

