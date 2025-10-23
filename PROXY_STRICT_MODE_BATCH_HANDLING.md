# Proxy Strict Mode - Batch Processing Update

## Summary

Updated proxy strict mode to handle batch processing intelligently: instead of failing the entire batch when proxy fails, the system now attempts each URL individually with fresh proxy attempts, and only writes permanently failed URLs to the failed_urls file at the end.

## Problem

The initial implementation of strict mode would block the entire batch of URLs if proxy initialization or testing failed upfront. This was too aggressive - if you had 10 URLs and the proxy had a temporary issue, all 10 URLs would be blocked immediately.

## Solution

Refactored to use **per-URL proxy validation** with **graceful degradation**:
- Each URL gets its own proxy attempt
- Failed URLs are skipped and tracked
- Processing continues for remaining URLs
- All failures written to file at the end

## Implementation Details

### 1. Removed Batch-Level Blocking

**Before** (lines 271-332):
- Checked proxy once at start of batch
- If proxy failed → returned error immediately
- Blocked ALL URLs in the batch

**After** (lines 271-299):
- Initialize proxy manager but don't block
- Log warnings about strict mode
- Continue to per-URL processing

### 2. Added Per-URL Proxy Checking

**Location**: `youtube_download.py` lines 687-720

```python
# STRICT MODE CHECK: Try to get proxy for this URL
proxy_available_for_this_url = False
if use_proxy and proxy_manager:
    try:
        current_proxy_url = proxy_manager.get_proxy_url(session_id=session_id)
        if current_proxy_url:
            proxy_available_for_this_url = True
    except Exception as e:
        logger.warning(f"Failed to get proxy URL for {video_id}: {e}")
        current_proxy_url = None

# STRICT MODE: Skip URL if no proxy available
if strict_mode and not proxy_available_for_this_url:
    error_msg = f"Proxy strict mode: Skipping {url} - no proxy available"
    logger.warning(f"⚠️ {error_msg}")
    if progress_callback:
        progress_callback(f"⏭️ Skipping ({i}/{len(urls)}): No proxy available (strict mode)")
    errors.append(error_msg)
    url_index += 1
    continue  # Skip to next URL
```

### 3. Error Collection and Tracking

**Mechanism**:
1. **Per-URL**: Failed URLs added to `errors` list (line 718)
2. **Batch End**: All errors returned in `ProcessorResult` (line 1637)
3. **Transcription Tab**: Processes errors and calls `_write_to_failed_urls_file` (lines 524-552)
4. **File Output**: Failed URLs written to `logs/failed_urls_TIMESTAMP.txt`

### 4. Proxy Test Behavior

**Location**: `youtube_download.py` lines 401-407

**Strict Mode Enabled**:
```
❌ PacketStream proxy test failed: [error]
⚠️ Strict mode: Will attempt each URL with fresh proxy
```
- Doesn't block batch
- Each URL gets individual proxy attempt
- Failed URLs skipped gracefully

**Strict Mode Disabled**:
- Single URL: Proceeds with direct connection
- Multiple URLs: Blocked (prevents bulk direct downloads)

## User Experience

### Scenario: 10 URLs, Proxy Temporarily Unavailable

**Strict Mode Enabled**:
1. System attempts to initialize proxy → Fails
2. Logs: "Will attempt each URL individually"
3. For each URL:
   - Tries to get fresh proxy
   - If fails: Skips URL, adds to errors
   - If succeeds: Downloads normally
4. End result:
   - Some URLs successfully downloaded (when proxy worked)
   - Failed URLs written to `failed_urls_TIMESTAMP.txt`
   - User can retry failed URLs later

**Strict Mode Disabled**:
- Single URL: Uses direct connection (risky but allowed)
- Multiple URLs: Blocked entirely (prevents IP exposure)

## Files Modified

1. **`src/knowledge_system/processors/youtube_download.py`**
   - Lines 256-299: Removed batch-level blocking
   - Lines 401-407: Updated proxy test to not block batch
   - Lines 687-720: Added per-URL proxy checking

2. **`src/knowledge_system/gui/tabs/transcription_tab.py`**
   - Lines 524-552: Existing failed URL writing mechanism (no changes needed)

## Failed URL File Format

```
https://youtube.com/watch?v=VIDEO_ID_1
# Error: Proxy strict mode: Skipping https://youtube.com/watch?v=VIDEO_ID_1 - no proxy available
# Timestamp: 2025-01-20T14:30:45.123456

https://youtube.com/watch?v=VIDEO_ID_2
# Error: Proxy strict mode: Skipping https://youtube.com/watch?v=VIDEO_ID_2 - no proxy available
# Timestamp: 2025-01-20T14:30:47.654321
```

## Benefits

1. **Resilience**: Temporary proxy issues don't kill entire batch
2. **Efficiency**: Successfully process what you can, skip what you can't
3. **Visibility**: Clear logging of which URLs failed and why
4. **Retry-able**: Failed URLs saved to file for manual retry
5. **IP Protection**: Still maintains strict mode protection per-URL

## Testing Scenarios

### Test 1: All URLs Succeed
- Proxy working for all URLs
- All downloads complete successfully
- No failed_urls file created

### Test 2: Some URLs Fail
- Proxy works for URLs 1, 3, 5
- Proxy fails for URLs 2, 4
- URLs 1, 3, 5 download successfully
- URLs 2, 4 skipped and written to failed_urls file

### Test 3: Proxy Completely Down
- Proxy fails for all URLs
- All URLs skipped
- All URLs written to failed_urls file
- Batch completes (doesn't hang)

### Test 4: Proxy Recovers Mid-Batch
- Proxy fails for URLs 1-3
- Proxy recovers for URLs 4-10
- URLs 1-3 written to failed_urls file
- URLs 4-10 download successfully

## Monitoring

### Logs to Watch For

**Per-URL Success**:
```
✅ Using PacketStream proxy session 'session_id' for video VIDEO_ID (5/10)
```

**Per-URL Failure** (Strict Mode):
```
⚠️ Proxy strict mode: Skipping https://youtube.com/watch?v=VIDEO_ID - no proxy available
⏭️ Skipping (5/10): No proxy available (strict mode)
```

**Batch Complete**:
```
💾 Saved failed URL to: logs/failed_urls_20250120_143045.txt
```

## Migration Notes

- **Existing behavior preserved**: Non-strict mode works same as before
- **New behavior**: Strict mode is more intelligent about batch handling
- **No breaking changes**: All APIs remain compatible
- **Better UX**: Users see progress instead of immediate failure

## Recommendations

1. **Monitor failed_urls files**: Check these periodically for patterns
2. **Retry failed URLs**: Use the saved file to retry later when proxy is stable
3. **Proxy health**: If seeing many failures, check proxy service status
4. **Batch size**: Larger batches benefit more from per-URL resilience

