#!/usr/bin/env python3
"""
Intelligent Processing Coordinator

Orchestrates the complete processing pipeline with dynamic resource allocation
to minimize overall processing time while maintaining silky smooth system performance.

Features:
- Dynamic audio file downloads with queue management
- Intelligent Stage-A (mining) and Stage-B (evaluation) parallelization
- Resource-aware worker scaling
- Optimal queue distribution for minimum processing time
- Real-time system monitoring and adjustment
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..utils.hardware_detection import detect_hardware_specs
from .dynamic_parallelization import JobType, initialize_parallelization_manager
from .parallel_processor import initialize_parallel_processor

logger = logging.getLogger(__name__)


@dataclass
class ProcessingPipeline:
    """Configuration for the complete processing pipeline"""

    download_urls: list[str]
    mining_func: Callable[[str], dict[str, Any]]
    evaluation_func: Callable[[dict[str, Any]], dict[str, Any]]
    progress_callback: Callable[[str, int, int, dict[str, Any]], None] | None = None
    max_queue_size: int = 1000
    enable_download_pacing: bool = True


class IntelligentProcessingCoordinator:
    """
    Orchestrates the complete processing pipeline with intelligent resource management.

    This coordinator ensures:
    1. Downloads keep the processing queue optimally fed
    2. Stage-A (mining) and Stage-B (evaluation) run with optimal parallelization
    3. Overall processing time is minimized through intelligent queue management
    4. System remains silky smooth under load
    """

    def __init__(self, hardware_specs: dict[str, Any] | None = None):
        # Detect hardware if not provided
        if hardware_specs is None:
            hardware_specs = detect_hardware_specs()

        self.hardware_specs = hardware_specs
        self.manager = initialize_parallelization_manager(hardware_specs)
        self.processor = initialize_parallel_processor(hardware_specs)

        # Pipeline state
        self.is_running = False
        self.current_pipeline: ProcessingPipeline | None = None

        # Queue management
        self.download_queue: list[str] = []
        self.mining_queue: list[str] = []
        self.evaluation_queue: list[dict[str, Any]] = []

        # Processing stats
        self.stats = {
            "downloads_completed": 0,
            "mining_completed": 0,
            "evaluation_completed": 0,
            "total_processing_time": 0.0,
            "avg_download_time": 0.0,
            "avg_mining_time": 0.0,
            "avg_evaluation_time": 0.0,
            "queue_efficiency": 0.0,
        }

        logger.info(
            f"Intelligent Processing Coordinator initialized for {hardware_specs.get('chip_type', 'Unknown')}"
        )

    async def process_complete_pipeline(
        self, pipeline: ProcessingPipeline
    ) -> dict[str, Any]:
        """
        Process the complete pipeline: downloads → mining → evaluation

        This method orchestrates all stages to minimize overall processing time
        while maintaining optimal resource utilization.
        """
        self.current_pipeline = pipeline
        self.is_running = True
        start_time = time.time()

        logger.info(
            f"Starting complete pipeline processing: {len(pipeline.download_urls)} URLs"
        )

        try:
            # Initialize queues
            self.download_queue = pipeline.download_urls.copy()
            self.mining_queue = []
            self.evaluation_queue = []

            # Start all processing stages concurrently
            tasks = [
                self._download_coordinator(pipeline),
                self._mining_coordinator(pipeline),
                self._evaluation_coordinator(pipeline),
                self._queue_monitor(),
            ]

            # Run all stages concurrently
            await asyncio.gather(*tasks, return_exceptions=True)

            # Calculate final stats
            self.stats["total_processing_time"] = time.time() - start_time
            self.stats["queue_efficiency"] = self._calculate_queue_efficiency()

            logger.info(
                f"Pipeline completed in {self.stats['total_processing_time']:.2f}s"
            )
            logger.info(f"Queue efficiency: {self.stats['queue_efficiency']:.1%}")

            return {
                "success": True,
                "stats": self.stats,
                "results": self.evaluation_queue,
            }

        except Exception as e:
            logger.error(f"Pipeline processing failed: {e}")
            return {"success": False, "error": str(e), "stats": self.stats}
        finally:
            self.is_running = False

    async def _download_coordinator(self, pipeline: ProcessingPipeline):
        """Coordinate downloads to keep processing queue optimally fed"""
        logger.info("Starting download coordinator")

        batch_size = self.manager.get_optimal_workers(JobType.DOWNLOAD)
        completed_downloads = 0

        while self.is_running and (
            self.download_queue or self.mining_queue or self.evaluation_queue
        ):
            # Get optimal download batch size based on current queue state
            current_queue_size = len(self.download_queue)
            if current_queue_size == 0:
                await asyncio.sleep(1)  # Wait for more downloads
                continue

            # Calculate optimal batch size to keep mining queue fed
            mining_queue_size = len(self.mining_queue)
            optimal_download_batch = min(
                batch_size,
                current_queue_size,
                max(
                    1,
                    (self.manager.get_optimal_workers(JobType.MINER) * 2)
                    - mining_queue_size,
                ),
            )

            # Download batch
            download_batch = self.download_queue[:optimal_download_batch]
            self.download_queue = self.download_queue[optimal_download_batch:]

            # Process downloads in parallel
            download_start = time.time()
            downloaded_files = await self.processor.process_downloads_parallel(
                download_batch,
                pipeline.mining_func,  # This would be a download function in practice
                lambda completed, total: self._update_progress(
                    "download", completed, total
                ),
            )
            download_time = time.time() - download_start

            # Add successful downloads to mining queue
            for i, result in enumerate(downloaded_files):
                if result:
                    self.mining_queue.append(download_batch[i])
                    completed_downloads += 1

            # Update stats
            self.stats["downloads_completed"] = completed_downloads
            self.stats["avg_download_time"] = download_time / len(download_batch)

            # Intelligent pacing: pause downloads if queues are backing up
            if pipeline.enable_download_pacing and self._should_pause_downloads():
                await asyncio.sleep(2)  # Brief pause to let processing catch up

        logger.info(f"Download coordinator completed: {completed_downloads} downloads")

    async def _mining_coordinator(self, pipeline: ProcessingPipeline):
        """Coordinate Stage-A mining with dynamic parallelization"""
        logger.info("Starting mining coordinator")

        completed_mining = 0

        while self.is_running and (self.mining_queue or self.evaluation_queue):
            if not self.mining_queue:
                await asyncio.sleep(0.5)  # Wait for downloads
                continue

            # Get optimal mining batch size
            batch_size = self.manager.get_optimal_workers(JobType.MINER)
            mining_batch = self.mining_queue[:batch_size]
            self.mining_queue = self.mining_queue[batch_size:]

            # Process mining in parallel
            mining_start = time.time()
            mining_results = await self.processor.process_mining_parallel(
                mining_batch,
                pipeline.mining_func,
                lambda completed, total: self._update_progress(
                    "mining", completed, total
                ),
            )
            mining_time = time.time() - mining_start

            # Add successful mining results to evaluation queue
            for i, result in enumerate(mining_results):
                if result:
                    self.evaluation_queue.append(result)
                    completed_mining += 1

            # Update stats
            self.stats["mining_completed"] = completed_mining
            self.stats["avg_mining_time"] = mining_time / len(mining_batch)

        logger.info(f"Mining coordinator completed: {completed_mining} items mined")

    async def _evaluation_coordinator(self, pipeline: ProcessingPipeline):
        """Coordinate Stage-B evaluation with dynamic parallelization"""
        logger.info("Starting evaluation coordinator")

        completed_evaluation = 0

        while self.is_running and self.evaluation_queue:
            # Get optimal evaluation batch size (limited for Stage-B)
            batch_size = min(
                self.manager.get_optimal_workers(JobType.FLAGSHIP_EVALUATOR),
                len(self.evaluation_queue),
            )

            if batch_size == 0:
                await asyncio.sleep(0.5)
                continue

            evaluation_batch = self.evaluation_queue[:batch_size]
            self.evaluation_queue = self.evaluation_queue[batch_size:]

            # Process evaluation in parallel
            evaluation_start = time.time()
            evaluation_results = await self.processor.process_evaluation_parallel(
                evaluation_batch,
                pipeline.evaluation_func,
                lambda completed, total: self._update_progress(
                    "evaluation", completed, total
                ),
            )
            evaluation_time = time.time() - evaluation_start

            # Update stats
            completed_evaluation += len([r for r in evaluation_results if r])
            self.stats["evaluation_completed"] = completed_evaluation
            self.stats["avg_evaluation_time"] = evaluation_time / len(evaluation_batch)

        logger.info(
            f"Evaluation coordinator completed: {completed_evaluation} items evaluated"
        )

    async def _queue_monitor(self):
        """Monitor queue states and adjust processing dynamically"""
        while self.is_running:
            try:
                # Get current queue states
                queue_states = {
                    "download_queue": len(self.download_queue),
                    "mining_queue": len(self.mining_queue),
                    "evaluation_queue": len(self.evaluation_queue),
                }

                # Calculate optimal queue distribution
                total_queue = sum(queue_states.values())
                if total_queue > 0:
                    optimal_distribution = self.manager.get_optimal_queue_distribution(
                        total_queue
                    )

                    # Log queue efficiency
                    logger.debug(f"Queue states: {queue_states}")
                    logger.debug(f"Optimal distribution: {optimal_distribution}")

                await asyncio.sleep(5)  # Monitor every 5 seconds

            except Exception as e:
                logger.error(f"Queue monitor error: {e}")
                await asyncio.sleep(10)

    def _should_pause_downloads(self) -> bool:
        """Determine if downloads should be paused to prevent queue overflow"""
        mining_queue_size = len(self.mining_queue)
        evaluation_queue_size = len(self.evaluation_queue)

        # Pause downloads if downstream queues are backing up
        max_mining_queue = self.manager.get_optimal_workers(JobType.MINER) * 3
        max_evaluation_queue = (
            self.manager.get_optimal_workers(JobType.FLAGSHIP_EVALUATOR) * 2
        )

        return (
            mining_queue_size > max_mining_queue
            or evaluation_queue_size > max_evaluation_queue
        )

    def _calculate_queue_efficiency(self) -> float:
        """Calculate overall queue processing efficiency"""
        if not self.stats["downloads_completed"]:
            return 0.0

        # Efficiency based on how well we kept queues fed without overflow
        expected_processing = self.stats["downloads_completed"]
        actual_processing = min(
            self.stats["mining_completed"], self.stats["evaluation_completed"]
        )

        return (
            actual_processing / expected_processing if expected_processing > 0 else 0.0
        )

    def _update_progress(self, stage: str, completed: int, total: int):
        """Update progress for the current pipeline"""
        if self.current_pipeline and self.current_pipeline.progress_callback:
            self.current_pipeline.progress_callback(stage, completed, total, self.stats)

    def get_system_status(self) -> dict[str, Any]:
        """Get current system status and resource utilization"""
        return {
            "is_running": self.is_running,
            "hardware_specs": self.hardware_specs,
            "queue_states": {
                "download_queue": len(self.download_queue),
                "mining_queue": len(self.mining_queue),
                "evaluation_queue": len(self.evaluation_queue),
            },
            "processing_stats": self.stats,
            "resource_limits": {
                "max_total_threads": self.manager.resource_limits.max_total_inference_threads,
                "max_threads_per_worker": self.manager.resource_limits.max_threads_per_worker,
                "model_ram_gb": self.manager.resource_limits.model_ram_gb,
            },
            "worker_pools": {
                job_type.value: {
                    "current_workers": pool.current_workers,
                    "max_workers": pool.max_workers,
                    "completed_jobs": pool.completed_jobs,
                }
                for job_type, pool in self.manager.worker_pools.items()
            },
        }

    def shutdown(self):
        """Shutdown the coordinator and clean up resources"""
        self.is_running = False
        if self.manager:
            self.manager.stop_monitoring()
        logger.info("Intelligent Processing Coordinator shutdown complete")


# Convenience functions
def create_processing_coordinator(
    hardware_specs: dict[str, Any] | None = None,
) -> IntelligentProcessingCoordinator:
    """Create a new intelligent processing coordinator"""
    return IntelligentProcessingCoordinator(hardware_specs)


async def process_with_intelligent_coordination(
    download_urls: list[str],
    mining_func: Callable[[str], dict[str, Any]],
    evaluation_func: Callable[[dict[str, Any]], dict[str, Any]],
    hardware_specs: dict[str, Any] | None = None,
    progress_callback: Callable[[str, int, int, dict[str, Any]], None] | None = None,
    max_queue_size: int = 1000,
) -> dict[str, Any]:
    """
    Process URLs with intelligent coordination for optimal performance.

    This is the main entry point for coordinated processing that ensures
    downloads, mining, and evaluation work together optimally.
    """
    coordinator = create_processing_coordinator(hardware_specs)

    try:
        pipeline = ProcessingPipeline(
            download_urls=download_urls,
            mining_func=mining_func,
            evaluation_func=evaluation_func,
            progress_callback=progress_callback,
            max_queue_size=max_queue_size,
        )

        return await coordinator.process_complete_pipeline(pipeline)
    finally:
        coordinator.shutdown()
