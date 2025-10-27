#!/usr/bin/env python3
"""
Multi-Account Download Scheduler

Manages downloads across multiple YouTube accounts with:
- Cookie rotation for load distribution
- Stale cookie detection and failover
- Retry queue for failed downloads
- Sleep period support
- Deduplication across all accounts
"""

import asyncio
import logging
import random
import time
from pathlib import Path

from ..database import DatabaseService
from ..logger import get_logger
from ..utils.deduplication import DuplicationPolicy, VideoDeduplicationService
from .download_scheduler import DownloadScheduler

logger = get_logger(__name__)


class MultiAccountDownloadScheduler:
    """
    Manages downloads across multiple YouTube accounts with failover.
    
    Features:
    - Cookie rotation to distribute load
    - Automatic stale cookie detection (401/403 errors)
    - Graceful failover when accounts fail
    - Retry queue for failed downloads
    - Deduplication across all accounts
    - Sleep period support per account
    """
    
    def __init__(
        self,
        cookie_files: list[str],
        parallel_workers: int = 20,
        enable_sleep_period: bool = True,
        sleep_start_hour: int = 0,
        sleep_end_hour: int = 6,
        sleep_timezone: str = "America/Los_Angeles",
        min_delay: float = 180.0,
        max_delay: float = 300.0,
        db_service: DatabaseService | None = None,
    ):
        """
        Initialize multi-account download scheduler.
        
        Args:
            cookie_files: List of paths to cookie files (1-6 accounts)
            parallel_workers: Number of parallel processing workers
            enable_sleep_period: Enable daily sleep period
            sleep_start_hour: Hour to start sleep (0-23)
            sleep_end_hour: Hour to end sleep (0-23)
            sleep_timezone: Timezone for sleep period
            min_delay: Minimum seconds between downloads per account
            max_delay: Maximum seconds between downloads per account
            db_service: Database service for deduplication
        """
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
                timezone=sleep_timezone,
                min_delay=min_delay,
                max_delay=max_delay,
            )
            for cf in cookie_files
        ]
        
        # Initialize deduplication service (shared across all accounts)
        self.dedup_service = VideoDeduplicationService(db_service)
        
        # Track last download time per account
        self.last_download_times = [0.0] * len(cookie_files)
        self.account_lock = asyncio.Lock()
        
        # Track account health
        self.account_health = {
            idx: {
                "active": True,
                "consecutive_failures": 0,
                "consecutive_auth_failures": 0,
                "last_success": time.time(),
                "total_downloads": 0,
                "total_failures": 0,
                "error_messages": [],
            }
            for idx in range(len(cookie_files))
        }
        
        # Failed downloads queue (for retry with other accounts)
        self.retry_queue = []
        
        # Statistics
        self.stats = {
            "total_urls": 0,
            "unique_urls": 0,
            "duplicates_skipped": 0,
            "downloads_completed": 0,
            "downloads_failed": 0,
            "accounts_disabled": 0,
            "retries_attempted": 0,
            "retries_successful": 0,
        }
        
        # Progress callback (set by caller)
        self.progress_callback = None
        
        logger.info(
            f"Multi-account scheduler initialized: {len(self.schedulers)} accounts, "
            f"sleep_period={'enabled' if enable_sleep_period else 'disabled'}"
        )
    
    async def get_available_account(self) -> tuple[int, DownloadScheduler] | None:
        """
        Get account that's ready to download (delay elapsed and not disabled).
        
        Returns:
            Tuple of (account_index, scheduler) or None if no account available
        """
        async with self.account_lock:
            current_time = time.time()
            
            for idx, (scheduler, last_time) in enumerate(
                zip(self.schedulers, self.last_download_times)
            ):
                # Skip disabled accounts
                if not self.account_health[idx]["active"]:
                    continue
                
                # Check if in sleep period
                if scheduler.is_sleep_time():
                    continue
                
                # Check if enough time elapsed since last download
                time_since_last = current_time - last_time
                required_delay = random.uniform(180, 300)  # 3-5 min
                
                if time_since_last >= required_delay:
                    return idx, scheduler
            
            return None
    
    async def download_with_failover(
        self,
        url: str,
        account_idx: int,
        scheduler: DownloadScheduler,
        output_dir: Path,
    ) -> dict:
        """
        Download with stale cookie detection and failover.
        
        Args:
            url: YouTube URL to download
            account_idx: Index of account being used
            scheduler: DownloadScheduler for this account
            output_dir: Output directory for downloaded files
            
        Returns:
            Result dict with success status
        """
        try:
            result = await scheduler.download_single(url, output_dir)
            
            if result["success"]:
                # Success - reset failure counters
                self.account_health[account_idx]["consecutive_failures"] = 0
                self.account_health[account_idx]["consecutive_auth_failures"] = 0
                self.account_health[account_idx]["last_success"] = time.time()
                self.account_health[account_idx]["total_downloads"] += 1
                self.stats["downloads_completed"] += 1
                return result
            
            else:
                # Download failed - analyze error
                error_msg = result.get("error", "").lower()
                
                # Check if error is auth-related (stale cookies)
                is_auth_error = any([
                    "401" in error_msg,
                    "403" in error_msg,
                    "unauthorized" in error_msg,
                    "forbidden" in error_msg,
                    "sign in" in error_msg,
                    "login" in error_msg,
                    "cookies" in error_msg,
                ])
                
                if is_auth_error:
                    logger.warning(
                        f"🔐 Account {account_idx+1} authentication failed: {error_msg}"
                    )
                    await self._handle_auth_failure(account_idx, url)
                else:
                    # Non-auth error
                    logger.warning(f"Download failed (account {account_idx+1}): {error_msg}")
                    self.account_health[account_idx]["consecutive_failures"] += 1
                    self.account_health[account_idx]["total_failures"] += 1
                
                # Track error message
                self.account_health[account_idx]["error_messages"].append(error_msg)
                if len(self.account_health[account_idx]["error_messages"]) > 10:
                    self.account_health[account_idx]["error_messages"].pop(0)
                
                self.stats["downloads_failed"] += 1
                return result
        
        except Exception as e:
            logger.error(f"Download exception (account {account_idx+1}): {e}")
            self.account_health[account_idx]["consecutive_failures"] += 1
            self.account_health[account_idx]["total_failures"] += 1
            self.stats["downloads_failed"] += 1
            return {"success": False, "url": url, "error": str(e)}
    
    async def _handle_auth_failure(self, account_idx: int, failed_url: str):
        """
        Handle authentication failure (likely stale cookies).
        
        Args:
            account_idx: Index of account that failed
            failed_url: URL that failed to download
        """
        health = self.account_health[account_idx]
        health["consecutive_auth_failures"] += 1
        health["consecutive_failures"] += 1
        
        # After 3 consecutive auth failures, disable account
        if health["consecutive_auth_failures"] >= 3:
            health["active"] = False
            self.stats["accounts_disabled"] += 1
            
            logger.error(
                f"❌ Account {account_idx+1} DISABLED after "
                f"{health['consecutive_auth_failures']} consecutive authentication failures"
            )
            logger.error(
                f"   Likely cause: Stale cookies (YouTube session expired)"
            )
            logger.info(
                f"   Remaining active accounts: {self._get_active_account_count()}"
            )
            
            # Notify via callback if available
            if self.progress_callback:
                self.progress_callback(
                    f"⚠️ Account {account_idx+1} disabled due to authentication failures. "
                    f"{self._get_active_account_count()} account(s) remaining."
                )
            
            # Add failed URL to retry queue
            self.retry_queue.append(failed_url)
        else:
            logger.warning(
                f"⚠️ Account {account_idx+1} authentication failure "
                f"({health['consecutive_auth_failures']}/3)"
            )
            
            # Add to retry queue
            self.retry_queue.append(failed_url)
    
    def _get_active_account_count(self) -> int:
        """Get number of still-active accounts"""
        return sum(1 for h in self.account_health.values() if h["active"])
    
    async def download_batch_with_rotation(
        self,
        urls: list[str],
        output_dir: Path,
        processing_queue: asyncio.Queue | None = None,
        progress_callback=None,
    ) -> list[dict]:
        """
        Download batch of URLs using account rotation with deduplication.
        
        Args:
            urls: List of YouTube URLs to download
            output_dir: Directory to save downloaded audio
            processing_queue: Optional queue to put results for processing
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of result dicts for each download
        """
        self.progress_callback = progress_callback
        results = []
        
        # Step 1: Filter duplicates BEFORE downloading
        logger.info(f"🔍 Checking {len(urls)} URLs for duplicates...")
        if progress_callback:
            progress_callback("🔍 Checking for duplicate videos...")
        
        self.stats["total_urls"] = len(urls)
        
        unique_urls, duplicate_results = self.dedup_service.check_batch_duplicates(
            urls,
            DuplicationPolicy.SKIP_ALL
        )
        
        self.stats["unique_urls"] = len(unique_urls)
        self.stats["duplicates_skipped"] = len(duplicate_results)
        
        logger.info(
            f"✅ Deduplication complete: {len(unique_urls)} unique, "
            f"{len(duplicate_results)} duplicates skipped"
        )
        
        if duplicate_results:
            time_saved = len(duplicate_results) * 25 / 60  # 25 min per video
            logger.info(f"💰 Time saved by skipping duplicates: ~{time_saved:.1f} hours")
        
        if progress_callback:
            progress_callback(
                f"✅ Found {len(unique_urls)} unique videos "
                f"({len(duplicate_results)} duplicates skipped)"
            )
        
        # Step 2: Download only unique URLs with account rotation
        logger.info(
            f"🚀 Starting downloads with {len(self.schedulers)} account(s)"
        )
        
        for idx, url in enumerate(unique_urls, 1):
            # Check if any accounts still active
            if self._get_active_account_count() == 0:
                logger.error("❌ All accounts disabled - cannot continue")
                if progress_callback:
                    progress_callback(
                        "❌ All accounts disabled. Remaining URLs cannot be downloaded."
                    )
                break
            
            # Wait for an available account
            account_info = None
            wait_start = time.time()
            
            while account_info is None:
                account_info = await self.get_available_account()
                
                if account_info is None:
                    # Check if we're in sleep period for all accounts
                    if all(s.is_sleep_time() for s in self.schedulers if self.account_health[i]["active"] for i, s in enumerate(self.schedulers)):
                        # Wait for wake time
                        for scheduler in self.schedulers:
                            if scheduler.is_sleep_time():
                                await scheduler.wait_until_wake_time()
                                break
                    else:
                        # All accounts on cooldown
                        await asyncio.sleep(10)
                
                # Check if processing queue is full (if provided)
                if processing_queue and processing_queue.qsize() >= self.parallel_workers * 2:
                    account_info = None
                    await asyncio.sleep(30)
                
                # Safety timeout
                if time.time() - wait_start > 600:  # 10 min
                    logger.error("Timeout waiting for available account")
                    break
            
            if account_info is None:
                logger.warning(f"Could not get available account for {url}")
                continue
            
            account_idx, scheduler = account_info
            
            # Download with this account
            result = await self.download_with_failover(url, account_idx, scheduler, output_dir)
            results.append(result)
            
            # Update last download time for this account
            async with self.account_lock:
                self.last_download_times[account_idx] = time.time()
            
            # Add to processing queue if successful
            if result["success"] and processing_queue:
                await processing_queue.put(result.get("audio_file"))
            
            # Progress update
            if progress_callback and idx % 10 == 0:
                progress_callback(
                    f"Downloaded {idx}/{len(unique_urls)} "
                    f"({self.stats['downloads_completed']} successful, "
                    f"{self.stats['downloads_failed']} failed)"
                )
            
            logger.info(
                f"✅ Downloaded via account {account_idx+1}/{len(self.schedulers)} "
                f"({idx}/{len(unique_urls)}), "
                f"queue: {processing_queue.qsize() if processing_queue else 'N/A'}"
            )
        
        # Step 3: Process retry queue if there are failed downloads
        if self.retry_queue:
            logger.info(f"🔄 Processing retry queue: {len(self.retry_queue)} URLs")
            await self._process_retry_queue(output_dir, processing_queue)
        
        # Log final statistics
        logger.info(
            f"📊 Download batch complete: "
            f"{self.stats['downloads_completed']}/{self.stats['unique_urls']} successful, "
            f"{self.stats['downloads_failed']} failed, "
            f"{self.stats['duplicates_skipped']} duplicates skipped, "
            f"{self.stats['accounts_disabled']} accounts disabled"
        )
        
        if progress_callback:
            progress_callback(
                f"✅ Batch complete: {self.stats['downloads_completed']} downloaded, "
                f"{self.stats['downloads_failed']} failed"
            )
        
        return results
    
    async def _process_retry_queue(
        self,
        output_dir: Path,
        processing_queue: asyncio.Queue | None = None,
    ):
        """Process failed downloads with remaining accounts"""
        retry_urls = self.retry_queue.copy()
        self.retry_queue.clear()
        
        for url in retry_urls:
            self.stats["retries_attempted"] += 1
            
            # Try with a different account
            account_info = None
            while account_info is None and self._get_active_account_count() > 0:
                account_info = await self.get_available_account()
                if account_info is None:
                    await asyncio.sleep(10)
            
            if not account_info:
                logger.error(f"No available accounts for retry: {url}")
                self.retry_queue.append(url)  # Keep for manual retry
                continue
            
            account_idx, scheduler = account_info
            
            result = await self.download_with_failover(url, account_idx, scheduler, output_dir)
            
            if result["success"]:
                logger.info(f"✅ Retry successful with account {account_idx+1}")
                self.stats["retries_successful"] += 1
                
                if processing_queue:
                    await processing_queue.put(result.get("audio_file"))
            else:
                logger.warning(f"❌ Retry failed: {url}")
                self.retry_queue.append(url)  # Failed again
    
    def get_stats(self) -> dict:
        """Get download statistics"""
        return {
            **self.stats,
            "active_accounts": self._get_active_account_count(),
            "total_accounts": len(self.schedulers),
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
            "retry_success_rate": (
                self.stats["retries_successful"] / self.stats["retries_attempted"]
                if self.stats["retries_attempted"] > 0
                else 0.0
            ),
            "account_health": self.account_health,
        }
    
    def get_failed_urls(self) -> list[str]:
        """Get list of URLs that failed after all retries"""
        return self.retry_queue.copy()

