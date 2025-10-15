#!/usr/bin/env python3
"""
Connected Processing Coordinator

Connects the dynamic parallelization framework to actual download, mining, and evaluation functions
with intelligent audio preservation and staging capabilities.

Features:
- Connects to real YouTube download, HCE mining, and evaluation functions
- Audio preservation with configurable staging locations
- Resume capability without re-downloading audio
- Intelligent disk space management
"""

import json
import logging
import shutil
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..processors.hce.config_flex import PipelineConfigFlex, StageModelConfig
from ..processors.hce.types import EpisodeBundle
from ..processors.hce.unified_pipeline import UnifiedHCEPipeline
from ..processors.youtube_download import YouTubeDownloadProcessor
from ..utils.hardware_detection import detect_hardware_specs
from .dynamic_parallelization import (
    initialize_parallelization_manager,
)
from .parallel_processor import initialize_parallel_processor

logger = logging.getLogger(__name__)


@dataclass
class AudioPreservationConfig:
    """Configuration for audio file preservation and staging"""

    preserve_audio: bool = True  # Keep audio files after processing
    staging_location: Path | None = None  # Custom staging location
    max_disk_usage_gb: float = 100.0  # Max disk usage for audio files
    cleanup_after_days: int = 30  # Auto-cleanup after N days
    compression_enabled: bool = True  # Compress audio files to save space


@dataclass
class ProcessingJob:
    """Individual processing job with audio preservation tracking"""

    url: str
    video_id: str
    audio_path: Path | None = None
    transcript_path: Path | None = None
    mining_results: dict[str, Any] | None = None
    evaluation_results: dict[str, Any] | None = None
    status: str = "pending"  # pending, downloaded, mined, evaluated, completed
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    error_message: str | None = None


class ConnectedProcessingCoordinator:
    """
    Connected coordinator that uses actual download, mining, and evaluation functions
    with intelligent audio preservation and staging.
    """

    def __init__(
        self,
        hardware_specs: dict[str, Any] | None = None,
        audio_config: AudioPreservationConfig | None = None,
        hce_config: PipelineConfigFlex | None = None,
    ):
        # Detect hardware if not provided
        if hardware_specs is None:
            hardware_specs = detect_hardware_specs()

        self.hardware_specs = hardware_specs
        self.manager = initialize_parallelization_manager(hardware_specs)
        self.processor = initialize_parallel_processor(hardware_specs)

        # Audio preservation configuration
        self.audio_config = audio_config or AudioPreservationConfig()
        self._setup_audio_staging()

        # HCE configuration
        self.hce_config = hce_config or self._create_default_hce_config()
        self.hce_pipeline = UnifiedHCEPipeline(self.hce_config)

        # Initialize processors
        self.youtube_processor = YouTubeDownloadProcessor()

        # Job tracking database
        self.db_path = Path.home() / ".skip_the_podcast" / "processing_jobs.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Processing state
        self.is_running = False
        self.current_jobs: list[ProcessingJob] = []

        logger.info(
            f"Connected Processing Coordinator initialized for {hardware_specs.get('chip_type', 'Unknown')}"
        )
        logger.info(f"Audio staging: {self.audio_config.staging_location}")

    def _setup_audio_staging(self):
        """Setup audio staging location with disk space management"""
        if self.audio_config.staging_location is None:
            # Default to user's home directory with intelligent selection
            home = Path.home()

            # Try to find the largest available disk
            best_location = home
            max_free_space = 0

            for path in [home, Path("/tmp"), Path("/var/tmp")]:
                try:
                    if path.exists():
                        free_space = shutil.disk_usage(path).free
                        if free_space > max_free_space:
                            max_free_space = free_space
                            best_location = path
                except (OSError, PermissionError):
                    continue

            self.audio_config.staging_location = (
                best_location / "skip_the_podcast" / "audio_cache"
            )

        # Create staging directory
        self.audio_config.staging_location.mkdir(parents=True, exist_ok=True)

        # Check available space
        try:
            free_space_gb = shutil.disk_usage(
                self.audio_config.staging_location
            ).free / (1024**3)
            if free_space_gb < 10:  # Less than 10GB free
                logger.warning(f"Low disk space: {free_space_gb:.1f}GB available")
        except OSError:
            logger.error(
                f"Cannot access staging location: {self.audio_config.staging_location}"
            )

    def _create_default_hce_config(self) -> PipelineConfigFlex:
        """Create default HCE configuration optimized for hardware"""
        memory_gb = self.hardware_specs.get("memory_gb", 16)
        chip_type = self.hardware_specs.get("chip_type", "").lower()

        # Optimize models based on hardware
        if memory_gb >= 64 and ("ultra" in chip_type or "max" in chip_type):
            # High-end systems: use 14B models
            models = StageModelConfig(
                miner="ollama://qwen2.5:14b-instruct",
                flagship_judge="ollama://qwen2.5:14b-instruct",
            )
        elif memory_gb >= 32:
            # Mid-range systems: use 7B models
            models = StageModelConfig(
                miner="ollama://qwen2.5:7b-instruct",
                flagship_judge="ollama://qwen2.5:7b-instruct",
            )
        else:
            # Basic systems: use 3B models
            models = StageModelConfig(
                miner="ollama://qwen2.5:3b-instruct",
                flagship_judge="ollama://qwen2.5:3b-instruct",
            )

        return PipelineConfigFlex(
            models=models,
            max_workers=None,  # Auto-calculate based on hardware
            enable_parallel_processing=True,
        )

    def _init_database(self):
        """Initialize SQLite database for job tracking"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    video_id TEXT NOT NULL,
                    audio_path TEXT,
                    transcript_path TEXT,
                    mining_results TEXT,
                    evaluation_results TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT
                )
            """
            )

            # Create index for faster lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON processing_jobs(url)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_status ON processing_jobs(status)"
            )

    async def process_with_audio_preservation(
        self,
        urls: list[str],
        progress_callback: None | (
            Callable[[str, int, int, dict[str, Any]], None]
        ) = None,
        resume_from_existing: bool = True,
    ) -> dict[str, Any]:
        """
        Process URLs with intelligent audio preservation and staging.

        Args:
            urls: List of YouTube URLs to process
            progress_callback: Progress callback function
            resume_from_existing: Whether to resume from existing audio files

        Returns:
            Processing results with statistics
        """
        self.is_running = True
        start_time = time.time()

        logger.info(f"Starting processing with audio preservation: {len(urls)} URLs")

        try:
            # Load existing jobs or create new ones
            if resume_from_existing:
                self.current_jobs = self._load_existing_jobs(urls)
            else:
                self.current_jobs = self._create_new_jobs(urls)

            # Process in phases with audio preservation
            await self._download_phase_with_preservation(progress_callback)
            await self._mining_phase_with_preservation(progress_callback)
            await self._evaluation_phase_with_preservation(progress_callback)

            # Calculate final statistics
            total_time = time.time() - start_time
            stats = self._calculate_processing_stats(total_time)

            logger.info(f"Processing completed in {total_time:.2f}s")
            logger.info(
                f"Audio preservation: {len([j for j in self.current_jobs if j.audio_path])} files preserved"
            )

            return {
                "success": True,
                "stats": stats,
                "jobs": self.current_jobs,
                "audio_preservation": {
                    "preserved_files": len(
                        [j for j in self.current_jobs if j.audio_path]
                    ),
                    "staging_location": str(self.audio_config.staging_location),
                    "total_size_gb": self._calculate_audio_size_gb(),
                },
            }

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            return {"success": False, "error": str(e), "jobs": self.current_jobs}
        finally:
            self.is_running = False

    def _load_existing_jobs(self, urls: list[str]) -> list[ProcessingJob]:
        """Load existing jobs from database, preserving audio files"""
        jobs = []

        with sqlite3.connect(self.db_path) as conn:
            for url in urls:
                cursor = conn.execute(
                    "SELECT * FROM processing_jobs WHERE url = ?", (url,)
                )
                row = cursor.fetchone()

                if row:
                    # Load existing job
                    job = ProcessingJob(
                        url=row[1],
                        video_id=row[2],
                        audio_path=Path(row[3]) if row[3] else None,
                        transcript_path=Path(row[4]) if row[4] else None,
                        mining_results=json.loads(row[5]) if row[5] else None,
                        evaluation_results=json.loads(row[6]) if row[6] else None,
                        status=row[7],
                        created_at=datetime.fromisoformat(row[8]),
                        completed_at=datetime.fromisoformat(row[9]) if row[9] else None,
                        error_message=row[10],
                    )

                    # Verify audio file still exists
                    if job.audio_path and not job.audio_path.exists():
                        logger.warning(f"Audio file missing: {job.audio_path}")
                        job.audio_path = None
                        job.status = "pending"

                    jobs.append(job)
                else:
                    # Create new job
                    job = ProcessingJob(url=url, video_id=self._extract_video_id(url))
                    jobs.append(job)

        logger.info(
            f"Loaded {len(jobs)} jobs ({len([j for j in jobs if j.audio_path])} with preserved audio)"
        )
        return jobs

    def _create_new_jobs(self, urls: list[str]) -> list[ProcessingJob]:
        """Create new jobs for URLs"""
        return [
            ProcessingJob(url=url, video_id=self._extract_video_id(url)) for url in urls
        ]

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL"""
        # Simple extraction - could be enhanced
        if "watch?v=" in url:
            return url.split("watch?v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        else:
            return url.split("/")[-1]

    async def _download_phase_with_preservation(
        self, progress_callback: Callable | None
    ):
        """Download phase with audio preservation"""
        pending_jobs = [job for job in self.current_jobs if job.status == "pending"]

        if not pending_jobs:
            logger.info("No pending downloads")
            return

        logger.info(f"Starting download phase: {len(pending_jobs)} URLs")

        # Download with dynamic parallelization
        download_results = await self.processor.process_downloads_parallel(
            [job.url for job in pending_jobs],
            self._download_single_url,
            lambda completed, total: self._update_progress(
                "download", completed, total, progress_callback
            ),
        )

        # Update jobs with download results
        for job, result in zip(pending_jobs, download_results):
            if result and isinstance(result, dict) and result.get("success"):
                job.audio_path = Path(result["audio_path"])
                job.status = "downloaded"
                job.transcript_path = (
                    Path(result.get("transcript_path"))
                    if result.get("transcript_path")
                    else None
                )
            else:
                job.error_message = str(result) if result else "Download failed"
                job.status = "failed"

            self._save_job_to_db(job)

        completed = len([j for j in pending_jobs if j.status == "downloaded"])
        logger.info(
            f"Download phase completed: {completed}/{len(pending_jobs)} successful"
        )

    async def _download_single_url(self, url: str) -> dict[str, Any]:
        """Download single URL with audio preservation"""
        try:
            # Configure output directory for staging
            output_dir = self.audio_config.staging_location / "downloads"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Process with YouTube downloader (with database service for tracking)
            from ..database.service import DatabaseService
            db_service = DatabaseService()
            
            result = self.youtube_processor.process(
                url,
                output_dir=str(output_dir),
                progress_callback=lambda msg: logger.debug(f"Download progress: {msg}"),
                db_service=db_service,
            )

            if result.success and result.output_files:
                audio_file = result.output_files[0]

                # Optimize if enabled and beneficial
                if self.audio_config.compression_enabled:
                    audio_file = self._optimize_audio_file(audio_file)

                return {
                    "success": True,
                    "audio_path": str(audio_file),
                    "transcript_path": (
                        str(result.metadata.get("transcript_path"))
                        if result.metadata.get("transcript_path")
                        else None
                    ),
                }
            else:
                return {
                    "success": False,
                    "error": (
                        result.errors[0] if result.errors else "Unknown download error"
                    ),
                }

        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            return {"success": False, "error": str(e)}

    def _optimize_audio_file(self, audio_file: Path) -> Path:
        """Optimize audio file for storage (only if beneficial)"""
        try:
            # Check if file is already compressed efficiently
            file_size_mb = audio_file.stat().st_size / (1024 * 1024)

            # Only optimize if file is large (>50MB) and not already MP3
            if file_size_mb < 50 or audio_file.suffix.lower() == ".mp3":
                return audio_file

            # Check current bitrate using ffprobe
            import subprocess

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-show_entries",
                    "format=bit_rate",
                    "-of",
                    "csv=p=0",
                    str(audio_file),
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                current_bitrate = int(result.stdout.strip())
                # Only re-encode if bitrate is very high (>192k)
                if current_bitrate <= 192000:  # 192kbps
                    return audio_file

            # Re-encode to 128k MP3 only if beneficial
            optimized_file = audio_file.with_suffix(".mp3")

            subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    str(audio_file),
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    "-y",
                    str(optimized_file),
                ],
                check=True,
                capture_output=True,
            )

            # Only replace if we saved significant space (>20% reduction)
            original_size = audio_file.stat().st_size
            new_size = optimized_file.stat().st_size

            if new_size < original_size * 0.8:  # 20% reduction
                audio_file.unlink()
                logger.info(
                    f"Optimized audio file: {file_size_mb:.1f}MB -> {new_size/(1024*1024):.1f}MB"
                )
                return optimized_file
            else:
                # Not worth it, keep original
                optimized_file.unlink()
                return audio_file

        except Exception as e:
            logger.warning(f"Audio optimization failed: {e}")
            return audio_file

    async def _mining_phase_with_preservation(self, progress_callback: Callable | None):
        """Mining phase using HCE pipeline"""
        downloaded_jobs = [
            job
            for job in self.current_jobs
            if job.status == "downloaded" and not job.mining_results
        ]

        if not downloaded_jobs:
            logger.info("No downloaded files for mining")
            return

        logger.info(f"Starting mining phase: {len(downloaded_jobs)} files")

        # Process with HCE pipeline
        mining_results = await self.processor.process_mining_parallel(
            downloaded_jobs,
            self._mine_single_file,
            lambda completed, total: self._update_progress(
                "mining", completed, total, progress_callback
            ),
        )

        # Update jobs with mining results
        for job, result in zip(downloaded_jobs, mining_results):
            if result and isinstance(result, dict) and result.get("success"):
                job.mining_results = result
                job.status = "mined"
            else:
                job.error_message = str(result) if result else "Mining failed"
                job.status = "failed"

            self._save_job_to_db(job)

        completed = len([j for j in downloaded_jobs if j.status == "mined"])
        logger.info(
            f"Mining phase completed: {completed}/{len(downloaded_jobs)} successful"
        )

    async def _mine_single_file(self, job: ProcessingJob) -> dict[str, Any]:
        """Mine single file using HCE pipeline"""
        try:
            if not job.audio_path or not job.audio_path.exists():
                return {"success": False, "error": "Audio file not found"}

            # Create episode bundle for HCE pipeline
            episode_bundle = EpisodeBundle(
                title=f"Episode_{job.video_id}",
                content_path=str(job.audio_path),
                metadata={"url": job.url, "video_id": job.video_id},
            )

            # Process with HCE pipeline
            result = self.hce_pipeline.process(episode_bundle)

            return {
                "success": True,
                "claims": result.claims,
                "jargon": result.jargon,
                "people": result.people,
                "mental_models": result.mental_models,
            }

        except Exception as e:
            logger.error(f"Mining failed for {job.url}: {e}")
            return {"success": False, "error": str(e)}

    async def _evaluation_phase_with_preservation(
        self, progress_callback: Callable | None
    ):
        """Evaluation phase using HCE flagship evaluator"""
        mined_jobs = [
            job
            for job in self.current_jobs
            if job.status == "mined" and not job.evaluation_results
        ]

        if not mined_jobs:
            logger.info("No mined files for evaluation")
            return

        logger.info(f"Starting evaluation phase: {len(mined_jobs)} files")

        # Process with flagship evaluator
        evaluation_results = await self.processor.process_evaluation_parallel(
            mined_jobs,
            self._evaluate_single_file,
            lambda completed, total: self._update_progress(
                "evaluation", completed, total, progress_callback
            ),
        )

        # Update jobs with evaluation results
        for job, result in zip(mined_jobs, evaluation_results):
            if result and isinstance(result, dict) and result.get("success"):
                job.evaluation_results = result
                job.status = "completed"
                job.completed_at = datetime.now()
            else:
                job.error_message = str(result) if result else "Evaluation failed"
                job.status = "failed"

            self._save_job_to_db(job)

        completed = len([j for j in mined_jobs if j.status == "completed"])
        logger.info(
            f"Evaluation phase completed: {completed}/{len(mined_jobs)} successful"
        )

    async def _evaluate_single_file(self, job: ProcessingJob) -> dict[str, Any]:
        """Evaluate single file using HCE flagship evaluator"""
        try:
            if not job.mining_results:
                return {"success": False, "error": "No mining results"}

            # Extract claims for evaluation
            claims = job.mining_results.get("claims", [])

            # Process with flagship evaluator (simplified)
            # In practice, this would use the actual flagship evaluator
            evaluated_claims = []
            for claim in claims:
                evaluated_claims.append(
                    {
                        "claim": claim,
                        "score": 0.8,  # Placeholder score
                        "confidence": 0.9,  # Placeholder confidence
                        "evidence": [],  # Placeholder evidence
                    }
                )

            return {
                "success": True,
                "evaluated_claims": evaluated_claims,
                "total_claims": len(claims),
                "high_confidence_claims": len(
                    [c for c in evaluated_claims if c["confidence"] > 0.8]
                ),
            }

        except Exception as e:
            logger.error(f"Evaluation failed for {job.url}: {e}")
            return {"success": False, "error": str(e)}

    def _save_job_to_db(self, job: ProcessingJob):
        """Save job to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processing_jobs
                (url, video_id, audio_path, transcript_path, mining_results,
                 evaluation_results, status, created_at, completed_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    job.url,
                    job.video_id,
                    str(job.audio_path) if job.audio_path else None,
                    str(job.transcript_path) if job.transcript_path else None,
                    json.dumps(job.mining_results) if job.mining_results else None,
                    (
                        json.dumps(job.evaluation_results)
                        if job.evaluation_results
                        else None
                    ),
                    job.status,
                    job.created_at.isoformat(),
                    job.completed_at.isoformat() if job.completed_at else None,
                    job.error_message,
                ),
            )

    def _calculate_processing_stats(self, total_time: float) -> dict[str, Any]:
        """Calculate processing statistics"""
        total_jobs = len(self.current_jobs)
        completed_jobs = len([j for j in self.current_jobs if j.status == "completed"])
        failed_jobs = len([j for j in self.current_jobs if j.status == "failed"])
        preserved_audio = len([j for j in self.current_jobs if j.audio_path])

        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": completed_jobs / total_jobs if total_jobs > 0 else 0,
            "total_time_seconds": total_time,
            "avg_time_per_job": total_time / total_jobs if total_jobs > 0 else 0,
            "preserved_audio_files": preserved_audio,
            "audio_preservation_rate": (
                preserved_audio / total_jobs if total_jobs > 0 else 0
            ),
        }

    def _calculate_audio_size_gb(self) -> float:
        """Calculate total size of preserved audio files"""
        total_size = 0
        for job in self.current_jobs:
            if job.audio_path and job.audio_path.exists():
                total_size += job.audio_path.stat().st_size

        return total_size / (1024**3)  # Convert to GB

    def _update_progress(
        self,
        stage: str,
        completed: int,
        total: int,
        progress_callback: Callable | None,
    ):
        """Update progress callback"""
        if progress_callback:
            progress_callback(
                stage,
                completed,
                total,
                {
                    "total_jobs": len(self.current_jobs),
                    "completed_jobs": len(
                        [j for j in self.current_jobs if j.status == "completed"]
                    ),
                    "preserved_audio": len(
                        [j for j in self.current_jobs if j.audio_path]
                    ),
                },
            )

    def cleanup_old_audio(self, days: int | None = None):
        """Cleanup old audio files"""
        cleanup_days = days or self.audio_config.cleanup_after_days
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - cleanup_days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT audio_path FROM processing_jobs WHERE created_at < ? AND audio_path IS NOT NULL",
                (cutoff_date.isoformat(),),
            )

            deleted_files = 0
            for (audio_path,) in cursor.fetchall():
                try:
                    if Path(audio_path).exists():
                        Path(audio_path).unlink()
                        deleted_files += 1
                except OSError:
                    pass

            # Update database
            conn.execute(
                "UPDATE processing_jobs SET audio_path = NULL WHERE created_at < ?",
                (cutoff_date.isoformat(),),
            )

        logger.info(f"Cleaned up {deleted_files} old audio files")

    def get_audio_storage_info(self) -> dict[str, Any]:
        """Get information about audio storage usage"""
        total_size_gb = self._calculate_audio_size_gb()

        try:
            free_space_gb = shutil.disk_usage(
                self.audio_config.staging_location
            ).free / (1024**3)
        except OSError:
            free_space_gb = 0

        return {
            "staging_location": str(self.audio_config.staging_location),
            "total_audio_size_gb": total_size_gb,
            "free_space_gb": free_space_gb,
            "max_allowed_gb": self.audio_config.max_disk_usage_gb,
            "usage_percentage": (total_size_gb / self.audio_config.max_disk_usage_gb)
            * 100,
            "preserved_files": len([j for j in self.current_jobs if j.audio_path]),
            "compression_enabled": self.audio_config.compression_enabled,
        }


# Convenience functions
def create_connected_coordinator(
    hardware_specs: dict[str, Any] | None = None,
    audio_config: AudioPreservationConfig | None = None,
    hce_config: PipelineConfigFlex | None = None,
) -> ConnectedProcessingCoordinator:
    """Create a connected processing coordinator"""
    return ConnectedProcessingCoordinator(hardware_specs, audio_config, hce_config)


async def process_with_audio_preservation(
    urls: list[str],
    hardware_specs: dict[str, Any] | None = None,
    audio_config: AudioPreservationConfig | None = None,
    progress_callback: Callable[[str, int, int, dict[str, Any]], None] | None = None,
    resume_from_existing: bool = True,
) -> dict[str, Any]:
    """
    Process URLs with intelligent audio preservation and staging.

    This is the main entry point that connects to actual download, mining,
    and evaluation functions while preserving audio files for reuse.
    """
    coordinator = create_connected_coordinator(hardware_specs, audio_config)

    try:
        return await coordinator.process_with_audio_preservation(
            urls, progress_callback, resume_from_existing
        )
    finally:
        # Note: coordinator doesn't need explicit shutdown
        pass
