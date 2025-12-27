# Multi-Account Download Timeout Fix

**Date:** December 26, 2025  
**Status:** ✅ Implemented

## Problem

The multi-account download system could get stuck on a single channel that wasn't making progress, blocking all other accounts from downloading. This resulted in:

- Single stuck download blocking entire batch
- No timeout mechanism to move on to next account
- Poor throughput when one account encountered issues
- Long wait times before system could recover

## Solution

Implemented a 60-second timeout mechanism with automatic failover and retry logic.

### Key Changes

#### 1. Per-Download Timeout (60 seconds)

```python
# Each download now has a 60-second timeout
result = await asyncio.wait_for(
    scheduler.download_single(url, output_dir),
    timeout=60.0
)
```

**Behavior:**
- If download doesn't complete in 60 seconds, system moves to next account
- Timeout downloads automatically added to retry queue
- Other accounts continue downloading without interruption

#### 2. Timeout Exception Handling

```python
except asyncio.TimeoutError:
    logger.warning(
        f"⏱️ Download timeout (account {account_idx+1}): {url} "
        f"exceeded {timeout}s - moving to next account"
    )
    # Add to retry queue for later attempt
    self.retry_queue.append(url)
```

**Benefits:**
- Clear logging when timeouts occur
- Failed URLs preserved for retry
- Account health tracking updated appropriately

#### 3. Enhanced Retry Queue Processing

```python
# Retry with same 60s timeout
result = await self.download_with_failover(
    url, account_idx, scheduler, output_dir, timeout=60.0
)
```

**Features:**
- Retries also use 60-second timeout
- Better progress reporting ("Retry 5/23 successful")
- Timeout for waiting on accounts (max 2 minutes)
- Statistics on retry success/failure rates

## Usage

### Default Behavior (Automatic)

The timeout is applied automatically to all downloads:

```python
# In download_batch_with_rotation()
result = await self.download_with_failover(
    url, account_idx, scheduler, output_dir, timeout=60.0
)
```

### Custom Timeout (Advanced)

You can specify a different timeout if needed:

```python
# Longer timeout for large files
result = await self.download_with_failover(
    url, account_idx, scheduler, output_dir, timeout=120.0
)
```

## Expected Behavior

### Scenario 1: Normal Download

```
Account 1: Download starts → completes in 30s → ✅ Success
Account 2: Download starts → completes in 45s → ✅ Success
Account 3: Download starts → completes in 25s → ✅ Success
```

### Scenario 2: Stuck Download

```
Account 1: Download starts → stuck at 30s → timeout at 60s → ⏱️ Timeout
           → Added to retry queue
Account 2: Download starts → completes in 40s → ✅ Success
Account 3: Download starts → completes in 35s → ✅ Success

Retry Round:
Account 2: Retry stuck URL → completes in 50s → ✅ Success (recovered)
```

### Scenario 3: Multiple Stuck Downloads

```
Account 1: Download starts → timeout at 60s → ⏱️ Timeout → retry queue
Account 2: Download starts → timeout at 60s → ⏱️ Timeout → retry queue
Account 3: Download starts → completes in 45s → ✅ Success

Retry Round 1:
Account 3: Retry URL 1 → completes in 55s → ✅ Success
Account 1: Retry URL 2 → timeout at 60s → ⏱️ Timeout → retry queue

Final Result:
- 2 successful downloads
- 1 failed (after 2 attempts)
- Logged to retry queue for manual review
```

## Statistics Tracking

The system tracks timeout-related statistics:

```python
stats = {
    "downloads_completed": 45,      # Successful downloads
    "downloads_failed": 5,          # Failed (including timeouts)
    "retries_attempted": 5,         # URLs retried
    "retries_successful": 3,        # Retries that succeeded
    "retry_success_rate": 0.60,     # 60% of retries succeeded
}
```

## Logging Examples

### Timeout Notification

```
⏱️ Download timeout (account 2): https://youtube.com/watch?v=abc123 
   exceeded 60s - moving to next account
```

### Retry Progress

```
🔄 Retry round 1: Processing 5 failed URLs
✅ Retry 1/5 successful with account 3
✅ Retry 2/5 successful with account 1
❌ Retry 3/5 failed: https://youtube.com/watch?v=xyz789
✅ Retry 4/5 successful with account 2
✅ Retry 5/5 successful with account 3
📊 Retry round complete: 4 successful, 1 still failed
```

### Final Statistics

```
📊 Download batch complete: 
   45/50 successful, 5 failed, 3 duplicates skipped, 0 accounts disabled
```

## Benefits

1. **Improved Throughput**: System no longer blocked by single stuck download
2. **Better Resource Utilization**: All accounts can work without waiting
3. **Automatic Recovery**: Timeout downloads automatically retried
4. **Clear Visibility**: Detailed logging shows exactly what's happening
5. **Predictable Timing**: Each download has maximum 60s before moving on

## Technical Details

### File Modified

- `src/knowledge_system/services/multi_account_downloader.py`

### Methods Changed

1. `download_with_failover()` - Added timeout parameter and TimeoutError handling
2. `download_batch_with_rotation()` - Pass timeout to download calls
3. `_process_retry_queue()` - Enhanced retry logic with timeouts and better logging

### Timeout Values

- **Download timeout**: 60 seconds (configurable)
- **Account wait timeout (retry)**: 120 seconds
- **Account wait timeout (main loop)**: 600 seconds (unchanged)

## Testing

To test the timeout behavior:

```python
# Simulate stuck download by using very short timeout
result = await self.download_with_failover(
    url, account_idx, scheduler, output_dir, timeout=5.0
)
```

Expected: Download times out after 5 seconds, moves to next account, URL added to retry queue.

## Future Enhancements

Potential improvements for future versions:

1. **Adaptive Timeouts**: Adjust timeout based on file size or network speed
2. **Timeout Statistics**: Track average download times per account
3. **Smart Retry Delays**: Wait longer before retrying timed-out URLs
4. **Partial Download Resume**: Resume from last position instead of restarting
5. **Timeout Patterns**: Identify accounts that consistently timeout

## Related Documentation

- `MULTI_ACCOUNT_IMPLEMENTATION_STATUS.md` - Overall multi-account system
- `MULTI_ACCOUNT_FAQ.md` - Common questions and troubleshooting
- `SESSION_BASED_ANTI_BOT_COMPLETE.md` - Session-based scheduling

