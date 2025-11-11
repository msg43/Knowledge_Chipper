"""Audio transcription tab for processing audio and video files using Whisper."""

import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...config import get_valid_whisper_models
from ...logger import get_logger
from ...utils.cancellation import CancellationError
from ..components.base_tab import BaseTab
from ..components.completion_summary import TranscriptionCompletionSummary
from ..components.enhanced_error_dialog import show_enhanced_error
from ..components.file_operations import FileOperationsMixin

# Removed rich log display import - using main output_text area instead
from ..core.settings_manager import get_gui_settings_manager
from ..widgets.cookie_file_manager import CookieFileManager

logger = get_logger(__name__)


class EnhancedTranscriptionWorker(QThread):
    """Enhanced worker thread for transcription with real-time progress."""

    progress_updated = pyqtSignal(object)  # Progress object
    file_completed = pyqtSignal(int, int)  # current, total
    processing_finished = pyqtSignal(
        int, int, list
    )  # completed_count, failed_count, failed_files_details
    processing_error = pyqtSignal(str)
    transcription_step_updated = pyqtSignal(
        str, int
    )  # step_description, progress_percent
    total_files_determined = pyqtSignal(int)  # total_files_count
    speaker_assignment_requested = pyqtSignal(
        object, str, object, str
    )  # speaker_data_list, recording_path, metadata, task_id
    log_message = pyqtSignal(str)  # Log messages from processing pipeline
    existing_audio_decision_requested = pyqtSignal(dict)

    def __init__(
        self, files: Any, settings: Any, gui_settings: Any, parent: Any = None
    ) -> None:
        super().__init__(parent)
        self.files = files
        self.settings = settings
        self.gui_settings = gui_settings
        self.should_stop = False
        self._speaker_assignment_result = None
        self._speaker_assignment_event = None
        self.current_file_index = 0
        self.total_files = len(files)
        self.completed_count = 0
        self.failed_count = 0
        self.failed_urls = []  # Track failed URLs with details
        self.failed_files = []  # Track failed local files with details
        self.successful_files = []  # Track successful files with details
        self.queue_for_retry = (
            []
        )  # Queue for smart retry logic with time-based decision making

        # Create cancellation token for proper stop support
        from ...utils.cancellation import CancellationToken

        self.cancellation_token = CancellationToken()
        self.log_handler = None  # Will be set when processing starts
        self._existing_audio_decision_event = threading.Event()
        self._existing_audio_decision_response = True

    def _transcription_progress_callback(
        self, step_description_or_dict: Any, progress_percent: int | None = None
    ) -> None:
        """Callback to emit real-time transcription progress."""
        # Handle both string step descriptions and model download dictionaries
        if isinstance(step_description_or_dict, dict):
            # This is a model download progress update
            progress_dict = step_description_or_dict
            status = progress_dict.get("status", "unknown")
            model = progress_dict.get("model", "model")

            if status == "starting_download":
                message = progress_dict.get(
                    "message", f"Starting download of {model} model..."
                )
                self.transcription_step_updated.emit(f"📥 {message}", 0)
            elif status == "downloading":
                percent = progress_dict.get("percent", 0)
                speed_mbps = progress_dict.get("speed_mbps", 0)
                downloaded_mb = progress_dict.get("downloaded_mb", 0)
                total_mb = progress_dict.get("total_mb", 0)
                message = f"Downloading {model} model: {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB @ {speed_mbps:.1f} MB/s)"
                self.transcription_step_updated.emit(f"📥 {message}", int(percent))
            elif status == "download_complete":
                message = progress_dict.get(
                    "message", f"Successfully downloaded {model} model"
                )
                self.transcription_step_updated.emit(f"✅ {message}", 100)
            else:
                # Generic progress message
                message = progress_dict.get("message", f"Model {model}: {status}")
                self.transcription_step_updated.emit(
                    f"🔄 {message}",
                    progress_percent if progress_percent is not None else 0,
                )
        else:
            # This is a regular string step description
            # If progress is None, use -1 as a sentinel to indicate "progress unknown but working"
            self.transcription_step_updated.emit(
                step_description_or_dict,
                progress_percent if progress_percent is not None else -1,
            )

    def _speaker_assignment_callback(
        self, speaker_data_list, recording_path, metadata=None
    ):
        """
        Non-blocking callback for speaker assignment requests from worker thread.
        Emits a signal to the main thread to show the dialog but does NOT wait.
        """
        # Extract task_id if provided
        task_id = metadata.get("task_id") if metadata else None

        # Emit to main thread to show dialog (non-blocking)
        self.speaker_assignment_requested.emit(
            speaker_data_list,
            recording_path,
            metadata,
            task_id,  # Pass task_id for tracking
        )

        # Return immediately - don't wait for result
        logger.info(
            f"Speaker assignment dialog queued for {recording_path}. "
            f"Processing continues without blocking."
        )
        return None  # Non-blocking - assignment will be handled asynchronously

    @pyqtSlot(bool)
    def set_existing_audio_decision(self, decision: bool) -> None:
        """Receive the user's decision about reusing existing audio."""

        self._existing_audio_decision_response = decision
        self._existing_audio_decision_event.set()

    def _await_existing_audio_decision(self, payload: dict) -> bool:
        """Emit decision request to main thread and block until resolved."""

        self._existing_audio_decision_event.clear()
        self._existing_audio_decision_response = True
        self.existing_audio_decision_requested.emit(payload)
        self._existing_audio_decision_event.wait()
        return self._existing_audio_decision_response

    def _apply_youtube_delay(self, median_delay: int, is_first: bool = False):
        """Apply randomized delay between YouTube downloads."""
        import random
        import time

        if is_first or median_delay == 0:
            return  # No delay for first video or if delay is 0

        # Randomize ±30%
        min_delay = median_delay * 0.7
        max_delay = median_delay * 1.3
        actual_delay = random.uniform(min_delay, max_delay)

        self.transcription_step_updated.emit(
            f"⏱️ Waiting {actual_delay:.1f}s before next download (avoiding bot detection)...",
            0,
        )
        logger.info(
            f"Applying delay: {actual_delay:.1f}s (median: {median_delay}s, range: {min_delay:.1f}-{max_delay:.1f}s)"
        )
        time.sleep(actual_delay)

    def _get_error_guidance(self, error_msg: str) -> str:
        """Get user-friendly guidance for specific error types."""
        # Use the centralized YouTube error handler for consistent categorization
        from ...utils.error_handling import YouTubeErrorHandler

        # Get categorized error message from the centralized handler
        categorized_error = YouTubeErrorHandler.categorize_youtube_error(error_msg)

        # If it's the generic fallback, provide additional guidance
        if (
            "❌ Error processing" in categorized_error
            or "❌ YouTube processing error" in categorized_error
        ):
            error_lower = error_msg.lower()

            if "503" in error_msg or "service unavailable" in error_lower:
                return "Proxy unavailable - check Settings or disable proxy checkbox"
            elif "sign in to confirm" in error_lower or "bot" in error_lower:
                return "Bot detected - increase delay between downloads or use proxy"
            elif "requested format is not available" in error_lower:
                return "Format unavailable - video may be restricted or deleted"
            elif "private video" in error_lower or "members-only" in error_lower:
                return "Video requires authentication - cannot download"
            elif "video unavailable" in error_lower:
                return "Video not accessible - may be deleted or region-locked"
            else:
                return "Check PacketStream config or try increasing download delay"
        else:
            # Use the categorized error message (removes URL for cleaner display)
            return categorized_error.replace(
                f" ({error_msg.split('=')[-1] if '=' in error_msg else ''})", ""
            )

    def _download_single_url(
        self,
        url: str,
        idx: int,
        total: int,
        downloader,
        downloads_dir,
        youtube_delay: int,
        is_first: bool = False,
    ):
        """Download a single YouTube URL with retry logic and delays.

        This is designed to be called from ThreadPoolExecutor for parallel downloads.
        Returns tuple of (url, audio_file_path, success, error_message).
        """
        try:
            # Apply delay before download (except first in batch)
            if not is_first and youtube_delay > 0:
                # Get rate limiting settings from config
                from ...config import get_settings

                settings = get_settings()
                yt_config = settings.youtube_processing

                # Use new rate limiting settings if available
                min_delay = yt_config.sequential_download_delay_min
                max_delay = yt_config.sequential_download_delay_max
                randomization = yt_config.delay_randomization_percent / 100.0

                # Calculate base delay and apply randomization
                base_delay = random.uniform(min_delay, max_delay)
                jitter = base_delay * randomization
                actual_delay = base_delay + random.uniform(-jitter, jitter)
                actual_delay = max(0, actual_delay)  # Ensure non-negative

                logger.info(
                    f"⏱️ [{idx}/{total}] Rate limiting: waiting {actual_delay:.1f}s before {url[:40]}..."
                )
                self.progress_updated.emit(
                    {
                        "message": f"⏱️ Rate limiting: waiting {actual_delay:.1f}s before next download...",
                        "percent": 0,
                    }
                )
                time.sleep(actual_delay)

            # Retry logic for this download
            max_retries = 3
            retry_count = 0
            last_error = None

            while retry_count < max_retries and not self.should_stop:
                try:
                    attempt_msg = (
                        f" (attempt {retry_count + 1}/{max_retries})"
                        if retry_count > 0
                        else ""
                    )

                    # Calculate progress range for this file
                    # Downloads occupy 20-90% of total progress
                    # Each file gets an equal portion of that range
                    download_range_start = 20 + ((idx - 1) / total) * 70
                    download_range_size = 70 / total

                    # Start at beginning of this file's range
                    self.transcription_step_updated.emit(
                        f"📥 [{idx}/{total}] Downloading{attempt_msg}...",
                        int(download_range_start),
                    )

                    # Import and pass database service for partial download tracking
                    from ...database.service import DatabaseService

                    db_service = DatabaseService()

                    # Create progress callback that maps download % to allocated range
                    def download_progress_callback(message: str, percent: int = 0):
                        """Map download progress (0-100%) to this file's allocated range."""
                        if percent > 0:
                            # Map 0-100% download progress to this file's range
                            mapped_progress = download_range_start + (
                                percent / 100 * download_range_size
                            )
                            self.transcription_step_updated.emit(
                                message, int(mapped_progress)
                            )
                        else:
                            # Just emit the message
                            self.transcription_step_updated.emit(
                                message, int(download_range_start)
                            )

                    result = downloader.process(
                        url,
                        output_dir=downloads_dir,
                        db_service=db_service,
                        progress_callback=download_progress_callback,
                        cancellation_token=self.cancellation_token,
                    )

                    reuse_records = []
                    if result.metadata:
                        reuse_records = (
                            result.metadata.get("reused_existing_audio", []) or []
                        )
                    if not reuse_records and result.data:
                        reuse_records = (
                            result.data.get("reused_existing_audio", []) or []
                        )

                    if reuse_records:
                        reuse_info = reuse_records[0]
                        decision_payload = {
                            "url": url,
                            "file_path": reuse_info.get("path"),
                            "size_bytes": reuse_info.get("size_bytes"),
                            "source_id": reuse_info.get("source_id"),
                        }
                        use_existing = self._await_existing_audio_decision(
                            decision_payload
                        )

                        if not use_existing:
                            self.transcription_step_updated.emit(
                                "♻️ Re-downloading to replace existing audio...",
                                int(download_range_start),
                            )
                            result = downloader.process(
                                url,
                                output_dir=downloads_dir,
                                db_service=db_service,
                                progress_callback=download_progress_callback,
                                cancellation_token=self.cancellation_token,
                                allow_existing_audio=False,
                                force_redownload=True,
                            )

                    if result.success and result.data.get("downloaded_files"):
                        audio_file = result.data["downloaded_files"][0]
                        logger.info(f"✅ [{idx}/{total}] Downloaded: {url}")
                        # Report end of this file's download range
                        download_range_end = 20 + (idx / total) * 70
                        self.transcription_step_updated.emit(
                            f"✅ [{idx}/{total}] Downloaded successfully",
                            int(download_range_end),
                        )
                        return (url, audio_file, True, None)
                    else:
                        # Debug: Log the result details
                        logger.error(
                            f"[{idx}/{total}] Download result check failed - "
                            f"success={result.success}, "
                            f"downloaded_files={result.data.get('downloaded_files', [])}, "
                            f"errors={result.errors}"
                        )
                        last_error = (
                            result.errors[0] if result.errors else "Unknown error"
                        )

                        # Check for retryable errors
                        if "503" in last_error or "Service Unavailable" in last_error:
                            retry_count += 1
                            if retry_count < max_retries:
                                backoff = 2**retry_count
                                self.transcription_step_updated.emit(
                                    f"⚠️ [{idx}/{total}] Proxy unavailable (503), retrying in {backoff}s...",
                                    0,
                                )
                                time.sleep(backoff)
                        elif (
                            "502" in last_error
                            or "Proxy Error" in last_error
                            or "relay is offline" in last_error
                        ):
                            # Proxy server issue (PacketStream relay offline/overloaded) - retry with new IP
                            retry_count += 1
                            if retry_count < max_retries:
                                backoff = 2**retry_count
                                self.transcription_step_updated.emit(
                                    f"⚠️ [{idx}/{total}] Proxy relay offline, retrying with new IP in {backoff}s...",
                                    0,
                                )
                                time.sleep(backoff)
                            else:
                                logger.error(
                                    f"[{idx}/{total}] Proxy relay failed after {max_retries} attempts"
                                )
                                break
                        elif "Sign in to confirm" in last_error or (
                            "bot" in last_error.lower()
                            and "not a bot" in last_error.lower()
                        ):
                            # Bot detection - RETRY with different IP (might get clean IP)
                            retry_count += 1
                            if retry_count < max_retries:
                                backoff = 2**retry_count
                                logger.warning(
                                    f"[{idx}/{total}] Bot detection (burned IP), retrying with new IP in {backoff}s..."
                                )
                                self.transcription_step_updated.emit(
                                    f"⚠️ [{idx}/{total}] IP flagged by YouTube, retrying with new IP in {backoff}s...",
                                    0,
                                )
                                time.sleep(backoff)
                            else:
                                logger.error(
                                    f"[{idx}/{total}] Bot detection on all {max_retries} IPs for {url}"
                                )
                                self.transcription_step_updated.emit(
                                    f"❌ [{idx}/{total}] All IPs flagged by YouTube", 0
                                )
                                break
                        elif "Requested format is not available" in last_error:
                            # Format issue - not retryable
                            retry_count += 1
                            logger.error(
                                f"[{idx}/{total}] Format unavailable for {url}"
                            )
                            break
                        elif (
                            "Unable to connect to proxy" in last_error
                            or "Tunnel connection failed" in last_error
                        ):
                            # Proxy connection issue - retry with new IP
                            retry_count += 1
                            if retry_count < max_retries:
                                backoff = 2**retry_count
                                self.transcription_step_updated.emit(
                                    f"⚠️ [{idx}/{total}] Proxy connection failed, retrying with new IP in {backoff}s...",
                                    0,
                                )
                                time.sleep(backoff)
                            else:
                                logger.error(
                                    f"[{idx}/{total}] Proxy connection failed after {max_retries} attempts"
                                )
                                break
                        else:
                            # Unknown error - retry anyway (might be transient)
                            retry_count += 1
                            if retry_count < max_retries:
                                backoff = 2**retry_count
                                logger.warning(
                                    f"[{idx}/{total}] Unknown error, retrying in {backoff}s: {last_error[:100]}"
                                )
                                self.transcription_step_updated.emit(
                                    f"⚠️ [{idx}/{total}] Retrying in {backoff}s...", 0
                                )
                                time.sleep(backoff)
                            else:
                                logger.error(
                                    f"[{idx}/{total}] Download failed for {url}: {last_error}"
                                )
                                break

                except Exception as e:
                    last_error = str(e)
                    logger.error(f"[{idx}/{total}] Exception downloading {url}: {e}")
                    retry_count += 1
                    if retry_count < max_retries:
                        backoff = 2**retry_count
                        self.transcription_step_updated.emit(
                            f"⚠️ [{idx}/{total}] Error, retrying in {backoff}s...", 0
                        )
                        time.sleep(backoff)

            # All retries exhausted
            error_guidance = self._get_error_guidance(last_error or "Unknown error")
            self.transcription_step_updated.emit(
                f"❌ [{idx}/{total}] Failed: {url[:40]}... - {error_guidance}", 0
            )
            logger.error(
                f"[{idx}/{total}] Failed to download after {retry_count} attempts: {url}"
            )

            # Track failed URL with full details
            self.failed_urls.append(
                {
                    "url": url,
                    "error": last_error or "Unknown error",
                    "error_guidance": error_guidance,
                    "index": idx,
                }
            )

            return (url, None, False, last_error or "Unknown error")

        except Exception as e:
            logger.error(
                f"[{idx}/{total}] Fatal error in _download_single_url for {url}: {e}"
            )

            # Track fatal error
            self.failed_urls.append(
                {
                    "url": url,
                    "error": str(e),
                    "error_guidance": "Fatal error during download",
                    "index": idx,
                }
            )

            return (url, None, False, str(e))

    def _handle_failed_url(self, url: str, error: str, db_service):
        """
        Handle a failed URL with sophisticated retry logic.

        Each URL gets up to 6 different residential IPs:
        - Initial attempt: 3 IPs (worker-level retries)
        - One requeue: 3 more IPs (kicked to back of queue)
        - Total: 6 different IPs

        Decision tree:
        1. If this is first failure (retry_count == 0 or no record):
           - Record first_failure_at timestamp
           - Add to end of queue for retry (retry_count = 1)
           - When retried: Gets 3 NEW IPs

        2. If retry_count == 1 and time since first_failure_at < 10 minutes:
           - Permanent failure (already tried 6 different IPs)
           - Write to failed_urls_TIMESTAMP.txt

        3. If time since first_failure_at >= 10 minutes:
           - Perform fresh 3-retry attempt with new IPs (already done by YouTubeDownloadProcessor)
           - If still fails, write to failed_urls_TIMESTAMP.txt

        Returns:
            str: "REQUEUE" if URL should be retried, "PERMANENT_FAILURE" if failed permanently
        """
        from datetime import datetime, timedelta

        try:
            # Get or create video record from database
            from ...utils.video_id_extractor import VideoIDExtractor

            source_id = VideoIDExtractor.extract_video_id(url)

            if not source_id:
                logger.warning(
                    f"Could not extract video ID from {url} - treating as permanent failure"
                )
                self._write_to_failed_urls_file(url, error)
                return "PERMANENT_FAILURE"

            video = db_service.get_source(source_id)
            current_time = datetime.now()

            if not video or video.retry_count == 0:
                # CASE 1: First failure - record timestamp and re-queue
                if video:
                    # Update existing record
                    video.first_failure_at = current_time
                    video.retry_count = 1
                    video.last_retry_at = current_time
                    video.failure_reason = error
                    video.needs_metadata_retry = True
                    db_service.update_source(video)
                else:
                    # Create new record for retry tracking
                    db_service.create_source(
                        source_id=source_id,
                        title=f"Retry: {url[:50]}",
                        source_url=url,
                        source_type="youtube",
                        status="failed",
                        first_failure_at=current_time,
                        retry_count=1,
                        last_retry_at=current_time,
                        failure_reason=error,
                        needs_metadata_retry=True,
                    )

                # Add to end of queue
                self.queue_for_retry.append(url)
                logger.info(
                    f"📋 First failure for {url[:50]} - added to end of queue (retry_count=1)"
                )
                self.transcription_step_updated.emit(
                    f"📋 Will retry {url[:40]}... later in queue", 0
                )
                return "REQUEUE"

            # Calculate time since first failure
            time_since_first_failure_minutes = 0
            if video.first_failure_at:
                time_since_first_failure = current_time - video.first_failure_at
                time_since_first_failure_minutes = (
                    time_since_first_failure.total_seconds() / 60
                )

            if time_since_first_failure_minutes < 10:
                # Still within 10 minute window
                if video.retry_count == 1:
                    # CASE 2: Second failure within 10 minutes - permanent failure
                    # We've already tried with 3 IPs initially + 3 IPs on requeue = 6 total IPs
                    logger.error(
                        f"❌ Permanent failure for {url[:50]} after retry (6 total IP attempts, {time_since_first_failure_minutes:.1f}m since first)"
                    )
                    video.retry_count = 2
                    video.max_retries_exceeded = True
                    video.failure_reason = error
                    db_service.update_video(video)

                    self._write_to_failed_urls_file(url, error)
                    self.transcription_step_updated.emit(
                        f"❌ {url[:40]}... failed after 6 IP attempts", 0
                    )
                    return "PERMANENT_FAILURE"
                else:
                    # CASE 3: Should not reach here, but handle gracefully
                    logger.error(
                        f"❌ Unexpected retry state for {url[:50]} (retry_count={video.retry_count})"
                    )
                    video.max_retries_exceeded = True
                    video.failure_reason = error
                    db_service.update_video(video)

                    self._write_to_failed_urls_file(url, error)
                    self.transcription_step_updated.emit(
                        f"❌ {url[:40]}... failed permanently", 0
                    )
                    return "PERMANENT_FAILURE"
            else:
                # CASE 4: More than 10 minutes - fresh 3-retry already attempted by YouTubeDownloadProcessor
                # If we're here, it means the fresh retry also failed
                logger.error(
                    f"❌ Permanent failure for {url[:50]} after fresh retry ({time_since_first_failure_minutes:.1f}m since first failure)"
                )
                video.max_retries_exceeded = True
                video.failure_reason = error
                db_service.update_video(video)

                self._write_to_failed_urls_file(url, error)
                self.transcription_step_updated.emit(
                    f"❌ {url[:40]}... failed after fresh retry", 0
                )
                return "PERMANENT_FAILURE"

        except Exception as e:
            logger.error(f"Error in _handle_failed_url for {url}: {e}")
            # On error, treat as permanent failure
            self._write_to_failed_urls_file(url, error)
            return "PERMANENT_FAILURE"

    def _write_to_failed_urls_file(self, url: str, error: str):
        """
        Write permanently failed URL to a timestamped file for manual retry later.

        Format: logs/failed_urls_TIMESTAMP.txt
        """
        try:
            from datetime import datetime
            from pathlib import Path

            from ...config import get_settings

            settings = get_settings()
            logs_dir = Path(settings.paths.logs).expanduser()
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Use timestamped filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            failed_file_path = logs_dir / f"failed_urls_{timestamp}.txt"

            # Append to file (or create if doesn't exist)
            with open(failed_file_path, "a", encoding="utf-8") as f:
                f.write(f"{url}\n")
                f.write(f"# Error: {error}\n")
                f.write(f"# Timestamp: {datetime.now().isoformat()}\n\n")

            logger.info(f"💾 Saved failed URL to: {failed_file_path}")

        except Exception as e:
            logger.error(f"Failed to write failed URL to file: {e}")

    def _download_urls(
        self,
        urls: list[str],
        cookie_files: list[str],
        downloads_dir: Path,
    ) -> list[Path]:
        """
        Download URLs using unified download path with optional YouTube-to-RSS mapping.

        Handles 0, 1, or multiple cookie files with consistent behavior:
        - 0 cookies: No authentication, safe rate limiting
        - 1 cookie: Single scheduler with deduplication and failover
        - 2+ cookies: Parallel schedulers with load distribution

        RSS Mapping: When enabled, automatically maps YouTube URLs to podcast RSS feeds,
        downloading from RSS (no rate limiting) and falling back to YouTube.
        """
        import asyncio

        from ...config import get_settings
        from ...database.service import DatabaseService
        from ...services.unified_download_orchestrator import (
            UnifiedDownloadOrchestrator,
        )

        # Handle no cookies case
        if not cookie_files:
            logger.info("📥 No cookies provided - downloading without authentication")
            cookie_files = []  # Empty list for orchestrator

        # Test and filter cookies (skips None values)
        if cookie_files:
            self.transcription_step_updated.emit("🧪 Testing cookie files...", 0)
            valid_cookies = self._test_and_filter_cookies(cookie_files)

            if not valid_cookies:
                raise Exception("No valid cookie files found")

            cookie_files = valid_cookies

            if len(cookie_files) == 1:
                self.transcription_step_updated.emit(
                    f"✅ Using 1 account for downloads\n"
                    f"   Rate limiting: 3-5 min delays for safety",
                    0,
                )
            else:
                self.transcription_step_updated.emit(
                    f"✅ Using {len(cookie_files)} account(s) for downloads\n"
                    f"   Expected speedup: {len(cookie_files)}x faster than single account",
                    0,
                )

        # Create progress callback
        def progress_callback(message):
            self.transcription_step_updated.emit(message, 0)

        # Create database service
        db_service = DatabaseService()

        # Get RSS mapping setting from gui_settings (default to False if not set)
        enable_rss_mapping = self.gui_settings.get("enable_rss_mapping", False)

        # Create unified orchestrator (handles RSS + YouTube)
        orchestrator = UnifiedDownloadOrchestrator(
            youtube_urls=urls,
            cookie_files=cookie_files if cookie_files else [],
            output_dir=downloads_dir,
            db_service=db_service,
            progress_callback=progress_callback,
            enable_rss_mapping=enable_rss_mapping,
        )

        # Run unified orchestrator (RSS + YouTube in parallel)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Returns: [(audio_file_path, source_id), ...]
            files_with_source_ids = loop.run_until_complete(orchestrator.process_all())

            # Ensure MediaSource records exist with audio_file_path
            # (This is now handled by the download processors, but we verify here)
            for audio_file, source_id in files_with_source_ids:
                self._ensure_source_record_has_file_path(audio_file, source_id)

            # Extract just file paths for return
            downloaded_files = [Path(path) for path, _ in files_with_source_ids]

            self.transcription_step_updated.emit(
                f"✅ Download complete: {len(downloaded_files)} files ready for transcription",
                0,
            )

        finally:
            loop.close()

        return downloaded_files

    def _ensure_source_record_has_file_path(
        self, audio_file: Path, source_id: str
    ) -> None:
        """
        Ensure MediaSource record has audio_file_path set.

        This is the database-centric approach that replaces sidecar files.
        The transcription pipeline will use get_source_by_file_path() to
        look up the source_id from the audio file path.

        Args:
            audio_file: Path to audio file
            source_id: Source ID for this file
        """
        from ...database.service import DatabaseService

        try:
            db_service = DatabaseService()

            # Check if source exists
            source = db_service.get_source(source_id)

            if source:
                # Update audio_file_path if not set or different
                if source.audio_file_path != str(audio_file):
                    db_service.update_source(
                        source_id=source_id, audio_file_path=str(audio_file)
                    )
                    logger.debug(
                        f"Updated audio_file_path for {source_id}: {audio_file.name}"
                    )
            else:
                # Create minimal source record if it doesn't exist
                # (This shouldn't happen if download processors work correctly)
                logger.warning(f"Source {source_id} not found, creating minimal record")
                db_service.create_source(
                    source_id=source_id,
                    title=audio_file.stem,  # Use filename as title
                    url="",  # Will be filled in later
                    source_type="unknown",
                    audio_file_path=str(audio_file),
                )

        except Exception as e:
            logger.error(f"Failed to ensure source record for {source_id}: {e}")

    def _test_and_filter_cookies(self, cookie_files: list[str]) -> list[str]:
        """Test cookie files and return only valid ones"""
        from http.cookiejar import MozillaCookieJar

        valid_cookies = []

        for idx, cookie_file in enumerate(cookie_files):
            try:
                # Test cookie file
                jar = MozillaCookieJar(cookie_file)
                jar.load(ignore_discard=True, ignore_expires=True)

                youtube_cookies = [
                    c
                    for c in jar
                    if "youtube.com" in c.domain or "google.com" in c.domain
                ]

                if youtube_cookies:
                    valid_cookies.append(cookie_file)
                    self.transcription_step_updated.emit(
                        f"✅ Account {idx+1}: Valid ({len(youtube_cookies)} cookies)", 0
                    )
                else:
                    self.transcription_step_updated.emit(
                        f"❌ Account {idx+1}: No YouTube cookies found", 0
                    )

            except Exception as e:
                self.transcription_step_updated.emit(
                    f"❌ Account {idx+1}: Invalid ({str(e)[:50]})", 0
                )

        return valid_cookies

    def run(self) -> None:
        """Run the transcription process with real-time progress tracking."""
        # Install GUI log handler to capture processing logs
        from ..utils.gui_log_handler import install_gui_log_handler

        # Capture logs from transcription processors and related modules
        logger_names = [
            "knowledge_system.processors.whisper_cpp_transcribe",
            "knowledge_system.processors.youtube_download",
            "knowledge_system.processors.audio_processor",
            "knowledge_system.processors.speaker_diarization",
            "knowledge_system.services.speaker_learning_service",
        ]

        try:
            self.log_handler = install_gui_log_handler(
                callback=self._handle_log_message,
                logger_names=logger_names,
                level=20,  # INFO level
            )

            self._run_transcription()

        finally:
            # Remove log handler when done
            if self.log_handler:
                from ..utils.gui_log_handler import remove_gui_log_handler

                remove_gui_log_handler(self.log_handler, logger_names)
                self.log_handler = None

    def _handle_log_message(self, message: str) -> None:
        """Handle log messages from the processing pipeline.

        Args:
            message: The log message to handle
        """
        # Emit the log message signal
        self.log_message.emit(message)

    def _run_transcription(self) -> None:
        """Internal method to run transcription with logging already set up."""
        try:
            from ...processors.audio_processor import AudioProcessor
            from ...processors.youtube_download import YouTubeDownloadProcessor
            from ...utils.youtube_utils import expand_playlist_urls_with_metadata

            # Handle URLs if provided - download them first
            urls = self.gui_settings.get("urls", [])
            downloaded_files = []

            if urls:
                self.transcription_step_updated.emit(
                    f"📥 Processing {len(urls)} URL(s)...", 0
                )

                # Expand playlists
                expansion_result = expand_playlist_urls_with_metadata(urls)
                expanded_urls = expansion_result["expanded_urls"]

                if expanded_urls:
                    self.transcription_step_updated.emit(
                        f"📥 Downloading {len(expanded_urls)} video(s)...", 10
                    )

                    output_dir = self.gui_settings.get("output_dir")
                    downloads_dir = Path(output_dir) / "downloads"
                    downloads_dir.mkdir(parents=True, exist_ok=True)

                    # Get cookie settings from GUI
                    enable_cookies = self.gui_settings.get("enable_cookies", True)
                    cookie_files = self.gui_settings.get("cookie_files", [])
                    use_multi_account = self.gui_settings.get(
                        "use_multi_account", False
                    )
                    disable_proxies_with_cookies = self.gui_settings.get(
                        "disable_proxies_with_cookies", True
                    )

                    # Log cookie configuration for debugging
                    logger.info(f"🍪 Cookie configuration:")
                    logger.info(f"   enable_cookies: {enable_cookies}")
                    logger.info(f"   cookie_files: {cookie_files}")
                    logger.info(f"   use_multi_account: {use_multi_account}")
                    logger.info(
                        f"   disable_proxies_with_cookies: {disable_proxies_with_cookies}"
                    )

                    # Use unified download path for all cases (0, 1, or multiple cookies)
                    logger.info(
                        f"   Using unified download path with {len(cookie_files)} cookie(s)"
                    )
                    downloaded_files = self._download_urls(
                        expanded_urls, cookie_files, downloads_dir
                    )

            # Combine downloaded files with local files
            all_files = list(self.files) + downloaded_files

            # Update total files count to include expanded URLs
            self.total_files = len(all_files)

            # Notify UI that total files count has been determined
            self.total_files_determined.emit(self.total_files)

            # Check if we have any files to process
            if len(all_files) == 0:
                # No files to process - emit completion immediately
                logger.info("No files to process (all downloads may have failed)")

                # Show failed downloads summary if any
                if self.failed_urls:
                    self.transcription_step_updated.emit(
                        f"\n{'='*60}\n📋 FAILED DOWNLOADS SUMMARY ({len(self.failed_urls)} URLs)\n{'='*60}",
                        0,
                    )
                    for failed_item in self.failed_urls:
                        self.transcription_step_updated.emit(
                            f"❌ [{failed_item['index']}] {failed_item['url']}", 0
                        )
                        self.transcription_step_updated.emit(
                            f"   Error: {failed_item['error_guidance']}", 0
                        )

                    # Save failed URLs to file for easy retry
                    try:
                        output_dir = self.gui_settings.get("output_dir")
                        if output_dir:
                            failed_urls_file = Path(output_dir) / "failed_downloads.txt"
                            with open(failed_urls_file, "w") as f:
                                f.write(
                                    f"# Failed YouTube Downloads - {len(self.failed_urls)} URLs\n"
                                )
                                f.write(
                                    f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                )
                                for failed_item in self.failed_urls:
                                    f.write(f"{failed_item['url']}\n")
                                    f.write(
                                        f"# Error: {failed_item['error_guidance']}\n\n"
                                    )

                            self.transcription_step_updated.emit(
                                f"💾 Failed URLs saved to: {failed_urls_file}", 0
                            )
                            logger.info(f"Failed URLs saved to: {failed_urls_file}")
                    except Exception as e:
                        logger.error(f"Failed to save failed URLs file: {e}")

                    self.transcription_step_updated.emit(
                        f"{'='*60}\n💡 Tip: Copy URLs above or use saved file to retry\n{'='*60}",
                        0,
                    )
                else:
                    self.transcription_step_updated.emit(
                        "⚠️ No files available for transcription", 0
                    )

                # Combine failed URLs and failed files for comprehensive error reporting
                all_failed_details = []

                # Add failed URLs
                for failed_url in self.failed_urls:
                    all_failed_details.append(
                        {
                            "file": failed_url.get("url", "Unknown URL"),
                            "error": failed_url.get(
                                "error_guidance",
                                failed_url.get("error", "Unknown error"),
                            ),
                        }
                    )

                # Add failed local files
                all_failed_details.extend(self.failed_files)

                # Emit processing finished with failure counts
                self.processing_finished.emit(
                    self.completed_count, self.failed_count, all_failed_details
                )
                return

            # Create processor with GUI settings - filter out conflicting diarization parameter
            kwargs = self.gui_settings.get("kwargs", {})
            # Extract diarization setting and pass it as enable_diarization
            # Check for testing mode and disable diarization if needed
            import os

            testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"
            if testing_mode:
                logger.info("🧪 Testing mode detected in worker - disabling diarization")
            # For local transcription, default to False to prevent unwanted speaker dialogs
            enable_diarization = kwargs.get("diarization", False) and not testing_mode

            # Log the diarization setting for debugging
            logger.info(
                f"✅ Local transcription diarization setting: {enable_diarization}"
            )

            # Valid AudioProcessor constructor parameters
            valid_audio_processor_params = {
                "normalize_audio",
                "target_format",
                "device",
                "temp_dir",
                "use_whisper_cpp",
                "model",
                "progress_callback",
                "enable_diarization",
                "hf_token",
                "require_diarization",
            }

            # Filter kwargs to only include valid AudioProcessor constructor parameters
            audio_processor_kwargs = {}
            processing_kwargs = {}

            for k, v in kwargs.items():
                if k in valid_audio_processor_params:
                    audio_processor_kwargs[k] = v
                else:
                    # These will be passed to the .process() method instead
                    processing_kwargs[k] = v

            # Ensure all relevant GUI settings are passed to the process method
            gui_settings_to_pass = [
                "timestamps",
                "language",
                "format",
                "overwrite",
                "output_dir",
                "enable_speaker_assignment",
                "enable_color_coding",
            ]

            for setting in gui_settings_to_pass:
                if setting in self.gui_settings:
                    processing_kwargs[setting] = self.gui_settings[setting]

            # Add progress callback to processor with timeout protection
            try:
                self.transcription_step_updated.emit(
                    "🔧 Initializing transcription engine...", 5
                )

                # Get preloaded models from the tab if available
                preloaded_transcriber = None
                preloaded_diarizer = None

                if hasattr(self.parent(), "model_preloader"):
                    (
                        preloaded_transcriber,
                        preloaded_diarizer,
                    ) = self.parent().model_preloader.get_preloaded_models()
                    if preloaded_transcriber:
                        logger.info("🚀 Using preloaded transcription model")
                    if preloaded_diarizer:
                        logger.info("🚀 Using preloaded diarization model")

                # Create DatabaseService once for all transcriptions in this batch
                from ...database.service import DatabaseService

                db_service = DatabaseService()

                processor = AudioProcessor(
                    model=self.gui_settings["model"],
                    device=self.gui_settings["device"],
                    enable_diarization=enable_diarization,
                    require_diarization=enable_diarization,  # Strict mode: if diarization enabled, require it
                    progress_callback=self._transcription_progress_callback,
                    speaker_assignment_callback=self._speaker_assignment_callback,
                    preloaded_transcriber=preloaded_transcriber,
                    preloaded_diarizer=preloaded_diarizer,
                    db_service=db_service,
                    **audio_processor_kwargs,
                )

                # Store processor reference for subprocess termination
                self.audio_processor = processor

                self.transcription_step_updated.emit("✅ Transcription engine ready", 10)

            except Exception as e:
                error_msg = f"Failed to initialize transcription engine: {str(e)}"
                logger.error(error_msg)
                self.transcription_step_updated.emit(f"❌ {error_msg}", 0)
                self.processing_error.emit(error_msg)
                return

            self.total_files = len(all_files)

            for i, file_path in enumerate(all_files):
                if self.should_stop:
                    break

                self.current_file_index = i
                file_name = Path(file_path).name

                # Emit file start progress
                self.transcription_step_updated.emit(
                    f"Starting transcription of {file_name}...", 0
                )
                self.file_completed.emit(i, self.total_files)

                try:
                    # Pass processing parameters (like omp_threads, batch_size, output_dir) to the process method
                    # Include output_dir for markdown file generation
                    processing_kwargs_with_output = processing_kwargs.copy()

                    # REQUIRE: Always ensure output_dir is set for file saving
                    # User must have specified an output directory
                    output_dir = self.gui_settings.get("output_dir")
                    if not output_dir or not output_dir.strip():
                        # This should be caught by validation, but just in case
                        raise ValueError(
                            "Output directory is required but was not specified"
                        )

                    processing_kwargs_with_output["output_dir"] = output_dir

                    # Check if this is a YouTube video and retrieve metadata from database
                    # This enables rich metadata in the markdown output (tags, uploader, etc.)
                    try:
                        from ...database.service import DatabaseService
                        from ...utils.youtube_utils import extract_video_id

                        # Try to retrieve metadata from database
                        # Strategy 1: Look up by file path (DATABASE-CENTRIC - preferred!)
                        # Strategy 2: Extract source_id from filename (fallback for old files)
                        file_path_obj = Path(file_path)
                        filename = file_path_obj.stem

                        logger.debug(f"🔍 Looking up metadata for file: {filename}")

                        db_service = DatabaseService()
                        video_record = None
                        source_id = None

                        # Strategy 1: Try to find by file path in database (DATABASE-CENTRIC!)
                        # This is the correct architecture - no filename parsing needed
                        logger.debug(
                            f"   Strategy 1: Querying database by file path..."
                        )
                        source_record = db_service.get_source_by_file_path(file_path)
                        if source_record:
                            source_id = source_record.source_id
                            logger.info(
                                f"✅ Found metadata by file path (database-centric): {source_id}"
                            )
                        else:
                            logger.debug(
                                f"   No match by file path, trying filename extraction..."
                            )

                        # Strategy 2: Extract source_id from filename (fallback for old files)
                        if not source_record:
                            logger.debug(
                                f"   Strategy 2: Extracting source_id from filename..."
                            )
                            # YouTube video IDs are 11 characters: [a-zA-Z0-9_-]{11}
                            import re

                            # Try multiple patterns in order of likelihood
                            patterns = [
                                r"_([a-zA-Z0-9_-]{11})_transcript",  # Title_videoID_transcript.md
                                r"_([a-zA-Z0-9_-]{11})$",  # Title_videoID.ext
                                r"\[([a-zA-Z0-9_-]{11})\]",  # Title [videoID].ext
                                r"_([a-zA-Z0-9_-]{11})_",  # Title_videoID_anything
                                r"([a-zA-Z0-9_-]{11})",  # videoID anywhere (last resort)
                            ]

                            for pattern in patterns:
                                match = re.search(pattern, filename)
                                if match:
                                    potential_id = match.group(1)
                                    # Verify it's not just random characters by checking database
                                    test_record = db_service.get_source(potential_id)
                                    resolved_source_id = None

                                    if test_record:
                                        resolved_source_id = potential_id
                                    else:
                                        (
                                            exists,
                                            canonical_id,
                                        ) = db_service.source_exists_or_has_alias(
                                            potential_id
                                        )
                                        if exists and canonical_id:
                                            alias_record = db_service.get_source(
                                                canonical_id
                                            )
                                            if alias_record:
                                                test_record = alias_record
                                                resolved_source_id = canonical_id
                                                logger.info(
                                                    f"🔗 Resolved alias {potential_id} → {canonical_id}"
                                                )

                                    if test_record and resolved_source_id:
                                        source_id = resolved_source_id
                                        source_record = test_record
                                        logger.info(
                                            f"✅ Found source_id in filename: {source_id} (pattern: {pattern})"
                                        )
                                        break

                            # Strategy 3: Try URL extraction as fallback
                            if not source_id:
                                try:
                                    source_id = extract_video_id(filename)
                                    if source_id:
                                        source_record = db_service.get_source(source_id)
                                        resolved_source_id = source_id

                                        if not source_record:
                                            (
                                                exists,
                                                canonical_id,
                                            ) = db_service.source_exists_or_has_alias(
                                                source_id
                                            )
                                            if exists and canonical_id:
                                                alias_record = db_service.get_source(
                                                    canonical_id
                                                )
                                                if alias_record:
                                                    source_record = alias_record
                                                    resolved_source_id = canonical_id
                                                    logger.info(
                                                        f"🔗 Resolved alias {source_id} → {canonical_id}"
                                                    )

                                        if source_record and resolved_source_id:
                                            source_id = resolved_source_id
                                            logger.info(
                                                f"✅ Extracted source_id via URL pattern: {source_id}"
                                            )
                                except:
                                    logger.debug(
                                        "Could not extract source_id from URL pattern"
                                    )

                        if not source_record:
                            logger.debug(f"⚠️ No metadata found for file: {filename}")
                            logger.debug(
                                f"   This is normal for local files or files downloaded outside the app"
                            )

                        if source_record:
                            # Retrieve platform metadata from preloaded lists to avoid detached session issues
                            tags = getattr(source_record, "tags_json", None) or []
                            categories = (
                                getattr(source_record, "categories_json", None) or []
                            )

                            # Convert database record to metadata dict for audio processor
                            video_metadata = {
                                "source_id": source_record.source_id,
                                "video_id": source_record.source_id,  # For backward compatibility with markdown template
                                "title": source_record.title,
                                "url": source_record.url,
                                "uploader": source_record.uploader,
                                "uploader_id": source_record.uploader_id,
                                "upload_date": source_record.upload_date,
                                "duration": source_record.duration_seconds,
                                "view_count": source_record.view_count,
                                "tags": tags,
                                "categories": categories,
                                "description": source_record.description,
                                "source_type": source_record.source_type,
                                "thumbnail_local_path": source_record.thumbnail_local_path,
                            }
                            processing_kwargs_with_output[
                                "source_metadata"
                            ] = video_metadata

                            # Debug logging for tags and metadata
                            tags_count = len(video_metadata["tags"])
                            categories_count = len(video_metadata["categories"])
                            has_thumbnail = bool(
                                video_metadata.get("thumbnail_local_path")
                            )
                            has_description = bool(video_metadata.get("description"))
                            logger.info(
                                f"✅ Retrieved YouTube metadata for {source_id}: {source_record.title} "
                                f"(tags: {tags_count}, categories: {categories_count}, "
                                f"thumbnail: {has_thumbnail}, description: {has_description})"
                            )
                            if tags_count > 0:
                                logger.debug(
                                    f"Tags: {video_metadata['tags'][:5]}..."
                                )  # Show first 5 tags
                            if categories_count > 0:
                                logger.debug(
                                    f"Categories: {video_metadata['categories']}"
                                )
                            if has_thumbnail:
                                logger.debug(
                                    f"Thumbnail path: {video_metadata['thumbnail_local_path']}"
                                )
                            if has_description:
                                desc_preview = (
                                    video_metadata["description"][:100] + "..."
                                    if len(video_metadata["description"]) > 100
                                    else video_metadata["description"]
                                )
                                logger.debug(f"Description preview: {desc_preview}")

                    except Exception as e:
                        logger.debug(f"Could not retrieve video metadata: {e}")
                        # Not fatal - continue without metadata

                    # Enable GUI mode for speaker assignment dialog (unless in testing mode)
                    import os

                    # Check multiple ways to detect testing mode
                    testing_mode = (
                        os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"
                        or os.environ.get("QT_MAC_DISABLE_FOREGROUND") == "1"
                        or (
                            hasattr(self, "_testing_mode")
                            and getattr(self, "_testing_mode", False)
                        )
                    )

                    # Log testing mode detection for debugging
                    logger.info(
                        f"🧪 Testing mode detection: env_var={os.environ.get('KNOWLEDGE_CHIPPER_TESTING_MODE', 'NOT_SET')}, "
                        f"qt_env={os.environ.get('QT_MAC_DISABLE_FOREGROUND', 'NOT_SET')}, final={testing_mode}"
                    )

                    if testing_mode:
                        logger.info(
                            "🧪 Testing mode detected - disabling diarization and speaker assignment dialog"
                        )
                        # Disable diarization entirely during testing to prevent speaker dialog
                        enable_diarization = False

                    # CRITICAL: Never enable gui_mode during testing to prevent dialog crashes
                    processing_kwargs_with_output["gui_mode"] = not testing_mode
                    # For local transcription, disable speaker dialog - handle in Speaker Attribution tab only
                    processing_kwargs_with_output["show_speaker_dialog"] = False

                    # Override diarization setting if in testing mode
                    if testing_mode:
                        processing_kwargs_with_output["diarization"] = False
                    processing_kwargs_with_output[
                        "enable_color_coding"
                    ] = self.gui_settings.get(
                        "enable_color_coding", False
                    )  # Default to False

                    # Pass cancellation token for proper stop support
                    processing_kwargs_with_output[
                        "cancellation_token"
                    ] = self.cancellation_token

                    # Pass database service for transcript storage
                    processing_kwargs_with_output["db_service"] = db_service

                    result = processor.process(
                        Path(file_path), **processing_kwargs_with_output
                    )

                    if result.success:
                        # Track successful completion
                        self.completed_count += 1

                        # Get transcription data info
                        transcript_data = result.data
                        text_length = (
                            len(transcript_data.get("text", ""))
                            if transcript_data
                            else 0
                        )

                        # Check if markdown file was saved
                        saved_file = (
                            result.metadata.get("saved_markdown_file")
                            if result.metadata
                            else None
                        )
                        if saved_file:
                            status_msg = f"transcription completed ({text_length:,} characters) - saved to {Path(saved_file).name}"
                            step_msg = f"✅ Transcription of {file_name} completed and saved to {Path(saved_file).name}"
                            logger.info(
                                f"Successfully transcribed and saved: {file_path} -> {saved_file}"
                            )
                        else:
                            status_msg = f"transcription completed ({text_length:,} characters) - WARNING: file not saved"
                            step_msg = f"⚠️ Transcription of {file_name} completed but file was not saved!"
                            logger.warning(
                                f"Transcription succeeded but file not saved for: {file_path}"
                            )

                        # Emit progress update with success
                        progress_data = {
                            "file": file_path,
                            "current": i + 1,
                            "total": self.total_files,
                            "status": status_msg,
                            "success": True,
                            "text_length": text_length,
                            "saved_file": saved_file,
                        }
                        self.progress_updated.emit(progress_data)
                        self.transcription_step_updated.emit(step_msg, 100)

                        # Track successful file with details
                        # Extract source_id from metadata for database-based summarization
                        source_id = (
                            result.metadata.get("database_media_id")
                            if result.metadata
                            else None
                        )
                        self.successful_files.append(
                            {
                                "file": file_name,
                                "text_length": text_length,
                                "saved_to": (
                                    Path(saved_file).name if saved_file else None
                                ),
                                "saved_file_path": saved_file,  # Store full path for summarization tab
                                "source_id": source_id,  # Store source_id for database lookup
                            }
                        )

                        # System 2: Handle auto-process if enabled
                        if (
                            self.gui_settings.get("auto_process", False)
                            and result.success
                        ):
                            self._handle_auto_process(file_path, transcript_data)
                    else:
                        # Track failed completion
                        self.failed_count += 1

                        # Get descriptive error message
                        error_detail = (
                            "; ".join(result.errors)
                            if result.errors
                            else "Unknown transcription error"
                        )

                        # Check if this is an audio corruption error that needs re-download
                        needs_redownload = result.metadata and result.metadata.get(
                            "needs_redownload", False
                        )

                        if (
                            needs_redownload
                            and "AUDIO_CORRUPTION_SUSPECTED" in error_detail
                        ):
                            # Try to get source URL from database for re-download
                            try:
                                from ...database.service import DatabaseService
                                from ...utils.youtube_utils import extract_video_id

                                source_id = None
                                file_path_obj = Path(file_path)
                                filename = file_path_obj.stem

                                # Extract source_id from filename
                                if "[" in filename and "]" in filename:
                                    source_id = filename.split("[")[-1].split("]")[0]
                                else:
                                    import re

                                    match = re.search(
                                        r"_([a-zA-Z0-9_-]{11})$", filename
                                    )
                                    if match:
                                        source_id = match.group(1)

                                if source_id:
                                    db_service = DatabaseService()
                                    source_record = db_service.get_source(source_id)

                                    if source_record and source_record.url:
                                        # Re-download with fresh IP and transcribe with large model
                                        logger.info(
                                            f"🔄 Audio corruption detected for {source_id}, attempting re-download and transcription with large model"
                                        )
                                        self.transcription_step_updated.emit(
                                            f"🔄 Re-downloading {file_name} with fresh IP...",
                                            0,
                                        )

                                        # Delete corrupted file
                                        try:
                                            file_path_obj.unlink(missing_ok=True)
                                            logger.info(
                                                f"Deleted corrupted file: {file_path}"
                                            )
                                        except Exception as del_error:
                                            logger.warning(
                                                f"Could not delete corrupted file: {del_error}"
                                            )

                                        # Re-download
                                        from ...processors.youtube_download import (
                                            YouTubeDownloadProcessor,
                                        )

                                        # Get cookie settings from GUI
                                        enable_cookies = self.gui_settings.get(
                                            "enable_cookies", True
                                        )
                                        cookie_files = self.gui_settings.get(
                                            "cookie_files", []
                                        )
                                        cookie_file_path = (
                                            cookie_files[0] if cookie_files else None
                                        )
                                        disable_proxies_with_cookies = (
                                            self.gui_settings.get(
                                                "disable_proxies_with_cookies", True
                                            )
                                        )

                                        logger.info(
                                            f"🍪 Re-download cookie configuration:"
                                        )
                                        logger.info(
                                            f"   enable_cookies: {enable_cookies}"
                                        )
                                        logger.info(
                                            f"   cookie_file_path: {cookie_file_path}"
                                        )
                                        logger.info(
                                            f"   disable_proxies_with_cookies: {disable_proxies_with_cookies}"
                                        )

                                        downloader = YouTubeDownloadProcessor(
                                            enable_cookies=enable_cookies,
                                            cookie_file_path=cookie_file_path,
                                            disable_proxies_with_cookies=disable_proxies_with_cookies,
                                        )

                                        download_result = downloader.process(
                                            source_record.url,
                                            output_dir=self.gui_settings.get(
                                                "output_dir"
                                            ),
                                            db_service=db_service,
                                            progress_callback=lambda msg, pct=0: self.transcription_step_updated.emit(
                                                msg, pct
                                            ),
                                            cancellation_token=self.cancellation_token,
                                        )

                                        if (
                                            download_result.success
                                            and download_result.data.get(
                                                "downloaded_files"
                                            )
                                        ):
                                            new_audio_file = download_result.data[
                                                "downloaded_files"
                                            ][0]
                                            logger.info(
                                                f"✅ Re-downloaded successfully: {new_audio_file}"
                                            )
                                            self.transcription_step_updated.emit(
                                                f"✅ Re-downloaded, now transcribing with large model...",
                                                0,
                                            )

                                            # Create new processor with large model
                                            from ...processors.audio_processor import (
                                                AudioProcessor,
                                            )

                                            large_processor = AudioProcessor(
                                                model="large",  # Use large model for recovery
                                                device=self.gui_settings["device"],
                                                enable_diarization=enable_diarization,
                                                require_diarization=enable_diarization,
                                                progress_callback=self._transcription_progress_callback,
                                                speaker_assignment_callback=self._speaker_assignment_callback,
                                                preloaded_transcriber=None,  # Don't use preloaded model
                                                preloaded_diarizer=preloaded_diarizer,
                                                db_service=db_service,
                                            )

                                            # Retry transcription with large model
                                            retry_result = large_processor.process(
                                                Path(new_audio_file),
                                                **processing_kwargs_with_output,
                                            )

                                            if retry_result.success:
                                                # Success after recovery!
                                                self.failed_count -= (
                                                    1  # Undo the failed count
                                                )
                                                self.completed_count += 1

                                                transcript_data = retry_result.data
                                                text_length = (
                                                    len(transcript_data.get("text", ""))
                                                    if transcript_data
                                                    else 0
                                                )
                                                saved_file = (
                                                    retry_result.metadata.get(
                                                        "saved_markdown_file"
                                                    )
                                                    if retry_result.metadata
                                                    else None
                                                )

                                                # Extract source_id from retry metadata
                                                retry_source_id = (
                                                    retry_result.metadata.get(
                                                        "database_media_id"
                                                    )
                                                    if retry_result.metadata
                                                    else None
                                                )
                                                self.successful_files.append(
                                                    {
                                                        "file": file_name,
                                                        "text_length": text_length,
                                                        "saved_to": (
                                                            Path(saved_file).name
                                                            if saved_file
                                                            else None
                                                        ),
                                                        "saved_file_path": saved_file,
                                                        "source_id": retry_source_id,  # Store source_id for database lookup
                                                        "recovery_note": "Recovered after re-download with large model",
                                                    }
                                                )

                                                self.transcription_step_updated.emit(
                                                    f"✅ {file_name} recovered successfully with large model!",
                                                    100,
                                                )
                                                logger.info(
                                                    f"🎉 Successfully recovered {file_name} after re-download and large model transcription"
                                                )
                                                continue  # Skip the failure tracking below
                                            else:
                                                # Still failed after recovery attempt
                                                error_detail = f"Failed even after re-download and large model: {'; '.join(retry_result.errors)}"
                                                logger.error(
                                                    f"❌ Recovery failed for {file_name}: {error_detail}"
                                                )
                                        else:
                                            # Re-download failed
                                            error_detail = f"Re-download failed: {'; '.join(download_result.errors)}"
                                            logger.error(
                                                f"❌ Re-download failed for {file_name}: {error_detail}"
                                            )
                                    else:
                                        logger.warning(
                                            f"Could not find source URL for source_id {source_id} in database"
                                        )
                                else:
                                    logger.warning(
                                        f"Could not extract source_id from filename: {filename}"
                                    )

                            except Exception as recovery_error:
                                logger.error(
                                    f"Error during recovery attempt: {recovery_error}"
                                )
                                error_detail = f"{error_detail} (recovery attempt failed: {str(recovery_error)})"

                        # Track failed file with details
                        self.failed_files.append(
                            {"file": file_name, "error": error_detail}
                        )

                        # Emit progress update with failure
                        progress_data = {
                            "file": file_path,
                            "current": i + 1,
                            "total": self.total_files,
                            "status": f"transcription failed: {error_detail}",
                            "success": False,
                        }
                        self.progress_updated.emit(progress_data)
                        self.transcription_step_updated.emit(
                            f"❌ Transcription of {file_name} failed", 0
                        )

                except CancellationError:
                    # User cancelled the operation
                    logger.info(
                        f"Transcription cancelled by user for file: {file_name}"
                    )
                    self.transcription_step_updated.emit(
                        f"⏹ Transcription of {file_name} cancelled", 0
                    )
                    # Break out of the file loop
                    break

                except Exception as e:
                    # Track failed completion
                    self.failed_count += 1

                    error_msg = str(e)

                    # Track failed file with details
                    self.failed_files.append(
                        {
                            "file": file_name,
                            "error": f"Exception during transcription: {error_msg}",
                        }
                    )

                    progress_data = {
                        "file": file_path,
                        "current": i + 1,
                        "total": self.total_files,
                        "status": f"transcription error: {error_msg}",
                        "success": False,
                    }
                    self.progress_updated.emit(progress_data)
                    self.transcription_step_updated.emit(
                        f"❌ Error transcribing {file_name}: {error_msg}", 0
                    )

            # Display failed URLs summary if any
            if self.failed_urls:
                self.transcription_step_updated.emit(
                    f"\n{'='*60}\n📋 FAILED DOWNLOADS SUMMARY ({len(self.failed_urls)} URLs)\n{'='*60}",
                    0,
                )
                for failed_item in self.failed_urls:
                    self.transcription_step_updated.emit(
                        f"❌ [{failed_item['index']}] {failed_item['url']}", 0
                    )
                    self.transcription_step_updated.emit(
                        f"   Error: {failed_item['error_guidance']}", 0
                    )

                # Save failed URLs to file for easy retry
                try:
                    output_dir = self.gui_settings.get("output_dir")
                    if output_dir:
                        failed_urls_file = Path(output_dir) / "failed_downloads.txt"
                        with open(failed_urls_file, "w") as f:
                            f.write(
                                f"# Failed YouTube Downloads - {len(self.failed_urls)} URLs\n"
                            )
                            f.write(
                                f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                            )
                            for failed_item in self.failed_urls:
                                f.write(f"{failed_item['url']}\n")
                                f.write(f"# Error: {failed_item['error_guidance']}\n\n")

                        self.transcription_step_updated.emit(
                            f"💾 Failed URLs saved to: {failed_urls_file}", 0
                        )
                        logger.info(f"Failed URLs saved to: {failed_urls_file}")
                except Exception as e:
                    logger.error(f"Failed to save failed URLs file: {e}")

                self.transcription_step_updated.emit(
                    f"{'='*60}\n💡 Tip: Copy URLs above or use saved file to retry\n{'='*60}",
                    0,
                )

            # Combine failed URLs and failed files for comprehensive error reporting
            all_failed_details = []

            # Add failed URLs
            for failed_url in self.failed_urls:
                all_failed_details.append(
                    {
                        "file": failed_url.get("url", "Unknown URL"),
                        "error": failed_url.get(
                            "error_guidance", failed_url.get("error", "Unknown error")
                        ),
                    }
                )

            # Add failed local files
            all_failed_details.extend(self.failed_files)

            self.processing_finished.emit(
                self.completed_count, self.failed_count, all_failed_details
            )

        except Exception as e:
            import traceback

            error_msg = str(e) if str(e) else "Unknown error occurred"
            error_details = traceback.format_exc()
            logger.error(f"❌ Transcription worker error: {error_msg}")
            logger.error(f"Full traceback:\n{error_details}")
            self.processing_error.emit(f"{error_msg}\n\nSee logs for full traceback.")

    def _handle_auto_process(self, file_path: str, transcript_data: dict) -> None:
        """Handle System 2 auto-process pipeline."""
        try:
            # Import System 2 orchestrator
            import asyncio

            from ...core.system2_orchestrator import System2Orchestrator

            # Extract source ID from file path or generate one
            source_id = Path(file_path).stem

            # Create orchestrator instance
            orchestrator = System2Orchestrator()

            # Create and execute a pipeline job
            job_id = orchestrator.create_job(
                "pipeline",  # Database job type (not JobType enum)
                source_id,
                config={
                    "source": "local_file",
                    "file_path": file_path,
                    "transcript_data": transcript_data,
                },
                auto_process=True,
            )

            self.transcription_step_updated.emit(
                f"🚀 Starting System 2 pipeline for {Path(file_path).name}", 0
            )

            # Execute the job (process_job is async, so we need to run it with asyncio)
            logger.info(f"System 2 pipeline initiated for {source_id} (job: {job_id})")
            result = asyncio.run(orchestrator.process_job(job_id))

            if result.get("status") == "succeeded":
                self.transcription_step_updated.emit(
                    f"✅ System 2 pipeline completed for {Path(file_path).name}", 0
                )
                logger.info(f"System 2 pipeline succeeded for {source_id}")
            else:
                error_msg = result.get("error_message", "Unknown error")
                self.transcription_step_updated.emit(
                    f"⚠️ Pipeline completed with issues: {error_msg}", 0
                )
                logger.warning(
                    f"System 2 pipeline had issues for {source_id}: {error_msg}"
                )

        except Exception as e:
            logger.error(f"Failed to execute System 2 pipeline: {e}")
            self.transcription_step_updated.emit(
                f"❌ Failed to run pipeline: {str(e)}", 0
            )

    def stop(self) -> None:
        """Stop the transcription process."""
        self.should_stop = True
        # Cancel the token to stop any ongoing processor operations
        if hasattr(self, "cancellation_token") and self.cancellation_token:
            self.cancellation_token.cancel()


class TranscriptionTab(BaseTab, FileOperationsMixin):
    """Tab for audio and video transcription using Whisper."""

    # Signal for tab navigation
    navigate_to_tab = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        self.transcription_worker: EnhancedTranscriptionWorker | None = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "Local Transcription"

        # MUST call super().__init__() first before creating child widgets
        super().__init__(parent)

        # Initialize model preloader AFTER super init
        from ..components.model_preloader import ModelPreloader

        self.model_preloader = ModelPreloader(self)
        self._setup_model_preloader()

    def _setup_model_preloader(self):
        """Setup model preloader signals and configuration."""
        # Connect preloader signals
        self.model_preloader.transcription_model_loading.connect(
            self._on_transcription_loading
        )
        self.model_preloader.transcription_model_ready.connect(
            self._on_transcription_ready
        )
        self.model_preloader.diarization_model_loading.connect(
            self._on_diarization_loading
        )
        self.model_preloader.diarization_model_ready.connect(self._on_diarization_ready)
        self.model_preloader.preloading_complete.connect(self._on_preloading_complete)
        self.model_preloader.preloading_error.connect(self._on_preloading_error)

    def _start_model_preloading(self):
        """Start preloading models with current settings."""
        try:
            # Get current settings
            settings = self._get_transcription_settings()

            # Configure preloader
            self.model_preloader.configure(
                model=settings.get("model", "medium"),
                device=settings.get("device"),
                hf_token=getattr(self.settings.api_keys, "huggingface_token", None),
                enable_diarization=settings.get("diarization", True),
            )

            # Start preloading
            self.model_preloader.start_preloading()
            logger.info("🚀 Model preloading started")

        except Exception as e:
            logger.error(f"Failed to start model preloading: {e}")

    def _on_transcription_loading(self, message: str, progress: int):
        """Handle transcription model loading progress."""
        self.append_log(f"🔄 {message}")

    def _on_transcription_ready(self):
        """Handle transcription model ready."""
        self.append_log("✅ Transcription model ready!")

    def _on_diarization_loading(self, message: str, progress: int):
        """Handle diarization model loading progress."""
        self.append_log(f"✅ {message}")

    def _on_diarization_ready(self):
        """Handle diarization model ready."""
        self.append_log("✅ Diarization model ready!")

    def _on_preloading_complete(self):
        """Handle all models preloaded."""
        self.append_log("🎉 All models preloaded! Ready for transcription.")

    def _on_preloading_error(self, error: str):
        """Handle preloading error."""
        self.append_log(f"⚠️ Model preloading warning: {error}")

    def _setup_ui(self) -> None:
        """Setup the transcription UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)  # Add consistent spacing
        layout.setContentsMargins(10, 10, 10, 10)  # Add margins

        # Hardware recommendations section moved to Settings tab

        # Input section with minimal stretch factor
        input_section = self._create_input_section()
        layout.addWidget(input_section, 0)  # Minimal stretch for input section

        # Settings section - use collapsible groups for better space usage
        settings_section = self._create_settings_section()
        layout.addWidget(
            settings_section, 0
        )  # No extra stretch - let it take only what it needs

        # System 2 Auto-process controls will be embedded in the action bar

        # Performance section removed - dynamic resource management handles this now

        # Action buttons
        action_layout = self._create_action_layout()
        layout.addLayout(action_layout)

        # Progress section
        progress_section = self._create_progress_section()
        layout.addWidget(progress_section, 0)  # No extra stretch

        # Output section - give it priority to expand with available space
        output_layout = self._create_output_section()
        layout.addLayout(output_layout, 1)  # Stretch factor 1 to claim vertical space

        # Load saved settings after UI is set up
        # Use a timer with a small delay to ensure all widgets are fully initialized
        QTimer.singleShot(200, self._load_settings)

        # Start model preloading after UI is ready
        QTimer.singleShot(500, self._start_model_preloading)

    def _create_input_section(self) -> QGroupBox:
        """Create the input files section."""
        group = QGroupBox("Input files")
        layout = QVBoxLayout()
        layout.setSpacing(8)  # Add spacing between elements

        # Add supported file types info
        supported_types_label = QLabel(
            "Supported: Audio/Video files (*.mp4 *.mp3 *.wav *.webm *.m4a *.flac *.ogg), YouTube URLs, Playlists, RSS feeds, URL files (*.txt *.csv)"
        )
        supported_types_label.setStyleSheet(
            "color: #666; font-style: italic; margin-bottom: 8px;"
        )
        supported_types_label.setWordWrap(True)
        layout.addWidget(supported_types_label)

        # File list with improved size policy - much more compact
        self.transcription_files = QListWidget()
        self.transcription_files.setMinimumHeight(60)  # Much smaller minimum height
        self.transcription_files.setMaximumHeight(
            90
        )  # Much smaller maximum to save space
        # Set size policy to allow proper vertical expansion/contraction
        from PyQt6.QtWidgets import QSizePolicy

        self.transcription_files.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        # Enable custom paste handling for URLs
        self.transcription_files.installEventFilter(self)

        # Add placeholder text hint
        self.transcription_files.setToolTip(
            "Add files, folders, or paste URLs here.\n"
            "• Click 'Add Files' or 'Add Folder' buttons\n"
            "• Or paste URLs directly (Ctrl+V / Cmd+V)\n"
            "• Supports YouTube videos, playlists, RSS feeds\n"
            "• One URL per line when pasting"
        )

        layout.addWidget(self.transcription_files)

        # File buttons with proper spacing
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)  # Add spacing between buttons

        add_files_btn = QPushButton("Add Files")
        add_files_btn.setMinimumHeight(30)  # Ensure minimum button height
        add_files_btn.clicked.connect(self._add_files)
        add_files_btn.setToolTip(
            "Add individual audio/video files for transcription.\n"
            "• Supported formats: MP3, WAV, MP4, AVI, MOV, WMV, FLV, FLAC, OGG, and more\n"
            "• Multiple files can be selected at once\n"
            "• Files are processed in the order they appear in the list"
        )
        button_layout.addWidget(add_files_btn)

        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.setMinimumHeight(30)  # Ensure minimum button height
        add_folder_btn.clicked.connect(self._add_folder)
        add_folder_btn.setToolTip(
            "Add all compatible files from a selected folder.\n"
            "• Recursively scans subfolders for audio/video files\n"
            "• Automatically filters for supported formats\n"
            "• Useful for processing large collections of media files"
        )
        button_layout.addWidget(add_folder_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setMinimumHeight(30)  # Ensure minimum button height
        clear_btn.clicked.connect(self._clear_files)
        clear_btn.setStyleSheet(
            "background-color: #d32f2f; color: white; font-weight: bold;"
        )
        button_layout.addWidget(clear_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

    # Hardware recommendations section moved to Settings tab

    def _create_auto_process_section(self) -> QGroupBox:
        """Create the System 2 auto-process section."""
        group = QGroupBox("")
        layout = QVBoxLayout(group)

        # Auto-process checkbox
        self.auto_process_checkbox = QCheckBox(
            "Run these transcriptions through Summarization Process Automatically"
        )
        self.auto_process_checkbox.setToolTip(
            "When enabled, transcribed files will automatically continue through:\n"
            "1. Mining (extract claims, people, jargon, mental models)\n"
            "2. Flagship evaluation (rank and tier claims)\n"
            "3. Upload to cloud (if configured)\n\n"
            "This runs the complete knowledge extraction pipeline without manual intervention."
        )
        layout.addWidget(self.auto_process_checkbox)

        # Pipeline status label
        self.pipeline_status_label = QLabel("Ready to process")
        self.pipeline_status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.pipeline_status_label)

        return group

    def _create_settings_section(self) -> QGroupBox:
        """Create the transcription settings section."""
        group = QGroupBox("Settings")
        layout = QGridLayout()
        layout.setSpacing(5)  # Reduce vertical spacing between rows
        layout.setHorizontalSpacing(10)  # Reduce horizontal spacing between columns

        # Set column stretch factors to prevent excessive spacing
        # Columns 0, 2, 4 are for labels - no stretch
        # Columns 1, 3, 5 are for widgets - minimal stretch
        # Column 6 can stretch for checkboxes
        for col in range(7):
            if col in [0, 2, 4]:  # Label columns
                layout.setColumnStretch(col, 0)
            elif col in [1, 3, 5]:  # Widget columns
                layout.setColumnStretch(col, 0)
            else:  # Last column for checkboxes
                layout.setColumnStretch(col, 1)

        # Model selection - compact combo without extra width
        self.model_combo = QComboBox()
        self.model_combo.addItems(get_valid_whisper_models())
        # Don't set a hardcoded default - let _load_settings() handle it via settings manager
        self.model_combo.setMaximumWidth(120)  # Compact width
        self.model_combo.currentTextChanged.connect(self._on_model_changed)

        # Model status label - hidden or inline
        self.model_status_label = QLabel("✅ Ready")
        self.model_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.model_status_label.setToolTip("Model availability status")
        self.model_status_label.setMaximumWidth(60)

        # Row 0: Transcription Model | Language | Checkboxes side by side
        # Wrap Transcription Model label + widget together
        model_label_widget = QWidget()
        model_label_layout = QHBoxLayout(model_label_widget)
        model_label_layout.setContentsMargins(0, 0, 0, 0)
        model_label_layout.setSpacing(6)
        transcription_model_label = QLabel("Transcription Model:")
        transcription_model_label.setMinimumWidth(130)  # Fixed width for alignment
        model_label_layout.addWidget(transcription_model_label)
        model_label_layout.addWidget(self.model_combo)
        model_label_layout.addWidget(self.model_status_label)
        model_label_layout.addStretch()  # Keep compact
        model_tooltip = "Choose the Whisper model size. Larger models are more accurate but slower and use more memory. 'medium' is recommended for the best balance of speed and accuracy (70-80% less hallucinations than large)."
        model_label_widget.setToolTip(
            f"<b>Transcription Model:</b><br/><br/>{model_tooltip}"
        )
        layout.addWidget(model_label_widget, 0, 0, 1, 2)

        # Language selection - compact label + widget
        layout.addWidget(QLabel("Language:"), 0, 2)
        self.language_combo = QComboBox()
        self.language_combo.addItems(
            ["en", "auto", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]
        )
        self.language_combo.setCurrentText("auto")
        self.language_combo.setMaximumWidth(100)  # Compact width
        self.language_combo.currentTextChanged.connect(self._on_setting_changed)
        language_tooltip = "Select the language of the audio. 'auto' lets Whisper detect the language automatically. Specifying the exact language can improve accuracy."
        self.language_combo.setToolTip(f"<b>Language:</b><br/><br/>{language_tooltip}")
        layout.addWidget(self.language_combo, 0, 3)

        # Checkboxes on same row (row 0, columns 4, 5, 6)
        self.timestamps_checkbox = QCheckBox("Include timestamps")
        self.timestamps_checkbox.setChecked(True)
        self.timestamps_checkbox.setToolTip(
            "Include precise timing information in the transcript. "
            "Useful for creating subtitles or referencing specific moments in the audio."
        )
        self.timestamps_checkbox.toggled.connect(self._on_setting_changed)
        layout.addWidget(self.timestamps_checkbox, 0, 4)

        self.diarization_checkbox = QCheckBox("Enable speaker diarization")
        self.diarization_checkbox.setToolTip(
            "Identify and separate different speakers in the audio. "
            "Requires a HuggingFace token and additional dependencies. "
            "Useful for meetings, interviews, or conversations with multiple speakers."
        )
        self.diarization_checkbox.toggled.connect(self._on_setting_changed)
        self.diarization_checkbox.toggled.connect(self._on_diarization_toggled)
        layout.addWidget(self.diarization_checkbox, 0, 5)

        # DISABLED: Color-coded transcripts feature causes YAML corruption
        # The enhanced markdown with HTML color codes breaks YAML frontmatter parsing
        # Normal transcripts with speaker assignment work perfectly without color coding
        self.color_coded_checkbox = QCheckBox("Generate color-coded transcripts")
        self.color_coded_checkbox.setChecked(False)  # Always disabled
        self.color_coded_checkbox.setEnabled(False)  # Disable UI control
        self.color_coded_checkbox.setToolTip(
            "⚠️ DISABLED: This feature causes YAML formatting issues. "
            "Use speaker assignment without color coding for best results."
        )
        self.color_coded_checkbox.toggled.connect(self._on_setting_changed)
        self.color_coded_checkbox.setVisible(False)  # Hide from UI
        # layout.addWidget(self.color_coded_checkbox, 0, 6)  # Commented out - checkbox hidden

        # Row 1: GPU Acceleration | Format | Checkboxes side by side
        # Wrap GPU Acceleration label + widget together
        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cpu", "cuda", "mps"])
        self.device_combo.setCurrentText("mps")
        self.device_combo.setMaximumWidth(100)  # Compact width
        self.device_combo.currentTextChanged.connect(self._on_setting_changed)
        device_label_widget = QWidget()
        device_label_layout = QHBoxLayout(device_label_widget)
        device_label_layout.setContentsMargins(0, 0, 0, 0)
        device_label_layout.setSpacing(6)
        device_label = QLabel("GPU Acceleration:")
        device_label.setMinimumWidth(130)  # Fixed width for alignment
        device_label_layout.addWidget(device_label)
        device_label_layout.addWidget(self.device_combo)
        device_label_layout.addStretch()  # Keep compact
        device_tooltip = "Choose processing device: 'auto' detects best available, 'cpu' uses CPU only, 'cuda' uses NVIDIA GPU, 'mps' uses Apple Silicon GPU."
        self.device_combo.setToolTip(
            f"<b>GPU Acceleration:</b><br/><br/>{device_tooltip}"
        )
        layout.addWidget(device_label_widget, 1, 0, 1, 2)

        # Format - compact label + widget
        layout.addWidget(QLabel("Format:"), 1, 2)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["md", "none"])
        self.format_combo.setCurrentText("md")
        self.format_combo.setMaximumWidth(80)  # Compact width
        self.format_combo.currentTextChanged.connect(self._on_setting_changed)
        format_tooltip = "Output format: 'md' for Markdown with YAML frontmatter and metadata, 'none' to save to database only without creating output files."
        self.format_combo.setToolTip(f"<b>Format:</b><br/><br/>{format_tooltip}")
        layout.addWidget(self.format_combo, 1, 3)

        # Checkboxes on row 1
        self.overwrite_checkbox = QCheckBox("Overwrite existing transcripts")
        self.overwrite_checkbox.setChecked(True)
        self.overwrite_checkbox.setToolTip(
            "If unchecked, existing transcripts will be skipped"
        )
        self.overwrite_checkbox.toggled.connect(self._on_setting_changed)
        layout.addWidget(self.overwrite_checkbox, 1, 4)

        self.speaker_assignment_checkbox = QCheckBox("Enable speaker assignment")
        self.speaker_assignment_checkbox.setChecked(True)
        self.speaker_assignment_checkbox.setToolTip(
            "Show interactive dialog to assign real names to detected speakers. "
            "Allows you to identify speakers and create color-coded transcripts."
        )
        self.speaker_assignment_checkbox.toggled.connect(self._on_setting_changed)
        layout.addWidget(self.speaker_assignment_checkbox, 1, 5)

        # YouTube to RSS mapping checkbox
        # POSITIONED ABOVE Proxy selector per user request
        self.enable_rss_mapping_checkbox = QCheckBox("Enable YT→RSS")
        self.enable_rss_mapping_checkbox.setChecked(False)  # Default to unchecked
        self.enable_rss_mapping_checkbox.setToolTip(
            "When enabled, YouTube URLs are first checked to see if an identical episode\n"
            "is available via podcast RSS feed. RSS downloads are faster and more reliable.\n\n"
            "When disabled, YouTube URLs are downloaded directly from YouTube.\n\n"
            "Note: RSS mapping requires network access to search for matching podcast episodes."
        )
        self.enable_rss_mapping_checkbox.toggled.connect(self._on_setting_changed)
        layout.addWidget(
            self.enable_rss_mapping_checkbox, 0, 6
        )  # Row 0, Position 6 (above proxy)

        # Proxy mode selector - custom layout for precise positioning
        # POSITIONED BELOW YT→RSS checkbox per user request
        proxy_container = QWidget()
        proxy_layout = QHBoxLayout(proxy_container)
        proxy_layout.setContentsMargins(-20, 0, 0, 0)  # Move left 20 pixels
        proxy_layout.setSpacing(6)

        proxy_label = QLabel("Proxy:")
        proxy_layout.addWidget(proxy_label)

        self.proxy_mode_combo = QComboBox()
        self.proxy_mode_combo.addItems(["Auto", "Always", "Never"])
        self.proxy_mode_combo.setCurrentIndex(0)  # Default to Auto
        self.proxy_mode_combo.setMinimumWidth(90)  # 80 + 10 pixels wider
        self.proxy_mode_combo.setToolTip(
            "Control proxy usage for YouTube downloads:\n\n"
            "• Auto (recommended): Disables proxies when using cookies (home IP + cookies is most reliable),\n"
            "  enables proxies otherwise\n\n"
            "• Always: Force PacketStream proxy usage (requires credentials in Settings)\n\n"
            "• Never: Always use direct connection (faster but may trigger bot detection)"
        )
        self.proxy_mode_combo.currentIndexChanged.connect(self._on_setting_changed)
        proxy_layout.addWidget(self.proxy_mode_combo)
        proxy_layout.addStretch()

        layout.addWidget(
            proxy_container, 1, 6, 1, 2
        )  # Row 1, Position 6, span 2 columns for space

        # Output directory with custom layout for tooltip positioning
        layout.addWidget(QLabel("Output Directory:"), 2, 0)

        # Create a horizontal layout for text input + tooltip + browse button
        output_dir_layout = QHBoxLayout()
        output_dir_layout.setContentsMargins(0, 0, 0, 0)
        output_dir_layout.setSpacing(8)

        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText(
            "Click Browse to select output directory (required)"
        )
        self.output_dir_input.textChanged.connect(self._on_setting_changed)
        output_dir_layout.addWidget(self.output_dir_input)

        # Add tooltip info indicator between input and browse button
        output_dir_tooltip = "Directory where transcribed files will be saved. Click Browse to select a folder with write permissions."
        formatted_tooltip = f"<b>Output Directory:</b><br/><br/>{output_dir_tooltip}"

        info_label = QLabel("ⓘ")
        info_label.setFixedSize(16, 16)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setToolTip(formatted_tooltip)
        info_label.setStyleSheet(
            """
            QLabel {
                color: #007AFF;
                font-size: 12px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                color: #0051D5;
            }
        """
        )
        output_dir_layout.addWidget(info_label)

        browse_output_btn = QPushButton("Browse")
        browse_output_btn.setMaximumWidth(80)
        browse_output_btn.clicked.connect(self._select_output_directory)
        output_dir_layout.addWidget(browse_output_btn)

        # Create container widget for the custom layout
        output_dir_container = QWidget()
        output_dir_container.setLayout(output_dir_layout)
        layout.addWidget(
            output_dir_container, 2, 1, 1, 6
        )  # Span across multiple columns

        # Set tooltips for input and button as well
        self.output_dir_input.setToolTip(formatted_tooltip)
        browse_output_btn.setToolTip(formatted_tooltip)

        # Note: Automatic quality recovery is now always enabled
        # If transcription quality issues are detected, the system will:
        # 1. Retry with next larger model
        # 2. If still failing, re-download audio and use large model
        # 3. If still failing, mark as permanent failure

        # Cookie Authentication Section - collapsible
        cookie_group = QGroupBox("Cookie Authentication (Multi-Account Support)")
        cookie_group.setCheckable(True)
        cookie_group.setChecked(
            True
        )  # Start expanded to emphasize cookie auth as default
        cookie_group.setFlat(True)  # Make it more compact
        cookie_layout = QVBoxLayout()

        # Multi-account cookie manager widget
        # Cookie authentication is automatically enabled when cookie files are provided
        # Multi-account mode is automatically enabled when multiple cookie files are provided
        self.cookie_manager = CookieFileManager()
        self.cookie_manager.cookies_changed.connect(self._on_setting_changed)
        cookie_layout.addWidget(self.cookie_manager)

        cookie_group.setLayout(cookie_layout)
        layout.addWidget(cookie_group, 3, 0, 1, 7)

        # Rate Limiting Section - collapsible
        rate_limit_group = QGroupBox("Rate Limiting (Per-Account Anti-Bot Protection)")
        rate_limit_group.setCheckable(True)
        rate_limit_group.setChecked(False)  # Start collapsed
        rate_limit_group.setFlat(True)  # Make it more compact
        rate_limit_layout = QVBoxLayout()

        # Explanation text
        explanation_label = QLabel(
            "⏱️ These delays apply <b>per account</b> in multi-account mode. With multiple accounts downloading "
            "<b>concurrently</b> from the same IP (like a family household), overall throughput is much faster "
            "while each account maintains human-like behavior patterns."
        )
        explanation_label.setWordWrap(True)
        explanation_label.setStyleSheet(
            "color: #888; font-size: 11px; padding: 5px; margin-bottom: 8px;"
        )
        rate_limit_layout.addWidget(explanation_label)

        # Single horizontal row for all delay controls
        delay_row = QHBoxLayout()
        delay_row.setSpacing(15)

        # Min delay
        min_delay_label = QLabel("Min delay:")
        delay_row.addWidget(min_delay_label)
        self.min_delay_spinbox = QSpinBox()
        self.min_delay_spinbox.setMinimum(0)
        self.min_delay_spinbox.setMaximum(600)
        self.min_delay_spinbox.setValue(180)  # 3 minutes default
        self.min_delay_spinbox.setSuffix(" sec")
        self.min_delay_spinbox.setMaximumWidth(90)
        self.min_delay_spinbox.setStyleSheet("QSpinBox { color: white; }")  # White text
        self.min_delay_spinbox.setToolTip(
            "Minimum delay between downloads for each account (seconds).\n"
            "With 6 accounts, effective rate is 6x faster than this delay."
        )
        self.min_delay_spinbox.valueChanged.connect(self._on_setting_changed)
        delay_row.addWidget(self.min_delay_spinbox)

        # Max delay
        max_delay_label = QLabel("Max delay:")
        delay_row.addWidget(max_delay_label)
        self.max_delay_spinbox = QSpinBox()
        self.max_delay_spinbox.setMinimum(0)
        self.max_delay_spinbox.setMaximum(600)
        self.max_delay_spinbox.setValue(300)  # 5 minutes default
        self.max_delay_spinbox.setSuffix(" sec")
        self.max_delay_spinbox.setMaximumWidth(90)
        self.max_delay_spinbox.setStyleSheet("QSpinBox { color: white; }")  # White text
        self.max_delay_spinbox.setToolTip(
            "Maximum delay between downloads for each account (seconds).\n"
            "With 6 accounts, effective rate is 6x faster than this delay."
        )
        self.max_delay_spinbox.valueChanged.connect(self._on_setting_changed)
        delay_row.addWidget(self.max_delay_spinbox)

        # Randomization
        randomization_label = QLabel("Randomization:")
        delay_row.addWidget(randomization_label)
        self.randomization_spinbox = QSpinBox()
        self.randomization_spinbox.setMinimum(0)
        self.randomization_spinbox.setMaximum(100)
        self.randomization_spinbox.setValue(25)  # ±25% default
        self.randomization_spinbox.setSuffix(" %")
        self.randomization_spinbox.setMaximumWidth(70)
        self.randomization_spinbox.setStyleSheet(
            "QSpinBox { color: white; }"
        )  # White text
        self.randomization_spinbox.setToolTip(
            "Percentage of random variation in delays (e.g., 25 = ±25%).\n"
            "Adds unpredictability to avoid bot detection patterns."
        )
        self.randomization_spinbox.valueChanged.connect(self._on_setting_changed)
        delay_row.addWidget(self.randomization_spinbox)

        delay_row.addStretch()  # Push to left
        rate_limit_layout.addLayout(delay_row)

        rate_limit_group.setLayout(rate_limit_layout)
        layout.addWidget(rate_limit_group, 4, 0, 1, 7)

        group.setLayout(layout)
        return group

    # Performance section removed - dynamic resource management handles this now

    def _create_progress_section(self) -> QWidget:
        """Create the progress tracking section with simple, reliable progress bar."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Use new simple progress bar for reliable percentage display
        from ..components.simple_progress_bar import SimpleTranscriptionProgressBar

        self.progress_display = SimpleTranscriptionProgressBar()
        # Note: Cancel functionality is handled by the parent tab's 'Stop Processing' button
        # No cancel_requested signal needed - SimpleTranscriptionProgressBar doesn't emit one
        layout.addWidget(self.progress_display)

        # Remove redundant rich log display to fix double console issue
        # The main output_text area in the base tab already provides console output

        # Keep old progress elements for backward compatibility (hidden)
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setVisible(False)
        self.progress_status_label = QLabel("")
        self.progress_status_label.setVisible(False)

        return container

    # Override: place auto-process controls on the same row as Dry Run
    def _create_action_layout(self) -> QHBoxLayout:
        from PyQt6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout()

        # Start button
        self.start_btn = QPushButton(self._get_start_button_text())
        self.start_btn.clicked.connect(self._start_processing)
        self.start_btn.setFixedHeight(25)
        self.start_btn.setStyleSheet(
            "background-color: #4caf50; font-weight: bold; font-size: 12px; padding: 4px;"
        )
        layout.addWidget(self.start_btn)

        # Stop button
        self.stop_btn = QPushButton("Stop Processing")
        self.stop_btn.clicked.connect(self._stop_processing)
        self.stop_btn.setFixedHeight(25)
        self.stop_btn.setStyleSheet(
            "background-color: #d32f2f; color: white; font-weight: bold; font-size: 12px; padding: 4px;"
        )
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        # Dry run checkbox
        self.dry_run_checkbox = QCheckBox("Dry run (test without processing)")
        layout.addWidget(self.dry_run_checkbox)

        # Auto-process controls inline with Dry run
        self.auto_process_checkbox = QCheckBox(
            "Run these transcriptions through Summarization Process Automatically"
        )
        self.auto_process_checkbox.setToolTip(
            "When enabled, transcribed files will automatically continue through:\n"
            "1. Mining (extract claims, people, jargon, mental models)\n"
            "2. Flagship evaluation (rank and tier claims)\n"
            "3. Upload to cloud (if configured)\n\n"
            "This runs the complete knowledge extraction pipeline without manual intervention."
        )
        layout.addWidget(self.auto_process_checkbox)

        self.pipeline_status_label = QLabel("Ready to process")
        self.pipeline_status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.pipeline_status_label)

        # Spacer then report button at far right
        layout.addStretch()

        self.report_btn = QPushButton("View Last Report")
        self.report_btn.clicked.connect(self._view_last_report)
        self.report_btn.setEnabled(True)
        self.report_btn.setFixedHeight(25)
        self.report_btn.setStyleSheet(
            "background-color: #1976d2; font-size: 12px; padding: 4px;"
        )
        layout.addWidget(self.report_btn)

        return layout

    def _add_files(
        self,
        checked: bool = False,  # Qt signal parameter (ignored)
        file_list_attr: str = "transcription_files",
        file_patterns: str = "Audio/Video files (*.mp4 *.mp3 *.wav *.webm *.m4a *.flac *.ogg);;All files (*.*)",
    ):
        """Add files for transcription."""
        file_list = getattr(self, file_list_attr, self.transcription_files)
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio/Video Files",
            "",
            file_patterns,
        )
        for file in files:
            file_list.addItem(file)

    def _add_folder(self):
        """Add transcription folder with async scanning to prevent GUI blocking."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            # Start async folder scanning to prevent GUI blocking
            self.append_log(f"📁 Scanning folder: {folder}")
            self.append_log("🔍 Please wait while scanning for audio/video files...")

            # Create and start folder scan worker
            self._start_folder_scan(folder)

    def _start_folder_scan(self, folder_path: str) -> None:
        """Start async folder scanning worker."""
        from PyQt6.QtCore import QThread, pyqtSignal

        class FolderScanWorker(QThread):
            """Worker thread for scanning folders without blocking GUI."""

            files_found = pyqtSignal(list)  # List of file paths found
            scan_progress = pyqtSignal(int, str)  # count, current_file_name
            scan_completed = pyqtSignal(int, str)  # total_found, folder_name
            scan_error = pyqtSignal(str)  # error_message

            def __init__(self, folder_path: str):
                super().__init__()
                self.folder_path = Path(folder_path)
                self.extensions = [
                    ".mp4",
                    ".mp3",
                    ".wav",
                    ".webm",
                    ".m4a",
                    ".flac",
                    ".ogg",
                ]
                self.should_stop = False

            def run(self):
                """Scan folder for audio/video files."""
                try:
                    found_files = []
                    files_processed = 0

                    # Use iterator to avoid loading all files into memory at once
                    for file_path in self.folder_path.rglob("*"):
                        if self.should_stop:
                            break

                        files_processed += 1

                        # Check if it's a file and has a valid extension
                        if (
                            file_path.is_file()
                            and file_path.suffix.lower() in self.extensions
                        ):
                            found_files.append(str(file_path))
                            # Emit progress update every 10 files found or every 100 files processed
                            if len(found_files) % 10 == 0 or files_processed % 100 == 0:
                                self.scan_progress.emit(
                                    len(found_files), file_path.name
                                )

                    # Emit final results
                    self.files_found.emit(found_files)
                    self.scan_completed.emit(len(found_files), self.folder_path.name)

                except Exception as e:
                    self.scan_error.emit(f"Error scanning folder: {str(e)}")

            def stop(self):
                """Stop the scanning process."""
                self.should_stop = True

        # Create and configure worker
        self._folder_scan_worker = FolderScanWorker(folder_path)
        self._folder_scan_worker.files_found.connect(self._handle_scanned_files)
        self._folder_scan_worker.scan_progress.connect(self._handle_scan_progress)
        self._folder_scan_worker.scan_completed.connect(self._handle_scan_completed)
        self._folder_scan_worker.scan_error.connect(self._handle_scan_error)

        # Start scanning
        self._folder_scan_worker.start()

    def _handle_scanned_files(self, file_paths: list[str]) -> None:
        """Handle the list of scanned files."""
        # Add all found files to the list
        for file_path in file_paths:
            self.transcription_files.addItem(file_path)

    def _handle_scan_progress(self, files_found: int, current_file: str) -> None:
        """Handle scan progress updates."""
        self.append_log(
            f"🔍 Found {files_found} audio/video files (scanning {current_file}...)"
        )

    def _handle_scan_completed(self, total_found: int, folder_name: str) -> None:
        """Handle scan completion."""
        self.append_log(
            f"✅ Scan complete: Found {total_found} audio/video files in '{folder_name}'"
        )

        # Clean up worker
        if hasattr(self, "_folder_scan_worker"):
            self._folder_scan_worker.deleteLater()
            del self._folder_scan_worker

    def _handle_scan_error(self, error_message: str) -> None:
        """Handle scan errors."""
        self.append_log(f"❌ {error_message}")
        self.show_error("Folder Scan Error", error_message)

        # Clean up worker
        if hasattr(self, "_folder_scan_worker"):
            self._folder_scan_worker.deleteLater()
            del self._folder_scan_worker

    def _clear_files(self):
        """Clear transcription file list."""
        self.transcription_files.clear()

    def eventFilter(self, obj, event):
        """Handle paste events for the file list to support URL pasting."""
        try:
            from PyQt6.QtCore import QEvent
            from PyQt6.QtGui import QKeySequence
            from PyQt6.QtWidgets import QApplication

            if obj == self.transcription_files and event.type() == QEvent.Type.KeyPress:
                # Check for Ctrl+V (Windows/Linux) or Cmd+V (Mac)
                if event.matches(QKeySequence.StandardKey.Paste):
                    clipboard = QApplication.clipboard()
                    text = clipboard.text() if clipboard else ""

                    if text:
                        # Split by newlines and process each line
                        lines = [
                            line.strip() for line in text.split("\n") if line.strip()
                        ]

                        added_count = 0
                        for line in lines:
                            # Add URLs and file paths directly
                            if line:
                                self.transcription_files.addItem(line)
                                added_count += 1

                        if added_count > 0:
                            self.append_log(
                                f"✅ Added {added_count} item(s) from clipboard"
                            )

                        return True  # Event handled

        except Exception as e:
            logger.error(f"Error in eventFilter: {e}")
            # Don't crash - just pass event to parent

        # Pass event to parent
        return super().eventFilter(obj, event)

    def _is_supported_url(self, url: str) -> bool:
        """Check if URL is supported (YouTube, playlist, or RSS)."""
        if not url or not isinstance(url, str):
            return False

        url_lower = url.lower()

        # Check for YouTube URLs
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return True

        # Check for RSS/podcast feeds (common patterns)
        if (
            url_lower.endswith((".rss", ".xml"))
            or "/feed" in url_lower
            or "/rss" in url_lower
        ):
            return True

        # Check for http/https URLs that might be RSS feeds
        if url.startswith(("http://", "https://")):
            return True

        return False

    def _select_output_directory(self):
        """Select output directory for transcripts."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_dir_input.setText(dir_path)

    def _get_start_button_text(self) -> str:
        """Get the text for the start button."""
        return "Start Transcription"

    def _start_processing(self) -> None:
        """Start transcription process."""
        # Check if required models are available
        from ..utils.model_check import ensure_models_ready

        if not ensure_models_ready(self.window(), "Local Transcription", ["whisper"]):
            # Models are downloading, notification shown
            return

        # Reset progress tracking for new operation
        self._failed_files = set()

        # Get files to process (can be local files or URLs)
        items = []
        for i in range(self.transcription_files.count()):
            item = self.transcription_files.item(i)
            if item is not None:
                items.append(item.text())

        if not items:
            self.show_warning("Warning", "No files or URLs selected for transcription")
            return

        # Separate URLs from local files
        urls = []
        local_files = []
        for item in items:
            if self._is_supported_url(item):
                urls.append(item)
            else:
                local_files.append(item)

        # Validate inputs
        if not self.validate_inputs():
            return

        # Validate cookie settings if processing YouTube URLs
        if urls and not self._validate_cookie_settings():
            return

        # Clear output and show progress
        self.output_text.clear()

        total_items = len(items)
        if urls and local_files:
            self.append_log(
                f"Starting transcription of {total_items} items ({len(urls)} URLs, {len(local_files)} local files)..."
            )
        elif urls:
            self.append_log(f"Starting transcription of {len(urls)} URLs...")
        else:
            self.append_log(f"Starting transcription of {len(local_files)} files...")

        # Enable processing state (disables start, enables stop)
        self.set_processing_state(True)
        self.start_btn.setText("Processing...")

        # Get transcription settings
        gui_settings = self._get_transcription_settings()

        # Add auto-process setting
        gui_settings["auto_process"] = self.auto_process_checkbox.isChecked()

        # Test PacketStream proxy if URLs present and user enabled it
        packetstream_available = False

        # Check strict mode setting
        from ...config import get_settings

        settings = get_settings()
        strict_mode = getattr(settings.youtube_processing, "proxy_strict_mode", True)

        # Determine proxy mode from combo box
        # 0 = Auto (disable with cookies)
        # 1 = Always use proxies
        # 2 = Never use proxies
        proxy_mode = self.proxy_mode_combo.currentIndex()

        # Determine if we should use proxies based on mode and cookie state
        # Cookies are automatically enabled when cookie files are present
        cookie_files = self.cookie_manager.get_all_cookie_files()
        cookies_enabled = len(cookie_files) > 0

        if proxy_mode == 0:  # Auto
            should_use_proxy = not cookies_enabled
        elif proxy_mode == 1:  # Always
            should_use_proxy = True
        else:  # Never (mode == 2)
            should_use_proxy = False

        # CRITICAL: Enforce strict mode ONLY if trying to use direct connection without exemption
        # Block if: strict_mode=True AND not using proxies AND NOT using cookie exemption
        if urls and strict_mode and not should_use_proxy and not cookies_enabled:
            self.append_log("🚫 BLOCKED: Proxy strict mode is enabled")
            self.append_log("⚠️ Direct connections blocked without proxies or cookies")
            self.append_log("🛡️ Blocked to protect your IP from YouTube bans")
            self.append_log(
                "💡 Fix: Change 'Proxy Mode' to 'Auto' or 'Always use proxies'"
            )
            self.append_log("💡 Or: Enable cookie authentication")
            self.append_log(
                "💡 Alternative: Disable strict mode in Settings > YouTube Processing"
            )
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "Proxy Required",
                "Proxy strict mode is enabled but you're trying to use direct connection without cookies.\n\n"
                "Direct YouTube connections are blocked to protect your IP address from rate limits and bans.\n\n"
                "Please either:\n"
                "• Change Proxy Mode to 'Auto' or 'Always use proxies'\n"
                "• Enable cookie authentication\n"
                "• Disable strict mode in Settings > YouTube Processing (not recommended)",
            )
            return

        # Log proxy decision
        if not should_use_proxy and cookies_enabled:
            self.append_log(
                "🍪 Using cookies with home IP - proxies disabled (Auto mode)"
            )
            packetstream_available = False
        elif urls and should_use_proxy:
            try:
                from ...utils.packetstream_proxy import PacketStreamProxyManager

                proxy_manager = PacketStreamProxyManager()
                if proxy_manager.username and proxy_manager.auth_key:
                    self.append_log("🔍 Testing PacketStream proxy connectivity...")

                    def retry_callback(message):
                        self.append_log(f"  🔄 {message}")

                    (
                        proxy_working,
                        proxy_message,
                    ) = proxy_manager.test_proxy_connectivity(
                        timeout=8, max_retries=5, retry_callback=retry_callback
                    )

                    if proxy_working:
                        self.append_log(f"✅ {proxy_message}")
                        self.append_log("✅ YouTube anti-bot protection enabled")
                        packetstream_available = True
                    else:
                        self.append_log(f"❌ PacketStream proxy failed: {proxy_message}")

                        if strict_mode:
                            self.append_log("🚫 BLOCKED: Proxy strict mode enabled")
                            self.append_log(
                                "🛡️ Direct connections blocked to protect your IP from YouTube bans"
                            )
                            self.append_log(
                                "💡 Fix: Check PacketStream configuration in Settings > API Keys"
                            )
                            self.append_log(
                                "💡 Alternative: Disable strict mode in Settings (NOT RECOMMENDED)"
                            )
                            from PyQt6.QtWidgets import QMessageBox

                            QMessageBox.critical(
                                self,
                                "Proxy Required",
                                "Proxy strict mode is enabled and the PacketStream proxy test failed.\n\n"
                                "Direct YouTube connections are blocked to protect your IP address from rate limits and bans.\n\n"
                                "Please fix your PacketStream configuration in Settings > API Keys, "
                                "or disable strict mode in Settings > YouTube Processing (not recommended).",
                            )
                            return
                        else:
                            self.append_log(
                                "⚠️ Falling back to direct download (strict mode disabled)"
                            )
                else:
                    if strict_mode:
                        self.append_log("🚫 BLOCKED: Proxy strict mode enabled")
                        self.append_log(
                            "⚠️ PacketStream credentials not configured in Settings"
                        )
                        self.append_log(
                            "🛡️ Direct connections blocked to protect your IP from YouTube bans"
                        )
                        self.append_log(
                            "💡 Fix: Configure PacketStream in Settings > API Keys"
                        )
                        self.append_log(
                            "💡 Alternative: Disable strict mode in Settings (NOT RECOMMENDED)"
                        )
                        from PyQt6.QtWidgets import QMessageBox

                        QMessageBox.critical(
                            self,
                            "Proxy Required",
                            "Proxy strict mode is enabled but PacketStream is not configured.\n\n"
                            "Direct YouTube connections are blocked to protect your IP address from rate limits and bans.\n\n"
                            "Please configure PacketStream in Settings > API Keys, "
                            "or disable strict mode in Settings > YouTube Processing (not recommended).",
                        )
                        return
                    else:
                        self.append_log(
                            "⚠️ PacketStream credentials not configured in Settings"
                        )
                        self.append_log("💡 Proceeding with direct download + delays")
            except Exception as e:
                self.append_log(f"⚠️ PacketStream error: {e}")

                if strict_mode:
                    self.append_log("🚫 BLOCKED: Proxy strict mode enabled")
                    self.append_log(
                        "🛡️ Direct connections blocked to protect your IP from YouTube bans"
                    )
                    self.append_log(
                        "💡 Fix: Check PacketStream configuration in Settings > API Keys"
                    )
                    self.append_log(
                        "💡 Alternative: Disable strict mode in Settings (NOT RECOMMENDED)"
                    )
                    from PyQt6.QtWidgets import QMessageBox

                    QMessageBox.critical(
                        self,
                        "Proxy Error",
                        f"Proxy strict mode is enabled and PacketStream encountered an error:\n{e}\n\n"
                        "Direct YouTube connections are blocked to protect your IP address from rate limits and bans.\n\n"
                        "Please fix your PacketStream configuration in Settings > API Keys, "
                        "or disable strict mode in Settings > YouTube Processing (not recommended).",
                    )
                    return
                else:
                    self.append_log(
                        "⚠️ Proceeding with direct download (strict mode disabled)"
                    )
        elif urls and not should_use_proxy:
            # Direct download mode (no proxy)
            if not cookies_enabled:
                # Warn user about risks of direct download without cookies
                self.append_log(
                    "⚠️ WARNING: Direct download mode (no proxy, no cookies)"
                )
                self.append_log(
                    "⚠️ YouTube may flag your IP as a bot and block downloads"
                )
                self.append_log(
                    "💡 RECOMMENDATION: Use 'Auto' proxy mode with cookies, or 'Always use proxies'"
                )
                self.append_log(
                    "ℹ️ Proceeding with sequential downloads + delays (minimal protection)"
                )

        # Pass both URLs and local files to worker
        gui_settings["urls"] = urls
        gui_settings["local_files"] = local_files
        gui_settings["use_proxy"] = should_use_proxy
        gui_settings["packetstream_available"] = packetstream_available
        gui_settings[
            "youtube_delay"
        ] = 5  # Default delay (legacy setting, rate limiting now handled by min/max delay spinboxes)

        # Pass cookie settings to worker (automatically enabled when cookie files are present)
        gui_settings["cookie_files"] = self.cookie_manager.get_all_cookie_files()
        gui_settings["enable_cookies"] = len(gui_settings["cookie_files"]) > 0
        gui_settings["use_multi_account"] = len(gui_settings["cookie_files"]) > 1

        # Pass RSS mapping setting to worker
        gui_settings[
            "enable_rss_mapping"
        ] = self.enable_rss_mapping_checkbox.isChecked()

        # Proxy mode: 0=Auto, 1=Always, 2=Never
        gui_settings["proxy_mode"] = self.proxy_mode_combo.currentIndex()
        # For backwards compatibility with YouTubeDownloadProcessor
        gui_settings["disable_proxies_with_cookies"] = (
            proxy_mode == 0 or proxy_mode == 2
        )

        # Start transcription worker
        self.transcription_worker = EnhancedTranscriptionWorker(
            local_files, self.settings, gui_settings, self
        )
        self.transcription_worker.progress_updated.connect(self._update_progress)
        self.transcription_worker.file_completed.connect(self._file_completed)
        self.transcription_worker.processing_finished.connect(self._processing_finished)
        self.transcription_worker.processing_error.connect(self._processing_error)
        self.transcription_worker.transcription_step_updated.connect(
            self._update_transcription_step
        )
        self.transcription_worker.total_files_determined.connect(
            self._on_total_files_determined
        )
        self.transcription_worker.speaker_assignment_requested.connect(
            self._handle_speaker_assignment_request
        )
        self.transcription_worker.log_message.connect(self._on_worker_log_message)
        self.transcription_worker.existing_audio_decision_requested.connect(
            self._on_existing_audio_decision_requested
        )

        self.active_workers.append(self.transcription_worker)
        self.transcription_worker.start()

        # Start progress tracking
        # Always start with at least 1 file to avoid indeterminate mode (rolling progress)
        # If we have URLs, the count will be updated when downloads complete
        if urls:
            # Start with 1 file minimum to show determinate progress
            # Will be updated to actual count after downloads via total_files_determined signal
            self.progress_display.start_processing(
                max(1, len(urls)), "Transcribing URLs"
            )
        else:
            # Use determinate progress for local files only
            self.progress_display.start_processing(total_items, "Transcribing Files")

        # Rich log display removed - using main output_text area instead

        self.status_updated.emit("Transcription in progress...")

    def _on_total_files_determined(self, total_files: int):
        """Handle when the total number of files has been determined (after URL expansion)."""
        logger.info(f"🔍 Total files determined: {total_files}")

        # Switch from indeterminate to determinate progress
        if total_files > 0:
            self.progress_display.set_total_files(total_files)
            logger.info(
                f"✅ Progress bar switched to determinate mode with {total_files} files"
            )

    def _handle_speaker_assignment_request(
        self, speaker_data_list, recording_path, metadata, task_id
    ):
        """
        Handle speaker assignment request from worker thread (non-blocking).
        Shows the dialog on the main thread but doesn't wait for completion.
        The dialog will update the database directly when completed.
        """
        try:
            logger.info(
                f"Main thread showing speaker assignment dialog for task {task_id}"
            )

            # Import dialog and queue lazily to avoid circular deps
            from knowledge_system.utils.speaker_assignment_queue import (
                get_speaker_assignment_queue,
            )

            from ..dialogs.speaker_assignment_dialog import SpeakerAssignmentDialog

            queue = get_speaker_assignment_queue()

            # Create and show dialog (non-modal so processing can continue)
            dialog = SpeakerAssignmentDialog(
                speaker_data_list, recording_path, metadata, self
            )

            # Connect completion signal to update the task in queue
            def on_dialog_completed():
                assignments = dialog.get_assignments()
                queue.complete_task(task_id, assignments)
                logger.info(f"Speaker assignment completed for task {task_id}")

            def on_dialog_cancelled():
                queue.complete_task(task_id, None)
                logger.info(f"Speaker assignment cancelled for task {task_id}")

            dialog.speaker_assignments_completed.connect(on_dialog_completed)
            dialog.assignment_cancelled.connect(on_dialog_cancelled)

            # Show dialog non-modally to allow other dialogs to stack up
            dialog.show()  # Non-modal - allows multiple dialogs

            # Append info to log
            self.append_log(
                f"✅ Speaker assignment dialog opened for {Path(recording_path).name}. "
                f"Processing continues in background..."
            )

        except Exception as e:
            logger.error(f"Error showing speaker assignment dialog: {e}")
            # If dialog fails, still complete the task
            from knowledge_system.utils.speaker_assignment_queue import (
                get_speaker_assignment_queue,
            )

            queue = get_speaker_assignment_queue()
            queue.complete_task(task_id, None)

    def _update_transcription_step(self, step_description: str, progress_percent: int):
        """Update real-time transcription step display."""
        # Log to both GUI console and terminal for visibility
        log_message = (
            step_description
            if step_description.startswith(("🎤", "📥", "✅", "⏱️", "🔗", "❌", "🍪", "🏠"))
            else f"🎤 {step_description}"
        )
        self.append_log(log_message)

        # Also print download progress to terminal/console for visibility
        if "Downloading" in step_description or "Download" in step_description:
            print(f"  {log_message}")

    def _on_existing_audio_decision_requested(self, payload: dict) -> None:
        """Show modal prompt asking whether to reuse existing audio or re-download."""

        try:
            file_path = payload.get("file_path")
            source_id = payload.get("source_id")
            size_bytes = payload.get("size_bytes") or 0
            if size_bytes >= 1024 * 1024:
                size_display = f"{size_bytes / (1024 * 1024):.2f} MB"
            elif size_bytes >= 1024:
                size_display = f"{size_bytes / 1024:.1f} KB"
            elif size_bytes:
                size_display = f"{size_bytes} bytes"
            else:
                size_display = "Unknown size"

            filename_display = Path(file_path).name if file_path else "Unknown file"
            message_lines = [
                "Audio for this URL already exists on disk.",
                "",
                f"File: {filename_display}",
                f"Size: {size_display}",
            ]
            if source_id:
                message_lines.append(f"Video ID: {source_id}")
            message_lines.extend(
                [
                    "",
                    "Choose an option:",
                    "• Yes — use the existing audio",
                    "• No — download a fresh copy",
                ]
            )

            result = QMessageBox.question(
                self,
                "Existing Audio Detected",
                "\n".join(message_lines),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            use_existing = result == QMessageBox.StandardButton.Yes
        except Exception as e:
            logger.error(f"Error showing existing audio prompt: {e}")
            use_existing = True
        finally:
            try:
                self.transcription_worker.set_existing_audio_decision(use_existing)
            except Exception as response_error:
                logger.error(
                    f"Failed to send existing audio decision back to worker: {response_error}"
                )

        # Handle unknown progress (-1 sentinel value)
        # This happens when whisper.cpp is processing but doesn't report numeric progress yet
        if progress_percent < 0:
            # Don't update progress bars, just log the message
            # The bars will keep showing their last known value
            return

        # Detect current phase and map to overall progress
        # Phase breakdown per file:
        # - Download: 20% (0-20)
        # - Audio Conversion: 5% (20-25)
        # - Transcription: 50% (25-75)
        # - Diarization: 20% (75-95)
        # - Save/Finalize: 5% (95-100)

        phase_name = "Processing"
        phase_progress = progress_percent  # Progress within this phase (0-100)
        overall_contribution = 0  # Contribution to overall file progress (0-100)

        if "Downloading" in step_description or "Download" in step_description:
            phase_name = "Downloading"
            # Download is 0-20% of overall
            overall_contribution = int(phase_progress * 0.20)

        elif (
            "Converting audio" in step_description
            or "convert" in step_description.lower()
        ):
            phase_name = "Converting Audio"
            # Conversion is 20-25% of overall
            overall_contribution = 20 + int(phase_progress * 0.05)

        elif (
            "transcription" in step_description.lower()
            or "Transcribing" in step_description
        ):
            phase_name = "Transcribing"
            # Transcription is 25-75% of overall
            overall_contribution = 25 + int(phase_progress * 0.50)

        elif (
            "diarization" in step_description.lower()
            or "speaker" in step_description.lower()
        ):
            phase_name = "Speaker Diarization"
            # Diarization is 75-95% of overall
            overall_contribution = 75 + int(phase_progress * 0.20)

        elif (
            "Saving" in step_description
            or "Writing" in step_description
            or "markdown" in step_description.lower()
        ):
            phase_name = "Saving Files"
            # Save is 95-100% of overall
            overall_contribution = 95 + int(phase_progress * 0.05)

        elif "metadata" in step_description.lower():
            phase_name = "Processing Metadata"
            # Metadata extraction happens during download phase
            overall_contribution = min(20, int(phase_progress * 0.20))

        elif "Testing" in step_description or "connectivity" in step_description:
            phase_name = "Testing Connection"
            overall_contribution = 0  # Setup doesn't count toward file progress

        elif "Using cookies" in step_description or "proxy" in step_description.lower():
            phase_name = "Setup"
            overall_contribution = 0  # Setup doesn't count toward file progress

        # Update phase progress bar (shows phase-specific progress)
        if hasattr(self, "progress_display"):
            self.progress_display.update_phase_progress(phase_name, phase_progress)

            # Update overall file progress based on phase contribution
            if overall_contribution > 0:
                self.progress_display.update_current_file_progress(overall_contribution)

        # Note: We no longer need to reset or directly update current_file_progress here
        # because phase-based calculation above handles it correctly

    def _update_progress(self, progress_data):
        """Update transcription progress display."""
        if isinstance(progress_data, dict):
            file_name = Path(progress_data["file"]).name
            current = progress_data["current"]
            total = progress_data["total"]
            status = progress_data["status"]
            success = progress_data.get("success", True)
            text_length = progress_data.get("text_length", 0)

            status_icon = "✅" if success else "❌"

            # Track failures more accurately by maintaining a set
            if not hasattr(self, "_failed_files"):
                self._failed_files = set()

            if not success:
                self._failed_files.add(progress_data["file"])

            # Calculate completed/failed counts properly
            # current is 1-indexed, representing the current file being processed
            # So current-1 files have been fully processed before this one
            failed_count = len(self._failed_files)
            completed_count = current - failed_count

            # Debug logging for progress tracking
            logger.info(
                f"🔍 Progress Update Debug: current={current}, total_files={total}, completed={completed_count}, failed={failed_count}, success={success}"
            )

            # Reset current file progress when a file completes
            # This ensures the progress bar shows the correct percentage for completed files
            self.progress_display.current_file_progress = 0

            # Update simple progress display
            self.progress_display.update_progress(
                completed=completed_count, failed=failed_count, current_file=file_name
            )

            # Show detailed transcription result information
            if success and text_length > 0:
                self.append_log(
                    f"[{current}/{total}] {file_name}: {status_icon} {status}"
                )
                self.append_log(
                    f"   📝 Generated {text_length:,} characters of transcription text"
                )
            else:
                self.append_log(
                    f"[{current}/{total}] {file_name}: {status_icon} {status}"
                )
        else:
            self.append_log(f"Progress: {progress_data}")

    def _file_completed(self, current: int, total: int):
        """Handle transcription file completion."""
        if current < total:
            self.append_log(f"📁 Processing file {current + 1} of {total}...")

    def _processing_finished(
        self,
        completed_files: int = 0,
        failed_files: int = 0,
        failed_files_details: list | None = None,
    ):
        """Handle transcription completion."""
        # Calculate final statistics
        total_files = (
            self.transcription_worker.total_files if self.transcription_worker else 0
        )

        # Use actual counts from worker
        # If both are 0, it means old signal format was used - fall back to total_files
        # BUT only if we're not in a cancelled state
        if completed_files == 0 and failed_files == 0 and total_files > 0:
            # Check if this was a cancellation by looking at worker state
            if (
                self.transcription_worker
                and hasattr(self.transcription_worker, "cancellation_token")
                and self.transcription_worker.cancellation_token.is_cancelled
            ):
                # This was a cancellation, not a successful completion
                completed_files = 0
                failed_files = 0
            else:
                completed_files = (
                    total_files  # Legacy fallback for successful completion
                )

        # Complete the progress display
        self.progress_display.finish(completed_files, failed_files)

        # Rich log display removed - using main output_text area instead

        # Show appropriate completion message based on results
        if completed_files > 0 and failed_files == 0:
            self.append_log("\n✅ All transcriptions completed successfully!")
            self.append_log(
                "📋 Note: Transcriptions are processed in memory. Use the Summarization tab to save transcripts to markdown files."
            )
        elif completed_files > 0 and failed_files > 0:
            self.append_log(
                f"\n⚠️ Transcription completed with {completed_files} success(es) and {failed_files} failure(s)"
            )
        elif failed_files > 0:
            self.append_log(f"\n❌ All transcriptions failed ({failed_files} file(s))")
        elif completed_files == 0 and failed_files == 0 and total_files > 0:
            # Check if this was a cancellation
            if (
                self.transcription_worker
                and hasattr(self.transcription_worker, "cancellation_token")
                and self.transcription_worker.cancellation_token.is_cancelled
            ):
                self.append_log("\n⏹️ Transcription cancelled by user")
            else:
                self.append_log("\n✅ Processing completed (no files processed)")
        else:
            self.append_log("\n✅ Processing completed (no files processed)")

        # Show completion summary if there were files processed
        if total_files > 0:
            self._show_completion_summary(
                completed_files, failed_files, failed_files_details or []
            )

        # Hide progress bar and status (legacy)
        if hasattr(self, "file_progress_bar") and hasattr(
            self, "progress_status_label"
        ):
            self.file_progress_bar.setVisible(False)
            self.progress_status_label.setVisible(False)

        # Disable processing state (enables start, disables stop)
        self.set_processing_state(False)
        self.start_btn.setText(self._get_start_button_text())
        self.pipeline_status_label.setText("Ready to process")
        self.pipeline_status_label.setStyleSheet("color: #666;")

        # Override the "Ready" status from set_processing_state with specific completion status
        self.status_updated.emit("Transcription completed")

    def _on_worker_log_message(self, message: str) -> None:
        """Handle log messages from the worker thread.

        Args:
            message: The log message to display
        """
        # Append to GUI output panel
        self.append_log(message)

    def _processing_error(self, error_msg: str):
        """Handle transcription error."""
        # CRITICAL: Thread safety check - ensure we're on the main thread
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None or QThread.currentThread() != app.thread():
            logger.error(
                "🚨 CRITICAL: _processing_error called from background thread - BLOCKED!"
            )
            logger.error(f"Current thread: {QThread.currentThread()}")
            logger.error(f"Main thread: {QApplication.instance().thread()}")
            # Still log on any thread
            self.append_log(f"❌ Error: {error_msg}")
            return

        # Log error
        self.append_log(f"❌ Error: {error_msg}")

        # Check for authorization-related errors first
        if (
            "not properly authorized" in error_msg
            or "authorization" in error_msg.lower()
        ):
            # Show authorization error with restart instruction
            show_enhanced_error(
                self,
                "App Authorization Required",
                f"{error_msg}\n\n🔐 This is required for transcription to work properly.\n\n💡 Solution: Restart Skip the Podcast Desktop and complete the authorization process when prompted.",
                context="App requires proper authorization for transcription functionality",
            )
        elif "whisper.cpp binary not found" in error_msg:
            # Show helpful error dialog with cloud transcription suggestion
            show_enhanced_error(
                self,
                "Local Transcription Unavailable",
                f"{error_msg}\n\n💡 Suggestion: Use the 'Cloud Transcription' tab instead, which doesn't require local installation.",
                context="Missing whisper.cpp binary for local transcription",
            )
        elif "bundled dependencies not accessible" in error_msg:
            # Show bundled dependency error
            show_enhanced_error(
                self,
                "Bundled Dependencies Issue",
                f"{error_msg}\n\n🔧 This typically means the app wasn't properly authorized during installation.\n\n💡 Solution: Restart Skip the Podcast Desktop and complete the authorization process.",
                context="Bundled transcription dependencies not accessible",
            )
        else:
            # Standard error handling
            show_enhanced_error(
                self,
                "Transcription Error",
                error_msg,
                context="Local transcription using Whisper",
            )

        # Hide progress bar and status (legacy)
        if hasattr(self, "file_progress_bar") and hasattr(
            self, "progress_status_label"
        ):
            self.file_progress_bar.setVisible(False)
            self.progress_status_label.setVisible(False)

        # Disable processing state (enables start, disables stop)
        self.set_processing_state(False)
        self.start_btn.setText(self._get_start_button_text())
        self.pipeline_status_label.setText("Ready to process")
        self.pipeline_status_label.setStyleSheet("color: #666;")

        # Override the "Ready" status from set_processing_state with specific error status
        self.status_updated.emit("Transcription error - Ready")

    # Speaker assignment request handler removed - handled in Speaker Attribution tab only

    def _retry_failed_files(self):
        """Retry transcription for files that failed."""
        # Check if there are any failed items to retry
        if not hasattr(self, "failed_urls"):
            self.failed_urls = []
        if not hasattr(self, "failed_files"):
            self.failed_files = []

        total_failed = len(self.failed_urls) + len(self.failed_files)

        if total_failed == 0:
            self.append_log("ℹ️ No failed files to retry")
            return

        # Collect items to retry
        retry_items = []

        # Add failed URLs
        if self.failed_urls:
            for failed_item in self.failed_urls:
                retry_items.append(failed_item.get("url", ""))
            self.append_log(
                f"🔄 Retrying {len(self.failed_urls)} failed YouTube download(s)..."
            )

        # Add failed local files
        if self.failed_files:
            for failed_item in self.failed_files:
                file_path = failed_item.get("file", "")
                if file_path and Path(file_path).exists():
                    retry_items.append(file_path)
            self.append_log(
                f"🔄 Retrying {len(self.failed_files)} failed local file(s)..."
            )

        if not retry_items:
            self.append_log("⚠️ No valid items found to retry")
            return

        # Clear failed tracking for fresh retry
        self.failed_urls = []
        self.failed_files = []

        # Clear current file list and add retry items
        self.transcription_files.clear()

        for item in retry_items:
            self.transcription_files.addItem(str(item))

        self.append_log(f"✅ Loaded {len(retry_items)} item(s) for retry")

        # Automatically start the retry
        self.append_log("🚀 Starting retry...")
        self.run()

    def _stop_processing(self):
        """Stop the current transcription process.

        Note: If a file is currently being transcribed, it will complete before stopping.
        The stop will take effect between files or during URL processing.
        """
        self.append_log("⏹ Stop button clicked...")
        self.append_log("💡 Attempting graceful shutdown (will force stop if needed)...")

        # Immediately disable the stop button to prevent multiple clicks
        if hasattr(self, "stop_btn"):
            self.stop_btn.setEnabled(False)

        if self.transcription_worker:
            if self.transcription_worker.isRunning():
                self.append_log("⏹ Sending stop signal to worker...")

                # Set the stop flag and cancel the token - this is non-blocking
                self.transcription_worker.stop()

                # Use QTimer to handle cleanup asynchronously without blocking UI
                from PyQt6.QtCore import QTimer

                # Reset UI immediately to prevent user confusion
                self._reset_ui_after_stop()

                # Start async cleanup that won't block the UI
                QTimer.singleShot(100, lambda: self._async_cleanup_worker())
            else:
                self.append_log("⚠️ Worker exists but is not running (already stopped)")
                self._reset_ui_after_stop()
        else:
            self.append_log("⚠️ No active transcription worker found")
            self._reset_ui_after_stop()

    def _reset_ui_after_stop(self):
        """Reset UI state after stop is requested (non-blocking)."""
        # Reset UI state regardless of worker state
        self.progress_display.reset()
        self._failed_files = set()

        # Disable processing state (enables start, disables stop)
        self.set_processing_state(False)
        self.start_btn.setText(self._get_start_button_text())
        self.pipeline_status_label.setText("Stopping...")
        self.pipeline_status_label.setStyleSheet("color: #f59e0b;")  # Orange

        # Override the "Ready" status from set_processing_state with specific stop status
        self.status_updated.emit("Stopping transcription...")

    def _async_cleanup_worker(self):
        """Asynchronously clean up worker thread without blocking UI."""
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication

        if not self.transcription_worker:
            return

        # Process events to keep UI responsive
        QApplication.processEvents()

        # Check if worker stopped on its own (gracefully)
        if not self.transcription_worker.isRunning():
            self.append_log("✓ Transcription stopped gracefully")
            self.pipeline_status_label.setText("Ready to process")
            self.pipeline_status_label.setStyleSheet("color: #666;")
            self.status_updated.emit("Transcription stopped - Ready")
            return

        # Give it 5 seconds total for graceful shutdown, checking every 500ms
        attempts_remaining = getattr(self, "_cleanup_attempts", 10)

        if attempts_remaining > 0:
            self._cleanup_attempts = attempts_remaining - 1
            # Still running, check again in 500ms
            QTimer.singleShot(500, lambda: self._async_cleanup_worker())

            # Show countdown in UI
            seconds_left = attempts_remaining * 0.5
            self.pipeline_status_label.setText(f"Stopping... ({seconds_left:.1f}s)")
        else:
            # Timeout reached - force terminate
            self.append_log("⏹ Transcription in progress - forcing stop...")
            self.append_log("💡 Note: The current file's transcription was interrupted")

            # First, try to terminate any subprocess
            self._terminate_subprocess()

            # Then terminate the worker thread
            self.transcription_worker.terminate()

            # Give termination a moment to complete, then check
            QTimer.singleShot(1000, lambda: self._finalize_stop())

    def _terminate_subprocess(self):
        """Attempt to terminate any running subprocess."""
        try:
            # Access the audio processor through the worker
            if hasattr(self.transcription_worker, "audio_processor"):
                processor = self.transcription_worker.audio_processor
                if processor and hasattr(processor, "transcriber"):
                    transcriber = processor.transcriber
                    if transcriber and hasattr(transcriber, "terminate_subprocess"):
                        self.append_log("🛑 Terminating whisper subprocess...")
                        transcriber.terminate_subprocess()
        except Exception as e:
            logger.error(f"Error terminating subprocess: {e}")

    def _finalize_stop(self):
        """Finalize the stop process after termination."""
        if self.transcription_worker:
            if self.transcription_worker.isRunning():
                self.append_log("⚠️ Worker still running after termination attempt")
            else:
                self.append_log("✓ Transcription stopped successfully")

        # Reset cleanup counter for next time
        self._cleanup_attempts = 10

        # Final UI state
        self.pipeline_status_label.setText("Ready to process")
        self.pipeline_status_label.setStyleSheet("color: #666;")
        self.status_updated.emit("Transcription stopped - Ready")

    def _show_completion_summary(
        self, completed_files: int, failed_files: int, failed_files_details: list
    ):
        """Show detailed completion summary."""
        # CRITICAL: Thread safety check - ensure we're on the main thread
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None or QThread.currentThread() != app.thread():
            logger.error(
                "🚨 CRITICAL: _show_completion_summary called from background thread - BLOCKED!"
            )
            logger.error(f"Current thread: {QThread.currentThread()}")
            logger.error(f"Main thread: {QApplication.instance().thread()}")
            return

        # Get actual file information from worker if available
        successful_files = []
        total_chars = 0

        if self.transcription_worker and hasattr(
            self.transcription_worker, "successful_files"
        ):
            successful_files = self.transcription_worker.successful_files
            total_chars = sum(f.get("text_length", 0) for f in successful_files)
        else:
            # Fallback: Create basic entries if worker data not available
            for i in range(completed_files):
                successful_files.append({"file": f"File_{i+1}", "text_length": 0})

        # Use provided failed files details (contains both failed URLs and failed local files)
        failed_files_list = failed_files_details

        # Calculate processing time (mock)
        processing_time = 60.0  # Mock 1 minute

        # Get output directory
        output_dir = (
            self.output_dir_input.text() if hasattr(self, "output_dir_input") else None
        )

        # If output directory is empty or None, try to get it from settings
        if not output_dir or not output_dir.strip():
            output_dir = self._get_transcription_settings().get("output_dir")

        # Show summary dialog (safe on main thread)
        summary = TranscriptionCompletionSummary(self)

        # Connect the signal to switch to summarization tab and load files
        summary.switch_to_summarization.connect(
            lambda: self._switch_to_summarization_with_files(
                summary.successful_files, output_dir
            )
        )

        summary.show_summary(
            successful_files=successful_files,
            failed_files=failed_files_list,
            processing_time=processing_time,
            total_characters=total_chars,
            operation_type="transcription",
            output_dir=output_dir,
        )

    def _switch_to_summarization_with_files(
        self, successful_files: list[dict], output_dir: str | None
    ):
        """Switch to summarization tab, select database mode, check transcripts, and auto-start."""
        # First, switch to the summarization tab
        self.navigate_to_tab.emit("Summarize")

        # Get the main window to access the summarization tab
        main_window = self.window()
        if hasattr(main_window, "tabs"):
            # Find the summarization tab
            for i in range(main_window.tabs.count()):
                if main_window.tabs.tabText(i) == "Summarize":
                    summarization_tab = main_window.tabs.widget(i)

                    # Extract source_ids from successful files
                    source_ids = []
                    for file_info in successful_files:
                        # Get source_id from the file info
                        # Try multiple approaches to extract source_id
                        source_id = file_info.get("source_id")

                        if not source_id:
                            # Fallback: extract from file path
                            file_path = file_info.get("file") or file_info.get(
                                "saved_file_path"
                            )
                            if file_path:
                                # Remove _transcript suffix if present, get stem
                                source_id = Path(file_path).stem.replace(
                                    "_transcript", ""
                                )

                        if source_id:
                            source_ids.append(source_id)

                    if not source_ids:
                        if hasattr(summarization_tab, "append_log"):
                            summarization_tab.append_log(
                                "⚠️ Could not determine source IDs from transcribed files"
                            )
                        break

                    # Switch to Database mode
                    if hasattr(summarization_tab, "database_radio"):
                        summarization_tab.database_radio.setChecked(True)
                        # This will trigger _on_source_changed which refreshes the database list

                        # Small delay to ensure database list is refreshed
                        from PyQt6.QtCore import QTimer

                        def select_and_start():
                            """Select the transcribed items and auto-start summarization."""
                            # Check the boxes for our source_ids
                            if hasattr(summarization_tab, "db_table"):
                                checked_count = 0
                                for row in range(summarization_tab.db_table.rowCount()):
                                    # Get source_id from the title item's UserRole data
                                    title_item = summarization_tab.db_table.item(row, 1)
                                    if title_item:
                                        row_source_id = title_item.data(
                                            Qt.ItemDataRole.UserRole
                                        )
                                        if row_source_id in source_ids:
                                            # Check the checkbox in column 0
                                            checkbox_widget = (
                                                summarization_tab.db_table.cellWidget(
                                                    row, 0
                                                )
                                            )
                                            if checkbox_widget and hasattr(
                                                checkbox_widget, "setChecked"
                                            ):
                                                checkbox_widget.setChecked(True)
                                                checked_count += 1

                                if checked_count > 0:
                                    if hasattr(summarization_tab, "append_log"):
                                        summarization_tab.append_log(
                                            f"✅ Selected {checked_count} transcribed source(s) from database"
                                        )

                                    # Auto-start summarization
                                    if hasattr(summarization_tab, "_start_processing"):
                                        summarization_tab.append_log(
                                            "🚀 Auto-starting summarization..."
                                        )
                                        summarization_tab._start_processing()
                                else:
                                    if hasattr(summarization_tab, "append_log"):
                                        summarization_tab.append_log(
                                            "⚠️ Transcribed sources not found in database. They may need a moment to sync."
                                        )
                            else:
                                if hasattr(summarization_tab, "append_log"):
                                    summarization_tab.append_log(
                                        "⚠️ Database table not available"
                                    )

                        # Wait 300ms for database refresh to complete
                        QTimer.singleShot(300, select_and_start)
                    else:
                        if hasattr(summarization_tab, "append_log"):
                            summarization_tab.append_log(
                                "⚠️ Database mode not available in summarization tab"
                            )
                    break

    # Hardware recommendations methods moved to Settings tab

    def _get_transcription_settings(self) -> dict[str, Any]:
        """Get current transcription settings."""
        return {
            "model": self.model_combo.currentText(),
            "device": self.device_combo.currentText(),
            "language": self.language_combo.currentText(),  # Always pass the language, including "auto"
            "format": self.format_combo.currentText(),
            "timestamps": self.timestamps_checkbox.isChecked(),
            "diarization": self.diarization_checkbox.isChecked(),
            "overwrite": self.overwrite_checkbox.isChecked(),
            "enable_speaker_assignment": self.speaker_assignment_checkbox.isChecked(),
            "enable_color_coding": False,  # Always disabled - causes YAML corruption
            "output_dir": self.output_dir_input.text().strip() or None,
            # Thread management handled by dynamic resource system
            "batch_size": 16,  # Default batch size
            "omp_threads": max(1, min(8, os.cpu_count() or 4)),  # Default threads
            "max_concurrent": 1,  # Default to sequential for safety
            "processing_mode": "Sequential",  # Default mode
            "tokenizers_parallelism": False,  # Disabled: causes warnings and minimal benefit
            "mps_fallback": True,  # Enabled: MPS automatically falls back to CPU when needed
            "hf_token": getattr(
                self.settings.api_keys, "huggingface_token", None
            ),  # Add HF token for diarization
            "kwargs": {
                "diarization": self.diarization_checkbox.isChecked(),
                "omp_threads": max(1, min(8, os.cpu_count() or 4)),  # Default threads
                "batch_size": 16,  # Default batch size
                "hf_token": getattr(
                    self.settings.api_keys, "huggingface_token", None
                ),  # Also add to kwargs for AudioProcessor
            },
        }

    def validate_inputs(self) -> bool:
        """Validate inputs before processing."""
        # Check output directory
        output_dir = self.output_dir_input.text().strip()
        if not output_dir:
            self.show_error("Invalid Output", "Output directory must be selected.")
            return False

        if not Path(output_dir).parent.exists():
            self.show_error("Invalid Output", "Output directory parent doesn't exist")
            return False

        # Check speaker diarization requirements
        if self.diarization_checkbox.isChecked():
            # Check if diarization is available
            try:
                from knowledge_system.processors.diarization import (
                    get_diarization_installation_instructions,
                    is_diarization_available,
                )

                # TODO: Temporary fix - dependencies are installed but check may fail in GUI context
                # Skip the installation dialog loop and proceed with a simple availability check
                if not is_diarization_available():
                    # Try one more time with a direct import test
                    try:
                        pass

                        from knowledge_system.logger import get_logger

                        logger = get_logger(__name__)
                        logger.info(
                            "Diarization dependencies available via direct import test"
                        )
                    except ImportError:
                        self.show_error(
                            "Missing Diarization Dependencies",
                            "Speaker diarization requires additional dependencies.\n\n"
                            + get_diarization_installation_instructions()
                            + "\n\nAlternatively, disable speaker diarization to proceed.",
                        )
                        return False
            except ImportError:
                self.show_error(
                    "Missing Dependency",
                    "Speaker diarization requires 'pyannote.audio' to be installed.\n\n"
                    "Install it with: pip install -e '.[diarization]'\n\n"
                    "Please install this dependency or disable speaker diarization.",
                )
                return False

            # Check if HuggingFace token is configured
            hf_token = getattr(self.settings.api_keys, "huggingface_token", None)
            if not hf_token:
                self.show_warning(
                    "Missing HuggingFace Token",
                    "Speaker diarization requires a HuggingFace token to access the pyannote models.\n\n"
                    "Please configure your HuggingFace token in the Settings tab or disable speaker diarization.\n\n"
                    "You can get a free token at: https://huggingface.co/settings/tokens",
                )
                # Don't return False here, just warn - let the user proceed if they want

        return True

    def cleanup_workers(self):
        """Clean up any active workers."""
        if self.transcription_worker and self.transcription_worker.isRunning():
            # Set stop flag and terminate if needed
            if hasattr(self.transcription_worker, "should_stop"):
                self.transcription_worker.should_stop = True
            self.transcription_worker.terminate()
            self.transcription_worker.wait(3000)
        super().cleanup_workers()

    def _load_settings(self) -> None:
        """Load saved settings from session."""
        try:
            # Helper function to safely check if a widget is valid
            def is_widget_valid(widget):
                try:
                    if widget is None:
                        return False
                    # Try to access a property to verify the widget hasn't been deleted
                    _ = widget.objectName()
                    return True
                except RuntimeError:
                    # Widget has been deleted
                    return False

            # Block signals during loading to prevent redundant saves
            # Only include widgets that are valid
            candidate_widgets = [
                self.output_dir_input,
                self.model_combo,
                self.device_combo,
                self.language_combo,
                self.format_combo,
                self.timestamps_checkbox,
                self.diarization_checkbox,
                self.speaker_assignment_checkbox,
                self.color_coded_checkbox,
                self.enable_rss_mapping_checkbox,
                self.proxy_mode_combo,
                self.cookie_manager,
                self.min_delay_spinbox,
                self.max_delay_spinbox,
                self.randomization_spinbox,
            ]

            widgets_to_block = [w for w in candidate_widgets if is_widget_valid(w)]

            if len(widgets_to_block) != len(candidate_widgets):
                logger.warning(
                    f"Some widgets are not valid yet: {len(candidate_widgets) - len(widgets_to_block)} widgets skipped"
                )
                # If critical widgets are missing, skip loading settings
                if not all(
                    is_widget_valid(w)
                    for w in [self.model_combo, self.output_dir_input]
                ):
                    logger.warning(
                        "Critical widgets not available, skipping settings load"
                    )
                    return

            # Block all signals
            for widget in widgets_to_block:
                widget.blockSignals(True)

            try:
                # Load output directory - no hardcoded default
                saved_output_dir = self.gui_settings.get_output_directory(
                    self.tab_name, ""  # Empty string - require user selection
                )
                self.output_dir_input.setText(saved_output_dir)

                # Load model selection
                # Settings manager handles the hierarchy:
                # 1. Session state (last used)
                # 2. settings.yaml (transcription.whisper_model)
                # 3. Fallback to "medium" (default from config.py)
                saved_model = self.gui_settings.get_combo_selection(
                    self.tab_name,
                    "model",
                    "medium",  # Default to medium, not empty string
                )
                if saved_model:
                    index = self.model_combo.findText(saved_model)
                    if index >= 0:
                        self.model_combo.setCurrentIndex(index)
                    else:
                        # If saved model not found, fall back to medium
                        logger.warning(
                            f"Saved model '{saved_model}' not found in available models. "
                            f"Falling back to 'medium'."
                        )
                        index = self.model_combo.findText("medium")
                        if index >= 0:
                            self.model_combo.setCurrentIndex(index)

                # Load device selection
                saved_device = self.gui_settings.get_combo_selection(
                    self.tab_name, "device", "auto"
                )
                index = self.device_combo.findText(saved_device)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)

                # Load language selection
                saved_language = self.gui_settings.get_combo_selection(
                    self.tab_name,
                    "language",
                    "en",  # Default to English instead of auto
                )

                # Safety check: warn if unusual language is loaded
                if saved_language not in ["auto", "en", ""]:
                    logger.warning(
                        f"📍 Loading saved language setting: '{saved_language}'. "
                        f"Transcriptions will be in {saved_language.upper()}. "
                        f"Change to 'auto' or 'en' for English transcription."
                    )

                index = self.language_combo.findText(saved_language)
                if index >= 0:
                    self.language_combo.setCurrentIndex(index)

                # Load format selection
                saved_format = self.gui_settings.get_combo_selection(
                    self.tab_name, "format", "md"
                )
                index = self.format_combo.findText(saved_format)
                if index >= 0:
                    self.format_combo.setCurrentIndex(index)

                # Load checkbox states
                self.timestamps_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "include_timestamps", True
                    )
                )
                self.diarization_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name,
                        "enable_diarization",
                        True,  # Default to True for local transcription
                    )
                )

                # Load speaker assignment settings
                self.speaker_assignment_checkbox.setChecked(
                    self.gui_settings.get_checkbox_state(
                        self.tab_name, "enable_speaker_assignment", True
                    )
                )
                # ALWAYS start color-coded checkbox as unchecked (ignore saved settings)
                # This is a user preference that should default to off each session
                # Users complained it kept getting re-enabled from saved state
                self.color_coded_checkbox.setChecked(False)

            finally:
                # Always restore signals
                for widget in widgets_to_block:
                    try:
                        widget.blockSignals(False)
                    except RuntimeError:
                        # Widget was deleted, skip it
                        pass
            self.overwrite_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "overwrite_existing", True
                )
            )
            # Ensure diarization state is properly reflected in UI
            self._on_diarization_toggled(self.diarization_checkbox.isChecked())

            # Load RSS mapping checkbox state (default to False)
            self.enable_rss_mapping_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "enable_rss_mapping", False
                )
            )

            # Load proxy mode (0=Auto, 1=Always, 2=Never)
            saved_proxy_mode = self.gui_settings.get_combo_selection(
                self.tab_name, "proxy_mode", "Auto"
            )
            index = self.proxy_mode_combo.findText(saved_proxy_mode)
            if index >= 0:
                self.proxy_mode_combo.setCurrentIndex(index)
            else:
                # Fallback: default to Auto
                self.proxy_mode_combo.setCurrentIndex(0)

            # Load cookie files list (cookie auth is automatically enabled when files are present)
            cookie_files = self.gui_settings.get_list_setting(
                self.tab_name, "cookie_files", []
            )

            if cookie_files:
                logger.info(
                    f"📂 Loading {len(cookie_files)} cookie file(s): {[Path(f).name for f in cookie_files]}"
                )
                logger.info(f"   Full paths: {cookie_files}")
            else:
                logger.debug(f"📂 No cookie files to load")

            # Verify cookie_manager widget is valid before loading
            if not hasattr(self, "cookie_manager") or self.cookie_manager is None:
                logger.error(
                    "❌ Cookie manager widget not initialized! Cannot load cookie files."
                )
                return

            # Temporarily disconnect signal to prevent save during load
            try:
                self.cookie_manager.cookies_changed.disconnect(self._on_setting_changed)
                logger.debug("   Disconnected cookies_changed signal for loading")
            except:
                logger.debug("   cookies_changed signal was not connected")
                pass  # Ignore if not connected

            if cookie_files:
                logger.debug(
                    f"   Calling cookie_manager.set_cookie_files() with {len(cookie_files)} files"
                )
                self.cookie_manager.set_cookie_files(cookie_files)

                # Verify the files were actually set
                loaded_files = self.cookie_manager.get_all_cookie_files()
                if loaded_files:
                    logger.info(
                        f"✅ Successfully loaded {len(loaded_files)} cookie file(s) into UI"
                    )
                else:
                    logger.error(
                        f"❌ Failed to load cookie files into UI! Expected {len(cookie_files)}, got 0"
                    )

            # ALWAYS reconnect signal, even if no cookies were loaded
            # This ensures future cookie additions will be saved
            self.cookie_manager.cookies_changed.connect(self._on_setting_changed)
            logger.debug("✅ Cookie file change signal reconnected")

            # Load rate limiting settings
            self.min_delay_spinbox.setValue(
                self.gui_settings.get_spinbox_value(self.tab_name, "min_delay", 180)
            )
            self.max_delay_spinbox.setValue(
                self.gui_settings.get_spinbox_value(self.tab_name, "max_delay", 300)
            )
            self.randomization_spinbox.setValue(
                self.gui_settings.get_spinbox_value(self.tab_name, "randomization", 25)
            )

            logger.debug(f"Loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")

    def _save_settings(self) -> None:
        """Save current settings to session."""
        try:
            # Save output directory
            self.gui_settings.set_output_directory(
                self.tab_name, self.output_dir_input.text()
            )

            # Save combo selections
            self.gui_settings.set_combo_selection(
                self.tab_name, "model", self.model_combo.currentText()
            )
            self.gui_settings.set_combo_selection(
                self.tab_name, "device", self.device_combo.currentText()
            )
            self.gui_settings.set_combo_selection(
                self.tab_name, "language", self.language_combo.currentText()
            )
            self.gui_settings.set_combo_selection(
                self.tab_name, "format", self.format_combo.currentText()
            )
            # Processing mode handled by dynamic resource management

            # Save checkbox states
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "include_timestamps",
                self.timestamps_checkbox.isChecked(),
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "enable_diarization",
                self.diarization_checkbox.isChecked(),
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "enable_speaker_assignment",
                self.speaker_assignment_checkbox.isChecked(),
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "enable_color_coding",
                self.color_coded_checkbox.isChecked(),
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "overwrite_existing", self.overwrite_checkbox.isChecked()
            )

            # Save RSS mapping checkbox state
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "enable_rss_mapping",
                self.enable_rss_mapping_checkbox.isChecked(),
            )

            # Save proxy mode
            self.gui_settings.set_combo_selection(
                self.tab_name, "proxy_mode", self.proxy_mode_combo.currentText()
            )

            # Save cookie files list (cookie auth is automatically enabled when files are present)
            cookie_files = self.cookie_manager.get_all_cookie_files()
            logger.info(
                f"💾 Saving {len(cookie_files)} cookie file(s): {[Path(f).name for f in cookie_files] if cookie_files else '[]'}"
            )
            logger.debug(f"   Full paths: {cookie_files}")
            self.gui_settings.set_list_setting(
                self.tab_name, "cookie_files", cookie_files
            )
            logger.debug(
                f"   ✅ Cookie files written to session: {self.tab_name}.cookie_files"
            )

            # Save rate limiting settings
            self.gui_settings.set_spinbox_value(
                self.tab_name, "min_delay", self.min_delay_spinbox.value()
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name, "max_delay", self.max_delay_spinbox.value()
            )
            self.gui_settings.set_spinbox_value(
                self.tab_name, "randomization", self.randomization_spinbox.value()
            )

            logger.debug(f"Saved settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")

    def _on_setting_changed(self):
        """Called when any setting changes to automatically save."""
        self._save_settings()

    def _validate_cookie_settings(self) -> bool:
        """Validate cookie settings before starting YouTube downloads.

        Returns:
            bool: True if validation passes, False otherwise
        """
        from pathlib import Path

        # Check if cookie files are provided and validate them
        cookie_files = self.cookie_manager.get_all_cookie_files()

        if cookie_files:
            # Cookie files specified - verify they exist
            missing_files = [f for f in cookie_files if not Path(f).exists()]
            if missing_files:
                self.show_warning(
                    "Cookie Files Not Found",
                    f"The following cookie file(s) do not exist:\n\n"
                    + "\n".join(missing_files)
                    + "\n\nPlease select valid cookie files or remove them from the list.",
                )
                return False

        return True

    def _on_model_changed(self):
        """Called when the model selection changes - validate and potentially download model."""
        self._save_settings()

        # Get the selected model
        selected_model = self.model_combo.currentText()

        # Update status to "checking"
        self.model_status_label.setText("🔄 Checking...")
        self.model_status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.model_status_label.setToolTip("Checking model availability...")

        # Start model validation in background thread
        self._start_model_validation(selected_model)

    def _start_model_validation(self, model_name: str):
        """Start background model validation/download."""
        from PyQt6.QtCore import QThread, pyqtSignal

        class ModelValidationWorker(QThread):
            """Worker thread for model validation/download."""

            validation_completed = pyqtSignal(
                bool, str, str
            )  # success, model_name, message
            download_progress = pyqtSignal(
                str, int, str
            )  # model_name, percent, message

            def __init__(self, model_name: str):
                super().__init__()
                self.model_name = model_name

            def run(self):
                """Validate model availability and download if needed."""
                try:
                    from ...processors.whisper_cpp_transcribe import (
                        WhisperCppTranscribeProcessor,
                    )

                    # Create a progress callback for downloads
                    def progress_callback(progress_data):
                        if isinstance(progress_data, dict):
                            status = progress_data.get("status", "")
                            percent = int(progress_data.get("percent", 0))
                            message = progress_data.get("message", "")

                            if status in ["downloading", "starting_download"]:
                                self.download_progress.emit(
                                    self.model_name, percent, message
                                )
                            elif status == "error":
                                # Download failed (e.g., not enough memory)
                                self.validation_completed.emit(
                                    False, self.model_name, message
                                )
                                return

                    # Create processor to trigger model validation/download
                    processor = WhisperCppTranscribeProcessor(
                        model=self.model_name, progress_callback=progress_callback
                    )

                    # This will download the model if not present
                    model_path = processor._download_model(
                        self.model_name, progress_callback
                    )

                    if model_path and model_path.exists():
                        size_mb = model_path.stat().st_size / (1024 * 1024)
                        self.validation_completed.emit(
                            True, self.model_name, f"Model ready ({size_mb:.0f}MB)"
                        )
                    else:
                        self.validation_completed.emit(
                            False, self.model_name, "Model not available"
                        )

                except Exception as e:
                    self.validation_completed.emit(
                        False, self.model_name, f"Error: {str(e)}"
                    )

        # Create and start worker
        self._model_validation_worker = ModelValidationWorker(model_name)
        self._model_validation_worker.validation_completed.connect(
            self._on_model_validation_completed
        )
        self._model_validation_worker.download_progress.connect(
            self._on_model_download_progress
        )
        self._model_validation_worker.start()

    def _on_model_download_progress(self, model_name: str, percent: int, message: str):
        """Handle model download progress updates."""
        if (
            model_name == self.model_combo.currentText()
        ):  # Only update if still selected
            self.model_status_label.setText(f"📥 {percent}%")
            self.model_status_label.setStyleSheet("color: blue; font-weight: bold;")
            self.model_status_label.setToolTip(f"Downloading {model_name}: {message}")

            # Log progress to main output
            self.append_log(f"📥 {message}")

    def _on_model_validation_completed(
        self, success: bool, model_name: str, message: str
    ):
        """Handle model validation completion."""
        if (
            model_name == self.model_combo.currentText()
        ):  # Only update if still selected
            if success:
                self.model_status_label.setText("✅ Ready")
                self.model_status_label.setStyleSheet(
                    "color: green; font-weight: bold;"
                )
                self.model_status_label.setToolTip(
                    f"Model {model_name} is ready: {message}"
                )
                self.append_log(f"✅ Model {model_name} ready: {message}")
            else:
                self.model_status_label.setText("❌ Error")
                self.model_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.model_status_label.setToolTip(
                    f"Model {model_name} error: {message}"
                )
                self.append_log(f"❌ Model {model_name} error: {message}")

        # Clean up worker
        if hasattr(self, "_model_validation_worker"):
            self._model_validation_worker.deleteLater()
            del self._model_validation_worker

    def _on_processor_progress(self, message: str, percentage: int):
        """Handle progress updates from the processor log integrator."""
        # Just log the message - simple progress bar doesn't need this

    def _on_processor_status(self, status: str):
        """Handle status updates from the processor log integrator."""
        # Add rich processor status to our regular log output
        self.append_log(f"🔧 {status}")

    def _on_diarization_toggled(self, checked: bool):
        """Handle toggling of diarization checkbox."""
        # Enable/disable speaker assignment options based on diarization setting
        self.speaker_assignment_checkbox.setEnabled(checked)
        # Note: color_coded_checkbox is always disabled (feature causes YAML issues)

        if not checked:
            # If diarization is disabled, also disable speaker assignment features
            self.speaker_assignment_checkbox.setChecked(False)
