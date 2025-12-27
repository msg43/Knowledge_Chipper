"""
FastAPI Routes

All daemon REST API endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException

from daemon import __version__
from daemon.models.schemas import (
    HealthResponse,
    JobListResponse,
    JobStatus,
    ProcessRequest,
    ProcessResponse,
)
from daemon.services.processing_service import processing_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================
# Health Check
# ============================================
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    GetReceipts.org pings this to detect if daemon is running.
    Returns daemon status, version, and capabilities.
    """
    return HealthResponse(
        status="healthy",
        version=__version__,
        uptime_seconds=processing_service.get_uptime_seconds(),
        active_jobs=processing_service.get_active_job_count(),
    )


# ============================================
# Process Video/Audio
# ============================================
@router.post("/process", response_model=ProcessResponse)
async def start_processing(request: ProcessRequest):
    """
    Start processing a video/audio source.
    
    Returns job_id for tracking progress via /jobs/{id} endpoint.
    
    Phase 1: Only download stage is fully implemented.
    Phase 2: Will add transcription, extraction, and upload.
    """
    logger.info(f"Starting processing job for {request.url}")

    try:
        job_id = await processing_service.start_job(request)

        return ProcessResponse(
            job_id=job_id,
            status="queued",
            message="Job queued successfully",
            estimated_duration_seconds=300,  # 5 minute estimate for download
        )

    except Exception as e:
        logger.exception("Failed to start job")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Job Status
# ============================================
@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    Get current status of a processing job.
    
    GetReceipts.org polls this for progress updates.
    Returns detailed status including progress, current stage, and results.
    """
    job = processing_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


# ============================================
# List All Jobs
# ============================================
@router.get("/jobs", response_model=JobListResponse)
async def list_all_jobs():
    """
    List all processing jobs.
    
    Returns summary counts and full job list.
    """
    jobs = processing_service.list_jobs()

    return JobListResponse(
        total=len(jobs),
        active=len([j for j in jobs if j.status not in ["complete", "failed"]]),
        completed=len([j for j in jobs if j.status == "complete"]),
        failed=len([j for j in jobs if j.status == "failed"]),
        jobs=jobs,
    )


# ============================================
# Cancel Job (Phase 2)
# ============================================
@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """
    Cancel a running job.
    
    Phase 2: Not yet implemented.
    """
    job = processing_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ["complete", "failed"]:
        raise HTTPException(status_code=400, detail="Job already finished")

    # TODO: Implement actual cancellation
    raise HTTPException(status_code=501, detail="Cancellation not yet implemented (Phase 2)")

