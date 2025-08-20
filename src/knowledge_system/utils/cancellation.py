"""
Cancellation Support for Long-Running Operations
Cancellation Support for Long-Running Operations

Provides thread-safe cancellation tokens for graceful operation cancellation.
"""

# Import logger for debugging
import logging
import threading

logger = logging.getLogger(__name__)


class CancellationToken:
    """Thread-safe cancellation token for graceful operation cancellation."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()
        self._paused = threading.Event()
        self._reason: str | None = None

        # Set paused to True initially (not paused)
        self._paused.set()

        logger.debug(
            f"CancellationToken created - cancelled: {self.is_cancelled()}, paused: {self.is_paused()}"
        )

    def cancel(self, reason: str = "User requested cancellation") -> None:
        """Cancel the operation with optional reason."""
        logger.info(f"CancellationToken.cancel() called with reason: {reason}")
        self._reason = reason
        self._cancelled.set()
        # Also unpause if paused, so cancelled operations don't hang
        self._paused.set()

    def pause(self) -> None:
        """Pause the operation."""
        logger.debug("CancellationToken.pause() called")
        self._paused.clear()

    def resume(self) -> None:
        """Resume the operation."""
        logger.debug("CancellationToken.resume() called")
        self._paused.set()

    def wait_if_paused(self, timeout: float | None = None) -> bool:
        """Wait if paused. Returns True if not paused/resumed, False if cancelled."""
        if self.is_cancelled():
            return False
        if not self._paused.is_set():
            # Operation is paused, wait for resume or cancellation
            return not self._cancelled.wait(timeout)
        return True

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        result = self._cancelled.is_set()
        if result:
            logger.debug(
                f"CancellationToken.is_cancelled() returning True, reason: {self._reason}"
            )
        return result

    def is_paused(self) -> bool:
        """Check if operation is paused."""
        return not self._paused.is_set()

    def throw_if_cancelled(self) -> None:
        """Raise CancellationError if cancelled."""
        if self.is_cancelled():
            raise CancellationError(self._reason or "Operation was cancelled")

    @property
    def cancellation_reason(self) -> str | None:
        """Get the cancellation reason."""
        return self._reason


class CancellationError(Exception):
    """Exception raised when an operation is cancelled."""
