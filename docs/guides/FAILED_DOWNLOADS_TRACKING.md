# Failed Downloads Tracking & Reporting ✅

## Overview

Enhanced the TranscriptionTab to **track and report failed YouTube downloads** in an easily accessible format, especially important for large batches (6000+ URLs).

## Implementation

### What's Tracked

For each failed download, the system captures:
- **Full URL** (not truncated)
- **Error message** (technical details)
- **Error guidance** (user-friendly advice)
- **Index position** (which video in the batch)

### Data Structure

```python
self.failed_urls = [
    {
        "url": "https://youtube.com/watch?v=...",
        "error": "HTTP Error 503: Service Unavailable",
        "error_guidance": "Proxy unavailable - check Settings or disable proxy checkbox",
        "index": 5
    },
    ...
]
```

## User-Accessible Outputs

### 1. GUI Log Display (Real-time)

During processing, failures show with truncated URLs for readability:
```
❌ [5/100] Failed: https://youtube.com/watch?v=test... - Bot detected - increase delay
```

### 2. End-of-Job Summary (GUI)

At completion, full details displayed in the output area:
```
============================================================
📋 FAILED DOWNLOADS SUMMARY (5 URLs)
============================================================
❌ [5] https://youtube.com/watch?v=dQw4w9WgXcQ
   Error: Bot detected - increase delay between downloads or use proxy
❌ [23] https://youtube.com/watch?v=jNQXAC9IVRw
   Error: Proxy unavailable - check Settings or disable proxy checkbox
❌ [47] https://youtube.com/watch?v=9bZkp7q19f0
   Error: Video not accessible - may be deleted or region-locked
❌ [88] https://youtube.com/watch?v=kJQP7kiw5Fk
   Error: Format unavailable - video may be restricted or deleted
❌ [91] https://youtube.com/watch?v=HIcSWuKMwOw
   Error: Bot detected - increase delay between downloads or use proxy
============================================================
💡 Tip: Copy URLs above or use saved file to retry
============================================================
💾 Failed URLs saved to: /path/to/output/failed_downloads.txt
```

**Benefits:**
- ✅ **Full URLs visible** (can copy/paste directly)
- ✅ **Actionable guidance** for each failure
- ✅ **Easy to copy** from GUI for immediate retry
- ✅ **Scrollable summary** at end of job

### 3. Saved File (Persistent)

**Location**: `{output_directory}/failed_downloads.txt`

**Format**:
```
# Failed YouTube Downloads - 5 URLs
# Generated: 2025-10-12 14:35:22

https://youtube.com/watch?v=dQw4w9WgXcQ
# Error: Bot detected - increase delay between downloads or use proxy

https://youtube.com/watch?v=jNQXAC9IVRw
# Error: Proxy unavailable - check Settings or disable proxy checkbox

https://youtube.com/watch?v=9bZkp7q19f0
# Error: Video not accessible - may be deleted or region-locked

https://youtube.com/watch?v=kJQP7kiw5Fk
# Error: Format unavailable - video may be restricted or deleted

https://youtube.com/watch?v=HIcSWuKMwOw
# Error: Bot detected - increase delay between downloads or use proxy
```

**Benefits:**
- ✅ **One URL per line** (easy parsing/processing)
- ✅ **Comments preserved** (context for errors)
- ✅ **Standard text format** (works with any tool)
- ✅ **Timestamped** (track when failures occurred)
- ✅ **Can paste directly** back into input box for retry

### 4. Log Files (Technical Details)

**Location**: Log file (configured in system settings)

**Format**:
```
ERROR [EnhancedTranscriptionWorker] [5/100] Failed to download after 3 attempts: https://youtube.com/watch?v=dQw4w9WgXcQ
ERROR [EnhancedTranscriptionWorker] [23/100] Bot detection for https://youtube.com/watch?v=jNQXAC9IVRw: Sign in to confirm you're not a bot
```

**Benefits:**
- ✅ Full technical details for debugging
- ✅ Includes all retry attempts
- ✅ Timestamped for correlation
- ✅ Survives app restart

## Workflow for Large Batches (6000+ URLs)

### Initial Run
```
User: Paste 6000 URLs into Transcription Tab
System: 
  - Downloads with conveyor belt (3-6 concurrent)
  - Applies delays and proxies
  - Tracks failures in real-time
  - Saves failed_downloads.txt

Result: 5800 success, 200 failures
```

### Retry Workflow
```
User: 
  1. Open output/failed_downloads.txt
  2. Copy all URLs (Cmd+A, Cmd+C)
  3. Paste into Transcription Tab input box
  4. Adjust settings (increase delay, enable proxy)
  5. Start processing

System:
  - Processes only the 200 failed URLs
  - Updates failed_downloads.txt with new failures

Result: 150 success, 50 failures
```

### Final Retry
```
User: Repeat with remaining 50 URLs

Result: 45 success, 5 persistent failures
```

**Final Status**: 5995/6000 successful (99.9%)

## Error Categories with Guidance

### 1. **Bot Detection**
```
Error: Bot detected - increase delay between downloads or use proxy
```
**Resolution:**
- Increase download delay (10-15s)
- Enable PacketStream proxy
- Reduce concurrent downloads

### 2. **Proxy Issues**
```
Error: Proxy unavailable - check Settings or disable proxy checkbox
```
**Resolution:**
- Check PacketStream credentials in Settings
- Verify proxy service status
- Temporarily disable proxy and use delays

### 3. **Video Unavailable**
```
Error: Video not accessible - may be deleted or region-locked
```
**Resolution:**
- Video permanently unavailable
- Remove from retry list
- Check if video was deleted/privated

### 4. **Format Issues**
```
Error: Format unavailable - video may be restricted or deleted
```
**Resolution:**
- Video format not available
- May be age-restricted or region-locked
- Usually not retryable

### 5. **Authentication Required**
```
Error: Video requires authentication - cannot download
```
**Resolution:**
- Members-only or private video
- Cannot download without cookies (not supported)
- Remove from retry list

## Code Changes

### Files Modified
- `src/knowledge_system/gui/tabs/transcription_tab.py`

### Key Changes

**1. Added tracking list to worker** (Line 69):
```python
self.failed_urls = []  # Track failed URLs with details
```

**2. Track failures in download method** (Lines 256-262):
```python
# Track failed URL with full details
self.failed_urls.append({
    "url": url,
    "error": last_error or "Unknown error",
    "error_guidance": error_guidance,
    "index": idx
})
```

**3. Display summary at end** (Lines 615-654):
```python
# Display failed URLs summary if any
if self.failed_urls:
    # Show formatted summary in GUI
    # Save to failed_downloads.txt
```

## Benefits

### For Users
1. **No more searching through logs** - all failures in one place
2. **Easy retry workflow** - copy/paste URLs directly
3. **Actionable guidance** - know what to try next
4. **Persistent storage** - failures saved to file
5. **Progress tracking** - see which URLs in batch failed

### For Support/Debugging
1. **Clear error patterns** - quickly identify systemic issues
2. **Reproduction data** - exact URLs that failed
3. **Timestamp correlation** - match failures to system events
4. **Complete context** - error + guidance + index

### For Large Batch Processing
1. **Iterative retry** - process failures incrementally
2. **Progress monitoring** - track success rate over retries
3. **Resource optimization** - focus on problematic URLs
4. **Completion tracking** - know when batch is truly done

## Testing

### Test Scenarios

**1. Single failure in small batch (10 URLs)**
- ✅ Failure shown in real-time
- ✅ Summary displayed at end
- ✅ File saved with 1 URL
- ✅ Full URL visible in GUI

**2. Multiple failures in medium batch (100 URLs)**
- ✅ All failures tracked
- ✅ Summary shows all 10 failed URLs
- ✅ File saved with proper formatting
- ✅ Copy/paste works for retry

**3. Many failures in large batch (1000 URLs)**
- ✅ Summary doesn't crash GUI (long list)
- ✅ File saved successfully
- ✅ Can paste file contents back into input
- ✅ Retry works with saved file

**4. No failures (perfect run)**
- ✅ No summary displayed
- ✅ No file created
- ✅ Clean completion message

**5. All failures (complete failure)**
- ✅ Summary shows all URLs
- ✅ File saved with all URLs
- ✅ Clear indication of 0% success

## Future Enhancements

### Potential Improvements:
1. **CSV export**: Include metadata (video title, duration, error code)
2. **Failure categories**: Group by error type for batch resolution
3. **Auto-retry**: Automatically retry with adjusted settings
4. **Success tracking**: Save successfully downloaded URLs too
5. **Stats dashboard**: Show failure patterns over time
6. **Batch comparison**: Track improvement across retry attempts

### Not Recommended:
- ❌ Automatic infinite retries (wastes resources)
- ❌ Email notifications (too noisy for large batches)
- ❌ Database storage (overkill for simple text list)

## Comparison: Before vs After

### Before ❌
```
User: "100 URLs failed, which ones?"
System: "Check the log file..."
User: *scrolls through 10,000 log lines*
User: *manually copies truncated URLs*
User: *tries to reconstruct full URLs*
Result: Frustration, lost time, incomplete retry
```

### After ✅
```
User: "100 URLs failed, which ones?"
System: "Here's the list + saved to failed_downloads.txt"
User: *opens file*
User: *copies all URLs (Cmd+A, Cmd+C)*
User: *pastes into input box*
Result: Clean retry in 30 seconds
```

## Example Output

### Real-world scenario: 6000 URLs

**First run:**
```
🏁 Download complete: 5823 successful, 177 failed
⚠️ 177 download(s) failed - see summary below

============================================================
📋 FAILED DOWNLOADS SUMMARY (177 URLs)
============================================================
[... 177 URLs with full details ...]
💾 Failed URLs saved to: /Users/user/output/failed_downloads.txt
============================================================
```

**User copies failed_downloads.txt contents, pastes, increases delay from 5s to 10s, reruns**

**Second run:**
```
🏁 Download complete: 159 successful, 18 failed
⚠️ 18 download(s) failed - see summary below

============================================================
📋 FAILED DOWNLOADS SUMMARY (18 URLs)
============================================================
[... 18 URLs with full details ...]
💾 Failed URLs saved to: /Users/user/output/failed_downloads.txt
============================================================
```

**User copies, increases delay to 15s, reruns**

**Third run:**
```
🏁 Download complete: 15 successful, 3 failed
⚠️ 3 download(s) failed - see summary below

============================================================
📋 FAILED DOWNLOADS SUMMARY (3 URLs)
============================================================
❌ [1] https://youtube.com/watch?v=deleted_video
   Error: Video not accessible - may be deleted or region-locked
❌ [2] https://youtube.com/watch?v=members_only
   Error: Video requires authentication - cannot download
❌ [3] https://youtube.com/watch?v=region_locked
   Error: Video not accessible - may be deleted or region-locked
============================================================
```

**User inspects, determines videos are truly unavailable, removes from list**

**Final result:** 5997/6000 successful (99.95%)

---

## Summary

✅ **Failed downloads now tracked with full details**
✅ **Multiple access methods** (GUI, file, logs)
✅ **Easy retry workflow** (copy/paste friendly)
✅ **Actionable guidance** for each error type
✅ **Persistent storage** in text file
✅ **Optimized for large batches** (6000+ URLs)
✅ **No data loss** - full URLs preserved
✅ **User-friendly format** - ready to use

This dramatically improves the user experience for batch YouTube downloads, especially when processing thousands of URLs.
