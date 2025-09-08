"""
YouTube Batch Processing Worker with Intelligent Resource Management.

Enhanced Features:
- Memory pressure handling with automatic mitigation
- Download-all mode for slow internet connections
- Conveyor belt processing for balanced resource usage
- Dynamic concurrency adjustment based on system resources
- Crash recovery with persistent audio storage
"""

import gc
import os
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import psutil
from PyQt6.QtCore import QThread, pyqtSignal

from ...logger import get_logger
from ...processors.youtube_transcript import YouTubeTranscriptProcessor
from ...utils.cancellation import CancellationToken
from ...utils.hardware_detection import HardwareDetector

logger = get_logger(__name__)


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
            # Stop processing completely until memory recovers
            return 0, True

        elif self.pressure_level >= 2:  # Critical
            # Force garbage collection if we haven't done it recently
            if current_time - self.last_gc_time > 10:  # At most once per 10 seconds
                logger.info(
                    "Forcing garbage collection due to critical memory pressure"
                )
                gc.collect()
                self.last_gc_time = current_time
                time.sleep(0.5)  # Brief pause to let GC work

            # Reduce concurrency aggressively
            new_concurrency = max(1, current_concurrency // 2)
            return new_concurrency, False

        elif self.pressure_level >= 1:  # Warning
            # Slightly reduce concurrency
            new_concurrency = max(1, current_concurrency - 1)
            return new_concurrency, False

        else:  # Normal
            return current_concurrency, False


class YouTubeBatchWorker(QThread):
    """
    Enhanced YouTube batch processing worker with advanced resource management.

    Features:
    - Memory pressure handling with automatic mitigation
    - Download-all mode for users with slow internet
    - Conveyor belt mode for balanced resource usage
    - Dynamic concurrency adjustment
    - Crash recovery with persistent audio storage
    """

    # Progress signals
    progress_updated = pyqtSignal(int, int, str)  # current, total, message
    url_completed = pyqtSignal(str, bool, str)  # url, success, message
    batch_status = pyqtSignal(dict)  # batch statistics
    resource_warning = pyqtSignal(str)  # resource warnings
    memory_pressure = pyqtSignal(int, str)  # pressure level, message

    # Final signals
    extraction_finished = pyqtSignal(dict)  # final results
    extraction_error = pyqtSignal(str)  # fatal errors

    def __init__(self, urls: list[str], config: dict[str, Any], parent=None):
        super().__init__(parent)
        self.urls = urls
        self.config = config
        self.should_stop = False
        self.cancellation_token = CancellationToken()

        # Processing mode selection
        self.download_all_mode = config.get("download_all_mode", False)

        # Resource management
        self.memory_handler = MemoryPressureHandler()

        # Conveyor belt vs download-all settings
        if self.download_all_mode:
            self.batch_size = len(urls)  # Download everything at once
            logger.info(
                "Download-all mode enabled - will download all audio files first"
            )
        else:
            self.batch_size = self._calculate_optimal_batch_size()

        self.initial_concurrency = self._calculate_optimal_concurrency()
        self.current_concurrency = self.initial_concurrency

        # Storage setup
        if self.download_all_mode:
            # Use a more permanent directory for download-all mode
            storage_name = f"youtube_audio_batch_{int(time.time())}"
            self.audio_storage_dir = (
                Path.home() / ".knowledge_system" / "audio_cache" / storage_name
            )
        else:
            # Use temp directory for conveyor belt mode
            self.audio_storage_dir = Path(tempfile.gettempdir()) / "youtube_audio_batch"

        self.audio_storage_dir.mkdir(parents=True, exist_ok=True)

        # Tracking
        self.processed_count = 0
        self.successful_count = 0
        self.failed_count = 0
        self.failed_urls = []
        self.successful_urls = []
        self.downloaded_audio_files = {}  # url -> file_path mapping

        logger.info(f"YouTube batch worker initialized:")
        logger.info(f"  - URLs to process: {len(urls)}")
        logger.info(
            f"  - Processing mode: {'Download-all' if self.download_all_mode else 'Conveyor belt'}"
        )
        logger.info(f"  - Batch size: {self.batch_size}")
        logger.info(f"  - Initial max concurrent: {self.initial_concurrency}")
        logger.info(f"  - Audio storage: {self.audio_storage_dir}")

    def _calculate_optimal_batch_size(self) -> int:
        """Calculate optimal batch size based on available disk space and mode."""
        try:
            output_dir = Path(self.config.get("output_dir", "."))
            disk_usage = shutil.disk_usage(output_dir)
            available_gb = disk_usage.free / (1024**3)

            # Estimate space needed per audio file (50MB average)
            space_per_audio_gb = 0.05

            if self.download_all_mode:
                # Check if we have space for ALL audio files
                total_space_needed = (
                    len(self.urls) * space_per_audio_gb * 1.2
                )  # 20% buffer
                if available_gb < total_space_needed:
                    logger.warning(
                        f"Insufficient space for download-all mode: need {total_space_needed:.1f}GB, have {available_gb:.1f}GB"
                    )
                    logger.info("Falling back to conveyor belt mode")
                    self.download_all_mode = False
                    self.config["download_all_mode"] = False
                    return max(
                        10, min(100, int(available_gb / space_per_audio_gb) // 2)
                    )
                else:
                    logger.info(
                        f"Download-all mode: sufficient space for {len(self.urls)} files ({total_space_needed:.1f}GB needed, {available_gb:.1f}GB available)"
                    )
                    return len(self.urls)
            else:
                # Conveyor belt mode: conservative batch size
                available_for_audio = max(0, available_gb - 2.0)
                max_simultaneous_files = int(available_for_audio / space_per_audio_gb)
                batch_size = max(10, min(100, max_simultaneous_files // 2))

                logger.info(f"Conveyor belt mode batch size: {batch_size}")
                return batch_size

        except Exception as e:
            logger.error(f"Error calculating batch size: {e}")
            return 50  # Safe default

    def _check_diarization_setup(self) -> bool:
        """Check if diarization dependencies are available."""
        try:
            from ...processors.diarization import _check_diarization_dependencies

            return _check_diarization_dependencies()
        except ImportError:
            logger.error("Diarization processor not available")
            return False
        except Exception as e:
            logger.error(f"Error checking diarization setup: {e}")
            return False

    def _calculate_optimal_concurrency(self) -> int:
        """Calculate optimal concurrency using enhanced logic."""
        try:
            # Use existing hardware detection but enhance with memory monitoring
            detector = HardwareDetector()
            specs = detector.detect_hardware()

            # Base concurrency from hardware
            hardware_limit = specs.max_concurrent_transcriptions

            # Memory-based limit (conservative for diarization)
            memory_gb = psutil.virtual_memory().total / (1024**3)
            memory_limit = max(1, int(memory_gb / 4))  # 4GB per diarization process

            # CPU-based limit
            cpu_limit = max(1, (os.cpu_count() or 4) // 2)

            # Take most conservative limit, but respect download-all mode
            base_limit = min(
                hardware_limit, memory_limit, cpu_limit, 8
            )  # Max 8 concurrent

            if self.download_all_mode:
                # Download-all mode can use higher concurrency since we're not downloading during processing
                optimal = min(base_limit + 2, 10)
            else:
                # Conveyor belt mode is more conservative
                optimal = base_limit

            logger.info(f"Concurrency calculation:")
            logger.info(f"  - Hardware limit: {hardware_limit}")
            logger.info(f"  - Memory limit: {memory_limit}")
            logger.info(f"  - CPU limit: {cpu_limit}")
            logger.info(f"  - Final limit: {optimal}")

            return optimal

        except Exception as e:
            logger.error(f"Error calculating concurrency: {e}")
            return 3  # Safe default

    def run(self):
        """Main processing loop with enhanced resource management."""
        try:
            logger.info(
                f"Starting enhanced YouTube batch processing: {len(self.urls)} URLs"
            )

            # Emit initialization progress
            self.progress_updated.emit(
                0, len(self.urls), "🔄 Initializing batch processing..."
            )

            # Check diarization dependencies if needed
            if self.config.get("enable_diarization", False):
                self.progress_updated.emit(
                    0, len(self.urls), "🎙️ Checking diarization dependencies..."
                )
                if not self._check_diarization_setup():
                    self.extraction_error.emit("Diarization dependencies not available")
                    return
                self.progress_updated.emit(
                    0, len(self.urls), "✅ Diarization dependencies ready"
                )

            if self.download_all_mode:
                self._run_download_all_mode()
            else:
                self._run_conveyor_belt_mode()

            # Final cleanup and results
            self.progress_updated.emit(
                len(self.urls), len(self.urls), "🧹 Cleaning up temporary files..."
            )
            self._cleanup_storage()

            final_results = {
                "successful": self.successful_count,
                "failed": self.failed_count,
                "urls_processed": self.successful_urls,
                "failed_urls": self.failed_urls,
                "total_urls": len(self.urls),
                "processing_mode": (
                    "download-all" if self.download_all_mode else "conveyor-belt"
                ),
            }

            logger.info(
                f"Processing completed: {self.successful_count} successful, {self.failed_count} failed"
            )
            self.extraction_finished.emit(final_results)

        except Exception as e:
            error_msg = f"YouTube batch processing failed: {str(e)}"
            logger.error(error_msg)
            self.extraction_error.emit(error_msg)

    def _run_download_all_mode(self):
        """Download-all mode: Download all audio first, then process."""
        logger.info("=== DOWNLOAD-ALL MODE ===")

        # Phase 1: Download all audio files
        self.progress_updated.emit(
            0, len(self.urls), "📥 Phase 1: Downloading all audio files..."
        )

        download_success_count = 0
        for i, url in enumerate(self.urls):
            if self.should_stop or self.cancellation_token.is_cancelled():
                break

            # Emit progress with more detail and immediate flush
            progress_msg = f"📥 Downloading audio {i+1}/{len(self.urls)}: {url[:50]}..."
            self.progress_updated.emit(i, len(self.urls), progress_msg)

            # Force signal processing
            import time

            time.sleep(0.001)  # Brief pause to ensure signal processing

            audio_file = self._download_audio_persistent(url, i)
            if audio_file and audio_file.exists():
                self.downloaded_audio_files[url] = audio_file
                download_success_count += 1
                logger.info(
                    f"Downloaded: {audio_file} ({audio_file.stat().st_size / 1024 / 1024:.1f}MB)"
                )
            else:
                logger.error(f"Failed to download audio for {url}")
                self._record_failure(url, "Audio download failed")

        logger.info(
            f"Download phase complete: {download_success_count}/{len(self.urls)} audio files downloaded"
        )

        # Phase 2: Process all downloaded audio with diarization
        if self.downloaded_audio_files:
            self.progress_updated.emit(
                0,
                len(self.downloaded_audio_files),
                "🎙️ Phase 2: Processing audio with diarization...",
            )
            self._process_all_downloaded_audio()

    def _run_conveyor_belt_mode(self):
        """Conveyor belt mode: Process in batches with resource monitoring."""
        logger.info("=== CONVEYOR BELT MODE ===")

        total_urls = len(self.urls)

        for batch_start in range(0, total_urls, self.batch_size):
            if self.should_stop or self.cancellation_token.is_cancelled():
                break

            # Check memory pressure before each batch
            pressure_level, pressure_msg = self.memory_handler.check_memory_pressure()
            if pressure_level > 0:
                self.memory_pressure.emit(pressure_level, pressure_msg)
                # Adjust concurrency based on memory pressure
                new_concurrency, should_pause = self.memory_handler.mitigate_pressure(
                    self.current_concurrency
                )
                self.current_concurrency = new_concurrency

                if should_pause:
                    logger.warning("Emergency memory pressure - pausing processing")
                    self.resource_warning.emit(
                        "Emergency memory pressure - pausing until memory recovers"
                    )
                    time.sleep(5)  # Wait for memory to recover
                    continue  # Skip this batch and recheck

            batch_end = min(batch_start + self.batch_size, total_urls)
            current_batch = self.urls[batch_start:batch_end]

            logger.info(
                f"Processing batch {batch_start//self.batch_size + 1}: URLs {batch_start+1}-{batch_end}"
            )
            logger.info(
                f"Current concurrency: {self.current_concurrency} (adjusted from {self.initial_concurrency})"
            )

            # Check disk space before each batch
            if not self._check_disk_space_for_batch(len(current_batch)):
                error_msg = f"Insufficient disk space for batch {batch_start//self.batch_size + 1}"
                logger.error(error_msg)
                self.extraction_error.emit(error_msg)
                break

            # Process current batch
            self._process_batch_conveyor_belt(current_batch, batch_start)

            # Emit batch completion status
            self._emit_batch_status(
                batch_start // self.batch_size + 1, len(current_batch)
            )

    def _process_all_downloaded_audio(self):
        """Process all pre-downloaded audio files with enhanced resource monitoring."""
        # Monitor memory during processing with enhanced mitigation
        with ThreadPoolExecutor(max_workers=self.current_concurrency) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(
                    self._process_single_url_with_audio, url, audio_file
                ): url
                for url, audio_file in self.downloaded_audio_files.items()
            }

            completed = 0
            for future in as_completed(future_to_url):
                if self.should_stop or self.cancellation_token.is_cancelled():
                    # Cancel remaining futures
                    for f in future_to_url:
                        f.cancel()
                    break

                # Check memory pressure after each completion
                (
                    pressure_level,
                    pressure_msg,
                ) = self.memory_handler.check_memory_pressure()
                if pressure_level >= 2:  # Critical or emergency pressure
                    self.memory_pressure.emit(pressure_level, pressure_msg)
                    if pressure_level >= 3:  # Emergency
                        # Pause briefly for emergency memory pressure
                        time.sleep(2.0)
                    else:  # Critical
                        time.sleep(1.0)  # Brief pause to let memory recover

                url = future_to_url[future]

                try:
                    success, message = future.result()

                    if success:
                        self._record_success(url, message)
                        # In download-all mode, we DON'T delete audio files immediately
                        # They'll be cleaned up at the end
                    else:
                        self._record_failure(url, message)

                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    self._record_failure(url, f"Processing error: {str(e)}")

                completed += 1
                self.progress_updated.emit(
                    completed,
                    len(self.downloaded_audio_files),
                    f"🎙️ Processing {completed}/{len(self.downloaded_audio_files)} audio files",
                )

    def _check_disk_space_for_batch(self, batch_size: int) -> bool:
        """Check if there's enough disk space for the current batch."""
        try:
            output_dir = Path(self.config.get("output_dir", "."))
            disk_usage = shutil.disk_usage(output_dir)
            available_gb = disk_usage.free / (1024**3)

            # Estimate space needed for this batch
            space_per_audio_gb = 0.05  # 50MB in GB
            required_gb = batch_size * space_per_audio_gb * 1.2  # 20% buffer

            if available_gb < required_gb:
                logger.warning(
                    f"Low disk space: need {required_gb:.1f}GB, have {available_gb:.1f}GB"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            return True  # Assume OK if we can't check

    def _process_batch_conveyor_belt(self, batch_urls: list[str], batch_offset: int):
        """
        Process a batch using the conveyor belt approach with enhanced memory monitoring.
        """

        # Step 1: Download audio files for the batch
        audio_files = {}  # url -> audio_file_path mapping

        for i, url in enumerate(batch_urls):
            if self.should_stop or self.cancellation_token.is_cancelled():
                break

            try:
                global_index = batch_offset + i
                self.progress_updated.emit(
                    global_index,
                    len(self.urls),
                    f"Downloading audio for video {global_index + 1}/{len(self.urls)}",
                )

                audio_file = self._download_audio_persistent(url, global_index)
                if audio_file and audio_file.exists():
                    audio_files[url] = audio_file
                    logger.info(
                        f"Downloaded audio: {audio_file} ({audio_file.stat().st_size / 1024 / 1024:.1f}MB)"
                    )
                else:
                    logger.error(f"Failed to download audio for {url}")
                    self._record_failure(url, "Audio download failed")

            except Exception as e:
                logger.error(f"Error downloading audio for {url}: {e}")
                self._record_failure(url, f"Audio download error: {str(e)}")

        # Step 2: Process downloaded audio files with parallel diarization and memory monitoring
        if audio_files:
            logger.info(
                f"Processing {len(audio_files)} downloaded audio files with diarization"
            )
            self._process_audio_files_parallel_with_memory_monitoring(
                audio_files, batch_offset
            )

    def _process_audio_files_parallel_with_memory_monitoring(
        self, audio_files: dict[str, Path], batch_offset: int
    ):
        """Process audio files in parallel with enhanced memory monitoring."""

        # Monitor memory usage before starting
        initial_memory = psutil.virtual_memory().percent
        if initial_memory > self.memory_handler.warning_threshold:
            self.resource_warning.emit(
                f"High memory usage before processing: {initial_memory:.1f}%"
            )

        # Process with controlled concurrency and memory monitoring
        with ThreadPoolExecutor(max_workers=self.current_concurrency) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(
                    self._process_single_url_with_audio, url, audio_file
                ): url
                for url, audio_file in audio_files.items()
            }

            # Process completed tasks as they finish
            for future in as_completed(future_to_url):
                if self.should_stop or self.cancellation_token.is_cancelled():
                    # Cancel remaining futures
                    for f in future_to_url:
                        f.cancel()
                    break

                url = future_to_url[future]
                audio_file = audio_files[url]

                try:
                    success, message = future.result()

                    if success:
                        self._record_success(url, message)
                        # Clean up audio file immediately after successful processing
                        self._cleanup_audio_file(audio_file)
                    else:
                        self._record_failure(url, message)
                        # Keep audio file for potential retry
                        logger.info(
                            f"Retaining audio file for failed processing: {audio_file}"
                        )

                    # Enhanced memory monitoring after each completion
                    (
                        pressure_level,
                        pressure_msg,
                    ) = self.memory_handler.check_memory_pressure()
                    if pressure_level > 0:
                        self.memory_pressure.emit(pressure_level, pressure_msg)

                        # Apply memory mitigation if needed
                        (
                            new_concurrency,
                            should_pause,
                        ) = self.memory_handler.mitigate_pressure(
                            self.current_concurrency
                        )
                        if new_concurrency != self.current_concurrency:
                            logger.info(
                                f"Adjusting concurrency from {self.current_concurrency} to {new_concurrency} due to memory pressure"
                            )
                            self.current_concurrency = new_concurrency

                        if should_pause:
                            logger.warning(
                                "Emergency memory pressure detected during processing"
                            )
                            time.sleep(2.0)  # Brief pause for emergency situations

                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    self._record_failure(url, f"Processing error: {str(e)}")

    def _download_audio_persistent(self, url: str, index: int) -> Path | None:
        """Download audio to persistent storage until successful processing."""
        try:
            # Check cancellation before starting
            if self.should_stop or self.cancellation_token.is_cancelled():
                logger.info(f"Download cancelled before starting for {url}")
                return None

            # Create unique filename for this audio
            video_id = self._extract_video_id(url)
            audio_file = self.audio_storage_dir / f"{video_id}_{index}.wav"

            # Skip if already exists (resuming from previous run)
            if audio_file.exists():
                logger.info(f"Audio file already exists: {audio_file}")
                return audio_file

            # Emit download start progress
            self.progress_updated.emit(
                index, len(self.urls), f"🌐 Connecting to YouTube for {video_id}..."
            )

            # Download using yt-dlp with Webshare proxy
            from ...config import get_settings

            settings = get_settings()

            import yt_dlp

            # Flag to track if download was cancelled
            download_cancelled = False

            # Track download progress and check for cancellation
            def progress_hook(d):
                nonlocal download_cancelled

                # Check for cancellation during download
                if self.should_stop or self.cancellation_token.is_cancelled():
                    download_cancelled = True
                    logger.info(f"Download cancelled during progress for {video_id}")
                    # Raise an exception to stop the download
                    raise Exception("Download cancelled by user")

                if d["status"] == "downloading":
                    # Emit detailed download progress
                    if "total_bytes" in d and d["total_bytes"]:
                        percent = (d["downloaded_bytes"] / d["total_bytes"]) * 100
                        size_mb = d["total_bytes"] / (1024 * 1024)
                        self.progress_updated.emit(
                            index,
                            len(self.urls),
                            f"📥 Downloading {video_id}: {percent:.1f}% ({size_mb:.1f}MB)",
                        )
                    elif "downloaded_bytes" in d:
                        size_mb = d["downloaded_bytes"] / (1024 * 1024)
                        self.progress_updated.emit(
                            index,
                            len(self.urls),
                            f"📥 Downloading {video_id}: {size_mb:.1f}MB...",
                        )
                elif d["status"] == "finished":
                    self.progress_updated.emit(
                        index,
                        len(self.urls),
                        f"✅ Downloaded {video_id}, converting to audio...",
                    )

            # Configure yt-dlp with proxy and progress hook
            ydl_opts = {
                "format": "250/249/140/worst",  # Use lowest quality audio to minimize file size
                "outtmpl": str(audio_file.with_suffix(".%(ext)s")),
                "extractaudio": True,
                "audioformat": "wav",
                "audioquality": 9,  # Lowest quality setting for minimum file size
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [progress_hook],
            }

            # Note: Proxy configuration is now handled by the main YouTube processors
            # which use Bright Data API when available. Direct yt-dlp usage here
            # should be minimal and rely on the processor layer for proper proxy handling.

            # Download with cancellation handling
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                if (
                    download_cancelled
                    or self.should_stop
                    or self.cancellation_token.is_cancelled()
                ):
                    logger.info(f"Download cancelled for {video_id}")
                    # Clean up any partial download
                    for partial_file in self.audio_storage_dir.glob(
                        f"{video_id}_{index}.*"
                    ):
                        try:
                            partial_file.unlink()
                            logger.info(f"Cleaned up partial download: {partial_file}")
                        except Exception as cleanup_e:
                            logger.warning(
                                f"Could not clean up partial file {partial_file}: {cleanup_e}"
                            )
                    return None
                else:
                    # Re-raise if it's not a cancellation
                    raise

            # Check cancellation after download but before processing
            if self.should_stop or self.cancellation_token.is_cancelled():
                logger.info(f"Processing cancelled after download for {video_id}")
                return None

            # Find the downloaded file (yt-dlp may have added extension)
            for possible_file in self.audio_storage_dir.glob(f"{video_id}_{index}.*"):
                if possible_file.suffix in [".wav", ".m4a", ".mp3"]:
                    if possible_file != audio_file:
                        # Rename to expected .wav extension
                        possible_file.rename(audio_file)
                    return audio_file

            return None

        except Exception as e:
            logger.error(f"Error downloading audio for {url}: {e}")
            return None

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL."""
        if "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        elif "watch?v=" in url:
            return url.split("watch?v=")[1].split("&")[0]
        else:
            # Fallback: use hash of URL
            import hashlib

            return hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:11]

    def _process_single_url_with_audio(
        self, url: str, audio_file: Path
    ) -> tuple[bool, str]:
        """Process a single URL using its downloaded audio file."""
        try:
            # Create progress callback to track processing steps
            def progress_callback(step: str, progress: int = 0):
                # Extract video ID for better reporting
                video_id = self._extract_video_id(url)
                self.url_completed.emit(url, None, f"🎯 {video_id}: {step}")

            # Use existing YouTubeTranscriptProcessor
            processor = YouTubeTranscriptProcessor()

            # Report processing start
            video_id = self._extract_video_id(url)
            progress_callback("Starting transcription processing")

            enable_diarization = self.config.get("enable_diarization", False)
            testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"

            result = processor.process(
                url,
                output_dir=self.config.get("output_dir"),
                output_format=self.config.get("format", "md"),
                include_timestamps=self.config.get("timestamps", True),
                overwrite=self.config.get("overwrite", False),
                enable_diarization=enable_diarization,
                gui_mode=not testing_mode,  # Enable GUI mode unless testing
                show_speaker_dialog=(
                    enable_diarization and not testing_mode
                ),  # Show dialog if diarization enabled and not testing
                cancellation_token=self.cancellation_token,
                progress_callback=progress_callback,  # Pass our progress callback
            )

            if result and result.success:
                progress_callback("Processing completed successfully")
                return True, "Successfully processed with diarization"
            else:
                error_msg = (
                    "; ".join(result.errors)
                    if result and result.errors
                    else "Unknown error"
                )
                progress_callback(f"Processing failed: {error_msg}")
                return False, error_msg

        except Exception as e:
            video_id = self._extract_video_id(url)
            error_msg = f"Processing exception: {str(e)}"
            self.url_completed.emit(url, None, f"❌ {video_id}: {error_msg}")
            return False, error_msg

    def _record_success(self, url: str, message: str):
        """Record successful processing."""
        self.successful_count += 1
        self.processed_count += 1
        self.successful_urls.append(url)
        self.url_completed.emit(url, True, message)
        self.progress_updated.emit(
            self.processed_count,
            len(self.urls),
            f"✅ Completed {self.processed_count}/{len(self.urls)} ({self.successful_count} successful)",
        )

    def _record_failure(self, url: str, error: str):
        """Record failed processing."""
        self.failed_count += 1
        self.processed_count += 1
        self.failed_urls.append({"url": url, "error": error})
        self.url_completed.emit(url, False, f"❌ {error}")
        self.progress_updated.emit(
            self.processed_count,
            len(self.urls),
            f"❌ Processed {self.processed_count}/{len(self.urls)} ({self.failed_count} failed)",
        )

    def _cleanup_audio_file(self, audio_file: Path):
        """Clean up audio file after successful processing."""
        try:
            if audio_file.exists():
                audio_file.unlink()
                logger.info(f"Cleaned up audio file: {audio_file}")
        except Exception as e:
            logger.error(f"Error cleaning up audio file {audio_file}: {e}")

    def _emit_batch_status(self, batch_number: int, batch_processed: int):
        """Emit enhanced batch status with memory information."""
        memory_percent = psutil.virtual_memory().percent

        self.batch_status.emit(
            {
                "batch_number": batch_number,
                "batch_processed": batch_processed,
                "total_processed": self.processed_count,
                "total_successful": self.successful_count,
                "total_failed": self.failed_count,
                "memory_usage": memory_percent,
                "current_concurrency": self.current_concurrency,
                "initial_concurrency": self.initial_concurrency,
                "memory_pressure_level": self.memory_handler.pressure_level,
            }
        )

    def _cleanup_storage(self):
        """Enhanced cleanup for both modes."""
        try:
            if self.audio_storage_dir.exists():
                remaining_files = list(self.audio_storage_dir.glob("*"))

                if self.download_all_mode:
                    # In download-all mode, clean up all files after processing
                    logger.info(
                        f"Download-all mode: cleaning up {len(remaining_files)} audio files"
                    )
                    for file in remaining_files:
                        try:
                            file.unlink()
                        except Exception as e:
                            logger.warning(f"Could not delete {file}: {e}")

                    # Try to remove the directory
                    try:
                        self.audio_storage_dir.rmdir()
                        logger.info("Download-all mode: storage directory cleaned up")
                    except Exception as e:
                        logger.warning(f"Could not remove storage directory: {e}")
                else:
                    # Conveyor belt mode: existing logic
                    if remaining_files:
                        logger.info(
                            f"Retaining {len(remaining_files)} audio files from failed processing"
                        )
                        for file in remaining_files[:5]:  # Log first 5
                            logger.info(f"  - {file}")
                        if len(remaining_files) > 5:
                            logger.info(f"  - ... and {len(remaining_files) - 5} more")
                    else:
                        self.audio_storage_dir.rmdir()
                        logger.info(
                            "All audio files processed successfully - storage cleaned up"
                        )

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def stop(self):
        """Stop processing."""
        self.should_stop = True
        self.cancellation_token.cancel()

    def pause(self):
        """Pause processing."""
        self.cancellation_token.pause()

    def resume(self):
        """Resume processing."""
        self.cancellation_token.resume()
