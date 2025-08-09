"""
Basic tests for project structure and CLI.
"""

import subprocess
import sys

from knowledge_system import Settings, __version__, get_logger


def test_version():
    """Test that version is accessible."""
    assert __version__ == "0.1.0"


def test_settings_basic():
    """Test basic Settings functionality."""
    settings = Settings()
    assert settings.app.version == "0.1.0"
    assert settings.app.debug is False

    # Test nested access
    assert settings.get_nested("app.version") == "0.1.0"
    assert settings.get_nested("transcription.whisper_model") == "base"

    # Test nested setting
    settings.set_nested("app.debug", True)
    assert settings.app.debug is True


def test_logger_basic():
    """Test basic logger functionality."""
    logger = get_logger("test")
    # Test that logger has the required methods
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
    assert hasattr(logger, "warning")
    assert hasattr(logger, "debug")
    assert hasattr(logger, "critical")


def test_cli_version():
    """Test CLI version command."""
    result = subprocess.run(
        [sys.executable, "-m", "knowledge_system.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_cli_help():
    """Test CLI help command."""
    result = subprocess.run(
        [sys.executable, "-m", "knowledge_system.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Knowledge System" in result.stdout
    assert "transcribe" in result.stdout
    assert "summarize" in result.stdout
    assert "moc" in result.stdout
    assert "watch" in result.stdout


def test_cli_dry_run():
    """Test CLI dry run functionality."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "knowledge_system.cli",
            "transcribe",
            "run",
            "--source",
            "test",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[DRY RUN]" in result.stdout
    assert "test" in result.stdout
