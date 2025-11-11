# Summarization Crash Fix

## Issue

The application was crashing immediately when attempting to summarize content from the database (using `db://` sources).

## Root Cause

In `src/knowledge_system/core/system2_orchestrator_mining.py`, the `file_path` variable was only defined inside a conditional block (lines 81-91) when segments couldn't be loaded from the database. However, the variable was later used unconditionally on lines 313 and 323:

```python
# Line 313
episode_title = Path(file_path).stem

# Line 323
episode_title=Path(file_path).stem,
```

When processing database sources (where segments ARE successfully loaded from the database), `file_path` was never defined, causing a `NameError: name 'file_path' is not defined` crash.

## Fix

1. **Early initialization**: Moved `file_path = config.get("file_path")` to the beginning of the function (line 54), so it's always defined (may be `None` for DB-only sources).

2. **Safe fallback**: Changed lines 313 and 323 to use a fallback when `file_path` is `None`:
   ```python
   episode_title = Path(file_path).stem if file_path else source_id
   ```

3. **Simplified conditional**: Removed redundant `file_path = config.get("file_path")` from line 81 since it's now defined earlier.

## Additional Fixes

While fixing the original crash, several related issues were discovered and fixed:

### Schema Mismatches
1. **Segment model fields**: Changed `episode_id` → `source_id`, `start_time/end_time` → `t0/t1` to match HCE types
2. **EpisodeBundle fields**: Changed `episode_id` → `source_id` to match HCE types  
3. **ClaimStore parameters**: Fixed `episode_title` → `source_title` and removed duplicate `source_id` parameter
4. **Error checkpoint**: Initialized `completed_segment_ids` early to prevent undefined variable error

### Database Segment Loading
5. **Enhanced `_load_transcript_segments_from_db`**: Added support for loading segments from the claim-centric `Segment` table, with fallback to legacy `Transcript.transcript_segments_json`. This enables database-only summarization without requiring file paths.

### File Generation
6. **Fixed `generate_summary_markdown_from_pipeline` call**: Removed duplicate `source_id` parameter - method signature only takes 2 arguments but was being called with 3, causing file generation to fail silently.

## Testing

All fixes have been tested and verified:
- ✅ File-based summarization works correctly (tested and verified)
- ✅ Database-based summarization works correctly (tested and verified)
- ✅ Summary markdown files generate correctly
- ✅ Episode title falls back to `source_id` when no file path is available
- ✅ No linter errors introduced
- ✅ Schema consistency between HCE types and database models
- ✅ Segments load from both claim-centric and legacy schemas

## Files Changed

- `src/knowledge_system/core/system2_orchestrator_mining.py` - Main fix for file_path undefined error
- `src/knowledge_system/core/system2_orchestrator.py` - Schema fixes for Segment and EpisodeBundle types

## Impact

Users can now successfully summarize content from:
1. ✅ **Database sources** - Transcripts already stored in the database (no file required)
2. ✅ **File-based sources** - Markdown transcript files
3. ✅ **Mixed workflows** - Seamlessly handles both DB and file sources

The crash is completely eliminated and the system gracefully handles all scenarios. The summarization feature now works reliably from the GUI for both database and file-based content.
