"""
Processing Service

Wraps existing Knowledge_Chipper processors for FastAPI daemon.
Phase 1: Only YouTubeDownloadProcessor
Phase 2: Will add AudioProcessor, TwoPassPipeline, and GetReceiptsUploader
"""

import asyncio
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from daemon.models.schemas import ProcessRequest, JobStatus

logger = logging.getLogger(__name__)


class ProcessingService:
    """
    High-level service that orchestrates processing jobs.
    
    Phase 1: Download only (YouTubeDownloadProcessor)
    Phase 2: Will add transcription, extraction, and upload
    """

    def __init__(self):
        self.jobs: dict[str, JobStatus] = {}
        self._start_time = datetime.now(timezone.utc)

    async def start_job(self, request: ProcessRequest) -> str:
        """
        Start a new processing job.
        Returns job_id for tracking.
        """
        job_id = str(uuid.uuid4())

        # Determine stages based on request options
        stages = []
        if request.source_type == "youtube":
            stages.append("download")
        if request.transcribe:
            stages.append("transcribe")
        if request.extract_claims:
            stages.append("extract")
        if request.auto_upload:
            stages.append("upload")

        # Create initial job status
        status = JobStatus(
            job_id=job_id,
            status="queued",
            progress=0.0,
            current_stage="Initializing",
            stages_complete=[],
            stages_remaining=stages.copy(),
            started_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.jobs[job_id] = status

        # Start processing in background
        asyncio.create_task(self._process_job(job_id, request))

        return job_id

    async def _process_job(self, job_id: str, request: ProcessRequest):
        """
        Background task that actually processes the job.
        Phase 1: Only download stage implemented.
        """
        try:
            # Stage 1: Download (Phase 1 - fully implemented)
            if request.source_type == "youtube":
                await self._update_job(job_id, "downloading", 0.1, "Downloading from YouTube")

                # Import and use YouTubeDownloadProcessor
                from src.knowledge_system.processors.youtube_download import (
                    YouTubeDownloadProcessor,
                )
                from src.knowledge_system.config import get_settings

                settings = get_settings()
                output_dir = Path(settings.output_directory) / "downloads" / "youtube"
                output_dir.mkdir(parents=True, exist_ok=True)

                downloader = YouTubeDownloadProcessor()
                result = await asyncio.to_thread(
                    downloader.process,
                    request.url,
                    output_dir=str(output_dir),
                )

                if not result.success:
                    raise Exception(f"Download failed: {', '.join(result.errors)}")

                # Extract info from result
                source_id = result.metadata.get("video_id", "unknown")
                title = result.metadata.get("title", "Unknown")

                await self._update_job(
                    job_id,
                    "downloading",
                    0.3,
                    "Download complete",
                    source_id=source_id,
                    title=title,
                )

                # Mark download stage complete
                job = self.jobs[job_id]
                if "download" in job.stages_remaining:
                    job.stages_remaining.remove("download")
                    job.stages_complete.append("download")

            # Phase 2 stages (TODO: Not implemented yet)
            if request.transcribe:
                await self._update_job(job_id, "transcribing", 0.4, "Transcription (Phase 2 - not implemented)")
                # TODO: Phase 2 - Add AudioProcessor integration
                job = self.jobs[job_id]
                if "transcribe" in job.stages_remaining:
                    job.stages_remaining.remove("transcribe")
                    job.stages_complete.append("transcribe")

            if request.extract_claims:
                await self._update_job(job_id, "extracting", 0.6, "Extraction (Phase 2 - not implemented)")
                # TODO: Phase 2 - Add TwoPassPipeline integration
                job = self.jobs[job_id]
                if "extract" in job.stages_remaining:
                    job.stages_remaining.remove("extract")
                    job.stages_complete.append("extract")

            if request.auto_upload:
                await self._update_job(job_id, "uploading", 0.9, "Upload (Phase 2 - not implemented)")
                # TODO: Phase 2 - Add GetReceiptsUploader integration
                job = self.jobs[job_id]
                if "upload" in job.stages_remaining:
                    job.stages_remaining.remove("upload")
                    job.stages_complete.append("upload")

            # Complete
            await self._update_job(
                job_id,
                "complete",
                1.0,
                "Processing complete",
            )

        except Exception as e:
            logger.exception(f"Job {job_id} failed")
            await self._update_job(
                job_id,
                "failed",
                self.jobs[job_id].progress,
                f"Failed: {str(e)}",
                error=str(e),
            )

    async def _update_job(
        self,
        job_id: str,
        status: str,
        progress: float,
        current_stage: str,
        **kwargs,
    ):
        """Update job status."""
        job = self.jobs[job_id]
        job.status = status
        job.progress = progress
        job.current_stage = current_stage
        job.updated_at = datetime.now(timezone.utc)

        # Update optional fields
        for key, value in kwargs.items():
            if hasattr(job, key) and value is not None:
                setattr(job, key, value)

        if status == "complete":
            job.completed_at = datetime.now(timezone.utc)

        logger.info(f"Job {job_id}: {status} - {current_stage} ({progress * 100:.0f}%)")

    def get_job(self, job_id: str) -> Optional[JobStatus]:
        """Get job status by ID."""
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[JobStatus]:
        """List all jobs."""
        return list(self.jobs.values())

    def get_active_job_count(self) -> int:
        """Get count of active (non-terminal) jobs."""
        return len(
            [j for j in self.jobs.values() if j.status not in ["complete", "failed"]]
        )

    def get_uptime_seconds(self) -> float:
        """Get daemon uptime in seconds."""
        return (datetime.now(timezone.utc) - self._start_time).total_seconds()


# Global service instance
processing_service = ProcessingService()

