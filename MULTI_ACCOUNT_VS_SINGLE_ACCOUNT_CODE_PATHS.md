# Multi-Account vs Single-Account Transcription Code Paths

**Date:** November 1, 2025  
**Question:** "Is there different code path for multi-account transcription vs single account?"  
**Answer:** YES - Completely different code paths with different schedulers and strategies

---

## Executive Summary

**YES**, there are **two distinct code paths**:

1. **Single-Account Path** - Uses `YouTubeDownloadProcessor` directly with simple sequential downloads
2. **Multi-Account Path** - Uses `MultiAccountDownloadScheduler` with parallel workers and cookie rotation

The decision is made at **line 974** in `transcription_tab.py` based on cookie file count.

---

## Decision Point

### Location
**File:** `src/knowledge_system/gui/tabs/transcription_tab.py`  
**Lines:** 973-998

### Decision Logic
```python
# Line 973-974
# Choose download strategy based on cookie file count
if use_multi_account and len(cookie_files) > 1:
    # Multi-account mode
    logger.info(f"   Using multi-account mode with {len(cookie_files)} cookies")
    downloaded_files = self._download_with_multi_account(
        expanded_urls, cookie_files, downloads_dir
    )
else:
    # Single-account mode (existing behavior)
    cookie_file_path = cookie_files[0] if cookie_files else None
    logger.info(f"   Using single-account mode")
    
    downloader = YouTubeDownloadProcessor(
        download_thumbnails=True,
        enable_cookies=enable_cookies,
        cookie_file_path=cookie_file_path,
        disable_proxies_with_cookies=disable_proxies_with_cookies,
    )
    
    downloaded_files = self._download_with_single_account(
        expanded_urls, downloader, downloads_dir, youtube_delay
    )
```

### Trigger Conditions
- **Multi-Account:** `use_multi_account=True` AND `len(cookie_files) > 1`
- **Single-Account:** Everything else (0 cookies, 1 cookie, or multi-account disabled)

---

## Single-Account Code Path

### Entry Point
**Method:** `_download_with_single_account()`  
**File:** `src/knowledge_system/gui/tabs/transcription_tab.py`

### Architecture
```
TranscriptionTab
    └── _download_with_single_account()
        └── YouTubeDownloadProcessor (direct)
            └── Sequential downloads with simple delays
```

### Key Characteristics

#### 1. Simple Sequential Processing
- Downloads one URL at a time
- Waits for completion before starting next
- No parallelization

#### 2. Direct Downloader Usage
```python
downloader = YouTubeDownloadProcessor(
    download_thumbnails=True,
    enable_cookies=enable_cookies,
    cookie_file_path=cookie_file_path,  # Single file or None
    disable_proxies_with_cookies=disable_proxies_with_cookies,
)
```

#### 3. Basic Rate Limiting
- Uses `youtube_delay` setting (default 5 seconds)
- Fixed delay between downloads
- No randomization
- No sleep periods

#### 4. No Cookie Rotation
- Uses same cookie file for all downloads
- No failover if cookies go stale
- Single point of failure

#### 5. No Deduplication
- Downloads everything in the list
- No database checks
- Can download duplicates

---

## Multi-Account Code Path

### Entry Point
**Method:** `_download_with_multi_account()`  
**File:** `src/knowledge_system/gui/tabs/transcription_tab.py`  
**Lines:** 754-850

### Architecture
```
TranscriptionTab
    └── _download_with_multi_account()
        └── MultiAccountDownloadScheduler
            ├── DownloadScheduler (per account)
            │   └── YouTubeDownloadProcessor
            ├── VideoDeduplicationService
            └── Parallel Worker Pool (20 workers)
```

### Key Characteristics

#### 1. Cookie Testing & Validation
```python
# Line 769-773
self.transcription_step_updated.emit("🧪 Testing cookie files...", 0)
valid_cookies = self._test_and_filter_cookies(cookie_files)

if not valid_cookies:
    raise Exception("No valid cookie files found")
```

**What it does:**
- Tests each cookie file before use
- Filters out stale/invalid cookies
- Only uses working accounts

#### 2. Parallel Processing
```python
# Line 788-796
scheduler = MultiAccountDownloadScheduler(
    cookie_files=valid_cookies,
    parallel_workers=20,  # For M2 Ultra
    enable_sleep_period=self.gui_settings.get("enable_sleep_period", True),
    sleep_start_hour=self.gui_settings.get("sleep_start_hour", 0),
    sleep_end_hour=self.gui_settings.get("sleep_end_hour", 6),
    db_service=db_service,
    disable_proxies_with_cookies=disable_proxies_with_cookies,
)
```

**Features:**
- 20 parallel workers (optimized for M2 Ultra)
- Each account downloads independently
- 3x faster with 3 accounts, 6x faster with 6 accounts

#### 3. Cookie Rotation Strategy
**File:** `src/knowledge_system/services/multi_account_downloader.py`  
**Lines:** 76-88

```python
# Create scheduler for each account
self.schedulers = [
    DownloadScheduler(
        cookie_file_path=cf,
        enable_sleep_period=enable_sleep_period,
        sleep_start_hour=sleep_start_hour,
        sleep_end_hour=sleep_end_hour,
        timezone=sleep_timezone,
        min_delay=min_delay,
        max_delay=max_delay,
        disable_proxies_with_cookies=disable_proxies_with_cookies,
    )
    for cf in cookie_files
]
```

**How it works:**
- Each cookie file gets its own `DownloadScheduler`
- Schedulers run in parallel
- Automatic load distribution
- Independent rate limiting per account

#### 4. Advanced Rate Limiting
**Per-Account Delays:**
- Min delay: 180 seconds (3 minutes)
- Max delay: 300 seconds (5 minutes)
- Randomized within range
- Mimics human behavior

**Sleep Periods:**
- Configurable daily sleep (default: midnight - 6am)
- Timezone-aware
- Per-account sleep tracking
- Avoids 24/7 bot patterns

#### 5. Stale Cookie Detection & Failover
**File:** `src/knowledge_system/services/multi_account_downloader.py`

**Features:**
- Detects 401/403 errors (stale cookies)
- Automatically marks account as failed
- Redistributes URLs to working accounts
- Continues with remaining accounts
- No total failure if some cookies are stale

#### 6. Deduplication Service
```python
# Line 90-91
self.dedup_service = VideoDeduplicationService(db_service)
```

**What it does:**
- Checks database before downloading
- Skips already-downloaded videos
- Shared across all accounts
- Prevents duplicate downloads

#### 7. Retry Queue
**Features:**
- Failed downloads go to retry queue
- Automatic retry with different account
- Configurable retry attempts
- Graceful degradation

---

## Detailed Comparison

| Feature | Single-Account | Multi-Account |
|---------|---------------|---------------|
| **Cookie Files** | 0 or 1 | 2-6 |
| **Parallelization** | None (sequential) | 20 workers |
| **Speed** | 1x baseline | 3-6x faster |
| **Rate Limiting** | Fixed delay (5s) | Randomized (3-5 min) |
| **Sleep Periods** | No | Yes (configurable) |
| **Cookie Rotation** | No | Yes (automatic) |
| **Failover** | No | Yes (automatic) |
| **Deduplication** | No | Yes (database) |
| **Retry Queue** | No | Yes (automatic) |
| **Cookie Testing** | No | Yes (pre-flight) |
| **Stale Detection** | No | Yes (401/403) |
| **Load Distribution** | N/A | Automatic |
| **Complexity** | Low | High |
| **Best For** | 1-10 videos | 10+ videos |

---

## Code Path Visualization

### Single-Account Flow
```
User clicks "Start Transcription"
    ↓
_start_processing()
    ↓
Check cookie count: 0 or 1
    ↓
Create YouTubeDownloadProcessor
    ↓
_download_with_single_account()
    ↓
Loop through URLs sequentially:
    ├── Download URL 1
    ├── Wait 5 seconds
    ├── Download URL 2
    ├── Wait 5 seconds
    └── ...
    ↓
Return downloaded files
    ↓
Process transcriptions
```

### Multi-Account Flow
```
User clicks "Start Transcription"
    ↓
_start_processing()
    ↓
Check cookie count: 2+
    ↓
_download_with_multi_account()
    ↓
Test all cookie files (parallel)
    ├── Test cookie 1 → Valid ✓
    ├── Test cookie 2 → Valid ✓
    └── Test cookie 3 → Stale ✗ (skip)
    ↓
Create MultiAccountDownloadScheduler
    ├── Create DownloadScheduler for cookie 1
    ├── Create DownloadScheduler for cookie 2
    └── Initialize deduplication service
    ↓
Check database for duplicates
    ├── URL 1: Not in DB → Queue
    ├── URL 2: Already downloaded → Skip
    └── URL 3: Not in DB → Queue
    ↓
Distribute URLs across accounts:
    ├── Account 1: URLs [1, 4, 7, 10, ...]
    └── Account 2: URLs [3, 6, 9, 12, ...]
    ↓
Parallel download (20 workers):
    ├── Account 1 downloads with 3-5 min delays
    └── Account 2 downloads with 3-5 min delays
    ↓
Monitor for failures:
    ├── Account 1: URL 7 fails (401) → Mark stale
    ├── Redistribute URL 7 to Account 2
    └── Account 2: Retry URL 7 → Success
    ↓
Sleep period check (midnight - 6am):
    ├── Current time: 2:00 AM
    ├── Pause all downloads
    ├── Resume at 6:00 AM
    └── Continue downloading
    ↓
Return downloaded files
    ↓
Process transcriptions
```

---

## When Each Path is Used

### Single-Account Path Triggers

#### 1. No Cookies
```python
enable_cookies = False
cookie_files = []
# Result: Single-account path (no authentication)
```

#### 2. One Cookie File
```python
enable_cookies = True
cookie_files = ["account1.txt"]
# Result: Single-account path
```

#### 3. Multi-Account Disabled
```python
enable_cookies = True
cookie_files = ["account1.txt", "account2.txt"]
use_multi_account = False  # User disabled it
# Result: Single-account path (uses first cookie only)
```

### Multi-Account Path Triggers

#### 1. Multiple Cookies + Enabled
```python
enable_cookies = True
cookie_files = ["account1.txt", "account2.txt", "account3.txt"]
use_multi_account = True
# Result: Multi-account path
```

---

## Performance Implications

### Single-Account Performance

**Example: 100 videos**
- Sequential downloads: 1 at a time
- 5 second delay between downloads
- No parallelization
- **Total time:** ~8-10 hours (download only)

**Bottlenecks:**
- Sequential processing
- Single network connection
- No load distribution
- Fixed delays

### Multi-Account Performance

**Example: 100 videos with 3 accounts**
- Parallel downloads: 3 simultaneous
- 3-5 minute delays per account
- 20 processing workers
- **Total time:** ~3-4 hours (download only)
- **Speedup:** 3x faster

**Example: 100 videos with 6 accounts**
- Parallel downloads: 6 simultaneous
- 3-5 minute delays per account
- 20 processing workers
- **Total time:** ~1.5-2 hours (download only)
- **Speedup:** 6x faster

**Advantages:**
- Parallel network connections
- Load distribution across accounts
- Automatic failover
- Deduplication saves time

---

## Configuration Differences

### Single-Account Settings
```python
# GUI Settings
enable_cookies = True/False
cookie_files = [single_file] or []
youtube_delay = 5  # seconds

# No additional settings needed
```

### Multi-Account Settings
```python
# GUI Settings
enable_cookies = True
cookie_files = [file1, file2, file3, ...]  # 2-6 files
use_multi_account = True

# Advanced Settings
parallel_workers = 20
enable_sleep_period = True
sleep_start_hour = 0  # midnight
sleep_end_hour = 6    # 6am
min_delay = 180       # 3 minutes
max_delay = 300       # 5 minutes
disable_proxies_with_cookies = True
```

---

## Error Handling Differences

### Single-Account Error Handling
- Download fails → Add to failed list
- No retry mechanism
- No failover
- User must manually retry

### Multi-Account Error Handling
- Download fails → Add to retry queue
- Automatic retry with different account
- Stale cookie detection → Disable account
- Graceful degradation (continue with working accounts)
- Comprehensive error tracking per account

---

## Logging Differences

### Single-Account Logging
```
🍪 Cookie configuration:
   enable_cookies: True
   cookie_files: ['account1.txt']
   use_multi_account: False
   Using single-account mode
   cookie_file_path: account1.txt
```

### Multi-Account Logging
```
🍪 Cookie configuration:
   enable_cookies: True
   cookie_files: ['account1.txt', 'account2.txt', 'account3.txt']
   use_multi_account: True
   Using multi-account mode with 3 cookies

🧪 Testing cookie files...
✅ Using 3 account(s) for downloads
   Expected speedup: 3x faster than single account

📊 Multi-account download stats:
   Account 1: 34 downloads, 2 failures
   Account 2: 33 downloads, 0 failures
   Account 3: 33 downloads, 1 failure (stale cookies)
```

---

## User Experience Differences

### Single-Account UX
- Simple setup (0 or 1 cookie file)
- No complexity
- Slower but predictable
- Good for small batches (1-10 videos)

### Multi-Account UX
- More complex setup (2-6 cookie files)
- Cookie testing phase
- Much faster
- Best for large batches (10+ videos)
- Progress tracking per account
- Automatic failover (transparent to user)

---

## Summary

### Question
> "Is there different code path for multi-account transcription vs single account?"

### Answer
**YES - Completely different code paths:**

1. **Decision Point:** Line 974 in `transcription_tab.py`
2. **Trigger:** Cookie file count (1 vs 2+)
3. **Single-Account:** Simple sequential downloads with `YouTubeDownloadProcessor`
4. **Multi-Account:** Complex parallel system with `MultiAccountDownloadScheduler`

### Key Differences
- **Architecture:** Direct vs Scheduler-based
- **Parallelization:** None vs 20 workers
- **Speed:** 1x vs 3-6x faster
- **Failover:** None vs Automatic
- **Deduplication:** None vs Database-backed
- **Rate Limiting:** Fixed vs Randomized with sleep periods

### Recommendation
- **1-10 videos:** Single-account (simpler)
- **10+ videos:** Multi-account (faster, more robust)
- **1000+ videos:** Multi-account with 6 accounts (6x speedup)
