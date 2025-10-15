"""
Intelligent Download Pacing System

This module provides intelligent pacing for YouTube downloads that:
1. Estimates processing time per file based on content length
2. Spaces downloads to stay ahead of the summarization pipeline
3. Adapts to bot detection patterns and rate limiting
4. Prevents overwhelming YouTube's servers while maintaining optimal throughput
"""

import random
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessingMetrics:
    """Tracks processing timing metrics for intelligent pacing."""

    # Timing data (in seconds)
    download_times: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    transcription_times: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    summarization_times: deque[float] = field(default_factory=lambda: deque(maxlen=20))

    # Content characteristics
    audio_durations: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    transcript_lengths: deque[int] = field(default_factory=lambda: deque(maxlen=20))

    # Rate limiting data
    rate_limit_events: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    successful_downloads: deque[float] = field(default_factory=lambda: deque(maxlen=50))

    # Real-time processing tracking
    processing_queue: deque[dict] = field(
        default_factory=lambda: deque(maxlen=100)
    )  # Active processing jobs
    completed_processing: deque[dict] = field(
        default_factory=lambda: deque(maxlen=50)
    )  # Recently completed jobs
    current_processing_speed: float = 0.0  # Files per minute currently being processed

    def get_avg_download_time(self) -> float:
        """Get average download time in seconds."""
        return (
            sum(self.download_times) / len(self.download_times)
            if self.download_times
            else 30.0
        )

    def get_avg_processing_time(self) -> float:
        """Get average total processing time (transcription + summarization)."""
        transcription_total = (
            sum(self.transcription_times) if self.transcription_times else 0.0
        )
        summarization_total = (
            sum(self.summarization_times) if self.summarization_times else 0.0
        )
        total_processing = (transcription_total + summarization_total) / max(
            len(self.transcription_times), 1
        )
        return total_processing

    def get_processing_to_download_ratio(self) -> float:
        """Get ratio of processing time to download time."""
        avg_download = self.get_avg_download_time()
        avg_processing = self.get_avg_processing_time()
        return avg_processing / max(avg_download, 1.0)

    def get_rate_limit_frequency(self) -> float:
        """Get rate limiting events per minute."""
        if not self.rate_limit_events:
            return 0.0

        # Count events in last 5 minutes
        now = time.time()
        recent_events = sum(
            1 for event_time in self.rate_limit_events if now - event_time < 300
        )
        return recent_events / 5.0  # per minute

    def should_increase_delays(self) -> bool:
        """Determine if we should increase delays due to rate limiting."""
        return self.get_rate_limit_frequency() > 2.0  # More than 2 events per minute

    def get_current_processing_speed(self) -> float:
        """Get current processing speed in files per minute."""
        return self.current_processing_speed

    def get_queue_depth(self) -> int:
        """Get current processing queue depth."""
        return len(self.processing_queue)

    def get_estimated_queue_clearance_time(self) -> float:
        """Estimate time in minutes to clear current processing queue."""
        if self.current_processing_speed > 0:
            return len(self.processing_queue) / self.current_processing_speed
        return 0.0

    def update_processing_speed(self):
        """Update current processing speed based on recent completions."""
        if not self.completed_processing:
            return

        # Calculate speed from recent completions (last 5 minutes)
        now = time.time()
        recent_completions = [
            job
            for job in self.completed_processing
            if now - job.get("completion_time", 0) < 300  # Last 5 minutes
        ]

        if len(recent_completions) >= 2:
            # Calculate speed from time span
            oldest = min(job["completion_time"] for job in recent_completions)
            newest = max(job["completion_time"] for job in recent_completions)
            time_span_minutes = (newest - oldest) / 60.0

            if time_span_minutes > 0:
                self.current_processing_speed = (
                    len(recent_completions) / time_span_minutes
                )
        else:
            # Use historical average if not enough recent data
            if self.transcription_times and self.summarization_times:
                avg_total_time = (
                    sum(self.transcription_times) + sum(self.summarization_times)
                ) / len(self.transcription_times)
                self.current_processing_speed = (
                    60.0 / avg_total_time
                )  # files per minute


@dataclass
class PacingConfig:
    """Configuration for intelligent pacing behavior."""

    # Base delays (seconds)
    min_delay: float = 2.0
    max_delay: float = 15.0
    base_delay: float = 5.0

    # Processing time estimates (seconds)
    estimated_transcription_per_minute: float = 30.0  # 30s per minute of audio
    estimated_summarization_per_1000_chars: float = 15.0  # 15s per 1000 chars

    # Safety margins
    download_buffer_multiplier: float = 1.5  # Keep 1.5x processing speed ahead
    rate_limit_safety_multiplier: float = 2.0  # Double delays when rate limited

    # Adaptive behavior
    enable_adaptive_pacing: bool = True
    enable_bot_detection_avoidance: bool = True
    max_concurrent_downloads: int = 4

    # Content-based adjustments
    long_content_delay_multiplier: float = 1.2  # 20% more delay for long content
    short_content_delay_multiplier: float = 0.8  # 20% less delay for short content

    def get_delay_for_content_length(self, audio_duration_minutes: float) -> float:
        """Calculate base delay based on content length."""
        if audio_duration_minutes > 30:  # Long content
            return self.base_delay * self.long_content_delay_multiplier
        elif audio_duration_minutes < 5:  # Short content
            return self.base_delay * self.short_content_delay_multiplier
        else:
            return self.base_delay


class IntelligentPacingManager:
    """
    Manages intelligent pacing for YouTube downloads.

    This class coordinates download timing to:
    1. Stay ahead of the processing pipeline
    2. Avoid bot detection
    3. Adapt to rate limiting patterns
    4. Optimize for different content types
    """

    def __init__(self, config: PacingConfig | None = None):
        self.config = config or PacingConfig()
        self.metrics = ProcessingMetrics()
        self.lock = threading.RLock()

        # Pipeline state tracking
        self.downloads_in_progress = 0
        self.downloads_completed = 0
        self.processing_queue_size = 0

        # Timing predictions
        self.estimated_total_processing_time = 0.0
        self.estimated_download_completion_time = 0.0

        logger.info("Intelligent pacing manager initialized")

    def estimate_processing_time(
        self, audio_duration_minutes: float, transcript_length: int | None = None
    ) -> float:
        """Estimate total processing time for a file."""
        # Base transcription time
        transcription_time = (
            audio_duration_minutes * self.config.estimated_transcription_per_minute
        )

        # Base summarization time (estimate if not provided)
        if transcript_length is None:
            # Rough estimate: 100 words per minute of audio
            estimated_words = audio_duration_minutes * 100
            transcript_length = estimated_words * 6  # ~6 chars per word

        summarization_time = (
            transcript_length / 1000.0
        ) * self.config.estimated_summarization_per_1000_chars

        return transcription_time + summarization_time

    def calculate_optimal_delay(
        self, audio_duration_minutes: float, transcript_length: int | None = None
    ) -> float:
        """Calculate optimal delay between downloads."""
        with self.lock:
            # Base delay from config
            base_delay = self.config.get_delay_for_content_length(
                audio_duration_minutes
            )

            # Estimate processing time for this file
            processing_time = self.estimate_processing_time(
                audio_duration_minutes, transcript_length
            )

            # Calculate how much we need to stay ahead
            if self.metrics.download_times:
                avg_download_time = self.metrics.get_avg_download_time()
                processing_to_download_ratio = processing_time / max(
                    avg_download_time, 1.0
                )

                # If processing is much slower than downloading, we can space out downloads more
                if processing_to_download_ratio > 5.0:  # Processing takes 5x longer
                    base_delay *= 2.0  # Double the delay
                elif processing_to_download_ratio > 2.0:  # Processing takes 2x longer
                    base_delay *= 1.5  # 50% more delay

            # Rate limiting adjustments
            if self.config.enable_adaptive_pacing:
                rate_limit_frequency = self.metrics.get_rate_limit_frequency()
                if rate_limit_frequency > 1.0:  # More than 1 rate limit per minute
                    base_delay *= self.config.rate_limit_safety_multiplier
                elif rate_limit_frequency > 0.5:  # More than 0.5 rate limits per minute
                    base_delay *= 1.5

            # Bot detection avoidance
            if self.config.enable_bot_detection_avoidance:
                # Add random variation to avoid predictable patterns
                random_factor = random.uniform(0.8, 1.2)
                base_delay *= random_factor

                # Longer delays for bulk operations
                if self.downloads_completed > 10:
                    base_delay *= 1.2
                if self.downloads_completed > 50:
                    base_delay *= 1.5

            # Ensure within bounds
            return max(self.config.min_delay, min(base_delay, self.config.max_delay))

    def should_pause_downloads(self) -> bool:
        """Determine if we should pause downloads to let processing catch up."""
        with self.lock:
            # Update processing speed metrics
            self.metrics.update_processing_speed()

            # Get real-time queue status
            queue_depth = self.metrics.get_queue_depth()
            current_speed = self.metrics.get_current_processing_speed()
            estimated_clearance_time = self.metrics.get_estimated_queue_clearance_time()

            # If we have many downloads queued for processing, pause downloads
            if queue_depth > 15:  # Increased threshold for real-time tracking
                logger.info(
                    f"Pausing downloads: {queue_depth} files queued for processing"
                )
                return True

            # If processing is very slow and queue is building up
            if (
                current_speed > 0 and estimated_clearance_time > 30
            ):  # More than 30 minutes to clear queue
                logger.warning(
                    f"Pausing downloads: queue clearance time is {estimated_clearance_time:.1f} minutes"
                )
                return True

            # If rate limiting is frequent, pause to cool down
            if self.metrics.get_rate_limit_frequency() > 3.0:
                logger.warning("Pausing downloads due to frequent rate limiting")
                return True

            # If processing speed is very low (less than 1 file per 10 minutes)
            if current_speed > 0 and current_speed < 0.1:
                logger.warning(
                    f"Pausing downloads: processing speed very low ({current_speed:.2f} files/min)"
                )
                return True

            return False

    def record_download_start(self, audio_duration_minutes: float):
        """Record that a download has started."""
        with self.lock:
            self.downloads_in_progress += 1

    def record_download_completion(
        self, audio_duration_minutes: float, download_time: float
    ):
        """Record that a download has completed."""
        with self.lock:
            self.downloads_in_progress -= 1
            self.downloads_completed += 1

            # Update metrics
            self.metrics.download_times.append(download_time)
            self.metrics.audio_durations.append(audio_duration_minutes)
            self.metrics.successful_downloads.append(time.time())

            # Estimate processing time and add to queue
            processing_time = self.estimate_processing_time(audio_duration_minutes)
            self.processing_queue_size += 1

            # Schedule processing completion (for queue management)
            time.time() + processing_time
            threading.Timer(processing_time, self._mark_processing_complete).start()

    def record_rate_limit_event(self):
        """Record that a rate limit event occurred."""
        with self.lock:
            self.metrics.rate_limit_events.append(time.time())
            logger.warning("Rate limit event recorded - will increase delays")

    def record_processing_start(
        self,
        job_id: str,
        audio_duration_minutes: float,
        estimated_processing_time: float,
    ):
        """Record that processing has started for a job."""
        with self.lock:
            job_info = {
                "job_id": job_id,
                "start_time": time.time(),
                "audio_duration_minutes": audio_duration_minutes,
                "estimated_processing_time": estimated_processing_time,
                "status": "processing",
            }
            self.metrics.processing_queue.append(job_info)
            self.processing_queue_size += 1

    def record_processing_completion(
        self,
        job_id: str,
        audio_duration_minutes: float,
        transcription_time: float,
        summarization_time: float,
        transcript_length: int,
    ):
        """Record that processing (transcription + summarization) has completed."""
        with self.lock:
            # Update historical metrics
            self.metrics.transcription_times.append(transcription_time)
            self.metrics.summarization_times.append(summarization_time)
            self.metrics.transcript_lengths.append(transcript_length)

            # Update real-time tracking
            completion_time = time.time()

            # Find and remove from processing queue
            job_found = False
            for i, job in enumerate(self.metrics.processing_queue):
                if job.get("job_id") == job_id:
                    job_info = self.metrics.processing_queue[i]
                    job_info["completion_time"] = completion_time
                    job_info["actual_processing_time"] = (
                        completion_time - job_info["start_time"]
                    )
                    job_info["transcription_time"] = transcription_time
                    job_info["summarization_time"] = summarization_time
                    job_info["transcript_length"] = transcript_length

                    # Move to completed queue
                    self.metrics.completed_processing.append(job_info)
                    del self.metrics.processing_queue[i]
                    job_found = True
                    break

            if job_found:
                self.processing_queue_size = max(0, self.processing_queue_size - 1)
                logger.debug(
                    f"Processing completed for job {job_id}: {transcription_time:.1f}s transcription + {summarization_time:.1f}s summarization"
                )
            else:
                logger.warning(
                    f"Could not find job {job_id} in processing queue for completion tracking"
                )

            # Update processing speed
            self.metrics.update_processing_speed()

    def _mark_processing_complete(self):
        """Internal method to mark processing as complete."""
        with self.lock:
            self.processing_queue_size = max(0, self.processing_queue_size - 1)

    def get_pacing_status(self) -> dict[str, Any]:
        """Get current pacing status for monitoring."""
        with self.lock:
            # Update processing speed metrics
            self.metrics.update_processing_speed()

            return {
                "downloads_in_progress": self.downloads_in_progress,
                "downloads_completed": self.downloads_completed,
                "processing_queue_size": self.processing_queue_size,
                "avg_download_time": self.metrics.get_avg_download_time(),
                "avg_processing_time": self.metrics.get_avg_processing_time(),
                "processing_to_download_ratio": self.metrics.get_processing_to_download_ratio(),
                "rate_limit_frequency": self.metrics.get_rate_limit_frequency(),
                "should_pause": self.should_pause_downloads(),
                # Real-time processing status
                "current_processing_speed": self.metrics.get_current_processing_speed(),
                "queue_depth": self.metrics.get_queue_depth(),
                "estimated_queue_clearance_time": self.metrics.get_estimated_queue_clearance_time(),
                "active_processing_jobs": len(self.metrics.processing_queue),
                "recent_completions": len(self.metrics.completed_processing),
            }

    def get_next_download_delay(
        self, audio_duration_minutes: float, transcript_length: int | None = None
    ) -> float:
        """Get the delay to wait before starting the next download."""
        # Check if we should pause
        if self.should_pause_downloads():
            return 30.0  # Wait 30 seconds before checking again

        # Calculate optimal delay
        delay = self.calculate_optimal_delay(audio_duration_minutes, transcript_length)

        logger.debug(
            f"Calculated download delay: {delay:.1f}s for {audio_duration_minutes:.1f}min audio"
        )
        return delay

    def wait_for_next_download(
        self,
        audio_duration_minutes: float,
        transcript_length: int | None = None,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> bool:
        """
        Wait for the optimal time before next download.

        Returns:
            bool: True if download should proceed, False if cancelled
        """
        delay = self.get_next_download_delay(audio_duration_minutes, transcript_length)

        if delay <= 0:
            return True

        logger.info(f"⏱️ Intelligent pacing: waiting {delay:.1f}s before next download")

        # Sleep in small increments to allow cancellation
        elapsed = 0
        while elapsed < delay:
            if cancellation_check and cancellation_check():
                logger.info("Download cancelled during pacing delay")
                return False

            sleep_time = min(1.0, delay - elapsed)  # Sleep max 1 second at a time
            time.sleep(sleep_time)
            elapsed += sleep_time

        return True


# Global pacing manager instance
_global_pacing_manager: IntelligentPacingManager | None = None


def get_pacing_manager(
    config: PacingConfig | None = None,
) -> IntelligentPacingManager:
    """Get the global pacing manager instance."""
    global _global_pacing_manager
    if _global_pacing_manager is None:
        _global_pacing_manager = IntelligentPacingManager(config)
    return _global_pacing_manager


def create_pacing_config_from_settings() -> PacingConfig:
    """Create pacing config from application settings."""
    from ..config import get_settings

    settings = get_settings()

    # Map settings to pacing config
    config = PacingConfig()

    # Adjust based on system capabilities
    import psutil

    memory_gb = psutil.virtual_memory().total / (1024**3)

    if memory_gb >= 64:  # High-memory system
        config.max_concurrent_downloads = 6
        config.base_delay = 3.0
    elif memory_gb >= 32:  # Medium-memory system
        config.max_concurrent_downloads = 4
        config.base_delay = 5.0
    else:  # Lower-memory system
        config.max_concurrent_downloads = 2
        config.base_delay = 7.0

    # Check GUI settings first (takes precedence)
    gui_intelligent_pacing_enabled = True
    try:
        from ..gui.settings import GUISettings

        gui_settings = GUISettings()
        gui_intelligent_pacing_enabled = gui_settings.get_checkbox_state(
            "youtube_tab", "enable_intelligent_pacing", True
        )
    except ImportError:
        # GUI not available, use default
        pass
    except Exception:
        # Other error, use default
        pass

    # Adjust based on YouTube processing config
    if hasattr(settings, "youtube_processing"):
        yt_config = settings.youtube_processing

        # Use intelligent pacing settings if enabled in both config and GUI
        if (
            hasattr(yt_config, "enable_intelligent_pacing")
            and yt_config.enable_intelligent_pacing
            and gui_intelligent_pacing_enabled
        ):
            config.enable_adaptive_pacing = True
            config.enable_bot_detection_avoidance = True

            # Use configured pacing values
            if hasattr(yt_config, "pacing_base_delay"):
                config.base_delay = yt_config.pacing_base_delay
            if hasattr(yt_config, "pacing_min_delay"):
                config.min_delay = yt_config.pacing_min_delay
            if hasattr(yt_config, "pacing_max_delay"):
                config.max_delay = yt_config.pacing_max_delay
            if hasattr(yt_config, "pacing_buffer_multiplier"):
                config.download_buffer_multiplier = yt_config.pacing_buffer_multiplier
            if hasattr(yt_config, "pacing_rate_limit_multiplier"):
                config.rate_limit_safety_multiplier = (
                    yt_config.pacing_rate_limit_multiplier
                )
        else:
            # Disable intelligent pacing if configured or GUI disabled
            config.enable_adaptive_pacing = False
            config.enable_bot_detection_avoidance = False
            logger.info("Intelligent pacing disabled by configuration or GUI setting")

        # Legacy proxy delay settings
        if (
            hasattr(yt_config, "disable_delays_with_proxy")
            and yt_config.disable_delays_with_proxy
        ):
            config.base_delay *= 0.5  # Reduce delays when using proxy

    return config
