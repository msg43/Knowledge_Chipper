"""
Processing Service

Wraps existing Knowledge_Chipper processors for FastAPI daemon.
Phase 1: YouTubeDownloadProcessor
Phase 2: AudioProcessor, TwoPassPipeline, GetReceiptsUploader (fully implemented)
"""

import asyncio
import logging
import os
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
    
    Full pipeline:
    1. Download (YouTubeDownloadProcessor)
    2. Transcribe (AudioProcessor with Whisper)
    3. Extract (TwoPassPipeline with Cloud LLM)
    4. Upload (GetReceiptsUploader)
    """

    def __init__(self):
        self.jobs: dict[str, JobStatus] = {}
        self._start_time = datetime.now(timezone.utc)
        # Track downloaded files per job for use in later stages
        self._job_data: dict[str, dict] = {}

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
        self._job_data[job_id] = {}

        # Start processing in background
        asyncio.create_task(self._process_job(job_id, request))

        return job_id

    async def _process_job(self, job_id: str, request: ProcessRequest):
        """
        Background task that processes the full pipeline.
        """
        job_data = self._job_data[job_id]
        
        try:
            # ============================================
            # Stage 1: Download
            # ============================================
            if request.source_type == "youtube":
                await self._update_job(job_id, "downloading", 0.05, "Downloading from YouTube")

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
                audio_file = result.metadata.get("audio_file")
                
                # Store for later stages
                job_data["source_id"] = source_id
                job_data["title"] = title
                job_data["audio_file"] = audio_file
                job_data["metadata"] = result.metadata

                await self._update_job(
                    job_id,
                    "downloading",
                    0.20,
                    "Download complete",
                    source_id=source_id,
                    title=title,
                )

                self._mark_stage_complete(job_id, "download")

            # ============================================
            # Stage 2: Transcribe with Whisper
            # ============================================
            if request.transcribe:
                await self._update_job(job_id, "transcribing", 0.25, "Transcribing with Whisper")

                from src.knowledge_system.processors.audio_processor import AudioProcessor
                
                audio_file = job_data.get("audio_file")
                if not audio_file or not Path(audio_file).exists():
                    raise Exception(f"Audio file not found: {audio_file}")

                # Use Whisper model from request or default
                model = request.whisper_model or "base"
                
                processor = AudioProcessor(
                    model=model,
                    use_whisper_cpp=True,  # Use whisper.cpp for better performance on Mac
                    use_claims_first=True,  # Skip diarization for speed
                )
                
                result = await asyncio.to_thread(
                    processor.process,
                    audio_file,
                )

                if not result.success:
                    raise Exception(f"Transcription failed: {', '.join(result.errors)}")

                # Store transcript for extraction
                transcript = result.data.get("transcript", "") if result.data else ""
                if not transcript and result.metadata:
                    transcript = result.metadata.get("transcript", "")
                    
                job_data["transcript"] = transcript
                job_data["transcript_length"] = len(transcript)

                await self._update_job(
                    job_id,
                    "transcribing",
                    0.45,
                    f"Transcription complete ({len(transcript):,} chars)",
                    transcript_length=len(transcript),
                )

                self._mark_stage_complete(job_id, "transcribe")

            # ============================================
            # Stage 3: Extract Claims with Cloud LLM
            # ============================================
            if request.extract_claims:
                await self._update_job(job_id, "extracting", 0.50, "Extracting claims with LLM")

                from src.knowledge_system.core.llm_adapter import LLMAdapter
                from src.knowledge_system.processors.two_pass.pipeline import TwoPassPipeline
                
                transcript = job_data.get("transcript", "")
                if not transcript:
                    raise Exception("No transcript available for extraction")

                # Determine LLM provider and model
                provider = request.llm_provider or "openai"
                model = request.llm_model
                
                # Default models per provider (cloud-only per plan)
                if not model:
                    if provider == "openai":
                        model = "gpt-4o"
                    elif provider == "anthropic":
                        model = "claude-3-5-sonnet-20241022"
                    else:
                        model = "gpt-4o"  # fallback to OpenAI
                
                # Initialize LLM adapter
                llm = LLMAdapter(provider=provider)
                
                # Run two-pass pipeline
                pipeline = TwoPassPipeline(llm_adapter=llm)
                
                source_id = job_data.get("source_id", "unknown")
                metadata = job_data.get("metadata", {})
                
                result = await asyncio.to_thread(
                    pipeline.process,
                    source_id=source_id,
                    transcript=transcript,
                    metadata=metadata,
                )

                # Store extraction results
                job_data["claims_count"] = result.total_claims
                job_data["extraction_result"] = result
                job_data["high_importance_claims"] = result.high_importance_claims

                await self._update_job(
                    job_id,
                    "extracting",
                    0.75,
                    f"Extracted {result.total_claims} claims",
                    claims_count=result.total_claims,
                )

                self._mark_stage_complete(job_id, "extract")

            # ============================================
            # Stage 4: Upload to GetReceipts
            # ============================================
            if request.auto_upload:
                await self._update_job(job_id, "uploading", 0.80, "Uploading to GetReceipts.org")

                from knowledge_chipper_oauth.getreceipts_uploader import GetReceiptsUploader
                
                extraction_result = job_data.get("extraction_result")
                if not extraction_result:
                    raise Exception("No extraction results to upload")

                # Prepare session data for upload
                # Convert extraction result to format expected by uploader
                session_data = self._prepare_upload_data(job_data)
                
                uploader = GetReceiptsUploader()
                
                if uploader.is_enabled():
                    upload_result = await asyncio.to_thread(
                        uploader.upload_session_data,
                        session_data,
                    )
                    
                    # Extract episode code from result if available
                    episode_code = upload_result.get("episode_code")
                    job_data["episode_code"] = episode_code
                    
                    await self._update_job(
                        job_id,
                        "uploading",
                        0.95,
                        f"Uploaded to GetReceipts (episode: {episode_code or 'N/A'})",
                        uploaded_to_getreceipts=True,
                        getreceipts_episode_code=episode_code,
                    )
                else:
                    await self._update_job(
                        job_id,
                        "uploading",
                        0.95,
                        "Upload skipped (auto-upload disabled)",
                        uploaded_to_getreceipts=False,
                    )

                self._mark_stage_complete(job_id, "upload")

            # ============================================
            # Complete
            # ============================================
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

    def _mark_stage_complete(self, job_id: str, stage: str):
        """Mark a stage as complete."""
        job = self.jobs[job_id]
        if stage in job.stages_remaining:
            job.stages_remaining.remove(stage)
            job.stages_complete.append(stage)

    def _prepare_upload_data(self, job_data: dict) -> dict:
        """
        Prepare extraction results for GetReceipts upload.
        Converts TwoPassResult to the session_data format expected by uploader.
        """
        extraction = job_data.get("extraction_result")
        if not extraction:
            return {}
        
        source_id = job_data.get("source_id", "unknown")
        metadata = job_data.get("metadata", {})
        
        # Build session data from extraction result
        session_data = {
            "episodes": [{
                "source_id": source_id,
                "title": metadata.get("title", "Unknown"),
                "channel": metadata.get("channel", "Unknown"),
                "url": metadata.get("url", ""),
                "duration_seconds": metadata.get("duration_seconds", 0),
            }],
            "claims": [],
            "people": [],
            "jargon": [],
            "concepts": [],
        }
        
        # Extract claims from the extraction result
        if hasattr(extraction, "extraction") and extraction.extraction:
            claims = extraction.extraction.claims or []
            for claim in claims:
                session_data["claims"].append({
                    "source_id": source_id,
                    "claim_text": claim.get("claim_text", ""),
                    "importance": claim.get("importance", 5),
                    "evidence_type": claim.get("evidence_type", "claim"),
                    "flagged": claim.get("flagged", False),
                })
            
            # Add people
            people = extraction.extraction.people or []
            for person in people:
                if isinstance(person, dict):
                    session_data["people"].append({
                        "source_id": source_id,
                        "name": person.get("name", ""),
                    })
            
            # Add jargon
            jargon = extraction.extraction.jargon or []
            for term in jargon:
                if isinstance(term, dict):
                    session_data["jargon"].append({
                        "source_id": source_id,
                        "term": term.get("term", ""),
                        "definition": term.get("definition", ""),
                    })
            
            # Add concepts
            concepts = extraction.extraction.concepts or []
            for concept in concepts:
                if isinstance(concept, dict):
                    session_data["concepts"].append({
                        "source_id": source_id,
                        "name": concept.get("name", ""),
                        "description": concept.get("description", ""),
                    })
        
        return session_data

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
