"""
Processing Service

Wraps existing Knowledge_Chipper processors for FastAPI daemon.
Supports single and batch processing with retry capability.
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

from daemon.models.schemas import ProcessRequest, JobStatus, BatchProcessResponse
from daemon.config.settings import settings

# Import YouTube playlist expansion functions
try:
    from src.knowledge_system.utils.youtube_utils import (
        is_playlist_url,
        expand_playlist_urls_with_metadata,
    )
    PLAYLIST_SUPPORT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Playlist expansion not available: {e}")
    PLAYLIST_SUPPORT_AVAILABLE = False

# Import RSS feed service
try:
    from daemon.services.rss_service import rss_service, RSS_SUPPORT_AVAILABLE
except ImportError as e:
    logger.warning(f"RSS support not available: {e}")
    RSS_SUPPORT_AVAILABLE = False
    rss_service = None

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
        # Job history limit
        self._max_history = 500

    async def expand_playlist_and_process(self, request: ProcessRequest) -> BatchProcessResponse:
        """
        Expand a YouTube playlist URL to individual videos and create jobs for each.
        
        Args:
            request: ProcessRequest with a playlist URL
            
        Returns:
            BatchProcessResponse with job_ids for all videos
        """
        if not PLAYLIST_SUPPORT_AVAILABLE:
            raise RuntimeError("Playlist expansion not available")
        
        if not request.url or not is_playlist_url(request.url):
            raise ValueError("Not a valid playlist URL")
        
        logger.info(f"Expanding playlist: {request.url}")
        
        # Expand playlist to individual video URLs
        try:
            result = expand_playlist_urls_with_metadata([request.url])
            video_urls = result["expanded_urls"]
            playlist_info = result["playlist_info"]
            
            if not video_urls:
                return BatchProcessResponse(
                    total_items=0,
                    jobs_created=0,
                    job_ids=[],
                    message="Playlist is empty or could not be expanded"
                )
            
            # Log playlist info
            if playlist_info:
                for playlist in playlist_info:
                    playlist_title = playlist.get("title", "Unknown Playlist")
                    video_count = playlist.get("total_videos", 0)
                    logger.info(f"Expanded playlist '{playlist_title}' to {video_count} videos")
            
            # Create individual jobs for each video
            job_ids = []
            for video_url in video_urls:
                single_request = ProcessRequest(
                    url=video_url,
                    source_type="youtube",
                    transcribe=request.transcribe,
                    extract_claims=request.extract_claims,
                    auto_upload=request.auto_upload,
                    process_full_pipeline=request.process_full_pipeline,
                    whisper_model=request.whisper_model,
                    llm_provider=request.llm_provider,
                    llm_model=request.llm_model,
                )
                job_id = await self.start_job(single_request)
                job_ids.append(job_id)
            
            message = f"Expanded playlist to {len(video_urls)} videos"
            if playlist_info:
                playlist_title = playlist_info[0].get("title", "Playlist")
                message = f"Playlist '{playlist_title}': {len(video_urls)} videos"
            
            return BatchProcessResponse(
                total_items=len(video_urls),
                jobs_created=len(job_ids),
                job_ids=job_ids,
                message=message
            )
        
        except Exception as e:
            logger.error(f"Failed to expand playlist: {e}")
            raise

    async def expand_rss_and_process(
        self, 
        request: ProcessRequest, 
        max_episodes: int = 9999
    ) -> BatchProcessResponse:
        """
        Expand an RSS feed URL to individual episodes and create jobs for each.
        
        Args:
            request: ProcessRequest with an RSS feed URL
            max_episodes: Maximum number of episodes to download (default 9999)
            
        Returns:
            BatchProcessResponse with job_ids for all episodes
        """
        if not RSS_SUPPORT_AVAILABLE or not rss_service:
            raise RuntimeError("RSS support not available")
        
        if not request.url:
            raise ValueError("RSS URL required")
        
        logger.info(f"Expanding RSS feed: {request.url} (max {max_episodes} episodes)")
        
        try:
            # Get latest episodes from RSS feed
            episodes = rss_service.get_latest_episodes(request.url, max_episodes)
            
            if not episodes:
                return BatchProcessResponse(
                    total_items=0,
                    jobs_created=0,
                    job_ids=[],
                    message="RSS feed is empty or could not be parsed"
                )
            
            logger.info(f"Found {len(episodes)} episodes in RSS feed")
            
            # Create jobs for each episode's audio URL
            job_ids = []
            for episode in episodes:
                audio_url = episode.get('audio_url')
                if not audio_url:
                    logger.warning(f"Skipping episode without audio URL: {episode.get('title')}")
                    continue
                
                # Create job for this episode
                single_request = ProcessRequest(
                    url=audio_url,
                    source_type="local_file",  # Treat as audio file
                    transcribe=request.transcribe,
                    extract_claims=request.extract_claims,
                    auto_upload=request.auto_upload,
                    process_full_pipeline=request.process_full_pipeline,
                    whisper_model=request.whisper_model,
                    llm_provider=request.llm_provider,
                    llm_model=request.llm_model,
                )
                job_id = await self.start_job(single_request)
                job_ids.append(job_id)
            
            message = f"RSS Feed: {len(job_ids)} episodes"
            if episodes and episodes[0].get('title'):
                # Try to extract feed/show name from first episode
                feed_name = episodes[0].get('title', 'RSS Feed').split(' - ')[0]
                message = f"{feed_name}: {len(job_ids)} episodes"
            
            return BatchProcessResponse(
                total_items=len(episodes),
                jobs_created=len(job_ids),
                job_ids=job_ids,
                message=message
            )
        
        except Exception as e:
            logger.error(f"Failed to expand RSS feed: {e}")
            raise

    async def start_job(self, request: ProcessRequest) -> str:
        """
        Start a new processing job.
        Returns job_id for tracking.
        
        If the URL is a YouTube playlist, this will be handled by expand_playlist_and_process().
        """
        job_id = str(uuid.uuid4())

        # Determine input URL
        input_url = request.url
        input_type = request.source_type
        
        # Handle local_paths - take first one for single job
        if request.local_paths and len(request.local_paths) > 0:
            input_url = request.local_paths[0]
            input_type = "local_file"

        # Determine stages based on request options
        stages = []
        if request.source_type == "youtube":
            stages.append("download")
        elif request.source_type in ["local_file", "pdf_transcript"]:
            # No download stage for local files
            pass
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
            input_url=input_url,
            input_type=input_type,
            original_request=request.model_dump(),  # Store for retry
        )

        self.jobs[job_id] = status
        self._job_data[job_id] = {}

        # Start processing in background
        asyncio.create_task(self._process_job(job_id, request))

        return job_id

    async def start_batch_jobs(self, request: ProcessRequest) -> list[str]:
        """
        Start multiple processing jobs from a batch request.
        Returns list of job_ids.
        """
        job_ids = []
        
        # Collect all URLs to process
        urls_to_process = []
        
        if request.url:
            urls_to_process.append((request.url, request.source_type))
        
        if request.urls:
            for url in request.urls:
                urls_to_process.append((url, "youtube"))
        
        if request.local_paths:
            for path in request.local_paths:
                # Detect PDF transcripts
                source_type = "pdf_transcript" if path.lower().endswith(".pdf") else "local_file"
                urls_to_process.append((path, source_type))
        
        # Create individual jobs for each URL
        for url, source_type in urls_to_process:
            single_request = ProcessRequest(
                url=url,
                source_type=source_type,
                transcribe=request.transcribe,
                extract_claims=request.extract_claims,
                auto_upload=request.auto_upload,
                process_full_pipeline=request.process_full_pipeline,
                whisper_model=request.whisper_model,
                llm_provider=request.llm_provider,
                llm_model=request.llm_model,
            )
            job_id = await self.start_job(single_request)
            job_ids.append(job_id)
        
        return job_ids

    async def retry_job(self, job_id: str) -> Optional[str]:
        """
        Retry a failed job.
        Returns new job_id or None if original job not found.
        """
        original_job = self.jobs.get(job_id)
        if not original_job:
            return None
        
        if original_job.status != "failed":
            return None  # Can only retry failed jobs
        
        # Recreate request from stored data
        original_request = original_job.original_request
        if not original_request:
            return None
        
        request = ProcessRequest(**original_request)
        new_job_id = await self.start_job(request)
        
        # Update retry count on new job
        new_job = self.jobs[new_job_id]
        new_job.retry_count = original_job.retry_count + 1
        
        return new_job_id

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.
        Returns True if cancelled, False if not found or already finished.
        """
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status in ["complete", "failed", "cancelled"]:
            return False
        
        job.status = "cancelled"
        job.current_stage = "Cancelled by user"
        job.updated_at = datetime.now(timezone.utc)
        job.completed_at = datetime.now(timezone.utc)
        
        # TODO: Implement actual task cancellation with CancellationToken
        
        return True

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from history.
        Only allows deletion of completed/failed/cancelled jobs.
        """
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status not in ["complete", "failed", "cancelled"]:
            return False  # Can't delete active jobs
        
        del self.jobs[job_id]
        if job_id in self._job_data:
            del self._job_data[job_id]
        
        return True

    async def _process_job(self, job_id: str, request: ProcessRequest):
        """
        Background task that processes the full pipeline.
        """
        job_data = self._job_data[job_id]
        
        try:
            # ============================================
            # Stage 0: Handle text content (if provided)
            # ============================================
            if request.text_content:
                # Text content provided directly - skip download and transcription
                logger.info("Processing direct text content")
                job_data["transcript"] = request.text_content
                job_data["transcript_length"] = len(request.text_content)
                job_data["source_id"] = f"text_{job_id[:8]}"
                job_data["title"] = "Text Content"
                job_data["metadata"] = {"source_type": request.source_type}
                
                # Skip download and transcription stages
                request.transcribe = False
                
                await self._update_job(
                    job_id,
                    "extracting",
                    0.10,
                    f"Text content loaded ({len(request.text_content):,} chars)",
                    transcript_length=len(request.text_content),
                )
            
            # ============================================
            # Stage 1: Download (YouTube only)
            # ============================================
            elif request.source_type == "youtube":
                logger.critical("VERIFYING CODE VERSION: LINE 409 - YOUTUBE DOWNLOAD PATH STARTING")
                logger.critical(f"DEBUG: request.url = {repr(request.url)}")
                logger.critical(f"DEBUG: request.url type = {type(request.url)}")
                logger.critical(f"DEBUG: request dict = {request.model_dump()}")
                
                # Validate URL before proceeding
                if not request.url:
                    raise Exception("No URL provided in request (url field is empty/None)")
                
                await self._update_job(job_id, "downloading", 0.05, "Downloading from YouTube - CODE VERSION 2026-01-09-11:00")

                try:
                    logger.critical("DEBUG v2: Before imports")
                    from src.knowledge_system.processors.youtube_download import (
                        YouTubeDownloadProcessor,
                    )
                    from src.knowledge_system.config import get_settings

                    logger.critical("DEBUG v2: About to call get_settings()")
                    kc_settings = get_settings()
                    logger.critical(f"DEBUG v2: kc_settings type: {type(kc_settings)}")
                    logger.critical(f"DEBUG v2: kc_settings.paths type: {type(kc_settings.paths)}")
                    logger.critical(f"DEBUG v2: kc_settings.paths.output_dir = {kc_settings.paths.output_dir}")
                    output_dir = Path(kc_settings.paths.output_dir) / "downloads" / "youtube"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    logger.critical(f"DEBUG v2: Created output_dir: {output_dir}")

                    # Initialize database service for download tracking
                    from src.knowledge_system.database.service import DatabaseService
                    import time
                    
                    db_service = DatabaseService()
                    logger.critical(f"DEBUG v3: DatabaseService created, db_path={db_service.db_path}")
                    
                    # Test database write to catch any SQLAlchemy issues
                    try:
                        test_source = db_service.create_source(
                            source_id="test_write_" + str(int(time.time())),
                            title="Test Write",
                            url="https://test.com",
                            source_type="youtube"
                        )
                        if test_source:
                            logger.critical("DEBUG v3: Test database write SUCCESSFUL ✓")
                        else:
                            logger.critical("DEBUG v3: Test database write returned None - exception was caught silently")
                    except Exception as test_e:
                        logger.critical(f"DEBUG v3: Test database write FAILED: {test_e}")
                        import traceback
                        logger.critical(f"DEBUG v3: Traceback:\n{traceback.format_exc()}")
                    
                    # Use YouTube Transcript Service (proven reliable approach)
                    # Gets transcript via YouTube Transcript API (fast, no download needed)
                    from daemon.services.youtube_transcript_service import YouTubeTranscriptService
                    
                    transcript_service = YouTubeTranscriptService()
                    logger.info(f"Getting YouTube transcript for: {request.url}")
                    
                    result = await asyncio.to_thread(
                        transcript_service.get_complete_data,
                        request.url
                    )
                    
                    if not result.get('success'):
                        raise Exception(f"Failed to get YouTube data: {result.get('error')}")
                except Exception as e:
                    import traceback
                    full_tb = traceback.format_exc()
                    logger.critical(f"EXCEPTION IN YOUTUBE DOWNLOAD:\n{full_tb}")
                    raise Exception(f"YouTube download error: {str(e)}\n\nFull traceback:\n{full_tb}")

                # Extract info from result
                source_id = result['video_id']
                title = result['title']
                transcript_text = result['transcript']
                
                # Save transcript to file for later processing
                transcript_file = output_dir / f"{source_id}_transcript.txt"
                transcript_file.write_text(transcript_text, encoding='utf-8')
                
                logger.info(f"✅ Got transcript: {len(transcript_text)} chars, {result.get('transcript_entry_count')} entries")
                
                # Store for later stages
                job_data["source_id"] = source_id
                job_data["title"] = title
                job_data["transcript_file"] = str(transcript_file)
                job_data["transcript_text"] = transcript_text
                job_data["metadata"] = result['metadata']
                job_data["skip_transcription"] = True  # We already have the transcript!

                await self._update_job(
                    job_id,
                    "downloading",
                    0.20,
                    "Download complete",
                    source_id=source_id,
                    title=title,
                )

                self._mark_stage_complete(job_id, "download")

            elif request.source_type in ["local_file", "pdf_transcript"]:
                # For local files, set up job data from path
                file_path = request.url
                job_data["audio_file"] = file_path
                job_data["source_id"] = Path(file_path).stem
                job_data["title"] = Path(file_path).stem
                job_data["metadata"] = {"file_path": file_path}

            # ============================================
            # Stage 2: Transcribe with Whisper (or use existing transcript)
            # ============================================
            if request.transcribe and not job_data.get("skip_transcription"):
                await self._update_job(job_id, "transcribing", 0.25, "Transcribing with Whisper")

                from src.knowledge_system.processors.audio_processor import AudioProcessor
                
                audio_file = job_data.get("audio_file")
                if not audio_file or not Path(audio_file).exists():
                    raise Exception(f"Audio file not found: {audio_file}")

                # Use Whisper model from request or default
                model = request.whisper_model or settings.default_whisper_model
                
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
            
            elif job_data.get("skip_transcription"):
                # We already have the transcript from YouTube Transcript API
                await self._update_job(job_id, "transcribing", 0.25, "Using YouTube transcript")
                transcript = job_data.get("transcript_text", "")
                job_data["transcript"] = transcript
                job_data["transcript_length"] = len(transcript)
                logger.info(f"✅ Using existing transcript: {len(transcript)} chars")

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

                from daemon.services.simple_llm_wrapper import SimpleLLMWrapper
                from src.knowledge_system.processors.two_pass.pipeline import TwoPassPipeline
                
                transcript = job_data.get("transcript", "")
                if not transcript:
                    raise Exception("No transcript available for extraction")

                # Determine LLM provider and model
                provider = request.llm_provider or settings.default_llm_provider or "openai"
                model = request.llm_model or settings.default_llm_model
                
                # Default models per provider (cloud-only per plan)
                if not model:
                    if provider == "openai":
                        model = "gpt-4o"
                    elif provider == "anthropic":
                        model = "claude-3-5-sonnet-20241022"
                    else:
                        model = "gpt-4o"  # fallback to OpenAI
                
                # Initialize LLM wrapper (provides simple complete(prompt) interface)
                llm = SimpleLLMWrapper(
                    provider=provider,
                    model=model,
                    temperature=0.3,
                )
                
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
            import traceback
            full_traceback = traceback.format_exc()
            logger.exception(f"Job {job_id} failed")
            logger.error(f"FULL ERROR TRACEBACK:\n{full_traceback}")
            await self._update_job(
                job_id,
                "failed",
                self.jobs[job_id].progress,
                f"Failed: {str(e)}",
                error=f"{str(e)}\n\nTraceback:\n{full_traceback}",
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
            
            # Note: ExtractionResult doesn't have 'concepts' - it has 'mental_models' instead
            # Concepts are not extracted in the two-pass pipeline
        
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

    def list_jobs(
        self,
        status_filter: str = "all",
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> list[JobStatus]:
        """
        List jobs with optional filtering.
        
        Args:
            status_filter: "all", "active", "completed", "failed"
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            search: Search string to filter by title or URL
        """
        jobs = list(self.jobs.values())
        
        # Filter by status
        if status_filter == "active":
            jobs = [j for j in jobs if j.status not in ["complete", "failed", "cancelled"]]
        elif status_filter == "completed":
            jobs = [j for j in jobs if j.status == "complete"]
        elif status_filter == "failed":
            jobs = [j for j in jobs if j.status == "failed"]
        
        # Filter by search
        if search:
            search_lower = search.lower()
            jobs = [
                j for j in jobs
                if (j.title and search_lower in j.title.lower())
                or (j.input_url and search_lower in j.input_url.lower())
            ]
        
        # Sort by start time (newest first)
        jobs.sort(key=lambda j: j.started_at, reverse=True)
        
        # Apply pagination
        return jobs[offset:offset + limit]

    def get_active_job_count(self) -> int:
        """Get count of active (non-terminal) jobs."""
        return len(
            [j for j in self.jobs.values() if j.status not in ["complete", "failed", "cancelled"]]
        )

    def get_uptime_seconds(self) -> float:
        """Get daemon uptime in seconds."""
        return (datetime.now(timezone.utc) - self._start_time).total_seconds()

    def get_job_counts(self) -> dict:
        """Get counts of jobs by status."""
        jobs = list(self.jobs.values())
        return {
            "total": len(jobs),
            "active": len([j for j in jobs if j.status not in ["complete", "failed", "cancelled"]]),
            "completed": len([j for j in jobs if j.status == "complete"]),
            "failed": len([j for j in jobs if j.status == "failed"]),
            "cancelled": len([j for j in jobs if j.status == "cancelled"]),
        }


# Global service instance
processing_service = ProcessingService()
