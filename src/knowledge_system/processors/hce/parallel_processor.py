"""
Parallel HCE Processing with Memory Pressure Integration

This module provides parallel processing capabilities for HCE components
while respecting system memory constraints using the existing memory pressure
monitoring infrastructure.
"""

import gc
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List

import psutil

logger = logging.getLogger(__name__)


class MemoryPressureHandler:
    """Handles memory pressure situations with various mitigation strategies."""

    def __init__(
        self, warning_threshold=80, critical_threshold=90, emergency_threshold=95
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


class ParallelHCEProcessor:
    """
    Parallel processor for HCE components with memory pressure awareness.

    Provides efficient parallel processing of HCE tasks while dynamically
    adjusting concurrency based on system memory pressure.
    """

    def __init__(self, max_workers: int = None):
        self.memory_handler = MemoryPressureHandler()
        self.max_workers = max_workers or self._calculate_optimal_workers()
        self.active_tasks = 0

    def _calculate_optimal_workers(self) -> int:
        """Calculate optimal number of workers based on system resources."""
        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024**3)
        cpu_cores = psutil.cpu_count(logical=False) or 4

        # LLM calls are less memory-intensive than full video processing
        # Estimate ~200MB per concurrent LLM call vs ~1.1GB per video
        llm_memory_per_worker = 0.2  # GB

        # Memory-based limit
        memory_based_max = int(available_gb / llm_memory_per_worker)

        # CPU-based limit (conservative for LLM I/O bound tasks)
        cpu_based_max = min(cpu_cores * 2, 12)  # Cap at 12 for stability

        # Use the more conservative limit
        optimal = min(
            memory_based_max, cpu_based_max, 3
        )  # Cap at 3 for OpenAI API stability

        logger.info(
            f"Calculated optimal workers: {optimal} "
            f"(memory_limit={memory_based_max}, cpu_limit={cpu_based_max}, available_gb={available_gb:.1f})"
        )

        return max(1, optimal)

    def process_parallel(
        self,
        items: list[Any],
        processor_func: Callable,
        progress_callback: Callable = None,
    ) -> list[Any]:
        """
        Process items in parallel with memory pressure monitoring.

        Args:
            items: List of items to process
            processor_func: Function to process each item
            progress_callback: Optional progress reporting function

        Returns:
            List of processed results
        """
        if not items:
            return []

        if len(items) == 1:
            # Single item - no need for parallelization overhead
            return [processor_func(items[0])]

        logger.info(
            f"Starting parallel processing of {len(items)} items with {self.max_workers} workers"
        )

        results = [None] * len(items)  # Preserve order
        completed_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit initial batch of futures
            future_to_index = {}
            submitted_count = 0

            # Submit first batch
            initial_batch_size = min(self.max_workers, len(items))
            for i in range(initial_batch_size):
                future = executor.submit(processor_func, items[i])
                future_to_index[future] = i
                submitted_count += 1
                self.active_tasks += 1

            # Process completed futures and submit new ones
            max_iterations = len(items) * 10  # Safety limit to prevent infinite loops
            iteration_count = 0

            while (
                submitted_count < len(items) or future_to_index
            ) and iteration_count < max_iterations:
                iteration_count += 1
                # Check memory pressure before submitting new tasks
                pressure_level, message = self.memory_handler.check_memory_pressure()

                if pressure_level >= 2:  # Critical or emergency
                    logger.warning(f"Memory pressure detected: {message}")

                    # Adjust concurrency
                    new_max, should_pause = self.memory_handler.mitigate_pressure(
                        self.active_tasks
                    )

                    if should_pause:
                        logger.warning(
                            "Pausing new task submission due to emergency memory pressure"
                        )
                        # Wait for some tasks to complete before continuing
                        if future_to_index:
                            completed_futures = []
                            for future in as_completed(
                                list(future_to_index.keys()), timeout=30
                            ):
                                completed_futures.append(future)
                                if len(completed_futures) >= self.active_tasks // 2:
                                    break

                            # Process completed futures
                            for future in completed_futures:
                                index = future_to_index.pop(future)
                                try:
                                    results[index] = future.result()
                                    completed_count += 1
                                    self.active_tasks -= 1
                                except Exception as e:
                                    logger.error(f"Task {index} failed: {e}")
                                    results[index] = None
                                    self.active_tasks -= 1
                        continue

                # Wait for next completion
                if future_to_index:
                    try:
                        # Use longer timeout for LLM API calls - they can take 30+ seconds
                        completed_future = next(
                            as_completed(future_to_index.keys(), timeout=60)
                        )
                        index = future_to_index.pop(completed_future)

                        try:
                            results[index] = completed_future.result()
                            completed_count += 1
                        except Exception as e:
                            logger.error(f"Task {index} failed: {e}")
                            results[index] = None

                        self.active_tasks -= 1
                    except StopIteration:
                        # No futures completed within timeout - continue loop
                        logger.debug(
                            "No futures completed within timeout, continuing..."
                        )
                        continue

                    # Submit next task if available and memory allows
                    if submitted_count < len(items) and pressure_level < 3:
                        future = executor.submit(processor_func, items[submitted_count])
                        future_to_index[future] = submitted_count
                        submitted_count += 1
                        self.active_tasks += 1

                    # Report progress
                    if progress_callback:
                        progress_callback(
                            f"Processed {completed_count}/{len(items)} items"
                        )

        # Handle any remaining unfinished futures
        if future_to_index:
            logger.warning(
                f"Cancelling {len(future_to_index)} unfinished futures due to timeout or iteration limit"
            )
            for future in future_to_index.keys():
                future.cancel()

        if iteration_count >= max_iterations:
            logger.error(
                f"Parallel processing stopped due to iteration limit ({max_iterations})"
            )

        logger.info(
            f"Parallel processing completed: {completed_count}/{len(items)} successful"
        )
        return [r for r in results if r is not None]

    def process_chunks_parallel(
        self,
        chunks: list[list[Any]],
        chunk_processor_func: Callable,
        progress_callback: Callable = None,
    ) -> list[Any]:
        """
        Process chunks in parallel - optimized for chunked HCE operations.

        Args:
            chunks: List of chunks (each chunk is a list of segments)
            chunk_processor_func: Function to process each chunk
            progress_callback: Optional progress reporting function

        Returns:
            Flattened list of results from all chunks
        """
        chunk_results = self.process_parallel(
            chunks, chunk_processor_func, progress_callback
        )

        # Flatten results
        flattened_results = []
        for chunk_result in chunk_results:
            if isinstance(chunk_result, list):
                flattened_results.extend(chunk_result)
            elif chunk_result is not None:
                flattened_results.append(chunk_result)

        return flattened_results


# Convenience function for easy integration
def create_parallel_processor(max_workers: int = None) -> ParallelHCEProcessor:
    """Create a parallel processor with optimal settings."""
    return ParallelHCEProcessor(max_workers=max_workers)
