"""
System 2 Orchestrator

Manages job execution with database-backed state, checkpoint support,
and auto-process chaining per SYSTEM_2_IMPLEMENTATION_GUIDE.md.
"""

import json
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..database import DatabaseService, Job, JobRun, LLMRequest, LLMResponse
from ..errors import ErrorCode, KnowledgeSystemError
from ..logger import get_logger
from ..logger_system2 import get_system2_logger
from ..processors import (
    AudioProcessor,
    YouTubeDownloadProcessor,
    YouTubeTranscriptProcessor,
)
from ..processors.hce.types import EpisodeBundle, Segment
from ..processors.hce.unified_pipeline import UnifiedHCEPipeline
from ..utils.hardware_detection import HardwareDetector
from .llm_adapter import LLMAdapter

# Use System 2 logger if available, fallback to standard
try:
    logger = get_system2_logger(__name__)
except ImportError:
    logger = get_logger(__name__)


class JobType(Enum):
    """Types of jobs that can be orchestrated."""

    TRANSCRIBE = "transcribe"
    MINE = "mine"
    FLAGSHIP = "flagship"
    UPLOAD = "upload"
    PIPELINE = "pipeline"  # Full auto-process pipeline


class JobStatus(Enum):
    """Job execution statuses."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class System2Orchestrator:
    """
    Orchestrates job execution with database persistence and checkpointing.

    Key features:
    - Creates job records for all operations
    - Supports checkpoint/resume for interrupted jobs
    - Auto-process chaining when enabled
    - Hardware-aware resource management
    - Comprehensive error handling and metrics
    """

    def __init__(self, db_service: DatabaseService | None = None):
        """
        Initialize the orchestrator.

        Args:
            db_service: Database service instance (creates one if not provided)
        """
        self.db_service = db_service or DatabaseService()
        self.hardware_detector = HardwareDetector()
        self.hardware_specs = self.hardware_detector.detect_hardware()

        # Initialize LLM adapter for centralized model calls
        self.llm_adapter = LLMAdapter(self.db_service)

        # Initialize processors
        self._init_processors()

        # Log initialization with System 2 context
        if hasattr(logger, "set_context"):
            logger.set_context(component="System2Orchestrator")

        logger.info(
            f"System2 Orchestrator initialized for {self.hardware_specs.get('chip_type', 'Unknown')}",
            context={"hardware_specs": self.hardware_specs},
        )

    def _init_processors(self):
        """Initialize various processors used by the orchestrator."""
        self.audio_processor = AudioProcessor()
        self.youtube_transcript_processor = YouTubeTranscriptProcessor()
        self.youtube_download_processor = YouTubeDownloadProcessor()

        # Processors will be initialized on demand with proper config

    def create_job(
        self,
        job_type: JobType,
        input_id: str,
        config: dict[str, Any] | None = None,
        auto_process: bool = False,
    ) -> str:
        """
        Create a new job record in the database.

        Args:
            job_type: Type of job to create
            input_id: Input identifier (video_id, episode_id, etc.)
            config: Job configuration
            auto_process: Whether to automatically chain to next stage

        Returns:
            job_id: Unique job identifier
        """
        job_id = f"{job_type.value}_{input_id}_{uuid.uuid4().hex[:8]}"

        with self.db_service.get_session() as session:
            job = Job(
                job_id=job_id,
                job_type=job_type.value,
                input_id=input_id,
                config_json=config or {},
                auto_process="true" if auto_process else "false",
            )
            session.add(job)
            session.commit()

        # Log job creation with System 2 metrics
        if hasattr(logger, "log_job_event"):
            logger.log_job_event(
                event_type="job_created",
                job_id=job_id,
                job_type=job_type.value,
                status="queued",
            )
        else:
            logger.info(f"Created job {job_id} for {job_type.value} on {input_id}")

        return job_id

    def execute_job(self, job_id: str, progress_callback=None) -> dict[str, Any]:
        """
        Execute a job with full tracking and error handling.

        Args:
            job_id: Job identifier
            progress_callback: Optional progress callback

        Returns:
            Dict with job results and metrics
        """
        start_time = time.time()
        run_id = f"run_{uuid.uuid4().hex}"

        with self.db_service.get_session() as session:
            # Get job details
            job = session.query(Job).filter_by(job_id=job_id).first()
            if not job:
                raise KnowledgeSystemError(
                    f"Job {job_id} not found",
                    error_code=ErrorCode.DATABASE_CONNECTION_ERROR_HIGH,
                )

            # Create job run record
            job_run = JobRun(
                run_id=run_id,
                job_id=job_id,
                status=JobStatus.RUNNING.value,
                started_at=datetime.utcnow(),
            )
            session.add(job_run)
            session.commit()

            try:
                # Execute based on job type
                result = self._execute_job_type(
                    job, job_run, session, progress_callback
                )

                # Update job run as succeeded
                job_run.status = JobStatus.SUCCEEDED.value
                job_run.completed_at = datetime.utcnow()
                job_run.metrics_json = {
                    "processing_time": time.time() - start_time,
                    "result_summary": result.get("summary", {}),
                }
                session.commit()

                # Handle auto-process chaining
                if job.auto_process == "true":
                    self._chain_next_job(job, result, session)

                return {
                    "job_id": job_id,
                    "run_id": run_id,
                    "status": "succeeded",
                    "result": result,
                    "metrics": job_run.metrics_json,
                }

            except Exception as e:
                # Update job run as failed
                job_run.status = JobStatus.FAILED.value
                job_run.completed_at = datetime.utcnow()
                job_run.error_code = getattr(e, "error_code", "UNKNOWN_ERROR")
                job_run.error_message = str(e)
                session.commit()

                logger.error(f"Job {job_id} failed: {e}")
                raise

    def _execute_job_type(
        self, job: Job, job_run: JobRun, session: Session, progress_callback=None
    ) -> dict[str, Any]:
        """Execute specific job type logic."""
        job_type = JobType(job.job_type)

        if job_type == JobType.TRANSCRIBE:
            return self._execute_transcribe(job, job_run, session, progress_callback)
        elif job_type == JobType.MINE:
            return self._execute_mine(job, job_run, session, progress_callback)
        elif job_type == JobType.FLAGSHIP:
            return self._execute_flagship(job, job_run, session, progress_callback)
        elif job_type == JobType.UPLOAD:
            return self._execute_upload(job, job_run, session, progress_callback)
        elif job_type == JobType.PIPELINE:
            return self._execute_pipeline(job, job_run, session, progress_callback)
        else:
            raise ValueError(f"Unknown job type: {job.job_type}")

    def _execute_transcribe(
        self, job: Job, job_run: JobRun, session: Session, progress_callback=None
    ) -> dict[str, Any]:
        """Execute transcription job."""
        video_id = job.input_id
        config = job.config_json or {}

        # Check for existing transcript
        from ..database import Transcript

        existing = session.query(Transcript).filter_by(video_id=video_id).first()
        if existing and not config.get("force_reprocess", False):
            logger.info(f"Using existing transcript for {video_id}")
            return {
                "video_id": video_id,
                "transcript_id": existing.transcript_id,
                "from_cache": True,
            }

        # Try YouTube transcript first
        try:
            result = self.youtube_transcript_processor.process(video_id)
            if result.success:
                # Save to database
                transcript_data = result.data
                self.db_service.create_transcript(
                    video_id=video_id,
                    transcript_text=transcript_data.get("text", ""),
                    transcript_segments=transcript_data.get("segments", []),
                    is_manual=False,
                )

                return {
                    "video_id": video_id,
                    "transcript_id": f"transcript_{video_id}",
                    "source": "youtube",
                    "segments": len(transcript_data.get("segments", [])),
                }
        except Exception as e:
            logger.warning(f"YouTube transcript failed for {video_id}: {e}")

        # Fall back to audio download and processing
        download_result = self.youtube_download_processor.process(
            f"https://youtube.com/watch?v={video_id}"
        )

        if not download_result.success:
            raise KnowledgeSystemError(
                f"Failed to download video {video_id}",
                error_code=ErrorCode.NETWORK_TIMEOUT_ERROR_MEDIUM,
            )

        audio_path = download_result.data.get("audio_path")
        audio_result = self.audio_processor.process(
            audio_path, progress_callback=progress_callback
        )

        if not audio_result.success:
            raise KnowledgeSystemError(
                f"Failed to process audio for {video_id}",
                error_code=ErrorCode.TRANSCRIPTION_PARTIAL_ERROR_MEDIUM,
            )

        # Save transcript to database
        transcript_data = audio_result.data
        transcript_result = self.db_service.create_transcript(
            video_id=video_id,
            transcript_text=transcript_data.get("text", ""),
            transcript_segments=transcript_data.get("segments", []),
            is_manual=False,
        )
        # Note: confidence_score might need to be stored in metadata

        return {
            "video_id": video_id,
            "transcript_id": f"transcript_{video_id}",
            "source": "whisper",
            "segments": len(transcript_data.get("segments", [])),
            "confidence": transcript_data.get("confidence", 0.0),
        }

    def _execute_mine(
        self, job: Job, job_run: JobRun, session: Session, progress_callback=None
    ) -> dict[str, Any]:
        """Execute mining job with checkpointing."""
        episode_id = job.input_id
        config = job.config_json or {}

        # Load checkpoint if exists
        checkpoint = job_run.checkpoint_json or {}
        last_segment_id = checkpoint.get("last_segment_id")

        # Get transcript segments
        from ..database import Transcript
        from ..database.hce_models import Episode

        episode = session.query(Episode).filter_by(episode_id=episode_id).first()
        if not episode:
            raise ValueError(f"Episode {episode_id} not found")

        transcript = (
            session.query(Transcript).filter_by(video_id=episode.video_id).first()
        )
        if not transcript:
            raise ValueError(f"No transcript found for episode {episode_id}")

        # Initialize unified miner if needed
        if not hasattr(self, "_unified_miner"):
            from ..processors.hce.unified_miner_system2 import UnifiedMinerSystem2

            # Get miner model from config or use default
            miner_config = config.get("miner_model", "openai:gpt-4")
            # Parse provider and model from config (format: "provider:model")
            if ":" in miner_config:
                provider, model = miner_config.split(":", 1)
            else:
                provider, model = "openai", miner_config

            self._unified_miner = UnifiedMinerSystem2(
                llm_adapter=self.llm_adapter, provider=provider, model=model
            )

        # Convert to segments for HCE
        segments = []
        start_processing = last_segment_id is None

        for seg in transcript.transcript_segments_json:
            seg_id = f"seg_{seg.get('start', 0)}"

            # Skip if before checkpoint
            if not start_processing and seg_id == last_segment_id:
                start_processing = True
                continue

            if not start_processing:
                continue

            segments.append(
                Segment(
                    segment_id=seg_id,
                    speaker=seg.get("speaker", "SPEAKER_00"),
                    t0=str(seg.get("start", 0)),
                    t1=str(seg.get("end", 0)),
                    text=seg.get("text", ""),
                )
            )

        # Process segments in batches
        batch_size = 10
        total_mined = checkpoint.get(
            "total_mined",
            {"claims": [], "jargon": [], "people": [], "mental_models": []},
        )

        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]

            # Mine each segment
            for segment in batch:
                try:
                    miner_output = self._unified_miner.mine_segment(
                        segment, job_run.run_id
                    )

                    # Track LLM request
                    self._track_llm_request(
                        job_run.run_id, "unified_miner", segment.segment_id, session
                    )

                    # Accumulate results
                    total_mined["claims"].extend(miner_output.claims)
                    total_mined["jargon"].extend(miner_output.jargon)
                    total_mined["people"].extend(miner_output.people)
                    total_mined["mental_models"].extend(miner_output.mental_models)

                except Exception as e:
                    logger.error(f"Failed to mine segment {segment.segment_id}: {e}")

            # Update checkpoint
            if batch:
                job_run.checkpoint_json = {
                    "last_segment_id": batch[-1].segment_id,
                    "total_mined": total_mined,
                    "segments_processed": i + len(batch),
                }
                session.commit()

            # Progress callback
            if progress_callback:
                progress_callback(
                    "mining",
                    i + len(batch),
                    len(segments),
                    {"current_segment": batch[-1].segment_id if batch else None},
                )

        # Store mined data
        from ..database.hce_models import Claim, Concept, JargonTerm, Person

        # Save claims
        for claim_data in total_mined["claims"]:
            claim_id = f"claim_{uuid.uuid4().hex[:12]}"
            claim = Claim(
                episode_id=episode_id,
                claim_id=claim_id,
                canonical=claim_data["claim_text"],
                claim_type=claim_data["claim_type"],
                tier="B",  # Default tier, will be set by flagship
                first_mention_ts=claim_data["evidence_spans"][0]["t0"]
                if claim_data["evidence_spans"]
                else "0",
                scores_json={"stance": claim_data["stance"]},
            )
            session.add(claim)

        session.commit()

        return {
            "episode_id": episode_id,
            "claims_extracted": len(total_mined["claims"]),
            "jargon_extracted": len(total_mined["jargon"]),
            "people_extracted": len(total_mined["people"]),
            "mental_models_extracted": len(total_mined["mental_models"]),
            "segments_processed": len(segments),
        }

    def _execute_flagship(
        self, job: Job, job_run: JobRun, session: Session, progress_callback=None
    ) -> dict[str, Any]:
        """Execute flagship evaluation job."""
        episode_id = job.input_id

        # Get claims to evaluate
        from ..database.hce_models import Claim

        claims = session.query(Claim).filter_by(episode_id=episode_id).all()

        if not claims:
            logger.warning(f"No claims found for episode {episode_id}")
            return {"episode_id": episode_id, "claims_evaluated": 0}

        # TODO: Implement flagship evaluation
        # For now, just update tiers based on simple rules
        tier_a_count = 0
        tier_b_count = 0
        tier_c_count = 0

        for claim in claims:
            # Simple tier assignment based on claim type
            if claim.claim_type in ["factual", "causal"]:
                claim.tier = "A"
                tier_a_count += 1
            elif claim.claim_type in ["normative", "forecast"]:
                claim.tier = "B"
                tier_b_count += 1
            else:
                claim.tier = "C"
                tier_c_count += 1

            claim.updated_at = datetime.utcnow()

        session.commit()

        return {
            "episode_id": episode_id,
            "claims_evaluated": len(claims),
            "tier_a_count": tier_a_count,
            "tier_b_count": tier_b_count,
            "tier_c_count": tier_c_count,
        }

    def _execute_upload(
        self, job: Job, job_run: JobRun, session: Session, progress_callback=None
    ) -> dict[str, Any]:
        """Execute upload job."""
        episode_id = job.input_id

        # Get claims to upload
        from ..database.hce_models import Claim

        claims = (
            session.query(Claim)
            .filter_by(episode_id=episode_id, upload_status="pending")
            .all()
        )

        if not claims:
            logger.info(f"No pending claims to upload for episode {episode_id}")
            return {"episode_id": episode_id, "claims_uploaded": 0}

        # TODO: Implement actual Supabase upload
        # For now, just mark as uploaded
        uploaded_count = 0
        for claim in claims:
            claim.upload_status = "uploaded"
            claim.last_uploaded_at = datetime.utcnow().isoformat()
            uploaded_count += 1

        session.commit()

        return {"episode_id": episode_id, "claims_uploaded": uploaded_count}

    def _execute_pipeline(
        self, job: Job, job_run: JobRun, session: Session, progress_callback=None
    ) -> dict[str, Any]:
        """Execute full pipeline job."""
        # This is handled by auto_process chaining
        # Just start with transcribe
        transcribe_job_id = self.create_job(
            JobType.TRANSCRIBE, job.input_id, job.config_json, auto_process=True
        )

        return self.execute_job(transcribe_job_id, progress_callback)

    def _chain_next_job(
        self, current_job: Job, result: dict[str, Any], session: Session
    ):
        """Chain to the next job in the pipeline if auto_process is enabled."""
        current_type = JobType(current_job.job_type)

        # Determine next job type
        next_type = None
        next_input_id = None

        if current_type == JobType.TRANSCRIBE:
            next_type = JobType.MINE
            # Create episode if needed
            video_id = current_job.input_id
            from ..database.hce_models import Episode

            episode = session.query(Episode).filter_by(video_id=video_id).first()
            if not episode:
                episode_id = f"episode_{video_id}"
                episode = Episode(
                    episode_id=episode_id,
                    video_id=video_id,
                    title=f"Episode for {video_id}",
                    recorded_at=datetime.utcnow().isoformat(),
                )
                session.add(episode)
                session.commit()
            next_input_id = episode.episode_id

        elif current_type == JobType.MINE:
            next_type = JobType.FLAGSHIP
            next_input_id = current_job.input_id

        elif current_type == JobType.FLAGSHIP:
            next_type = JobType.UPLOAD
            next_input_id = current_job.input_id

        # Create and execute next job
        if next_type and next_input_id:
            next_job_id = self.create_job(
                next_type, next_input_id, current_job.config_json, auto_process=True
            )

            # Execute asynchronously
            logger.info(f"Chaining to next job: {next_job_id}")
            # In a real implementation, this would be queued
            # For now, we just log it

    def _track_llm_request(
        self, run_id: str, operation: str, context: str, session: Session
    ):
        """Track LLM request for cost and audit purposes."""
        request_id = f"llm_{uuid.uuid4().hex[:12]}"

        llm_request = LLMRequest(
            request_id=request_id,
            job_run_id=run_id,
            provider="openai",  # Would come from config
            model="gpt-4",  # Would come from config
            endpoint=operation,
            request_json={"context": context},
        )
        session.add(llm_request)
        session.commit()

    def resume_interrupted_jobs(self) -> list[str]:
        """
        Resume any jobs that were interrupted.

        Returns:
            List of resumed job IDs
        """
        resumed = []

        with self.db_service.get_session() as session:
            # Find interrupted runs
            interrupted_runs = (
                session.query(JobRun).filter_by(status=JobStatus.RUNNING.value).all()
            )

            for run in interrupted_runs:
                logger.info(f"Resuming interrupted job run {run.run_id}")

                # Mark as queued for re-execution
                run.status = JobStatus.QUEUED.value
                session.commit()

                # Re-execute the job
                try:
                    self.execute_job(run.job_id)
                    resumed.append(run.job_id)
                except Exception as e:
                    logger.error(f"Failed to resume job {run.job_id}: {e}")

        return resumed
