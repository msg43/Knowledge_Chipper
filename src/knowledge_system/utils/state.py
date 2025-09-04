"""
DEPRECATED: JSON-based State Management

⚠️ This module is deprecated and replaced by SQLite-based state management.

MIGRATION NOTICE:
- Use `DatabaseService` from `..database.service` for operational data
- Use `ProgressTracker` from `..utils.progress_tracker` for job tracking
- Use the new SQLite-based architecture for all state management

This file is maintained for backward compatibility but will be removed in a future version.
"""

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, validator

from .. import __version__
from ..config import get_settings
from ..logger import get_logger
from ..utils.file_io import atomic_write, ensure_directory

logger = get_logger("state")


class ProcessingState(BaseModel):
    """
    DEPRECATED: State for ongoing processing operations.

    ⚠️ This class is deprecated. Use DatabaseService with ProcessingJob model instead.
    """

    operation_id: str
    operation_type: str  # 'transcribe', 'summarize', 'moc', 'watch'
    status: str  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    input_path: str
    output_path: str | None = None
    progress: float = 0.0  # 0.0 to 1.0
    started_at: float
    completed_at: float | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("progress")
    def validate_progress(cls, v) -> bool:
        """Ensure progress is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Progress must be between 0.0 and 1.0")
        return v

    @validator("status")
    def validate_status(cls, v) -> bool:
        """Ensure status is valid."""
        valid_statuses = {"pending", "running", "completed", "failed", "cancelled"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v

    def is_active(self) -> bool:
        """Check if operation is currently active."""
        return self.status in {"pending", "running"}

    def is_completed(self) -> bool:
        """Check if operation completed successfully."""
        return self.status == "completed"

    def duration(self) -> float | None:
        """Get operation duration in seconds."""
        if self.completed_at:
            return self.completed_at - self.started_at
        elif self.is_active():
            return time.time() - self.started_at
        return None


class UserPreferences(BaseModel):
    """User preferences and settings."""

    # UI Preferences
    theme: str = "dark"
    language: str = "en"
    auto_save: bool = True
    show_progress: bool = True

    # Processing Preferences
    default_whisper_model: str = "base"
    default_device: str = "auto"
    default_output_format: str = "md"
    auto_transcribe: bool = True
    auto_summarize: bool = True

    # LLM Preferences
    last_llm_provider: str | None = None
    last_llm_model: str | None = None
    max_tokens: int = 1000
    temperature: float = 0.7

    # File Management
    auto_organize: bool = True
    backup_enabled: bool = True
    cleanup_temp_files: bool = True

    # Monitoring
    log_level: str = "INFO"
    enable_notifications: bool = True
    
    # Update Preferences
    auto_check_updates: bool = True
    last_update_check: float | None = None

    @validator("temperature")
    def validate_temperature(cls, v) -> bool:
        """Ensure temperature is valid."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    @validator("max_tokens")
    def validate_max_tokens(cls, v) -> bool:
        """Ensure max_tokens is positive."""
        if v <= 0:
            raise ValueError("max_tokens must be positive")
        return v


class SessionInfo(BaseModel):
    """Information about the current session."""

    session_id: str
    started_at: float
    last_activity: float
    user_agent: str | None = None
    version: str

    # Session statistics
    operations_count: int = 0
    files_processed: int = 0
    errors_count: int = 0

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()

    def duration(self) -> float:
        """Get session duration in seconds."""
        return time.time() - self.started_at

    def is_active(self, timeout: float = 3600) -> bool:
        """Check if session is still active based on timeout."""
        return (time.time() - self.last_activity) < timeout


class RecentFiles(BaseModel):
    """Recently accessed files tracking."""

    files: list[dict[str, Any]] = Field(default_factory=list)
    max_files: int = 50

    def add_file(
        self,
        file_path: str | Path,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a file to recent files list."""
        file_entry = {
            "path": str(file_path),
            "operation": operation,
            "accessed_at": time.time(),
            "metadata": metadata or {},
        }

        # Remove existing entry for this file if it exists
        self.files = [f for f in self.files if f["path"] != str(file_path)]

        # Add to beginning of list
        self.files.insert(0, file_entry)

        # Trim to max_files
        if len(self.files) > self.max_files:
            self.files = self.files[: self.max_files]

    def get_recent(self, count: int = 10) -> list[dict[str, Any]]:
        """Get most recent files."""
        return self.files[:count]

    def get_by_operation(self, operation: str, count: int = 10) -> list[dict[str, Any]]:
        """Get recent files by operation type."""
        filtered = [f for f in self.files if f["operation"] == operation]
        return filtered[:count]

    def clear_old(self, max_age_days: int = 30) -> None:
        """Clear files older than specified days."""
        cutoff = time.time() - (max_age_days * 24 * 3600)
        self.files = [f for f in self.files if f["accessed_at"] > cutoff]


class ApplicationState(BaseModel):
    """Complete application state."""

    # Core state components
    session: SessionInfo
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    recent_files: RecentFiles = Field(default_factory=RecentFiles)

    # Processing state
    active_operations: dict[str, ProcessingState] = Field(default_factory=dict)

    # Cache and temporary data
    cache: dict[str, Any] = Field(default_factory=dict)

    # Metadata
    last_saved: float = Field(default_factory=time.time)
    version: str = __version__

    def add_operation(self, operation: ProcessingState) -> None:
        """Add an active operation."""
        self.active_operations[operation.operation_id] = operation
        self.session.operations_count += 1
        self.session.update_activity()

    def update_operation(self, operation_id: str, **updates) -> bool:
        """Update an operation's state."""
        if operation_id in self.active_operations:
            operation = self.active_operations[operation_id]
            for key, value in updates.items():
                if hasattr(operation, key):
                    setattr(operation, key, value)

            # Mark as completed if status changed to completed/failed/cancelled
            if updates.get("status") in {"completed", "failed", "cancelled"}:
                operation.completed_at = time.time()
                if updates.get("status") == "completed":
                    self.session.files_processed += 1
                elif updates.get("status") == "failed":
                    self.session.errors_count += 1

            self.session.update_activity()
            return True
        return False

    def remove_operation(self, operation_id: str) -> bool:
        """Remove an operation from active operations."""
        if operation_id in self.active_operations:
            del self.active_operations[operation_id]
            self.session.update_activity()
            return True
        return False

    def get_active_operations(self) -> list[ProcessingState]:
        """Get all active operations."""
        return [op for op in self.active_operations.values() if op.is_active()]

    def cleanup_completed_operations(self, max_age_hours: int = 24) -> None:
        """Clean up old completed operations."""
        cutoff = time.time() - (max_age_hours * 3600)
        to_remove = []

        for op_id, operation in self.active_operations.items():
            if (
                not operation.is_active()
                and operation.completed_at
                and operation.completed_at < cutoff
            ):
                to_remove.append(op_id)

        for op_id in to_remove:
            del self.active_operations[op_id]


class StateManager:
    """Manages application state persistence and operations."""

    def __init__(self, state_file: Path | None = None) -> None:
        """Initialize state manager."""
        self.settings = get_settings()

        if state_file is None:
            # Use macOS standard Application Support directory for state
            try:
                from .macos_paths import get_application_support_dir
                state_dir = get_application_support_dir() / "state"
            except ImportError:
                # Fallback to cache directory if macos_paths not available
                state_dir = Path(self.settings.paths.cache) / "state"
            
            ensure_directory(state_dir)
            self.state_file = state_dir / "application_state.json"
        else:
            self.state_file = state_file

        self._state: ApplicationState | None = None
        self._auto_save = True
        self._save_interval = 30  # seconds
        self._last_save = 0.0

    def _create_new_state(self) -> ApplicationState:
        """Create a new application state."""
        import uuid

        session = SessionInfo(
            session_id=str(uuid.uuid4()),
            started_at=time.time(),
            last_activity=time.time(),
            version=__version__,
        )

        return ApplicationState(session=session)

    def load(self) -> ApplicationState:
        """Load application state from file."""
        if self._state is not None:
            return self._state

        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    data = json.load(f)

                # Validate and create state
                self._state = ApplicationState(**data)

                # Update session activity
                self._state.session.update_activity()

                logger.info(f"Loaded application state from {self.state_file}")
            else:
                logger.info("No existing state file found, creating new state")
                self._state = self._create_new_state()

        except Exception as e:
            logger.error(f"Failed to load state from {self.state_file}: {e}")
            logger.info("Creating new application state")
            self._state = self._create_new_state()

        return self._state

    def save(self, force: bool = False) -> bool:
        """Save application state to file."""
        if self._state is None:
            return False

        # Check if we need to save
        current_time = time.time()
        if not force and (current_time - self._last_save) < self._save_interval:
            return False

        try:
            # Update metadata
            self._state.last_saved = current_time

            # Clean up old operations
            self._state.cleanup_completed_operations()
            self._state.recent_files.clear_old()

            # Save to file
            data = self._state.model_dump()
            atomic_write(self.state_file, json.dumps(data, indent=2))

            self._last_save = current_time
            logger.debug(f"Saved application state to {self.state_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save state to {self.state_file}: {e}")
            return False

    def get_state(self) -> ApplicationState:
        """Get current application state."""
        if self._state is None:
            return self.load()
        return self._state

    def update_preferences(self, **preferences) -> bool:
        """Update user preferences."""
        try:
            state = self.get_state()
            for key, value in preferences.items():
                if hasattr(state.preferences, key):
                    setattr(state.preferences, key, value)

            if self._auto_save:
                self.save()
            return True

        except Exception as e:
            logger.error(f"Failed to update preferences: {e}")
            return False

    def add_recent_file(
        self,
        file_path: str | Path,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a file to recent files."""
        state = self.get_state()
        state.recent_files.add_file(file_path, operation, metadata)

        if self._auto_save:
            self.save()

    def start_operation(
        self,
        operation_type: str,
        input_path: str | Path,
        output_path: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Start a new operation and return operation ID."""
        import uuid

        operation_id = str(uuid.uuid4())
        operation = ProcessingState(
            operation_id=operation_id,
            operation_type=operation_type,
            status="pending",
            input_path=str(input_path),
            output_path=str(output_path) if output_path else None,
            started_at=time.time(),
            metadata=metadata or {},
        )

        state = self.get_state()
        state.add_operation(operation)

        if self._auto_save:
            self.save()

        logger.info(
            f"Started {operation_type} operation {operation_id} for {input_path}"
        )
        return operation_id

    def update_operation_progress(
        self,
        operation_id: str,
        progress: float,
        status: str | None = None,
        error_message: str | None = None,
    ) -> bool:
        """Update operation progress."""
        updates = {"progress": progress}
        if status:
            updates["status"] = status
        if error_message:
            updates["error_message"] = error_message

        state = self.get_state()
        success = state.update_operation(operation_id, **updates)

        if success and self._auto_save:
            self.save()

        return success

    def complete_operation(
        self,
        operation_id: str,
        success: bool = True,
        error_message: str | None = None,
    ) -> bool:
        """Mark operation as completed."""
        status = "completed" if success else "failed"
        return self.update_operation_progress(operation_id, 1.0, status, error_message)

    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel an operation."""
        return self.update_operation_progress(operation_id, 0.0, "cancelled")

    def get_recent_files(
        self, operation: str | None = None, count: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent files, optionally filtered by operation."""
        state = self.get_state()
        if operation:
            return state.recent_files.get_by_operation(operation, count)
        return state.recent_files.get_recent(count)

    def get_active_operations(self) -> list[ProcessingState]:
        """Get all active operations."""
        state = self.get_state()
        return state.get_active_operations()

    def get_session_info(self) -> SessionInfo:
        """Get current session information."""
        state = self.get_state()
        return state.session

    def clear_cache(self) -> None:
        """Clear application cache."""
        state = self.get_state()
        state.cache.clear()

        if self._auto_save:
            self.save()

    def reset_state(self) -> None:
        """Reset application state (for testing or fresh start)."""
        self._state = self._create_new_state()
        if self.state_file.exists():
            self.state_file.unlink()
        self.save(force=True)
        logger.info("Application state reset")

    def set_auto_save(self, enabled: bool, interval: int = 30) -> None:
        """Configure auto-save behavior."""
        self._auto_save = enabled
        self._save_interval = interval

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - save state."""
        self.save(force=True)


# Global state manager instance
_state_manager: StateManager | None = None


def get_state_manager() -> StateManager:
    """Get or create global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def get_application_state() -> ApplicationState:
    """Get current application state."""
    return get_state_manager().get_state()


def save_application_state() -> bool:
    """Save current application state."""
    return get_state_manager().save(force=True)
