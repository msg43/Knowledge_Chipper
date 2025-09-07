"""Rich log display component that captures and displays detailed processor logging."""

import re
import time
from typing import Any, Dict, List, Optional

from loguru import logger
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogCapture(QObject):
    """Captures loguru logs and formats them for GUI display."""

    log_captured = pyqtSignal(str, str, str)  # level, module, message

    def __init__(self):
        super().__init__()
        self.handler_id = None
        self.is_active = False

    def start_capture(self):
        """Start capturing logs."""
        if self.handler_id is not None:
            return

        self.is_active = True
        # Add a custom handler that captures logs and emits signals
        self.handler_id = logger.add(
            self._capture_handler,
            level="DEBUG",
            format="{time:HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            filter=self._should_capture_log,
            enqueue=True,
        )

    def stop_capture(self):
        """Stop capturing logs."""
        if self.handler_id is not None:
            logger.remove(self.handler_id)
            self.handler_id = None
        self.is_active = False

    def _should_capture_log(self, record):
        """Filter which logs to capture for GUI display."""
        if not self.is_active:
            return False

        # Capture logs from processors and interesting modules
        module_name = record.get("name", "")
        interesting_modules = [
            "processors",
            "whisper",
            "youtube",
            "diarization",
            "summarizer",
            "audio_processor",
            "transcribe",
        ]

        return any(mod in module_name.lower() for mod in interesting_modules)

    def _capture_handler(self, message):
        """Handler that processes captured log messages."""
        try:
            # Parse the formatted message
            record = message.record
            level = record["level"].name
            module = record.get("name", "unknown")
            formatted_message = message

            # Emit signal to GUI
            self.log_captured.emit(level, module, formatted_message)
        except Exception as e:
            # Don't break logging if there's an error
            pass


class RichLogDisplay(QFrame):
    """Rich log display that shows detailed processor information like the terminal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet(
            """
            QFrame {
                background-color: #1e1e1e;
                border: 2px solid #404040;
                border-radius: 8px;
                margin: 5px;
            }
        """
        )

        # Initialize log capture
        self.log_capture = LogCapture()
        self.log_capture.log_captured.connect(self._on_log_captured)

        # Buffer to store recent logs
        self.log_buffer: list[dict[str, Any]] = []
        self.max_buffer_size = 1000

        # Progress tracking
        self.current_file = ""
        self.processing_start_time = None
        self.last_progress_update = 0

        # Hide initially
        self.hide()
        self._setup_ui()

    def _setup_ui(self):
        """Setup the rich log display UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Create scrollable text area for logs
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: none;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.4;
            }
        """
        )

        # Set monospace font for better log formatting
        font = QFont("Courier New", 11)
        self.log_text.setFont(font)

        layout.addWidget(self.log_text)

    def start_processing(self, operation_type: str = "Processing"):
        """Start capturing logs for a processing operation."""
        self.processing_start_time = time.time()
        self.show()

        # Clear previous logs
        self.log_text.clear()
        self.log_buffer.clear()

        # Start capturing logs
        self.log_capture.start_capture()

        # Add initial message
        self._add_log_entry(
            "INFO", "gui", f"🚀 Starting {operation_type} - Rich logging enabled"
        )

    def stop_processing(self):
        """Stop capturing logs."""
        self.log_capture.stop_capture()

        # Add completion message
        if self.processing_start_time:
            elapsed = time.time() - self.processing_start_time
            self._add_log_entry(
                "INFO", "gui", f"✅ Processing completed in {elapsed:.1f}s"
            )

    def _on_log_captured(self, level: str, module: str, formatted_message: str):
        """Handle captured log message."""
        # Add to display
        self._add_log_entry(level, module, formatted_message)

    def _add_log_entry(self, level: str, module: str, message: str):
        """Add a log entry to the display with proper formatting."""
        # Clean up the message
        clean_message = self._clean_log_message(message)

        # Add to buffer
        log_entry = {
            "timestamp": time.time(),
            "level": level,
            "module": module,
            "message": clean_message,
        }
        self.log_buffer.append(log_entry)

        # Trim buffer if too large
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer = self.log_buffer[-self.max_buffer_size :]

        # Format and add to display
        self._append_formatted_log(log_entry)

    def _clean_log_message(self, message: str) -> str:
        """Clean log message for display."""
        # Remove ANSI color codes
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        cleaned = ansi_escape.sub("", message)

        # Remove extra loguru formatting if present
        # Pattern: timestamp | level | module:function:line | message
        log_pattern = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3} \| \w+ +\| [^|]+ \| (.+)$")
        match = log_pattern.match(cleaned.strip())
        if match:
            return match.group(1)

        return cleaned.strip()

    def _append_formatted_log(self, log_entry: dict[str, Any]):
        """Append formatted log entry to the display."""
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Create timestamp
        timestamp = time.strftime("%H:%M:%S", time.localtime(log_entry["timestamp"]))

        # Format level with color
        level = log_entry["level"]
        level_colors = {
            "DEBUG": "#6c757d",
            "INFO": "#28a745",
            "WARNING": "#ffc107",
            "ERROR": "#dc3545",
            "CRITICAL": "#dc3545",
        }
        level_color = level_colors.get(level, "#ffffff")

        # Create formatted text
        format_normal = QTextCharFormat()
        format_normal.setForeground(self.log_text.palette().text().color())

        format_timestamp = QTextCharFormat()
        format_timestamp.setForeground(
            self.log_text.palette().color(
                self.log_text.palette().ColorRole.PlaceholderText
            )
        )

        format_level = QTextCharFormat()
        format_level.setForeground(
            self.log_text.palette().color(self.log_text.palette().ColorRole.Highlight)
        )

        # Add the log line
        cursor.insertText(f"[{timestamp}] ", format_timestamp)
        cursor.insertText(f"{level:8} ", format_level)
        cursor.insertText(f"| {log_entry['message']}\n", format_normal)

        # Auto-scroll to bottom
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def update_current_file(self, file_path: str):
        """Update the current file being processed."""
        self.current_file = file_path

    def clear_logs(self):
        """Clear all logs."""
        self.log_text.clear()
        self.log_buffer.clear()

    def export_logs(self) -> str:
        """Export logs as plain text."""
        return "\n".join(
            f"[{time.strftime('%H:%M:%S', time.localtime(entry['timestamp']))}] "
            f"{entry['level']:8} | {entry['message']}"
            for entry in self.log_buffer
        )


class ProcessorLogIntegrator(QObject):
    """Integrates processor logging with GUI components."""

    progress_updated = pyqtSignal(str, int)  # message, percentage
    status_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.rich_display = RichLogDisplay()

        # Connect log capture to extract progress information
        self.rich_display.log_capture.log_captured.connect(self._extract_progress_info)

    def _extract_progress_info(self, level: str, module: str, message: str):
        """Extract progress information from log messages."""
        try:
            clean_msg = self.rich_display._clean_log_message(message)

            # Look for progress indicators
            progress_patterns = [
                (r"(\d+)% complete", self._extract_percentage),
                (r"Processing.*?(\d+)/(\d+)", self._extract_fraction),
                (r"Downloading.*?(\d+\.?\d*)%", self._extract_percentage),
                (r"Generated (\d+,?\d+) characters", self._extract_character_count),
            ]

            for pattern, extractor in progress_patterns:
                match = re.search(pattern, clean_msg, re.IGNORECASE)
                if match:
                    percentage = extractor(match, clean_msg)
                    if percentage is not None:
                        self.progress_updated.emit(clean_msg, percentage)
                        break

            # Emit status updates for key messages
            status_keywords = [
                "starting",
                "processing",
                "downloading",
                "converting",
                "loading",
                "transcribing",
                "analyzing",
                "extracting",
                "generating",
                "completed",
                "failed",
                "error",
                "warning",
            ]

            if any(keyword in clean_msg.lower() for keyword in status_keywords):
                self.status_updated.emit(clean_msg)

        except Exception:
            # Don't break on parsing errors
            pass

    def _extract_percentage(self, match, message: str) -> int | None:
        """Extract percentage from regex match."""
        try:
            return int(float(match.group(1)))
        except (ValueError, IndexError):
            return None

    def _extract_fraction(self, match, message: str) -> int | None:
        """Extract percentage from fraction (e.g., 3/10)."""
        try:
            current = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                return int((current / total) * 100)
        except (ValueError, IndexError, ZeroDivisionError):
            pass
        return None

    def _extract_character_count(self, match, message: str) -> int | None:
        """Extract progress from character count (completion indicator)."""
        # Character count usually indicates completion
        return 100
