"""
System 2 Enhanced Logger

Provides structured logging with error codes, job tracking,
and metrics integration per SYSTEM_2_IMPLEMENTATION_GUIDE.md.
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from loguru import logger

from .config import get_settings
from .errors import ErrorCode


class System2LogFilter:
    """Filter that adds System 2 context to log records."""

    def __init__(self):
        self.current_job_run_id: str | None = None
        self.current_component: str | None = None
        self.current_operation: str | None = None

    def __call__(self, record):
        """Add System 2 context to log record."""
        # Add System 2 fields
        record["extra"]["job_run_id"] = self.current_job_run_id
        record["extra"]["component"] = self.current_component
        record["extra"]["operation"] = self.current_operation
        record["extra"]["timestamp_ms"] = int(time.time() * 1000)

        # Add error code if present
        if hasattr(record["extra"], "error_code"):
            error_code = record["extra"]["error_code"]
            if isinstance(error_code, ErrorCode):
                record["extra"]["error_code"] = error_code.value

        return True


# Global filter instance
_system2_filter = System2LogFilter()


def get_system2_logger(name: str) -> "System2Logger":
    """
    Get a System 2 enhanced logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        System2Logger instance
    """
    return System2Logger(name)


class System2Logger:
    """
    Enhanced logger for System 2 with structured logging support.

    Features:
    - Error code integration
    - Job run ID tracking
    - Component and operation tracking
    - Structured JSON output option
    - Metrics integration
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logger.bind(logger_name=name)

    def set_context(
        self,
        job_run_id: str | None = None,
        component: str | None = None,
        operation: str | None = None,
    ):
        """Set logging context for current operation."""
        if job_run_id is not None:
            _system2_filter.current_job_run_id = job_run_id
        if component is not None:
            _system2_filter.current_component = component
        if operation is not None:
            _system2_filter.current_operation = operation

    def clear_context(self):
        """Clear logging context."""
        _system2_filter.current_job_run_id = None
        _system2_filter.current_component = None
        _system2_filter.current_operation = None

    def _log_with_context(
        self,
        level: str,
        message: str,
        error_code: ErrorCode | str | None = None,
        context: dict[str, Any] | None = None,
        **kwargs,
    ):
        """Internal method to log with System 2 context."""
        extra = kwargs.get("extra", {})

        # Add error code
        if error_code:
            if isinstance(error_code, ErrorCode):
                extra["error_code"] = error_code.value
            else:
                extra["error_code"] = error_code

        # Add custom context
        if context:
            extra["context"] = context

        # Add standard fields
        extra["component"] = _system2_filter.current_component or self.name
        extra["operation"] = _system2_filter.current_operation
        extra["job_run_id"] = _system2_filter.current_job_run_id

        kwargs["extra"] = extra

        # Use appropriate log level
        getattr(self.logger, level)(message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log_with_context("debug", message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log_with_context("info", message, **kwargs)

    def warning(
        self, message: str, error_code: ErrorCode | str | None = None, **kwargs
    ):
        """Log warning message with optional error code."""
        self._log_with_context("warning", message, error_code=error_code, **kwargs)

    def error(self, message: str, error_code: ErrorCode | str | None = None, **kwargs):
        """Log error message with optional error code."""
        self._log_with_context("error", message, error_code=error_code, **kwargs)

    def critical(
        self, message: str, error_code: ErrorCode | str | None = None, **kwargs
    ):
        """Log critical message with optional error code."""
        self._log_with_context("critical", message, error_code=error_code, **kwargs)

    def log_metric(
        self,
        metric_name: str,
        value: int | float,
        tags: dict[str, str] | None = None,
    ):
        """Log a metric value."""
        self._log_with_context(
            "info",
            f"METRIC: {metric_name}={value}",
            context={"metric": metric_name, "value": value, "tags": tags or {}},
        )

    def log_job_event(
        self,
        event_type: str,
        job_id: str,
        job_type: str,
        status: str | None = None,
        metrics: dict[str, Any] | None = None,
    ):
        """Log a job-related event."""
        self._log_with_context(
            "info",
            f"JOB_EVENT: {event_type} for {job_type} job {job_id}",
            context={
                "event_type": event_type,
                "job_id": job_id,
                "job_type": job_type,
                "status": status,
                "metrics": metrics or {},
            },
        )


def setup_system2_logging(
    log_level: str = "INFO",
    log_file: str | Path | None = None,
    enable_json: bool = False,
    enable_console: bool = True,
    enable_file: bool = True,
):
    """
    Set up System 2 enhanced logging.

    Args:
        log_level: Logging level
        log_file: Path to log file
        enable_json: Enable JSON structured output
        enable_console: Enable console output
        enable_file: Enable file output
    """
    # Remove default handlers
    logger.remove()

    # Get settings for configuration
    try:
        settings = get_settings()
        if log_file is None:
            log_dir = Path(settings.paths.logs_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "knowledge_system_s2.log"
    except Exception:
        # Fallback if settings not available
        if log_file is None:
            log_file = Path("logs/knowledge_system_s2.log")
            log_file.parent.mkdir(parents=True, exist_ok=True)

    # Format for structured logging
    if enable_json:
        # JSON format for machine parsing
        def json_formatter(record):
            """Format log record as JSON."""
            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record["level"].name,
                "component": record["extra"].get("component", record["name"]),
                "operation": record["extra"].get("operation"),
                "message": record["message"],
                "job_run_id": record["extra"].get("job_run_id"),
                "error_code": record["extra"].get("error_code"),
                "context": record["extra"].get("context", {}),
            }

            # Add exception info if present
            if record["exception"]:
                log_data["exception"] = {
                    "type": record["exception"].type.__name__,
                    "value": str(record["exception"].value),
                    "traceback": record["exception"].traceback,
                }

            return json.dumps(log_data)

        format_func = json_formatter
    else:
        # Human-readable format per TECHNICAL_SPECIFICATIONS.md
        format_func = (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} "
            "[{level}] "
            "{extra[component]}.{extra[operation]} - "
            "{message} "
            "[{extra[error_code]}] "
            "{extra[context]}"
        )

    # Add console handler
    if enable_console:
        logger.add(
            sys.stderr,
            format=format_func,
            level=log_level,
            filter=_system2_filter,
            colorize=not enable_json,
            serialize=enable_json,
        )

    # Add file handler
    if enable_file:
        logger.add(
            log_file,
            format=format_func,
            level=log_level,
            filter=_system2_filter,
            rotation="100 MB",
            retention="1 week",
            compression="zip",
            serialize=enable_json,
        )

    # Add metrics file handler for metric events
    if enable_file:
        metrics_file = log_file.parent / "metrics.jsonl"
        logger.add(
            metrics_file,
            format=json_formatter if enable_json else format_func,
            level="INFO",
            filter=lambda record: "METRIC:" in record["message"]
            or "JOB_EVENT:" in record["message"],
            rotation="50 MB",
            retention="2 weeks",
            serialize=True,
        )


# Initialize System 2 logging on import
setup_system2_logging()
