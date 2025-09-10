"""
Real-time monitoring utilities for disk space and system resources.

Provides continuous monitoring during batch operations to prevent resource exhaustion.
"""

import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path

import psutil

from ..logger import get_logger

logger = get_logger(__name__)


class RealtimeDiskMonitor:
    """
    Real-time disk space monitor that can trigger callbacks when thresholds are reached.

    Monitors disk space continuously during long-running operations like batch downloads.
    """

    def __init__(
        self,
        watch_path: Path | str,
        warning_threshold_gb: float = 5.0,
        critical_threshold_gb: float = 2.0,
        check_interval_seconds: float = 30.0,
    ):
        """
        Initialize disk space monitor.

        Args:
            watch_path: Path to monitor for disk space
            warning_threshold_gb: Warn when free space drops below this (GB)
            critical_threshold_gb: Critical alert when free space drops below this (GB)
            check_interval_seconds: How often to check disk space
        """
        self.watch_path = Path(watch_path)
        self.warning_threshold_gb = warning_threshold_gb
        self.critical_threshold_gb = critical_threshold_gb
        self.check_interval = check_interval_seconds

        # Monitoring state
        self.monitoring = False
        self.monitor_thread = None
        self.last_warning_time = 0
        self.last_critical_time = 0

        # Callbacks
        self.warning_callback: Callable[[float], None] | None = None
        self.critical_callback: Callable[[float], None] | None = None
        self.recovery_callback: Callable[[float], None] | None = None

        # State tracking
        self.was_warning = False
        self.was_critical = False

    def set_warning_callback(self, callback: Callable[[float], None]):
        """Set callback for warning threshold."""
        self.warning_callback = callback

    def set_critical_callback(self, callback: Callable[[float], None]):
        """Set callback for critical threshold."""
        self.critical_callback = callback

    def set_recovery_callback(self, callback: Callable[[float], None]):
        """Set callback for recovery from low disk space."""
        self.recovery_callback = callback

    def get_disk_space_gb(self) -> tuple[float, float, float]:
        """
        Get current disk space information.

        Returns:
            Tuple of (total_gb, used_gb, free_gb)
        """
        try:
            disk_usage = shutil.disk_usage(self.watch_path)
            total_gb = disk_usage.total / (1024**3)
            free_gb = disk_usage.free / (1024**3)
            used_gb = total_gb - free_gb
            return total_gb, used_gb, free_gb
        except Exception as e:
            logger.error(f"Error getting disk space: {e}")
            return 0.0, 0.0, 0.0

    def start_monitoring(self):
        """Start real-time disk space monitoring."""
        if self.monitoring:
            logger.warning("Disk monitoring already running")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Started real-time disk monitoring for {self.watch_path}")

    def stop_monitoring(self):
        """Stop real-time disk space monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("Stopped real-time disk monitoring")

    def _monitor_loop(self):
        """Main monitoring loop (runs in separate thread)."""
        while self.monitoring:
            try:
                total_gb, used_gb, free_gb = self.get_disk_space_gb()

                if free_gb == 0.0:  # Error getting disk space
                    time.sleep(self.check_interval)
                    continue

                current_time = time.time()

                # Check for critical threshold
                if free_gb <= self.critical_threshold_gb:
                    if not self.was_critical and self.critical_callback:
                        # Avoid spam by only calling once per hour
                        if current_time - self.last_critical_time > 3600:
                            logger.error(
                                f"CRITICAL: Only {free_gb:.1f}GB free space remaining!"
                            )
                            self.critical_callback(free_gb)
                            self.last_critical_time = current_time
                    self.was_critical = True

                # Check for warning threshold
                elif free_gb <= self.warning_threshold_gb:
                    if not self.was_warning and self.warning_callback:
                        # Avoid spam by only calling once every 10 minutes
                        if current_time - self.last_warning_time > 600:
                            logger.warning(
                                f"WARNING: Only {free_gb:.1f}GB free space remaining"
                            )
                            self.warning_callback(free_gb)
                            self.last_warning_time = current_time
                    self.was_warning = True
                    self.was_critical = (
                        False  # Reset critical if we're above critical threshold
                    )

                # Recovery
                else:
                    if (
                        self.was_warning or self.was_critical
                    ) and self.recovery_callback:
                        logger.info(
                            f"RECOVERY: Disk space recovered to {free_gb:.1f}GB"
                        )
                        self.recovery_callback(free_gb)
                    self.was_warning = False
                    self.was_critical = False

                # Log periodic status
                if current_time % 300 < self.check_interval:  # Every 5 minutes
                    logger.debug(
                        f"Disk space: {free_gb:.1f}GB free / {total_gb:.1f}GB total"
                    )

            except Exception as e:
                logger.error(f"Error in disk monitoring loop: {e}")

            time.sleep(self.check_interval)


class RealtimeMemoryMonitor:
    """
    Real-time memory monitor for tracking memory usage during batch operations.
    """

    def __init__(
        self,
        warning_threshold_percent: float = 85.0,
        critical_threshold_percent: float = 95.0,
        check_interval_seconds: float = 10.0,
    ):
        """
        Initialize memory monitor.

        Args:
            warning_threshold_percent: Warn when memory usage exceeds this %
            critical_threshold_percent: Critical alert when memory usage exceeds this %
            check_interval_seconds: How often to check memory usage
        """
        self.warning_threshold = warning_threshold_percent
        self.critical_threshold = critical_threshold_percent
        self.check_interval = check_interval_seconds

        # Monitoring state
        self.monitoring = False
        self.monitor_thread = None

        # Callbacks
        self.warning_callback: Callable[[float], None] | None = None
        self.critical_callback: Callable[[float], None] | None = None

    def set_warning_callback(self, callback: Callable[[float], None]):
        """Set callback for warning threshold."""
        self.warning_callback = callback

    def set_critical_callback(self, callback: Callable[[float], None]):
        """Set callback for critical threshold."""
        self.critical_callback = callback

    def get_memory_usage(self) -> tuple[float, float, float]:
        """
        Get current memory usage information.

        Returns:
            Tuple of (total_gb, used_gb, percent_used)
        """
        try:
            memory = psutil.virtual_memory()
            total_gb = memory.total / (1024**3)
            used_gb = memory.used / (1024**3)
            percent_used = memory.percent
            return total_gb, used_gb, percent_used
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return 0.0, 0.0, 0.0

    def start_monitoring(self):
        """Start real-time memory monitoring."""
        if self.monitoring:
            logger.warning("Memory monitoring already running")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Started real-time memory monitoring")

    def stop_monitoring(self):
        """Stop real-time memory monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("Stopped real-time memory monitoring")

    def _monitor_loop(self):
        """Main monitoring loop (runs in separate thread)."""
        last_warning_time = 0
        last_critical_time = 0

        while self.monitoring:
            try:
                total_gb, used_gb, percent_used = self.get_memory_usage()
                current_time = time.time()

                if percent_used >= self.critical_threshold:
                    if (
                        self.critical_callback
                        and current_time - last_critical_time > 60
                    ):
                        logger.error(f"CRITICAL: Memory usage at {percent_used:.1f}%")
                        self.critical_callback(percent_used)
                        last_critical_time = current_time

                elif percent_used >= self.warning_threshold:
                    if self.warning_callback and current_time - last_warning_time > 30:
                        logger.warning(f"WARNING: Memory usage at {percent_used:.1f}%")
                        self.warning_callback(percent_used)
                        last_warning_time = current_time

            except Exception as e:
                logger.error(f"Error in memory monitoring loop: {e}")

            time.sleep(self.check_interval)


class RealtimeResourceManager:
    """
    Unified real-time resource manager that monitors both disk and memory.
    """

    def __init__(
        self,
        watch_path: Path | str,
        disk_warning_gb: float = 5.0,
        disk_critical_gb: float = 2.0,
        memory_warning_percent: float = 85.0,
        memory_critical_percent: float = 95.0,
    ):
        """
        Initialize unified resource manager.

        Args:
            watch_path: Path to monitor for disk space
            disk_warning_gb: Disk space warning threshold (GB)
            disk_critical_gb: Disk space critical threshold (GB)
            memory_warning_percent: Memory warning threshold (%)
            memory_critical_percent: Memory critical threshold (%)
        """
        self.disk_monitor = RealtimeDiskMonitor(
            watch_path, disk_warning_gb, disk_critical_gb
        )
        self.memory_monitor = RealtimeMemoryMonitor(
            memory_warning_percent, memory_critical_percent
        )

        # Resource management callbacks
        self.pause_callback: Callable[[], None] | None = None
        self.resume_callback: Callable[[], None] | None = None
        self.stop_callback: Callable[[], None] | None = None

        # Set up internal callbacks
        self.disk_monitor.set_critical_callback(self._handle_disk_critical)
        self.memory_monitor.set_critical_callback(self._handle_memory_critical)

    def set_pause_callback(self, callback: Callable[[], None]):
        """Set callback to pause operations during resource pressure."""
        self.pause_callback = callback

    def set_resume_callback(self, callback: Callable[[], None]):
        """Set callback to resume operations after resource recovery."""
        self.resume_callback = callback

    def set_stop_callback(self, callback: Callable[[], None]):
        """Set callback to stop operations during critical resource issues."""
        self.stop_callback = callback

    def start_monitoring(self):
        """Start monitoring both disk and memory."""
        self.disk_monitor.start_monitoring()
        self.memory_monitor.start_monitoring()
        logger.info("Started unified resource monitoring")

    def stop_monitoring(self):
        """Stop monitoring both disk and memory."""
        self.disk_monitor.stop_monitoring()
        self.memory_monitor.stop_monitoring()
        logger.info("Stopped unified resource monitoring")

    def get_status(self) -> dict:
        """Get current resource status."""
        total_gb, used_gb, free_gb = self.disk_monitor.get_disk_space_gb()
        mem_total_gb, mem_used_gb, mem_percent = self.memory_monitor.get_memory_usage()

        return {
            "disk": {
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "warning_threshold_gb": self.disk_monitor.warning_threshold_gb,
                "critical_threshold_gb": self.disk_monitor.critical_threshold_gb,
            },
            "memory": {
                "total_gb": mem_total_gb,
                "used_gb": mem_used_gb,
                "percent_used": mem_percent,
                "warning_threshold_percent": self.memory_monitor.warning_threshold,
                "critical_threshold_percent": self.memory_monitor.critical_threshold,
            },
        }

    def _handle_disk_critical(self, free_gb: float):
        """Handle critical disk space situation."""
        logger.error(f"🚨 CRITICAL DISK SPACE: Only {free_gb:.1f}GB remaining!")
        if self.pause_callback:
            self.pause_callback()

    def _handle_memory_critical(self, percent_used: float):
        """Handle critical memory usage situation."""
        logger.error(f"🚨 CRITICAL MEMORY USAGE: {percent_used:.1f}% used!")
        if self.pause_callback:
            self.pause_callback()
