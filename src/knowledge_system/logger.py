"""
Logging setup for Knowledge System.
Provides structured logging with rotation, multiple outputs, and proper formatting.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Optional, Union

from loguru import logger

from .config import get_settings


class InterceptHandler(logging.Handler):
    """Intercept standard logging records and send them to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to loguru."""
        # Get corresponding loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelname

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    log_level: str = "INFO",
    log_file: str | Path | None = None,
    log_format: str | None = None,
    rotation: str = "10 MB",
    retention: str = "1 week",
    enable_console: bool = True,
    enable_file: bool = True,
    intercept_stdlib: bool = True,
) -> None:
    """
    Set up comprehensive logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (auto-detected from settings if None)
        log_format: Custom format string (uses default if None)
        rotation: When to rotate log files
        retention: How long to keep rotated files
        enable_console: Whether to log to console
        enable_file: Whether to log to file
        intercept_stdlib: Whether to intercept standard library logging
    """
    # Remove default handler
    logger.remove()

    # Get settings for configuration
    try:
        settings = get_settings()
        if log_file is None:
            log_dir = Path(settings.paths.logs_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "knowledge_system.log"
    except Exception:
        # Fallback if settings not available
        if log_file is None:
            log_file = Path("logs/knowledge_system.log")
            log_file.parent.mkdir(parents=True, exist_ok=True)

    # Default format for structured logging
    if log_format is None:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    # Console handler
    if enable_console:
        logger.add(
            sys.stderr,
            format=log_format,
            level=log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    # File handler with rotation
    if enable_file:
        logger.add(
            str(log_file),
            format=log_format,
            level=log_level,
            rotation=rotation,
            retention=retention,
            compression="gz",
            backtrace=True,
            diagnose=True,
        )

    # Intercept standard library logging
    if intercept_stdlib:
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def get_logger(name: str = "knowledge_system") -> Any:
    """
    Get a logger instance.

    Args:
        name: Logger name (for filtering and identification)

    Returns:
        Loguru logger instance bound to the specified name
    """
    return logger.bind(name=name)


def log_exception(
    exception: Exception,
    message: str = "An error occurred",
    level: str = "ERROR",
    **kwargs: Any,
) -> None:
    """
    Log an exception with context.

    Args:
        exception: The exception to log
        message: Custom message
        level: Log level
        **kwargs: Additional context to include
    """
    logger.bind(**kwargs).opt(exception=True).log(level, f"{message}: {exception}")


def log_performance(operation: str, duration: float, **kwargs: Any) -> None:
    """
    Log performance metrics.

    Args:
        operation: Name of the operation
        duration: Duration in seconds
        **kwargs: Additional context
    """
    logger.bind(operation=operation, duration=duration, **kwargs).info(
        f"Performance: {operation} took {duration:.3f}s"
    )


def log_user_action(action: str, user_id: str | None = None, **kwargs: Any) -> None:
    """
    Log user actions for audit trail.

    Args:
        action: Description of the action
        user_id: User identifier (if available)
        **kwargs: Additional context
    """
    context = {"action": action, "user_id": user_id, **kwargs}
    logger.bind(**context).info(f"User action: {action}")


def log_system_event(
    event: str, component: str, status: str = "info", **kwargs: Any
) -> None:
    """
    Log system events.

    Args:
        event: Event description
        component: System component that generated the event
        status: Event status (info, warning, error, critical)
        **kwargs: Additional context
    """
    context = {"event": event, "component": component, "status": status, **kwargs}

    level_map = {
        "info": "INFO",
        "warning": "WARNING",
        "error": "ERROR",
        "critical": "CRITICAL",
        "debug": "DEBUG",
    }

    level = level_map.get(status.lower(), "INFO")
    logger.bind(**context).log(level, f"System event: {component} - {event}")


def configure_third_party_logging() -> None:
    """Configure logging for third-party libraries."""
    # Set specific levels for noisy libraries
    third_party_loggers = {
        "urllib3.connectionpool": "WARNING",
        "requests": "WARNING",
        "httpx": "WARNING",
        "httpcore": "WARNING",
        "openai": "WARNING",
        "anthropic": "WARNING",
        "transformers": "WARNING",
        "torch": "WARNING",
        "whisper": "INFO",
        "yt_dlp": "WARNING",
    }

    for logger_name, level in third_party_loggers.items():
        logging.getLogger(logger_name).setLevel(getattr(logging, level))


class LogContext:
    """Context manager for adding structured context to logs."""

    def __init__(self, **context: Any) -> None:
        """Initialize context manager with key-value pairs."""
        self.context = context
        self._token = None

    def __enter__(self) -> None:
        """Enter context and bind logger."""
        self._token = logger.contextualize(**self.context)
        return self._token

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        if self._token:
            self._token.__exit__(exc_type, exc_val, exc_tb)


# Initialize logging on module import
def initialize_logging() -> None:
    """Initialize logging with default configuration."""
    try:
        setup_logging()
        configure_third_party_logging()
        logger.info("Logging system initialized")
    except Exception as e:
        # Fallback to basic logging if setup fails
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logging.error(f"Failed to initialize advanced logging: {e}")


# Auto-initialize when module is imported
initialize_logging()


# Convenience functions for common log levels
def debug(message: str, **kwargs: Any) -> None:
    """Log a debug message."""
    logger.bind(**kwargs).debug(message)


def info(message: str, **kwargs: Any) -> None:
    """Log an info message."""
    logger.bind(**kwargs).info(message)


def warning(message: str, **kwargs: Any) -> None:
    """Log a warning message."""
    logger.bind(**kwargs).warning(message)


def error(message: str, **kwargs: Any) -> None:
    """Log an error message."""
    logger.bind(**kwargs).error(message)


def critical(message: str, **kwargs: Any) -> None:
    """Log a critical message."""
    logger.bind(**kwargs).critical(message)
