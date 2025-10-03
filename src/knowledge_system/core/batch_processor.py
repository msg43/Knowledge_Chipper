#!/usr/bin/env python3
"""
Intelligent Batch Processing System

Handles large-scale operations like "5000 episode Download + mine + flagship summarize"
with intelligent resume capabilities and dynamic parallelization.

Features:
- Smart resume from interruptions
- Dynamic parallelization integration
- Progress persistence and recovery
- Component caching integration
- Resource-aware processing
"""

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .dynamic_parallelization import (
    DynamicParallelizationManager,
    JobType,
    get_parallelization_manager,
    initialize_parallelization_manager,
)
from .parallel_processor import get_parallel_processor, initialize_parallel_processor

logger = logging.getLogger(__name__)


class BatchJobStatus(Enum):
    """Status of batch processing jobs"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchJob:
    """Individual job within a batch"""

    job_id: str
    episode_url: str
    status: BatchJobStatus = BatchJobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Processing results
    download_path: str | None = None
    transcript_path: str | None = None
    mining_results: dict[str, Any] | None = None
    evaluation_results: dict[str, Any] | None = None


@dataclass
class BatchProcess:
    """Complete batch processing operation"""

    batch_id: str
    name: str
    total_jobs: int
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    status: BatchJobStatus = BatchJobStatus.PENDING

    # Progress tracking
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_cancelled: int = 0

    # Configuration
    max_parallel_downloads: int = 4
    max_parallel_mining: int = 8
    max_parallel_evaluation: int = 6
    resume_enabled: bool = True

    # Results
    results_summary: dict[str, Any] = field(default_factory=dict)


class IntelligentBatchProcessor:
    """
    Intelligent batch processor that handles large-scale operations
    with resume capabilities and dynamic parallelization.
    """

    def __init__(self, hardware_specs: dict[str, Any], db_path: Path | None = None):
        self.hardware_specs = hardware_specs
        self.db_path = (
            db_path or Path.home() / ".skip_the_podcast" / "batch_processing.db"
        )

        # Initialize systems
        self.manager = initialize_parallelization_manager(hardware_specs)
        self.processor = initialize_parallel_processor(hardware_specs)

        # Database setup
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Active batch tracking
        self.active_batch: BatchProcess | None = None
        self.progress_callback: Callable | None = None

        logger.info(
            f"Intelligent batch processor initialized for {hardware_specs.get('chip_type', 'Unknown')}"
        )

    def _init_database(self):
        """Initialize SQLite database for batch processing tracking"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_processes (
                    batch_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    total_jobs INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    status TEXT NOT NULL,
                    jobs_completed INTEGER DEFAULT 0,
                    jobs_failed INTEGER DEFAULT 0,
                    jobs_cancelled INTEGER DEFAULT 0,
                    max_parallel_downloads INTEGER DEFAULT 4,
                    max_parallel_mining INTEGER DEFAULT 8,
                    max_parallel_evaluation INTEGER DEFAULT 6,
                    resume_enabled BOOLEAN DEFAULT 1,
                    results_summary TEXT,
                    metadata TEXT
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_jobs (
                    job_id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    episode_url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    error_message TEXT,
                    download_path TEXT,
                    transcript_path TEXT,
                    mining_results TEXT,
                    evaluation_results TEXT,
                    metadata TEXT,
                    FOREIGN KEY (batch_id) REFERENCES batch_processes (batch_id)
                )
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_batch_jobs_batch_id ON batch_jobs (batch_id);
                CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs (status);
                CREATE INDEX IF NOT EXISTS idx_batch_processes_status ON batch_processes (status);
            """
            )

    async def start_batch_process(
        self,
        name: str,
        episode_urls: list[str],
        download_func: Callable[[str], str],
        mining_func: Callable[[str], dict[str, Any]],
        evaluation_func: Callable[[dict[str, Any]], dict[str, Any]],
        progress_callback: None
        | (Callable[[str, int, int, dict[str, Any]], None]) = None,
    ) -> str:
        """
        Start a new batch processing operation.

        Args:
            name: Human-readable name for the batch
            episode_urls: List of episode URLs to process
            download_func: Function to download episodes
            mining_func: Function to mine claims from transcripts
            evaluation_func: Function to evaluate claims
            progress_callback: Optional progress callback

        Returns:
            Batch ID for tracking
        """
        batch_id = self._generate_batch_id(name, episode_urls)

        # Check for existing batch (resume capability)
        existing_batch = self._load_batch_process(batch_id)
        if existing_batch and existing_batch.resume_enabled:
            logger.info(f"Resuming existing batch: {batch_id}")
            return await self._resume_batch_process(
                existing_batch,
                download_func,
                mining_func,
                evaluation_func,
                progress_callback,
            )

        # Create new batch
        batch = BatchProcess(
            batch_id=batch_id,
            name=name,
            total_jobs=len(episode_urls),
            max_parallel_downloads=self._calculate_optimal_downloads(),
            max_parallel_mining=self._calculate_optimal_mining(),
            max_parallel_evaluation=self._calculate_optimal_evaluation(),
        )

        # Save batch to database
        self._save_batch_process(batch)

        # Create individual jobs
        jobs = []
        for i, url in enumerate(episode_urls):
            job_id = f"{batch_id}_job_{i:04d}"
            job = BatchJob(
                job_id=job_id,
                episode_url=url,
                metadata={
                    "index": i,
                    "url_hash": hashlib.md5(url.encode()).hexdigest(),
                },
            )
            jobs.append(job)
            self._save_batch_job(job)

        logger.info(f"Created batch process: {name} with {len(jobs)} jobs")

        # Start processing
        return await self._execute_batch_process(
            batch, jobs, download_func, mining_func, evaluation_func, progress_callback
        )

    async def _execute_batch_process(
        self,
        batch: BatchProcess,
        jobs: list[BatchJob],
        download_func: Callable[[str], str],
        mining_func: Callable[[str], dict[str, Any]],
        evaluation_func: Callable[[dict[str, Any]], dict[str, Any]],
        progress_callback: Callable | None = None,
    ) -> str:
        """Execute the batch processing with intelligent parallelization"""

        self.active_batch = batch
        self.progress_callback = progress_callback

        try:
            # Update batch status
            batch.status = BatchJobStatus.IN_PROGRESS
            batch.started_at = time.time()
            self._save_batch_process(batch)

            # Phase 1: Download episodes
            await self._download_phase(jobs, download_func)

            # Phase 2: Mining (parallel with dynamic scaling)
            await self._mining_phase(jobs, mining_func)

            # Phase 3: Evaluation (parallel with dynamic scaling)
            await self._evaluation_phase(jobs, evaluation_func)

            # Complete batch
            batch.status = BatchJobStatus.COMPLETED
            batch.completed_at = time.time()
            batch.results_summary = self._generate_results_summary(jobs)
            self._save_batch_process(batch)

            logger.info(
                f"Batch process completed: {batch.name} ({batch.jobs_completed}/{batch.total_jobs} successful)"
            )
            return batch.batch_id

        except Exception as e:
            batch.status = BatchJobStatus.FAILED
            batch.completed_at = time.time()
            self._save_batch_process(batch)
            logger.error(f"Batch process failed: {batch.name} - {e}")
            raise

        finally:
            self.active_batch = None
            self.progress_callback = None

    async def _download_phase(
        self, jobs: list[BatchJob], download_func: Callable[[str], str]
    ):
        """Download phase with parallel processing"""
        pending_jobs = [job for job in jobs if job.status == BatchJobStatus.PENDING]

        logger.info(f"Starting download phase: {len(pending_jobs)} episodes")

        # Use semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(self.active_batch.max_parallel_downloads)

        async def download_single(job: BatchJob):
            async with semaphore:
                try:
                    job.status = BatchJobStatus.IN_PROGRESS
                    job.started_at = time.time()
                    self._save_batch_job(job)

                    # Download episode
                    download_path = await asyncio.get_event_loop().run_in_executor(
                        None, download_func, job.episode_url
                    )

                    job.download_path = download_path
                    job.status = BatchJobStatus.COMPLETED
                    job.completed_at = time.time()
                    self._save_batch_job(job)

                    self.active_batch.jobs_completed += 1
                    self._save_batch_process(self.active_batch)

                    if self.progress_callback:
                        self.progress_callback(
                            f"Downloaded episode {job.metadata.get('index', 0) + 1}",
                            self.active_batch.jobs_completed,
                            self.active_batch.total_jobs,
                            {"phase": "download", "job_id": job.job_id},
                        )

                except Exception as e:
                    job.status = BatchJobStatus.FAILED
                    job.error_message = str(e)
                    job.completed_at = time.time()
                    self._save_batch_job(job)

                    self.active_batch.jobs_failed += 1
                    self._save_batch_process(self.active_batch)

                    logger.error(f"Download failed for {job.episode_url}: {e}")

        # Execute downloads in parallel
        await asyncio.gather(
            *[download_single(job) for job in pending_jobs], return_exceptions=True
        )

    async def _mining_phase(
        self, jobs: list[BatchJob], mining_func: Callable[[str], dict[str, Any]]
    ):
        """Mining phase with dynamic parallelization"""
        completed_jobs = [
            job
            for job in jobs
            if job.status == BatchJobStatus.COMPLETED and job.download_path
        ]

        if not completed_jobs:
            logger.warning("No completed downloads for mining phase")
            return

        logger.info(f"Starting mining phase: {len(completed_jobs)} episodes")

        # Use dynamic parallelization for mining
        mining_tasks = []
        for job in completed_jobs:
            if not job.mining_results:  # Skip if already mined
                task = self.processor.process_miner_batch(
                    [job.download_path],
                    mining_func,
                    lambda completed, total: self._update_progress(
                        job, "mining", completed, total
                    ),
                )
                mining_tasks.append((job, task))

        # Execute mining with dynamic worker scaling
        for job, task in mining_tasks:
            try:
                results = await task
                if results and len(results) > 0:
                    job.mining_results = results[0]
                    job.status = BatchJobStatus.COMPLETED  # Update if needed
                    self._save_batch_job(job)
                else:
                    raise Exception("No mining results returned")

            except Exception as e:
                job.status = BatchJobStatus.FAILED
                job.error_message = f"Mining failed: {e}"
                self._save_batch_job(job)
                logger.error(f"Mining failed for {job.job_id}: {e}")

    async def _evaluation_phase(
        self,
        jobs: list[BatchJob],
        evaluation_func: Callable[[dict[str, Any]], dict[str, Any]],
    ):
        """Evaluation phase with dynamic parallelization"""
        mined_jobs = [
            job for job in jobs if job.mining_results and not job.evaluation_results
        ]

        if not mined_jobs:
            logger.warning("No mined results for evaluation phase")
            return

        logger.info(f"Starting evaluation phase: {len(mined_jobs)} episodes")

        # Collect all claims from mined jobs
        all_claims = []
        job_claim_mapping = {}

        for job in mined_jobs:
            if job.mining_results and "claims" in job.mining_results:
                claims = job.mining_results["claims"]
                all_claims.extend(claims)
                job_claim_mapping[job.job_id] = claims

        if not all_claims:
            logger.warning("No claims found for evaluation")
            return

        # Use dynamic parallelization for evaluation
        try:
            evaluation_results = await self.processor.process_evaluator_batch(
                all_claims,
                evaluation_func,
                lambda completed, total: self._update_evaluation_progress(
                    completed, total, len(all_claims)
                ),
            )

            # Distribute results back to jobs
            self._distribute_evaluation_results(
                jobs, evaluation_results, job_claim_mapping
            )

        except Exception as e:
            logger.error(f"Evaluation phase failed: {e}")
            # Mark jobs as failed
            for job in mined_jobs:
                job.status = BatchJobStatus.FAILED
                job.error_message = f"Evaluation failed: {e}"
                self._save_batch_job(job)

    def _calculate_optimal_downloads(self) -> int:
        """Calculate optimal number of parallel downloads"""
        # I/O bound, limited by bandwidth and disk I/O
        return min(4, max(1, self.hardware_specs.get("cpu_cores", 8) // 2))

    def _calculate_optimal_mining(self) -> int:
        """Calculate optimal number of parallel mining workers"""
        # Get from dynamic parallelization manager
        return self.manager.get_optimal_workers(JobType.MINER, 0)

    def _calculate_optimal_evaluation(self) -> int:
        """Calculate optimal number of parallel evaluation workers"""
        # Get from dynamic parallelization manager
        return self.manager.get_optimal_workers(JobType.FLAGSHIP_EVALUATOR, 0)

    def _generate_batch_id(self, name: str, urls: list[str]) -> str:
        """Generate unique batch ID based on name and URLs"""
        url_hash = hashlib.md5("".join(sorted(urls)).encode()).hexdigest()[:8]
        name_hash = hashlib.md5(name.encode()).hexdigest()[:8]
        timestamp = int(time.time())
        return f"batch_{name_hash}_{url_hash}_{timestamp}"

    def _load_batch_process(self, batch_id: str) -> BatchProcess | None:
        """Load batch process from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM batch_processes WHERE batch_id = ?", (batch_id,)
            )
            row = cursor.fetchone()

            if row:
                return BatchProcess(
                    batch_id=row["batch_id"],
                    name=row["name"],
                    total_jobs=row["total_jobs"],
                    created_at=row["created_at"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    status=BatchJobStatus(row["status"]),
                    jobs_completed=row["jobs_completed"],
                    jobs_failed=row["jobs_failed"],
                    jobs_cancelled=row["jobs_cancelled"],
                    max_parallel_downloads=row["max_parallel_downloads"],
                    max_parallel_mining=row["max_parallel_mining"],
                    max_parallel_evaluation=row["max_parallel_evaluation"],
                    resume_enabled=bool(row["resume_enabled"]),
                    results_summary=json.loads(row["results_summary"])
                    if row["results_summary"]
                    else {},
                )
        return None

    def _save_batch_process(self, batch: BatchProcess):
        """Save batch process to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO batch_processes
                (batch_id, name, total_jobs, created_at, started_at, completed_at, status,
                 jobs_completed, jobs_failed, jobs_cancelled, max_parallel_downloads,
                 max_parallel_mining, max_parallel_evaluation, resume_enabled, results_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    batch.batch_id,
                    batch.name,
                    batch.total_jobs,
                    batch.created_at,
                    batch.started_at,
                    batch.completed_at,
                    batch.status.value,
                    batch.jobs_completed,
                    batch.jobs_failed,
                    batch.jobs_cancelled,
                    batch.max_parallel_downloads,
                    batch.max_parallel_mining,
                    batch.max_parallel_evaluation,
                    batch.resume_enabled,
                    json.dumps(batch.results_summary),
                ),
            )

    def _save_batch_job(self, job: BatchJob):
        """Save batch job to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO batch_jobs
                (job_id, batch_id, episode_url, status, created_at, started_at, completed_at,
                 error_message, download_path, transcript_path, mining_results, evaluation_results, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    job.job_id,
                    self.active_batch.batch_id,
                    job.episode_url,
                    job.status.value,
                    job.created_at,
                    job.started_at,
                    job.completed_at,
                    job.error_message,
                    job.download_path,
                    job.transcript_path,
                    json.dumps(job.mining_results) if job.mining_results else None,
                    json.dumps(job.evaluation_results)
                    if job.evaluation_results
                    else None,
                    json.dumps(job.metadata),
                ),
            )

    def _update_progress(self, job: BatchJob, phase: str, completed: int, total: int):
        """Update progress for individual job"""
        if self.progress_callback:
            self.progress_callback(
                f"{phase.title()} episode {job.metadata.get('index', 0) + 1} ({completed}/{total})",
                self.active_batch.jobs_completed,
                self.active_batch.total_jobs,
                {
                    "phase": phase,
                    "job_id": job.job_id,
                    "progress": f"{completed}/{total}",
                },
            )

    def _update_evaluation_progress(
        self, completed: int, total: int, total_claims: int
    ):
        """Update progress for evaluation phase"""
        if self.progress_callback:
            self.progress_callback(
                f"Evaluating claims ({completed}/{total})",
                self.active_batch.jobs_completed,
                self.active_batch.total_jobs,
                {
                    "phase": "evaluation",
                    "progress": f"{completed}/{total}",
                    "total_claims": total_claims,
                },
            )

    def _generate_results_summary(self, jobs: list[BatchJob]) -> dict[str, Any]:
        """Generate summary of batch processing results"""
        completed_jobs = [job for job in jobs if job.status == BatchJobStatus.COMPLETED]
        failed_jobs = [job for job in jobs if job.status == BatchJobStatus.FAILED]

        total_claims = 0
        total_evaluations = 0

        for job in completed_jobs:
            if job.mining_results and "claims" in job.mining_results:
                total_claims += len(job.mining_results["claims"])
            if job.evaluation_results:
                total_evaluations += 1

        return {
            "total_episodes": len(jobs),
            "completed_episodes": len(completed_jobs),
            "failed_episodes": len(failed_jobs),
            "success_rate": len(completed_jobs) / len(jobs) if jobs else 0,
            "total_claims_extracted": total_claims,
            "total_evaluations_completed": total_evaluations,
            "processing_time_seconds": (
                self.active_batch.completed_at - self.active_batch.started_at
            )
            if self.active_batch.completed_at
            else 0,
            "parallelization_efficiency": self.manager.get_resource_status().get(
                "parallelization_efficiency", 0
            ),
        }

    async def _resume_batch_process(
        self,
        batch: BatchProcess,
        download_func: Callable[[str], str],
        mining_func: Callable[[str], dict[str, Any]],
        evaluation_func: Callable[[dict[str, Any]], dict[str, Any]],
        progress_callback: Callable | None = None,
    ) -> str:
        """Resume an interrupted batch process"""
        # Load all jobs for this batch
        jobs = self._load_batch_jobs(batch.batch_id)

        logger.info(
            f"Resuming batch: {batch.name} - {batch.jobs_completed}/{batch.total_jobs} completed"
        )

        # Continue from where we left off
        return await self._execute_batch_process(
            batch, jobs, download_func, mining_func, evaluation_func, progress_callback
        )

    def _load_batch_jobs(self, batch_id: str) -> list[BatchJob]:
        """Load all jobs for a batch"""
        jobs = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM batch_jobs WHERE batch_id = ? ORDER BY created_at",
                (batch_id,),
            )

            for row in cursor.fetchall():
                job = BatchJob(
                    job_id=row["job_id"],
                    episode_url=row["episode_url"],
                    status=BatchJobStatus(row["status"]),
                    created_at=row["created_at"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    error_message=row["error_message"],
                    download_path=row["download_path"],
                    transcript_path=row["transcript_path"],
                    mining_results=json.loads(row["mining_results"])
                    if row["mining_results"]
                    else None,
                    evaluation_results=json.loads(row["evaluation_results"])
                    if row["evaluation_results"]
                    else None,
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )
                jobs.append(job)

        return jobs

    def get_batch_status(self, batch_id: str) -> dict[str, Any] | None:
        """Get current status of a batch process"""
        batch = self._load_batch_process(batch_id)
        if not batch:
            return None

        jobs = self._load_batch_jobs(batch_id)

        return {
            "batch_id": batch_id,
            "name": batch.name,
            "status": batch.status.value,
            "progress": {
                "total": batch.total_jobs,
                "completed": batch.jobs_completed,
                "failed": batch.jobs_failed,
                "cancelled": batch.jobs_cancelled,
                "percentage": (batch.jobs_completed / batch.total_jobs) * 100
                if batch.total_jobs > 0
                else 0,
            },
            "timing": {
                "created_at": batch.created_at,
                "started_at": batch.started_at,
                "completed_at": batch.completed_at,
                "duration_seconds": (batch.completed_at - batch.started_at)
                if batch.completed_at and batch.started_at
                else None,
            },
            "parallelization": {
                "max_downloads": batch.max_parallel_downloads,
                "max_mining": batch.max_parallel_mining,
                "max_evaluation": batch.max_parallel_evaluation,
            },
            "results": batch.results_summary,
        }

    def list_batches(
        self, status_filter: BatchJobStatus | None = None
    ) -> list[dict[str, Any]]:
        """List all batch processes, optionally filtered by status"""
        batches = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM batch_processes"
            params = []

            if status_filter:
                query += " WHERE status = ?"
                params.append(status_filter.value)

            query += " ORDER BY created_at DESC"

            cursor = conn.execute(query, params)

            for row in cursor.fetchall():
                batch_info = {
                    "batch_id": row["batch_id"],
                    "name": row["name"],
                    "status": row["status"],
                    "total_jobs": row["total_jobs"],
                    "jobs_completed": row["jobs_completed"],
                    "jobs_failed": row["jobs_failed"],
                    "created_at": row["created_at"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "success_rate": (row["jobs_completed"] / row["total_jobs"]) * 100
                    if row["total_jobs"] > 0
                    else 0,
                }
                batches.append(batch_info)

        return batches


# Convenience function for GUI integration
async def start_episode_batch_process(
    name: str,
    episode_urls: list[str],
    hardware_specs: dict[str, Any],
    download_func: Callable[[str], str],
    mining_func: Callable[[str], dict[str, Any]],
    evaluation_func: Callable[[dict[str, Any]], dict[str, Any]],
    progress_callback: Callable[[str, int, int, dict[str, Any]], None] | None = None,
    db_path: Path | None = None,
) -> str:
    """
    Start a batch process for episode download, mining, and evaluation.

    This is the main function that the GUI should call for large-scale processing.
    """
    processor = IntelligentBatchProcessor(hardware_specs, db_path)
    return await processor.start_batch_process(
        name,
        episode_urls,
        download_func,
        mining_func,
        evaluation_func,
        progress_callback,
    )
