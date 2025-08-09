"""
Tests for the state management system.
"""

import tempfile
import time
from pathlib import Path

import pytest

from knowledge_system.utils.state import (
    ApplicationState,
    ProcessingState,
    RecentFiles,
    StateManager,
    UserPreferences,
    get_application_state,
    get_state_manager,
    save_application_state,
)


class TestProcessingState:
    """Test ProcessingState model."""

    def test_init_valid(self) -> None:
        """Test valid ProcessingState initialization."""
        state = ProcessingState(
            operation_id="test-123",
            operation_type="transcribe",
            status="pending",
            input_path="/test/input.mp4",
            started_at=time.time(),
        )

        assert state.operation_id == "test-123"
        assert state.operation_type == "transcribe"
        assert state.status == "pending"
        assert state.input_path == "/test/input.mp4"
        assert state.progress == 0.0
        assert state.output_path is None
        assert state.completed_at is None
        assert state.error_message is None
        assert isinstance(state.metadata, dict)

    def test_progress_validation(self) -> None:
        """Test progress validation."""
        # Valid progress
        state = ProcessingState(
            operation_id="test",
            operation_type="transcribe",
            status="pending",
            input_path="/test/input.mp4",
            started_at=time.time(),
            progress=0.5,
        )
        assert state.progress == 0.5

        # Invalid progress
        with pytest.raises(ValueError, match="Progress must be between 0.0 and 1.0"):
            ProcessingState(
                operation_id="test",
                operation_type="transcribe",
                status="pending",
                input_path="/test/input.mp4",
                started_at=time.time(),
                progress=1.5,
            )

    def test_status_validation(self) -> None:
        """Test status validation."""
        # Valid status
        for status in ["pending", "running", "completed", "failed", "cancelled"]:
            state = ProcessingState(
                operation_id="test",
                operation_type="transcribe",
                status=status,
                input_path="/test/input.mp4",
                started_at=time.time(),
            )
            assert state.status == status

        # Invalid status
        with pytest.raises(ValueError, match="Status must be one of"):
            ProcessingState(
                operation_id="test",
                operation_type="transcribe",
                status="invalid",
                input_path="/test/input.mp4",
                started_at=time.time(),
            )

    def test_is_active(self) -> None:
        """Test is_active method."""
        # Active states
        for status in ["pending", "running"]:
            state = ProcessingState(
                operation_id="test",
                operation_type="transcribe",
                status=status,
                input_path="/test/input.mp4",
                started_at=time.time(),
            )
            assert state.is_active() is True

        # Inactive states
        for status in ["completed", "failed", "cancelled"]:
            state = ProcessingState(
                operation_id="test",
                operation_type="transcribe",
                status=status,
                input_path="/test/input.mp4",
                started_at=time.time(),
            )
            assert state.is_active() is False

    def test_is_completed(self) -> None:
        """Test is_completed method."""
        completed_state = ProcessingState(
            operation_id="test",
            operation_type="transcribe",
            status="completed",
            input_path="/test/input.mp4",
            started_at=time.time(),
        )
        assert completed_state.is_completed() is True

        pending_state = ProcessingState(
            operation_id="test",
            operation_type="transcribe",
            status="pending",
            input_path="/test/input.mp4",
            started_at=time.time(),
        )
        assert pending_state.is_completed() is False


class TestUserPreferences:
    """Test UserPreferences model."""

    def test_init_defaults(self) -> None:
        """Test default initialization."""
        prefs = UserPreferences()

        assert prefs.theme == "dark"
        assert prefs.language == "en"
        assert prefs.auto_save is True
        assert prefs.default_whisper_model == "base"
        assert prefs.default_llm_model == "gpt-4o-mini-2024-07-18"
        assert prefs.max_tokens == 1000
        assert prefs.temperature == 0.7

    def test_temperature_validation(self) -> None:
        """Test temperature validation."""
        # Valid temperatures
        for temp in [0.0, 0.5, 1.0, 2.0]:
            prefs = UserPreferences(temperature=temp)
            assert prefs.temperature == temp

        # Invalid temperatures
        for temp in [-0.1, 2.1]:
            with pytest.raises(
                ValueError, match="Temperature must be between 0.0 and 2.0"
            ):
                UserPreferences(temperature=temp)

    def test_max_tokens_validation(self) -> None:
        """Test max_tokens validation."""
        # Valid max_tokens
        prefs = UserPreferences(max_tokens=500)
        assert prefs.max_tokens == 500

        # Invalid max_tokens
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            UserPreferences(max_tokens=0)

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            UserPreferences(max_tokens=-1)


class TestRecentFiles:
    """Test RecentFiles model."""

    def test_init(self) -> None:
        """Test RecentFiles initialization."""
        recent = RecentFiles()

        assert recent.files == []
        assert recent.max_files == 50

    def test_add_file(self) -> None:
        """Test adding files."""
        recent = RecentFiles()

        recent.add_file("/test/file1.mp4", "transcribe", {"size": 1000})

        assert len(recent.files) == 1
        assert recent.files[0]["path"] == "/test/file1.mp4"
        assert recent.files[0]["operation"] == "transcribe"
        assert recent.files[0]["metadata"]["size"] == 1000
        assert "accessed_at" in recent.files[0]


class TestStateManager:
    """Test StateManager class."""

    def test_init(self) -> None:
        """Test StateManager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "test_state.json"
            manager = StateManager(state_file=state_file)

            assert manager.state_file == state_file
            assert manager._state is None
            assert manager._auto_save is True

    def test_create_new_state(self) -> None:
        """Test creating new state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "test_state.json"
            manager = StateManager(state_file=state_file)

            state = manager._create_new_state()

            assert isinstance(state, ApplicationState)
            assert state.session.session_id is not None
            assert state.session.version == "0.1.1"

    def test_load_nonexistent_file(self) -> None:
        """Test loading when no state file exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "nonexistent.json"
            manager = StateManager(state_file=state_file)

            state = manager.load()

            assert isinstance(state, ApplicationState)
            assert state.session.session_id is not None

    def test_save_and_load(self) -> None:
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "test_state.json"
            manager = StateManager(state_file=state_file)

            # Create and modify state
            state = manager.get_state()
            state.preferences.theme = "light"
            state.preferences.default_whisper_model = "large"

            # Save state
            success = manager.save(force=True)
            assert success is True
            assert state_file.exists()

            # Create new manager and load
            manager2 = StateManager(state_file=state_file)
            loaded_state = manager2.load()

            assert loaded_state.preferences.theme == "light"
            assert loaded_state.preferences.default_whisper_model == "large"

    def test_operation_lifecycle(self) -> None:
        """Test complete operation lifecycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "test_state.json"
            manager = StateManager(state_file=state_file)
            manager.set_auto_save(False)

            # Start operation
            op_id = manager.start_operation("transcribe", "/test/input.mp4")
            assert op_id is not None

            # Check operation exists
            active_ops = manager.get_active_operations()
            assert len(active_ops) == 1
            assert active_ops[0].operation_id == op_id

            # Update progress
            success = manager.update_operation_progress(op_id, 0.5, "running")
            assert success is True

            # Complete operation
            success = manager.complete_operation(op_id, success=True)
            assert success is True

            # Check operation is no longer active
            active_ops = manager.get_active_operations()
            assert len(active_ops) == 0


class TestGlobalFunctions:
    """Test global state functions."""

    def test_get_state_manager(self) -> None:
        """Test global state manager getter."""
        # Clear global state
        import knowledge_system.utils.state as state_module

        state_module._state_manager = None

        manager1 = get_state_manager()
        manager2 = get_state_manager()

        assert manager1 is manager2  # Should be singleton

    def test_get_application_state(self) -> None:
        """Test getting application state."""
        state = get_application_state()
        assert isinstance(state, ApplicationState)

    def test_save_application_state(self) -> None:
        """Test saving application state."""
        success = save_application_state()
        assert isinstance(success, bool)
