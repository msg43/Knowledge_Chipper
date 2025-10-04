"""
Pacing Monitor - Real-time monitoring of download and processing pipeline status.

This module provides utilities to monitor the intelligent pacing system and
get real-time insights into download and processing performance.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict

from ..logger import get_logger
from .intelligent_pacing import create_pacing_config_from_settings, get_pacing_manager

logger = get_logger(__name__)


@dataclass
class PipelineStatus:
    """Current status of the download and processing pipeline."""

    # Download status
    downloads_in_progress: int
    downloads_completed: int

    # Processing status
    processing_queue_depth: int
    active_processing_jobs: int
    recent_completions: int

    # Performance metrics
    current_processing_speed: float  # files per minute
    estimated_queue_clearance_time: float  # minutes
    avg_download_time: float  # seconds
    avg_processing_time: float  # seconds

    # Rate limiting
    rate_limit_frequency: float  # events per minute

    # Recommendations
    should_pause_downloads: bool
    recommended_delay: float  # seconds

    # Efficiency metrics
    processing_to_download_ratio: float
    pipeline_efficiency: float  # percentage


class PacingMonitor:
    """
    Real-time monitor for the intelligent pacing system.

    Provides continuous monitoring and status reporting for the download
    and processing pipeline.
    """

    def __init__(self):
        self.pacing_manager = None
        self.last_status_time = 0
        self.status_history = []

    def _get_pacing_manager(self):
        """Get the pacing manager, creating if needed."""
        if self.pacing_manager is None:
            config = create_pacing_config_from_settings()
            self.pacing_manager = get_pacing_manager(config)
        return self.pacing_manager

    def get_current_status(self) -> PipelineStatus:
        """Get the current pipeline status."""
        pacing_manager = self._get_pacing_manager()
        status_data = pacing_manager.get_pacing_status()

        # Calculate pipeline efficiency
        efficiency = self._calculate_pipeline_efficiency(status_data)

        # Get recommended delay for next download
        recommended_delay = self._get_recommended_delay(status_data)

        status = PipelineStatus(
            # Download status
            downloads_in_progress=status_data.get("downloads_in_progress", 0),
            downloads_completed=status_data.get("downloads_completed", 0),
            # Processing status
            processing_queue_depth=status_data.get("queue_depth", 0),
            active_processing_jobs=status_data.get("active_processing_jobs", 0),
            recent_completions=status_data.get("recent_completions", 0),
            # Performance metrics
            current_processing_speed=status_data.get("current_processing_speed", 0.0),
            estimated_queue_clearance_time=status_data.get(
                "estimated_queue_clearance_time", 0.0
            ),
            avg_download_time=status_data.get("avg_download_time", 0.0),
            avg_processing_time=status_data.get("avg_processing_time", 0.0),
            # Rate limiting
            rate_limit_frequency=status_data.get("rate_limit_frequency", 0.0),
            # Recommendations
            should_pause_downloads=status_data.get("should_pause", False),
            recommended_delay=recommended_delay,
            # Efficiency metrics
            processing_to_download_ratio=status_data.get(
                "processing_to_download_ratio", 1.0
            ),
            pipeline_efficiency=efficiency,
        )

        # Store in history
        self.status_history.append((time.time(), status))
        self.last_status_time = time.time()

        # Keep only last 100 status updates
        if len(self.status_history) > 100:
            self.status_history = self.status_history[-100:]

        return status

    def _calculate_pipeline_efficiency(self, status_data: dict[str, Any]) -> float:
        """Calculate pipeline efficiency as a percentage."""
        downloads_completed = status_data.get("downloads_completed", 0)
        queue_depth = status_data.get("queue_depth", 0)

        if downloads_completed == 0:
            return 100.0  # No downloads yet, consider efficient

        # Efficiency is higher when queue depth is low relative to completed downloads
        if downloads_completed > 0:
            queue_ratio = queue_depth / downloads_completed
            efficiency = max(
                0.0, 100.0 - (queue_ratio * 50.0)
            )  # Penalize high queue ratios
            return min(100.0, efficiency)

        return 100.0

    def _get_recommended_delay(self, status_data: dict[str, Any]) -> float:
        """Get recommended delay for next download."""
        pacing_manager = self._get_pacing_manager()

        # Get current processing speed and queue status
        processing_speed = status_data.get("current_processing_speed", 0.0)
        queue_depth = status_data.get("queue_depth", 0)

        # Base delay calculation
        base_delay = 5.0  # Default 5 seconds

        # Adjust based on processing speed
        if processing_speed > 0:
            # If processing is fast, we can download more frequently
            if processing_speed > 2.0:  # More than 2 files per minute
                base_delay = max(2.0, base_delay * 0.5)
            elif processing_speed < 0.5:  # Less than 0.5 files per minute
                base_delay = min(15.0, base_delay * 2.0)

        # Adjust based on queue depth
        if queue_depth > 10:
            base_delay = min(20.0, base_delay * 1.5)
        elif queue_depth > 20:
            base_delay = min(30.0, base_delay * 2.0)

        # Adjust for rate limiting
        rate_limit_freq = status_data.get("rate_limit_frequency", 0.0)
        if rate_limit_freq > 1.0:
            base_delay = min(30.0, base_delay * 2.0)

        return base_delay

    def get_status_summary(self) -> str:
        """Get a human-readable status summary."""
        status = self.get_current_status()

        summary_parts = []

        # Overall status
        if status.should_pause_downloads:
            summary_parts.append("⏸️ Downloads PAUSED")
        else:
            summary_parts.append("✅ Downloads ACTIVE")

        # Processing status
        if status.current_processing_speed > 0:
            summary_parts.append(
                f"🎯 Processing: {status.current_processing_speed:.1f} files/min"
            )
        else:
            summary_parts.append("🎯 Processing: No recent activity")

        # Queue status
        if status.processing_queue_depth > 0:
            clearance_time = status.estimated_queue_clearance_time
            if clearance_time > 0:
                summary_parts.append(
                    f"📋 Queue: {status.processing_queue_depth} files (~{clearance_time:.0f}min to clear)"
                )
            else:
                summary_parts.append(f"📋 Queue: {status.processing_queue_depth} files")
        else:
            summary_parts.append("📋 Queue: Empty")

        # Efficiency
        summary_parts.append(f"⚡ Efficiency: {status.pipeline_efficiency:.0f}%")

        # Rate limiting
        if status.rate_limit_frequency > 0:
            summary_parts.append(
                f"⚠️ Rate limiting: {status.rate_limit_frequency:.1f} events/min"
            )

        # Recommendations
        if status.recommended_delay > 5.0:
            summary_parts.append(
                f"💡 Recommended delay: {status.recommended_delay:.1f}s"
            )

        return " | ".join(summary_parts)

    def get_detailed_report(self) -> str:
        """Get a detailed pipeline report."""
        status = self.get_current_status()

        report_lines = [
            "=== INTELLIGENT PACING PIPELINE REPORT ===",
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "DOWNLOAD STATUS:",
            f"  • Downloads in progress: {status.downloads_in_progress}",
            f"  • Downloads completed: {status.downloads_completed}",
            f"  • Average download time: {status.avg_download_time:.1f}s",
            "",
            "PROCESSING STATUS:",
            f"  • Active processing jobs: {status.active_processing_jobs}",
            f"  • Queue depth: {status.processing_queue_depth}",
            f"  • Current processing speed: {status.current_processing_speed:.2f} files/min",
            f"  • Average processing time: {status.avg_processing_time:.1f}s",
            f"  • Estimated queue clearance: {status.estimated_queue_clearance_time:.1f} min",
            f"  • Recent completions: {status.recent_completions}",
            "",
            "PERFORMANCE METRICS:",
            f"  • Processing/Download ratio: {status.processing_to_download_ratio:.1f}x",
            f"  • Pipeline efficiency: {status.pipeline_efficiency:.1f}%",
            f"  • Rate limiting frequency: {status.rate_limit_frequency:.2f} events/min",
            "",
            "RECOMMENDATIONS:",
            f"  • Should pause downloads: {'Yes' if status.should_pause_downloads else 'No'}",
            f"  • Recommended next delay: {status.recommended_delay:.1f}s",
        ]

        # Add warnings if needed
        warnings = []
        if status.processing_queue_depth > 20:
            warnings.append("⚠️ High processing queue - consider pausing downloads")
        if status.rate_limit_frequency > 2.0:
            warnings.append("⚠️ Frequent rate limiting - increase delays")
        if status.pipeline_efficiency < 50.0:
            warnings.append("⚠️ Low pipeline efficiency - check processing bottlenecks")
        if status.current_processing_speed < 0.1:
            warnings.append("⚠️ Very slow processing - check system resources")

        if warnings:
            report_lines.extend(
                ["", "WARNINGS:"] + [f"  • {warning}" for warning in warnings]
            )

        return "\n".join(report_lines)

    def monitor_continuously(
        self, interval_seconds: int = 30, max_iterations: int | None = None
    ):
        """
        Continuously monitor the pipeline status.

        Args:
            interval_seconds: How often to check status
            max_iterations: Maximum number of checks (None for infinite)
        """
        logger.info("Starting continuous pipeline monitoring...")

        iteration = 0
        try:
            while max_iterations is None or iteration < max_iterations:
                status = self.get_current_status()
                summary = self.get_status_summary()

                logger.info(f"Pipeline Status: {summary}")

                # Log warnings
                if status.should_pause_downloads:
                    logger.warning("Downloads are paused due to pipeline constraints")

                if status.rate_limit_frequency > 1.0:
                    logger.warning(
                        f"Rate limiting detected: {status.rate_limit_frequency:.1f} events/min"
                    )

                if status.pipeline_efficiency < 50.0:
                    logger.warning(
                        f"Low pipeline efficiency: {status.pipeline_efficiency:.1f}%"
                    )

                iteration += 1
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("Pipeline monitoring stopped by user")
        except Exception as e:
            logger.error(f"Pipeline monitoring error: {e}")


# Global monitor instance
_global_monitor = None


def get_pacing_monitor() -> PacingMonitor:
    """Get the global pacing monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PacingMonitor()
    return _global_monitor


def print_current_status():
    """Print current pipeline status to console."""
    monitor = get_pacing_monitor()
    status = monitor.get_current_status()
    print(monitor.get_status_summary())


def print_detailed_report():
    """Print detailed pipeline report to console."""
    monitor = get_pacing_monitor()
    print(monitor.get_detailed_report())


def start_monitoring(interval_seconds: int = 30):
    """Start continuous monitoring."""
    monitor = get_pacing_monitor()
    monitor.monitor_continuously(interval_seconds)
