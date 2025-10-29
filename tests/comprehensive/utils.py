"""
Comprehensive Real Testing Suite - Utilities

Shared utilities for all real GUI + real data tests.
"""

import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton, QTextEdit


def create_sandbox(sandbox_path: Path) -> "TestSandbox":
    """Create isolated test sandbox with DB and output dirs."""
    sandbox_path.mkdir(parents=True, exist_ok=True)

    db_path = sandbox_path / "test.db"
    output_dir = sandbox_path / "output"
    output_dir.mkdir(exist_ok=True)

    return TestSandbox(db_path, output_dir)


class TestSandbox:
    """Test sandbox with database and output directories."""

    def __init__(self, db_path: Path, output_dir: Path):
        self.db_path = db_path
        self.output_dir = output_dir


def set_env_sandboxes(db_path: Path, output_dir: Path):
    """Set environment variables for sandbox paths."""
    os.environ["KNOWLEDGE_CHIPPER_DB_PATH"] = str(db_path)
    os.environ["KNOWLEDGE_CHIPPER_OUTPUT_DIR"] = str(output_dir)


def switch_to_tab(main_window, tab_name: str) -> bool:
    """Switch to a specific tab by name."""
    tabs = getattr(main_window, "tabs", None)
    if not tabs:
        return False

    # Find tab by name
    for i in range(tabs.count()):
        if tabs.tabText(i).lower() == tab_name.lower():
            tabs.setCurrentIndex(i)
            return True

    return False


def process_events_for(milliseconds: int):
    """Process Qt events for specified duration."""
    app = QApplication.instance()
    if app:
        # Process events multiple times during the duration
        # to ensure signals are delivered
        import time

        end_time = time.time() + (milliseconds / 1000.0)
        while time.time() < end_time:
            app.processEvents()
            time.sleep(0.01)  # Small sleep to prevent CPU spinning


def find_button_by_text(parent, text: str) -> QPushButton | None:
    """Find button by text content."""
    for child in parent.findChildren(QPushButton):
        if child.text() == text:
            return child
    return None


def wait_until(
    condition_func, timeout_seconds: int = 30, check_interval: float = 0.1
) -> bool:
    """Wait until condition is met or timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        if condition_func():
            return True
        time.sleep(check_interval)
    return False


def get_transcribe_tab(main_window):
    """Get the transcribe tab widget."""
    tabs = getattr(main_window, "tabs", None)
    if not tabs:
        return None

    for i in range(tabs.count()):
        if "transcribe" in tabs.tabText(i).lower():
            return tabs.widget(i)
    return None


def get_summarize_tab(main_window):
    """Get the summarize tab widget."""
    tabs = getattr(main_window, "tabs", None)
    if not tabs:
        return None

    for i in range(tabs.count()):
        if "summarize" in tabs.tabText(i).lower():
            return tabs.widget(i)
    return None


def add_file_to_transcribe(transcribe_tab, file_path: Path) -> bool:
    """Add file to transcription queue."""
    try:
        # Find the file list widget (QListWidget named 'transcription_files')
        from PyQt6.QtWidgets import QApplication, QListWidget

        file_list = getattr(transcribe_tab, "transcription_files", None)
        if file_list is None:
            # Try finding it as a child
            file_lists = transcribe_tab.findChildren(QListWidget)
            file_list = file_lists[0] if file_lists else None

        if file_list:
            file_list.addItem(str(file_path))
            # Process events to ensure the item is added
            app = QApplication.instance()
            if app:
                app.processEvents()
            return True
        return False
    except Exception as e:
        print(f"Error adding file to transcribe: {e}")
        import traceback

        traceback.print_exc()
        return False


def add_file_to_summarize(summarize_tab, file_path: Path) -> bool:
    """Add file to summarization queue."""
    try:
        # Find the file list widget
        from PyQt6.QtWidgets import QListWidget

        file_list = getattr(summarize_tab, "file_list", None)
        if file_list is None:
            # Try finding it as a child
            file_lists = summarize_tab.findChildren(QListWidget)
            file_list = file_lists[0] if file_lists else None

        if file_list:
            file_list.addItem(str(file_path))
            return True
        return False
    except Exception as e:
        print(f"Error adding file to summarize: {e}")
        return False


def wait_for_completion(tab, timeout_seconds: int = 300) -> bool:
    """Wait for processing to complete."""
    import time

    from PyQt6.QtWidgets import QApplication

    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        # Process events to ensure signals are delivered
        app = QApplication.instance()
        if app:
            app.processEvents()

        # Check if worker thread is running
        worker_running = False
        if hasattr(tab, "transcription_worker") and tab.transcription_worker:
            if hasattr(tab.transcription_worker, "isRunning"):
                worker_running = tab.transcription_worker.isRunning()

        # If worker is NOT running, check for completion
        if not worker_running:
            # Check output text for completion indicators
            if hasattr(tab, "output_text"):
                output = tab.output_text.toPlainText()
                completion_words = [
                    "complete",
                    "finished",
                    "done",
                    "success",
                    "✅",
                    "transcribed",
                    "saved successfully",
                ]
                if any(word in output.lower() for word in completion_words):
                    return True

            # If no completion message but worker finished, might be done
            if hasattr(tab, "transcription_worker") and tab.transcription_worker:
                if hasattr(tab.transcription_worker, "isFinished"):
                    if tab.transcription_worker.isFinished():
                        # Worker finished - check if there's any output
                        if hasattr(tab, "output_text"):
                            output = tab.output_text.toPlainText()
                            if len(output) > 100:  # Has some output
                                return True

        # Check for error indicators
        if hasattr(tab, "output_text"):
            output = tab.output_text.toPlainText()
            error_words = ["error", "failed", "❌", "exception", "critical"]
            if any(word in output.lower() for word in error_words):
                return True

        # Small sleep to prevent CPU spinning
        time.sleep(0.1)

    return False


def check_ollama_running() -> bool:
    """Check if Ollama is running."""
    try:
        import requests

        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def read_markdown_with_frontmatter(file_path: Path) -> tuple[dict[str, Any], str]:
    """Read markdown file and parse frontmatter."""
    content = file_path.read_text()

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter_text = parts[1].strip()
            body = parts[2].strip()

            # Simple YAML parsing
            frontmatter = {}
            for line in frontmatter_text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip().strip("\"'")

            return frontmatter, body

    return {}, content


class DBValidator:
    """Database validator for test results."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def get_all_videos(self) -> list:
        """Get all video records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM media_sources")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    def get_transcript_for_video(self, video_id: str) -> dict[str, Any] | None:
        """Get transcript for video."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM transcripts WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()

            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
        finally:
            conn.close()

    def get_all_summaries(self) -> list:
        """Get all summary records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM summaries")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    def validate_transcript_schema(self, transcript: dict[str, Any]) -> list:
        """Validate transcript schema."""
        errors = []

        required_fields = ["video_id", "transcript_text"]
        for field in required_fields:
            if field not in transcript:
                errors.append(f"Missing required field: {field}")

        if "transcript_text" in transcript and not transcript["transcript_text"]:
            errors.append("Transcript text is empty")

        return errors

    def validate_summary_schema(self, summary: dict[str, Any]) -> list:
        """Validate summary schema."""
        errors = []

        required_fields = ["summary_text"]
        for field in required_fields:
            if field not in summary:
                errors.append(f"Missing required field: {field}")

        if "summary_text" in summary and not summary["summary_text"]:
            errors.append("Summary text is empty")

        return errors
