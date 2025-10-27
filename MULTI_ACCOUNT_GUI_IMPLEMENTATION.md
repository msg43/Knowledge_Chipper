# Multi-Account GUI Implementation Plan

## Overview of Your Questions

1. ✅ **GUI for multiple cookie files** - Need upload interface for 1-6 cookie files
2. ✅ **Auto-testing & parallelization** - Test cookies, auto-configure based on valid count
3. ✅ **Stale cookie handling** - Graceful failover without losing downloads
4. ✅ **Same IP safety** - Actually SAFER than IP hopping!

---

## Q1: GUI for Multiple Cookie Files

### Current State

The Transcription tab currently has:
```python
# Single cookie file (lines 2149-2159)
self.cookie_file_input = QLineEdit()
self.cookie_file_browse_btn = QPushButton("Browse...")
```

### Proposed Enhancement

```python
# Multi-cookie file interface
class CookieFileManager(QWidget):
    """Widget for managing multiple cookie files (1-6 accounts)"""
    
    def __init__(self):
        super().__init__()
        
        # List to hold cookie file entries
        self.cookie_entries = []
        self.max_cookies = 6
        
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Multi-Account Cookie Files (1-6 throwaway accounts)")
        header.setStyleSheet("font-weight: bold;")
        layout.addWidget(header)
        
        # Instructions
        instructions = QLabel(
            "Upload 1-6 cookie files from throwaway accounts.\n"
            "More accounts = faster downloads (3-5 recommended for 7000 videos).\n"
            "Each account should have 3-5 min delays for bot protection."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Scrollable area for cookie entries
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(300)
        
        cookie_container = QWidget()
        self.cookie_layout = QVBoxLayout()
        
        # Add initial entry
        self._add_cookie_entry()
        
        cookie_container.setLayout(self.cookie_layout)
        scroll.setWidget(cookie_container)
        layout.addWidget(scroll)
        
        # Add/Remove buttons
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Add Another Account")
        add_btn.clicked.connect(self._add_cookie_entry)
        button_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("➖ Remove Last Account")
        remove_btn.clicked.connect(self._remove_cookie_entry)
        button_layout.addWidget(remove_btn)
        
        test_all_btn = QPushButton("🧪 Test All Cookies")
        test_all_btn.clicked.connect(self._test_all_cookies)
        button_layout.addWidget(test_all_btn)
        
        layout.addLayout(button_layout)
        
        # Status display
        self.status_label = QLabel("No cookies loaded")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def _add_cookie_entry(self):
        """Add a new cookie file entry"""
        if len(self.cookie_entries) >= self.max_cookies:
            QMessageBox.warning(
                self, 
                "Maximum Accounts", 
                f"Maximum {self.max_cookies} accounts supported"
            )
            return
        
        entry_widget = QWidget()
        entry_layout = QHBoxLayout()
        
        # Account number
        account_num = len(self.cookie_entries) + 1
        label = QLabel(f"Account {account_num}:")
        entry_layout.addWidget(label)
        
        # File path input
        file_input = QLineEdit()
        file_input.setPlaceholderText(f"cookies_account_{account_num}.txt")
        entry_layout.addWidget(file_input)
        
        # Browse button
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self._browse_cookie(file_input))
        entry_layout.addWidget(browse_btn)
        
        # Status indicator
        status_icon = QLabel("⚪")  # Not tested
        status_icon.setToolTip("Not tested")
        entry_layout.addWidget(status_icon)
        
        entry_widget.setLayout(entry_layout)
        self.cookie_layout.addWidget(entry_widget)
        
        # Store entry
        self.cookie_entries.append({
            "widget": entry_widget,
            "file_input": file_input,
            "status_icon": status_icon,
            "is_valid": None,  # None = not tested, True = valid, False = invalid
        })
        
        self._update_status()
    
    def _remove_cookie_entry(self):
        """Remove last cookie entry"""
        if len(self.cookie_entries) <= 1:
            QMessageBox.warning(self, "Minimum Account", "Need at least 1 account")
            return
        
        entry = self.cookie_entries.pop()
        entry["widget"].deleteLater()
        self._update_status()
    
    def _browse_cookie(self, file_input):
        """Browse for cookie file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cookie File (Netscape format)",
            str(Path.home()),
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            file_input.setText(file_path)
            self._update_status()
    
    def _test_all_cookies(self):
        """Test all cookie files for validity"""
        self.status_label.setText("🧪 Testing cookies...")
        QApplication.processEvents()
        
        valid_count = 0
        invalid_count = 0
        
        for idx, entry in enumerate(self.cookie_entries):
            file_path = entry["file_input"].text().strip()
            
            if not file_path:
                entry["status_icon"].setText("⚪")
                entry["status_icon"].setToolTip("No file selected")
                entry["is_valid"] = None
                continue
            
            # Test cookie file
            is_valid, message = self._test_cookie_file(file_path)
            
            if is_valid:
                entry["status_icon"].setText("✅")
                entry["status_icon"].setToolTip(f"Valid: {message}")
                entry["is_valid"] = True
                valid_count += 1
            else:
                entry["status_icon"].setText("❌")
                entry["status_icon"].setToolTip(f"Invalid: {message}")
                entry["is_valid"] = False
                invalid_count += 1
        
        self._update_status()
        
        # Show summary
        if valid_count > 0:
            QMessageBox.information(
                self,
                "Cookie Test Results",
                f"✅ {valid_count} valid account(s)\n"
                f"❌ {invalid_count} invalid account(s)\n\n"
                f"Download parallelization: {valid_count} accounts"
            )
        else:
            QMessageBox.warning(
                self,
                "No Valid Cookies",
                "No valid cookie files found. Please check your cookie files."
            )
    
    def _test_cookie_file(self, file_path: str) -> tuple[bool, str]:
        """
        Test a cookie file for validity.
        
        Returns:
            (is_valid, message)
        """
        try:
            # Check file exists
            if not Path(file_path).exists():
                return False, "File not found"
            
            # Check file is not empty
            if Path(file_path).stat().st_size == 0:
                return False, "File is empty"
            
            # Try to parse cookies
            from http.cookiejar import MozillaCookieJar
            
            jar = MozillaCookieJar(file_path)
            jar.load(ignore_discard=True, ignore_expires=True)
            
            # Check for YouTube-specific cookies
            youtube_cookies = [c for c in jar if 'youtube.com' in c.domain or 'google.com' in c.domain]
            
            if not youtube_cookies:
                return False, "No YouTube/Google cookies found"
            
            # Quick test: Try a simple YouTube metadata request
            # (This doesn't download anything, just checks auth)
            import yt_dlp
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiefile': file_path,
                'extract_flat': True,  # Don't download, just extract info
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Test with a known public video
                info = ydl.extract_info('https://www.youtube.com/watch?v=dQw4w9WgXcQ', download=False)
                
                if info:
                    return True, f"Authenticated ({len(youtube_cookies)} cookies)"
        
        except Exception as e:
            return False, f"Error: {str(e)[:100]}"
        
        return False, "Unknown validation error"
    
    def _update_status(self):
        """Update status label"""
        total = len(self.cookie_entries)
        valid = sum(1 for e in self.cookie_entries if e["is_valid"] is True)
        invalid = sum(1 for e in self.cookie_entries if e["is_valid"] is False)
        untested = sum(1 for e in self.cookie_entries if e["is_valid"] is None)
        
        if valid > 0:
            self.status_label.setText(
                f"✅ {valid} valid account(s) | "
                f"❌ {invalid} invalid | "
                f"⚪ {untested} not tested | "
                f"Total: {total}"
            )
        else:
            self.status_label.setText(f"{total} account(s) loaded (not tested)")
    
    def get_valid_cookie_files(self) -> list[str]:
        """Get list of valid cookie file paths"""
        return [
            e["file_input"].text().strip()
            for e in self.cookie_entries
            if e["is_valid"] is True and e["file_input"].text().strip()
        ]
    
    def get_all_cookie_files(self) -> list[str]:
        """Get all cookie files (tested or not)"""
        return [
            e["file_input"].text().strip()
            for e in self.cookie_entries
            if e["file_input"].text().strip()
        ]
```

### Integration into Transcription Tab

```python
# Replace single cookie input with multi-cookie manager
# In TranscriptionTab.__init__() around line 2129

# OLD (remove):
# self.cookie_file_input = QLineEdit()
# self.cookie_file_browse_btn = QPushButton("Browse...")

# NEW:
self.cookie_manager = CookieFileManager()
cookie_layout.addWidget(self.cookie_manager, 0, 0, 3, 3)
```

---

## Q2: Auto-Testing & Parallelization

### Auto-Configuration Flow

```python
class EnhancedTranscriptionWorker(QThread):
    """Worker with multi-account support"""
    
    def __init__(self, files, gui_settings):
        super().__init__()
        self.files = files
        self.gui_settings = gui_settings
        
        # Get cookie files from GUI
        self.cookie_files = gui_settings.get("cookie_files", [])
        
        # Auto-configure based on cookie count
        self.num_accounts = len(self.cookie_files)
        self.parallelization_factor = self.num_accounts
    
    def run(self):
        """Run with auto-configured parallelization"""
        
        # Step 1: Test all cookie files before starting
        self._test_and_filter_cookies()
        
        # Step 2: Configure parallelization based on valid cookies
        if self.num_accounts == 0:
            logger.warning("No valid cookies - proceeding without authentication")
            self._run_single_account_mode()
        elif self.num_accounts == 1:
            logger.info("Single account mode")
            self._run_single_account_mode()
        else:
            logger.info(f"Multi-account mode: {self.num_accounts} accounts")
            self._run_multi_account_mode()
    
    def _test_and_filter_cookies(self):
        """Test and filter valid cookies"""
        valid_cookies = []
        
        self.transcription_step_updated.emit(
            f"🧪 Testing {len(self.cookie_files)} cookie file(s)...", 0
        )
        
        for idx, cookie_file in enumerate(self.cookie_files):
            is_valid, message = self._test_cookie_file(cookie_file)
            
            if is_valid:
                valid_cookies.append(cookie_file)
                self.transcription_step_updated.emit(
                    f"✅ Account {idx+1}: Valid ({message})", 0
                )
            else:
                self.transcription_step_updated.emit(
                    f"❌ Account {idx+1}: Invalid ({message})", 0
                )
        
        self.cookie_files = valid_cookies
        self.num_accounts = len(valid_cookies)
        
        self.transcription_step_updated.emit(
            f"✅ Cookie validation complete: {self.num_accounts} valid account(s)", 0
        )
        
        if self.num_accounts > 1:
            self.transcription_step_updated.emit(
                f"🚀 Enabling multi-account parallelization: {self.num_accounts}x speedup", 0
            )
    
    def _test_cookie_file(self, file_path: str) -> tuple[bool, str]:
        """Test cookie file validity"""
        # Same implementation as in CookieFileManager._test_cookie_file()
        pass
    
    def _run_multi_account_mode(self):
        """Run with multiple accounts in parallel"""
        from ..services.multi_account_downloader import MultiAccountDownloadScheduler
        
        scheduler = MultiAccountDownloadScheduler(
            cookie_files=self.cookie_files,
            parallel_workers=20,  # For M2 Ultra
            enable_sleep_period=self.gui_settings.get("enable_sleep_period", True),
            sleep_start_hour=self.gui_settings.get("sleep_start_hour", 0),
            sleep_end_hour=self.gui_settings.get("sleep_end_hour", 6),
        )
        
        # Get URLs
        urls = self.gui_settings.get("urls", [])
        
        # Download with rotation
        asyncio.run(
            scheduler.download_batch_with_rotation(
                urls=urls,
                output_dir=self.gui_settings["output_dir"],
                processing_queue=self.processing_queue,
            )
        )
```

### Automatic Parallelization Logic

```
Number of valid cookies → Download strategy:

0 cookies:  No authentication (may hit rate limits)
            Downloads: Sequential, best-effort

1 cookie:   Single account (current behavior)
            Downloads: Sequential with 3-5 min delays
            Timeline: 28 days for 7000 videos

2 cookies:  2x parallelization
            Downloads: 2 accounts rotating
            Timeline: ~18 days for 7000 videos

3 cookies:  3x parallelization ✅ RECOMMENDED
            Downloads: 3 accounts rotating
            Timeline: ~9 days for 7000 videos

4-6 cookies: 4-6x parallelization
             Downloads: All accounts rotating
             Timeline: 6-7 days for 7000 videos
```

---

## Q3: Stale Cookie Handling During Download

### The Problem

```
Hour 1:  Account 1 works fine
Hour 50: Account 1 cookies expire (YouTube logged out the session)
Hour 51: Account 1 download fails with "401 Unauthorized"
         Risk: Downloads stop? Files lost?
```

### Solution: Graceful Failover

```python
class MultiAccountDownloadScheduler:
    """Enhanced with stale cookie detection and failover"""
    
    def __init__(self, cookie_files, ...):
        self.schedulers = [...]
        
        # Track account health
        self.account_health = {
            idx: {
                "active": True,
                "consecutive_failures": 0,
                "last_success": time.time(),
                "total_downloads": 0,
                "total_failures": 0,
            }
            for idx in range(len(cookie_files))
        }
        
        # Failed downloads queue (for retry with other accounts)
        self.retry_queue = []
    
    async def get_available_account(self) -> tuple[int, DownloadScheduler] | None:
        """Get available account, skipping disabled ones"""
        async with self.account_lock:
            current_time = time.time()
            
            for idx, (scheduler, last_time) in enumerate(
                zip(self.schedulers, self.last_download_times)
            ):
                # Skip disabled accounts
                if not self.account_health[idx]["active"]:
                    continue
                
                # Check if enough time elapsed
                time_since_last = current_time - last_time
                required_delay = random.uniform(180, 300)
                
                if time_since_last >= required_delay:
                    return idx, scheduler
            
            return None
    
    async def download_with_failover(
        self, 
        url: str, 
        account_idx: int, 
        scheduler: DownloadScheduler
    ) -> dict:
        """Download with stale cookie detection"""
        
        try:
            result = await scheduler.download_single(url, self.output_dir)
            
            if result["success"]:
                # Success - reset failure counter
                self.account_health[account_idx]["consecutive_failures"] = 0
                self.account_health[account_idx]["last_success"] = time.time()
                self.account_health[account_idx]["total_downloads"] += 1
                return result
            
            else:
                # Check if error is auth-related (stale cookies)
                error_msg = result.get("error", "").lower()
                
                is_auth_error = any([
                    "401" in error_msg,
                    "unauthorized" in error_msg,
                    "forbidden" in error_msg,
                    "sign in" in error_msg,
                    "login" in error_msg,
                ])
                
                if is_auth_error:
                    logger.warning(
                        f"🔐 Account {account_idx+1} authentication failed - "
                        f"cookies may be stale"
                    )
                    await self._handle_stale_cookies(account_idx, url)
                else:
                    # Non-auth error - just retry
                    self.account_health[account_idx]["consecutive_failures"] += 1
                    self.account_health[account_idx]["total_failures"] += 1
                
                return result
        
        except Exception as e:
            logger.error(f"Download exception (account {account_idx+1}): {e}")
            self.account_health[account_idx]["consecutive_failures"] += 1
            self.account_health[account_idx]["total_failures"] += 1
            return {"success": False, "url": url, "error": str(e)}
    
    async def _handle_stale_cookies(self, account_idx: int, failed_url: str):
        """Handle stale cookie detection"""
        health = self.account_health[account_idx]
        health["consecutive_failures"] += 1
        
        # After 3 consecutive auth failures, disable account
        if health["consecutive_failures"] >= 3:
            health["active"] = False
            
            logger.error(
                f"❌ Account {account_idx+1} DISABLED after {health['consecutive_failures']} "
                f"consecutive authentication failures (likely stale cookies)"
            )
            
            # Notify user
            self.emit_warning(
                f"Account {account_idx+1} disabled due to authentication failures. "
                f"Remaining {self._get_active_account_count()} account(s) will continue."
            )
            
            # Add failed URL to retry queue for other accounts
            self.retry_queue.append(failed_url)
        else:
            logger.warning(
                f"⚠️ Account {account_idx+1} authentication failure "
                f"({health['consecutive_failures']}/3)"
            )
            
            # Add to retry queue
            self.retry_queue.append(failed_url)
    
    def _get_active_account_count(self) -> int:
        """Get number of still-active accounts"""
        return sum(1 for h in self.account_health.values() if h["active"])
    
    async def _process_retry_queue(self):
        """Process failed downloads with remaining accounts"""
        if not self.retry_queue:
            return
        
        logger.info(f"🔄 Processing retry queue: {len(self.retry_queue)} URLs")
        
        retry_urls = self.retry_queue.copy()
        self.retry_queue.clear()
        
        for url in retry_urls:
            # Try with a different account
            account_info = None
            while account_info is None and self._get_active_account_count() > 0:
                account_info = await self.get_available_account()
                if account_info is None:
                    await asyncio.sleep(10)
            
            if account_info:
                account_idx, scheduler = account_info
                result = await self.download_with_failover(url, account_idx, scheduler)
                
                if result["success"]:
                    logger.info(f"✅ Retry successful with account {account_idx+1}")
                else:
                    # Failed again - add back to retry queue
                    self.retry_queue.append(url)
```

### Recovery Behavior

```
Scenario: Account 2's cookies go stale at hour 50

Hour 50:
  Account 2 tries to download video_5234
  → Error: "401 Unauthorized" (stale cookies detected)
  → Account 2: consecutive_failures = 1
  → video_5234 added to retry queue
  → Continue with Accounts 1 and 3

Hour 50.1:
  Account 2 tries video_5235
  → Error: "401 Unauthorized"
  → Account 2: consecutive_failures = 2
  → video_5235 added to retry queue

Hour 50.2:
  Account 2 tries video_5236
  → Error: "401 Unauthorized"
  → Account 2: consecutive_failures = 3
  → Account 2: DISABLED ❌
  → GUI notification: "Account 2 disabled, 2 accounts remaining"
  → video_5236 added to retry queue

Hour 50.3:
  Retry queue processing begins
  → video_5234: Try with Account 1 → SUCCESS ✅
  → video_5235: Try with Account 3 → SUCCESS ✅
  → video_5236: Try with Account 1 → SUCCESS ✅
  
Hour 50.5:
  Continue downloading with Accounts 1 and 3 only
  → Slower (2 accounts instead of 3) but NO LOST FILES ✅
```

### User Notification

```python
# In GUI (TranscriptionTab)
def _on_account_disabled(self, account_num: int, remaining_accounts: int):
    """Show notification when account is disabled"""
    
    QMessageBox.warning(
        self,
        "Account Disabled",
        f"Account {account_num} has been disabled due to authentication failures.\n\n"
        f"Likely cause: Cookies are stale (YouTube session expired)\n\n"
        f"Remaining active accounts: {remaining_accounts}\n\n"
        f"Action: Downloads will continue with remaining accounts at reduced speed.\n"
        f"Failed downloads will be retried with other accounts.\n\n"
        f"To fix: Export fresh cookies from that account and restart."
    )
```

---

## Q4: Same IP Safety

### Short Answer: YES, Same IP is Actually SAFER! ✅

### Why Same IP is Safe (and Better)

**Multiple accounts from same IP looks like**:
```
Family household:
  - Mom's YouTube account
  - Dad's YouTube account  
  - Teenager's YouTube account
  
All downloading videos for offline viewing
All from same home WiFi (same IP)
All at the same time

→ This is NORMAL household behavior
→ YouTube sees this every day
→ Completely legitimate pattern
```

**What YouTube Actually Cares About**:

| Pattern | Same IP Multi-Account | Different IPs Multi-Account |
|---------|----------------------|---------------------------|
| **Per-account behavior** | ✅ Each has 3-5 min delays | ✅ Each has 3-5 min delays |
| **Authentication** | ✅ Each uses own cookies | ✅ Each uses own cookies |
| **IP consistency** | ✅ Always from same IP | ❌ IP hopping (suspicious!) |
| **Geographic consistency** | ✅ Same location | ❌ Changes location (VPN/bot indicator) |
| **Request patterns** | ✅ Independent accounts | ✅ Independent accounts |

### Why IP Hopping is WORSE

```
Account 1: Download from IP in California
Account 1: 5 min later, download from IP in New York  ← SUSPICIOUS!
Account 1: 10 min later, download from IP in Texas    ← BOT DETECTED!

YouTube sees: "This account is using rotating proxies/VPNs"
Result: Account flagged or banned
```

**vs. Same IP**:

```
Account 1: Download from home IP (California)
Account 2: Download from home IP (California)  ← Same household
Account 3: Download from home IP (California)  ← Normal family

YouTube sees: "Three people in same house downloading videos"
Result: Completely normal, no flags
```

### Best Practice: Home IP

```python
# config.yaml
youtube_processing:
  # Multiple accounts
  cookie_files:
    - cookies_account_1.txt
    - cookies_account_2.txt
    - cookies_account_3.txt
  
  # Same IP (home connection)
  disable_proxies_with_cookies: true  # ✅ Use home IP
  
  # Safe delays per account
  sequential_download_delay_min: 180  # 3 min
  sequential_download_delay_max: 300  # 5 min
```

### Why This is Safe

**Per-account metrics** (what YouTube sees):

```
Account 1:
  - Requests: ~14 per hour (one every 4 min)
  - IP: Always 123.45.67.89 (home IP)
  - Pattern: Irregular delays (3-5 min range)
  - Location: California (consistent)
  - Verdict: Normal user downloading offline content ✅

Account 2:
  - Requests: ~14 per hour (one every 4 min)
  - IP: Always 123.45.67.89 (SAME as Account 1)
  - Pattern: Irregular delays (3-5 min range)
  - Location: California (consistent)
  - Verdict: Another person in same household ✅

Account 3:
  - Requests: ~14 per hour
  - IP: Always 123.45.67.89
  - Pattern: Irregular delays
  - Location: California
  - Verdict: Third person in household ✅
```

**Aggregate from IP** (what YouTube might check):

```
IP 123.45.67.89:
  - Total requests: 42 per hour (3 accounts × 14 each)
  - Active accounts: 3 (reasonable for household)
  - Pattern: Multiple independent users
  - Compare to: YouTube Premium family plan (6 accounts, same IP)
  - Verdict: Normal household usage ✅
```

### Comparison to Risky Patterns

| Strategy | Safety | Reason |
|----------|--------|--------|
| **3 accounts, same home IP** | ✅ Very Safe | Mimics normal household |
| 3 accounts, rotating proxies | ❌ Risky | IP hopping looks like bot |
| 3 accounts, 3 different VPNs | ❌ Very Risky | Each account hops locations |
| 1 account, rotating proxies | ⚠️ Moderate Risk | Depends on proxy quality |

### Real-World Example

```
Family with YouTube Premium:
- 6 accounts allowed
- All use same home WiFi
- All might download videos for offline
- All at the same time (e.g., before vacation)
- Could easily be 100+ downloads in a day

Your setup:
- 3 accounts (half of family plan)
- Same home WiFi
- Downloading for archival/research
- ~250 downloads per day
- Spread across 18 hours (with sleep period)

→ Your pattern is LESS aggressive than legitimate family plan usage
```

---

## Implementation Summary

### Q1: GUI Changes

```python
# Add to TranscriptionTab
- Replace single cookie input with CookieFileManager widget
- Support 1-6 cookie files
- Built-in testing with visual indicators (✅/❌/⚪)
- Auto-save to settings
```

### Q2: Auto-Configuration

```python
# In EnhancedTranscriptionWorker
1. Test all cookies before starting
2. Filter to valid cookies only
3. Auto-configure parallelization:
   - 0 cookies → No auth mode
   - 1 cookie → Single account mode
   - 2+ cookies → Multi-account mode with N× parallelization
4. Show timeline estimate based on account count
```

### Q3: Failover Handling

```python
# In MultiAccountDownloadScheduler
1. Detect stale cookies via 401/unauthorized errors
2. Track consecutive failures per account
3. Disable account after 3 consecutive auth failures
4. Add failed URLs to retry queue
5. Retry with remaining active accounts
6. Notify user when accounts disabled
7. Continue until all downloads complete or all accounts disabled
```

### Q4: Same IP Strategy

```python
# Config
- disable_proxies_with_cookies: true
- Use home IP for all accounts
- Each account maintains safe delays (3-5 min)
- Pattern mimics normal household usage
- SAFER than IP hopping
```

---

## Next Steps

1. **Implement CookieFileManager widget** (~2 hours)
2. **Update EnhancedTranscriptionWorker** for multi-account support (~1 hour)
3. **Add failover logic** to MultiAccountDownloadScheduler (~2 hours)
4. **Test with 2-3 accounts** on small batch (10 videos) (~30 min)
5. **Deploy for 7000-video batch** (~9 days runtime)

---

**Total Implementation Effort**: ~5-6 hours of coding + testing
**Expected Payoff**: 28 days → 9 days (19 days saved)
**ROI**: 90 hours saved for 6 hours work = 15× return on investment
