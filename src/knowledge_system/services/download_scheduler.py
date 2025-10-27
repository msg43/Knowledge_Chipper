#!/usr/bin/env python3
"""
Download Scheduler with Sleep Period Support

Manages download timing to mimic human behavior patterns, including
optional sleep periods to avoid appearing as automated 24/7 bot activity.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..processors.youtube_download import YouTubeDownloadProcessor

logger = logging.getLogger(__name__)


class DownloadScheduler:
    """
    Schedules downloads with human-like patterns including sleep periods.

    Features:
    - Configurable daily sleep period (e.g., midnight - 6am)
    - Randomized delays between downloads (3-5 min)
    - Queue-aware pacing to match processing throughput
    - Timezone-aware sleep scheduling
    """

    def __init__(
        self,
        cookie_file_path: str | None = None,
        enable_sleep_period: bool = True,
        sleep_start_hour: int = 0,
        sleep_end_hour: int = 6,
        timezone: str = "America/Los_Angeles",
        min_delay: float = 180.0,
        max_delay: float = 300.0,
    ):
        """
        Initialize download scheduler.

        Args:
            cookie_file_path: Path to cookies.txt file for authentication
            enable_sleep_period: Enable daily sleep period
            sleep_start_hour: Hour to start sleep (0-23, e.g., 0 = midnight)
            sleep_end_hour: Hour to end sleep (0-23, e.g., 6 = 6am)
            timezone: Timezone for sleep period (e.g., 'America/New_York')
            min_delay: Minimum seconds between downloads (default 180 = 3 min)
            max_delay: Maximum seconds between downloads (default 300 = 5 min)
        """
        self.cookie_file_path = cookie_file_path
        self.enable_sleep_period = enable_sleep_period
        self.sleep_start = sleep_start_hour
        self.sleep_end = sleep_end_hour
        self.timezone = ZoneInfo(timezone)
        self.min_delay = min_delay
        self.max_delay = max_delay

        # Initialize downloader
        self.downloader = YouTubeDownloadProcessor(
            enable_cookies=bool(cookie_file_path),
            cookie_file_path=cookie_file_path,
            download_thumbnails=True,
        )

        # Statistics
        self.stats = {
            "downloads_attempted": 0,
            "downloads_successful": 0,
            "downloads_failed": 0,
            "sleep_periods": 0,
            "total_sleep_time": 0.0,
        }

        logger.info(
            f"Download scheduler initialized: "
            f"sleep_period={'enabled' if enable_sleep_period else 'disabled'}, "
            f"sleep_hours={sleep_start_hour:02d}:00-{sleep_end_hour:02d}:00 {timezone}"
        )

    def is_sleep_time(self) -> bool:
        """Check if currently in sleep period"""
        if not self.enable_sleep_period:
            return False

        now = datetime.now(self.timezone)
        current_hour = now.hour

        # Handle wrap-around (e.g., 23:00 to 07:00)
        if self.sleep_start < self.sleep_end:
            # Normal case: e.g., 0 to 6 (midnight to 6am)
            return self.sleep_start <= current_hour < self.sleep_end
        else:
            # Wrap-around case: e.g., 22 to 6 (10pm to 6am)
            return current_hour >= self.sleep_start or current_hour < self.sleep_end

    def get_next_wake_time(self) -> datetime:
        """Calculate when sleep period ends"""
        now = datetime.now(self.timezone)

        # Create wake time for today
        wake_time = now.replace(hour=self.sleep_end, minute=0, second=0, microsecond=0)

        # If wake time already passed today, use tomorrow's wake time
        if wake_time <= now:
            wake_time += timedelta(days=1)

        return wake_time

    async def wait_until_wake_time(self):
        """Wait until sleep period ends"""
        if not self.is_sleep_time():
            return

        wake_time = self.get_next_wake_time()
        now = datetime.now(self.timezone)
        sleep_duration = (wake_time - now).total_seconds()

        logger.info(
            f"😴 Entering sleep period. "
            f"Will resume in {sleep_duration/3600:.1f} hours at {wake_time.strftime('%Y-%m-%d %H:%M %Z')}"
        )

        self.stats["sleep_periods"] += 1
        self.stats["total_sleep_time"] += sleep_duration

        await asyncio.sleep(sleep_duration)

        logger.info("☀️ Sleep period ended, resuming downloads")

    def calculate_delay(
        self, queue_size: int | None = None, target_queue_size: int = 10
    ) -> float:
        """
        Calculate delay before next download based on queue state.

        Args:
            queue_size: Current number of videos in processing queue
            target_queue_size: Desired queue size to maintain

        Returns:
            Delay in seconds
        """
        # Base delay with randomization
        base_delay = random.uniform(self.min_delay, self.max_delay)

        # Adjust based on queue size if provided
        if queue_size is not None:
            if queue_size < target_queue_size // 2:
                # Queue is low - download faster (reduce delay by 33%)
                return base_delay * 0.67
            elif queue_size > target_queue_size * 2:
                # Queue is high - slow down (increase delay by 50%)
                return base_delay * 1.5

        return base_delay

    async def download_single(self, url: str, output_dir: Path | None = None) -> dict:
        """
        Download single video with sleep period awareness.

        Args:
            url: YouTube video URL
            output_dir: Directory to save downloaded audio

        Returns:
            Result dict with success status and file path
        """
        # Check if we should sleep
        if self.is_sleep_time():
            await self.wait_until_wake_time()

        # Download video
        self.stats["downloads_attempted"] += 1

        try:
            result = self.downloader.process(
                input_data=url,
                output_dir=output_dir,
            )

            if result.success:
                self.stats["downloads_successful"] += 1
                logger.info(
                    f"✅ Downloaded: {result.output_data} "
                    f"({self.stats['downloads_successful']}/{self.stats['downloads_attempted']})"
                )
                return {
                    "success": True,
                    "url": url,
                    "audio_file": result.output_data,
                    "metadata": result.metadata,
                }
            else:
                self.stats["downloads_failed"] += 1
                logger.error(f"❌ Download failed: {url}")
                return {
                    "success": False,
                    "url": url,
                    "error": "Download processor returned failure",
                }

        except Exception as e:
            self.stats["downloads_failed"] += 1
            logger.error(f"❌ Download error for {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e),
            }

    async def download_batch_with_pacing(
        self,
        urls: list[str],
        output_dir: Path | None = None,
        queue_size_callback=None,
        progress_callback=None,
        target_queue_size: int = 10,
    ) -> list[dict]:
        """
        Download batch of URLs with intelligent pacing and sleep periods.

        Args:
            urls: List of YouTube URLs to download
            output_dir: Directory to save downloaded audio
            queue_size_callback: Callable that returns current queue size
            progress_callback: Callable for progress updates
            target_queue_size: Desired processing queue size to maintain

        Returns:
            List of result dicts for each download
        """
        results = []

        for idx, url in enumerate(urls, 1):
            # Download
            result = await self.download_single(url, output_dir)
            results.append(result)

            # Progress callback
            if progress_callback:
                progress_callback(idx, len(urls), result)

            # Don't delay after last download
            if idx < len(urls):
                # Get current queue size if callback provided
                current_queue_size = (
                    queue_size_callback() if queue_size_callback else None
                )

                # Calculate delay
                delay = self.calculate_delay(current_queue_size, target_queue_size)

                logger.info(
                    f"⏳ Waiting {delay/60:.1f} minutes before next download "
                    f"(queue: {current_queue_size if current_queue_size is not None else 'N/A'})"
                )

                await asyncio.sleep(delay)

        return results

    def get_stats(self) -> dict:
        """Get download statistics"""
        return {
            **self.stats,
            "success_rate": (
                self.stats["downloads_successful"] / self.stats["downloads_attempted"]
                if self.stats["downloads_attempted"] > 0
                else 0.0
            ),
            "total_sleep_hours": self.stats["total_sleep_time"] / 3600,
        }

    def log_stats(self):
        """Log current statistics"""
        stats = self.get_stats()
        logger.info(
            f"📊 Download stats: "
            f"{stats['downloads_successful']}/{stats['downloads_attempted']} successful "
            f"({stats['success_rate']:.1%}), "
            f"{stats['sleep_periods']} sleep periods "
            f"({stats['total_sleep_hours']:.1f} hours)"
        )


def create_download_scheduler(
    cookie_file_path: str | None = None,
    use_config: bool = True,
) -> DownloadScheduler:
    """
    Create download scheduler from config or with defaults.

    Args:
        cookie_file_path: Path to cookies file (overrides config)
        use_config: Load settings from config file

    Returns:
        Configured DownloadScheduler instance
    """
    if use_config:
        config = get_settings()
        yt_config = config.youtube_processing

        return DownloadScheduler(
            cookie_file_path=cookie_file_path or yt_config.cookie_file_path,
            enable_sleep_period=getattr(yt_config, "enable_sleep_period", True),
            sleep_start_hour=getattr(yt_config, "sleep_start_hour", 0),
            sleep_end_hour=getattr(yt_config, "sleep_end_hour", 6),
            sleep_timezone=getattr(yt_config, "sleep_timezone", "America/Los_Angeles"),
            min_delay=yt_config.sequential_download_delay_min,
            max_delay=yt_config.sequential_download_delay_max,
        )
    else:
        return DownloadScheduler(cookie_file_path=cookie_file_path)
