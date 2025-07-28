"""
Tests for the CLI framework.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from knowledge_system.cli import CLIContext, handle_cli_error, main
from knowledge_system.errors import KnowledgeSystemError


class TestCLIContext:
    """Test CLIContext class."""

    def test_init(self) -> None:
        """Test CLI context initialization."""
        ctx = CLIContext()

        assert ctx.settings is None
        assert ctx.verbose is False
        assert ctx.quiet is False

    def test_get_settings(self) -> None:
        """Test settings getter."""
        ctx = CLIContext()

        # First call should initialize settings
        settings = ctx.get_settings()
        assert settings is not None
        assert ctx.settings is settings

        # Second call should return same instance
        settings2 = ctx.get_settings()
        assert settings2 is settings


class TestHandleCLIError:
    """Test CLI error handler decorator."""

    def test_successful_function(self) -> None:
        """Test decorator with successful function."""

        @handle_cli_error
        def success_func():
            return "success"

        result = success_func()
        assert result == "success"

    def test_knowledge_system_error(self) -> None:
        """Test decorator with KnowledgeSystemError."""

        @handle_cli_error
        def error_func():
            raise KnowledgeSystemError("Test error", context={"key": "value"})

        with pytest.raises(SystemExit) as exc_info:
            error_func()

        assert exc_info.value.code == 1

    def test_unexpected_error(self) -> None:
        """Test decorator with unexpected error."""

        @handle_cli_error
        def error_func():
            raise ValueError("Unexpected error")

        with pytest.raises(SystemExit) as exc_info:
            error_func()

        assert exc_info.value.code == 1


class TestMainCommand:
    """Test main CLI command and options."""

    def setup_method(self) -> None:
        """Setup for each test method."""
        self.runner = CliRunner()

    def test_help_output(self) -> None:
        """Test help output."""
        result = self.runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Knowledge_Chipper" in result.output
        assert "transcribe" in result.output
        assert "summarize" in result.output
        assert "moc" in result.output
        assert "watch" in result.output
        assert "status" in result.output
        assert "info" in result.output

    def test_version_flag(self) -> None:
        """Test version flag."""
        result = self.runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "Knowledge_Chipper v" in result.output

    def test_no_command_shows_help(self) -> None:
        """Test that no command shows help."""
        result = self.runner.invoke(main, [])

        assert result.exit_code == 0
        assert "Usage:" in result.output or "Commands:" in result.output

    def test_verbose_flag(self) -> None:
        """Test verbose flag sets context."""
        with patch("knowledge_system.cli.log_system_event"):
            result = self.runner.invoke(main, ["--verbose"])

            assert result.exit_code == 0

    def test_quiet_flag(self) -> None:
        """Test quiet flag sets context."""
        with patch("knowledge_system.cli.log_system_event"):
            result = self.runner.invoke(main, ["--quiet"])

            assert result.exit_code == 0


class TestTranscribeCommand:
    """Test transcribe command."""

    def setup_method(self) -> None:
        """Setup for each test method."""
        self.runner = CliRunner()

    def test_transcribe_help(self) -> None:
        """Test transcribe command help."""
        result = self.runner.invoke(main, ["transcribe", "--help"])

        assert result.exit_code == 0
        assert "Transcribe audio/video files" in result.output
        assert "--model" in result.output
        assert "--device" in result.output
        assert "--format" in result.output

    def test_transcribe_with_file(self) -> None:
        """Test transcribe command with file."""
        with self.runner.isolated_filesystem():
            # Create test file
            test_file = Path("test.mp4")
            test_file.touch()

            with patch("knowledge_system.cli.log_system_event"):
                result = self.runner.invoke(
                    main, ["transcribe", str(test_file)])

            assert result.exit_code == 0
            assert "Transcribing:" in result.output
            assert "not yet implemented" in result.output

    def test_transcribe_nonexistent_file(self) -> None:
        """Test transcribe command with nonexistent file."""
        result = self.runner.invoke(main, ["transcribe", "nonexistent.mp4"])

        assert result.exit_code != 0


class TestSummarizeCommand:
    """Test summarize command."""

    def setup_method(self) -> None:
        """Setup for each test method."""
        self.runner = CliRunner()

    def test_summarize_help(self) -> None:
        """Test summarize command help."""
        result = self.runner.invoke(main, ["summarize", "--help"])

        assert result.exit_code == 0
        assert "Summarize transcripts" in result.output
        assert "--model" in result.output
        assert "--style" in result.output
        assert "--max-tokens" in result.output

    def test_summarize_with_file(self) -> None:
        """Test summarize command with file."""
        with self.runner.isolated_filesystem():
            test_file = Path("test.md")
            test_file.touch()

            with patch("knowledge_system.cli.log_system_event"):
                result = self.runner.invoke(
                    main, ["summarize", str(test_file)])

            assert result.exit_code == 0
            assert "Summarizing:" in result.output
            assert "not yet implemented" in result.output


class TestMocCommand:
    """Test MOC command."""

    def setup_method(self) -> None:
        """Setup for each test method."""
        self.runner = CliRunner()

    def test_moc_help(self) -> None:
        """Test MOC command help."""
        result = self.runner.invoke(main, ["moc", "--help"])

        assert result.exit_code == 0
        assert "Generate Maps of Content" in result.output
        assert "--theme" in result.output
        assert "--depth" in result.output
        assert "--include-beliefs" in result.output

    def test_moc_with_files(self) -> None:
        """Test MOC command with files."""
        with self.runner.isolated_filesystem():
            # Create test files
            test_file1 = Path("test1.md")
            test_file2 = Path("test2.md")
            test_file1.touch()
            test_file2.touch()

            with patch("knowledge_system.cli.log_system_event"):
                result = self.runner.invoke(
                    main, ["moc", str(test_file1), str(test_file2)]
                )

            assert result.exit_code == 0
            assert "Generating MOC:" in result.output
            assert "2 sources" in result.output
            assert "not yet implemented" in result.output

    def test_moc_no_input_paths(self) -> None:
        """Test MOC command with no input paths."""
        result = self.runner.invoke(main, ["moc"])

        assert result.exit_code == 1
        assert "No input paths provided" in result.output


class TestStatusCommand:
    """Test status command."""

    def setup_method(self) -> None:
        """Setup for each test method."""
        self.runner = CliRunner()

    def test_status_help(self) -> None:
        """Test status command help."""
        result = self.runner.invoke(main, ["status", "--help"])

        assert result.exit_code == 0
        assert "Show system status" in result.output
        assert "--processors" in result.output
        assert "--paths" in result.output
        assert "--settings" in result.output
        assert "--logs" in result.output

    @patch("knowledge_system.cli.get_all_processor_stats")
    def test_status_default(self, mock_get_stats: Mock) -> None:
        """Test status command with default options."""
        mock_get_stats.return_value = {
            "TestProcessor": {
                "processed_count": 5,
                "success_count": 4,
                "success_rate": 0.8,
                "average_processing_time": 1.5,
            }
        }

        result = self.runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "Knowledge_Chipper Status" in result.output
        assert "Processor Statistics" in result.output
        assert "Configured Paths" in result.output
        assert "TestProcessor" in result.output

    @patch("knowledge_system.cli.get_all_processor_stats")
    def test_status_no_processors(self, mock_get_stats: Mock) -> None:
        """Test status command with no processors."""
        mock_get_stats.return_value = {}

        result = self.runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "No processor statistics available" in result.output


class TestInfoCommand:
    """Test info command."""

    def setup_method(self) -> None:
        """Setup for each test method."""
        self.runner = CliRunner()

    def test_info_help(self) -> None:
        """Test info command help."""
        result = self.runner.invoke(main, ["info", "--help"])

        assert result.exit_code == 0
        assert "Show detailed information about a file" in result.output

    @patch("knowledge_system.cli.get_file_info")
    @patch("knowledge_system.cli.list_processors")
    def test_info_with_file(
        self, mock_list_processors: Mock, mock_get_file_info: Mock
    ) -> None:
        """Test info command with file."""
        mock_get_file_info.return_value = {
            "size_human": "1.5 MB",
            "modified": "2023-01-01 12:00:00",
            "mime_type": "video/mp4",
            "hash_md5": "abc123",
        }
        mock_list_processors.return_value = ["TestProcessor"]

        with self.runner.isolated_filesystem():
            test_file = Path("test.mp4")
            test_file.touch()

            result = self.runner.invoke(main, ["info", str(test_file)])

        assert result.exit_code == 0
        assert "File Information:" in result.output
        assert "1.5 MB" in result.output
        assert "video/mp4" in result.output
        assert "abc123" in result.output
        assert "Processor Compatibility" in result.output

    def test_info_nonexistent_file(self) -> None:
        """Test info command with nonexistent file."""
        result = self.runner.invoke(main, ["info", "nonexistent.mp4"])

        assert result.exit_code != 0
