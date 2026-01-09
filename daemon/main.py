"""
Knowledge_Chipper Daemon - Entry Point

Decoupled entry point for PyInstaller compatibility.
App definition is in app_factory.py to prevent circular imports.

Usage:
    # Development
    python -m daemon.main
    
    # Production (PyInstaller bundle)
    ./GetReceiptsDaemon
"""

import logging
import multiprocessing
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn

from daemon.app_factory import app  # Import the app instance
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


def main():
    """
    Entry point for running the daemon.
    
    Uses the Decoupled Entry Point pattern for PyInstaller compatibility:
    - App is defined in app_factory.py (not here)
    - multiprocessing.freeze_support() for macOS/Windows
    - Pass app object directly to uvicorn.run()
    - Force reload=False and workers=1
    """
    # CRITICAL: Required for PyInstaller on macOS/Windows
    multiprocessing.freeze_support()
    
    logger.info("Starting Knowledge_Chipper Daemon...")
    
    # Run Uvicorn with the app OBJECT (not string path)
    # This works in PyInstaller because we're not doing string-based imports
    uvicorn.run(
        app,  # Pass the object directly
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,   # MUST be False for PyInstaller
        workers=1,      # MUST be 1 for PyInstaller
        factory=False,  # We're passing instance, not factory
    )


if __name__ == "__main__":
    main()
