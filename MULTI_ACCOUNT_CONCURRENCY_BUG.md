# Multi-Account Concurrency Bug

## Critical Finding

The multi-account download system is currently implementing **sequential rotation** instead of **concurrent downloads**, resulting in significantly slower throughput than intended.

## Current Implementation (WRONG)

**File:** `src/knowledge_system/services/multi_account_downloader.py:343-399`

```python
for idx, url in enumerate(unique_urls, 1):
    # Wait for an available account
    account_info = await self.get_available_account()
    
    # Download with this account (BLOCKS until complete)
    result = await self.download_with_failover(url, account_idx, scheduler, output_dir)
    results.append(result)
```

**Behavior:**
- Downloads happen **one at a time** (sequential)
- Account 1 downloads → completes → Account 2 downloads → completes → Account 3 downloads
- Only **1 download active** at any moment
- Throughput: ~15 videos/hour (1 every 4 minutes)

## Intended Implementation (CORRECT)

**Strategy:** Concurrent downloads from same IP (mimics family household)

```python
# Launch 2-5 concurrent download tasks
async def download_batch_concurrent(urls, max_concurrent=3):
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def download_with_semaphore(url):
        async with semaphore:
            # Wait for available account
            account_info = await self.get_available_account()
            # Download (other downloads continue in parallel)
            return await self.download_with_failover(url, account_idx, scheduler, output_dir)
    
    # Launch all downloads concurrently
    tasks = [download_with_semaphore(url) for url in urls]
    results = await asyncio.gather(*tasks)
```

**Behavior:**
- **2-5 downloads active simultaneously** (configurable)
- All from **same home IP** (looks like family household)
- Each account maintains 3-5 min delays between **its own** downloads
- Accounts don't wait for each other
- Throughput with 3 concurrent: ~45 videos/hour (3x faster)

## Why Same IP + Concurrent is SAFER

From `MULTI_ACCOUNT_GUI_IMPLEMENTATION.md:666-768`:

**What YouTube Sees:**

```
IP 123.45.67.89 (your home):
  Account 1: Download at 10:00, 10:04, 10:08 (4 min apart)
  Account 2: Download at 10:01, 10:05, 10:09 (4 min apart)  
  Account 3: Download at 10:02, 10:06, 10:10 (4 min apart)

YouTube's interpretation: "Normal family household with 3 people downloading videos"
Result: ✅ No flags, completely normal behavior
```

**vs. Sequential Rotation (current implementation):**

```
IP 123.45.67.89:
  Account 1: Download at 10:00
  Account 2: Download at 10:04
  Account 3: Download at 10:08
  Account 1: Download at 10:12
  
YouTube's interpretation: "One person switching between accounts?"
Result: ⚠️ Slower and potentially more suspicious pattern
```

## Performance Impact

| Implementation | Concurrent Downloads | Throughput | Time for 7000 videos |
|----------------|---------------------|------------|---------------------|
| **Current (sequential)** | 1 | ~15/hour | 467 hours (19.5 days) |
| **Intended (3 concurrent)** | 3 | ~45/hour | 156 hours (6.5 days) |
| **Intended (5 concurrent)** | 5 | ~75/hour | 93 hours (3.9 days) |

**Current implementation is 3-5x slower than intended!**

## Why Rate Limiting Controls Are NOT Obsolete

**User's Question:** "Does the multi-worker orchestrator make rate limiting obsolete?"

**Answer:** **NO** - Rate limiting is essential, but it works differently than currently implemented:

### Per-Account Delays (Essential)
- **Min delay: 180 sec, Max delay: 300 sec** = 3-5 minutes between downloads **for each account**
- Account 1: Download → wait 4 min → Download → wait 4 min
- Account 2: Download → wait 4 min → Download → wait 4 min
- Account 3: Download → wait 4 min → Download → wait 4 min

### Concurrent Execution (Missing)
- All 3 accounts download **at the same time** (not waiting for each other)
- From **same home IP** (looks like family)
- Overall rate: 3 downloads every 4 minutes = 45/hour

### What Needs to Change

**Rate Limiting UI (already fixed):**
- ✅ Changed title to "Rate Limiting (Per-Account Anti-Bot Protection)"
- ✅ Added explanation: "These delays apply per account in multi-account mode"
- ✅ Updated tooltips: "With 6 accounts, effective rate is 6x faster"

**Implementation (needs fix):**
- ❌ Change `download_batch_with_rotation()` from sequential loop to concurrent tasks
- ❌ Use `asyncio.Semaphore` to limit concurrent downloads (2-5)
- ❌ Use `asyncio.gather()` or task queue for parallel execution

## Recommended Fix

### Option 1: Semaphore-Based (Simpler)

```python
async def download_batch_with_rotation(
    self,
    urls: list[str],
    output_dir: Path,
    processing_queue: asyncio.Queue | None = None,
    progress_callback=None,
    max_concurrent: int = 3,  # NEW: configurable concurrency
) -> list[dict]:
    """Download batch with concurrent downloads from multiple accounts."""
    
    # Semaphore limits concurrent downloads
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def download_one(url: str, idx: int):
        async with semaphore:
            # Wait for available account (with cooldown)
            account_info = await self.get_available_account()
            if account_info is None:
                return {"success": False, "url": url, "error": "No accounts available"}
            
            account_idx, scheduler = account_info
            
            # Download (other downloads continue in parallel)
            result = await self.download_with_failover(url, account_idx, scheduler, output_dir)
            
            # Update last download time
            async with self.account_lock:
                self.last_download_times[account_idx] = time.time()
            
            return result
    
    # Launch all downloads concurrently (semaphore limits active count)
    tasks = [download_one(url, idx) for idx, url in enumerate(unique_urls, 1)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return results
```

### Option 2: Task Queue (More Control)

```python
async def download_batch_with_rotation(self, urls, output_dir, max_concurrent=3):
    """Download batch using task queue for better control."""
    
    url_queue = asyncio.Queue()
    for url in urls:
        await url_queue.put(url)
    
    async def worker():
        while not url_queue.empty():
            url = await url_queue.get()
            
            # Wait for available account
            account_info = await self.get_available_account()
            if account_info:
                account_idx, scheduler = account_info
                result = await self.download_with_failover(url, account_idx, scheduler, output_dir)
                results.append(result)
            
            url_queue.task_done()
    
    # Launch N concurrent workers
    workers = [asyncio.create_task(worker()) for _ in range(max_concurrent)]
    await url_queue.join()
    
    # Cancel workers
    for w in workers:
        w.cancel()
```

## Configuration

Add to `config.py`:

```python
class YouTubeProcessingConfig(BaseModel):
    # ... existing fields ...
    
    # Multi-account concurrency
    max_concurrent_downloads: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum concurrent downloads across all accounts (2-5 recommended for home IP)"
    )
```

## Testing Strategy

1. **Test with 1 account:** Should behave identically to current implementation
2. **Test with 3 accounts:** Should see 3 simultaneous downloads in logs
3. **Monitor timing:** Each account should maintain 3-5 min delays between its own downloads
4. **Verify IP:** All downloads should come from same home IP (no proxy rotation)

## Priority

**HIGH** - This bug reduces throughput by 3-5x compared to intended design.

For 7000 videos:
- Current: 19.5 days
- Fixed: 6.5 days (with 3 concurrent)
- **Time saved: 13 days**
