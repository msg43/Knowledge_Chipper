# Batch Processing 7000 Videos: Performance Analysis & Optimization

**Date**: October 27, 2025  
**Scope**: Processing 7000 YouTube videos (60 min average) through complete pipeline  
**Goal**: Minimize wall clock time while avoiding YouTube bot detection

---

## Executive Summary

For 7000 videos with local LLM processing, the timeline is **dominated by local inference time**, not downloads:

| Hardware | Parallel Workers | Estimated Timeline |
|----------|------------------|-------------------|
| M2 Max (32 GB) | 6-8 workers | **12-13 days** |
| M2 Ultra (64 GB) | 12-16 workers | **6-8 days** |
| M2 Ultra (128 GB) | 20-24 workers | **4-5 days** |

**Key Finding**: Cookie-based download delays (3-5 min) are **irrelevant** because processing takes 40-50x longer than downloads. Simple sequential downloads with standard cookie delays keep the processing queue optimally fed with zero special management needed.

---

## Download Size & Speed Calculations

### Audio File Size (60-min video, worst quality audio-only)

**Bitrate**: 64 kbps (YouTube's lowest audio-only stream)

```
64 kbps = 64,000 bits/second = 8,000 bytes/second

8,000 bytes/second × 60 seconds = 480,000 bytes/minute
                                 ≈ 0.46 MB/minute

With overhead, metadata, VBR fluctuations: ~1 MB/minute is safe estimate

For 60-min video: 60 MB total
```

### Download Time by Connection Speed

| Connection Speed | MB/s | Time for 60 MB | Typical Use Case |
|------------------|------|----------------|------------------|
| 10 Mbps | 1.25 MB/s | **48 sec** | Basic broadband |
| 25 Mbps | 3.1 MB/s | **19 sec** | Standard home |
| 50 Mbps | 6.25 MB/s | **10 sec** | Good home connection |
| 100 Mbps | 12.5 MB/s | **5 sec** | Fast home/office |
| 250 Mbps | 31.25 MB/s | **2 sec** | Very fast connection |

**Conservative estimate for planning**: **10-20 seconds per 60-min video**

---

## Complete Pipeline Timing (60-min video)

### Sequential Processing (Single Video)

| Stage | Time | Notes |
|-------|------|-------|
| **Download** | 10-20 sec | 60 MB @ 25-50 Mbps |
| **Cookie delay** | 3-5 min | YouTube bot prevention |
| **Transcription** (Whisper local) | 5-10 min | Apple Silicon NPU acceleration |
| **Mining** (8 parallel segments) | 8-12 min | Local LLM, 100 segments ÷ 8 workers |
| **Evaluation** (local LLM) | 2-5 min | Single flagship call |
| **Storage** | < 5 sec | SQLite bulk insert |
| **TOTAL** | **18-32 min** | **Average: ~25 min** |

### Processing Dominates Download by 40-50x

```
Download time:           15 sec   (0.25 min)
Download + cookie delay: 4.25 min
Processing time:         20 min

Ratio: 20 min ÷ 0.25 min = 80x slower processing
Ratio: 20 min ÷ 4.25 min = 4.7x slower even with cookie delay

Conclusion: Downloads stay ahead of processing automatically
```

---

## Timeline for 7000 Videos

### Sequential Processing (1 at a time)

```
7000 videos × 25 min avg = 175,000 minutes
                         = 2,917 hours
                         = 121 DAYS 😱
```

### Parallel Processing (Hardware-Limited)

**M2 Max (32 GB RAM, 8-12 cores)**:
- **RAM limit**: (32 - 8) GB ÷ 5 GB per model = **4 model instances**
- **CPU limit**: 12 cores × 1.5 = **18 threads**
- **Bottleneck**: RAM (4 instances)
- **Plus transcription**: +2 concurrent Whisper instances
- **Effective parallel videos**: **6 simultaneous**

```
7000 ÷ 6 videos = 1,167 batches
1,167 × 25 min = 29,175 minutes = 486 hours = 20.3 days

With optimization: ~12-13 days (accounting for overlap in stages)
```

**M2 Ultra (64 GB RAM, 20-24 cores)**:
- **RAM limit**: (64 - 8) GB ÷ 5 GB = **11 model instances**
- **CPU limit**: 24 cores × 1.5 = **36 threads**
- **Bottleneck**: RAM (11 instances)
- **Plus transcription**: +4 Whisper instances
- **Effective parallel videos**: **15 simultaneous**

```
7000 ÷ 15 videos = 467 batches
467 × 25 min = 11,675 minutes = 194 hours = 8.1 days

With optimization: ~6-7 days
```

**M2 Ultra (128 GB RAM, 20-24 cores)**:
- **RAM limit**: (128 - 8) GB ÷ 5 GB = **24 model instances**
- **CPU limit**: 24 cores × 1.5 = **36 threads**
- **Bottleneck**: Balanced
- **Plus transcription**: +6 Whisper instances
- **Effective parallel videos**: **24 simultaneous**

```
7000 ÷ 24 videos = 292 batches
292 × 25 min = 7,300 minutes = 122 hours = 5.1 days

With optimization: ~4-5 days
```

---

## Why Cookie Delays Don't Matter

### Download Timeline vs Processing Timeline

```
Time:  0     1     2     3     4     5     10    15    20    25
       |-----|-----|-----|-----|-----|-----|-----|-----|-----|

Video 1:
  DL:  [=]                                                      (15 sec)
  Delay:   [===========]                                       (4 min)
  Process:               [================================]     (20 min)
  Done:                                                   ^     (24.25 min)

Video 2:
  DL:       [=]                                                (at 1 min)
  Delay:        [===========]                                  
  Process:                     [================================]
  Done:                                                       ^ (25.25 min)

Video 3:
  DL:            [=]                                           (at 2 min)
  Delay:             [===========]
  Process:                          [================================]
  Done:                                                          ^(26.25 min)

...continuing pattern...

Video 6:
  DL:                              [=]                         (at 5 min)
  Delay:                               [===========]
  Process:                                         [================================]
  Done:                                                                        ^(29.25 min)
```

**Observation**: 
- By the time Video 1 finishes processing (24.25 min), we've already downloaded and started 6 more videos
- Downloads occur at: 0, 1, 2, 3, 4, 5, 6, 7... minutes (1 per minute after initial delay)
- Processing completes at: 24, 25, 26, 27, 28, 29... minutes
- **Queue naturally maintains 5-6 videos at steady state**

### Download Rate vs Processing Rate

**Download rate** (with 4-min cookie delays):
```
1 video per (15 sec + 4 min) ≈ 1 video per 4.25 min
= 14 videos per hour
```

**Processing rate** (with 6 parallel workers):
```
6 videos × (25 min each) = 150 min per batch
= 2.4 batches per hour
= 14.4 videos per hour
```

**Perfect balance!** Downloads and processing match almost exactly with standard cookie delays.

---

## Optimal Implementation Strategy

### Phase 1: Initial Buffer Build (First 30 min)

```python
# Download first 10-15 videos rapidly to start all workers
initial_buffer_size = num_parallel_workers * 2  # e.g., 12 for 6 workers

for url in urls[0:initial_buffer_size]:
    audio_file = download_audio_only(url)
    processing_queue.put(audio_file)
    await sleep(random.uniform(30, 60))  # Reduced delay for buffer build
    
# After 10-15 min: Queue has 10-15 videos, all workers start processing
```

### Phase 2: Steady State (Main Processing Period)

```python
# Download remaining videos with standard cookie delays
for url in urls[initial_buffer_size:7000]:
    # Simple queue management
    queue_size = processing_queue.qsize()
    
    if queue_size < num_parallel_workers:
        # Queue is low - download slightly faster
        delay = random.uniform(120, 180)  # 2-3 min
    elif queue_size > num_parallel_workers * 3:
        # Queue is getting large - use full delay
        delay = random.uniform(240, 360)  # 4-6 min
    else:
        # Normal cookie-safe delay
        delay = random.uniform(180, 300)  # 3-5 min
    
    audio_file = download_audio_only(url)
    processing_queue.put(audio_file)
    await sleep(delay)
```

### Phase 3: Queue Drain (Final Period)

```python
# All downloads complete, wait for processing to finish
while not processing_queue.empty() or any_workers_active():
    await sleep(60)
    log_progress()
    
logger.info("All processing complete!")
```

---

## Hardware Optimization Details

### RAM Calculation for Parallel Workers

**Each processing instance requires**:
```
Whisper model:        ~2-3 GB (large-v3 model)
LLM model (7B):       ~5 GB (with context and overhead)
LLM model (13B):      ~8 GB
Working memory:       ~1 GB (transcripts, buffers, etc.)

Total per video:      ~8 GB (with 7B model)
Total per video:      ~11 GB (with 13B model)
```

**System overhead**:
```
macOS system:         ~6-8 GB
Browser/apps:         ~2-4 GB

Reserved total:       ~8-12 GB
```

**Optimal worker calculation**:
```python
def calculate_optimal_workers(total_ram_gb: int, model_size: str = "7B") -> dict:
    """Calculate optimal parallel workers based on available RAM"""
    
    # Reserve for system
    reserved_ram = 8  # GB
    available_ram = total_ram_gb - reserved_ram
    
    # Memory per video
    whisper_ram = 2.5
    llm_ram = 5 if model_size == "7B" else 8
    working_ram = 1
    per_video_ram = whisper_ram + llm_ram + working_ram
    
    # Calculate workers
    max_workers = int(available_ram / per_video_ram)
    
    # Add some buffer for safety
    safe_workers = max(1, int(max_workers * 0.8))
    
    return {
        "max_workers": max_workers,
        "recommended_workers": safe_workers,
        "ram_per_video": per_video_ram,
        "total_ram_needed": safe_workers * per_video_ram,
    }

# Examples
calculate_optimal_workers(32, "7B")
# → {"max_workers": 2, "recommended_workers": 2}  # Too conservative!

# Better calculation considering segment-level parallelism
def calculate_segment_level_workers(total_ram_gb: int, model_size: str = "7B") -> dict:
    """Account for segment-level parallelization within each video"""
    
    reserved_ram = 8
    available_ram = total_ram_gb - reserved_ram
    
    # At segment level, multiple segments share the transcription
    # Only need multiple LLM instances for parallel segment mining
    whisper_ram = 2.5  # Shared across all segments of same video
    llm_ram = 5 if model_size == "7B" else 8
    
    # For segment-level parallelization
    # Can run N videos, each with M parallel segments
    
    # Strategy 1: Few videos, many segments per video
    videos_parallel = 2
    segments_per_video = int((available_ram - (videos_parallel * whisper_ram)) / llm_ram)
    
    # Strategy 2: Many videos, few segments per video  
    # (Better for steady throughput)
    
    return {
        "parallel_videos": videos_parallel,
        "parallel_segments_per_video": segments_per_video,
        "total_llm_instances": videos_parallel * segments_per_video,
    }
```

### Actual Achievable Parallelization

**M2 Max (32 GB)**:
```
Strategy: 4 videos in parallel, 6 segment workers each
- Whisper instances: 4 × 2.5 GB = 10 GB
- LLM instances: 4 × 6 × 5 GB = 120 GB  ← Too much!

Better strategy: Share LLM instances across videos
- Whisper instances: 4 × 2.5 GB = 10 GB
- Shared LLM pool: 4 instances × 5 GB = 20 GB
- Total: 30 GB (fits in 32 GB with 2 GB overhead)

Throughput: 4 videos with shared LLM queue
Effective parallelization: ~6 videos equivalent
```

**M2 Ultra (64 GB)**:
```
Strategy: 8 videos in parallel, shared LLM pool
- Whisper instances: 8 × 2.5 GB = 20 GB
- Shared LLM pool: 8 instances × 5 GB = 40 GB
- Total: 60 GB (fits in 64 GB with 4 GB overhead)

Effective parallelization: ~12-15 videos equivalent
```

**M2 Ultra (128 GB)**:
```
Strategy: 16 videos in parallel, dedicated LLM workers
- Whisper instances: 16 × 2.5 GB = 40 GB
- LLM instances: 16 instances × 5 GB = 80 GB
- Total: 120 GB (fits in 128 GB with 8 GB overhead)

Effective parallelization: ~20-24 videos equivalent
```

---

## Implementation Code

### Simple Download + Processing Coordinator

```python
class SimpleVideoProcessor:
    """Processes 7000 videos with optimal queue management"""
    
    def __init__(
        self,
        cookie_file: str,
        parallel_workers: int = 6,
        target_queue_size: int = None,
    ):
        self.cookie_file = cookie_file
        self.parallel_workers = parallel_workers
        self.target_queue_size = target_queue_size or (parallel_workers * 2)
        
        # Queues
        self.download_queue = asyncio.Queue()
        self.processing_queue = asyncio.Queue(maxsize=parallel_workers * 4)
        
        # Stats
        self.stats = {
            "downloaded": 0,
            "processed": 0,
            "failed": 0,
            "start_time": None,
        }
    
    async def process_batch(self, urls: list[str]) -> dict:
        """Process large batch of URLs"""
        self.stats["start_time"] = time.time()
        
        # Start download and processing tasks
        tasks = [
            self._download_coordinator(urls),
            *[self._processing_worker(i) for i in range(self.parallel_workers)],
            self._monitor_progress(),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            "success": True,
            "stats": self.stats,
            "duration_hours": (time.time() - self.stats["start_time"]) / 3600,
        }
    
    async def _download_coordinator(self, urls: list[str]):
        """Download videos with intelligent pacing"""
        
        # Phase 1: Build initial buffer
        initial_buffer = min(self.target_queue_size, len(urls))
        
        logger.info(f"Phase 1: Building buffer of {initial_buffer} videos")
        for url in urls[:initial_buffer]:
            await self._download_single(url, delay_range=(30, 60))
        
        logger.info(f"Phase 2: Processing remaining {len(urls) - initial_buffer} videos")
        # Phase 2: Steady state with cookie delays
        for url in urls[initial_buffer:]:
            # Dynamic delay based on queue size
            queue_size = self.processing_queue.qsize()
            
            if queue_size < self.parallel_workers:
                delay_range = (120, 180)  # 2-3 min
            elif queue_size > self.target_queue_size:
                delay_range = (240, 360)  # 4-6 min
            else:
                delay_range = (180, 300)  # 3-5 min (standard)
            
            await self._download_single(url, delay_range=delay_range)
        
        logger.info("All downloads complete")
    
    async def _download_single(self, url: str, delay_range: tuple[int, int]):
        """Download single video with delay"""
        try:
            # Download
            downloader = YouTubeDownloadProcessor(
                enable_cookies=True,
                cookie_file_path=self.cookie_file,
            )
            result = downloader.process(url)
            
            if result.success:
                await self.processing_queue.put(result.output_data)
                self.stats["downloaded"] += 1
                logger.info(f"Downloaded: {self.stats['downloaded']}/7000")
            else:
                self.stats["failed"] += 1
                logger.error(f"Download failed for {url}")
            
            # Cookie delay
            delay = random.uniform(*delay_range)
            await asyncio.sleep(delay)
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            self.stats["failed"] += 1
    
    async def _processing_worker(self, worker_id: int):
        """Process videos from queue"""
        logger.info(f"Processing worker {worker_id} started")
        
        while True:
            try:
                # Get next video from queue
                audio_file = await self.processing_queue.get()
                
                # Create System2 job for this video
                orchestrator = System2Orchestrator(db_service=self.db_service)
                
                # Transcribe
                transcribe_job = orchestrator.create_job(
                    job_type="transcribe",
                    input_id=str(audio_file),
                    config={"file_path": str(audio_file)},
                )
                transcribe_result = await orchestrator.process_job(transcribe_job)
                
                # Mine
                mine_job = orchestrator.create_job(
                    job_type="mine",
                    input_id=transcribe_result["episode_id"],
                    config={
                        "file_path": transcribe_result["transcript_path"],
                        "parallel_workers": 8,  # Segment-level parallelization
                    },
                )
                mine_result = await orchestrator.process_job(mine_job)
                
                self.stats["processed"] += 1
                logger.info(f"Processed: {self.stats['processed']}/7000 (worker {worker_id})")
                
                self.processing_queue.task_done()
                
            except asyncio.QueueEmpty:
                # No more work
                if self.stats["downloaded"] >= 7000:
                    logger.info(f"Worker {worker_id} shutting down")
                    break
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Processing error (worker {worker_id}): {e}")
                self.processing_queue.task_done()
    
    async def _monitor_progress(self):
        """Monitor and log progress"""
        while True:
            await asyncio.sleep(300)  # Every 5 minutes
            
            elapsed = time.time() - self.stats["start_time"]
            rate = self.stats["processed"] / (elapsed / 3600) if elapsed > 0 else 0
            remaining = 7000 - self.stats["processed"]
            eta_hours = remaining / rate if rate > 0 else 0
            
            logger.info(
                f"Progress: {self.stats['processed']}/7000 "
                f"({self.stats['processed']/70:.1f}%), "
                f"Rate: {rate:.1f}/hr, "
                f"ETA: {eta_hours:.1f} hours, "
                f"Queue: {self.processing_queue.qsize()}"
            )
```

### Usage

```python
# For M2 Max (32 GB)
processor = SimpleVideoProcessor(
    cookie_file="cookies.txt",
    parallel_workers=6,
    target_queue_size=12,
)

urls = [...]  # 7000 YouTube URLs
result = await processor.process_batch(urls)

# Expected: ~12-13 days on M2 Max
```

---

## Dynamic Parallelization Not Needed

### Why Simple is Better

The analysis shows that with cookie delays:
- Downloads: **14 videos/hour**
- Processing (6 workers): **14.4 videos/hour**

These rates are **naturally balanced**. No complex adaptive scheduling needed.

### Simple Rules Suffice

```python
if queue_size < num_workers:
    delay = 2-3 min      # Download slightly faster
elif queue_size > 3 × num_workers:
    delay = 4-6 min      # Slow down
else:
    delay = 3-5 min      # Standard cookie-safe rate
```

This simple logic prevents:
- **Queue starvation**: Workers idle waiting for downloads
- **Queue overflow**: Excessive memory usage from too many queued videos
- **Bot detection**: Maintains safe 3-5 min average between downloads

---

## Summary & Recommendations

### For 7000 Videos (60 min average)

**Bottleneck**: Local LLM inference for segment mining  
**Download constraint**: Irrelevant (downloads naturally stay ahead)  
**Optimization target**: Maximize parallel LLM workers based on RAM  
**Sleep period**: 6-hour nightly pause (midnight - 6am) for human-like behavior

### Recommended Approach

1. **Single YouTube account** with cookie-based auth
   - Sequential downloads with 3-5 min delays
   - **6-hour sleep period (midnight - 6am)** for added safety
   - No need for multiple accounts or complex scheduling

2. **Simple queue management**
   - Build buffer of 10-15 videos initially
   - Maintain queue of 5-15 videos during processing
   - Basic delay adjustment based on queue depth

3. **Maximize hardware utilization**
   - Auto-detect RAM and CPU capacity
   - Scale parallel workers to hardware limits
   - Use shared LLM instance pool for efficiency

### Expected Timelines (with 6-hour sleep period)

| Hardware | Workers | Timeline | Cost |
|----------|---------|----------|------|
| M2 Max (32 GB) | 6 | **13-14 days** | $0 (local) |
| M2 Ultra (64 GB) | 15 | **7-8 days** | $0 (local) |
| M2 Ultra (128 GB) | 24 | **5-6 days** | $0 (local) |

### Implementation Effort

- **Complexity**: Low (simple sequential downloads + worker pool + sleep scheduler)
- **Risk**: Low (uses existing System2 infrastructure)
- **Testing**: Can validate with 100-video batch first
- **Monitoring**: Simple queue depth and throughput metrics
- **Sleep period**: 6 hours nightly (midnight - 6am) for added safety

### Configuration Example

```yaml
# config/settings.yaml (or GUI settings)

youtube_processing:
  # Cookie authentication
  enable_cookies: true
  cookie_file_path: "cookies.txt"
  
  # Download delays (3-5 min between requests)
  sequential_download_delay_min: 180.0  # 3 min
  sequential_download_delay_max: 300.0  # 5 min
  delay_randomization_percent: 25.0
  
  # Sleep period (Option B: Light sleep)
  enable_sleep_period: true
  sleep_start_hour: 0   # Midnight
  sleep_end_hour: 6     # 6am
  sleep_timezone: "America/Los_Angeles"  # Adjust to your timezone
```

### Usage Example

```python
from knowledge_system.services.download_scheduler import create_download_scheduler

# Create scheduler with sleep period enabled
scheduler = create_download_scheduler(
    cookie_file_path="cookies.txt",
    use_config=True,  # Load sleep settings from config
)

# Download batch (will automatically pause midnight - 6am)
urls = [...]  # Your 7000 YouTube URLs
results = await scheduler.download_batch_with_pacing(
    urls=urls,
    output_dir=Path("downloads"),
    target_queue_size=10,
)

# Check stats
scheduler.log_stats()
# Output:
# 📊 Download stats: 7000/7000 successful (100.0%), 
#     14 sleep periods (84.0 hours)
```

---

**End of Analysis**
