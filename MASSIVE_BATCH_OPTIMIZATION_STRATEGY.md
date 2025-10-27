# Massive Batch Processing Optimization (7000 Videos)

## Executive Summary

For processing 7000 videos, the **download stage with cookie-based authentication is the critical bottleneck**, representing 98%+ of total wall clock time. A dynamic parallelization strategy can reduce processing from **~24 days to ~3-5 days** while maintaining bot-detection safety.

---

## Current Bottleneck Analysis

### Time Breakdown (Per Video, Typical 1-hour content)

| Stage | Time | Parallelizable? | Current Status |
|-------|------|-----------------|----------------|
| **Download (w/ cookies)** | **3-5 min delay** | ❌ Sequential only | Bottleneck (98% of time) |
| Download (actual) | 30-60 sec | ✅ Yes (with proxies) | Fast |
| Transcription (Whisper) | 10-30 min | ✅ Yes | Optimized |
| Mining (HCE Pass 1) | 2-5 min | ✅ Yes (segment-level) | Optimized |
| Evaluation (HCE Pass 2-4) | 30-60 sec | ⚠️ Limited | Acceptable |
| Storage | < 2 sec | ✅ Yes | Fast |

### For 7000 Videos (Sequential Processing)

```
Downloads: 7000 × 4 min avg = 28,000 minutes = 467 hours = 19.5 DAYS
Transcription: 7000 × 20 min avg = 140,000 minutes = 2,333 hours (if sequential)
Mining: 7000 × 3.5 min avg = 24,500 minutes = 408 hours (if sequential)
Evaluation: 7000 × 45 sec = 5,250 minutes = 87.5 hours (if sequential)
---
Sequential Total: ~24 DAYS minimum
```

**Critical Finding**: Downloads alone take 19.5 days with cookie-based rate limiting.

---

## The Cookie-Based Download Dilemma

### Why 3-5 Minute Delays?

From `config.py` lines 473-485:
- `sequential_download_delay_min: 180.0` (3 minutes)
- `sequential_download_delay_max: 300.0` (5 minutes)
- Designed to prevent YouTube's anti-bot detection when using cookie auth

### Why Cookies? [[memory:9931912]]

Cookie-based authentication allows:
- Accessing age-restricted content
- Bypassing geographic restrictions
- More reliable downloads for large batches
- Using throwaway accounts for safety

### The Constraint

**You cannot parallelize cookie-based downloads from the same account** without triggering bot detection:
- YouTube detects simultaneous connections from same cookie jar
- Multiple concurrent requests = immediate 429 rate limiting
- Account flagging can lead to permanent blocks

---

## Optimization Strategy: Multi-Track Processing

### Core Principle

**Parallelize everything EXCEPT the cookie-constrained download stage**, and use intelligent queueing to keep downstream processes fully fed.

### Architecture: Conveyor Belt with Smart Buffering

```
DOWNLOAD STAGE (Sequential)          PROCESSING STAGE (Parallel)
═══════════════════════════         ═══════════════════════════

Video 1 ──┐                          ┌──> Transcribe (parallel: 8 workers)
          │ 3-5 min delay            │
Video 2 ──┤                          ├──> Mine (parallel: 6 workers)
          │ 3-5 min delay            │
Video 3 ──┤                          ├──> Evaluate (parallel: 4 workers)
          │ 3-5 min delay            │
Video N ──┘                          └──> Store (parallel: 10 workers)

Downloads feed into buffer queue
Processing workers pull from buffer as they become available
```

### Key Insight: Download Speed vs Processing Speed

**Download Rate**: 1 video per ~4 minutes = 15 videos/hour
**Processing Capacity** (with 8-core M2 Max):
- Transcription: ~3-6 videos/hour (8 parallel workers)
- Mining: ~10-20 videos/hour (segment-level parallelization)
- Evaluation: ~80 videos/hour (4 parallel workers)

**Bottleneck**: Downloads (15/hr) < Transcription (3-6/hr)

**Solution**: Build up a buffer queue at start, then let processing catch up overnight.

---

## Proposed Implementation: Dynamic Multi-Stage Pipeline

### Phase 1: Fast Buffer Build (First 100 Videos)

**Goal**: Build a buffer queue to keep processing workers busy while downloads continue.

```python
# First 100 videos: Download with MINIMAL delays (30-60 sec)
# This builds a 6-hour buffer of work for transcription workers

for video in videos[0:100]:
    download(video)
    delay(30-60 sec)  # Reduced delay for initial buffer build
    
# Result: ~2 hours to download 100 videos
# Processing time: ~16-30 hours for those 100 videos
```

### Phase 2: Steady State (Videos 101-6900)

**Goal**: Match download rate to transcription throughput to maintain optimal queue size.

```python
# Monitor queue sizes and adjust download rate dynamically

target_queue_size = 50  # Keep 50 videos queued for processing
max_queue_size = 100    # Don't exceed 100 to avoid memory pressure

for video in videos[100:6900]:
    # Check current queue size
    queue_size = len(transcription_queue) + len(mining_queue)
    
    if queue_size < target_queue_size:
        # Queue is low - download faster
        delay = random.uniform(60, 120)  # 1-2 min
    elif queue_size > max_queue_size:
        # Queue is full - slow down
        delay = random.uniform(300, 600)  # 5-10 min
    else:
        # Normal rate
        delay = random.uniform(180, 300)  # 3-5 min
    
    download(video)
    time.sleep(delay)
```

### Phase 3: Drain Queue (Last 100 Videos)

**Goal**: Final downloads complete, then wait for all processing to finish.

```python
# Last 100: Normal rate (3-5 min)
for video in videos[6900:7000]:
    download(video)
    delay(180-300 sec)

# Then wait for processing queues to drain
while transcription_queue or mining_queue or evaluation_queue:
    wait(60 sec)
    report_progress()
```

---

## Dynamic Parallelization Strategy

### Worker Pool Sizing (8-core M2 Max Example)

```python
# Detect hardware capacity
cores = 8
ram_gb = 32

# Calculate optimal workers per stage
transcription_workers = min(cores, ram_gb // 4)  # ~4 GB per Whisper instance
                                                  # = 8 workers

mining_workers = cores * 2  # Segment-level parallelization
                            # = 16 parallel segments

evaluation_workers = 4  # Limited to avoid LLM API rate limits

storage_workers = 10  # Fast, I/O bound
```

### Queue Management Rules

```python
class IntelligentBatchCoordinator:
    def __init__(self):
        self.download_queue = []
        self.transcription_queue = []
        self.mining_queue = []
        self.evaluation_queue = []
        
        # Thresholds
        self.target_buffer = 50
        self.max_buffer = 100
        self.min_buffer = 20
        
    def calculate_download_delay(self) -> float:
        """Dynamically adjust download delay based on queue state"""
        total_queued = (
            len(self.transcription_queue) + 
            len(self.mining_queue) + 
            len(self.evaluation_queue)
        )
        
        if total_queued < self.min_buffer:
            # Aggressive download to rebuild buffer
            return random.uniform(30, 60)  # 30-60 sec
        elif total_queued > self.max_buffer:
            # Slow down to let processing catch up
            return random.uniform(300, 600)  # 5-10 min
        else:
            # Normal cookie-safe rate
            return random.uniform(180, 300)  # 3-5 min
    
    def should_download_now(self) -> bool:
        """Determine if it's safe to download next video"""
        total_queued = (
            len(self.transcription_queue) + 
            len(self.mining_queue)
        )
        
        # Never exceed max buffer (memory pressure)
        if total_queued > self.max_buffer:
            return False
        
        # Always download if buffer is low
        if total_queued < self.min_buffer:
            return True
        
        # Normal operation: download at steady rate
        return True
```

---

## Alternative Strategy: Multi-Account Parallelization

### Concept

Use **multiple throwaway YouTube accounts** with separate cookie files to enable parallel downloads.

### Implementation

```python
# Create 5 throwaway YouTube accounts
# Export 5 separate cookie files: cookies_account_1.txt, cookies_account_2.txt, etc.

cookie_files = [
    "cookies_account_1.txt",
    "cookies_account_2.txt", 
    "cookies_account_3.txt",
    "cookies_account_4.txt",
    "cookies_account_5.txt",
]

# Each account can download 1 video per 3-5 minutes
# With 5 accounts: 5 videos per 3-5 minutes = 60-100 videos/hour

async def parallel_download_with_multiple_accounts(urls: list[str]):
    """Download using multiple accounts in parallel"""
    account_queues = {i: [] for i in range(len(cookie_files))}
    
    # Distribute URLs across accounts
    for idx, url in enumerate(urls):
        account_id = idx % len(cookie_files)
        account_queues[account_id].append(url)
    
    # Download each account's queue independently
    tasks = []
    for account_id, cookie_file in enumerate(cookie_files):
        task = download_sequential_with_cookies(
            account_queues[account_id],
            cookie_file,
            delay_range=(180, 300)  # Still 3-5 min per account
        )
        tasks.append(task)
    
    # Run all accounts in parallel
    await asyncio.gather(*tasks)
```

### Time Savings with 5 Accounts

```
Single account: 7000 videos × 4 min = 28,000 min = 467 hours
5 accounts:     7000 / 5 × 4 min = 5,600 min = 93 hours = 3.9 DAYS

Speedup: 5x faster (19.5 days → 3.9 days)
```

### Safety Considerations

- Each account downloads at safe rate (3-5 min between requests)
- Accounts are isolated (separate cookies, separate IPs if using proxies)
- No concurrent requests from same account
- YouTube sees normal usage pattern per account

### Risks

- Requires maintaining 5 throwaway accounts
- Account bans affect 1/5 of throughput (not catastrophic)
- More complex credential management

---

## Recommended Hybrid Strategy for 7000 Videos

### Approach: 3 Accounts + Dynamic Queue Management

**Setup**:
- 3 throwaway YouTube accounts with separate cookies
- Each account: 1 download per 3-5 minutes
- Total download rate: ~3 videos per 4 minutes = 45 videos/hour

**Timeline**:
```
Phase 1 (Hours 0-3): Buffer Build
  - Download first 150 videos (50 per account)
  - Reduced delays: 2-3 min per account
  - Result: 150 videos queued, transcription workers start

Phase 2 (Hours 3-156): Steady State
  - Download remaining 6850 videos at normal rate
  - 6850 / 45 per hour = 152 hours = 6.3 days
  - Transcription/mining/evaluation run in parallel
  - Queue size stabilizes at 30-50 videos

Phase 3 (Hours 156-180): Queue Drain
  - All downloads complete
  - Processing finishes remaining ~30-50 videos
  - Final storage and cleanup
```

**Total Wall Clock Time**: ~7-8 days (vs 24 days sequential)

---

## Implementation Checklist

### 1. Multi-Account Download Manager

```python
class MultiAccountDownloadManager:
    """Manages parallel downloads across multiple YouTube accounts"""
    
    def __init__(self, cookie_files: list[str], min_delay: float, max_delay: float):
        self.accounts = [
            {
                "cookie_file": cf,
                "downloader": YouTubeDownloadProcessor(
                    enable_cookies=True,
                    cookie_file_path=cf
                ),
                "last_download_time": 0,
                "downloads_completed": 0,
            }
            for cf in cookie_files
        ]
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.account_lock = asyncio.Lock()
    
    async def get_available_account(self) -> dict | None:
        """Get an account that's ready to download (delay elapsed)"""
        async with self.account_lock:
            current_time = time.time()
            
            for account in self.accounts:
                time_since_last = current_time - account["last_download_time"]
                required_delay = random.uniform(self.min_delay, self.max_delay)
                
                if time_since_last >= required_delay:
                    return account
            
            return None  # All accounts on cooldown
    
    async def download_with_account_rotation(
        self, urls: list[str], queue_manager
    ) -> list[Path]:
        """Download URLs using account rotation"""
        downloaded_files = []
        
        for url in urls:
            # Wait for an available account
            account = None
            while account is None:
                account = await self.get_available_account()
                if account is None:
                    await asyncio.sleep(10)  # Check every 10 seconds
                
                # Also check if we should pause due to queue pressure
                if not queue_manager.should_download_now():
                    account = None
                    await asyncio.sleep(30)
            
            # Download with this account
            try:
                result = account["downloader"].process(url)
                if result.success:
                    downloaded_files.append(result.output_data)
                    account["downloads_completed"] += 1
                account["last_download_time"] = time.time()
            except Exception as e:
                logger.error(f"Download failed for {url}: {e}")
        
        return downloaded_files
```

### 2. Queue-Aware Download Scheduler

```python
class QueueAwareDownloadScheduler:
    """Adjusts download rate based on processing queue state"""
    
    def __init__(
        self,
        target_buffer: int = 50,
        max_buffer: int = 100,
        min_buffer: int = 20,
    ):
        self.target_buffer = target_buffer
        self.max_buffer = max_buffer
        self.min_buffer = min_buffer
        
        # Queue references
        self.transcription_queue = []
        self.mining_queue = []
        self.evaluation_queue = []
    
    def get_total_queued(self) -> int:
        """Get total items in all processing queues"""
        return (
            len(self.transcription_queue) +
            len(self.mining_queue) +
            len(self.evaluation_queue)
        )
    
    def should_download_now(self) -> bool:
        """Determine if we should download next video"""
        total = self.get_total_queued()
        
        # Never exceed max buffer
        if total >= self.max_buffer:
            logger.info(f"Queue at max ({total}/{self.max_buffer}), pausing downloads")
            return False
        
        return True
    
    def get_download_delay_multiplier(self) -> float:
        """Get multiplier for download delay based on queue pressure"""
        total = self.get_total_queued()
        
        if total < self.min_buffer:
            # Aggressive: 0.5x normal delay (e.g., 90-150 sec instead of 180-300)
            return 0.5
        elif total > self.target_buffer:
            # Conservative: 1.5x normal delay
            return 1.5
        else:
            # Normal rate
            return 1.0
    
    def log_queue_status(self):
        """Log current queue state for monitoring"""
        logger.info(
            f"Queue Status: "
            f"Transcription={len(self.transcription_queue)}, "
            f"Mining={len(self.mining_queue)}, "
            f"Evaluation={len(self.evaluation_queue)}, "
            f"Total={self.get_total_queued()}/{self.target_buffer}"
        )
```

### 3. Integrated Pipeline Coordinator

```python
class MassiveBatchCoordinator:
    """Coordinates 7000+ video processing with optimal throughput"""
    
    def __init__(
        self,
        cookie_files: list[str],
        hardware_specs: dict,
        db_service,
    ):
        # Initialize components
        self.download_manager = MultiAccountDownloadManager(
            cookie_files=cookie_files,
            min_delay=180,  # 3 min
            max_delay=300,  # 5 min
        )
        
        self.queue_scheduler = QueueAwareDownloadScheduler(
            target_buffer=50,
            max_buffer=100,
            min_buffer=20,
        )
        
        self.orchestrator = System2Orchestrator(db_service=db_service)
        
        # Worker pools
        self.transcription_workers = hardware_specs.get("cores", 8)
        self.mining_workers = hardware_specs.get("cores", 8) * 2
        self.evaluation_workers = 4
        
    async def process_massive_batch(
        self,
        urls: list[str],
        progress_callback=None,
    ) -> dict:
        """Process 7000+ videos with optimal parallelization"""
        
        logger.info(f"Starting massive batch processing: {len(urls)} videos")
        logger.info(f"Using {len(self.download_manager.accounts)} accounts")
        
        # Phase 1: Build initial buffer (first 150 videos)
        logger.info("Phase 1: Building initial buffer")
        await self._build_initial_buffer(urls[:150], progress_callback)
        
        # Phase 2: Steady state processing
        logger.info("Phase 2: Steady state processing")
        await self._steady_state_processing(urls[150:], progress_callback)
        
        # Phase 3: Drain queues
        logger.info("Phase 3: Draining processing queues")
        await self._drain_queues(progress_callback)
        
        return {
            "success": True,
            "videos_processed": len(urls),
            "accounts_used": len(self.download_manager.accounts),
        }
    
    async def _build_initial_buffer(self, urls: list[str], progress_callback):
        """Phase 1: Aggressively download first batch to build queue"""
        
        # Temporarily reduce delays for buffer build
        self.download_manager.min_delay = 60   # 1 min
        self.download_manager.max_delay = 120  # 2 min
        
        # Download first batch
        download_task = self.download_manager.download_with_account_rotation(
            urls, self.queue_scheduler
        )
        
        # Start processing workers immediately
        process_task = self._run_processing_workers()
        
        # Wait for downloads to complete
        await download_task
        
        # Restore normal delays
        self.download_manager.min_delay = 180  # 3 min
        self.download_manager.max_delay = 300  # 5 min
        
        logger.info(f"Buffer built: {self.queue_scheduler.get_total_queued()} videos queued")
    
    async def _steady_state_processing(self, urls: list[str], progress_callback):
        """Phase 2: Download at rate that matches processing throughput"""
        
        # Start download and processing tasks in parallel
        download_task = self.download_manager.download_with_account_rotation(
            urls, self.queue_scheduler
        )
        
        process_task = self._run_processing_workers()
        
        # Run both until downloads complete
        await download_task
        
        logger.info("All downloads complete, processing continues...")
    
    async def _drain_queues(self, progress_callback):
        """Phase 3: Wait for all processing to complete"""
        
        while self.queue_scheduler.get_total_queued() > 0:
            self.queue_scheduler.log_queue_status()
            await asyncio.sleep(60)  # Check every minute
        
        logger.info("All queues drained, processing complete!")
    
    async def _run_processing_workers(self):
        """Run transcription/mining/evaluation workers in parallel"""
        
        tasks = [
            self._transcription_worker_pool(),
            self._mining_worker_pool(),
            self._evaluation_worker_pool(),
        ]
        
        await asyncio.gather(*tasks)
    
    async def _transcription_worker_pool(self):
        """Worker pool for parallel transcription"""
        # Implementation uses System2Orchestrator for transcription jobs
        pass
    
    async def _mining_worker_pool(self):
        """Worker pool for parallel mining"""
        # Implementation uses System2Orchestrator for mining jobs
        pass
    
    async def _evaluation_worker_pool(self):
        """Worker pool for parallel evaluation"""
        # Implementation uses System2Orchestrator for evaluation jobs
        pass
```

---

## Expected Performance: 7000 Videos

### Conservative Estimate (3 Accounts, Normal Delays)

| Phase | Duration | Notes |
|-------|----------|-------|
| Phase 1: Buffer Build | 3 hours | Download 150 videos with 1-2 min delays |
| Phase 2: Steady State | 156 hours (6.5 days) | Download 6850 videos at 45/hour |
| Phase 3: Queue Drain | 8-12 hours | Process final ~50 videos in queue |
| **Total** | **~7 days** | vs 24 days sequential |

### Aggressive Estimate (5 Accounts, Dynamic Delays)

| Phase | Duration | Notes |
|-------|----------|-------|
| Phase 1: Buffer Build | 2 hours | Download 200 videos with 1 min delays |
| Phase 2: Steady State | 93 hours (3.9 days) | Download 6800 videos at 75/hour |
| Phase 3: Queue Drain | 6-8 hours | Process final ~40 videos in queue |
| **Total** | **~4.5 days** | vs 24 days sequential |

---

## Monitoring & Safety

### Real-Time Monitoring Dashboard

```python
def get_pipeline_status() -> dict:
    """Get real-time status of massive batch processing"""
    return {
        "downloads": {
            "completed": sum(a["downloads_completed"] for a in accounts),
            "queued": len(download_queue),
            "accounts_active": len([a for a in accounts if is_active(a)]),
        },
        "processing": {
            "transcription_queue": len(transcription_queue),
            "mining_queue": len(mining_queue),
            "evaluation_queue": len(evaluation_queue),
            "total_queued": queue_scheduler.get_total_queued(),
        },
        "workers": {
            "transcription_active": transcription_workers_active,
            "mining_active": mining_workers_active,
            "evaluation_active": evaluation_workers_active,
        },
        "timing": {
            "elapsed_hours": elapsed_time / 3600,
            "estimated_remaining_hours": estimate_remaining(),
            "download_rate_per_hour": calculate_download_rate(),
            "processing_rate_per_hour": calculate_processing_rate(),
        },
    }
```

### Bot Detection Warning Signs

Monitor for these indicators:
- **429 Rate Limit Errors**: YouTube blocking requests
  - Action: Increase delays by 2x for that account
  - Pause account for 1-2 hours
  
- **Repeated Download Failures**: Same video fails 3+ times
  - Action: Mark video as problematic, skip temporarily
  - Retry later with longer delay
  
- **Account Access Denied**: Cookie authentication fails
  - Action: Disable that account, redistribute queue
  - Alert user to check account status

### Adaptive Rate Limiting

```python
class AdaptiveRateLimiter:
    """Adjusts download delays based on YouTube response patterns"""
    
    def __init__(self):
        self.failure_counts = {}
        self.delay_multipliers = {}
    
    def record_download_result(self, account_id: str, success: bool):
        """Track download outcomes to detect rate limiting"""
        if account_id not in self.failure_counts:
            self.failure_counts[account_id] = 0
            self.delay_multipliers[account_id] = 1.0
        
        if success:
            # Success - gradually reduce delay multiplier
            self.failure_counts[account_id] = max(0, self.failure_counts[account_id] - 1)
            self.delay_multipliers[account_id] = max(1.0, self.delay_multipliers[account_id] - 0.1)
        else:
            # Failure - increase delay multiplier
            self.failure_counts[account_id] += 1
            self.delay_multipliers[account_id] *= 1.5
            
            if self.failure_counts[account_id] >= 3:
                logger.warning(
                    f"Account {account_id} has {self.failure_counts[account_id]} failures, "
                    f"delay multiplier now {self.delay_multipliers[account_id]:.2f}x"
                )
    
    def get_delay_for_account(self, account_id: str, base_delay: float) -> float:
        """Get adjusted delay for account based on recent performance"""
        multiplier = self.delay_multipliers.get(account_id, 1.0)
        return base_delay * multiplier
```

---

## Summary & Recommendations

### For 7000 Videos, The Optimal Strategy Is:

1. **Use 3-5 Throwaway YouTube Accounts**
   - Each with separate cookie file
   - Maintains safe 3-5 min delay per account
   - Achieves 3-5x parallelization of downloads

2. **Dynamic Queue Management**
   - Build initial buffer (50-100 videos)
   - Monitor queue sizes in real-time
   - Adjust download rate to match processing throughput

3. **Full Parallelization of Processing Stages**
   - Transcription: 8 parallel workers (hardware-limited)
   - Mining: 16 parallel segments (already optimized)
   - Evaluation: 4 parallel workers (API rate-limit aware)

4. **Adaptive Rate Limiting**
   - Monitor for bot detection signals
   - Auto-adjust delays based on success/failure rates
   - Pause accounts that hit rate limits

### Expected Results:

- **Wall Clock Time**: 4-7 days (vs 24 days sequential)
- **Speedup**: 3-5x faster
- **Safety**: Each account maintains safe download patterns
- **Robustness**: Account failures don't halt entire pipeline

### Key Configuration Parameters:

```yaml
massive_batch_config:
  # Account setup
  cookie_files:
    - "cookies_account_1.txt"
    - "cookies_account_2.txt"
    - "cookies_account_3.txt"
  
  # Queue management
  target_buffer_size: 50
  max_buffer_size: 100
  min_buffer_size: 20
  
  # Download delays (per account)
  min_delay_seconds: 180  # 3 min
  max_delay_seconds: 300  # 5 min
  
  # Phase 1: Buffer build
  buffer_build_videos: 150
  buffer_build_min_delay: 60   # 1 min
  buffer_build_max_delay: 120  # 2 min
  
  # Worker pools
  transcription_workers: 8
  mining_workers: 16
  evaluation_workers: 4
  
  # Safety
  adaptive_rate_limiting: true
  max_failures_before_pause: 3
  failure_delay_multiplier: 1.5
```

---

## Next Steps

1. **Create throwaway YouTube accounts** (3-5 accounts recommended)
2. **Export cookies** from each account (use browser extension)
3. **Implement `MultiAccountDownloadManager`** (extend existing `YouTubeDownloadProcessor`)
4. **Implement `QueueAwareDownloadScheduler`** (extend `IntelligentProcessingCoordinator`)
5. **Integrate with `System2Orchestrator`** for job tracking
6. **Add monitoring dashboard** for real-time status
7. **Test with 100-video batch** to validate timings
8. **Scale to full 7000-video batch**

---

**End of Analysis**
