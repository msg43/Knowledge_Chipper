"""
Knowledge_Chipper Daemon

FastAPI server that exposes processing capabilities via REST API.
Designed to work with GetReceipts.org website as the primary UI.

Usage:
    # Development
    python -m daemon.main
    
    # Or with uvicorn directly
    uvicorn daemon.main:app --host 127.0.0.1 --port 8765
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from daemon import __version__
from daemon.api.routes import router
from daemon.config.settings import settings

# Setup logging
log_dir = Path(settings.log_file).parent if settings.log_file else None
if log_dir:
    log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.log_file)
        if settings.log_file
        else logging.NullHandler(),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("=" * 60)
    logger.info(f"Knowledge_Chipper Daemon v{__version__} starting...")
    logger.info(f"Server: http://{settings.host}:{settings.port}")
    logger.info(f"Swagger UI: http://{settings.host}:{settings.port}/docs")
    logger.info(f"CORS enabled for: {settings.cors_origins}")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("Knowledge_Chipper Daemon shutting down")


# Create FastAPI app
app = FastAPI(
    title="Knowledge_Chipper Daemon",
    description="""
Local processing daemon for extracting claims from audio/video.

## Architecture
- **Website (GetReceipts.org)** = Primary UI
- **Daemon (localhost:8765)** = Local processing

All heavy lifting (Whisper, LLM, yt-dlp) happens locally on your Mac.

## Endpoints
- `GET /api/health` - Check if daemon is running
- `POST /api/process` - Start processing a video
- `GET /api/jobs/{id}` - Check job progress
- `GET /api/jobs` - List all jobs
    """,
    version=__version__,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    lifespan=lifespan,
)


# CORS middleware - allow GetReceipts.org to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routes
app.include_router(router, prefix="/api")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Knowledge_Chipper Daemon",
        "version": __version__,
        "status": "running",
        "docs": "/docs",
        "api": "/api",
        "health": "/api/health",
    }


def main():
    """Entry point for running the daemon."""
    import uvicorn

    uvicorn.run(
        "daemon.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
