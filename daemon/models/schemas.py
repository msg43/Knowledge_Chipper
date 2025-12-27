"""
API Request/Response Models

Pydantic schemas for type-safe API validation.
These schemas must match the TypeScript interfaces in GetReceipts.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ============================================
# Health Check
# ============================================
class HealthResponse(BaseModel):
    """Health check response - used by website to detect daemon."""

    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    version: str
    uptime_seconds: float
    active_jobs: int
    capabilities: list[str] = Field(
        default_factory=lambda: [
            "youtube_download",
            "local_file_processing",
            "whisper_transcription",
            "cloud_llm_extraction",
            "claims_upload",
        ]
    )


# ============================================
# Processing Jobs
# ============================================
class ProcessRequest(BaseModel):
    """Request to process a video/audio source."""

    url: str = Field(..., description="YouTube URL or local file path")
    source_type: Literal["youtube", "local_file", "rss"] = "youtube"

    # Processing options
    transcribe: bool = True
    extract_claims: bool = True
    auto_upload: bool = True  # Upload to GetReceipts on completion

    # Model selection (optional, uses defaults)
    whisper_model: Optional[str] = None
    llm_provider: Optional[Literal["openai", "anthropic"]] = None
    llm_model: Optional[str] = None


class ProcessResponse(BaseModel):
    """Immediate response when starting a job."""

    job_id: str
    status: Literal["queued", "starting"] = "queued"
    message: str = "Job queued successfully"
    estimated_duration_seconds: Optional[int] = None


# ============================================
# Job Status
# ============================================
class JobStatus(BaseModel):
    """Current status of a processing job."""

    job_id: str
    status: Literal[
        "queued",
        "downloading",
        "transcribing",
        "extracting",
        "uploading",
        "complete",
        "failed",
    ]

    # Progress
    progress: float = Field(0.0, ge=0.0, le=1.0)  # 0.0 to 1.0
    current_stage: str = "Initializing"
    stages_complete: list[str] = Field(default_factory=list)
    stages_remaining: list[str] = Field(default_factory=list)

    # Timing
    started_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    # Results (when complete)
    source_id: Optional[str] = None
    title: Optional[str] = None
    claims_count: Optional[int] = None
    transcript_length: Optional[int] = None
    error: Optional[str] = None

    # Upload status
    uploaded_to_getreceipts: bool = False
    getreceipts_episode_code: Optional[str] = None  # e.g., "EA4G69"


# ============================================
# Job List
# ============================================
class JobListResponse(BaseModel):
    """List of all jobs."""

    total: int
    active: int
    completed: int
    failed: int
    jobs: list[JobStatus]

