"""
Pytest configuration for GUI tests.

This file provides shared fixtures and configuration for all GUI tests,
including qtbot setup, mock data, and helper utilities.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Check if PyQt6 is available
try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


@pytest.fixture(scope="session")
def qapp():
    """
    Create a QApplication instance for the entire test session.

    This fixture is session-scoped to avoid creating multiple QApplication
    instances, which would cause crashes.
    """
    if not PYQT_AVAILABLE:
        pytest.skip("PyQt6 not available")

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app

    # Cleanup is automatic - QApplication will be destroyed at session end


@pytest.fixture
def mock_settings():
    """Provide mock settings manager for testing."""
    settings = MagicMock()
    settings.get.return_value = None
    settings.set.return_value = None
    settings.get_checkbox_state.return_value = False
    settings.set_checkbox_state.return_value = None
    return settings


@pytest.fixture
def mock_gui_settings():
    """Provide mock GUI settings manager for testing."""
    settings = MagicMock()
    settings.get.return_value = {}
    settings.set.return_value = None
    settings.save.return_value = None
    return settings


@pytest.fixture
def sample_transcript_file(tmp_path):
    """Create a sample transcript file for testing."""
    transcript = tmp_path / "sample_transcript.txt"
    content = """
    Speaker 1 (00:00:00): Hello, this is a test transcript.
    Speaker 2 (00:00:05): This is another speaker responding.
    Speaker 1 (00:00:10): Here's some more content for testing.
    """
    transcript.write_text(content)
    return transcript


@pytest.fixture
def sample_transcript_files(tmp_path):
    """Create multiple sample transcript files for batch testing."""
    files = []
    for i in range(3):
        transcript = tmp_path / f"transcript_{i}.txt"
        transcript.write_text(f"Speaker 1: This is transcript {i}")
        files.append(transcript)
    return files


@pytest.fixture
def sample_yaml_template(tmp_path):
    """Create a sample YAML template for testing."""
    template = tmp_path / "test_template.yaml"
    content = """
    analysis_type: "test"
    max_claims: 50
    include_people: true
    include_concepts: true
    """
    template.write_text(content)
    return template


@pytest.fixture
def mock_ollama_manager():
    """Provide mock Ollama manager for testing."""
    manager = MagicMock()
    manager.is_installed.return_value = True
    manager.is_running.return_value = True
    manager.list_models.return_value = ["llama2", "mistral"]
    return manager


@pytest.fixture
def mock_model_registry():
    """Provide mock model registry for testing."""
    registry = {
        "openai": ["gpt-4", "gpt-3.5-turbo"],
        "anthropic": ["claude-3-opus", "claude-3-sonnet"],
        "ollama": ["llama2", "mistral"],
    }
    return registry


@pytest.fixture
def wait_for_signal(qtbot):
    """
    Helper fixture to wait for Qt signals with better error messages.

    Usage:
        with wait_for_signal(widget.my_signal, timeout=5000):
            # Trigger action that should emit signal
            widget.do_something()
    """

    def _wait(signal, timeout=1000):
        return qtbot.waitSignal(signal, timeout=timeout)

    return _wait


@pytest.fixture
def click_button(qtbot):
    """
    Helper fixture to click buttons with proper event processing.

    Usage:
        click_button(my_button)
    """

    def _click(button):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        qtbot.wait(50)  # Small delay for event processing

    return _click


@pytest.fixture
def type_text(qtbot):
    """
    Helper fixture to type text into widgets with proper event processing.

    Usage:
        type_text(line_edit, "Hello World")
    """

    def _type(widget, text):
        widget.clear()
        qtbot.keyClicks(widget, text)
        qtbot.wait(50)  # Small delay for event processing

    return _type


@pytest.fixture
def mock_file_dialog(monkeypatch):
    """
    Mock QFileDialog to return predetermined files without showing dialog.

    Usage:
        mock_file_dialog(["/path/to/file1.txt", "/path/to/file2.txt"])
        # Now QFileDialog.getOpenFileNames() will return those files
    """

    def _mock(files):
        from PyQt6.QtWidgets import QFileDialog

        monkeypatch.setattr(
            QFileDialog, "getOpenFileNames", lambda *args, **kwargs: (files, "")
        )
        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            lambda *args, **kwargs: (files[0] if files else "", ""),
        )
        monkeypatch.setattr(
            QFileDialog,
            "getExistingDirectory",
            lambda *args, **kwargs: str(Path(files[0]).parent) if files else "",
        )

    return _mock


@pytest.fixture
def mock_message_box(monkeypatch):
    """
    Mock QMessageBox to avoid showing dialogs during tests.

    Returns a mock object that tracks which message boxes were shown.

    Usage:
        mbox = mock_message_box()
        # ... trigger code that shows message box ...
        assert mbox.warning.called
    """
    from PyQt6.QtWidgets import QMessageBox

    mock = MagicMock()
    monkeypatch.setattr(QMessageBox, "information", mock.information)
    monkeypatch.setattr(QMessageBox, "warning", mock.warning)
    monkeypatch.setattr(QMessageBox, "critical", mock.critical)
    monkeypatch.setattr(QMessageBox, "question", mock.question)

    return mock


@pytest.fixture
def disable_network(monkeypatch):
    """
    Disable network access for tests to prevent accidental external calls.

    Usage:
        def test_something(disable_network):
            # Network calls will raise an error
            ...
    """
    import requests

    def mock_request(*args, **kwargs):
        raise RuntimeError("Network access disabled in tests")

    monkeypatch.setattr(requests, "get", mock_request)
    monkeypatch.setattr(requests, "post", mock_request)
    monkeypatch.setattr(requests, "put", mock_request)
    monkeypatch.setattr(requests, "delete", mock_request)


@pytest.fixture
def capture_signals(qtbot):
    """
    Capture signals emitted during test for later inspection.

    Usage:
        signals = capture_signals(widget.my_signal)
        widget.do_something()
        assert len(signals) == 1
        assert signals[0] == expected_value
    """

    def _capture(signal):
        captured = []
        signal.connect(
            lambda *args: captured.append(args[0] if len(args) == 1 else args)
        )
        return captured

    return _capture


# Markers for test organization
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_ollama: marks tests that require Ollama to be running"
    )
    config.addinivalue_line(
        "markers", "requires_api_key: marks tests that require API keys"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
