""" Message Queue Processor for GUI.
Message Queue Processor for GUI

Handles inter-thread communication and message processing in the GUI.
"""

import queue
from collections.abc import Callable
from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ...logger import get_logger

logger = get_logger(__name__)


class Message:
    """ Represents a message in the queue."""

    def __init__(
        self, message_type: str, data: Any = None, callback: Callable | None = None
    ) -> None:
        self.type = message_type
        self.data = data
        self.callback = callback


class MessageQueueProcessor(QObject):
    """ Processes messages from a queue in the GUI thread."""

    # Signals for different message types
    status_message = pyqtSignal(str)
    error_message = pyqtSignal(str)
    progress_update = pyqtSignal(int, str)
    log_message = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.message_queue = queue.Queue()
        self.timer = QTimer()
        self.timer.timeout.connect(self._process_messages)
        self.timer.start(100)  # Process messages every 100ms

        # Message handlers
        self.handlers: dict[str, Callable] = {
            "status": self._handle_status_message,
            "error": self._handle_error_message,
            "progress": self._handle_progress_message,
            "log": self._handle_log_message,
        }

    def add_message(
        self, message_type: str, data: Any = None, callback: Callable | None = None
    ):
        """ Add a message to the queue."""
        message = Message(message_type, data, callback)
        self.message_queue.put(message)

    def _process_messages(self):
        """ Process all messages in the queue."""
        try:
            while True:
                try:
                    message = self.message_queue.get_nowait()
                    self._handle_message(message)
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"Error processing messages: {e}")

    def _handle_message(self, message: Message):
        """ Handle a single message."""
        try:
            handler = self.handlers.get(message.type)
            if handler:
                handler(message)
            elif message.callback:
                message.callback(message.data)
            else:
                logger.warning(f"No handler for message type: {message.type}")
        except Exception as e:
            logger.error(f"Error handling message {message.type}: {e}")

    def _handle_status_message(self, message: Message):
        """ Handle status messages."""
        self.status_message.emit(str(message.data))

    def _handle_error_message(self, message: Message):
        """ Handle error messages."""
        self.error_message.emit(str(message.data))

    def _handle_progress_message(self, message: Message):
        """ Handle progress update messages."""
        if isinstance(message.data, tuple) and len(message.data) == 2:
            progress, text = message.data
            self.progress_update.emit(int(progress), str(text))
        else:
            logger.warning(f"Invalid progress message data: {message.data}")

    def _handle_log_message(self, message: Message):
        """ Handle log messages."""
        self.log_message.emit(str(message.data))

    def stop(self):
        """ Stop the message processor."""
        self.timer.stop()
