"""
Memory Safety Monitoring Module

Provides comprehensive memory monitoring and management capabilities
to prevent crashes due to memory exhaustion during batch processing.

Features:
- Real-time memory pressure detection
- Adaptive resource management
- Emergency cleanup procedures
- Memory usage optimization
- Process memory isolation monitoring
"""

import gc
import logging
import os
import tempfile
import threading
import time
import weakref
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


class MemoryMonitor:
    """Monitors system memory usage and provides cleanup mechanisms."""

    def __init__(
        self,
        memory_threshold: float = 85.0,
        swap_threshold: float = 50.0,
        growth_rate_threshold: float = 10.0,
    ):
        """
        Initialize memory monitor.

        Args:
            memory_threshold: RAM usage percentage that triggers warnings
            swap_threshold: Swap usage percentage that triggers warnings
            growth_rate_threshold: Memory growth rate (MB/s) that triggers warnings
        """
        self.memory_threshold = memory_threshold
        self.swap_threshold = swap_threshold
        self.growth_rate_threshold = growth_rate_threshold

        # Memory tracking
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss
        self.last_memory_check = time.time()
        self.last_memory_usage = self.initial_memory
        self.memory_history = []

        # Cleanup tracking
        self.temp_files = set()
        self.model_caches = weakref.WeakSet()
        self.cleanup_callbacks = []

        # Thread safety
        self._lock = threading.Lock()

        # Configuration
        self.enable_aggressive_cleanup = False
        self.max_memory_gb = self._get_system_memory_gb()

    def _get_system_memory_gb(self) -> float:
        """Get total system memory in GB."""
        return psutil.virtual_memory().total / (1024**3)

    def register_temp_file(self, file_path: str | Path):
        """Register a temporary file for cleanup."""
        with self._lock:
            self.temp_files.add(str(file_path))

    def register_model_cache(self, cache_object):
        """Register a model cache object for cleanup."""
        with self._lock:
            self.model_caches.add(cache_object)

    def register_cleanup_callback(self, callback):
        """Register a cleanup callback function."""
        with self._lock:
            self.cleanup_callbacks.append(callback)

    def check_memory_pressure(self) -> tuple[bool, str]:
        """
        Check current memory pressure status.

        Returns:
            Tuple of (is_pressure, description)
        """
        try:
            # Get system memory stats
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory() if hasattr(psutil, "swap_memory") else None

            # Get process memory stats
            process_memory = self.process.memory_info()
            process_memory_mb = process_memory.rss / (1024 * 1024)

            # Calculate memory growth rate
            current_time = time.time()
            time_delta = current_time - self.last_memory_check
            memory_delta = process_memory.rss - self.last_memory_usage
            growth_rate_mb_per_sec = 0

            if time_delta > 0:
                growth_rate_mb_per_sec = (memory_delta / (1024 * 1024)) / time_delta

            # Update tracking
            with self._lock:
                self.last_memory_check = current_time
                self.last_memory_usage = process_memory.rss
                self.memory_history.append(
                    {
                        "timestamp": current_time,
                        "process_memory_mb": process_memory_mb,
                        "system_memory_percent": memory.percent,
                        "growth_rate": growth_rate_mb_per_sec,
                    }
                )

                # Keep only last 100 entries
                if len(self.memory_history) > 100:
                    self.memory_history.pop(0)

            # Check for pressure conditions
            pressure_reasons = []

            if memory.percent > self.memory_threshold:
                pressure_reasons.append(f"High RAM usage: {memory.percent:.1f}%")

            if swap and swap.percent > self.swap_threshold:
                pressure_reasons.append(f"High swap usage: {swap.percent:.1f}%")

            if growth_rate_mb_per_sec > self.growth_rate_threshold:
                pressure_reasons.append(
                    f"High memory growth rate: {growth_rate_mb_per_sec:.1f} MB/s"
                )

            # Process-specific checks
            if process_memory_mb > (
                self.max_memory_gb * 1024 * 0.8
            ):  # 80% of system memory
                pressure_reasons.append(
                    f"Process using {process_memory_mb:.0f}MB ({process_memory_mb/1024:.1f}GB)"
                )

            if pressure_reasons:
                return True, "; ".join(pressure_reasons)
            else:
                return (
                    False,
                    f"Memory usage normal: {memory.percent:.1f}% RAM, {process_memory_mb:.0f}MB process",
                )

        except Exception as e:
            logger.error(f"Error checking memory pressure: {e}")
            return False, f"Memory check error: {e}"

    def get_memory_stats(self) -> dict[str, float]:
        """Get detailed memory statistics."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory() if hasattr(psutil, "swap_memory") else None
            process_memory = self.process.memory_info()

            stats = {
                "system_memory_total_gb": memory.total / (1024**3),
                "system_memory_available_gb": memory.available / (1024**3),
                "system_memory_percent": memory.percent,
                "process_memory_mb": process_memory.rss / (1024 * 1024),
                "process_memory_gb": process_memory.rss / (1024**3),
                "memory_since_start_mb": (process_memory.rss - self.initial_memory)
                / (1024 * 1024),
            }

            if swap:
                stats.update(
                    {
                        "swap_total_gb": swap.total / (1024**3),
                        "swap_used_gb": swap.used / (1024**3),
                        "swap_percent": swap.percent,
                    }
                )

            return stats

        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {}

    def emergency_cleanup(self):
        """Perform emergency memory cleanup."""
        logger.info("Starting emergency memory cleanup")

        try:
            # 1. Force garbage collection
            collected = gc.collect()
            logger.info(f"Garbage collection freed {collected} objects")

            # 2. Clean up temporary files
            self._cleanup_temp_files()

            # 3. Clear model caches
            self._clear_model_caches()

            # 4. Run registered cleanup callbacks
            self._run_cleanup_callbacks()

            # 5. Force another garbage collection
            gc.collect()

            logger.info("Emergency cleanup completed")

        except Exception as e:
            logger.error(f"Error during emergency cleanup: {e}")

    def cleanup_between_files(self):
        """Lighter cleanup to run between file processing."""
        try:
            # Gentle garbage collection
            gc.collect()

            # Clean up any temporary files that are safe to remove
            self._cleanup_temp_files(aggressive=False)

        except Exception as e:
            logger.error(f"Error during between-files cleanup: {e}")

    def _cleanup_temp_files(self, aggressive: bool = True):
        """Clean up temporary files."""
        with self._lock:
            files_to_remove = list(self.temp_files)

        removed_count = 0
        removed_size = 0

        for file_path in files_to_remove:
            try:
                path = Path(file_path)
                if path.exists():
                    size = path.stat().st_size
                    path.unlink()
                    removed_count += 1
                    removed_size += size

                with self._lock:
                    self.temp_files.discard(file_path)

            except Exception as e:
                logger.warning(f"Failed to remove temp file {file_path}: {e}")

        if removed_count > 0:
            logger.info(
                f"Cleaned up {removed_count} temp files, freed {removed_size / (1024*1024):.1f}MB"
            )

        # Also clean system temp directory if aggressive
        if aggressive:
            self._cleanup_system_temp()

    def _cleanup_system_temp(self):
        """Clean up system temporary directory of our files."""
        try:
            temp_dir = Path(tempfile.gettempdir())
            our_files = list(temp_dir.glob("knowledge_chipper_*"))
            our_files.extend(list(temp_dir.glob("tmp*_audio_*")))
            our_files.extend(list(temp_dir.glob("ffmpeg_*")))

            removed_count = 0
            for file_path in our_files:
                try:
                    if file_path.is_file():
                        file_path.unlink()
                        removed_count += 1
                    elif file_path.is_dir():
                        import shutil

                        shutil.rmtree(file_path)
                        removed_count += 1
                except Exception:
                    pass  # Ignore errors for system temp cleanup

            if removed_count > 0:
                logger.info(
                    f"Cleaned up {removed_count} files from system temp directory"
                )

        except Exception as e:
            logger.warning(f"Error cleaning system temp directory: {e}")

    def _clear_model_caches(self):
        """Clear model caches."""
        cleared_count = 0

        # Clear registered model caches
        with self._lock:
            model_caches = list(self.model_caches)

        for cache in model_caches:
            try:
                if hasattr(cache, "clear"):
                    cache.clear()
                    cleared_count += 1
                elif hasattr(cache, "unload"):
                    cache.unload()
                    cleared_count += 1
            except Exception as e:
                logger.warning(f"Failed to clear model cache: {e}")

        # Try to clear common ML framework caches
        try:
            # PyTorch
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            cleared_count += 1
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Failed to clear PyTorch cache: {e}")

        try:
            # TensorFlow
            import tensorflow as tf

            tf.keras.backend.clear_session()
            cleared_count += 1
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Failed to clear TensorFlow cache: {e}")

        if cleared_count > 0:
            logger.info(f"Cleared {cleared_count} model caches")

    def _run_cleanup_callbacks(self):
        """Run registered cleanup callbacks."""
        with self._lock:
            callbacks = list(self.cleanup_callbacks)

        for callback in callbacks:
            try:
                callback()
            except Exception as e:
                logger.warning(f"Cleanup callback failed: {e}")

    def get_adaptive_batch_size(self, base_batch_size: int, file_size_mb: float) -> int:
        """Get adaptive batch size based on current memory pressure."""
        try:
            is_pressure, _ = self.check_memory_pressure()
            memory_stats = self.get_memory_stats()

            available_gb = memory_stats.get("system_memory_available_gb", 8)

            # Reduce batch size under memory pressure
            if is_pressure:
                return max(1, base_batch_size // 4)

            # Adjust based on available memory and file size
            if available_gb < 4:  # Less than 4GB available
                return max(1, base_batch_size // 2)
            elif available_gb > 16:  # More than 16GB available
                return min(base_batch_size * 2, 32)  # Cap at 32
            else:
                return base_batch_size

        except Exception as e:
            logger.error(f"Error calculating adaptive batch size: {e}")
            return base_batch_size

    def should_load_large_model(self, model_size_gb: float) -> bool:
        """Determine if it's safe to load a large model."""
        try:
            memory_stats = self.get_memory_stats()
            available_gb = memory_stats.get("system_memory_available_gb", 0)

            # Need at least 2x the model size in available memory
            return available_gb >= (model_size_gb * 2)

        except Exception as e:
            logger.error(f"Error checking model load safety: {e}")
            return False

    def start_monitoring(self, check_interval: int = 30):
        """Start continuous memory monitoring in a background thread."""

        def monitor_loop():
            while getattr(self, "_monitoring", True):
                try:
                    is_pressure, message = self.check_memory_pressure()
                    if is_pressure:
                        logger.warning(f"Memory pressure detected: {message}")

                        # Auto-cleanup if configured
                        if self.enable_aggressive_cleanup:
                            self.cleanup_between_files()

                    time.sleep(check_interval)

                except Exception as e:
                    logger.error(f"Error in memory monitoring loop: {e}")
                    time.sleep(check_interval)

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info("Started memory monitoring")

    def stop_monitoring(self):
        """Stop continuous memory monitoring."""
        self._monitoring = False
        if hasattr(self, "_monitor_thread"):
            self._monitor_thread.join(timeout=5)
        logger.info("Stopped memory monitoring")

    def get_memory_report(self) -> str:
        """Generate a detailed memory usage report."""
        try:
            stats = self.get_memory_stats()
            is_pressure, pressure_msg = self.check_memory_pressure()

            report_lines = [
                "=== Memory Usage Report ===",
                f"System Memory: {stats.get('system_memory_percent', 0):.1f}% used",
                f"Available: {stats.get('system_memory_available_gb', 0):.1f}GB",
                f"Process Memory: {stats.get('process_memory_mb', 0):.1f}MB",
                f"Memory Since Start: +{stats.get('memory_since_start_mb', 0):.1f}MB",
            ]

            if "swap_percent" in stats:
                report_lines.append(f"Swap Usage: {stats['swap_percent']:.1f}%")

            report_lines.append(f"Memory Pressure: {'YES' if is_pressure else 'NO'}")
            if is_pressure:
                report_lines.append(f"Pressure Details: {pressure_msg}")

            report_lines.append(f"Temp Files Tracked: {len(self.temp_files)}")
            report_lines.append(f"Model Caches Tracked: {len(self.model_caches)}")

            return "\n".join(report_lines)

        except Exception as e:
            return f"Error generating memory report: {e}"


# Global memory monitor instance
_global_monitor = None


def get_memory_monitor() -> MemoryMonitor:
    """Get the global memory monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = MemoryMonitor()
    return _global_monitor


def clear_model_caches():
    """Convenience function to clear all model caches."""
    monitor = get_memory_monitor()
    monitor._clear_model_caches()


def emergency_cleanup():
    """Convenience function for emergency cleanup."""
    monitor = get_memory_monitor()
    monitor.emergency_cleanup()


def check_memory_pressure() -> tuple[bool, str]:
    """Convenience function to check memory pressure."""
    monitor = get_memory_monitor()
    return monitor.check_memory_pressure()
