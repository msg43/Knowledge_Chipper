"""
Folder Monitor Service

Wraps existing FileWatcher for API access.
Allows web UI to configure and control folder watching.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from daemon.models.schemas import (
    MonitorConfig,
    MonitorEvent,
    MonitorStartRequest,
    MonitorStatus,
    ProcessRequest,
)
from daemon.config.settings import settings

logger = logging.getLogger(__name__)


class MonitorService:
    """
    Service for folder monitoring.
    
    Wraps the existing FileWatcher class and exposes it via API.
    """

    def __init__(self):
        self._watcher = None
        self._is_watching = False
        self._config = MonitorConfig()
        self._events: list[MonitorEvent] = []
        self._max_events = 100
        self._files_detected = 0
        self._files_processed = 0
        self._last_file: Optional[str] = None
        self._last_detection: Optional[datetime] = None
        self._errors: list[str] = []
        self._processing_callback: Optional[Callable] = None

    def set_processing_callback(self, callback: Callable):
        """Set callback for auto-processing detected files."""
        self._processing_callback = callback

    def get_status(self) -> MonitorStatus:
        """Get current monitor status."""
        return MonitorStatus(
            is_watching=self._is_watching,
            watch_path=self._config.watch_path,
            patterns=self._config.patterns,
            files_detected=self._files_detected,
            files_processed=self._files_processed,
            last_file_detected=self._last_file,
            last_detection_time=self._last_detection,
            errors=self._errors[-10:],  # Last 10 errors
        )

    def get_config(self) -> MonitorConfig:
        """Get current configuration."""
        return self._config

    def update_config(self, config: MonitorConfig) -> MonitorConfig:
        """Update configuration. Requires restart if already watching."""
        if self._is_watching:
            raise ValueError("Cannot update config while watching. Stop first.")
        self._config = config
        return self._config

    async def start(self, request: MonitorStartRequest) -> MonitorStatus:
        """Start folder monitoring."""
        if self._is_watching:
            raise ValueError("Already watching. Stop first.")

        # Validate path
        watch_path = Path(request.watch_path)
        if not watch_path.exists():
            raise ValueError(f"Path does not exist: {request.watch_path}")
        if not watch_path.is_dir():
            raise ValueError(f"Path is not a directory: {request.watch_path}")

        # Update config
        self._config = MonitorConfig(
            watch_path=request.watch_path,
            patterns=request.patterns or self._config.patterns,
            recursive=request.recursive,
            debounce_seconds=request.debounce_seconds,
            auto_process=request.auto_process,
            dry_run=request.dry_run,
        )

        # Import and create FileWatcher
        try:
            from src.knowledge_system.watchers import FileWatcher

            def file_callback(file_path: Path):
                """Handle detected file."""
                asyncio.create_task(self._on_file_detected(file_path))

            self._watcher = FileWatcher(
                directory=watch_path,
                patterns=self._config.patterns,
                callback=file_callback,
                debounce=self._config.debounce_seconds,
                recursive=self._config.recursive,
            )

            self._watcher.start()
            self._is_watching = True
            self._errors = []

            logger.info(f"Started watching: {request.watch_path}")
            self._add_event("file_detected", str(watch_path), job_id=None)

            return self.get_status()

        except Exception as e:
            logger.exception("Failed to start watcher")
            self._errors.append(str(e))
            raise

    async def stop(self) -> MonitorStatus:
        """Stop folder monitoring."""
        if not self._is_watching:
            return self.get_status()

        if self._watcher:
            try:
                self._watcher.stop()
            except Exception as e:
                logger.warning(f"Error stopping watcher: {e}")

        self._watcher = None
        self._is_watching = False
        logger.info("Stopped watching")

        return self.get_status()

    async def _on_file_detected(self, file_path: Path):
        """Handle a detected file."""
        self._files_detected += 1
        self._last_file = str(file_path)
        self._last_detection = datetime.now(timezone.utc)

        logger.info(f"File detected: {file_path}")

        # Add event
        event = self._add_event("file_detected", str(file_path))

        # Auto-process if enabled
        if self._config.auto_process and not self._config.dry_run:
            try:
                job_id = await self._process_file(file_path)
                if job_id:
                    event.job_id = job_id
                    self._files_processed += 1
                    self._add_event("file_processed", str(file_path), job_id=job_id)
            except Exception as e:
                error_msg = f"Failed to process {file_path}: {e}"
                logger.error(error_msg)
                self._errors.append(error_msg)
                self._add_event("error", str(file_path), error=str(e))

    async def _process_file(self, file_path: Path) -> Optional[str]:
        """Process a detected file."""
        if not self._processing_callback:
            logger.warning("No processing callback set")
            return None

        # Determine source type from extension
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            source_type = "pdf_transcript"
        elif ext in [".mp3", ".mp4", ".wav", ".m4a", ".webm", ".ogg", ".flac"]:
            source_type = "local_file"
        else:
            logger.info(f"Skipping unsupported file type: {ext}")
            return None

        # Create process request
        request = ProcessRequest(
            url=str(file_path),
            source_type=source_type,
            transcribe=True,
            extract_claims=True,
            auto_upload=settings.auto_upload_enabled,
            whisper_model=settings.default_whisper_model,
            llm_provider=settings.default_llm_provider,
            llm_model=settings.default_llm_model,
        )

        # Call processing callback
        return await self._processing_callback(request)

    def _add_event(
        self,
        event_type: str,
        file_path: str,
        job_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> MonitorEvent:
        """Add an event to the history."""
        event = MonitorEvent(
            event_type=event_type,
            file_path=file_path,
            timestamp=datetime.now(timezone.utc),
            job_id=job_id,
            error=error,
        )
        self._events.append(event)

        # Trim old events
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        return event

    def get_events(self, limit: int = 50) -> list[MonitorEvent]:
        """Get recent events."""
        return self._events[-limit:]

    def clear_events(self):
        """Clear event history."""
        self._events = []

    def browse_folder(self, start_path: Optional[str] = None) -> list[str]:
        """
        List directories for folder browsing.
        
        Args:
            start_path: Starting directory. Defaults to home.
        
        Returns:
            List of directory paths.
        """
        if start_path:
            base = Path(start_path)
        else:
            base = Path.home()

        if not base.exists():
            return []

        dirs = []
        try:
            for item in base.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    dirs.append(str(item))
        except PermissionError:
            pass

        return sorted(dirs)


# Global service instance
monitor_service = MonitorService()

