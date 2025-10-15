"""
System 2 Orchestrator

Extends the IntelligentProcessingCoordinator with job tracking, checkpoint persistence,
and auto-process chaining per the System 2 architecture.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..database import DatabaseService
from ..database.system2_models import Job, JobRun, LLMRequest, LLMResponse
from ..errors import ErrorCode, KnowledgeSystemError
from ..utils.id_generation import create_deterministic_id
from .intelligent_processing_coordinator import (
    IntelligentProcessingCoordinator,
    ProcessingPipeline,
)

logger = logging.getLogger(__name__)


class System2Orchestrator:
    """
    Orchestrator that wraps IntelligentProcessingCoordinator with System 2 features:
    - Creates job and job_run records
    - Persists checkpoints for resumability
    - Supports auto_process chaining
    - Tracks all LLM requests/responses
    """

    def __init__(self, db_service: DatabaseService | None = None):
        """Initialize the System 2 orchestrator."""
        self.db_service = db_service or DatabaseService()
        self.coordinator = IntelligentProcessingCoordinator()
        self._current_job_run_id: str | None = None

    def create_job(
        self,
        job_type: str,
        input_id: str,
        config: dict[str, Any],
        auto_process: bool = False,
    ) -> str:
        """
        Create a new job record.

        Args:
            job_type: Type of job ('transcribe', 'mine', 'flagship', 'upload', 'pipeline')
            input_id: ID of the input (video_id or episode_id)
            config: Job configuration
            auto_process: Whether to automatically chain to next stage

        Returns:
            job_id: The created job ID
        """
        # Generate deterministic job ID
        job_id = create_deterministic_id(
            f"{job_type}_{input_id}_{json.dumps(config, sort_keys=True)}"
        )

        with self.db_service.get_session() as session:
            # Check if job already exists
            existing_job = session.query(Job).filter_by(job_id=job_id).first()
            if existing_job:
                logger.info(f"Job {job_id} already exists, reusing")
                return job_id

            # Create new job
            job = Job(
                job_id=job_id,
                job_type=job_type,
                input_id=input_id,
                config_json=config,
                auto_process="true" if auto_process else "false",
            )
            session.add(job)
            session.commit()
            logger.info(f"Created job {job_id} for {job_type} on {input_id}")

        return job_id

    def create_job_run(
        self, job_id: str, checkpoint: dict[str, Any] | None = None
    ) -> str:
        """
        Create a new job run for a job.

        Args:
            job_id: The job to run
            checkpoint: Optional checkpoint to resume from

        Returns:
            run_id: The created job run ID
        """
        run_id = f"{job_id}_run_{uuid.uuid4().hex[:8]}"

        with self.db_service.get_session() as session:
            # Get the job
            job = session.query(Job).filter_by(job_id=job_id).first()
            if not job:
                raise KnowledgeSystemError(
                    f"Job {job_id} not found", ErrorCode.PROCESSING_FAILED
                )

            # Count previous attempts
            attempt_count = session.query(JobRun).filter_by(job_id=job_id).count()

            # Create job run
            job_run = JobRun(
                run_id=run_id,
                job_id=job_id,
                attempt_number=attempt_count + 1,
                status="queued",
                checkpoint_json=checkpoint,
            )
            session.add(job_run)
            session.commit()
            logger.info(f"Created job run {run_id} for job {job_id}")

        self._current_job_run_id = run_id
        return run_id

    def update_job_run_status(
        self,
        run_id: str,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        metrics: dict[str, Any] | None = None,
    ):
        """Update job run status and metrics."""
        with self.db_service.get_session() as session:
            job_run = session.query(JobRun).filter_by(run_id=run_id).first()
            if not job_run:
                logger.warning(f"Job run {run_id} not found")
                return

            job_run.status = status
            job_run.updated_at = datetime.utcnow()

            if status == "running" and not job_run.started_at:
                job_run.started_at = datetime.utcnow()
            elif status in ["succeeded", "failed", "cancelled"]:
                job_run.completed_at = datetime.utcnow()

            if error_code:
                job_run.error_code = error_code
            if error_message:
                job_run.error_message = error_message
            if metrics:
                job_run.metrics_json = metrics

            session.commit()
            logger.info(f"Updated job run {run_id} status to {status}")

    def save_checkpoint(self, run_id: str, checkpoint: dict[str, Any]):
        """Save checkpoint for a job run."""
        with self.db_service.get_session() as session:
            job_run = session.query(JobRun).filter_by(run_id=run_id).first()
            if job_run:
                job_run.checkpoint_json = checkpoint
                job_run.updated_at = datetime.utcnow()
                session.commit()
                logger.debug(f"Saved checkpoint for job run {run_id}")

    def load_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        """Load checkpoint for a job run."""
        with self.db_service.get_session() as session:
            job_run = session.query(JobRun).filter_by(run_id=run_id).first()
            if job_run and job_run.checkpoint_json:
                logger.info(f"Loaded checkpoint for job run {run_id}")
                return job_run.checkpoint_json
        return None

    def track_llm_request(
        self,
        provider: str,
        model: str,
        request_payload: dict[str, Any],
        endpoint: str | None = None,
    ) -> str:
        """
        Track an LLM request.

        Args:
            provider: LLM provider (openai, anthropic, etc)
            model: Model name
            request_payload: Full request payload
            endpoint: API endpoint

        Returns:
            request_id: The created request ID
        """
        if not self._current_job_run_id:
            logger.warning("No current job run, skipping LLM request tracking")
            return ""

        request_id = f"llm_req_{uuid.uuid4().hex[:8]}"

        with self.db_service.get_session() as session:
            llm_request = LLMRequest(
                request_id=request_id,
                job_run_id=self._current_job_run_id,
                provider=provider,
                model=model,
                endpoint=endpoint,
                request_json=request_payload,
                prompt_tokens=request_payload.get("prompt_tokens"),
                max_tokens=request_payload.get("max_tokens"),
                temperature=request_payload.get("temperature"),
            )
            session.add(llm_request)
            session.commit()

        return request_id

    def track_llm_response(
        self,
        request_id: str,
        response_payload: dict[str, Any],
        response_time_ms: int,
    ):
        """Track an LLM response."""
        if not request_id:
            return

        response_id = f"llm_resp_{uuid.uuid4().hex[:8]}"

        with self.db_service.get_session() as session:
            llm_response = LLMResponse(
                response_id=response_id,
                request_id=request_id,
                response_json=response_payload,
                latency_ms=float(response_time_ms),
                completion_tokens=response_payload.get("usage", {}).get(
                    "completion_tokens"
                ),
                total_tokens=response_payload.get("usage", {}).get("total_tokens"),
                status_code=200,  # Default to success
            )
            session.add(llm_response)
            session.commit()

    async def process_job(
        self, job_id: str, resume_from_checkpoint: bool = True
    ) -> dict[str, Any]:
        """
        Process a job with full System 2 tracking.

        Args:
            job_id: The job to process
            resume_from_checkpoint: Whether to resume from saved checkpoint

        Returns:
            Processing results
        """
        # Create job run
        run_id = self.create_job_run(job_id)

        try:
            # Update status to running
            self.update_job_run_status(run_id, "running")

            # Load job configuration
            with self.db_service.get_session() as session:
                job = session.query(Job).filter_by(job_id=job_id).first()
                if not job:
                    raise KnowledgeSystemError(
                        f"Job {job_id} not found", ErrorCode.PROCESSING_FAILED
                    )

                job_type = job.job_type
                input_id = job.input_id
                config = job.config_json or {}
                auto_process = job.auto_process == "true"

            # Load checkpoint if requested
            checkpoint = None
            if resume_from_checkpoint:
                checkpoint = self.load_checkpoint(run_id)

            # Process based on job type
            result = await self._process_by_type(
                job_type, input_id, config, checkpoint, run_id
            )

            # Update status to succeeded
            metrics = self._extract_metrics(result)
            self.update_job_run_status(run_id, "succeeded", metrics=metrics)

            # Chain to next stage if auto_process is enabled
            if auto_process:
                next_job_type = self._get_next_job_type(job_type)
                if next_job_type:
                    logger.info(f"Auto-processing enabled, chaining to {next_job_type}")
                    next_job_id = self.create_job(
                        next_job_type,
                        result.get("output_id", input_id),
                        config,
                        auto_process=True,
                    )
                    # Process next job asynchronously
                    asyncio.create_task(self.process_job(next_job_id))

            return result

        except Exception as e:
            # Update status to failed
            error_code = (
                e.error_code
                if isinstance(e, KnowledgeSystemError)
                else ErrorCode.PROCESSING_FAILED
            )
            self.update_job_run_status(
                run_id, "failed", error_code=error_code, error_message=str(e)
            )
            raise

        finally:
            self._current_job_run_id = None

    async def _process_by_type(
        self,
        job_type: str,
        input_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """Process based on job type."""
        if job_type == "transcribe":
            return await self._process_transcribe(input_id, config, checkpoint, run_id)
        elif job_type == "mine":
            return await self._process_mine(input_id, config, checkpoint, run_id)
        elif job_type == "flagship":
            return await self._process_flagship(input_id, config, checkpoint, run_id)
        elif job_type == "upload":
            return await self._process_upload(input_id, config, checkpoint, run_id)
        elif job_type == "pipeline":
            return await self._process_pipeline(input_id, config, checkpoint, run_id)
        else:
            raise KnowledgeSystemError(
                f"Unknown job type: {job_type}", ErrorCode.INVALID_INPUT
            )

    async def _process_transcribe(
        self,
        video_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """Process transcription job."""
        # TODO: Implement transcription with checkpoint support
        logger.info(f"Processing transcription for {video_id}")
        return {"status": "completed", "output_id": f"episode_{video_id}"}

    async def _process_mine(
        self,
        episode_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """Process mining job."""
        # TODO: Implement mining with checkpoint support
        logger.info(f"Processing mining for {episode_id}")
        return {"status": "completed", "output_id": episode_id}

    async def _process_flagship(
        self,
        episode_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """Process flagship evaluation job."""
        # TODO: Implement flagship with checkpoint support
        logger.info(f"Processing flagship for {episode_id}")
        return {"status": "completed", "output_id": episode_id}

    async def _process_upload(
        self,
        episode_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """Process upload job."""
        # TODO: Implement upload with checkpoint support
        logger.info(f"Processing upload for {episode_id}")
        return {"status": "completed", "output_id": episode_id}

    async def _process_pipeline(
        self,
        video_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """Process complete pipeline job."""
        # TODO: Implement full pipeline with checkpoint support
        logger.info(f"Processing pipeline for {video_id}")
        return {"status": "completed", "output_id": f"episode_{video_id}"}

    def _get_next_job_type(self, current_type: str) -> str | None:
        """Get the next job type in the pipeline."""
        pipeline_order = {
            "transcribe": "mine",
            "mine": "flagship",
            "flagship": "upload",
            "upload": None,
        }
        return pipeline_order.get(current_type)

    def _extract_metrics(self, result: dict[str, Any]) -> dict[str, Any]:
        """Extract metrics from processing result."""
        return {
            "processing_time": result.get("processing_time", 0),
            "items_processed": result.get("items_processed", 0),
            "errors": result.get("errors", 0),
        }

    async def list_jobs(
        self,
        job_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List jobs with optional filtering."""
        with self.db_service.get_session() as session:
            query = session.query(Job)

            if job_type:
                query = query.filter_by(job_type=job_type)

            jobs = query.order_by(Job.created_at.desc()).limit(limit).all()

            result = []
            for job in jobs:
                # Get latest run
                latest_run = (
                    session.query(JobRun)
                    .filter_by(job_id=job.job_id)
                    .order_by(JobRun.created_at.desc())
                    .first()
                )

                if status and latest_run and latest_run.status != status:
                    continue

                job_dict = {
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "input_id": job.input_id,
                    "auto_process": job.auto_process,
                    "created_at": job.created_at.isoformat(),
                    "latest_run": None,
                }

                if latest_run:
                    job_dict["latest_run"] = {
                        "run_id": latest_run.run_id,
                        "status": latest_run.status,
                        "attempt_number": latest_run.attempt_number,
                        "started_at": (
                            latest_run.started_at.isoformat()
                            if latest_run.started_at
                            else None
                        ),
                        "completed_at": (
                            latest_run.completed_at.isoformat()
                            if latest_run.completed_at
                            else None
                        ),
                        "error_code": latest_run.error_code,
                    }

                result.append(job_dict)

            return result

    async def resume_failed_jobs(self, job_type: str | None = None) -> int:
        """Resume all failed jobs."""
        jobs = await self.list_jobs(job_type=job_type, status="failed")
        resumed_count = 0

        for job_info in jobs:
            try:
                logger.info(f"Resuming failed job {job_info['job_id']}")
                asyncio.create_task(
                    self.process_job(job_info["job_id"], resume_from_checkpoint=True)
                )
                resumed_count += 1
            except Exception as e:
                logger.error(f"Failed to resume job {job_info['job_id']}: {e}")

        return resumed_count


# Singleton instance
_orchestrator: System2Orchestrator | None = None


def get_orchestrator(
    db_service: DatabaseService | None = None,
) -> System2Orchestrator:
    """Get the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = System2Orchestrator(db_service)
    return _orchestrator
