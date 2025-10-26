"""
Database validation helpers for tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class DBValidator:
    def __init__(self, db_path: Path) -> None:
        self.engine: Engine = create_engine(f"sqlite:///{db_path}")

    def _fetchall(self, sql: str, **params) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            res = conn.execute(text(sql), params)
            cols = res.keys()
            return [dict(zip(cols, row)) for row in res.fetchall()]

    def job_completed(self, job_type: str) -> bool:
        rows = self._fetchall(
            "SELECT * FROM processing_jobs WHERE job_type = :jt AND status = 'completed' ORDER BY created_at DESC LIMIT 1",
            jt=job_type,
        )
        return len(rows) > 0

    def has_summary_for_video(self, video_id: str) -> bool:
        rows = self._fetchall(
            "SELECT * FROM summaries WHERE video_id = :vid ORDER BY created_at DESC LIMIT 1",
            vid=video_id,
        )
        return len(rows) > 0

    def has_transcript_for_video(self, video_id: str) -> bool:
        rows = self._fetchall(
            "SELECT * FROM transcripts WHERE video_id = :vid ORDER BY created_at DESC LIMIT 1",
            vid=video_id,
        )
        return len(rows) > 0

    def latest_generated_file(self, file_type: str) -> dict | None:
        rows = self._fetchall(
            "SELECT * FROM generated_files WHERE file_type = :ft ORDER BY created_at DESC LIMIT 1",
            ft=file_type,
        )
        return rows[0] if rows else None

    def get_all_videos(self) -> list[dict]:
        """Get all video/media records."""
        return self._fetchall("SELECT * FROM media_sources ORDER BY processed_at DESC")

    def get_transcript_for_video(self, video_id: str) -> dict | None:
        """Get transcript for video with full validation."""
        rows = self._fetchall(
            "SELECT * FROM transcripts WHERE video_id = :vid ORDER BY created_at DESC LIMIT 1",
            vid=video_id,
        )
        return rows[0] if rows else None

    def get_all_summaries(self) -> list[dict]:
        """Get all summary records."""
        return self._fetchall("SELECT * FROM summaries ORDER BY created_at DESC")

    def validate_transcript_schema(self, transcript: dict) -> list[str]:
        """Validate transcript has all required fields. Returns list of errors."""
        errors = []
        required_fields = [
            "transcript_id",
            "video_id",
            "language",
            "transcript_text",
            "transcript_segments_json",
            "created_at",
        ]
        for field in required_fields:
            if field not in transcript or transcript[field] is None:
                errors.append(f"Missing required field: {field}")

        # Validate data types
        if (
            "transcript_segments_json" in transcript
            and transcript["transcript_segments_json"]
        ):
            if not isinstance(transcript["transcript_segments_json"], (list, str)):
                errors.append("transcript_segments_json must be list or JSON string")

        return errors

    def validate_summary_schema(self, summary: dict) -> list[str]:
        """Validate summary has all required fields. Returns list of errors."""
        errors = []
        required_fields = [
            "summary_id",
            "video_id",
            "summary_text",
            "llm_provider",
            "llm_model",
            "created_at",
        ]
        for field in required_fields:
            if field not in summary or summary[field] is None:
                errors.append(f"Missing required field: {field}")

        # Validate content
        if "summary_text" in summary and not summary["summary_text"]:
            errors.append("summary_text cannot be empty")

        return errors
