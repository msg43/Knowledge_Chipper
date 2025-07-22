"""
Tests for logging system.
"""

import logging
import tempfile
from pathlib import Path


from knowledge_system.logger import (
    get_logger,
    setup_logging,
    log_exception,
    log_performance,
    log_user_action,
    log_system_event,
    LogContext,
    debug,
    info,
    warning,
    error,
    critical,
)


class TestBasicLogging:
    """Test basic logging functionality."""

    def test_get_logger(self):
        """Test getting a logger instance."""
        logger = get_logger("test")
        assert logger is not None
        # Logger should be a loguru logger
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_get_logger_with_name(self):
        """Test getting logger with custom name."""
        logger = get_logger("custom_logger")
        assert logger is not None

    def test_convenience_functions(self):
        """Test convenience logging functions."""
        # These should not raise exceptions
        debug("Debug message", component="test")
        info("Info message", component="test")
        warning("Warning message", component="test")
        error("Error message", component="test")
        critical("Critical message", component="test")


class TestLoggingSetup:
    """Test logging setup and configuration."""

    def test_setup_logging_with_file(self):
        """Test setting up logging with file output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            # Setup logging with custom file
            setup_logging(
                log_level="DEBUG",
                log_file=str(log_file),
                enable_console=False,
                enable_file=True,
            )

            # Log a test message
            logger = get_logger("test")
            logger.info("Test message")

            # Check if log file was created
            assert log_file.exists()

    def test_setup_logging_console_only(self):
        """Test setting up logging with console output only."""
        # This should not raise exceptions
        setup_logging(
            log_level="INFO",
            enable_console=True,
            enable_file=False,
        )

        logger = get_logger("test")
        logger.info("Console test message")

    def test_setup_logging_custom_format(self):
        """Test setting up logging with custom format."""
        custom_format = "{time} | {level} | {message}"

        setup_logging(
            log_format=custom_format,
            enable_console=True,
            enable_file=False,
        )

        logger = get_logger("test")
        logger.info("Custom format test")


class TestSpecializedLogging:
    """Test specialized logging functions."""

    def test_log_exception(self):
        """Test exception logging."""
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            # Should not raise
            log_exception(e, "Test exception message", test_context="value")

    def test_log_performance(self):
        """Test performance logging."""
        log_performance(
            operation="test_operation",
            duration=1.234,
            context="test",
            items_processed=100,
        )

    def test_log_user_action(self):
        """Test user action logging."""
        log_user_action(
            action="test_action", user_id="test_user", resource="test_resource"
        )

        # Test without user_id
        log_user_action(action="anonymous_action", resource="test_resource")

    def test_log_system_event(self):
        """Test system event logging."""
        # Test different status levels
        statuses = ["info", "warning", "error", "critical", "debug"]

        for status in statuses:
            log_system_event(
                event="test_event",
                component="test_component",
                status=status,
                extra_data="test_value",
            )

        # Test with invalid status (should default to INFO)
        log_system_event(
            event="test_event", component="test_component", status="invalid_status"
        )


class TestLogContext:
    """Test log context manager."""

    def test_log_context_basic(self):
        """Test basic LogContext functionality."""
        # Test that LogContext can be created and doesn't crash
        context = LogContext(request_id="123", user="test_user")
        assert context is not None
        assert context.context["request_id"] == "123"
        assert context.context["user"] == "test_user"


class TestLoggingIntegration:
    """Test integration with other components."""

    def test_logging_with_settings(self):
        """Test logging integration with settings."""
        # This should use settings to determine log location
        setup_logging()

        logger = get_logger("integration_test")
        logger.info("Integration test message")

    def test_stdlib_logging_interception(self):
        """Test that standard library logging is intercepted."""
        # Set up logging with stdlib interception
        setup_logging(intercept_stdlib=True)

        # Use standard library logger
        stdlib_logger = logging.getLogger("test_stdlib")
        stdlib_logger.info("Standard library log message")

        # This should be intercepted and handled by loguru


class TestLoggingFileOperations:
    """Test file-related logging operations."""

    def test_log_file_creation(self):
        """Test that log files are created properly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "creation_test.log"

            setup_logging(
                log_file=str(log_file),
                enable_console=False,
                enable_file=True,
            )

            logger = get_logger("file_test")
            logger.info("File creation test message")

            # Check file exists and has content
            assert log_file.exists()
            assert log_file.stat().st_size > 0

    def test_log_directory_creation(self):
        """Test that log directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "subdir" / "dir_test.log"

            # Directory doesn't exist yet
            assert not log_file.parent.exists()

            setup_logging(
                log_file=str(log_file),
                enable_console=False,
                enable_file=True,
            )

            logger = get_logger("dir_test")
            logger.info("Directory creation test")

            # Directory should be created
            assert log_file.parent.exists()
            assert log_file.exists()


class TestLoggingLevels:
    """Test different logging levels."""

    def test_logging_levels(self):
        """Test that all logging levels work."""
        logger = get_logger("level_test")

        # Test all standard levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

    def test_log_level_filtering(self):
        """Test that log level filtering works."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "level_filter_test.log"

            # Set up logging at WARNING level
            setup_logging(
                log_level="WARNING",
                log_file=str(log_file),
                enable_console=False,
                enable_file=True,
            )

            logger = get_logger("filter_test")

            # These should not appear in the file
            logger.debug("Debug message")
            logger.info("Info message")

            # These should appear
            logger.warning("Warning message")
            logger.error("Error message")

            # Read log file content
            with open(log_file, "r") as f:
                content = f.read()

            # Should contain warning/error but not debug/info
            assert "Warning message" in content
            assert "Error message" in content
            assert "Debug message" not in content
            assert "Info message" not in content


class TestLoggingEdgeCases:
    """Test edge cases and error conditions."""

    def test_logging_with_none_values(self):
        """Test logging with None values in context."""
        logger = get_logger("edge_test")
        logger.info("Message with None", none_value=None, valid_value="test")

    def test_logging_with_complex_objects(self):
        """Test logging with complex objects."""
        logger = get_logger("complex_test")

        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "tuple": (1, 2, 3),
        }

        logger.info("Complex object test", data=complex_data)

    def test_logging_unicode_characters(self):
        """Test logging with unicode characters."""
        logger = get_logger("unicode_test")
        logger.info("Unicode test: 🚀 日本語 émojis")

    def test_logging_very_long_message(self):
        """Test logging with very long messages."""
        logger = get_logger("long_test")
        long_message = "x" * 1000  # Reduced from 10000 for faster tests
        logger.info(f"Long message: {long_message}")


class TestLoggingPerformance:
    """Test logging performance characteristics."""

    def test_logging_performance_overhead(self):
        """Test that logging doesn't have excessive overhead."""
        import time

        logger = get_logger("perf_test")

        # Time a batch of log messages
        start_time = time.time()

        for i in range(100):
            logger.info(f"Performance test message {i}", iteration=i)

        duration = time.time() - start_time

        # Should complete reasonably quickly (less than 1 second for 100
        # messages)
        assert duration < 1.0

    def test_structured_logging(self):
        """Test structured logging with context."""
        logger = get_logger("structured_test")

        # Test that we can add structured data
        logger.info(
    "Structured message",
    user_id="123",
    operation="test",
     count=42)

        # Should not raise exceptions
        assert True
