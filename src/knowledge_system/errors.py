"""
Custom exception hierarchy for Knowledge System.
Provides structured error handling with context preservation.
"""

from typing import Any, Dict, Optional


class KnowledgeSystemError(Exception):
    """Base exception for all Knowledge System errors."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        Initialize base exception.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            context: Additional context information
            cause: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.cause = cause

    def __str__(self) -> str:
        """Return formatted error message."""
        parts = [self.message]

        if self.error_code:
            parts.append(f"[{self.error_code}]")

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"({context_str})")

        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None,
        }


# Configuration and Settings Errors
class ConfigurationError(KnowledgeSystemError):
    """Raised when configuration is invalid or missing."""


class SettingsValidationError(ConfigurationError):
    """Raised when settings fail validation."""


class ConfigFileError(ConfigurationError):
    """Raised when configuration file cannot be loaded or parsed."""


# File System Errors
class FileSystemError(KnowledgeSystemError):
    """Base class for file system related errors."""


class FileNotFoundError(FileSystemError):
    """Raised when a required file is not found."""


class FilePermissionError(FileSystemError):
    """Raised when file permissions prevent access."""


class DirectoryError(FileSystemError):
    """Raised when directory operations fail."""


class FileFormatError(FileSystemError):
    """Raised when file format is invalid or unsupported."""


# Processing Errors
class ProcessingError(KnowledgeSystemError):
    """Base class for data processing errors."""


class TranscriptionError(ProcessingError):
    """Raised when audio transcription fails."""


class SummarizationError(ProcessingError):
    """Raised when text summarization fails."""


class MOCGenerationError(ProcessingError):
    """Raised when Maps-of-Content generation fails."""


class PDFProcessingError(ProcessingError):
    """Raised when PDF processing fails."""


class VideoProcessingError(ProcessingError):
    """Raised when video processing fails."""


# Network and API Errors
class NetworkError(KnowledgeSystemError):
    """Base class for network-related errors."""


class APIError(NetworkError):
    """Raised when API calls fail."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize API error with additional HTTP context."""
        full_context = context.copy() if context else {}

        if status_code:
            full_context["status_code"] = status_code
        if response_body:
            full_context["response_body"] = response_body

        super().__init__(
            message=message, error_code=error_code, context=full_context, cause=cause
        )
        self.status_code = status_code
        self.response_body = response_body


class YouTubeAPIError(APIError):
    """Raised when YouTube API operations fail."""


class LLMAPIError(APIError):
    """Raised when LLM API calls fail."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize LLM API error with provider context."""
        context = kwargs.get("context", {}).copy()

        if provider:
            context["provider"] = provider
        if model:
            context["model"] = model

        # Remove context from kwargs to avoid conflict
        if "context" in kwargs:
            del kwargs["context"]

        super().__init__(message, context=context, **kwargs)
        self.provider = provider
        self.model = model


class RateLimitError(APIError):
    """Raised when API rate limits are exceeded."""

    def __init__(
        self, message: str, retry_after: int | None = None, **kwargs: Any
    ) -> None:
        """Initialize rate limit error with retry information."""
        context = kwargs.get("context", {}).copy()

        if retry_after:
            context["retry_after"] = retry_after

        # Remove context from kwargs to avoid conflict
        if "context" in kwargs:
            del kwargs["context"]

        super().__init__(message, context=context, **kwargs)
        self.retry_after = retry_after


class AuthenticationError(APIError):
    """Raised when API authentication fails."""


# Resource and State Errors
class ResourceError(KnowledgeSystemError):
    """Base class for resource-related errors."""


class MemoryError(ResourceError):
    """Raised when memory allocation fails."""


class DiskSpaceError(ResourceError):
    """Raised when disk space is insufficient."""


class GPUError(ResourceError):
    """Raised when GPU operations fail."""


class StateError(KnowledgeSystemError):
    """Raised when application state is invalid."""


class DatabaseError(StateError):
    """Raised when database operations fail."""


# Validation and Input Errors
class ValidationError(KnowledgeSystemError):
    """Base class for validation errors."""


class InputValidationError(ValidationError):
    """Raised when user input is invalid."""

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        field_value: Any = None,
        **kwargs: Any,
    ) -> None:
        """Initialize input validation error with field context."""
        context = kwargs.get("context", {}).copy()

        if field_name:
            context["field_name"] = field_name
        if field_value is not None:
            context["field_value"] = str(field_value)

        # Remove context from kwargs to avoid conflict
        if "context" in kwargs:
            del kwargs["context"]

        super().__init__(message, context=context, **kwargs)
        self.field_name = field_name
        self.field_value = field_value


class URLValidationError(ValidationError):
    """Raised when URL format is invalid."""


class ModelValidationError(ValidationError):
    """Raised when data model validation fails."""


# Operation and Workflow Errors
class OperationError(KnowledgeSystemError):
    """Base class for operation errors."""


class WorkflowError(OperationError):
    """Raised when workflow execution fails."""


class TimeoutError(OperationError):
    """Raised when operations timeout."""

    def __init__(
        self, message: str, timeout_seconds: float | None = None, **kwargs: Any
    ) -> None:
        """Initialize timeout error with duration context."""
        context = kwargs.get("context", {}).copy()

        if timeout_seconds:
            context["timeout_seconds"] = timeout_seconds

        # Remove context from kwargs to avoid conflict
        if "context" in kwargs:
            del kwargs["context"]

        super().__init__(message, context=context, **kwargs)
        self.timeout_seconds = timeout_seconds


class CancellationError(OperationError):
    """Raised when operations are cancelled."""


class DependencyError(OperationError):
    """Raised when required dependencies are missing or incompatible."""


# Monitoring and Watch Errors
class MonitoringError(KnowledgeSystemError):
    """Base class for monitoring-related errors."""


class FileWatchError(MonitoringError):
    """Raised when file watching fails."""


class PlaylistMonitorError(MonitoringError):
    """Raised when playlist monitoring fails."""


# Utility Functions for Error Handling
def wrap_exception(
    func_name: str,
    original_exception: Exception,
    context: dict[str, Any] | None = None,
    error_type: type[KnowledgeSystemError] = KnowledgeSystemError,
) -> KnowledgeSystemError:
    """
    Wrap a generic exception in a Knowledge System exception.

    Args:
        func_name: Name of the function where error occurred
        original_exception: The original exception
        context: Additional context information
        error_type: Type of Knowledge System exception to create

    Returns:
        Wrapped Knowledge System exception
    """
    message = f"Error in {func_name}: {str(original_exception)}"
    full_context = {"function": func_name}
    if context:
        full_context.update(context)

    return error_type(message=message, context=full_context, cause=original_exception)


def handle_api_error(
    response: Any, provider: str, operation: str, context: dict[str, Any] | None = None
) -> APIError:
    """
    Handle API response errors and create appropriate exceptions.

    Args:
        response: HTTP response object
        provider: API provider name
        operation: Operation being performed
        context: Additional context

    Returns:
        Appropriate API error exception
    """
    status_code = getattr(response, "status_code", None)
    response_text = getattr(response, "text", "No response body")

    error_context = {
        "provider": provider,
        "operation": operation,
    }
    if context:
        error_context.update(context)

    message = f"API error from {provider} during {operation}"

    if status_code == 401:
        return AuthenticationError(
            message=f"Authentication failed for {provider}",
            status_code=status_code,
            response_body=response_text,
            context=error_context,
        )
    elif status_code == 429:
        return RateLimitError(
            message=f"Rate limit exceeded for {provider}",
            status_code=status_code,
            response_body=response_text,
            context=error_context,
        )
    else:
        return APIError(
            message=message,
            status_code=status_code,
            response_body=response_text,
            context=error_context,
        )


def format_error_message(
    error: Exception, include_context: bool = True, include_cause: bool = True
) -> str:
    """
    Format an error message for user display.

    Args:
        error: Exception to format
        include_context: Whether to include context information
        include_cause: Whether to include cause information

    Returns:
        Formatted error message
    """
    if isinstance(error, KnowledgeSystemError):
        message = str(error)

        if include_cause and error.cause:
            message += f"\nCaused by: {error.cause}"

        return message
    else:
        return str(error)
