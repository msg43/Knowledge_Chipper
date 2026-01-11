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
            "pdf_transcript_import",
            "whisper_transcription",
            "cloud_llm_extraction",
            "claims_upload",
            "folder_monitoring",
        ]
    )


# ============================================
# Processing Jobs
# ============================================
class ProcessRequest(BaseModel):
    """Request to process a video/audio source."""

    # Single URL (backwards compatible)
    url: Optional[str] = Field(None, description="Single YouTube URL or local file path")
    
    # NEW: Batch support
    urls: Optional[list[str]] = Field(None, description="Multiple YouTube URLs for batch processing")
    local_paths: Optional[list[str]] = Field(None, description="Local file paths (audio, video, PDF)")
    
    # NEW: Text content support
    text_content: Optional[str] = Field(None, description="Direct text content (for documents, transcripts)")
    
    # Source type
    source_type: Literal["youtube", "local_file", "pdf_transcript", "rss", "text", "docx", "pdf"] = "youtube"

    # Processing options
    transcribe: bool = True
    extract_claims: bool = True
    auto_upload: bool = True  # Upload to GetReceipts on completion
    process_full_pipeline: bool = True  # Run entire pipeline automatically

    # Model selection
    whisper_model: Literal["tiny", "base", "small", "medium", "large-v3"] = "medium"
    llm_provider: Optional[Literal["openai", "anthropic"]] = None
    llm_model: Optional[str] = None
    
    # RSS-specific options
    max_rss_episodes: int = Field(9999, description="Maximum number of episodes to download from RSS feed", ge=1, le=99999)
    
    # NEW: Transcript detection and YouTube matching
    is_transcript: bool = Field(False, description="Whether the content is a transcript of a video")
    search_youtube: bool = Field(False, description="Whether to search YouTube for matching video (when is_transcript=True)")
    youtube_match_id: Optional[str] = Field(None, description="YouTube video ID if a match was selected")


class ProcessResponse(BaseModel):
    """Immediate response when starting a job."""

    job_id: str
    status: Literal["queued", "starting"] = "queued"
    message: str = "Job queued successfully"
    estimated_duration_seconds: Optional[int] = None
    # NEW: For batch processing
    batch_job_ids: Optional[list[str]] = None  # If multiple jobs created


class BatchProcessResponse(BaseModel):
    """Response for batch processing requests."""
    
    total_items: int
    jobs_created: int
    job_ids: list[str]
    message: str


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
        "cancelled",
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

    # Input info
    input_url: Optional[str] = None
    input_type: Optional[str] = None  # "youtube", "local_file", "pdf_transcript"

    # Results (when complete)
    source_id: Optional[str] = None
    title: Optional[str] = None
    claims_count: Optional[int] = None
    transcript_length: Optional[int] = None
    error: Optional[str] = None

    # Upload status
    uploaded_to_getreceipts: bool = False
    getreceipts_episode_code: Optional[str] = None  # e.g., "EA4G69"
    
    # NEW: Retry support
    retry_count: int = 0
    original_request: Optional[dict] = None  # Store for retry


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


class JobFilterParams(BaseModel):
    """Filter parameters for job listing."""
    
    status: Optional[Literal["all", "active", "completed", "failed"]] = "all"
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    search: Optional[str] = None  # Search by title or URL


# ============================================
# Configuration
# ============================================
class DaemonConfig(BaseModel):
    """Full daemon configuration."""
    
    # API Keys (status only, not actual keys)
    openai_configured: bool = False
    anthropic_configured: bool = False
    google_configured: bool = False
    
    # Processing defaults
    default_whisper_model: Literal["tiny", "base", "small", "medium", "large-v3"] = "medium"
    default_llm_provider: Optional[Literal["openai", "anthropic", "google"]] = None
    default_llm_model: Optional[str] = None
    auto_upload_enabled: bool = True
    process_full_pipeline: bool = True
    
    # Device status
    device_id: Optional[str] = None
    device_linked: bool = False
    
    # Daemon info
    version: str
    uptime_seconds: float


class ConfigUpdateRequest(BaseModel):
    """Request to update daemon configuration."""
    
    # Note: Only "medium" is exposed in web UI, but other models supported for advanced users
    default_whisper_model: Optional[Literal["tiny", "base", "small", "medium", "large-v3"]] = None
    default_llm_provider: Optional[Literal["openai", "anthropic", "google"]] = None
    default_llm_model: Optional[str] = None
    auto_upload_enabled: Optional[bool] = None
    process_full_pipeline: Optional[bool] = None


class APIKeyConfig(BaseModel):
    """API key configuration for cloud LLM providers."""
    
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None


class APIKeyStatus(BaseModel):
    """Status of configured API keys."""
    
    openai_configured: bool
    anthropic_configured: bool
    google_configured: bool


class WhisperModelInfo(BaseModel):
    """Information about a Whisper model."""
    
    name: str
    size_mb: int
    description: str
    installed: bool


class WhisperModelsResponse(BaseModel):
    """List of available Whisper models."""
    
    models: list[WhisperModelInfo]
    current_default: str


# ============================================
# Folder Monitor
# ============================================
class MonitorConfig(BaseModel):
    """Folder monitoring configuration."""
    
    watch_path: Optional[str] = None
    patterns: list[str] = Field(default_factory=lambda: ["*.mp3", "*.mp4", "*.wav", "*.m4a", "*.pdf"])
    recursive: bool = True
    debounce_seconds: int = 5
    auto_process: bool = True
    dry_run: bool = False


class MonitorStatus(BaseModel):
    """Current status of folder monitoring."""
    
    is_watching: bool
    watch_path: Optional[str] = None
    patterns: list[str] = Field(default_factory=list)
    files_detected: int = 0
    files_processed: int = 0
    last_file_detected: Optional[str] = None
    last_detection_time: Optional[datetime] = None
    errors: list[str] = Field(default_factory=list)


class MonitorStartRequest(BaseModel):
    """Request to start folder monitoring."""
    
    watch_path: str
    patterns: Optional[list[str]] = None
    recursive: bool = True
    debounce_seconds: int = 5
    auto_process: bool = True
    dry_run: bool = False


class MonitorEvent(BaseModel):
    """Event from folder monitor."""
    
    event_type: Literal["file_detected", "file_processed", "error"]
    file_path: str
    timestamp: datetime
    job_id: Optional[str] = None  # If auto-processed
    error: Optional[str] = None


class MonitorEventsResponse(BaseModel):
    """Recent monitor events."""
    
    events: list[MonitorEvent]
    total_count: int


# ============================================
# YouTube Matching
# ============================================
class YouTubeSearchRequest(BaseModel):
    """Request to search YouTube for matching videos."""
    
    query: str = Field(..., description="Search query (typically extracted from transcript)")
    max_results: int = Field(10, ge=1, le=50, description="Maximum number of results to return")


class YouTubeMatch(BaseModel):
    """A potential YouTube video match."""
    
    video_id: str
    title: str
    channel_name: str
    channel_id: str
    thumbnail_url: str
    duration_seconds: int
    upload_date: str
    description: Optional[str] = None


class YouTubeSearchResponse(BaseModel):
    """Response containing YouTube search results."""
    
    matches: list[YouTubeMatch]
    query: str


# ============================================
# Manual Metadata Entry
# ============================================
class ManualMetadata(BaseModel):
    """Manually entered metadata for non-YouTube content."""
    
    title: str = Field(..., description="Content title")
    author_name: Optional[str] = Field(None, description="Existing author name")
    author_id: Optional[str] = Field(None, description="Existing author ID")
    new_author_name: Optional[str] = Field(None, description="New author name (if creating)")
    new_author_type: Optional[Literal["individual", "channel", "organization"]] = Field(None, description="New author type")
    new_author_bio: Optional[str] = Field(None, description="New author bio")
    date: Optional[str] = Field(None, description="Publication/recording date (ISO format)")
    description: Optional[str] = Field(None, description="Content description")
    source_url: Optional[str] = Field(None, description="Source URL for attribution")


# ============================================
# Author/Channel Management
# ============================================
class Author(BaseModel):
    """Author or channel information."""
    
    id: str
    name: str
    type: Literal["individual", "channel", "organization"]
    bio: Optional[str] = None
    source_count: int = Field(0, description="Number of episodes/sources from this author")


class AuthorListResponse(BaseModel):
    """List of authors."""
    
    authors: list[Author]
    total: int


class CreateAuthorRequest(BaseModel):
    """Request to create a new author."""
    
    name: str = Field(..., description="Author/channel name")
    type: Literal["individual", "channel", "organization"] = Field(..., description="Author type")
    bio: Optional[str] = Field(None, description="Author biography or description")


class ManualMetadataRequest(BaseModel):
    """Request to process content with manual metadata."""
    
    text_content: str = Field(..., description="Text content to process")
    source_type: Literal["text", "docx", "pdf"] = Field("text", description="Content type")
    metadata: ManualMetadata = Field(..., description="Manual metadata for the content")
    auto_upload: bool = Field(True, description="Whether to auto-upload to GetReceipts")
