"""
System 2 Orchestrator

Provides job tracking, checkpoint persistence, and auto-process chaining
per the System 2 architecture for Knowledge System operations.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..database import DatabaseService
from ..database.system2_models import Job, JobRun, LLMRequest, LLMResponse
from ..errors import ErrorCode, KnowledgeSystemError
from ..utils.id_generation import create_deterministic_id

logger = logging.getLogger(__name__)


class System2Orchestrator:
    """
    Orchestrator that provides System 2 features for Knowledge System processing:
    - Creates job and job_run records for tracking
    - Persists checkpoints for resumability
    - Supports auto_process chaining between stages
    - Tracks all LLM requests/responses for cost accounting
    """

    def __init__(
        self, db_service: DatabaseService | None = None, progress_callback=None
    ):
        """Initialize the System 2 orchestrator."""
        self.db_service = db_service or DatabaseService()
        self._current_job_run_id: str | None = None
        self.progress_callback = (
            progress_callback  # Callback for real-time progress updates
        )

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
            input_id: ID of the input (source_id)
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
                # Ensure plain string stored, not Enum
                try:
                    job_run.error_code = error_code.value  # type: ignore[attr-defined]
                except Exception:
                    job_run.error_code = str(error_code)
            if error_message:
                job_run.error_message = error_message
            if metrics:
                job_run.metrics_json = metrics

            session.commit()
            logger.debug(f"Updated job run {run_id} status to {status}")

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
        media_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """
        Process transcription job using AudioProcessor with checkpoint support.

        This method performs actual audio transcription with:
        - Whisper.cpp Core ML acceleration
        - Optional speaker diarization
        - Database storage
        - Markdown file generation
        - Full checkpoint/resume support

        Checkpoint structure:
        {
            "stage": "validating" | "transcribing" | "diarizing" | "storing" | "completed",
            "file_path": "/path/to/audio.mp3",
            "transcript_text": "...",  # Partial if interrupted
            "final_result": {...}  # Cached result if completed
        }
        """
        try:
            # Check if already completed
            if checkpoint and checkpoint.get("stage") == "completed":
                logger.info(
                    f"Transcription already completed (from checkpoint), returning cached result"
                )
                return checkpoint.get(
                    "final_result", {"status": "succeeded", "output_id": media_id}
                )

            # Report progress
            if self.progress_callback:
                self.progress_callback("loading", 0, media_id)

            # Get file path from config
            file_path = config.get("file_path")
            if not file_path:
                raise KnowledgeSystemError(
                    f"No file_path in config for media {media_id}",
                    ErrorCode.INVALID_INPUT,
                )

            file_path = Path(file_path)
            if not file_path.exists():
                raise KnowledgeSystemError(
                    f"Audio file not found: {file_path}",
                    ErrorCode.INVALID_INPUT,
                )

            logger.info(f"📄 Transcribing: {file_path.name}")

            # Save initial checkpoint
            self.save_checkpoint(
                run_id, {"stage": "validating", "file_path": str(file_path)}
            )

            # Check if transcription already completed in checkpoint
            if checkpoint and checkpoint.get("stage") in ["diarizing", "storing"]:
                logger.info("Resuming from checkpoint - transcription already complete")
                transcript_text = checkpoint.get("transcript_text", "")
                transcript_path = checkpoint.get("transcript_path")
                language = checkpoint.get("language", "unknown")
                duration = checkpoint.get("duration")
            else:
                # Report progress
                if self.progress_callback:
                    self.progress_callback("transcribing", 10, media_id)

                # Save checkpoint before transcription
                self.save_checkpoint(
                    run_id, {"stage": "transcribing", "file_path": str(file_path)}
                )

                # Create AudioProcessor
                from ..processors.audio_processor import AudioProcessor

                model = config.get("model", "medium")
                device = config.get("device", "cpu")
                enable_diarization = config.get("enable_diarization", False)

                processor = AudioProcessor(
                    model=model,
                    device=device,
                    use_whisper_cpp=True,
                    enable_diarization=enable_diarization,
                    require_diarization=enable_diarization,
                    db_service=self.db_service,
                )

                # Process audio file
                result = processor.process(
                    file_path,
                    output_dir=config.get("output_dir"),
                    include_timestamps=config.get("include_timestamps", True),
                    video_metadata=config.get("video_metadata"),
                )

                if not result.success:
                    error_msg = (
                        result.errors[0] if result.errors else "Transcription failed"
                    )
                    raise KnowledgeSystemError(error_msg, ErrorCode.PROCESSING_FAILED)

                # Extract output
                transcript_path = result.metadata.get("transcript_file")
                transcript_text = result.data.get("transcript", "")
                language = result.data.get("language", "unknown")
                duration = result.data.get("duration")

                # Save checkpoint after transcription
                enable_diarization = config.get("enable_diarization", False)
                self.save_checkpoint(
                    run_id,
                    {
                        "stage": "diarizing" if enable_diarization else "storing",
                        "file_path": str(file_path),
                        "transcript_path": str(transcript_path)
                        if transcript_path
                        else None,
                        "transcript_text": transcript_text,
                        "language": language,
                        "duration": duration,
                    },
                )

            # Report progress
            if self.progress_callback:
                self.progress_callback("completed", 100, media_id)

            logger.info(f"✅ Transcription complete: {file_path.name}")

            # Build final result
            final_result = {
                "status": "succeeded",
                "output_id": media_id,
                "result": {
                    "transcript_path": str(transcript_path)
                    if transcript_path
                    else None,
                    "transcript_text": transcript_text,
                    "language": language,
                    "duration": duration,
                    "diarization_enabled": config.get("enable_diarization", False),
                    "speaker_count": 0,  # Would come from diarization if enabled
                },
            }

            # Save final checkpoint
            self.save_checkpoint(
                run_id,
                {
                    "stage": "completed",
                    "file_path": str(file_path),
                    "final_result": final_result,
                },
            )

            return final_result

        except Exception as e:
            logger.error(f"Transcription failed for {media_id}: {e}")
            # Save error checkpoint
            try:
                self.save_checkpoint(
                    run_id,
                    {
                        "stage": "failed",
                        "file_path": config.get("file_path", ""),
                        "error": str(e),
                    },
                )
            except Exception as checkpoint_error:
                logger.warning(f"Failed to save error checkpoint: {checkpoint_error}")
            raise KnowledgeSystemError(
                f"Transcription failed: {str(e)}", ErrorCode.PROCESSING_FAILED
            ) from e

    async def _process_mine(
        self,
        source_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """
        Process mining job using UnifiedHCEPipeline.

        This replaces the old sequential mining with parallel processing
        and rich data capture (evidence, relations, categories).
        """
        from .system2_orchestrator_mining import process_mine_with_unified_pipeline

        return await process_mine_with_unified_pipeline(
            self, source_id, config, checkpoint, run_id
        )

    def _create_summary_from_mining(
        self,
        source_id: str,
        miner_outputs: list[Any],
        config: dict[str, Any],
    ) -> str:
        """Create a Summary record from mining results."""
        import uuid
        from datetime import datetime

        from ..database.models import Summary

        # Generate summary ID
        summary_id = f"summary_{uuid.uuid4().hex[:12]}"

        # Aggregate mining results for summary text
        total_claims = sum(len(o.claims) for o in miner_outputs)
        total_jargon = sum(len(o.jargon) for o in miner_outputs)
        total_people = sum(len(o.people) for o in miner_outputs)
        total_concepts = sum(len(o.mental_models) for o in miner_outputs)

        # Create summary text
        summary_text = f"""# HCE Analysis Summary

This content was analyzed using Hybrid Claim Extraction (HCE).

## Extraction Statistics
- **Claims Extracted:** {total_claims}
- **Jargon Terms:** {total_jargon}
- **People Mentioned:** {total_people}
- **Mental Models/Concepts:** {total_concepts}

## Key Claims
"""
        # Add top claims
        all_claims = []
        for output in miner_outputs:
            all_claims.extend(output.claims)

        for i, claim in enumerate(all_claims[:10], 1):  # Top 10 claims
            claim_text = claim.get("claim_text") or claim.get("text", "")
            summary_text += f"{i}. {claim_text}\n"

        # Prepare HCE data JSON
        hce_data_json = {
            "claims": all_claims,
            "jargon": [j for output in miner_outputs for j in output.jargon],
            "people": [p for output in miner_outputs for p in output.people],
            "mental_models": [
                m for output in miner_outputs for m in output.mental_models
            ],
        }

        # Get LLM info from config
        miner_model = config.get("miner_model", "ollama:qwen2.5:7b-instruct")
        if ":" in miner_model:
            provider, model = miner_model.split(":", 1)
        else:
            provider = "unknown"
            model = miner_model

        # Create Summary record
        with self.db_service.get_session() as session:
            summary = Summary(
                summary_id=summary_id,
                video_id=source_id,
                transcript_id=None,  # Could link to transcript if available
                summary_text=summary_text,
                summary_metadata_json={
                    "source_id": source_id,
                    "mining_timestamp": datetime.utcnow().isoformat(),
                },
                processing_type="hce",
                hce_data_json=hce_data_json,
                llm_provider=provider,
                llm_model=model,
                prompt_template_path=None,
                focus_area=config.get("source", "manual_summarization"),
                prompt_tokens=0,  # Could be tracked if available
                completion_tokens=0,
                total_tokens=0,
                processing_cost=0.0,
                input_length=len(str(miner_outputs)),
                summary_length=len(summary_text),
                compression_ratio=0.0,
                processing_time_seconds=0.0,  # Could be tracked
                created_at=datetime.utcnow(),
                template_used="HCE Mining",
            )
            session.add(summary)
            session.commit()
            logger.info(f"Created summary record: {summary_id} for video {source_id}")

        return summary_id

    def _create_summary_from_pipeline_outputs(
        self,
        source_id: str,
        pipeline_outputs: Any,  # PipelineOutputs
        config: dict[str, Any],
    ) -> str:
        """
        Create summary record from rich pipeline outputs.

        This replaces _create_summary_from_mining() to work with
        PipelineOutputs instead of simple miner outputs.
        """
        import uuid
        from datetime import datetime

        from ..database.models import Summary
        from ..utils.id_generation import create_deterministic_id

        # Generate summary ID
        summary_id = f"summary_{uuid.uuid4().hex[:12]}"

        # Prefer the pipeline-provided long summary as canonical output
        summary_text = None
        try:
            long_summary = getattr(pipeline_outputs, "long_summary", None)
            if isinstance(long_summary, str) and long_summary.strip():
                summary_text = long_summary.strip()
        except Exception:
            summary_text = None

        # Fallback: construct a compact stats summary if long summary missing
        if not summary_text:
            summary_text = f"""# HCE Analysis Summary

This content was analyzed using Hybrid Claim Extraction (HCE) with parallel processing.

## Extraction Statistics
- **Claims Extracted:** {len(pipeline_outputs.claims)}
  - Tier A (High Importance): {len([c for c in pipeline_outputs.claims if c.tier == "A"])}
  - Tier B (Medium Importance): {len([c for c in pipeline_outputs.claims if c.tier == "B"])}
  - Tier C (Lower Importance): {len([c for c in pipeline_outputs.claims if c.tier == "C"])}
- **Evidence Spans:** {sum(len(c.evidence) for c in pipeline_outputs.claims)}
- **Jargon Terms:** {len(pipeline_outputs.jargon)}
- **People Mentioned:** {len(pipeline_outputs.people)}
- **Mental Models/Concepts:** {len(pipeline_outputs.concepts)}
- **Relations:** {len(pipeline_outputs.relations)}
- **Categories:** {len(pipeline_outputs.structured_categories)}

## Top Claims (Tier A)
"""
            # Add top tier A claims
            tier_a_claims = [c for c in pipeline_outputs.claims if c.tier == "A"]
            for i, claim in enumerate(tier_a_claims[:10], 1):
                summary_text += f"{i}. {claim.canonical}\n"

        # Do not embed large HCE JSON; data are persisted in unified tables
        hce_data_json = None

        # Get LLM info from config
        miner_model = config.get("miner_model", "ollama:qwen2.5:7b-instruct")
        if ":" in miner_model:
            provider, model = miner_model.split(":", 1)
        else:
            provider = "unknown"
            model = miner_model

        # Ensure a MediaSource exists for FK integrity on summaries.video_id
        try:
            if not self.db_service.source_exists(source_id):
                fallback_title = Path(config.get("file_path", source_id)).stem
                source_url = config.get("source_url", f"local://{source_id}")
                self.db_service.create_source(
                    video_id=source_id, title=fallback_title, url=source_url
                )
        except Exception as _e:
            logger.warning(f"Could not ensure MediaSource for {source_id}: {_e}")

        with self.db_service.get_session() as session:
            summary = Summary(
                summary_id=summary_id,
                video_id=source_id,
                transcript_id=None,
                summary_text=summary_text,
                summary_metadata_json={
                    "source_id": source_id,
                    "mining_timestamp": datetime.utcnow().isoformat(),
                    "tier_distribution": {
                        "A": len([c for c in pipeline_outputs.claims if c.tier == "A"]),
                        "B": len([c for c in pipeline_outputs.claims if c.tier == "B"]),
                        "C": len([c for c in pipeline_outputs.claims if c.tier == "C"]),
                    },
                    "has_evidence_spans": sum(
                        len(c.evidence) for c in pipeline_outputs.claims
                    )
                    > 0,
                    "has_relations": len(pipeline_outputs.relations) > 0,
                    "has_categories": len(pipeline_outputs.structured_categories) > 0,
                },
                processing_type="hce_unified",
                hce_data_json=hce_data_json,
                llm_provider=provider,
                llm_model=model,
                prompt_template_path=None,
                focus_area=config.get("source", "manual_summarization"),
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                processing_cost=0.0,
                input_length=len(str(pipeline_outputs)),
                summary_length=len(summary_text),
                compression_ratio=0.0,
                processing_time_seconds=0.0,
                created_at=datetime.utcnow(),
                template_used="HCE Unified Pipeline",
            )
            session.add(summary)
            session.commit()
            logger.info(
                f"Created unified summary record: {summary_id} for video {source_id}"
            )

        return summary_id

    async def _process_flagship(
        self,
        source_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """
        Process flagship evaluation with checkpoint support.

        NOTE: This is a legacy/deprecated path. The UnifiedHCEPipeline now includes
        flagship evaluation as part of the mining process. This remains for
        backward compatibility.

        Checkpoint structure:
        {
            "stage": "loading" | "evaluating" | "completed",
            "final_result": {...}
        }
        """
        try:
            # Check if already completed
            if checkpoint and checkpoint.get("stage") == "completed":
                logger.info(f"Flagship evaluation already completed (from checkpoint)")
                return checkpoint.get(
                    "final_result", {"status": "succeeded", "output_id": source_id}
                )

            # Save initial checkpoint
            self.save_checkpoint(run_id, {"stage": "loading"})

            # 1. Load mining results (deprecated legacy path); skip
            miner_outputs = []

            if not miner_outputs:
                logger.warning(
                    f"No mining results found for source {source_id}. "
                    "Flagship evaluation is now integrated into UnifiedHCEPipeline."
                )
                final_result = {
                    "status": "succeeded",
                    "output_id": source_id,
                    "result": {
                        "claims_evaluated": 0,
                        "claims_accepted": 0,
                        "claims_rejected": 0,
                        "note": "Flagship evaluation now integrated in mining pipeline",
                    },
                }

                # Save completion checkpoint
                self.save_checkpoint(
                    run_id, {"stage": "completed", "final_result": final_result}
                )

                return final_result

            # Save checkpoint before evaluation
            self.save_checkpoint(run_id, {"stage": "evaluating"})

            # 2. Run flagship evaluation (simplified for MVP)
            _flagship_model = config.get(
                "flagship_judge_model", "ollama:qwen2.5:7b-instruct"
            )

            # For now, just mark all claims as tier B (MVP simplification)
            # Full flagship evaluation can be added later
            claims_count = sum(len(o.claims) for o in miner_outputs)

            logger.info(
                f"Flagship evaluation complete for {source_id}: {claims_count} claims"
            )

            final_result = {
                "status": "succeeded",
                "output_id": source_id,
                "result": {
                    "claims_evaluated": claims_count,
                    "claims_accepted": claims_count,
                    "claims_rejected": 0,
                },
            }

            # Save completion checkpoint
            self.save_checkpoint(
                run_id, {"stage": "completed", "final_result": final_result}
            )

            return final_result

        except Exception as e:
            logger.error(f"Flagship evaluation failed for {source_id}: {e}")
            # Save error checkpoint
            try:
                self.save_checkpoint(run_id, {"stage": "failed", "error": str(e)})
            except Exception as checkpoint_error:
                logger.warning(f"Failed to save error checkpoint: {checkpoint_error}")
            raise KnowledgeSystemError(
                f"Flagship evaluation failed: {str(e)}", ErrorCode.PROCESSING_FAILED
            ) from e

    async def _process_upload(
        self,
        source_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """
        Process upload job with checkpoint support.

        Checkpoint structure:
        {
            "stage": "preparing" | "uploading" | "completed",
            "uploaded_bytes": 1234,
            "total_bytes": 5678,
            "final_result": {...}
        }
        """
        try:
            # Check if already completed
            if checkpoint and checkpoint.get("stage") == "completed":
                logger.info(f"Upload already completed (from checkpoint)")
                return checkpoint.get(
                    "final_result", {"status": "succeeded", "output_id": source_id}
                )

            logger.info(f"Processing upload for {source_id}")

            # Save initial checkpoint
            self.save_checkpoint(
                run_id, {"stage": "preparing", "uploaded_bytes": 0, "total_bytes": 0}
            )

            # TODO: Implement actual upload logic here
            # For now, just mark as completed

            final_result = {
                "status": "succeeded",
                "output_id": source_id,
                "result": {"note": "Upload functionality pending implementation"},
            }

            # Save completion checkpoint
            self.save_checkpoint(
                run_id, {"stage": "completed", "final_result": final_result}
            )

            return final_result

        except Exception as e:
            logger.error(f"Upload failed for {source_id}: {e}")
            # Save error checkpoint
            try:
                self.save_checkpoint(run_id, {"stage": "failed", "error": str(e)})
            except Exception as checkpoint_error:
                logger.warning(f"Failed to save error checkpoint: {checkpoint_error}")
            raise KnowledgeSystemError(
                f"Upload failed: {str(e)}", ErrorCode.PROCESSING_FAILED
            ) from e

    async def _process_pipeline(
        self,
        source_id: str,
        config: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any]:
        """Process complete pipeline with checkpoint support."""
        try:
            stages = config.get("stages", ["transcribe", "mine", "flagship"])
            completed_stages = (
                checkpoint.get("completed_stages", []) if checkpoint else []
            )

            results = {}

            for stage in stages:
                if stage in completed_stages:
                    logger.info(f"Skipping completed stage: {stage}")
                    continue

                logger.info(f"Running pipeline stage: {stage}")

                # Create sub-job
                stage_job_id = self.create_job(
                    job_type=stage,
                    input_id=source_id,
                    config=config,
                    auto_process=False,
                )

                # Process the stage
                stage_result = await self.process_job(
                    stage_job_id, resume_from_checkpoint=True
                )

                if stage_result.get("status") != "succeeded":
                    raise KnowledgeSystemError(
                        f"Pipeline stage '{stage}' failed", ErrorCode.PROCESSING_FAILED
                    )

                results[stage] = stage_result.get("result", {})
                completed_stages.append(stage)

                # Update checkpoint
                self.save_checkpoint(
                    run_id, {"completed_stages": completed_stages, "results": results}
                )

            logger.info(
                f"Pipeline completed for {source_id}: {len(completed_stages)} stages"
            )

            return {
                "status": "succeeded",
                "output_id": source_id,
                "result": {
                    "stages_completed": len(completed_stages),
                    "stages": completed_stages,
                    "results": results,
                },
            }
        except Exception as e:
            logger.error(f"Pipeline failed for {source_id}: {e}")
            raise KnowledgeSystemError(
                f"Pipeline failed: {str(e)}", ErrorCode.PROCESSING_FAILED
            ) from e

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

    async def _mine_single_segment(
        self, segment: Any, miner_model: str, run_id: str
    ) -> Any:
        """Mine a single segment with LLM tracking."""
        from ..processors.hce.model_uri_parser import parse_model_uri
        from ..processors.hce.models.llm_system2 import System2LLM
        from ..processors.hce.unified_miner import UnifiedMiner

        # Parse model URI
        provider, model = parse_model_uri(miner_model)

        # Create LLM instance that uses System2 adapter
        llm = System2LLM(provider=provider, model=model)
        llm.set_job_run_id(run_id)

        # Create miner and process segment
        prompt_path = (
            Path(__file__).parent.parent
            / "processors"
            / "hce"
            / "prompts"
            / "unified_miner.txt"
        )
        miner = UnifiedMiner(llm, prompt_path)

        return miner.mine_segment(segment)

    def _load_transcript_segments_from_db(
        self, source_id: str
    ) -> list[dict[str, Any]] | None:
        """
        Load transcript segments from database (Whisper.cpp output).

        Returns raw Whisper segments (typically 30-150 segments for a few minutes of audio).
        These need to be re-chunked for efficient HCE processing.
        """
        try:
            transcripts = self.db_service.get_transcripts_for_video(source_id)
            if not transcripts:
                logger.debug(f"No transcripts found in DB for video {source_id}")
                return None

            # Get the most recent transcript
            transcript = transcripts[0]
            segments = transcript.transcript_segments_json

            if segments and len(segments) > 0:
                logger.info(
                    f"📊 Loaded {len(segments)} raw Whisper segments from database for {source_id}"
                )
                return segments

            return None
        except Exception as e:
            logger.debug(f"Could not load segments from DB for {source_id}: {e}")
            return None

    def _rechunk_whisper_segments(
        self,
        whisper_segments: list[dict[str, Any]],
        source_id: str,
        target_tokens: int = 750,
    ) -> list[Any]:
        """
        Intelligently re-chunk Whisper segments for efficient HCE processing.

        Whisper.cpp creates many small segments (~2-5 seconds each) based on pauses.
        We combine these into larger ~750-token chunks while respecting:
        - Sentence boundaries (don't split mid-sentence)
        - Speaker changes (preserve speaker context)
        - Natural topic shifts
        - Overlap for claim coherence when hitting max boundary

        Args:
            whisper_segments: Raw segments from Whisper (list of dicts with 'text', 'start', 'end', 'speaker')
            source_id: Source identifier
            target_tokens: Target tokens per chunk (default 750)

        Returns:
            List of optimized Segment objects for HCE processing
        """
        from ..processors.hce.types import Segment
        from ..utils.text_utils import ChunkingConfig, estimate_tokens_improved

        if not whisper_segments:
            return []

        # Create chunking configuration with overlap
        config = ChunkingConfig(
            max_chunk_tokens=1000,
            overlap_tokens=100,  # 100 token overlap when hitting max boundary
            min_chunk_tokens=300,  # Lower minimum for active conversations
            prefer_sentence_boundaries=True,
            prefer_paragraph_boundaries=False,  # Not relevant for transcripts
        )

        chunked_segments = []
        current_chunk_parts = []
        current_tokens = 0
        chunk_idx = 0
        overlap_parts = []  # Parts to include in next chunk for overlap

        # Track first and last timestamps for the chunk
        chunk_start_time = None
        chunk_end_time = None
        current_speaker = None

        for seg in whisper_segments:
            seg_text = seg.get("text", "").strip()
            if not seg_text:
                continue

            seg_tokens = estimate_tokens_improved(seg_text, "default")
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)
            seg_speaker = seg.get("speaker", "Unknown")

            # Initialize chunk timing
            if chunk_start_time is None:
                chunk_start_time = seg_start
                current_speaker = seg_speaker

            # Check if we should start a new chunk
            should_split = False

            # HARD BOUNDARY: Always split on speaker change
            if seg_speaker != current_speaker and current_chunk_parts:
                should_split = True
                overlap_parts = []  # No overlap on speaker change
                logger.debug(
                    f"Splitting chunk due to speaker change: {current_speaker} → {seg_speaker}"
                )

            # Split if we'd exceed max tokens
            elif (
                current_tokens + seg_tokens > config.max_chunk_tokens
                and current_chunk_parts
            ):
                should_split = True
                # Calculate overlap when hitting max boundary
                if config.overlap_tokens > 0:
                    # Keep last N tokens worth of text for overlap
                    overlap_token_count = 0
                    overlap_parts = []
                    for part in reversed(current_chunk_parts):
                        part_tokens = estimate_tokens_improved(part, "default")
                        if overlap_token_count + part_tokens <= config.overlap_tokens:
                            overlap_parts.insert(0, part)
                            overlap_token_count += part_tokens
                        else:
                            break
                    if overlap_parts:
                        logger.debug(
                            f"Including {len(overlap_parts)} parts ({overlap_token_count} tokens) as overlap"
                        )

            # Split if we've reached target and hit a sentence boundary
            elif (
                current_tokens >= config.min_chunk_tokens
                and seg_text.rstrip().endswith((".", "!", "?"))
            ):
                should_split = True
                overlap_parts = []  # Clean break at sentence boundary

            if should_split:
                # Save current chunk (single speaker only)
                chunk_text = " ".join(current_chunk_parts)

                chunked_segments.append(
                    Segment(
                        episode_id=source_id,
                        segment_id=f"chunk_{chunk_idx:04d}",
                        speaker=current_speaker
                        or "Unknown",  # Single speaker per chunk
                        t0=str(chunk_start_time),
                        t1=str(chunk_end_time),
                        text=chunk_text,
                    )
                )

                # Reset for next chunk
                current_chunk_parts = overlap_parts.copy()  # Start with overlap
                current_tokens = sum(
                    estimate_tokens_improved(part, "default") for part in overlap_parts
                )
                chunk_idx += 1

                # Update timing and speaker
                if seg_speaker != current_speaker:
                    # Speaker change - no overlap, clean start
                    chunk_start_time = seg_start
                    current_speaker = seg_speaker
                else:
                    # Same speaker - adjust start time if we have overlap
                    if not overlap_parts:
                        chunk_start_time = seg_start

            # Add segment to current chunk
            current_chunk_parts.append(seg_text)
            current_tokens += seg_tokens
            chunk_end_time = seg_end

        # Add remaining chunk
        if current_chunk_parts:
            chunk_text = " ".join(current_chunk_parts)
            chunked_segments.append(
                Segment(
                    episode_id=source_id,
                    segment_id=f"chunk_{chunk_idx:04d}",
                    speaker=current_speaker or "Unknown",
                    t0=str(chunk_start_time),
                    t1=str(chunk_end_time),
                    text=chunk_text,
                )
            )

        logger.info(
            f"📊 Re-chunked {len(whisper_segments)} Whisper segments → {len(chunked_segments)} optimized segments "
            f"(target: {target_tokens} tokens/segment, range: {config.min_chunk_tokens}-{config.max_chunk_tokens}, "
            f"overlap: {config.overlap_tokens} tokens)"
        )
        return chunked_segments

    def _parse_transcript_to_segments(
        self, transcript_text: str, source_id: str
    ) -> list[Any]:
        """Parse transcript text into intelligent segments (chunks of ~500-1000 tokens).

        FALLBACK METHOD: Only used when DB segments are not available.
        Prefer _load_transcript_segments_from_db() + _rechunk_whisper_segments() instead.
        """
        from ..processors.hce.types import Segment
        from ..utils.text_utils import estimate_tokens_improved

        segments = []

        # Clean transcript: remove headers, combine into paragraphs
        lines = transcript_text.split("\n")
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip markdown headers, YAML frontmatter, and very short lines
            if (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith("---")
                and len(stripped) >= 10
            ):
                clean_lines.append(stripped)

        # Combine into full text
        full_text = " ".join(clean_lines)

        # Target: 500-1000 tokens per segment (optimal for LLM processing)
        target_tokens = 750
        max_tokens = 1000

        # Split into sentences for better chunking
        import re

        sentences = re.split(r"(?<=[.!?])\s+", full_text)

        current_chunk = []
        current_tokens = 0
        segment_idx = 0

        for sentence in sentences:
            sentence_tokens = estimate_tokens_improved(sentence, "default")

            # If adding this sentence would exceed max, save current chunk
            if current_tokens + sentence_tokens > max_tokens and current_chunk:
                chunk_text = " ".join(current_chunk)
                segments.append(
                    Segment(
                        episode_id=source_id,
                        segment_id=f"seg_{segment_idx:04d}",
                        speaker="Unknown",
                        t0=f"00:{segment_idx*2:02d}:00",  # Approximate timestamps
                        t1=f"00:{(segment_idx+1)*2:02d}:00",
                        text=chunk_text,
                    )
                )
                current_chunk = []
                current_tokens = 0
                segment_idx += 1

            current_chunk.append(sentence)
            current_tokens += sentence_tokens

            # If we've reached target size, save chunk
            if current_tokens >= target_tokens:
                chunk_text = " ".join(current_chunk)
                segments.append(
                    Segment(
                        episode_id=source_id,
                        segment_id=f"seg_{segment_idx:04d}",
                        speaker="Unknown",
                        t0=f"00:{segment_idx*2:02d}:00",
                        t1=f"00:{(segment_idx+1)*2:02d}:00",
                        text=chunk_text,
                    )
                )
                current_chunk = []
                current_tokens = 0
                segment_idx += 1

        # Add remaining chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            segments.append(
                Segment(
                    episode_id=episode_id,
                    segment_id=f"seg_{segment_idx:04d}",
                    speaker="Unknown",
                    t0=f"00:{segment_idx*2:02d}:00",
                    t1=f"00:{(segment_idx+1)*2:02d}:00",
                    text=chunk_text,
                )
            )

        logger.info(
            f"📊 Created {len(segments)} intelligent segments from transcript (target: {target_tokens} tokens/segment)"
        )
        return segments

    def _chunk_speaker_segments_intelligently(
        self, speaker_segments: list[Any], source_id: str, target_tokens: int = 750
    ) -> list[Any]:
        """
        Chunk speaker-turn segments into larger segments while preserving speaker context.

        This is used when we have many small speaker turns (e.g., 135 segments) and want to
        group them into larger chunks for more efficient LLM processing.
        """
        from ..processors.hce.types import Segment
        from ..utils.text_utils import estimate_tokens_improved

        if not speaker_segments:
            return []

        chunked_segments = []
        current_chunk_texts = []
        current_tokens = 0
        chunk_idx = 0
        max_tokens = 1000

        for seg in speaker_segments:
            seg_text = seg.text if hasattr(seg, "text") else str(seg)
            seg_tokens = estimate_tokens_improved(seg_text, "default")

            # If adding this segment would exceed max, save current chunk
            if current_tokens + seg_tokens > max_tokens and current_chunk_texts:
                chunk_text = " ".join(current_chunk_texts)
                chunked_segments.append(
                    Segment(
                        episode_id=source_id,
                        segment_id=f"chunk_{chunk_idx:04d}",
                        speaker="Multiple",  # Chunked segments may have multiple speakers
                        t0="00:00:00",  # Approximate - would need proper timestamp tracking
                        t1="00:00:00",
                        text=chunk_text,
                    )
                )
                current_chunk_texts = []
                current_tokens = 0
                chunk_idx += 1

            # Add speaker attribution to text for context
            speaker = getattr(seg, "speaker", "Unknown")
            attributed_text = (
                f"[{speaker}]: {seg_text}"
                if speaker and speaker != "Unknown"
                else seg_text
            )
            current_chunk_texts.append(attributed_text)
            current_tokens += seg_tokens

            # If we've reached target size, save chunk
            if current_tokens >= target_tokens:
                chunk_text = " ".join(current_chunk_texts)
                chunked_segments.append(
                    Segment(
                        episode_id=source_id,
                        segment_id=f"chunk_{chunk_idx:04d}",
                        speaker="Multiple",
                        t0="00:00:00",
                        t1="00:00:00",
                        text=chunk_text,
                    )
                )
                current_chunk_texts = []
                current_tokens = 0
                chunk_idx += 1

        # Add remaining chunk
        if current_chunk_texts:
            chunk_text = " ".join(current_chunk_texts)
            chunked_segments.append(
                Segment(
                    episode_id=episode_id,
                    segment_id=f"chunk_{chunk_idx:04d}",
                    speaker="Multiple",
                    t0="00:00:00",
                    t1="00:00:00",
                    text=chunk_text,
                )
            )

        logger.info(
            f"📊 Chunked {len(speaker_segments)} speaker segments into {len(chunked_segments)} larger segments (target: {target_tokens} tokens/segment)"
        )
        return chunked_segments


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
