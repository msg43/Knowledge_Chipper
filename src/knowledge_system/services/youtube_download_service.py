"""
YouTube Download Service

Unified service for downloading YouTube audio with retry logic, cookie support,
and smart failure handling. Consolidates duplicate logic from TranscriptionTab
worker and UnifiedBatchProcessor.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ..logger import get_logger
from ..processors.youtube_download import YouTubeDownloadProcessor
from ..utils.cancellation import CancellationToken
from ..utils.youtube_utils import expand_playlist_urls_with_metadata

logger = get_logger(__name__)


class DownloadResult:
    """Result of a YouTube download operation."""

    def __init__(
        self,
        url: str,
        success: bool,
        audio_file: Path | None = None,
        error: str | None = None,
    ):
        self.url = url
        self.success = success
        self.audio_file = audio_file
        self.error = error


class YouTubeDownloadService:
    """
    Unified YouTube download service with retry logic and failure tracking.

    Features:
    - Sequential or parallel download modes
    - Smart retry queue with failure tracking
    - Cookie-based authentication support
    - Progress callbacks for GUI integration
    - Automatic playlist expansion
    """

    def __init__(
        self,
        enable_cookies: bool = False,
        cookie_file_path: str | None = None,
        youtube_delay: int = 5,
        db_service=None,
        disable_proxies_with_cookies: bool | None = None,
    ):
        """
        Initialize YouTube download service.

        Args:
            enable_cookies: Enable cookie-based authentication
            cookie_file_path: Path to cookie file
            youtube_delay: Delay between sequential downloads (seconds)
            db_service: Database service for failure tracking
            disable_proxies_with_cookies: Disable proxies when cookies are enabled
        """
        self.enable_cookies = enable_cookies
        self.cookie_file_path = cookie_file_path
        self.youtube_delay = youtube_delay
        self.db_service = db_service
        self.disable_proxies_with_cookies = disable_proxies_with_cookies

        # Create YouTube downloader
        self.downloader = YouTubeDownloadProcessor(
            download_thumbnails=True,
            enable_cookies=enable_cookies,
            cookie_file_path=cookie_file_path if cookie_file_path else None,
            disable_proxies_with_cookies=disable_proxies_with_cookies,
        )

        # Retry tracking
        self.max_retries = 3
        self.retry_queue = []
        self.failed_urls = []

    def expand_urls(self, urls: list[str]) -> tuple[list[str], list[dict]]:
        """
        Expand YouTube playlists into individual video URLs.

        Returns:
            (expanded_urls, playlist_info)
        """
        if not urls:
            return [], []

        expansion_result = expand_playlist_urls_with_metadata(urls)
        expanded_urls = expansion_result["expanded_urls"]
        playlist_info = expansion_result["playlist_info"]

        if playlist_info:
            total_playlist_videos = sum(p["total_videos"] for p in playlist_info)
            logger.info(
                f"Found {len(playlist_info)} playlist(s) with {total_playlist_videos} total videos"
            )
            for i, playlist in enumerate(playlist_info, 1):
                title = playlist.get("title", "Unknown Playlist")
                video_count = playlist.get("total_videos", 0)
                logger.info(f"  {i}. {title} ({video_count} videos)")

        return expanded_urls, playlist_info

    def download_sequential(
        self,
        urls: list[str],
        downloads_dir: Path,
        progress_callback=None,
        cancellation_token: CancellationToken | None = None,
    ) -> list[DownloadResult]:
        """
        Download URLs sequentially (one at a time) to avoid bot detection.

        Args:
            urls: List of YouTube URLs to download
            downloads_dir: Directory to save audio files
            progress_callback: Optional callback(url, index, total, status)
            cancellation_token: Optional cancellation token

        Returns:
            List of DownloadResult objects
        """
        downloads_dir.mkdir(parents=True, exist_ok=True)
        results = []
        cancellation_token = cancellation_token or CancellationToken()

        logger.info(
            f"Starting sequential downloads: {len(urls)} URLs (one at a time for safety)"
        )

        for idx, url in enumerate(urls, 1):
            if cancellation_token.is_cancelled():
                logger.info("Download cancelled by user")
                break

            if progress_callback:
                progress_callback(url, idx, len(urls), "downloading")

            # Apply delay between videos (skip for first video)
            if idx > 1 and self.youtube_delay > 0:
                logger.info(f"⏱️ Waiting {self.youtube_delay}s before next download...")
                time.sleep(self.youtube_delay)

            # Attempt download
            result = self._download_single_url(url, idx, len(urls), downloads_dir)
            results.append(result)

            if not result.success and self.db_service:
                # Handle failure with retry logic
                retry_decision = self._handle_failed_url(url, result.error)
                if retry_decision == "REQUEUE":
                    self.retry_queue.append(url)
                    logger.info(f"🔄 Queued for retry: {url[:40]}...")
                else:
                    self.failed_urls.append(
                        {
                            "url": url,
                            "error": result.error,
                            "index": idx,
                        }
                    )

        # Process retry queue
        if self.retry_queue and not cancellation_token.is_cancelled():
            logger.info(f"🔄 Processing retry queue: {len(self.retry_queue)} URLs")
            retry_results = self._process_retry_queue(
                downloads_dir, len(urls), progress_callback, cancellation_token
            )
            results.extend(retry_results)

        return results

    def download_parallel(
        self,
        urls: list[str],
        downloads_dir: Path,
        max_concurrent: int = 4,
        progress_callback=None,
        cancellation_token: CancellationToken | None = None,
    ) -> list[DownloadResult]:
        """
        Download URLs in parallel for batch processing.

        Args:
            urls: List of YouTube URLs to download
            downloads_dir: Directory to save audio files
            max_concurrent: Maximum concurrent downloads
            progress_callback: Optional callback(url, current, total, status)
            cancellation_token: Optional cancellation token

        Returns:
            List of DownloadResult objects
        """
        downloads_dir.mkdir(parents=True, exist_ok=True)
        results = []
        cancellation_token = cancellation_token or CancellationToken()

        logger.info(
            f"Starting parallel downloads: {len(urls)} URLs ({max_concurrent} concurrent)"
        )

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_url = {
                executor.submit(
                    self._download_single_url, url, idx, len(urls), downloads_dir
                ): (url, idx)
                for idx, url in enumerate(urls, 1)
            }

            for future in as_completed(future_to_url):
                if cancellation_token.is_cancelled():
                    # Cancel remaining futures
                    for f in future_to_url:
                        if not f.done():
                            f.cancel()
                    break

                url, idx = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)

                    if progress_callback:
                        status = "success" if result.success else "failed"
                        progress_callback(url, len(results), len(urls), status)

                except Exception as e:
                    logger.error(f"Exception downloading {url}: {e}")
                    results.append(DownloadResult(url, False, None, str(e)))

        return results

    def _download_single_url(
        self, url: str, index: int, total: int, downloads_dir: Path
    ) -> DownloadResult:
        """
        Download a single YouTube video.

        Args:
            url: YouTube URL
            index: Current index (1-based)
            total: Total number of URLs
            downloads_dir: Download directory

        Returns:
            DownloadResult object
        """
        try:
            logger.info(f"📥 [{index}/{total}] Downloading: {url[:60]}...")

            # Use YouTubeDownloadProcessor
            result = self.downloader.process(
                url,
                output_dir=str(downloads_dir),
                download_thumbnails=True,
                db_service=self.db_service,
            )

            if result.success and result.data:
                audio_file = Path(result.data.get("audio_path", ""))
                if audio_file.exists():
                    logger.info(f"✅ [{index}/{total}] Downloaded: {audio_file.name}")
                    return DownloadResult(url, True, audio_file, None)
                else:
                    error = "Audio file not found after download"
                    logger.error(f"❌ [{index}/{total}] {error}")
                    return DownloadResult(url, False, None, error)
            else:
                error = result.errors[0] if result.errors else "Unknown download error"
                logger.error(f"❌ [{index}/{total}] Failed: {error}")
                return DownloadResult(url, False, None, error)

        except Exception as e:
            error = f"Exception: {str(e)}"
            logger.error(f"❌ [{index}/{total}] {error}")
            return DownloadResult(url, False, None, error)

    def _handle_failed_url(self, url: str, error: str) -> str:
        """
        Handle failed URL with smart retry logic.

        Returns:
            "REQUEUE" if should retry, "PERMANENT_FAILURE" otherwise
        """
        if not self.db_service:
            return "PERMANENT_FAILURE"

        try:
            # Check how many times this URL has failed
            from ..utils.youtube_utils import extract_video_id

            video_id = extract_video_id(url)

            # Query database for failure count
            failure_count = self.db_service.get_download_failure_count(video_id)

            if failure_count < self.max_retries:
                logger.info(
                    f"URL failed {failure_count + 1}/{self.max_retries} times - will retry"
                )
                return "REQUEUE"
            else:
                logger.warning(
                    f"URL failed {failure_count + 1} times - marking as permanent failure"
                )
                return "PERMANENT_FAILURE"

        except Exception as e:
            logger.warning(f"Could not check failure count: {e}")
            return "PERMANENT_FAILURE"

    def _process_retry_queue(
        self,
        downloads_dir: Path,
        original_total: int,
        progress_callback=None,
        cancellation_token: CancellationToken | None = None,
    ) -> list[DownloadResult]:
        """Process URLs in the retry queue."""
        results = []
        retry_idx = 0

        while self.retry_queue and not (
            cancellation_token and cancellation_token.is_cancelled()
        ):
            retry_url = self.retry_queue.pop(0)
            retry_idx += 1

            logger.info(f"🔄 Retry {retry_idx}: {retry_url[:40]}...")

            if progress_callback:
                progress_callback(
                    retry_url,
                    original_total + retry_idx,
                    original_total + len(self.retry_queue) + retry_idx,
                    "retrying",
                )

            # Apply delay before retry
            if self.youtube_delay > 0:
                time.sleep(self.youtube_delay)

            result = self._download_single_url(
                retry_url,
                original_total + retry_idx,
                original_total + len(self.retry_queue) + retry_idx,
                downloads_dir,
            )
            results.append(result)

            if not result.success:
                # Second failure - mark as permanent
                retry_decision = self._handle_failed_url(retry_url, result.error)
                if retry_decision == "PERMANENT_FAILURE":
                    self.failed_urls.append(
                        {
                            "url": retry_url,
                            "error": result.error,
                            "index": original_total + retry_idx,
                        }
                    )
                    logger.error(f"❌ Retry failed permanently: {retry_url[:40]}...")

        return results

    def get_failed_urls(self) -> list[dict]:
        """Get list of permanently failed URLs."""
        return self.failed_urls

    def save_failed_urls(self, output_dir: Path) -> Path | None:
        """
        Save failed URLs to a text file for easy retry.

        Returns:
            Path to saved file, or None if no failures
        """
        if not self.failed_urls:
            return None

        try:
            failed_urls_file = output_dir / "failed_downloads.txt"
            with open(failed_urls_file, "w") as f:
                f.write(f"# Failed YouTube Downloads - {len(self.failed_urls)} URLs\n")
                f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                for failed_item in self.failed_urls:
                    f.write(f"{failed_item['url']}\n")
                    f.write(f"# Error: {failed_item['error']}\n\n")

            logger.info(f"💾 Failed URLs saved to: {failed_urls_file}")
            return failed_urls_file

        except Exception as e:
            logger.error(f"Failed to save failed URLs file: {e}")
            return None
