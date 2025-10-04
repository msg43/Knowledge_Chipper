#!/usr/bin/env python3
"""
Dynamic Parallelization System for Knowledge Processing

Intelligently manages parallel workers based on:
- Available RAM and CPU resources
- Job completion times and queue lengths
- Real-time resource utilization
- Hardware-specific optimization

Key Features:
- FP16 model optimization for high-end systems
- Dynamic worker scaling based on resource usage
- Job completion-based worker adjustment
- Memory-aware parallelization
"""

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


class JobType(Enum):
    """Types of processing jobs"""

    DOWNLOAD = "download"  # Audio file downloads (YouTube, etc.)
    MINER = "miner"  # Stage-A: Claim extraction and mining
    FLAGSHIP_EVALUATOR = "flagship_evaluator"  # Stage-B: Claim evaluation and ranking
    TRANSCRIPTION = "transcription"  # Audio transcription
    VOICE_FINGERPRINTING = "voice_fingerprinting"  # Voice analysis


@dataclass
class ResourceLimits:
    """Resource limits for parallelization with sophisticated constraints"""

    max_ram_gb: float
    max_cpu_cores: int
    model_ram_gb: float  # RAM used by the loaded model

    # KV Cache Budget Management (Critical for M2 Ultra)
    kv_cache_2k_ctx_gb: float = 0.4  # Qwen2.5-14B-instruct: 2k ctx ≈ 0.3-0.5GB
    kv_cache_4k_ctx_gb: float = 0.9  # Qwen2.5-14B-instruct: 4k ctx ≈ 0.8-1.0GB
    kv_cache_8k_ctx_gb: float = 1.8  # Qwen2.5-14B-instruct: 8k ctx ≈ 1.6-2.0GB

    # Dynamic Thread Management (Based on actual hardware capacity)
    max_total_inference_threads: int = 0  # Calculated dynamically
    max_threads_per_worker: int = 0  # Calculated dynamically
    os_reserve_cores: int = 4  # Reserve cores for OS and other apps

    # Context Limits (Prevent KV cache explosion)
    stage_a_max_ctx: int = 4000  # Stage-A: 2-4k ctx
    stage_b_max_ctx: int = 8000  # Stage-B: ~8k ctx

    # System overhead
    system_overhead_gb: float = 2.0


@dataclass
class JobMetrics:
    """Metrics for job performance tracking"""

    job_type: JobType
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration: float | None = None
    memory_used_mb: float = 0.0
    cpu_percent: float = 0.0
    success: bool = True
    error: str | None = None


@dataclass
class WorkerPool:
    """Worker pool configuration with sophisticated constraints"""

    job_type: JobType
    current_workers: int = 1
    min_workers: int = 1
    max_workers: int = 8
    active_jobs: int = 0
    completed_jobs: int = 0
    avg_duration: float = 0.0
    last_adjustment: float = field(default_factory=time.time)
    adjustment_cooldown: float = 30.0  # Seconds between adjustments

    # Thread and Context Management
    threads_per_worker: int = 4  # Default threads per worker
    context_length: int = 2000  # Default context length
    kv_cache_gb_per_worker: float = 0.4  # Estimated KV cache per worker

    # Performance Tracking
    p95_latency: float = 0.0  # 95th percentile latency
    p99_latency: float = 0.0  # 99th percentile latency
    token_throughput: float = 0.0  # Tokens per second
    validation_failures: int = 0  # JSON validation failures


class DynamicParallelizationManager:
    """
    Intelligent parallelization manager that dynamically adjusts worker counts
    based on resource usage, job completion times, and hardware capabilities.
    """

    def __init__(self, hardware_specs: dict[str, Any]):
        self.hardware_specs = hardware_specs
        self.resource_limits = self._calculate_resource_limits()
        self.worker_pools: dict[JobType, WorkerPool] = {}
        self.job_metrics: list[JobMetrics] = []
        self.monitoring_active = False
        self.monitor_thread: threading.Thread | None = None

        # Initialize worker pools
        self._initialize_worker_pools()

        # Performance tracking
        self.performance_history: dict[JobType, list[float]] = {
            job_type: [] for job_type in JobType
        }

        logger.info(
            f"Dynamic parallelization initialized for {hardware_specs.get('chip_type', 'Unknown')} "
            f"with {self.resource_limits.max_ram_gb}GB RAM, {self.resource_limits.max_cpu_cores} cores"
        )

    def _calculate_resource_limits(self) -> ResourceLimits:
        """Calculate resource limits based on hardware specs with sophisticated constraints"""
        memory_gb = self.hardware_specs.get("memory_gb", 16)
        cpu_cores = self.hardware_specs.get("cpu_cores", 8)
        chip_type = self.hardware_specs.get("chip_type", "").lower()

        # Model RAM usage (FP16 optimization for high-end systems)
        if memory_gb >= 64 and ("ultra" in chip_type or "max" in chip_type):
            model_ram_gb = 32.0  # Qwen2.5-14B-instruct FP16
            os_reserve_cores = 6  # More aggressive on high-end systems
        elif memory_gb >= 32 and ("max" in chip_type or "pro" in chip_type):
            model_ram_gb = 32.0  # Qwen2.5-14B-instruct FP16
            os_reserve_cores = 5
        elif memory_gb >= 16:
            model_ram_gb = 8.0  # Qwen2.5-7b-instruct
            os_reserve_cores = 4
        else:
            model_ram_gb = 4.0  # Qwen2.5-3b-instruct
            os_reserve_cores = 3

        # Calculate dynamic thread limits based on actual hardware
        available_cores = max(1, cpu_cores - os_reserve_cores)
        max_total_threads = self._calculate_optimal_thread_limits(
            available_cores, memory_gb, chip_type
        )

        return ResourceLimits(
            max_ram_gb=memory_gb,
            max_cpu_cores=cpu_cores,
            model_ram_gb=model_ram_gb,
            # KV Cache Budget (Qwen2.5-14B-instruct specific)
            kv_cache_2k_ctx_gb=0.4,  # 2k ctx ≈ 0.3-0.5GB
            kv_cache_4k_ctx_gb=0.9,  # 4k ctx ≈ 0.8-1.0GB
            kv_cache_8k_ctx_gb=1.8,  # 8k ctx ≈ 1.6-2.0GB
            # Dynamic Thread Management
            max_total_inference_threads=int(max_total_threads),
            max_threads_per_worker=self._calculate_max_threads_per_worker(
                available_cores, chip_type
            ),
            os_reserve_cores=os_reserve_cores,
            # Context Limits (Prevent KV cache explosion)
            stage_a_max_ctx=4000,  # Stage-A: 2-4k ctx
            stage_b_max_ctx=8000,  # Stage-B: ~8k ctx
            system_overhead_gb=2.0,
        )

    def _calculate_optimal_thread_limits(
        self, available_cores: int, memory_gb: float, chip_type: str
    ) -> int:
        """Calculate optimal total inference threads based on hardware capacity"""

        # Base thread calculation: available cores * threads per core
        # Modern CPUs have 2 threads per core (hyperthreading/SMT)
        base_threads = available_cores * 2

        # Adjust based on chip architecture and memory bandwidth
        if "ultra" in chip_type:
            # M2/M3 Ultra: High memory bandwidth, can handle more threads
            thread_multiplier = 1.8  # Up to 1.8x threads vs cores
        elif "max" in chip_type:
            # M2/M3 Max: Good balance of cores and memory bandwidth
            thread_multiplier = 1.6
        elif "pro" in chip_type:
            # M2/M3 Pro: Moderate memory bandwidth
            thread_multiplier = 1.4
        else:
            # Base chips: Conservative threading
            thread_multiplier = 1.2

        # Memory bandwidth consideration
        if memory_gb >= 64:
            # High memory systems can sustain more concurrent threads
            memory_multiplier = 1.2
        elif memory_gb >= 32:
            memory_multiplier = 1.1
        elif memory_gb >= 16:
            memory_multiplier = 1.0
        else:
            # Low memory systems: be conservative
            memory_multiplier = 0.9

        # Calculate final thread limit
        optimal_threads = int(base_threads * thread_multiplier * memory_multiplier)

        # Reasonable bounds to prevent extreme values
        min_threads = max(4, available_cores)  # At least 4 threads or 1 per core
        max_threads = available_cores * 3  # Never more than 3x cores

        return max(min_threads, min(optimal_threads, max_threads))

    def _calculate_max_threads_per_worker(
        self, available_cores: int, chip_type: str
    ) -> int:
        """Calculate max threads per worker based on hardware capacity"""

        # Base calculation: threads per worker should scale with available cores
        if available_cores >= 20:  # Ultra systems
            base_threads_per_worker = 6
        elif available_cores >= 12:  # Max systems
            base_threads_per_worker = 5
        elif available_cores >= 8:  # Pro systems
            base_threads_per_worker = 4
        elif available_cores >= 4:  # Base systems
            base_threads_per_worker = 3
        else:
            base_threads_per_worker = 2

        # Adjust based on chip architecture
        if "ultra" in chip_type:
            # Ultra chips have excellent thread scheduling
            return min(base_threads_per_worker + 1, 7)
        elif "max" in chip_type:
            return min(base_threads_per_worker + 1, 6)
        else:
            return min(base_threads_per_worker, 5)

    def _initialize_worker_pools(self):
        """Initialize worker pools for each job type with dynamic limits"""
        # Calculate dynamic max workers based on available hardware
        available_cores = (
            self.resource_limits.max_cpu_cores - self.resource_limits.os_reserve_cores
        )
        base_max_workers = min(
            8, available_cores
        )  # Conservative start, will scale up dynamically

        self.worker_pools = {
            JobType.DOWNLOAD: WorkerPool(
                job_type=JobType.DOWNLOAD,
                max_workers=min(
                    12, available_cores * 2
                ),  # I/O bound, can handle many concurrent downloads
                min_workers=1,
                threads_per_worker=min(
                    2, self.resource_limits.max_threads_per_worker
                ),  # I/O bound, fewer threads
                context_length=1000,  # Minimal context for downloads
                kv_cache_gb_per_worker=0.1,  # Minimal memory usage for downloads
            ),
            JobType.MINER: WorkerPool(
                job_type=JobType.MINER,
                max_workers=base_max_workers * 2,  # CPU-intensive, can parallelize more
                min_workers=1,
                threads_per_worker=self.resource_limits.max_threads_per_worker,
                context_length=self.resource_limits.stage_a_max_ctx,
                kv_cache_gb_per_worker=self.resource_limits.kv_cache_4k_ctx_gb,
            ),
            JobType.FLAGSHIP_EVALUATOR: WorkerPool(
                job_type=JobType.FLAGSHIP_EVALUATOR,
                max_workers=min(
                    2, base_max_workers
                ),  # Limited parallelization for Stage-B
                min_workers=1,
                threads_per_worker=self.resource_limits.max_threads_per_worker,
                context_length=self.resource_limits.stage_b_max_ctx,
                kv_cache_gb_per_worker=self.resource_limits.kv_cache_8k_ctx_gb,
            ),
            JobType.TRANSCRIPTION: WorkerPool(
                job_type=JobType.TRANSCRIPTION,
                max_workers=base_max_workers // 2,  # I/O bound, fewer workers
                min_workers=1,
                threads_per_worker=min(
                    2, self.resource_limits.max_threads_per_worker
                ),  # I/O bound, fewer threads
                context_length=self.resource_limits.stage_a_max_ctx,
                kv_cache_gb_per_worker=self.resource_limits.kv_cache_2k_ctx_gb,
            ),
            JobType.VOICE_FINGERPRINTING: WorkerPool(
                job_type=JobType.VOICE_FINGERPRINTING,
                max_workers=base_max_workers,  # CPU-intensive, good parallelization
                min_workers=1,
                threads_per_worker=self.resource_limits.max_threads_per_worker,
                context_length=self.resource_limits.stage_a_max_ctx,
                kv_cache_gb_per_worker=self.resource_limits.kv_cache_2k_ctx_gb,
            ),
        }

        logger.info(
            f"Initialized worker pools: {[(pool.job_type.value, pool.max_workers) for pool in self.worker_pools.values()]}"
        )

    def get_optimal_queue_distribution(
        self, total_queue_size: int
    ) -> dict[JobType, int]:
        """
        Intelligently distribute queue across job types to minimize overall processing time.

        This ensures downloads keep the processing pipeline fed while maintaining
        optimal resource utilization across all stages.
        """
        # Get current system state
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)

        # Calculate optimal distribution based on current resource availability
        distribution = {}

        # Downloads: Keep queue fed but don't overwhelm
        download_queue = min(
            total_queue_size * 0.4,  # Max 40% of queue for downloads
            self.worker_pools[JobType.DOWNLOAD].max_workers
            * 3,  # 3x workers for queue depth
        )
        distribution[JobType.DOWNLOAD] = int(download_queue)

        # Mining: Process downloaded content efficiently
        miner_queue = min(
            total_queue_size * 0.35,  # 35% for mining
            self.worker_pools[JobType.MINER].max_workers
            * 2,  # 2x workers for queue depth
        )
        distribution[JobType.MINER] = int(miner_queue)

        # Flagship Evaluation: Limited but high priority
        flagship_queue = min(
            total_queue_size * 0.15,  # 15% for flagship evaluation
            self.worker_pools[
                JobType.FLAGSHIP_EVALUATOR
            ].max_workers,  # 1x workers (bottleneck)
        )
        distribution[JobType.FLAGSHIP_EVALUATOR] = int(flagship_queue)

        # Other processing: Remaining capacity
        remaining_capacity = total_queue_size - sum(distribution.values())
        distribution[JobType.TRANSCRIPTION] = int(remaining_capacity * 0.6)
        distribution[JobType.VOICE_FINGERPRINTING] = int(remaining_capacity * 0.4)

        # Adjust based on resource pressure
        if memory.percent > 80 or cpu_percent > 85:
            # High pressure: reduce all queues
            for job_type in distribution:
                distribution[job_type] = max(1, int(distribution[job_type] * 0.7))
        elif memory.percent < 60 and cpu_percent < 70:
            # Low pressure: can handle more
            for job_type in distribution:
                distribution[job_type] = int(distribution[job_type] * 1.2)

        logger.info(f"Optimal queue distribution: {distribution}")
        return distribution

    def get_optimal_workers(self, job_type: JobType, queue_length: int = 0) -> int:
        """
        Calculate optimal number of workers based on:
        - Current resource utilization
        - Job queue length
        - Historical performance
        - Hardware capabilities
        """
        pool = self.worker_pools[job_type]
        current_time = time.time()

        # Don't adjust too frequently
        if current_time - pool.last_adjustment < pool.adjustment_cooldown:
            return pool.current_workers

        # Get current resource usage
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Calculate optimal workers based on resources
        optimal_workers = self._calculate_optimal_workers(
            job_type, cpu_percent, memory_percent, queue_length
        )

        # Clamp to pool limits
        optimal_workers = max(pool.min_workers, min(optimal_workers, pool.max_workers))

        # Only adjust if significant change
        if abs(optimal_workers - pool.current_workers) >= 1:
            old_workers = pool.current_workers
            pool.current_workers = optimal_workers
            pool.last_adjustment = current_time

            logger.info(
                f"Adjusted {job_type.value} workers: {old_workers} -> {optimal_workers} "
                f"(CPU: {cpu_percent:.1f}%, RAM: {memory_percent:.1f}%, Queue: {queue_length})"
            )

        return pool.current_workers

    def _calculate_optimal_workers(
        self,
        job_type: JobType,
        cpu_percent: float,
        memory_percent: float,
        queue_length: int,
    ) -> int:
        """Calculate optimal workers based on current conditions"""
        pool = self.worker_pools[job_type]

        # Base calculation on resource availability
        if cpu_percent < 50 and memory_percent < 70:
            # Resources available, can increase workers
            if queue_length > pool.current_workers * 2:
                # High queue, increase workers
                return min(pool.current_workers + 2, pool.max_workers)
            elif queue_length > pool.current_workers:
                # Moderate queue, slight increase
                return min(pool.current_workers + 1, pool.max_workers)
            else:
                # Low queue, maintain current
                return pool.current_workers

        elif cpu_percent > 80 or memory_percent > 85:
            # Resource pressure, decrease workers
            return max(pool.current_workers - 1, pool.min_workers)

        else:
            # Balanced resources, maintain current
            return pool.current_workers

    def start_job(self, job_type: JobType) -> JobMetrics:
        """Start tracking a new job"""
        metrics = JobMetrics(job_type=job_type)
        self.job_metrics.append(metrics)
        self.worker_pools[job_type].active_jobs += 1
        return metrics

    def complete_job(
        self, metrics: JobMetrics, success: bool = True, error: str | None = None
    ):
        """Complete job tracking and update performance metrics"""
        metrics.end_time = time.time()
        metrics.duration = metrics.end_time - metrics.start_time
        metrics.success = success
        metrics.error = error

        pool = self.worker_pools[metrics.job_type]
        pool.active_jobs = max(0, pool.active_jobs - 1)
        pool.completed_jobs += 1

        # Update average duration
        if metrics.success and metrics.duration:
            self.performance_history[metrics.job_type].append(metrics.duration)
            # Keep only last 10 measurements
            if len(self.performance_history[metrics.job_type]) > 10:
                self.performance_history[metrics.job_type].pop(0)

            # Update pool average
            pool.avg_duration = sum(self.performance_history[metrics.job_type]) / len(
                self.performance_history[metrics.job_type]
            )

        logger.debug(
            f"Completed {metrics.job_type.value} job in {metrics.duration:.2f}s "
            f"(Active: {pool.active_jobs}, Completed: {pool.completed_jobs})"
        )

    def get_resource_status(self) -> dict[str, Any]:
        """Get current resource utilization status"""
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / (1024**3),
            "worker_pools": {
                job_type.value: {
                    "current_workers": pool.current_workers,
                    "active_jobs": pool.active_jobs,
                    "completed_jobs": pool.completed_jobs,
                    "avg_duration": pool.avg_duration,
                }
                for job_type, pool in self.worker_pools.items()
            },
            "resource_limits": {
                "max_ram_gb": self.resource_limits.max_ram_gb,
                "max_cpu_cores": self.resource_limits.max_cpu_cores,
                "model_ram_gb": self.resource_limits.model_ram_gb,
            },
        }

    def start_monitoring(self):
        """Start background resource monitoring"""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_resources, daemon=True
        )
        self.monitor_thread.start()
        logger.info("Started dynamic parallelization monitoring")

    def stop_monitoring(self):
        """Stop background resource monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Stopped dynamic parallelization monitoring")

    def _monitor_resources(self):
        """Background monitoring thread"""
        while self.monitoring_active:
            try:
                # Get current resource usage
                memory = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=5)

                # Log resource status every minute
                if len(self.job_metrics) % 12 == 0:  # Every 12 iterations (1 minute)
                    logger.info(
                        f"Resource status - CPU: {cpu_percent:.1f}%, "
                        f"RAM: {memory.percent:.1f}% ({memory.available/(1024**3):.1f}GB available)"
                    )

                # Check for resource pressure and adjust if needed
                if cpu_percent > 90 or memory.percent > 90:
                    logger.warning(
                        f"High resource usage detected - CPU: {cpu_percent:.1f}%, RAM: {memory.percent:.1f}%"
                    )

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                time.sleep(10)

    def save_performance_data(self, filepath: Path):
        """Save performance data for analysis"""
        data = {
            "hardware_specs": self.hardware_specs,
            "resource_limits": {
                "max_ram_gb": self.resource_limits.max_ram_gb,
                "max_cpu_cores": self.resource_limits.max_cpu_cores,
                "model_ram_gb": self.resource_limits.model_ram_gb,
            },
            "worker_pools": {
                job_type.value: {
                    "current_workers": pool.current_workers,
                    "max_workers": pool.max_workers,
                    "completed_jobs": pool.completed_jobs,
                    "avg_duration": pool.avg_duration,
                }
                for job_type, pool in self.worker_pools.items()
            },
            "performance_history": {
                job_type.value: durations
                for job_type, durations in self.performance_history.items()
            },
            "job_metrics": [
                {
                    "job_type": metrics.job_type.value,
                    "duration": metrics.duration,
                    "success": metrics.success,
                    "error": metrics.error,
                }
                for metrics in self.job_metrics[-100:]  # Last 100 jobs
            ],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved performance data to {filepath}")

    def _calculate_optimal_workers_with_constraints(
        self,
        job_type: JobType,
        cpu_percent: float,
        memory_percent: float,
        queue_length: int,
    ) -> int:
        """Calculate optimal workers with sophisticated M2 Ultra constraints"""
        pool = self.worker_pools[job_type]

        # 1. KV Cache Budget Constraint (Critical for M2 Ultra)
        kv_cache_budget = self._calculate_kv_cache_budget(job_type)
        max_workers_by_kv = kv_cache_budget // pool.kv_cache_gb_per_worker

        # 2. Dynamic Thread Contention Constraint (Based on actual hardware capacity)
        total_threads_used = self._calculate_total_threads_used()
        available_threads = (
            self.resource_limits.max_total_inference_threads - total_threads_used
        )
        max_workers_by_threads = available_threads // pool.threads_per_worker

        # Additional constraint: ensure we don't exceed hardware capacity
        max_workers_by_hardware = (
            self.resource_limits.max_cpu_cores - self.resource_limits.os_reserve_cores
        )

        # 3. Memory Pressure Constraint (macOS unified memory)
        memory_pressure_factor = self._calculate_memory_pressure_factor(memory_percent)

        # 4. Performance Constraint (Latency and throughput)
        performance_factor = self._calculate_performance_factor(pool)

        # 5. Error Rate Constraint (Backoff on validation failures)
        error_factor = self._calculate_error_factor(pool)

        # Calculate base workers from queue length and CPU
        if cpu_percent < 50 and memory_percent < 70:
            if queue_length > pool.current_workers * 2:
                base_workers = min(pool.current_workers + 2, pool.max_workers)
            elif queue_length > pool.current_workers:
                base_workers = min(pool.current_workers + 1, pool.max_workers)
            else:
                base_workers = pool.current_workers
        elif cpu_percent > 80 or memory_percent > 85:
            base_workers = max(pool.current_workers - 1, pool.min_workers)
        else:
            base_workers = pool.current_workers

        # Apply all constraints including hardware capacity
        optimal_workers = min(
            base_workers,
            max_workers_by_kv,
            max_workers_by_threads,
            max_workers_by_hardware,
            int(
                pool.max_workers
                * memory_pressure_factor
                * performance_factor
                * error_factor
            ),
        )

        return max(pool.min_workers, int(optimal_workers))

    def _calculate_kv_cache_budget(self, job_type: JobType) -> float:
        """Calculate available KV cache budget"""
        # Available RAM minus model and system overhead
        available_ram = (
            self.resource_limits.max_ram_gb
            - self.resource_limits.model_ram_gb
            - self.resource_limits.system_overhead_gb
        )

        # Reserve some RAM for other processes
        kv_cache_budget = available_ram * 0.8  # 80% of available RAM for KV cache

        # Adjust based on job type and context length
        if job_type == JobType.DOWNLOAD:
            # Downloads: minimal memory usage
            kv_per_worker = 0.1  # 100MB per download worker
        elif job_type == JobType.MINER:
            # Stage-A: 2-4k ctx
            kv_per_worker = self.resource_limits.kv_cache_4k_ctx_gb
        elif job_type == JobType.FLAGSHIP_EVALUATOR:
            # Stage-B: 8k ctx
            kv_per_worker = self.resource_limits.kv_cache_8k_ctx_gb
        else:
            kv_per_worker = self.resource_limits.kv_cache_2k_ctx_gb

        return kv_cache_budget / kv_per_worker

    def _calculate_total_threads_used(self) -> int:
        """Calculate total threads currently used across all workers"""
        total_threads = 0
        for pool in self.worker_pools.values():
            total_threads += pool.current_workers * pool.threads_per_worker
        return total_threads

    def _calculate_memory_pressure_factor(self, memory_percent: float) -> float:
        """Calculate memory pressure factor for macOS unified memory"""
        if memory_percent < 60:
            return 1.0  # No pressure
        elif memory_percent < 70:
            return 0.9  # Light pressure
        elif memory_percent < 80:
            return 0.7  # Moderate pressure
        elif memory_percent < 90:
            return 0.5  # High pressure
        else:
            return 0.3  # Critical pressure

    def _calculate_performance_factor(self, pool: WorkerPool) -> float:
        """Calculate performance factor based on latency and throughput"""
        factor = 1.0

        # Back off if p95 latency is too high
        if pool.p95_latency > 5.0:  # 5 seconds
            factor *= 0.8
        elif pool.p95_latency > 3.0:  # 3 seconds
            factor *= 0.9

        # Back off if p99 latency is too high
        if pool.p99_latency > 10.0:  # 10 seconds
            factor *= 0.7
        elif pool.p99_latency > 7.0:  # 7 seconds
            factor *= 0.8

        # Back off if token throughput is dropping
        if pool.token_throughput < 100:  # Less than 100 tokens/sec
            factor *= 0.8

        return factor

    def _calculate_error_factor(self, pool: WorkerPool) -> float:
        """Calculate error factor based on validation failures"""
        if pool.validation_failures > 10:  # High error rate
            return 0.5
        elif pool.validation_failures > 5:  # Moderate error rate
            return 0.7
        elif pool.validation_failures > 2:  # Low error rate
            return 0.9
        else:
            return 1.0  # No significant errors


# Convenience function for getting the manager instance
_global_manager: DynamicParallelizationManager | None = None


def get_parallelization_manager() -> DynamicParallelizationManager | None:
    """Get the global parallelization manager instance"""
    return _global_manager


def initialize_parallelization_manager(
    hardware_specs: dict[str, Any]
) -> DynamicParallelizationManager:
    """Initialize the global parallelization manager"""
    global _global_manager
    _global_manager = DynamicParallelizationManager(hardware_specs)
    _global_manager.start_monitoring()
    return _global_manager


def shutdown_parallelization_manager():
    """Shutdown the global parallelization manager"""
    global _global_manager
    if _global_manager:
        _global_manager.stop_monitoring()
        _global_manager = None


# Enhanced constraint checking methods for M2 Ultra optimization
# Methods are now properly defined within the DynamicParallelizationManager class
