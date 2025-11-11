# Deduplication Bug Fix

## Problem

When attempting to transcribe a podcast URL (e.g., from Apple Podcasts), the system would immediately return "0 files ready for transcription" with the message "All URLs already downloaded, nothing to do", even when:

1. The audio file didn't exist on disk
2. The transcription had never been completed
3. Only a partial database record existed

## Root Cause

The deduplication logic was too aggressive. It checked only if a `source_id` existed in the `media_sources` table, without verifying:

1. **Audio file existence**: Whether the audio file actually exists on disk
2. **Transcription completion**: Whether the source has segments (transcription completed)
3. **Processing status**: Whether the previous attempt succeeded or failed

This meant that if a source was ever added to the database (even with just metadata), it would be skipped forever, even if the download or transcription had failed.

## Solution

### 1. Added `has_segments_for_source()` method to DatabaseService

```python
def has_segments_for_source(self, source_id: str) -> bool:
    """Check if a source has segments (transcription completed)."""
```

This method checks if a source has any segments in the database, which indicates that transcription was completed successfully.

### 2. Added `source_is_fully_processed()` method to DatabaseService

```python
def source_is_fully_processed(self, source_id: str) -> tuple[bool, str | None]:
    """
    Check if a source has been fully downloaded and transcribed.
    
    A source is considered fully processed if:
    1. It exists in the database (or has an alias)
    2. The audio file exists on disk
    3. It has segments (transcription completed)
    """
```

This method performs comprehensive checks to ensure a source is truly complete before skipping it.

### 3. Updated UnifiedDownloadOrchestrator

Changed from checking `source_exists_or_has_alias()` to `source_is_fully_processed()`:

```python
# OLD (too aggressive):
exists, existing_source_id = self.db_service.source_exists_or_has_alias(source_id)
if exists:
    # Skip download

# NEW (comprehensive):
is_complete, existing_source_id = self.db_service.source_is_fully_processed(source_id)
if is_complete:
    # Skip download only if truly complete
```

### 4. Fixed VideoDeduplicationService

- **Fixed bug**: Changed `self.db.get_video()` to `self.db.get_source()` (the `get_video` method didn't exist)
- **Enhanced completeness check**: Now verifies:
  - Audio is marked as downloaded
  - Audio file actually exists on disk
  - Source has segments (transcription completed)

## Files Modified

1. `src/knowledge_system/database/service.py`
   - Added `has_segments_for_source()` method
   - Added `source_is_fully_processed()` method

2. `src/knowledge_system/services/unified_download_orchestrator.py`
   - Updated deduplication logic to use `source_is_fully_processed()`

3. `src/knowledge_system/utils/deduplication.py`
   - Fixed `get_video()` → `get_source()` bug
   - Enhanced `_apply_policy()` to check audio file existence and segments

## Impact

- **Podcast RSS downloads**: Will now work correctly even if a source was previously attempted
- **YouTube downloads**: More robust deduplication that handles partial downloads
- **Failed transcriptions**: Can now be retried without manual database cleanup
- **Missing audio files**: Sources with missing audio files will be re-downloaded

## Testing

To test the fix, try transcribing a podcast URL that previously returned "0 files ready for transcription":

```bash
# Example URL that was failing:
https://podcasts.apple.com/us/podcast/regime-change-for-venezuela-peter-zeihan/id1702067155?i=1000734606759
```

The system should now:
1. Check if the source is fully processed (audio exists + has segments)
2. If not complete, proceed with download and transcription
3. Only skip if the source is truly complete

## Related Issues

This fix addresses the issue where the system would skip URLs that:
- Had metadata but no audio file
- Had audio file but no transcription
- Had failed previous attempts
- Had been partially processed

The new logic ensures that only truly complete sources (with audio file on disk AND transcription segments) are skipped.
