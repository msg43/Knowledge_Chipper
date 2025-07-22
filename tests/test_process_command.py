"""
Tests for the process command functionality.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from knowledge_system.cli import main


class TestProcessCommand:
    """Test the process command functionality."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner for testing."""
        return CliRunner()

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_process_single_file_dry_run(self, runner, temp_dir):
        """Test processing a single file in dry run mode."""
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")

        result = runner.invoke(main, ["process", str(test_file), "--dry-run"])

        assert result.exit_code == 0
        assert "Processing:" in result.output
        assert "test.txt" in result.output
        assert "Operations: Transcribe=True, Summarize=True, MOC=True" in result.output
        assert "[DRY RUN]" in result.output

    def test_process_directory_dry_run(self, runner, temp_dir):
        """Test processing a directory in dry run mode."""
        # Create test files
        (temp_dir / "file1.txt").write_text("Content 1")
        (temp_dir / "file2.md").write_text("Content 2")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file3.txt").write_text("Content 3")

        result = runner.invoke(
            main, ["process", str(temp_dir), "--dry-run", "--recursive"]
        )

        assert result.exit_code == 0
        assert "Processing:" in result.output
        assert str(temp_dir) in result.output
        assert "Directory processing: recursive" in result.output

    def test_process_with_patterns(self, runner, temp_dir):
        """Test processing with specific file patterns."""
        # Create test files
        (temp_dir / "file1.txt").write_text("Content 1")
        (temp_dir / "file2.md").write_text("Content 2")
        (temp_dir / "file3.pdf").write_text("Content 3")

        result = runner.invoke(
            main,
            [
                "process",
                str(temp_dir),
                "--dry-run",
                "--no-recursive",
                "-p",
                "*.txt",
                "-p",
                "*.md",
            ],
        )

        assert result.exit_code == 0
        assert "Patterns: *.txt, *.md" in result.output

    def test_process_selective_operations(self, runner, temp_dir):
        """Test processing with selective operations."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")

        result = runner.invoke(
            main,
            [
                "process",
                str(test_file),
                "--dry-run",
                "--no-transcribe",
                "--summarize",
                "--moc",
            ],
        )

        assert result.exit_code == 0
        assert "Operations: Transcribe=False, Summarize=True, MOC=True" in result.output

    def test_process_with_custom_models(self, runner, temp_dir):
        """Test processing with custom model settings."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")

        result = runner.invoke(
            main,
            [
                "process",
                str(test_file),
                "--dry-run",
                "--transcription-model",
                "large",
                "--summarization-model",
                "gpt-4",
            ],
        )

        assert result.exit_code == 0
        assert "Models: Transcription=large, Summarization=gpt-4" in result.output

    def test_process_with_progress(self, runner, temp_dir):
        """Test processing with progress tracking."""
        # Create multiple test files
        for i in range(3):
            (temp_dir / f"file{i}.txt").write_text(f"Content {i}")

        result = runner.invoke(
            main, ["process", str(temp_dir), "--dry-run", "--progress"]
        )

        assert result.exit_code == 0
        assert "Processing:" in result.output

    def test_process_empty_directory(self, runner, temp_dir):
        """Test processing an empty directory."""
        result = runner.invoke(main, ["process", str(temp_dir), "--dry-run"])

        assert result.exit_code == 0
        assert "Processing:" in result.output

    def test_process_nonexistent_file(self, runner):
        """Test processing a nonexistent file."""
        result = runner.invoke(
            main, ["process", "nonexistent.txt", "--dry-run"])

        assert result.exit_code != 0
        assert "Error" in result.output

    @patch("knowledge_system.cli.AudioProcessor")
    @patch("knowledge_system.cli.SummarizerProcessor")
    @patch("knowledge_system.cli.MOCProcessor")
    def test_process_actual_execution(
        self, mock_moc, mock_summarizer, mock_audio, runner, temp_dir
    ):
        """Test actual processing execution with mocked processors."""
        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")

        # Mock successful processor results
        mock_audio_instance = MagicMock()
        mock_audio_instance.process.return_value.success = True
        mock_audio_instance.process.return_value.data = "Mock transcript"
        mock_audio_instance.process.return_value.metadata = {
            "timestamp": "2023-01-01"}
        mock_audio.return_value = mock_audio_instance

        mock_summarizer_instance = MagicMock()
        mock_summarizer_instance.process.return_value.success = True
        mock_summarizer_instance.process.return_value.data = "Mock summary"
        mock_summarizer_instance.process.return_value.metadata = {
            "provider": "test"}
        mock_summarizer.return_value = mock_summarizer_instance

        mock_moc_instance = MagicMock()
        mock_moc_instance.process.return_value.success = True
        mock_moc_instance.process.return_value.data = {"MOC.md": "Mock MOC"}
        mock_moc.return_value = mock_moc_instance

        result = runner.invoke(
            main, ["process", str(test_file),
                                  "--no-transcribe", "--summarize", "--moc"]
        )

        assert result.exit_code == 0
        assert "Processing completed!" in result.output
        assert "Files summarized: 1" in result.output
        assert "MOCs generated: 1" in result.output
