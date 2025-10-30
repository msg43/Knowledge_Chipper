"""GUI Log Handler for capturing and forwarding logs to GUI components.

This handler captures INFO and higher level logs from the processing pipeline
and forwards them to the GUI output panel for real-time visibility.
"""

import logging
from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal


class GUILogHandler(logging.Handler, QObject):
    """Custom logging handler that emits logs as Qt signals for GUI display."""

    # Signal to emit log messages to GUI
    log_message = pyqtSignal(str)

    def __init__(self, level=logging.INFO):
        """Initialize the handler.

        Args:
            level: Minimum logging level to capture (default: INFO)
        """
        logging.Handler.__init__(self, level=level)
        QObject.__init__(self)

        # Set a formatter for clean output
        formatter = logging.Formatter("%(message)s")
        self.setFormatter(formatter)

        # Track last message to avoid duplicates
        self._last_message = None

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record as a Qt signal.

        Args:
            record: The log record to emit
        """
        try:
            # Format the message
            msg = self.format(record)

            # Skip empty messages
            if not msg or not msg.strip():
                return

            # Skip duplicate consecutive messages
            if msg == self._last_message:
                return

            self._last_message = msg

            # Filter out debug-level noise that shouldn't appear in GUI
            skip_patterns = [
                "MINER DEBUG:",
                "Exception formatting error:",
                "Exception args:",
                "Full traceback:",
                "🔒 Using structured outputs",
                "Structured JSON generation failed",
            ]

            if any(pattern in msg for pattern in skip_patterns):
                return

            # Emit the signal with the formatted message
            self.log_message.emit(msg)

        except Exception:
            # Silently fail - we don't want logging errors to break the app
            pass


class GUILogCapture:
    """Context manager for capturing logs and forwarding them to a callback.

    This is useful for capturing logs from a specific code block and forwarding
    them to a GUI component.
    """

    def __init__(
        self,
        callback: Callable[[str], None],
        logger_names: list[str] | None = None,
        level: int = logging.INFO,
    ):
        """Initialize the log capture.

        Args:
            callback: Function to call with each log message
            logger_names: List of logger names to capture (None = root logger)
            level: Minimum logging level to capture
        """
        self.callback = callback
        self.logger_names = logger_names or [""]  # Empty string = root logger
        self.level = level
        self.handlers: list[GUILogHandler] = []

    def __enter__(self):
        """Start capturing logs."""
        for logger_name in self.logger_names:
            logger = logging.getLogger(logger_name)

            # Create and configure handler
            handler = GUILogHandler(level=self.level)
            handler.log_message.connect(self.callback)

            # Add to logger
            logger.addHandler(handler)
            self.handlers.append((logger, handler))

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop capturing logs."""
        for logger, handler in self.handlers:
            logger.removeHandler(handler)
            handler.log_message.disconnect(self.callback)

        self.handlers.clear()
        return False  # Don't suppress exceptions


def install_gui_log_handler(
    callback: Callable[[str], None],
    logger_names: list[str] | None = None,
    level: int = logging.INFO,
) -> GUILogHandler:
    """Install a GUI log handler on specified loggers.

    Args:
        callback: Function to call with each log message
        logger_names: List of logger names to attach to (None = root logger)
        level: Minimum logging level to capture

    Returns:
        The installed handler (for later removal if needed)
    """
    if logger_names is None:
        logger_names = [""]  # Root logger

    handler = GUILogHandler(level=level)
    handler.log_message.connect(callback)

    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        logger.addHandler(handler)

    return handler


def remove_gui_log_handler(
    handler: GUILogHandler, logger_names: list[str] | None = None
):
    """Remove a GUI log handler from specified loggers.

    Args:
        handler: The handler to remove
        logger_names: List of logger names to remove from (None = root logger)
    """
    if logger_names is None:
        logger_names = [""]  # Root logger

    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        logger.removeHandler(handler)

    # Disconnect signal
    try:
        handler.log_message.disconnect()
    except TypeError:
        # Signal already disconnected
        pass
