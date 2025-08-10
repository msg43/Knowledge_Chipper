"""
Base processor class for Knowledge System

Base processor class for Knowledge System.
Provides abstract interface and common functionality for all processors.
"""

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..config import get_settings
from ..errors import ProcessingError, ValidationError
from ..logger import get_logger, log_performance, log_system_event
from ..utils.progress import CancellationError, CancellationToken


class ProcessorResult:
    """ Container for processor execution results."""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        metadata: dict[str, Any] | None = None,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        dry_run: bool = False,
    ) -> None:
        """
        Initialize processor result
        Initialize processor result.

        Args:
            success: Whether the processing was successful
            data: The processed data/output
            metadata: Additional metadata about the processing
            errors: List of error messages
            warnings: List of warning messages
            dry_run: If True, do not perform any real processing, just simulate
        """

        self.success = success
        self.data = data
        self.metadata = metadata or {}
        self.errors = errors or []
        self.warnings = warnings or []
        self.dry_run = dry_run
        self.timestamp = time.time()

    def __bool__(self) -> bool:
        """ Return success status when used in boolean context."""
        return self.success

    def __str__(self) -> str:
        """ String representation of the result."""
        status = "SUCCESS" if self.success else "FAILED"
        error_info = f" ({len(self.errors)} errors)" if self.errors else ""
        warning_info = f" ({len(self.warnings)} warnings)" if self.warnings else ""
        return f"ProcessorResult[{status}{error_info}{warning_info}]"

    def add_error(self, error: str) -> None:
        """ Add an error message."""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str) -> None:
        """ Add a warning message."""
        self.warnings.append(warning)


class BaseProcessor(ABC):
    """
    Abstract base class for all processors in the Knowledge System
    Abstract base class for all processors in the Knowledge System.

    Provides common functionality and defines the interface that all
    processors must implement.
    """

    def __init__(self, name: str | None = None) -> None:
        """
        Initialize the base processor
        Initialize the base processor.

        Args:
            name: Optional name for the processor (defaults to class name)
        """

        self.name = name or self.__class__.__name__
        self.logger = get_logger(f"processor.{self.name.lower()}")
        self.settings = get_settings()
        self._stats = {
            "processed_count": 0,
            "success_count": 0,
            "error_count": 0,
            "total_processing_time": 0.0,
        }

    @abstractmethod
    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        """
        Process the input data and return results
        Process the input data and return results.

        This is the main method that subclasses must implement.

        Args:
            input_data: The data to process
            dry_run: If True, do not perform any real processing, just simulate
            **kwargs: Additional processing parameters

        Returns:
            ProcessorResult containing the processing results

        Raises:
            ProcessingError: If processing fails
        """

    @abstractmethod
    def validate_input(self, input_data: Any) -> bool:
        """
        Validate that the input data is suitable for processing
        Validate that the input data is suitable for processing.

        Args:
            input_data: The data to validate

        Returns:
            True if input is valid, False otherwise

        Raises:
            ValidationError: If validation fails with specific error
        """

    @property
    @abstractmethod
    def supported_formats(self) -> list[str]:
        """ Return list of supported input formats."""

    def can_process(self, input_path: str | Path) -> bool:
        """
        Check if this processor can handle the given input
        Check if this processor can handle the given input.

        Args:
            input_path: Path to the input file or data

        Returns:
            True if processor can handle this input
        """

        path = Path(input_path)
        return path.suffix.lower() in [fmt.lower() for fmt in self.supported_formats]

    def check_cancellation(self, cancellation_token: CancellationToken | None) -> None:
        """
        Check for cancellation and pause requests
        Check for cancellation and pause requests.

        Args:
            cancellation_token: Token to check for cancellation/pause

        Raises:
            CancellationError: If operation was cancelled
        """

        if cancellation_token:
            # Check for cancellation first
            cancellation_token.throw_if_cancelled()

            # Then wait if paused (with a reasonable timeout)
            if not cancellation_token.wait_if_paused(timeout=1.0):
                # If wait_if_paused returns False, operation was cancelled while paused
                cancellation_token.throw_if_cancelled()

    def process_with_cancellation(
        self,
        input_data: Any,
        cancellation_token: CancellationToken | None = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> ProcessorResult:
        """
        Process with cancellation support
        Process with cancellation support.

        This is a wrapper around process() that adds cancellation checking.
        Processors can override this for more granular cancellation checking.

        Args:
            input_data: The data to process
            cancellation_token: Token for cancellation/pause control
            dry_run: If True, do not perform any real processing
            **kwargs: Additional processing parameters

        Returns:
            ProcessorResult containing the processing results
        """

        try:
            # Check cancellation before starting
            self.check_cancellation(cancellation_token)

            # Add cancellation token to kwargs for processors that support it
            if cancellation_token:
                kwargs["cancellation_token"] = cancellation_token

            # Call the main process method
            return self.process(input_data, dry_run=dry_run, **kwargs)

        except CancellationError as e:
            self.logger.info(f"Processing cancelled: {e}")
            return ProcessorResult(
                success=False,
                errors=[f"Processing cancelled: {e}"],
                metadata={
                    "processor": self.name,
                    "cancelled": True,
                    "cancellation_reason": str(e),
                },
                dry_run=dry_run,
            )

    def process_safe(self, input_data: Any, **kwargs: Any) -> ProcessorResult:
        """
        Safely process input data with error handling and logging
        Safely process input data with error handling and logging.

        This method wraps the abstract process() method with common
        functionality like timing, logging, and error handling.

        Args:
            input_data: The data to process
            **kwargs: Additional processing parameters

        Returns:
            ProcessorResult containing the processing results
        """

        start_time = time.time()
        cancellation_token = kwargs.get("cancellation_token")

        try:
            # Log processing start
            log_system_event(
                event="processing_started",
                component=self.name,
                status="info",
                input_type=type(input_data).__name__,
            )

            # Check for cancellation before validation
            self.check_cancellation(cancellation_token)

            # Validate input
            if not self.validate_input(input_data):
                error_msg = f"Input validation failed for {self.name}"
                self.logger.error(error_msg, input_type=type(input_data).__name__)
                self._update_stats(success=False, duration=time.time() - start_time)
                return ProcessorResult(
                    success=False,
                    errors=[error_msg],
                    metadata={
                        "processor": self.name,
                        "duration": time.time() - start_time,
                    },
                )

            # Check for cancellation after validation
            self.check_cancellation(cancellation_token)

            # Process the data with cancellation support
            result = self.process_with_cancellation(
                input_data, cancellation_token, **kwargs
            )

            # Update result metadata
            duration = time.time() - start_time
            result.metadata.update(
                {
                    "processor": self.name,
                    "duration": duration,
                    "input_type": type(input_data).__name__,
                }
            )

            # Update statistics
            self._update_stats(success=result.success, duration=duration)

            # Log completion
            status = "info" if result.success else "error"
            log_system_event(
                event="processing_completed",
                component=self.name,
                status=status,
                duration=duration,
                success=result.success,
            )

            # Log performance
            log_performance(
                operation=f"{self.name}.process",
                duration=duration,
                success=result.success,
                errors=len(result.errors),
                warnings=len(result.warnings),
            )

            return result

        except CancellationError as e:
            duration = time.time() - start_time
            self.logger.info(f"Processing cancelled for {self.name}: {e}")

            # Update statistics for cancellation
            self._update_stats(success=False, duration=duration)

            log_system_event(
                event="processing_cancelled",
                component=self.name,
                status="info",
                duration=duration,
                reason=str(e),
            )

            return ProcessorResult(
                success=False,
                errors=[f"Processing cancelled: {e}"],
                metadata={
                    "processor": self.name,
                    "duration": duration,
                    "cancelled": True,
                    "cancellation_reason": str(e),
                },
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Unexpected error in {self.name}: {str(e)}"

            self.logger.error(
                error_msg,
                exception=str(e),
                duration=duration,
                input_type=type(input_data).__name__,
            )

            self._update_stats(success=False, duration=duration)

            log_system_event(
                event="processing_failed",
                component=self.name,
                status="error",
                error=str(e),
                duration=duration,
            )

            # Wrap in ProcessingError if it's not already a known error type
            if isinstance(e, (ProcessingError, ValidationError)):
                raise
            else:
                raise ProcessingError(
                    error_msg,
                    context={
                        "processor": self.name,
                        "input_type": type(input_data).__name__,
                        "duration": duration,
                    },
                    cause=e,
                )

    def _update_stats(self, success: bool, duration: float) -> None:
        """ Update internal statistics."""
        self._stats["processed_count"] += 1
        self._stats["total_processing_time"] += duration

        if success:
            self._stats["success_count"] += 1
        else:
            self._stats["error_count"] += 1

    def get_stats(self) -> dict[str, Any]:
        """
        Get processing statistics for this processor
        Get processing statistics for this processor.

        Returns:
            Dictionary containing processing statistics
        """
        stats = self._stats.copy()

        if stats["processed_count"] > 0:
            stats["success_rate"] = stats["success_count"] / stats["processed_count"]
            stats["average_processing_time"] = (
                stats["total_processing_time"] / stats["processed_count"]
            )
        else:
            stats["success_rate"] = 0.0
            stats["average_processing_time"] = 0.0

        return stats

    def reset_stats(self) -> None:
        """ Reset processing statistics."""
        self._stats = {
            "processed_count": 0,
            "success_count": 0,
            "error_count": 0,
            "total_processing_time": 0.0,
        }
        self.logger.info(f"Statistics reset for {self.name}")

    def __str__(self) -> str:
        """ String representation of the processor."""
        return f"{self.__class__.__name__}(name={self.name})"

    def __repr__(self) -> str:
        """ Detailed string representation of the processor."""
        stats = self.get_stats()
        return (
            f"{self.__class__.__name__}("
            f"name={self.name}, "
            f"processed={stats['processed_count']}, "
            f"success_rate={stats['success_rate']:.2%})"
        )

    def process_batch(
        self,
        inputs: list[Any],
        dry_run: bool = False,
        cancellation_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> list[ProcessorResult]:
        """
        Process a batch of inputs with cancellation support
        Process a batch of inputs with cancellation support.

        Args:
            inputs: List of input data
            dry_run: If True, do not perform any real processing, just simulate
            cancellation_token: Token for cancellation/pause control
            **kwargs: Additional processing parameters

        Returns:
            List of ProcessorResult objects
        """
        results = []
        for i, input_item in enumerate(inputs):
            try:
                # Check for cancellation before each item
                self.check_cancellation(cancellation_token)

                # Process the item
                result = self.process_with_cancellation(
                    input_item,
                    cancellation_token=cancellation_token,
                    dry_run=dry_run,
                    **kwargs,
                )
                results.append(result)

            except CancellationError as e:
                # Add cancellation result for remaining items
                remaining_count = len(inputs) - i
                for _ in range(remaining_count):
                    results.append(
                        ProcessorResult(
                            success=False,
                            errors=[f"Batch processing cancelled: {e}"],
                            metadata={
                                "processor": self.name,
                                "cancelled": True,
                                "cancellation_reason": str(e),
                            },
                            dry_run=dry_run,
                        )
                    )
                break

        return results


class ProcessorRegistry:
    """ Registry for managing processor instances."""

    def __init__(self) -> None:
        """ Initialize the processor registry."""
        self._processors: dict[str, BaseProcessor] = {}
        self.logger = get_logger("processor.registry")

    def register(self, processor: BaseProcessor, name: str | None = None) -> None:
        """
        Register a processor instance
        Register a processor instance.

        Args:
            processor: The processor instance to register
            name: Optional name override (defaults to processor.name)
        """
        processor_name = name or processor.name
        processor_name = name or processor.name

        if processor_name in self._processors:
            self.logger.warning(
                f"Processor '{processor_name}' already registered, overwriting"
            )

        self._processors[processor_name] = processor
        self.logger.info(f"Registered processor: {processor_name}")

    def get(self, name: str) -> BaseProcessor | None:
        """
        Get a processor by name
        Get a processor by name.

        Args:
            name: Name of the processor

        Returns:
            Processor instance or None if not found
        """
        return self._processors.get(name)

    def list_processors(self) -> list[str]:
        """
        Get list of registered processor names
        Get list of registered processor names.

        Returns:
            List of processor names
        """
        return list(self._processors.keys())

    def unregister(self, name: str) -> bool:
        """
        Unregister a processor
        Unregister a processor.

        Args:
            name: Name of the processor to unregister

        Returns:
            True if processor was found and removed, False otherwise
        """
        if name in self._processors:
            del self._processors[name]
            self.logger.info(f"Unregistered processor: {name}")
            return True
        return False

    def clear(self) -> None:
        """ Clear all registered processors."""
        count = len(self._processors)
        self._processors.clear()
        self.logger.info(f"Cleared {count} registered processors")


# Global registry instance
_registry = ProcessorRegistry()


def get_processor_registry() -> ProcessorRegistry:
    """ Get the global processor registry."""
    return _registry
