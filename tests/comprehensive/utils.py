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
        timer = QTimer()
        timer.timeout.connect(app.quit)
        timer.start(milliseconds)
        app.exec()


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
        # Find file input widget
        file_input = transcribe_tab.findChild(QLineEdit)
        if file_input:
            file_input.setText(str(file_path))
            return True
        return False
    except Exception:
        return False


def add_file_to_summarize(summarize_tab, file_path: Path) -> bool:
    """Add file to summarization queue."""
    try:
        # Find file input widget
        file_input = summarize_tab.findChild(QLineEdit)
        if file_input:
            file_input.setText(str(file_path))
            return True
        return False
    except Exception:
        return False


def wait_for_completion(tab, timeout_seconds: int = 300) -> bool:
    """Wait for processing to complete."""

    def is_complete():
        # Check if processing is complete
        if hasattr(tab, "is_processing"):
            return not tab.is_processing()

        # Check output text for completion indicators
        if hasattr(tab, "output_text"):
            output = tab.output_text.toPlainText()
            return any(
                word in output.lower()
                for word in ["complete", "finished", "done", "success"]
            )

        return False

    return wait_until(is_complete, timeout_seconds)


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
