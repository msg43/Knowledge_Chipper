# Optimized Strategy: 7000 Videos on M2 Ultra 128GB

**Hardware**: M2 Ultra, 128 GB RAM, 24 cores  
**Constraint**: Cookie-based downloads with bot detection avoidance

---

## Hardware Capacity Analysis

### M2 Ultra Specs
- **CPU**: 24 cores (16 performance + 8 efficiency)
- **RAM**: 128 GB
- **Neural Engine**: 32-core (excellent for Whisper)

### Maximum Parallel Capacity

**RAM-based calculation**:
```
Available RAM: 128 - 8 (system) = 120 GB

Per video processing:
  Whisper model: ~2.5 GB (can be shared)
  LLM model (7B): ~5 GB
  Working memory: ~1 GB per worker
  Total: ~8.5 GB per fully independent video

Theoretical max: 120 GB ÷ 8.5 GB = 14 videos

BUT with shared LLM pool optimization:
  Shared LLM instances: 16 × 5 GB = 80 GB
  Shared Whisper instances: 6 × 2.5 GB = 15 GB
  Working memory: 20 GB
  Total: 115 GB
  
Optimized capacity: 20-24 parallel workers ✅
```

**CPU-based calculation**:
```
24 cores × 1.5 (for I/O overlap) = 36 threads

Optimal: 20-24 workers
```

**Recommendation**: **20 parallel workers** (good balance)

---

## The Download Bottleneck Problem

With 20 workers, processing becomes MUCH faster than downloads:

### Processing Rate (20 workers)
```
20 workers × 2.5 videos/hour each = 50 videos/hour
= 1,200 videos/day (if unlimited downloads available)
```

### Download Rate (6-hour sleep)
```
Active hours: 18/day
Download rate: 14 videos/hour (with 3-5 min delays)
= 252 videos/day

Processing capacity: 1,200/day
Download capacity: 252/day

Workers idle: 79% of the time! 😱
```

**Timeline**: Limited by downloads, not processing
```
7000 videos ÷ 252 per day = 27.8 days
```

---

## Solution: Adjust Sleep Period for Better Utilization

### Option 1: Reduce Sleep to 4 Hours (Recommended)

**Sleep**: 2am - 6am (4 hours)

```
Active hours: 20/day
Download rate: 14/hour × 20 hours = 280 videos/day

Processing capacity: 1,200/day
Download capacity: 280/day

Workers idle: 77% of time (still not great, but better)

Timeline: 7000 ÷ 280 = 25 days
```

**Benefit**: Still looks human (4-hour sleep is realistic for power user)

### Option 2: Eliminate Sleep Entirely (24/7) ⚡

**Sleep**: None (continuous)

```
Active hours: 24/day
Download rate: 14/hour × 24 hours = 336 videos/day

Processing capacity: 1,200/day
Download capacity: 336/day

Workers idle: 72% of time

Timeline: 7000 ÷ 336 = 21 days
```

**Safety**: Still very safe with 3-5 min delays + cookies + randomization

### Option 3: Multi-Account Parallelization (Advanced) 🚀

Use **3 throwaway accounts** with separate cookies:

```
Each account: 14 videos/hour
3 accounts parallel: 42 videos/hour
Daily (with 6-hour sleep): 42/hr × 18 hrs = 756 videos/day

Processing capacity: 1,200/day
Download capacity: 756/day

Workers idle: 37% (much better utilization!)

Timeline: 7000 ÷ 756 = 9.3 days ✅
```

### Option 4: Aggressive Multi-Account (Maximum Speed) 🏎️

Use **5 accounts** + **no sleep** + **20 workers**:

```
Each account: 14 videos/hour
5 accounts parallel: 70 videos/hour
Daily (24/7): 70/hr × 24 hrs = 1,680 videos/day

But processing limited to: 1,200/day

Actually becomes PROCESSING-LIMITED!

Timeline: 7000 ÷ 1,200 = 5.8 days ≈ 6 DAYS 🚀
```

---

## Comparison Table

| Strategy | Sleep | Accounts | Download Rate | Timeline | Safety | Worker Util |
|----------|-------|----------|---------------|----------|--------|-------------|
| **A: Current (6hr sleep, 1 account)** | 6hr | 1 | 252/day | **28 days** | Very Safe | 21% |
| **B: Light sleep (4hr, 1 account)** | 4hr | 1 | 280/day | **25 days** | Very Safe | 23% |
| **C: No sleep (24/7, 1 account)** | 0hr | 1 | 336/day | **21 days** | Safe | 28% |
| **D: Multi-account (6hr sleep, 3 accounts)** | 6hr | 3 | 756/day | **9 days** ✅ | Safe | 63% |
| **E: Aggressive (no sleep, 5 accounts)** | 0hr | 5 | 1,680/day | **6 days** 🚀 | Moderate | 100% |

---

## Recommended Strategy for M2 Ultra 128GB

### Primary Recommendation: **Option D** (Multi-Account with Sleep)

**Configuration**:
- **3 throwaway YouTube accounts** with separate cookie files
- **20 parallel processing workers**
- **6-hour sleep period** (midnight - 6am)
- **3-5 min delays per account** (same safety as before)

**Timeline**: **9-10 days** ✅

**Why this is optimal**:
1. **Safe**: Each account downloads at normal rate (14/hr)
2. **Human-like**: 6-hour sleep period maintained
3. **Good utilization**: 63% of worker capacity used
4. **Reasonable**: 3 throwaway accounts is manageable
5. **Fast**: ~9 days vs 28 days (3x speedup)

### Alternative: **Option E** (Maximum Speed)

If you're willing to:
- Manage 5 throwaway accounts
- Run 24/7 (no sleep period)
- Accept slightly higher risk (still moderate)

**Timeline**: **~6 days** 🚀

---

## Implementation for Multi-Account Strategy

### 1. Setup Multiple Accounts

Create 3-5 throwaway YouTube accounts:
```
Account 1: throwaway.yt.1@gmail.com
Account 2: throwaway.yt.2@gmail.com
Account 3: throwaway.yt.3@gmail.com
(Optional) Account 4, 5...
```

Export cookies for each:
```
cookies_account_1.txt
cookies_account_2.txt
cookies_account_3.txt
```

### 2. Enhanced Download Scheduler

```python
from knowledge_system.utils.deduplication import (
    VideoDeduplicationService,
    DuplicationPolicy,
)

class MultiAccountDownloadScheduler:
    """Manages downloads across multiple YouTube accounts with deduplication"""
    
    def __init__(
        self,
        cookie_files: list[str],
        parallel_workers: int = 20,
        enable_sleep_period: bool = True,
        sleep_start_hour: int = 0,
        sleep_end_hour: int = 6,
        db_service=None,
    ):
        self.cookie_files = cookie_files
        self.parallel_workers = parallel_workers
        self.enable_sleep_period = enable_sleep_period
        self.sleep_start = sleep_start_hour
        self.sleep_end = sleep_end_hour
        
        # Create scheduler for each account
        self.schedulers = [
            DownloadScheduler(
                cookie_file_path=cf,
                enable_sleep_period=enable_sleep_period,
                sleep_start_hour=sleep_start_hour,
                sleep_end_hour=sleep_end_hour,
            )
            for cf in cookie_files
        ]
        
        # Initialize deduplication service (shared across all accounts)
        self.dedup_service = VideoDeduplicationService(db_service)
        
        # Track last download time per account
        self.last_download_times = [0.0] * len(cookie_files)
        self.account_lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            "total_urls": 0,
            "unique_urls": 0,
            "duplicates_skipped": 0,
            "downloads_completed": 0,
        }
    
    async def get_available_account(self) -> tuple[int, DownloadScheduler] | None:
        """Get account that's ready to download (delay elapsed)"""
        async with self.account_lock:
            current_time = time.time()
            
            for idx, (scheduler, last_time) in enumerate(
                zip(self.schedulers, self.last_download_times)
            ):
                # Check if in sleep period
                if scheduler.is_sleep_time():
                    continue
                
                # Check if enough time elapsed since last download
                time_since_last = current_time - last_time
                required_delay = random.uniform(180, 300)  # 3-5 min
                
                if time_since_last >= required_delay:
                    return idx, scheduler
            
            return None
    
    async def download_batch_with_rotation(
        self,
        urls: list[str],
        output_dir: Path,
        processing_queue: asyncio.Queue,
    ):
        """Download URLs using account rotation with deduplication"""
        
        # Step 1: Filter duplicates BEFORE downloading
        logger.info(f"🔍 Checking {len(urls)} URLs for duplicates...")
        self.stats["total_urls"] = len(urls)
        
        unique_urls, duplicate_results = self.dedup_service.check_batch_duplicates(
            urls,
            DuplicationPolicy.SKIP_ALL  # Skip all duplicates
        )
        
        self.stats["unique_urls"] = len(unique_urls)
        self.stats["duplicates_skipped"] = len(duplicate_results)
        
        logger.info(
            f"✅ Deduplication complete: {len(unique_urls)} unique, "
            f"{len(duplicate_results)} duplicates skipped"
        )
        
        if duplicate_results:
            logger.info(
                f"💰 Time saved by skipping duplicates: "
                f"~{len(duplicate_results) * 25 / 60:.1f} hours"
            )
        
        # Step 2: Download only unique URLs
        for url in unique_urls:
            # Wait for available account
            account_info = None
            while account_info is None:
                account_info = await self.get_available_account()
                
                if account_info is None:
                    # All accounts on cooldown or sleeping
                    await asyncio.sleep(10)
                
                # Check if processing queue is full
                if processing_queue.qsize() >= self.parallel_workers * 2:
                    # Queue is full, wait before downloading more
                    account_info = None
                    await asyncio.sleep(30)
            
            account_idx, scheduler = account_info
            
            # Download with this account
            try:
                result = await scheduler.download_single(url, output_dir)
                
                if result["success"]:
                    await processing_queue.put(result["audio_file"])
                    self.stats["downloads_completed"] += 1
                
                # Update last download time for this account
                async with self.account_lock:
                    self.last_download_times[account_idx] = time.time()
                
                logger.info(
                    f"✅ Downloaded via account {account_idx+1}/{len(self.schedulers)} "
                    f"({self.stats['downloads_completed']}/{len(unique_urls)}), "
                    f"queue: {processing_queue.qsize()}"
                )
                
            except Exception as e:
                logger.error(f"Download failed (account {account_idx+1}): {e}")
        
        # Log final statistics
        logger.info(
            f"📊 Download batch complete: "
            f"{self.stats['downloads_completed']}/{self.stats['unique_urls']} downloaded, "
            f"{self.stats['duplicates_skipped']} duplicates skipped, "
            f"{self.stats['total_urls']} total URLs processed"
        )
    
    def get_stats(self) -> dict:
        """Get download statistics"""
        return {
            **self.stats,
            "duplicate_rate": (
                self.stats["duplicates_skipped"] / self.stats["total_urls"]
                if self.stats["total_urls"] > 0
                else 0.0
            ),
            "success_rate": (
                self.stats["downloads_completed"] / self.stats["unique_urls"]
                if self.stats["unique_urls"] > 0
                else 0.0
            ),
        }
```

### 3. Configuration

**File**: `config/settings.yaml`

```yaml
youtube_processing:
  # Multi-account setup
  cookie_files:
    - "cookies_account_1.txt"
    - "cookies_account_2.txt"
    - "cookies_account_3.txt"
  
  # Download delays (per account)
  sequential_download_delay_min: 180.0  # 3 min
  sequential_download_delay_max: 300.0  # 5 min
  
  # Sleep period (Option D: 6 hours)
  enable_sleep_period: true
  sleep_start_hour: 0
  sleep_end_hour: 6
  sleep_timezone: "America/Los_Angeles"

hce_processing:
  # M2 Ultra 128GB optimization
  parallel_mining_workers: 20
  auto_detect_parallel_capacity: false  # Manual override
```

### 4. Usage

```python
# Option D: 3 accounts, 6-hour sleep, 20 workers
scheduler = MultiAccountDownloadScheduler(
    cookie_files=[
        "cookies_account_1.txt",
        "cookies_account_2.txt",
        "cookies_account_3.txt",
    ],
    parallel_workers=20,
    enable_sleep_period=True,
    sleep_start_hour=0,
    sleep_end_hour=6,
)

# Download + process
urls = [...]  # 7000 URLs
processing_queue = asyncio.Queue(maxsize=40)

# Start download and processing in parallel
await asyncio.gather(
    scheduler.download_batch_with_rotation(urls, output_dir, processing_queue),
    process_queue_with_workers(processing_queue, num_workers=20),
)

# Expected: 9-10 days total
```

---

## Updated Timeline Estimates for M2 Ultra 128GB

### Single Account Strategies

| Strategy | Workers | Sleep | Downloads/Day | Timeline |
|----------|---------|-------|---------------|----------|
| Conservative | 20 | 6hr | 252 | **28 days** |
| Moderate | 20 | 4hr | 280 | **25 days** |
| Aggressive | 20 | None | 336 | **21 days** |

### Multi-Account Strategies (Better Utilization)

| Strategy | Workers | Accounts | Sleep | Downloads/Day | Timeline |
|----------|---------|----------|-------|---------------|----------|
| **Recommended** | 20 | 3 | 6hr | 756 | **9 days** ✅ |
| Aggressive | 20 | 5 | 6hr | 1,260 | **6 days** |
| Maximum | 20 | 5 | None | 1,680 | **6 days** 🚀 |

---

## Safety Considerations

### 3-Account Strategy (Option D)

**Per-account behavior**:
- 14 downloads/hour per account (same as single account)
- 3-5 min delays per account
- 6-hour sleep period
- Cookie authentication

**From YouTube's perspective**:
- 3 separate users downloading videos
- Each following normal patterns
- No connection between accounts (separate cookies, can use separate IPs if desired)

**Risk level**: ⭐⭐⭐⭐⭐ Very Safe (each account behaves normally)

### 5-Account Strategy (Option E)

**Same per-account behavior**, just more accounts

**Risk level**: ⭐⭐⭐⭐ Safe (requires managing more accounts)

---

## Recommendation Summary

For **M2 Ultra 128GB**, I recommend:

### **Option D: 3 Accounts + 6-Hour Sleep + 20 Workers**

**Why**:
- ✅ **Fast**: 9-10 days (3x faster than single account)
- ✅ **Safe**: Each account follows conservative patterns
- ✅ **Efficient**: 63% worker utilization (reasonable)
- ✅ **Manageable**: Only 3 throwaway accounts to set up
- ✅ **Human-like**: Maintains 6-hour sleep period

**Setup effort**:
- Create 3 throwaway Gmail accounts (~30 min)
- Export cookies from each (~10 min)
- Configure multi-account scheduler (~5 min)
- Total: ~1 hour setup for 19-day time savings

**Timeline**: **9-10 days** instead of 28 days with single account

---

## Alternative: If You Don't Want Multi-Account

If managing multiple accounts is too much hassle:

### **Single Account + No Sleep + 20 Workers**

- Timeline: **21 days**
- Safety: Still very safe (3-5 min delays + cookies)
- Setup: Just use existing single-account code
- Worker utilization: 28% (low, but you have RAM to spare)

This is the **simplest option** that still leverages your hardware better than the M2 Max setup.

---

**Bottom Line**: With 128GB RAM, you can run 20+ workers, but you need either multiple accounts OR 24/7 downloads to keep them fed. The 3-account strategy is the sweet spot for speed + safety.
