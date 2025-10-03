#!/usr/bin/env python3
"""
Parallel Processing Integration for Knowledge System

Integrates the dynamic parallelization manager with the existing
processing pipeline to provide intelligent resource-aware parallelization.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .dynamic_parallelization import (
    DynamicParallelizationManager,
    JobMetrics,
    JobType,
    get_parallelization_manager,
    initialize_parallelization_manager,
)

logger = logging.getLogger(__name__)


class ParallelProcessor:
    """
    Intelligent parallel processor that manages concurrent execution
    of mining, evaluation, and other knowledge processing tasks.
    """

    def __init__(self, hardware_specs: dict[str, Any]):
        self.hardware_specs = hardware_specs
        self.manager = initialize_parallelization_manager(hardware_specs)
        self.executors: dict[JobType, ThreadPoolExecutor | ProcessPoolExecutor] = {}

        # Initialize executors for each job type
        self._initialize_executors()

        logger.info(f"Parallel processor initialized with dynamic resource management")

    def _initialize_executors(self):
        """Initialize thread/process pools for each job type"""
        for job_type in JobType:
            # Get optimal workers from dynamic parallelization manager
            optimal_workers = self.manager.get_optimal_workers(job_type)

            if job_type == JobType.DOWNLOAD:
                # Downloads: I/O bound, use thread pools for high concurrency
                self.executors[job_type] = ThreadPoolExecutor(
                    max_workers=optimal_workers,
                    thread_name_prefix=f"{job_type.value}_download",
                )
            elif job_type in [
                JobType.MINER,
                JobType.FLAGSHIP_EVALUATOR,
                JobType.VOICE_FINGERPRINTING,
            ]:
                # CPU-intensive tasks - use thread pools (ProcessPoolExecutor has issues with complex objects)
                self.executors[job_type] = ThreadPoolExecutor(
                    max_workers=optimal_workers,
                    thread_name_prefix=f"{job_type.value}_process",
                )
            else:
                # I/O bound tasks - use thread pools
                self.executors[job_type] = ThreadPoolExecutor(
                    max_workers=optimal_workers,
                    thread_name_prefix=f"{job_type.value}_thread",
                )

    async def process_batch_parallel(
        self,
        job_type: JobType,
        items: list[Any],
        processing_func: Callable[[Any], Any],
        batch_size: int | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[Any]:
        """
        Process a batch of items in parallel with dynamic worker adjustment.

        Args:
            job_type: Type of job being processed
            items: List of items to process
            processing_func: Function to process each item
            batch_size: Optional batch size (auto-calculated if None)
            progress_callback: Optional progress callback function

        Returns:
            List of processed results
        """
        if not items:
            return []

        # Calculate optimal batch size if not provided
        if batch_size is None:
            batch_size = self._calculate_optimal_batch_size(job_type, len(items))

        logger.info(
            f"Processing {len(items)} items with {job_type.value} "
            f"(batch size: {batch_size}, workers: {self.manager.worker_pools[job_type].current_workers})"
        )

        results = []
        completed = 0
        total = len(items)

        # Process in batches with dynamic worker adjustment
        for i in range(0, total, batch_size):
            batch = items[i : i + batch_size]

            # Get optimal number of workers for current conditions
            optimal_workers = self.manager.get_optimal_workers(job_type, len(batch))
            executor = self.executors[job_type]

            # Note: ThreadPoolExecutor max_workers cannot be changed after creation
            # We limit the number of futures we submit instead

            # Submit batch jobs
            futures = []
            for item in batch:
                metrics = self.manager.start_job(job_type)
                future = executor.submit(
                    self._process_with_metrics, processing_func, item, metrics
                )
                futures.append(future)

            # Collect results as they complete
            batch_results = []
            for future in as_completed(
                futures[:optimal_workers]
            ):  # Limit concurrent futures
                try:
                    result = future.result()
                    batch_results.append(result)
                    completed += 1

                    if progress_callback:
                        progress_callback(completed, total)

                except Exception as e:
                    logger.error(f"Error processing {job_type.value} item: {e}")
                    batch_results.append(None)

            results.extend(batch_results)

        logger.info(
            f"Completed {job_type.value} batch processing: {completed}/{total} items"
        )
        return results

    async def process_downloads_parallel(
        self,
        urls: list[str],
        download_func: Callable[[str], Any],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[Any]:
        """Process downloads with dynamic parallelization"""
        return await self.process_batch_parallel(
            JobType.DOWNLOAD, urls, download_func, progress_callback=progress_callback
        )

    async def process_mining_parallel(
        self,
        items: list[Any],
        mining_func: Callable[[Any], dict[str, Any]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Process mining (Stage-A) with dynamic parallelization"""
        return await self.process_batch_parallel(
            JobType.MINER, items, mining_func, progress_callback=progress_callback
        )

    async def process_evaluation_parallel(
        self,
        items: list[dict[str, Any]],
        evaluation_func: Callable[[dict[str, Any]], dict[str, Any]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Process evaluation (Stage-B) with dynamic parallelization"""
        return await self.process_batch_parallel(
            JobType.FLAGSHIP_EVALUATOR,
            items,
            evaluation_func,
            progress_callback=progress_callback,
        )

    def _process_with_metrics(
        self, processing_func: Callable, item: Any, metrics: JobMetrics
    ) -> Any:
        """Process an item while tracking metrics"""
        try:
            result = processing_func(item)
            self.manager.complete_job(metrics, success=True)
            return result
        except Exception as e:
            self.manager.complete_job(metrics, success=False, error=str(e))
            raise

    def _calculate_optimal_batch_size(self, job_type: JobType, total_items: int) -> int:
        """Calculate optimal batch size based on job type and hardware"""
        pool = self.manager.worker_pools[job_type]

        # Base batch size on available workers and job characteristics
        if job_type == JobType.MINER:
            # CPU-intensive, can handle larger batches
            return min(8, max(2, pool.current_workers * 2))
        elif job_type == JobType.FLAGSHIP_EVALUATOR:
            # Memory-intensive, moderate batches
            return min(4, max(1, pool.current_workers))
        elif job_type == JobType.TRANSCRIPTION:
            # I/O bound, smaller batches
            return min(2, max(1, pool.current_workers // 2))
        else:
            # Default
            return min(4, max(1, pool.current_workers))

    async def process_miner_batch(
        self,
        chunks: list[str],
        miner_func: Callable[[str], dict[str, Any]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Process mining chunks in parallel with dynamic scaling"""
        return await self.process_batch_parallel(
            JobType.MINER, chunks, miner_func, progress_callback=progress_callback
        )

    async def process_evaluator_batch(
        self,
        claims: list[dict[str, Any]],
        evaluator_func: Callable[[dict[str, Any]], dict[str, Any]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Process flagship evaluation in parallel with dynamic scaling"""
        return await self.process_batch_parallel(
            JobType.FLAGSHIP_EVALUATOR,
            claims,
            evaluator_func,
            progress_callback=progress_callback,
        )

    async def process_transcription_batch(
        self,
        audio_files: list[Path],
        transcription_func: Callable[[Path], str],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[str]:
        """Process transcription in parallel with dynamic scaling"""
        return await self.process_batch_parallel(
            JobType.TRANSCRIPTION,
            audio_files,
            transcription_func,
            progress_callback=progress_callback,
        )

    async def process_voice_fingerprinting_batch(
        self,
        audio_segments: list[dict[str, Any]],
        fingerprint_func: Callable[[dict[str, Any]], dict[str, Any]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Process voice fingerprinting in parallel with dynamic scaling"""
        return await self.process_batch_parallel(
            JobType.VOICE_FINGERPRINTING,
            audio_segments,
            fingerprint_func,
            progress_callback=progress_callback,
        )

    def get_resource_status(self) -> dict[str, Any]:
        """Get current resource utilization and worker status"""
        return self.manager.get_resource_status()

    def save_performance_data(self, filepath: Path):
        """Save performance data for analysis"""
        self.manager.save_performance_data(filepath)

    def shutdown(self):
        """Shutdown all executors and monitoring"""
        for executor in self.executors.values():
            executor.shutdown(wait=True)

        self.manager.stop_monitoring()
        logger.info("Parallel processor shutdown complete")


# Global processor instance
_global_processor: ParallelProcessor | None = None


def get_parallel_processor() -> ParallelProcessor | None:
    """Get the global parallel processor instance"""
    return _global_processor


def initialize_parallel_processor(hardware_specs: dict[str, Any]) -> ParallelProcessor:
    """Initialize the global parallel processor"""
    global _global_processor
    _global_processor = ParallelProcessor(hardware_specs)
    return _global_processor


def shutdown_parallel_processor():
    """Shutdown the global parallel processor"""
    global _global_processor
    if _global_processor:
        _global_processor.shutdown()
        _global_processor = None


# Convenience functions for common operations
async def process_mining_parallel(
    chunks: list[str],
    miner_func: Callable[[str], dict[str, Any]],
    hardware_specs: dict[str, Any],
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Process mining chunks in parallel with automatic resource management"""
    processor = get_parallel_processor() or initialize_parallel_processor(
        hardware_specs
    )
    return await processor.process_miner_batch(chunks, miner_func, progress_callback)


async def process_evaluation_parallel(
    claims: list[dict[str, Any]],
    evaluator_func: Callable[[dict[str, Any]], dict[str, Any]],
    hardware_specs: dict[str, Any],
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Process flagship evaluation in parallel with automatic resource management"""
    processor = get_parallel_processor() or initialize_parallel_processor(
        hardware_specs
    )
    return await processor.process_evaluator_batch(
        claims, evaluator_func, progress_callback
    )
