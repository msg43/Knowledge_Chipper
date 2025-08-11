"""
Unified Error Handling Utilities
Unified Error Handling Utilities

Provides standardized error handling patterns across all processors to eliminate
duplicate error processing code and ensure consistent error reporting.
"""

import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

from ..errors import ProcessingError, ValidationError
from ..logger import get_logger
from ..processors.base import ProcessorResult

logger = get_logger(__name__)


class ErrorHandler:
    """ Centralized error handling for processors."""

    @staticmethod
    def create_error_result(
        error: str | Exception,
        processor_name: str = "unknown",
        context: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> ProcessorResult:
        """
        Create a standardized error ProcessorResult
        Create a standardized error ProcessorResult.

        Args:
            error: Error message or exception object
            processor_name: Name of the processor that failed
            context: Additional context information
            dry_run: Whether this was a dry run

        Returns:
            ProcessorResult with error details
        """
        if isinstance(error, Exception):
            error_msg = f"{processor_name} failed: {str(error)}"
        else:
            error_msg = f"{processor_name} failed: {error}"

        metadata = {
            "processor": processor_name,
            "error_type": (
                type(error).__name__ if isinstance(error, Exception) else "UserError"
            ),
            "timestamp": time.time(),
        }

        if context:
            metadata.update(context)

        return ProcessorResult(
            success=False,
            errors=[error_msg],
            metadata=metadata,
            dry_run=dry_run,
        )

    @staticmethod
    def create_validation_error_result(
        input_data: Any,
        processor_name: str = "unknown",
        expected_formats: list[str] | None = None,
        dry_run: bool = False,
    ) -> ProcessorResult:
        """
        Create a standardized validation error ProcessorResult
        Create a standardized validation error ProcessorResult.

        Args:
            input_data: The invalid input data
            processor_name: Name of the processor
            expected_formats: List of expected file formats
            dry_run: Whether this was a dry run

        Returns:
            ProcessorResult with validation error details
        """
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            if not path.exists():
                error_msg = f"File not found: {path}"
            elif path.is_file() and expected_formats:
                error_msg = f"Unsupported file format: {path.suffix}. Expected: {', '.join(expected_formats)}"
            else:
                error_msg = f"Invalid input file: {path}"
        else:
            error_msg = f"Invalid input type: {type(input_data).__name__}. Expected file path or string."

        return ProcessorResult(
            success=False,
            errors=[error_msg],
            metadata={
                "processor": processor_name,
                "error_type": "ValidationError",
                "input_type": type(input_data).__name__,
                "expected_formats": expected_formats or [],
                "timestamp": time.time(),
            },
            dry_run=dry_run,
        )

    @staticmethod
    def create_no_input_error_result(
        processor_name: str = "unknown",
        input_description: str = "valid input",
        dry_run: bool = False,
    ) -> ProcessorResult:
        """
        Create a standardized "no input found" error ProcessorResult
        Create a standardized "no input found" error ProcessorResult.

        Args:
            processor_name: Name of the processor
            input_description: Description of what input was expected
            dry_run: Whether this was a dry run

        Returns:
            ProcessorResult with no input error details
        """
        error_msg = f"No {input_description} found in input"

        return ProcessorResult(
            success=False,
            errors=[error_msg],
            metadata={
                "processor": processor_name,
                "error_type": "NoInputError",
                "expected_input": input_description,
                "timestamp": time.time(),
            },
            dry_run=dry_run,
        )


class YouTubeErrorHandler:
    """ Specialized error handling for YouTube-related processors."""

    ERROR_PATTERNS = {
        "proxy_auth": {
            "patterns": [
                "407 Proxy Authentication Required",
                "Proxy authentication failed",
            ],
            "message": "🔐 Proxy authentication failed: Please check your WebShare Username and Password in Settings",
            "category": "authentication",
        },
        "proxy_connection": {
            "patterns": [
                "Proxy connection failed",
                "Tunnel connection failed",
                "ProxyError",
            ],
            "message": "🌐 Proxy connection failed: WebShare proxy may be unavailable or blocked",
            "category": "network",
        },
        "bot_detection": {
            "patterns": ["Sign in to confirm you're not a bot", "bot detection"],
            "message": "🔐 Authentication required: YouTube is requiring sign-in verification",
            "category": "authentication",
        },
        "live_stream": {
            "patterns": ["live stream recording is not available"],
            "message": "❌ Video unavailable: appears to be a live stream recording that is no longer available",
            "category": "content",
        },
        "video_unavailable": {
            "patterns": [
                "Video unavailable",
                "This video is not available",
                "Private video",
                "Deleted video",
            ],
            "message": "❌ Video unavailable: video may be private, deleted, or region-restricted",
            "category": "content",
        },
        "age_restricted": {
            "patterns": ["age-restricted", "Sign in to confirm your age"],
            "message": "🔞 Age-restricted content: video requires age verification",
            "category": "access",
        },
        "geo_blocked": {
            "patterns": ["not available in your country", "geo-blocked"],
            "message": "🌍 Geographic restriction: video is not available in your region",
            "category": "access",
        },
    }

    @classmethod
    def categorize_youtube_error(cls, error_msg: str, url: str = "") -> str:
        """
        Categorize and format YouTube-specific errors for better user understanding
        Categorize and format YouTube-specific errors for better user understanding.

        Args:
            error_msg: Raw error message
            url: YouTube URL that failed (optional)

        Returns:
            User-friendly error message with emoji and clear explanation
        """
        error_msg_lower = error_msg.lower()

        for error_type, config in cls.ERROR_PATTERNS.items():
            if any(
                pattern.lower() in error_msg_lower for pattern in config["patterns"]
            ):
                formatted_msg = config["message"]
                if url:
                    formatted_msg = f"{formatted_msg} ({url})"
                return formatted_msg

        # Generic fallback
        if url:
            return f"❌ Error processing {url}: {error_msg}"
        else:
            return f"❌ YouTube processing error: {error_msg}"

    @classmethod
    def create_youtube_error_result(
        cls,
        error: str | Exception,
        processor_name: str,
        url: str = "",
        context: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> ProcessorResult:
        """
        Create a ProcessorResult with YouTube-specific error formatting
        Create a ProcessorResult with YouTube-specific error formatting.

        Args:
            error: Error message or exception
            processor_name: Name of the processor
            url: YouTube URL that failed
            context: Additional context
            dry_run: Whether this was a dry run

        Returns:
            ProcessorResult with categorized YouTube error
        """
        error_msg = str(error)
        categorized_error = cls.categorize_youtube_error(error_msg, url)

        metadata = {
            "processor": processor_name,
            "error_type": (
                type(error).__name__ if isinstance(error, Exception) else "YouTubeError"
            ),
            "url": url,
            "raw_error": error_msg,
            "timestamp": time.time(),
        }

        if context:
            metadata.update(context)

        return ProcessorResult(
            success=False,
            errors=[categorized_error],
            metadata=metadata,
            dry_run=dry_run,
        )


def with_error_handling(
    processor_name: str | None = None, error_handler: Callable | None = None
) -> Callable:
    """
    Decorator to add standardized error handling to processor methods
    Decorator to add standardized error handling to processor methods.

    Args:
        processor_name: Name of the processor (auto-detected if None)
        error_handler: Custom error handler function

    Returns:
        Decorated function with error handling
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            proc_name = processor_name or getattr(self, "name", func.__name__)

            try:
                return func(self, *args, **kwargs)
            except ValidationError as e:
                logger.error(f"Validation error in {proc_name}: {e}")
                return ErrorHandler.create_validation_error_result(
                    input_data=args[0] if args else "unknown",
                    processor_name=proc_name,
                    dry_run=kwargs.get("dry_run", False),
                )
            except ProcessingError as e:
                logger.error(f"Processing error in {proc_name}: {e}")
                return ErrorHandler.create_error_result(
                    error=e,
                    processor_name=proc_name,
                    context=getattr(e, "context", None),
                    dry_run=kwargs.get("dry_run", False),
                )
            except Exception as e:
                logger.error(f"Unexpected error in {proc_name}: {e}")

                if error_handler:
                    return error_handler(e, proc_name, *args, **kwargs)
                else:
                    return ErrorHandler.create_error_result(
                        error=e,
                        processor_name=proc_name,
                        context={
                            "input_args": len(args),
                            "input_kwargs": list(kwargs.keys()),
                        },
                        dry_run=kwargs.get("dry_run", False),
                    )

        return wrapper

    return decorator


def with_youtube_error_handling(processor_name: str | None = None) -> Callable:
    """
    Decorator specifically for YouTube processors with specialized error handling
    Decorator specifically for YouTube processors with specialized error handling.

    Args:
        processor_name: Name of the processor (auto-detected if None)

    Returns:
        Decorated function with YouTube-specific error handling
    """

    def youtube_error_handler(
        error: Any, proc_name: str, *args: Any, **kwargs: Any
    ) -> None:
        # Try to extract URL from args for better error messages
        url = ""
        if args and isinstance(args[0], str) and "youtube" in args[0].lower():
            url = args[0]

        return YouTubeErrorHandler.create_youtube_error_result(
            error=error,
            processor_name=proc_name,
            url=url,
            dry_run=kwargs.get("dry_run", False),
        )

    return with_error_handling(processor_name, youtube_error_handler)


class BatchErrorHandler:
    """ Error handling for batch processing operations."""

    @staticmethod
    def collect_batch_errors(
        results: list[ProcessorResult], operation_name: str = "batch_operation"
    ) -> dict[str, Any]:
        """
        Collect and categorize errors from a batch of ProcessorResults
        Collect and categorize errors from a batch of ProcessorResults.

        Args:
            results: List of ProcessorResult objects
            operation_name: Name of the batch operation

        Returns:
            Dictionary with error statistics and details
        """
        total_count = len(results)

        total_count = len(results)
        success_count = sum(1 for r in results if r.success)
        error_count = total_count - success_count

        # Categorize errors
        error_categories: dict[str, int] = {}
        all_errors = []

        for i, result in enumerate(results):
            if not result.success:
                for error in result.errors:
                    all_errors.append(f"Item {i+1}: {error}")

                    # Categorize by error type
                    error_type = result.metadata.get("error_type", "Unknown")
                    if error_type not in error_categories:
                        error_categories[error_type] = []
                    error_categories[error_type].append(i + 1)

        return {
            "operation": operation_name,
            "total_items": total_count,
            "successful": success_count,
            "failed": error_count,
            "success_rate": success_count / total_count if total_count > 0 else 0,
            "error_categories": error_categories,
            "all_errors": all_errors,
            "error_summary": f"{error_count}/{total_count} items failed",
        }

    @staticmethod
    def create_batch_summary_result(
        results: list[ProcessorResult],
        operation_name: str = "batch_operation",
        dry_run: bool = False,
    ) -> ProcessorResult:
        """
        Create a summary ProcessorResult for a batch operation
        Create a summary ProcessorResult for a batch operation.

        Args:
            results: List of individual ProcessorResults
            operation_name: Name of the batch operation
            dry_run: Whether this was a dry run

        Returns:
            Summary ProcessorResult with batch statistics
        """
        error_analysis = BatchErrorHandler.collect_batch_errors(results, operation_name)

        # Determine overall success (succeed if any items succeeded)
        overall_success = error_analysis["successful"] > 0

        # Collect successful data
        successful_data = [r.data for r in results if r.success and r.data is not None]

        return ProcessorResult(
            success=overall_success,
            data={
                "batch_results": successful_data,
                "statistics": error_analysis,
                "individual_results": results,
            },
            errors=(
                error_analysis["all_errors"] if error_analysis["all_errors"] else None
            ),
            metadata={
                "operation": operation_name,
                "batch_size": error_analysis["total_items"],
                "success_count": error_analysis["successful"],
                "error_count": error_analysis["failed"],
                "success_rate": error_analysis["success_rate"],
                "error_categories": error_analysis["error_categories"],
                "timestamp": time.time(),
            },
            dry_run=dry_run,
        )


# Convenience functions for common error scenarios
def file_not_found_error(
    file_path: str | Path, processor_name: str = "processor"
) -> ProcessorResult:
    """ Create a standardized file not found error."""
    return ErrorHandler.create_error_result(
        error=f"File not found: {file_path}",
        processor_name=processor_name,
        context={"file_path": str(file_path)},
    )


def unsupported_format_error(
    file_path: str | Path,
    supported_formats: list[str],
    processor_name: str = "processor",
) -> ProcessorResult:
    """ Create a standardized unsupported format error."""
    path = Path(file_path)
    return ErrorHandler.create_error_result(
        error=f"Unsupported format: {path.suffix}. Supported: {', '.join(supported_formats)}",
        processor_name=processor_name,
        context={
            "file_path": str(file_path),
            "actual_format": path.suffix,
            "supported_formats": supported_formats,
        },
    )


def network_error(
    url: str, error_msg: str, processor_name: str = "processor"
) -> ProcessorResult:
    """ Create a standardized network error."""
    return ErrorHandler.create_error_result(
        error=f"Network error accessing {url}: {error_msg}",
        processor_name=processor_name,
        context={"url": url, "network_error": error_msg},
    )
