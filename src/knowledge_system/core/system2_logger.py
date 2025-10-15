"""
System 2 Logger

Provides structured logging with:
- Error code taxonomy
- Job run ID correlation
- Performance metrics
- JSON output format
- Log aggregation support
"""

import json
import logging
import time
from contextvars import ContextVar
from datetime import datetime
from typing import Any

# Context variables for correlation
_job_run_id: ContextVar[str | None] = ContextVar("job_run_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class System2LogFormatter(logging.Formatter):
    """JSON formatter for System 2 structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with System 2 fields."""
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation IDs
        job_run_id = _job_run_id.get()
        if job_run_id:
            log_data["job_run_id"] = job_run_id

        request_id = _request_id.get()
        if request_id:
            log_data["request_id"] = request_id

        # Add error code if present
        if hasattr(record, "error_code"):
            log_data["error_code"] = record.error_code

        # Add metrics if present
        if hasattr(record, "metrics"):
            log_data["metrics"] = record.metrics

        # Add any extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Handle exceptions
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class System2Logger:
    """
    Enhanced logger for System 2 with structured output and correlation.

    Usage:
        logger = System2Logger(__name__)
        logger.set_job_run_id("job_run_123")

        logger.info("Processing started", metrics={"items": 100})
        logger.error("Processing failed", error_code=ErrorCode.PROCESSING_FAILED)
    """

    def __init__(self, name: str):
        """Initialize System 2 logger."""
        self.logger = logging.getLogger(name)
        self._setup_json_handler()

    def _setup_json_handler(self):
        """Set up JSON formatter if not already configured."""
        # Check if already has System2 handler
        for handler in self.logger.handlers:
            if isinstance(handler.formatter, System2LogFormatter):
                return

        # Add JSON handler
        handler = logging.StreamHandler()
        handler.setFormatter(System2LogFormatter())
        self.logger.addHandler(handler)

    def set_job_run_id(self, job_run_id: str | None):
        """Set job run ID for correlation."""
        _job_run_id.set(job_run_id)

    def set_request_id(self, request_id: str | None):
        """Set request ID for correlation."""
        _request_id.set(request_id)

    def _log_with_extras(
        self,
        level: int,
        msg: str,
        error_code: str | None = None,
        metrics: dict[str, Any] | None = None,
        **kwargs,
    ):
        """Log with System 2 extra fields."""
        extra = {}

        if error_code:
            extra["error_code"] = error_code

        if metrics:
            extra["metrics"] = metrics

        if kwargs:
            extra["extra_fields"] = kwargs

        self.logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs):
        """Log debug message."""
        self._log_with_extras(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        """Log info message."""
        self._log_with_extras(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """Log warning message."""
        self._log_with_extras(logging.WARNING, msg, **kwargs)

    def error(
        self,
        msg: str,
        error_code: str | None = None,
        exc_info: bool = False,
        **kwargs,
    ):
        """Log error message with optional error code."""
        if exc_info:
            self.logger.error(msg, exc_info=True, extra={"error_code": error_code})
        else:
            self._log_with_extras(logging.ERROR, msg, error_code=error_code, **kwargs)

    def critical(self, msg: str, error_code: str | None = None, **kwargs):
        """Log critical message."""
        self._log_with_extras(logging.CRITICAL, msg, error_code=error_code, **kwargs)

    def log_operation(
        self,
        operation: str,
        duration_ms: int | None = None,
        status: str = "success",
        **metrics,
    ):
        """Log an operation with metrics."""
        msg = f"Operation '{operation}' completed with status '{status}'"

        operation_metrics = {"operation": operation, "status": status}

        if duration_ms is not None:
            operation_metrics["duration_ms"] = duration_ms

        operation_metrics.update(metrics)

        level = logging.INFO if status == "success" else logging.WARNING
        self._log_with_extras(level, msg, metrics=operation_metrics)

    def log_llm_call(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        cost: float | None = None,
        **kwargs,
    ):
        """Log an LLM API call with metrics."""
        msg = f"LLM call to {provider}/{model}"

        metrics = {
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "duration_ms": duration_ms,
        }

        if cost is not None:
            metrics["estimated_cost_usd"] = cost

        metrics.update(kwargs)

        self._log_with_extras(logging.INFO, msg, metrics=metrics)

    def log_pipeline_stage(
        self,
        stage: str,
        input_count: int,
        output_count: int,
        duration_ms: int,
        errors: int = 0,
        **kwargs,
    ):
        """Log a pipeline stage completion."""
        msg = f"Pipeline stage '{stage}' processed {input_count} items"

        metrics = {
            "stage": stage,
            "input_count": input_count,
            "output_count": output_count,
            "duration_ms": duration_ms,
            "errors": errors,
            "success_rate": (
                (output_count - errors) / input_count if input_count > 0 else 0
            ),
        }

        metrics.update(kwargs)

        level = logging.INFO if errors == 0 else logging.WARNING
        self._log_with_extras(level, msg, metrics=metrics)


class MetricsCollector:
    """Collects and aggregates metrics for reporting."""

    def __init__(self):
        self.metrics = {}
        self.timers = {}

    def start_timer(self, name: str):
        """Start a named timer."""
        self.timers[name] = time.time()

    def stop_timer(self, name: str) -> int:
        """Stop a timer and return duration in milliseconds."""
        if name not in self.timers:
            return 0

        duration_ms = int((time.time() - self.timers[name]) * 1000)
        del self.timers[name]
        return duration_ms

    def increment(self, name: str, value: int = 1):
        """Increment a counter."""
        if name not in self.metrics:
            self.metrics[name] = 0
        self.metrics[name] += value

    def set(self, name: str, value: Any):
        """Set a metric value."""
        self.metrics[name] = value

    def get_metrics(self) -> dict[str, Any]:
        """Get all collected metrics."""
        return self.metrics.copy()

    def reset(self):
        """Reset all metrics."""
        self.metrics.clear()
        self.timers.clear()


def get_system2_logger(name: str) -> System2Logger:
    """Get a System 2 logger instance."""
    return System2Logger(name)


# Global metrics collector
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return _metrics_collector
