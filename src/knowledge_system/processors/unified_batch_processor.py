"""
Unified Batch Processor for YouTube URLs and Local Files.

This module provides a unified batch processing interface that works identically
for both CLI and GUI modes, with maximum parallelization based on system constraints.
"""

import gc
import os
import shutil
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import psutil

from ..logger import get_logger
from ..utils.cancellation import CancellationToken
from ..utils.hardware_detection import HardwareDetector
from ..utils.youtube_utils import expand_playlist_urls_with_metadata, is_youtube_url

logger = get_logger(__name__)


class UnifiedBatchProcessor:
    """
    Unified batch processor that handles both YouTube URLs and local files
    with maximum parallelization based on system constraints.

    Features:
    - Automatic resource detection and optimization
    - Dynamic concurrency adjustment based on memory pressure
    - PacketStream proxy management for YouTube downloads
    - Download-all vs conveyor belt mode selection
    - Unified progress reporting for CLI and GUI
    """

    def __init__(
        self,
        items: list[str | Path],
        config: dict[str, Any],
        progress_callback: Callable[[int, int, str], None] | None = None,
        url_completed_callback: Callable[[str, bool, str], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ):
        """
        Initialize the unified batch processor.

        Args:
            items: List of YouTube URLs, playlist URLs, or local file paths
            config: Processing configuration
            progress_callback: Called with (current, total, message)
            url_completed_callback: Called with (url/path, success, message)
            cancellation_token: For cancellation support
        """
        self.items = items
        self.config = config
        self.progress_callback = progress_callback or self._default_progress
        self.url_completed_callback = (
            url_completed_callback or self._default_url_completed
        )
        self.cancellation_token = cancellation_token or CancellationToken()

        # Resource management
        self.memory_handler = MemoryPressureHandler()
        self.hardware_detector = HardwareDetector()
        self.hardware_specs = self.hardware_detector.detect_hardware()

        # Processing state
        self.processed_count = 0
        self.successful_count = 0
        self.failed_count = 0
        self.failed_items = []
        self.successful_items = []

        # Determine processing strategy
        self.should_stop = False
        self._analyze_items()
        self._determine_processing_strategy()

    def _default_progress(self, current: int, total: int, message: str):
        """Default progress callback for CLI mode."""
        percent = (current / total * 100) if total > 0 else 0
        print(f"[{percent:5.1f}%] {current}/{total} - {message}")

    def _default_url_completed(self, item: str, success: bool, message: str):
        """Default completion callback for CLI mode."""
        status = "✅" if success else "❌"
        print(
            f"{status} {Path(item).name if not is_youtube_url(item) else item[:50]}: {message}"
        )

    def _analyze_items(self):
        """Analyze input items and expand playlists."""
        logger.info(f"Analyzing {len(self.items)} input items...")

        # Separate YouTube URLs from local files
        youtube_urls = []
        local_files = []

        for item in self.items:
            item_str = str(item)
            if is_youtube_url(item_str):
                youtube_urls.append(item_str)
            else:
                local_files.append(Path(item))

        # Expand YouTube playlists
        if youtube_urls:
            logger.info(
                f"Expanding {len(youtube_urls)} YouTube URLs (checking for playlists)..."
            )
            expansion_result = expand_playlist_urls_with_metadata(youtube_urls)
            self.expanded_youtube_urls = expansion_result["expanded_urls"]
            self.playlist_info = expansion_result["playlist_info"]

            # Log playlist information
            if self.playlist_info:
                total_playlist_videos = sum(
                    p["total_videos"] for p in self.playlist_info
                )
                logger.info(
                    f"Found {len(self.playlist_info)} playlist(s) with {total_playlist_videos} total videos"
                )
                for i, playlist in enumerate(self.playlist_info, 1):
                    title = playlist.get("title", "Unknown Playlist")
                    video_count = playlist.get("total_videos", 0)
                    logger.info(f"  {i}. {title} ({video_count} videos)")
        else:
            self.expanded_youtube_urls = []
            self.playlist_info = []

        self.local_files = local_files
        self.total_items = len(self.expanded_youtube_urls) + len(self.local_files)

        logger.info(
            f"Analysis complete: {len(self.expanded_youtube_urls)} YouTube videos, {len(self.local_files)} local files"
        )

    def _determine_processing_strategy(self):
        """Determine optimal processing strategy based on item count and resources."""
        from ..utils.batch_processing import calculate_memory_safe_concurrency

        # Check if we should use batch processing (>3 items triggers advanced processing)
        if self.total_items <= 3:
            self.use_batch_processing = False
            self.max_concurrent = 1
            logger.info(f"Using sequential processing for {self.total_items} items")
            return

        self.use_batch_processing = True

        # Calculate optimal concurrency
        memory_gb = psutil.virtual_memory().total / (1024**3)
        cpu_cores = os.cpu_count() or 4

        self.max_concurrent = calculate_memory_safe_concurrency(memory_gb, cpu_cores)

        # Determine batch strategy for YouTube downloads
        if self.expanded_youtube_urls:
            self.download_concurrency = self._calculate_download_concurrency()
            self.batch_size = self._calculate_optimal_batch_size()

            # Choose between download-all and conveyor belt mode
            if (
                self.config.get("download_all_mode", False)
                or len(self.expanded_youtube_urls) <= 50
            ):
                self.youtube_processing_mode = "download_all"
                logger.info("Using download-all mode for YouTube videos")
            else:
                self.youtube_processing_mode = "conveyor_belt"
                logger.info(
                    f"Using conveyor belt mode with batch size {self.batch_size}"
                )
        else:
            self.download_concurrency = 0
            self.batch_size = 0
            self.youtube_processing_mode = None

        logger.info(
            f"Batch processing strategy: max_concurrent={self.max_concurrent}, download_concurrency={self.download_concurrency}"
        )

    def _calculate_download_concurrency(self) -> int:
        """Calculate safe download concurrency based on proxy limits and system resources."""
        # Use optimized logic for high-end systems
        base_download_limit = min(12, max(4, self.hardware_specs.cpu_cores // 2))

        # Check current system load
        memory = psutil.virtual_memory()
        if memory.percent > 85:
            download_concurrency = 2
            logger.info(
                f"High memory usage ({memory.percent:.1f}%) - limiting downloads to 2 concurrent"
            )
        elif memory.percent > 70:
            download_concurrency = min(4, base_download_limit)
            logger.info(
                f"Moderate memory usage ({memory.percent:.1f}%) - limiting downloads to 4 concurrent"
            )
        else:
            download_concurrency = base_download_limit
            logger.info(
                f"Good memory availability ({memory.percent:.1f}%) - allowing {base_download_limit} concurrent downloads"
            )

        # Conservative PacketStream limit (can handle more but be respectful)
        final_concurrency = min(download_concurrency, 12)
        logger.info(f"Download concurrency: {final_concurrency} parallel sessions")
        return final_concurrency

    def _calculate_optimal_batch_size(self) -> int:
        """Calculate optimal batch size based on available disk space and intelligent pacing."""
        try:
            output_dir = Path(self.config.get("output_dir", "."))
            disk_usage = shutil.disk_usage(output_dir)
            available_gb = disk_usage.free / (1024**3)

            # Realistic space needed per audio file (~10MB for 10min video = 1MB/min)
            space_per_audio_gb = 0.01  # 10MB average

            # Conservative batch size based on available space
            available_for_audio = max(0, available_gb - 2.0)  # Reserve 2GB
            max_simultaneous_files = int(available_for_audio / space_per_audio_gb)
            batch_size = max(10, min(100, max_simultaneous_files // 2))

            # Intelligent pacing adjustment
            try:
                from ..utils.intelligent_pacing import (
                    create_pacing_config_from_settings,
                    get_pacing_manager,
                )

                pacing_config = create_pacing_config_from_settings()
                pacing_manager = get_pacing_manager(pacing_config)
                pacing_status = pacing_manager.get_pacing_status()

                # Adjust batch size based on processing pipeline
                processing_ratio = pacing_status.get(
                    "processing_to_download_ratio", 1.0
                )
                if processing_ratio > 5.0:  # Processing is much slower
                    batch_size = max(3, batch_size // 2)  # Smaller batches
                    logger.info(
                        f"Reducing batch size to {batch_size} due to slow processing pipeline"
                    )
                elif processing_ratio > 2.0:  # Processing is slower
                    batch_size = max(
                        5, int(batch_size * 0.75)
                    )  # Slightly smaller batches
                    logger.info(
                        f"Adjusting batch size to {batch_size} due to processing pipeline timing"
                    )

                # Adjust for rate limiting
                rate_limit_freq = pacing_status.get("rate_limit_frequency", 0.0)
                if rate_limit_freq > 1.0:  # Frequent rate limiting
                    batch_size = max(2, batch_size // 3)  # Much smaller batches
                    logger.info(
                        f"Reducing batch size to {batch_size} due to rate limiting"
                    )

                # Adjust for processing queue size
                queue_size = pacing_status.get("processing_queue_size", 0)
                if queue_size > 10:  # Large processing queue
                    batch_size = max(2, batch_size // 2)  # Smaller batches
                    logger.info(
                        f"Reducing batch size to {batch_size} due to large processing queue ({queue_size})"
                    )

            except Exception as pacing_error:
                logger.debug(
                    f"Could not get pacing status for batch size adjustment: {pacing_error}"
                )

            logger.info(
                f"Calculated batch size: {batch_size} (based on {available_gb:.1f}GB available)"
            )
            return batch_size

        except Exception as e:
            logger.error(f"Error calculating batch size: {e}")
            return 50  # Safe default

    def process_all(self) -> dict[str, Any]:
        """
        Process all items with optimal parallelization.

        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting unified batch processing: {self.total_items} items")

        try:
            # Process YouTube videos if any
            if self.expanded_youtube_urls:
                if self.youtube_processing_mode == "download_all":
                    self._process_youtube_download_all()
                else:
                    self._process_youtube_conveyor_belt()

            # Process local files if any
            if self.local_files:
                self._process_local_files()

            # Final results
            return {
                "successful": self.successful_count,
                "failed": self.failed_count,
                "items_processed": self.successful_items,
                "failed_items": self.failed_items,
                "total_items": self.total_items,
                "youtube_urls": len(self.expanded_youtube_urls),
                "local_files": len(self.local_files),
                "processing_mode": (
                    "batch" if self.use_batch_processing else "sequential"
                ),
            }

        except Exception as e:
            logger.error(f"Unified batch processing failed: {e}")
            raise

    def _process_youtube_download_all(self):
        """Process YouTube videos using download-all strategy with optimized concurrency."""
        logger.info("=== YOUTUBE DOWNLOAD-ALL MODE ===")
        logger.info(
            f"Using {self.download_concurrency} concurrent downloads, {self.max_concurrent} concurrent processing"
        )

        # Phase 1: Download all audio files in parallel using our optimized concurrency
        self.progress_callback(
            0, self.total_items, "📥 Phase 1: Downloading all YouTube audio files..."
        )

        downloaded_files = self._download_youtube_parallel(self.expanded_youtube_urls)

        download_success_count = len(downloaded_files)
        logger.info(
            f"Downloaded {download_success_count}/{len(self.expanded_youtube_urls)} audio files"
        )

        # Phase 2: Process all downloaded audio with parallel diarization
        if downloaded_files:
            self.progress_callback(
                0,
                len(downloaded_files),
                f"🎙️ Phase 2: Processing {len(downloaded_files)} audio files with diarization...",
            )
            self._process_downloaded_youtube_audio(downloaded_files)

    def _download_youtube_parallel(self, urls: list[str]) -> dict[str, Path]:
        """Download YouTube audio files in parallel with optimized concurrency."""

        logger.info(
            f"Starting parallel downloads: {len(urls)} URLs with {self.download_concurrency} concurrent sessions"
        )

        downloaded_files = {}

        with ThreadPoolExecutor(max_workers=self.download_concurrency) as executor:
            # Submit all download tasks
            future_to_url = {
                executor.submit(self._download_single_youtube_audio, url): url
                for url in urls
            }

            completed = 0
            for future in as_completed(future_to_url):
                if self.should_stop or self.cancellation_token.is_cancelled():
                    break

                url = future_to_url[future]

                try:
                    audio_file = future.result()
                    if audio_file and audio_file.exists():
                        downloaded_files[url] = audio_file
                        logger.debug(f"Successfully downloaded: {url}")
                    else:
                        logger.warning(f"Download failed: {url}")

                except Exception as e:
                    logger.error(f"Download error for {url}: {e}")

                completed += 1
                self.progress_callback(
                    completed,
                    len(urls),
                    f"📥 Downloaded {completed}/{len(urls)} audio files",
                )

        logger.info(
            f"Completed downloads: {len(downloaded_files)}/{len(urls)} successful"
        )
        return downloaded_files

    def _download_single_youtube_audio(self, url: str) -> Path | None:
        """Download audio for a single YouTube URL."""
        try:
            from ..processors.youtube_transcript import YouTubeTranscriptProcessor

            # Create processor for this download
            processor = YouTubeTranscriptProcessor(
                whisper_model=self.config.get("model", "base"),
                use_whisper_cpp=self.config.get("use_whisper_cpp", False),
                cancellation_token=self.cancellation_token,
            )

            # Extract video ID and create output filename
            import hashlib

            video_id = (
                url.split("v=")[-1].split("&")[0]
                if "v=" in url
                else hashlib.md5(url.encode()).hexdigest()[:8]
            )

            output_dir = Path(self.config.get("output_dir", "."))
            audio_file = output_dir / f"{video_id}_audio.wav"

            # Download audio only
            success = processor._download_youtube_audio(url, audio_file)

            if success and audio_file.exists():
                return audio_file
            else:
                return None

        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return None

    def _process_youtube_conveyor_belt(self):
        """Process YouTube videos using conveyor belt strategy."""
        from ..gui.workers.youtube_batch_worker import YouTubeBatchWorker

        logger.info("=== YOUTUBE CONVEYOR BELT MODE ===")

        batch_worker = YouTubeBatchWorker(self.expanded_youtube_urls, self.config)

        # Process in batches
        for batch_start in range(0, len(self.expanded_youtube_urls), self.batch_size):
            if self.should_stop or self.cancellation_token.is_cancelled():
                break

            batch_end = min(
                batch_start + self.batch_size, len(self.expanded_youtube_urls)
            )
            current_batch = self.expanded_youtube_urls[batch_start:batch_end]

            logger.info(
                f"Processing YouTube batch {batch_start//self.batch_size + 1}: URLs {batch_start+1}-{batch_end}"
            )

            # Process current batch
            batch_worker._process_batch_conveyor_belt(current_batch, batch_start)

    def _process_downloaded_youtube_audio(self, downloaded_files: dict[str, Path]):
        """Process pre-downloaded YouTube audio files with parallel diarization."""
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(self._process_single_youtube_item, url, audio_file): url
                for url, audio_file in downloaded_files.items()
            }

            completed = 0
            for future in as_completed(future_to_url):
                if self.should_stop or self.cancellation_token.is_cancelled():
                    break

                url = future_to_url[future]

                try:
                    success, message = future.result()

                    if success:
                        self._record_success(url, message)
                    else:
                        self._record_failure(url, message)

                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    self._record_failure(url, f"Processing error: {str(e)}")

                completed += 1
                self.progress_callback(
                    self.processed_count,
                    self.total_items,
                    f"🎙️ Processed {completed}/{len(downloaded_files)} YouTube videos",
                )

    def _process_local_files(self):
        """Process local files with parallel processing."""
        logger.info(f"=== PROCESSING {len(self.local_files)} LOCAL FILES ===")

        if not self.use_batch_processing:
            # Sequential processing for ≤3 files
            for i, file_path in enumerate(self.local_files):
                if self.should_stop or self.cancellation_token.is_cancelled():
                    break

                self.progress_callback(
                    self.processed_count,
                    self.total_items,
                    f"Processing {file_path.name}...",
                )

                success, message = self._process_single_local_file(file_path)

                if success:
                    self._record_success(str(file_path), message)
                else:
                    self._record_failure(str(file_path), message)
        else:
            # Parallel processing for >3 files
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                future_to_file = {
                    executor.submit(
                        self._process_single_local_file, file_path
                    ): file_path
                    for file_path in self.local_files
                }

                completed = 0
                for future in as_completed(future_to_file):
                    if self.should_stop or self.cancellation_token.is_cancelled():
                        break

                    file_path = future_to_file[future]

                    try:
                        success, message = future.result()

                        if success:
                            self._record_success(str(file_path), message)
                        else:
                            self._record_failure(str(file_path), message)

                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
                        self._record_failure(
                            str(file_path), f"Processing error: {str(e)}"
                        )

                    completed += 1
                    self.progress_callback(
                        self.processed_count,
                        self.total_items,
                        f"Processed {completed}/{len(self.local_files)} local files",
                    )

    def _process_single_youtube_item(
        self, url: str, audio_file: Path
    ) -> tuple[bool, str]:
        """Process a single YouTube URL using the transcription service."""
        try:
            from ..services.transcription_service import TranscriptionService

            service = TranscriptionService(
                whisper_model=self.config.get("model", "base"),
                download_thumbnails=self.config.get("download_thumbnails", False),
                use_whisper_cpp=self.config.get("use_whisper_cpp", False),
            )

            result = service.transcribe_youtube_url(
                url,
                download_thumbnails=self.config.get("download_thumbnails", False),
                output_dir=self.config.get("output_dir"),
                include_timestamps=self.config.get("timestamps", True),
                enable_diarization=self.config.get("enable_diarization", False),
                require_diarization=False,  # Allow fallback when diarization fails
                overwrite=self.config.get("overwrite", False),
            )

            if result["success"]:
                return True, "Successfully processed with diarization"
            else:
                error_msg = result.get("error", "Unknown error")
                return False, error_msg

        except Exception as e:
            return False, f"Processing exception: {str(e)}"

    def _process_single_local_file(self, file_path: Path) -> tuple[bool, str]:
        """Process a single local file."""
        try:
            from ..services.transcription_service import TranscriptionService

            service = TranscriptionService(
                whisper_model=self.config.get("model", "base"),
                download_thumbnails=False,  # Not applicable for local files
                use_whisper_cpp=self.config.get("use_whisper_cpp", False),
            )

            result = service.transcribe_input(
                file_path,
                download_thumbnails=False,
                output_dir=self.config.get("output_dir"),
                include_timestamps=self.config.get("timestamps", True),
            )

            if result["success"]:
                return True, f"Successfully transcribed {file_path.name}"
            else:
                return False, result.get("error", "Unknown error")

        except Exception as e:
            return False, f"Processing exception: {str(e)}"

    def _record_success(self, item: str, message: str):
        """Record successful processing."""
        self.successful_count += 1
        self.processed_count += 1
        self.successful_items.append(item)
        self.url_completed_callback(item, True, message)

    def _record_failure(self, item: str, error: str):
        """Record failed processing."""
        self.failed_count += 1
        self.processed_count += 1
        self.failed_items.append({"item": item, "error": error})
        self.url_completed_callback(item, False, error)

    def stop(self):
        """Stop processing."""
        self.should_stop = True
        if self.cancellation_token:
            self.cancellation_token.cancel()


class MemoryPressureHandler:
    """Handles memory pressure situations with various mitigation strategies."""

    def __init__(
        self, warning_threshold=85, critical_threshold=95, emergency_threshold=98
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.emergency_threshold = emergency_threshold
        self.pressure_level = 0  # 0=normal, 1=warning, 2=critical, 3=emergency
        self.last_gc_time = 0

    def check_memory_pressure(self) -> tuple[int, str]:
        """Check current memory pressure and return (level, message)."""
        memory = psutil.virtual_memory()
        percent = memory.percent

        if percent >= self.emergency_threshold:
            self.pressure_level = 3
            return 3, f"EMERGENCY memory pressure: {percent:.1f}% - stopping new tasks"
        elif percent >= self.critical_threshold:
            self.pressure_level = 2
            return (
                2,
                f"CRITICAL memory pressure: {percent:.1f}% - forcing garbage collection and reducing concurrency",
            )
        elif percent >= self.warning_threshold:
            self.pressure_level = 1
            return 1, f"Memory pressure warning: {percent:.1f}% - monitoring closely"
        else:
            self.pressure_level = 0
            return 0, f"Memory normal: {percent:.1f}%"

    def mitigate_pressure(self, current_concurrency: int) -> tuple[int, bool]:
        """
        Apply mitigation strategies and return (adjusted_concurrency, should_pause).

        Returns:
            tuple: (new_concurrency, should_pause_processing)
        """
        current_time = time.time()

        if self.pressure_level >= 3:  # Emergency
            return 0, True

        elif self.pressure_level >= 2:  # Critical
            if current_time - self.last_gc_time > 10:
                logger.info(
                    "Forcing garbage collection due to critical memory pressure"
                )
                gc.collect()
                self.last_gc_time = current_time
                time.sleep(0.5)

            new_concurrency = max(1, current_concurrency // 2)
            return new_concurrency, False

        elif self.pressure_level >= 1:  # Warning
            new_concurrency = max(1, current_concurrency - 1)
            return new_concurrency, False

        else:  # Normal
            return current_concurrency, False
