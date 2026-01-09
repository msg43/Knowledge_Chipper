"""
FastAPI Application Factory

Separates app creation from execution for PyInstaller compatibility.
This prevents circular imports and allows uvicorn.run(app) to work correctly.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from daemon import __version__
from daemon.api.routes import router
from daemon.config.settings import settings

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
    
    # Check for auto-linking token from installation
    try:
        from daemon.services.link_token_handler import get_link_token_handler
        handler = get_link_token_handler()
        # Don't block startup - run in background
        import asyncio
        asyncio.create_task(asyncio.to_thread(handler.check_and_link))
    except Exception as e:
        logger.warning(f"Link token check failed (non-critical): {e}")
    
    # Start auto-update scheduler
    update_scheduler = None
    try:
        from daemon.services.update_checker import get_update_scheduler
        update_scheduler = get_update_scheduler(__version__)
        await update_scheduler.start()
        logger.info("Auto-update system enabled (checks every 24 hours)")
    except Exception as e:
        logger.warning(f"Auto-update scheduler failed to start (non-critical): {e}")
    
    yield  # Application runs
    
    # Shutdown
    if update_scheduler:
        await update_scheduler.stop()
        logger.info("Auto-update scheduler stopped")
    
    logger.info("Daemon shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    This factory pattern is required for PyInstaller compatibility.
    """
    app = FastAPI(
        title="Knowledge_Chipper Daemon",
        version=__version__,
        description="Local processing daemon for GetReceipts.org",
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

    return app


# Create the app instance globally
# This allows direct import: from daemon.app_factory import app
app = create_app()

