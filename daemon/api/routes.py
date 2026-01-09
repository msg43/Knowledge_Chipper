"""
FastAPI Routes

All daemon REST API endpoints.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from daemon import __version__
from daemon.config.settings import settings
from daemon.models.schemas import (
    APIKeyConfig,
    APIKeyStatus,
    Author,
    AuthorListResponse,
    BatchProcessResponse,
    ConfigUpdateRequest,
    CreateAuthorRequest,
    DaemonConfig,
    HealthResponse,
    JobFilterParams,
    JobListResponse,
    JobStatus,
    ManualMetadataRequest,
    MonitorConfig,
    MonitorEventsResponse,
    MonitorStartRequest,
    MonitorStatus,
    ProcessRequest,
    ProcessResponse,
    WhisperModelInfo,
    WhisperModelsResponse,
    YouTubeSearchRequest,
    YouTubeSearchResponse,
)
from daemon.services.processing_service import processing_service
from daemon.services.monitor_service import monitor_service
from daemon.api.database_viewer import database_viewer

# Import playlist detection
try:
    from src.knowledge_system.utils.youtube_utils import is_playlist_url
    PLAYLIST_DETECTION_AVAILABLE = True
except ImportError:
    PLAYLIST_DETECTION_AVAILABLE = False

# Import RSS detection
try:
    from daemon.services.rss_service import rss_service, RSS_SUPPORT_AVAILABLE
except ImportError:
    RSS_SUPPORT_AVAILABLE = False
    rss_service = None

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
    
    Supports:
    - Single YouTube URL (url field)
    - YouTube playlist URLs (auto-expanded to individual videos)
    - RSS/Podcast feed URLs (auto-downloads latest episodes)
    - Multiple YouTube URLs (urls field)
    - Local file paths (local_paths field)
    - PDF transcripts (auto-detected from .pdf extension)
    
    Returns job_id for tracking progress via /jobs/{id} endpoint.
    For batch requests, use /process/batch instead.
    """
    # Check if this is an RSS feed URL
    is_rss = (
        RSS_SUPPORT_AVAILABLE and
        rss_service and
        request.url and
        rss_service.is_rss_url(request.url)
    )
    
    if is_rss:
        # Expand RSS feed and create jobs for latest episodes
        try:
            # Get max episodes from request (default 10)
            max_episodes = getattr(request, 'max_rss_episodes', 9999)
            batch_response = await processing_service.expand_rss_and_process(
                request, 
                max_episodes=max_episodes
            )
            return ProcessResponse(
                job_id=batch_response.job_ids[0] if batch_response.job_ids else "",
                status="queued",
                message=batch_response.message,
                batch_job_ids=batch_response.job_ids,
            )
        except Exception as e:
            logger.exception("Failed to expand RSS feed")
            raise HTTPException(status_code=500, detail=f"RSS feed expansion failed: {str(e)}")
    
    # Check if this is a playlist URL
    is_playlist = (
        PLAYLIST_DETECTION_AVAILABLE and
        request.url and
        is_playlist_url(request.url)
    )
    
    if is_playlist:
        # Expand playlist and create jobs for all videos
        try:
            batch_response = await processing_service.expand_playlist_and_process(request)
            return ProcessResponse(
                job_id=batch_response.job_ids[0] if batch_response.job_ids else "",
                status="queued",
                message=batch_response.message,
                batch_job_ids=batch_response.job_ids,
            )
        except Exception as e:
            logger.exception("Failed to expand playlist")
            raise HTTPException(status_code=500, detail=f"Playlist expansion failed: {str(e)}")
    
    # Check if this is a batch request
    is_batch = (
        (request.urls and len(request.urls) > 0) or
        (request.local_paths and len(request.local_paths) > 0)
    )
    
    if is_batch:
        # For batch, start multiple jobs
        job_ids = await processing_service.start_batch_jobs(request)
        return ProcessResponse(
            job_id=job_ids[0] if job_ids else "",
            status="queued",
            message=f"Started {len(job_ids)} jobs",
            batch_job_ids=job_ids,
        )
    else:
        # Single job
        logger.info(f"Starting processing job for {request.url}")

        try:
            job_id = await processing_service.start_job(request)

            return ProcessResponse(
                job_id=job_id,
                status="queued",
                message="Job queued successfully",
                estimated_duration_seconds=300,
            )

        except Exception as e:
            logger.exception("Failed to start job")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/process/batch", response_model=BatchProcessResponse)
async def start_batch_processing(request: ProcessRequest):
    """
    Start batch processing of multiple sources.
    
    Use urls field for multiple YouTube URLs.
    Use local_paths field for multiple local files.
    """
    try:
        job_ids = await processing_service.start_batch_jobs(request)

        return BatchProcessResponse(
            total_items=len(job_ids),
            jobs_created=len(job_ids),
            job_ids=job_ids,
            message=f"Created {len(job_ids)} processing jobs",
        )

    except Exception as e:
        logger.exception("Failed to start batch jobs")
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
async def list_all_jobs(
    status: Optional[str] = Query("all", description="Filter: all, active, completed, failed"),
    limit: int = Query(50, ge=1, le=500, description="Max jobs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    search: Optional[str] = Query(None, description="Search by title or URL"),
):
    """
    List all processing jobs with optional filtering.
    
    Supports pagination and filtering by status.
    """
    jobs = processing_service.list_jobs(
        status_filter=status or "all",
        limit=limit,
        offset=offset,
        search=search,
    )
    
    counts = processing_service.get_job_counts()

    return JobListResponse(
        total=counts["total"],
        active=counts["active"],
        completed=counts["completed"],
        failed=counts["failed"],
        jobs=jobs,
    )


# ============================================
# Job Actions
# ============================================
@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    """
    Retry a failed job.
    
    Creates a new job with the same parameters.
    Returns the new job_id.
    """
    new_job_id = await processing_service.retry_job(job_id)
    
    if not new_job_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot retry: job not found or not in failed state",
        )
    
    return {
        "status": "retrying",
        "original_job_id": job_id,
        "new_job_id": new_job_id,
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """
    Cancel a running job.
    """
    success = await processing_service.cancel_job(job_id)
    
    if not success:
        job = processing_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=400, detail="Job already finished")

    return {"status": "cancelled", "job_id": job_id}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a job from history.
    
    Only completed, failed, or cancelled jobs can be deleted.
    """
    success = processing_service.delete_job(job_id)
    
    if not success:
        job = processing_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=400, detail="Cannot delete active job")

    return {"status": "deleted", "job_id": job_id}


@router.post("/jobs/bulk/retry")
async def bulk_retry_jobs(job_ids: list[str]):
    """
    Retry multiple failed jobs.
    """
    results = []
    for job_id in job_ids:
        new_job_id = await processing_service.retry_job(job_id)
        results.append({
            "original_job_id": job_id,
            "new_job_id": new_job_id,
            "success": new_job_id is not None,
        })
    
    return {"results": results}


@router.post("/jobs/bulk/delete")
async def bulk_delete_jobs(job_ids: list[str]):
    """
    Delete multiple jobs from history.
    """
    results = []
    for job_id in job_ids:
        success = processing_service.delete_job(job_id)
        results.append({
            "job_id": job_id,
            "success": success,
        })
    
    return {"results": results}


# ============================================
# Configuration
# ============================================
@router.get("/config", response_model=DaemonConfig)
async def get_config():
    """
    Get current daemon configuration.
    """
    return DaemonConfig(
        openai_configured=bool(os.environ.get("OPENAI_API_KEY")),
        anthropic_configured=bool(os.environ.get("ANTHROPIC_API_KEY")),
        google_configured=bool(os.environ.get("GOOGLE_API_KEY")),
        default_whisper_model=settings.default_whisper_model,
        default_llm_provider=settings.default_llm_provider,
        default_llm_model=settings.default_llm_model,
        auto_upload_enabled=settings.auto_upload_enabled,
        process_full_pipeline=settings.process_full_pipeline,
        device_id=settings.get_device_id(),
        device_linked=settings.is_device_linked(),
        version=__version__,
        uptime_seconds=processing_service.get_uptime_seconds(),
    )


@router.patch("/config", response_model=DaemonConfig)
async def update_config(updates: ConfigUpdateRequest):
    """
    Update daemon configuration.
    
    Changes are persisted to disk.
    """
    if updates.default_whisper_model is not None:
        settings.default_whisper_model = updates.default_whisper_model
    if updates.default_llm_provider is not None:
        settings.default_llm_provider = updates.default_llm_provider
    if updates.default_llm_model is not None:
        settings.default_llm_model = updates.default_llm_model
    if updates.auto_upload_enabled is not None:
        settings.auto_upload_enabled = updates.auto_upload_enabled
    if updates.process_full_pipeline is not None:
        settings.process_full_pipeline = updates.process_full_pipeline
    
    # Save to disk
    settings.save_config()
    
    return await get_config()


@router.get("/config/api-keys", response_model=APIKeyStatus)
async def get_api_key_status():
    """
    Check which API keys are configured.
    
    Returns boolean flags for each provider.
    Does not return the actual keys for security.
    """
    return APIKeyStatus(
        openai_configured=bool(os.environ.get("OPENAI_API_KEY")),
        anthropic_configured=bool(os.environ.get("ANTHROPIC_API_KEY")),
        google_configured=bool(os.environ.get("GOOGLE_API_KEY")),
    )


@router.post("/config/api-keys", response_model=APIKeyStatus)
async def set_api_keys(config: APIKeyConfig):
    """
    Set API keys for cloud LLM providers.
    
    Keys are stored persistently in:
    ~/Library/Application Support/Knowledge_Chipper/daemon_config.json
    
    File permissions are set to 600 (owner read/write only) for security.
    Keys are automatically loaded on daemon startup.
    """
    if config.openai_api_key:
        os.environ["OPENAI_API_KEY"] = config.openai_api_key
        logger.info("✅ OpenAI API key configured")
    
    if config.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = config.anthropic_api_key
        logger.info("✅ Anthropic API key configured")
    
    if config.google_api_key:
        os.environ["GOOGLE_API_KEY"] = config.google_api_key
        logger.info("✅ Google API key configured")
    
    # Persist API keys to disk
    settings.save_config()
    logger.info("💾 API keys saved to config file")
    
    return APIKeyStatus(
        openai_configured=bool(config.openai_api_key or os.environ.get("OPENAI_API_KEY")),
        anthropic_configured=bool(config.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")),
        google_configured=bool(config.google_api_key or os.environ.get("GOOGLE_API_KEY")),
    )


class ModelAccessTest(BaseModel):
    provider: str
    model: str


class ModelAccessTestResult(BaseModel):
    success: bool
    accessible: bool
    error_message: Optional[str] = None
    details: Optional[str] = None


@router.post("/config/test-model-access", response_model=ModelAccessTestResult)
async def test_model_access(test: ModelAccessTest):
    """
    Test whether a specific model is accessible with the current API key.
    
    Makes a minimal API call (single token) to validate:
    - API key is valid
    - Model exists
    - User has access to the model
    
    Returns:
    - success: Whether the API call completed without network errors
    - accessible: Whether the model is accessible (true if call succeeded)
    - error_message: User-friendly error message if not accessible
    - details: Technical details about the error
    """
    try:
        from src.knowledge_system.core.llm_adapter import LLMAdapter
        
        # Check if API key is configured
        key_env_var = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
        }.get(test.provider)
        
        if not key_env_var or not os.environ.get(key_env_var):
            return ModelAccessTestResult(
                success=True,
                accessible=False,
                error_message=f"No API key configured for {test.provider}",
                details="Please configure your API key in Settings before testing model access.",
            )
        
        # Create adapter and make minimal test call
        adapter = LLMAdapter()
        
        # Minimal test message
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        
        # Attempt the call with minimal tokens
        response = await adapter.complete(
            provider=test.provider,
            model=test.model,
            messages=messages,
            temperature=0,
            max_tokens=1,  # Request only 1 token to minimize cost
        )
        
        # If we got here, the model is accessible
        return ModelAccessTestResult(
            success=True,
            accessible=True,
            error_message=None,
            details=f"Model '{test.model}' is accessible. Test call completed successfully.",
        )
    
    except Exception as e:
        error_msg = str(e).lower()
        
        # Parse error type and provide actionable feedback
        if any(x in error_msg for x in ["403", "permission", "access denied", "not authorized", "forbidden"]):
            return ModelAccessTestResult(
                success=True,
                accessible=False,
                error_message=f"Access Denied",
                details=(
                    f"You don't have access to '{test.model}' on {test.provider}. "
                    f"This model may require a higher usage tier, special approval, or specific subscription plan."
                ),
            )
        
        elif any(x in error_msg for x in ["404", "not found", "does not exist", "invalid model"]):
            return ModelAccessTestResult(
                success=True,
                accessible=False,
                error_message="Model Not Found",
                details=(
                    f"Model '{test.model}' is not available on {test.provider}. "
                    f"It may have been deprecated, renamed, or not yet released in your region."
                ),
            )
        
        elif any(x in error_msg for x in ["401", "unauthorized", "invalid api key", "authentication"]):
            return ModelAccessTestResult(
                success=True,
                accessible=False,
                error_message="Authentication Failed",
                details=f"Your {test.provider} API key is invalid or expired. Please update it in Settings.",
            )
        
        elif any(x in error_msg for x in ["rate", "429"]):
            return ModelAccessTestResult(
                success=True,
                accessible=False,
                error_message="Rate Limit Exceeded",
                details="You've hit the rate limit. Please wait a moment and try again.",
            )
        
        else:
            # Unknown error
            return ModelAccessTestResult(
                success=True,
                accessible=False,
                error_message="Test Failed",
                details=f"Unable to test model access: {str(e)}",
            )


@router.get("/config/whisper-models", response_model=WhisperModelsResponse)
async def get_whisper_models():
    """
    List available Whisper models with installation status.
    
    NOTE: For web UI simplicity, only the 'medium' model is exposed.
    This provides the best balance of accuracy, speed, and memory usage
    (70-80% fewer hallucinations than large, better quality than base).
    Advanced users can still use other models via API if needed.
    """
    # Only expose medium model in web UI to reduce complexity
    models = [
        WhisperModelInfo(
            name="medium",
            size_mb=1500,
            description="Best balance of speed, accuracy, and memory usage. Recommended for all use cases.",
            installed=True,
        ),
    ]
    
    return WhisperModelsResponse(
        models=models,
        current_default=settings.default_whisper_model,
    )


@router.get("/config/models")
async def get_available_models(
    provider: Optional[str] = Query(None, description="Filter by provider (openai, anthropic, google, local)"),
    force_refresh: bool = Query(False, description="Force refresh from APIs"),
    include_metadata: bool = Query(True, description="Include access metadata for models"),
):
    """
    Get available LLM models for all providers or a specific provider.
    
    Returns dynamically fetched models from OpenAI and Google APIs,
    with hardcoded fallbacks for Anthropic (no public API).
    
    Models are cached and only refreshed when force_refresh=true.
    
    When include_metadata=true, each model includes:
    - status: public, gated, experimental, deprecated, or tier_restricted
    - tier_required: Minimum usage tier (if applicable)
    - note: Human-readable access requirements
    - display_name: Formatted model name
    """
    try:
        from src.knowledge_system.utils.model_registry import get_provider_models
        from src.knowledge_system.utils.model_metadata import get_model_metadata, get_status_badge, get_status_label
        
        def enrich_with_metadata(provider: str, model_ids: list[str]) -> list[dict]:
            """Add metadata to each model."""
            if not include_metadata:
                return [{"id": m} for m in model_ids]
            
            enriched = []
            for model_id in model_ids:
                metadata = get_model_metadata(provider, model_id)
                enriched.append({
                    "id": model_id,
                    "display_name": metadata.display_name,
                    "status": metadata.status.value,
                    "status_badge": get_status_badge(metadata.status),
                    "status_label": get_status_label(metadata.status),
                    "tier_required": metadata.tier_required,
                    "note": metadata.note,
                })
            return enriched
        
        if provider:
            # Return models for specific provider
            model_ids = get_provider_models(provider, force_refresh=force_refresh)
            models_with_metadata = enrich_with_metadata(provider, model_ids)
            
            return {
                "provider": provider,
                "models": models_with_metadata,
                "count": len(models_with_metadata),
            }
        else:
            # Return models for all providers
            providers = ["openai", "anthropic", "google", "local"]
            all_models = {}
            for p in providers:
                model_ids = get_provider_models(p, force_refresh=force_refresh)
                all_models[p] = enrich_with_metadata(p, model_ids)
            
            return {
                "providers": all_models,
                "counts": {p: len(models) for p, models in all_models.items()},
            }
    
    except Exception as e:
        logger.exception("Failed to fetch models")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/device-status")
async def get_device_status():
    """
    Get device linking status.
    """
    return {
        "device_id": settings.get_device_id(),
        "is_linked": settings.is_device_linked(),
    }


# ============================================
# Folder Monitor
# ============================================
@router.get("/monitor/status", response_model=MonitorStatus)
async def get_monitor_status():
    """
    Get current folder monitoring status.
    """
    return monitor_service.get_status()


@router.get("/monitor/config", response_model=MonitorConfig)
async def get_monitor_config():
    """
    Get current folder monitoring configuration.
    """
    return monitor_service.get_config()


@router.patch("/monitor/config", response_model=MonitorConfig)
async def update_monitor_config(config: MonitorConfig):
    """
    Update folder monitoring configuration.
    
    Requires monitor to be stopped first.
    """
    try:
        return monitor_service.update_config(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/monitor/start", response_model=MonitorStatus)
async def start_monitoring(request: MonitorStartRequest):
    """
    Start folder monitoring.
    
    Watches the specified folder for new audio/video files.
    Auto-processes them if enabled.
    """
    try:
        # Set up processing callback
        async def process_callback(req: ProcessRequest) -> str:
            return await processing_service.start_job(req)
        
        monitor_service.set_processing_callback(process_callback)
        
        return await monitor_service.start(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to start monitoring")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor/stop", response_model=MonitorStatus)
async def stop_monitoring():
    """
    Stop folder monitoring.
    """
    return await monitor_service.stop()


@router.get("/monitor/events", response_model=MonitorEventsResponse)
async def get_monitor_events(
    limit: int = Query(50, ge=1, le=200, description="Max events to return"),
):
    """
    Get recent monitoring events.
    """
    events = monitor_service.get_events(limit=limit)
    return MonitorEventsResponse(
        events=events,
        total_count=len(events),
    )


@router.delete("/monitor/events")
async def clear_monitor_events():
    """
    Clear monitoring event history.
    """
    monitor_service.clear_events()
    return {"status": "cleared"}


@router.get("/monitor/browse")
async def browse_folders(
    path: Optional[str] = Query(None, description="Starting path. Defaults to home."),
):
    """
    Browse folders for monitoring selection.
    
    Returns list of subdirectories at the given path.
    """
    dirs = monitor_service.browse_folder(path)
    return {
        "current_path": path or str(os.path.expanduser("~")),
        "directories": dirs,
    }


# ============================================
# Database Admin Viewer
# ============================================
@router.get("/admin/database", response_class=HTMLResponse)
async def database_admin_page():
    """
    Admin page for viewing local SQLite database.
    
    Non-public, localhost-only page showing database contents.
    Sorted by most recent records first with "Load More" functionality.
    """
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Database Viewer - Knowledge Chipper</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            padding: 20px;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            background: #2a2a2a;
            padding: 20px 30px;
            border-radius: 8px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        h1 {
            font-size: 24px;
            font-weight: 600;
            color: #fff;
        }
        
        .header-info {
            display: flex;
            gap: 20px;
            font-size: 14px;
            color: #888;
        }
        
        .refresh-btn {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.2s;
        }
        
        .refresh-btn:hover {
            background: #45a049;
        }
        
        .refresh-btn:active {
            background: #3d8b40;
        }
        
        .db-summary {
            background: #2a2a2a;
            padding: 20px 30px;
            border-radius: 8px;
            margin-bottom: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        
        .db-stat {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .db-stat-label {
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .db-stat-value {
            font-size: 18px;
            font-weight: 600;
            color: #fff;
        }
        
        .table-section {
            background: #2a2a2a;
            border-radius: 8px;
            margin-bottom: 30px;
            overflow: hidden;
        }
        
        .table-header {
            background: #333;
            padding: 15px 30px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #444;
        }
        
        .table-header:hover {
            background: #383838;
        }
        
        .table-title {
            font-size: 16px;
            font-weight: 600;
            color: #fff;
        }
        
        .table-meta {
            font-size: 14px;
            color: #888;
        }
        
        .table-content {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }
        
        .table-content.expanded {
            max-height: 10000px;
        }
        
        .table-wrapper {
            overflow-x: auto;
            padding: 20px 30px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        
        th {
            background: #333;
            color: #fff;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 10;
            white-space: nowrap;
        }
        
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #333;
            max-width: 400px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        tr:hover td {
            background: #2f2f2f;
        }
        
        .load-more-container {
            padding: 20px 30px;
            text-align: center;
            border-top: 1px solid #333;
        }
        
        .load-more-btn {
            background: #2196F3;
            color: white;
            border: none;
            padding: 10px 30px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.2s;
        }
        
        .load-more-btn:hover {
            background: #1976D2;
        }
        
        .load-more-btn:disabled {
            background: #555;
            cursor: not-allowed;
            opacity: 0.6;
        }
        
        .loading {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid #fff;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 1s linear infinite;
            margin-left: 10px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .error {
            background: #d32f2f;
            color: white;
            padding: 15px 30px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        
        .empty-state {
            padding: 40px;
            text-align: center;
            color: #888;
        }
        
        .chevron {
            transition: transform 0.3s;
            color: #888;
        }
        
        .chevron.expanded {
            transform: rotate(180deg);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>📊 Database Viewer</h1>
            </div>
            <div class="header-info">
                <div>Last Refreshed: <span id="last-refresh">Loading...</span></div>
                <button class="refresh-btn" onclick="refreshAll()">🔄 Manual Refresh</button>
            </div>
        </header>
        
        <div id="db-summary" class="db-summary">
            <!-- Database summary will be inserted here -->
        </div>
        
        <div id="error-container"></div>
        
        <div id="tables-container">
            <!-- Tables will be inserted here -->
        </div>
    </div>

    <script>
        let dbSummary = null;
        let tableStates = {}; // Track offset for each table
        
        async function fetchDatabaseSummary() {
            try {
                const response = await fetch('/api/admin/database/summary');
                dbSummary = await response.json();
                updateLastRefresh();
                renderDatabaseSummary();
            } catch (error) {
                showError('Failed to load database summary: ' + error.message);
            }
        }
        
        function renderDatabaseSummary() {
            const container = document.getElementById('db-summary');
            container.innerHTML = `
                <div class="db-stat">
                    <div class="db-stat-label">Database Size</div>
                    <div class="db-stat-value">${dbSummary.database_size_mb} MB</div>
                </div>
                <div class="db-stat">
                    <div class="db-stat-label">Total Tables</div>
                    <div class="db-stat-value">${dbSummary.table_count}</div>
                </div>
                <div class="db-stat">
                    <div class="db-stat-label">Database Path</div>
                    <div class="db-stat-value" style="font-size: 12px; word-break: break-all;">${dbSummary.database_path}</div>
                </div>
                <div class="db-stat">
                    <div class="db-stat-label">Last Modified</div>
                    <div class="db-stat-value" style="font-size: 14px;">${dbSummary.last_modified}</div>
                </div>
            `;
        }
        
        async function loadAllTables() {
            if (!dbSummary) await fetchDatabaseSummary();
            
            const container = document.getElementById('tables-container');
            container.innerHTML = '';
            
            // Initialize state for each table
            for (const table of dbSummary.tables) {
                tableStates[table.name] = { offset: 0, hasMore: true };
                await renderTable(table.name, true);
            }
        }
        
        async function renderTable(tableName, isInitial = false) {
            const state = tableStates[tableName];
            
            try {
                const response = await fetch(
                    `/api/admin/database/table/${tableName}?limit=100&offset=${state.offset}`
                );
                const data = await response.json();
                
                if (isInitial) {
                    createTableSection(tableName, data);
                } else {
                    appendTableRecords(tableName, data);
                }
                
                // Update state
                state.hasMore = data.has_more;
                
            } catch (error) {
                showError(`Failed to load table ${tableName}: ` + error.message);
            }
        }
        
        function createTableSection(tableName, data) {
            const container = document.getElementById('tables-container');
            
            const section = document.createElement('div');
            section.className = 'table-section';
            section.id = `table-${tableName}`;
            
            section.innerHTML = `
                <div class="table-header" onclick="toggleTable('${tableName}')">
                    <div>
                        <div class="table-title">${tableName}</div>
                        <div class="table-meta">${data.total_count} records • ${data.columns.length} columns</div>
                    </div>
                    <div class="chevron" id="chevron-${tableName}">▼</div>
                </div>
                <div class="table-content" id="content-${tableName}">
                    <div class="table-wrapper">
                        <table id="data-${tableName}">
                            <thead>
                                <tr>
                                    ${data.columns.map(col => `<th>${col}</th>`).join('')}
                                </tr>
                            </thead>
                            <tbody id="tbody-${tableName}">
                                ${renderTableRows(data.records, data.columns)}
                            </tbody>
                        </table>
                    </div>
                    ${data.has_more ? `
                        <div class="load-more-container">
                            <button class="load-more-btn" id="load-more-${tableName}" 
                                    onclick="loadMoreRecords('${tableName}')">
                                Load More (100 records)
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
            
            container.appendChild(section);
        }
        
        function renderTableRows(records, columns) {
            if (records.length === 0) {
                return '<tr><td colspan="100" class="empty-state">No records found</td></tr>';
            }
            
            return records.map(record => `
                <tr>
                    ${columns.map(col => {
                        const value = record[col];
                        const displayValue = value === null ? '<em style="color: #666;">null</em>' : 
                                           value === '' ? '<em style="color: #666;">empty</em>' :
                                           String(value);
                        return `<td title="${String(value)}">${displayValue}</td>`;
                    }).join('')}
                </tr>
            `).join('');
        }
        
        async function loadMoreRecords(tableName) {
            const button = document.getElementById(`load-more-${tableName}`);
            button.disabled = true;
            button.innerHTML = 'Loading<span class="loading"></span>';
            
            const state = tableStates[tableName];
            state.offset += 100;
            
            await renderTable(tableName, false);
            
            button.disabled = false;
            button.innerHTML = 'Load More (100 records)';
            
            // Remove button if no more records
            if (!state.hasMore) {
                button.parentElement.remove();
            }
        }
        
        function appendTableRecords(tableName, data) {
            const tbody = document.getElementById(`tbody-${tableName}`);
            const rows = renderTableRows(data.records, data.columns);
            tbody.insertAdjacentHTML('beforeend', rows);
        }
        
        function toggleTable(tableName) {
            const content = document.getElementById(`content-${tableName}`);
            const chevron = document.getElementById(`chevron-${tableName}`);
            
            content.classList.toggle('expanded');
            chevron.classList.toggle('expanded');
        }
        
        function updateLastRefresh() {
            const now = new Date().toLocaleString();
            document.getElementById('last-refresh').textContent = now;
        }
        
        function showError(message) {
            const container = document.getElementById('error-container');
            container.innerHTML = `<div class="error">⚠️ ${message}</div>`;
            setTimeout(() => { container.innerHTML = ''; }, 5000);
        }
        
        async function refreshAll() {
            tableStates = {};
            await loadAllTables();
        }
        
        // Initial load
        loadAllTables();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html)


@router.get("/admin/database/summary")
async def get_database_summary():
    """
    Get database summary (table counts, size, etc.).
    """
    try:
        return database_viewer.get_database_summary()
    except Exception as e:
        logger.exception("Failed to get database summary")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/database/table/{table_name}")
async def get_table_data(
    table_name: str,
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Get records from a specific table with pagination.
    
    Sorted by most recent (created_at/updated_at/etc) first.
    """
    try:
        return database_viewer.get_records(table_name, limit=limit, offset=offset)
    except Exception as e:
        logger.exception(f"Failed to get records from {table_name}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# YouTube Matching
# ============================================
@router.post("/youtube/search", response_model=YouTubeSearchResponse)
async def search_youtube_matches(request: YouTubeSearchRequest):
    """
    Search YouTube for videos matching a query (typically from transcript content).
    
    Uses YouTube Data API (requires YOUTUBE_API_KEY environment variable).
    """
    try:
        from daemon.services.youtube_matcher import get_youtube_matcher
        
        matcher = get_youtube_matcher()
        if not matcher:
            raise HTTPException(
                status_code=503, 
                detail="YouTube matching not available. Check YOUTUBE_API_KEY configuration."
            )
        
        return matcher.search_youtube(request)
    
    except Exception as e:
        logger.exception("YouTube search failed")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Author Management
# ============================================
@router.get("/authors", response_model=AuthorListResponse)
async def get_authors(
    search: Optional[str] = Query(None, description="Search query to filter authors"),
    limit: int = Query(100, ge=1, le=500, description="Max authors to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Get list of authors/channels from database.
    
    Authors are extracted from uploaded content metadata.
    """
    try:
        from daemon.services.author_service import author_service
        
        if not author_service:
            raise HTTPException(
                status_code=503,
                detail="Author service not available"
            )
        
        return author_service.get_authors(search=search, limit=limit, offset=offset)
    
    except Exception as e:
        logger.exception("Failed to get authors")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/authors", response_model=Author)
async def create_author(request: CreateAuthorRequest):
    """
    Create a new author/channel for manual metadata entry.
    """
    try:
        from daemon.services.author_service import author_service
        
        if not author_service:
            raise HTTPException(
                status_code=503,
                detail="Author service not available"
            )
        
        return author_service.create_author(request)
    
    except Exception as e:
        logger.exception("Failed to create author")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Manual Metadata Processing
# ============================================
@router.post("/process/manual-metadata", response_model=ProcessResponse)
async def process_with_manual_metadata(request: ManualMetadataRequest):
    """
    Process content with manually entered metadata.
    
    Used when content doesn't have automatic metadata (non-YouTube sources).
    """
    try:
        # Create a ProcessRequest with the provided metadata
        process_request = ProcessRequest(
            text_content=request.text_content,
            source_type=request.source_type,
            transcribe=False,  # Already have text
            extract_claims=True,
            auto_upload=request.auto_upload,
            process_full_pipeline=True,
        )
        
        # Start the job
        job_id = await processing_service.start_job(process_request)
        
        # Store manual metadata with the job for later use in upload
        job = processing_service.jobs.get(job_id)
        if job and job.original_request:
            job.original_request['manual_metadata'] = request.metadata.model_dump()
        
        return ProcessResponse(
            job_id=job_id,
            status="queued",
            message="Processing with manual metadata",
        )
    
    except Exception as e:
        logger.exception("Failed to process with manual metadata")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Device Linking (Auto-link on Installation)
# ============================================
@router.post("/config/link-device")
async def link_device_with_token(token: str = Query(..., description="Link token from download URL")):
    """
    Auto-link device using token from download URL.
    
    Flow:
    1. User downloads .pkg while signed in (token embedded in URL)
    2. Installer/first-run extracts token from URL
    3. Daemon calls this endpoint with token
    4. Daemon verifies token with GetReceipts API
    5. Device credentials are updated with user_id
    
    This enables zero-friction device linking without manual claim codes.
    """
    import json
    import requests
    from pathlib import Path
    
    try:
        # Verify token with GetReceipts API
        verify_url = f"{settings.getreceipts_api_url.rstrip('/api')}/api/download/generate-link-token"
        params = {"token": token}
        
        logger.info(f"Verifying link token with GetReceipts API: {verify_url}")
        
        response = requests.get(verify_url, params=params, timeout=10)
        
        if response.status_code != 200:
            error_detail = response.json().get('error', 'Unknown error')
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid or expired link token: {error_detail}"
            )
        
        data = response.json()
        if not data.get('valid'):
            raise HTTPException(status_code=400, detail="Token is not valid")
        
        user_id = data.get('user_id')
        if not user_id:
            raise HTTPException(status_code=500, detail="Token validation succeeded but no user_id returned")
        
        # Load or create device credentials
        creds_path = Path(settings.device_credentials_path)
        creds_path.parent.mkdir(parents=True, exist_ok=True)
        
        if creds_path.exists():
            # Update existing credentials with user_id
            creds = json.loads(creds_path.read_text())
            creds['user_id'] = user_id
            creds['linked_at'] = data.get('used_at', str(os.popen('date -u +"%Y-%m-%dT%H:%M:%SZ"').read().strip()))
        else:
            # Create new device credentials
            import secrets
            creds = {
                'device_id': secrets.token_urlsafe(16),
                'device_key': secrets.token_urlsafe(32),
                'user_id': user_id,
                'linked_at': data.get('used_at', str(os.popen('date -u +"%Y-%m-%dT%H:%M:%SZ"').read().strip()))
            }
        
        # Save updated credentials
        creds_path.write_text(json.dumps(creds, indent=2))
        creds_path.chmod(0o600)  # Secure permissions
        
        logger.info(f"✅ Device auto-linked to user {user_id[:8]}... via download token")
        
        return {
            "success": True,
            "message": "Device successfully linked to your account",
            "device_id": creds['device_id'],
            "user_id": user_id
        }
    
    except requests.RequestException as e:
        logger.error(f"Failed to verify link token with GetReceipts API: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Unable to connect to GetReceipts API for token verification"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Device linking failed")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Auto-Update System
# ============================================
@router.get("/updates/check")
async def check_for_updates():
    """
    Check if daemon updates are available.
    
    Queries GitHub releases API to check for newer daemon versions.
    Returns update status and version information.
    """
    from daemon.services.update_checker import get_update_checker
    
    checker = get_update_checker(__version__)
    has_update, latest_version = await checker.check_for_updates()
    
    return {
        "update_available": has_update,
        "current_version": checker.current_version,
        "latest_version": latest_version,
        "last_checked": checker.last_check.isoformat() if checker.last_check else None
    }


@router.post("/updates/install")
async def install_update():
    """
    Manually trigger daemon update installation.
    
    Downloads and installs the latest daemon version if available.
    The daemon will automatically restart via LaunchAgent after installation.
    """
    import asyncio
    from daemon.services.update_checker import get_update_checker
    
    checker = get_update_checker(__version__)
    
    # Check if update is available
    has_update, latest_version = await checker.check_for_updates()
    
    if not has_update:
        return {
            "status": "no_update",
            "message": f"Already on latest version ({checker.current_version})",
            "current_version": checker.current_version
        }
    
    # Install the update
    logger.info(f"Manual update triggered: {checker.current_version} → {latest_version}")
    success = await checker.download_and_install_update()
    
    if success:
        # Schedule daemon restart in 3 seconds
        async def delayed_restart():
            await asyncio.sleep(3)
            logger.info("Exiting for update restart...")
            os._exit(0)  # LaunchAgent will restart us
        
        asyncio.create_task(delayed_restart())
        
        return {
            "status": "success",
            "message": f"Update to version {latest_version} installed - daemon will restart in 3 seconds",
            "new_version": latest_version,
            "restart_in_seconds": 3
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Update installation failed - check daemon logs for details"
        )


@router.get("/updates/status")
async def update_status():
    """
    Get current update status and settings.
    
    Returns information about auto-update configuration and current state.
    """
    from daemon.services.update_checker import get_update_checker
    
    checker = get_update_checker(__version__)
    
    return {
        "auto_update_enabled": True,  # Always enabled for daemon
        "check_interval_hours": 24,
        "current_version": checker.current_version,
        "last_check": checker.last_check.isoformat() if checker.last_check else None,
        "update_available": checker.update_available,
        "latest_version": checker.latest_version
    }
