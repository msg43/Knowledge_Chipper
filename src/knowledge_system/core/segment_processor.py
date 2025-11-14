"""
Segment Processor

Handles transcript segment parsing, chunking, and transformation.
Extracted from System2Orchestrator to follow single responsibility principle.
"""

from typing import Any

from ..database import DatabaseService
from ..logger import get_logger
from .processing_config import CHUNKING

logger = get_logger(__name__)


class SegmentProcessor:
    """Processes transcript segments with parsing and chunking capabilities."""

    def __init__(self, db_service: DatabaseService | None = None):
        """Initialize segment processor."""
        self.db_service = db_service or DatabaseService()

    def load_segments_from_database(self, source_id: str) -> list[dict[str, Any]]:
        """
        Load segments from database for a source.

        Args:
            source_id: Source ID to load segments for

        Returns:
            List of segment dictionaries
        """
        try:
            segments = self.db_service.get_segments(source_id)
            if not segments:
                logger.warning(f"No segments found for source {source_id}")
                return []

            # Convert to dict format for processing
            segment_list = []
            for seg in segments:
                segment_list.append({
                    "id": seg.id,
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "text": seg.text,
                    "speaker": getattr(seg, "speaker", None),
                })

            logger.info(f"Loaded {len(segment_list)} segments for {source_id}")
            return segment_list

        except Exception as e:
            logger.error(f"Failed to load segments for {source_id}: {e}")
            return []

    def parse_transcript_to_segments(
        self,
        transcript_text: str,
        source_format: str = "whisper",
    ) -> list[dict[str, Any]]:
        """
        Parse transcript text into structured segments.

        Supports multiple formats:
        - whisper: [00:00:00.000 --> 00:00:05.000] Speaker: Text
        - plain: Simple text with or without timestamps

        Args:
            transcript_text: Raw transcript text
            source_format: Format of transcript ("whisper", "plain")

        Returns:
            List of segment dictionaries with start_time, end_time, text, speaker
        """
        # TODO: Implement full parsing logic (extracted from system2_orchestrator.py:1352-1517)
        # This is a placeholder for the ~165 line method to be extracted
        logger.warning("parse_transcript_to_segments() not yet fully implemented")
        return []

    def chunk_segments_by_tokens(
        self,
        segments: list[dict[str, Any]],
        max_chunk_tokens: int | None = None,
        overlap_tokens: int | None = None,
        min_chunk_tokens: int | None = None,
    ) -> list[list[dict[str, Any]]]:
        """
        Chunk segments into token-limited groups.

        Uses configuration from processing_config.CHUNKING:
        - MAX_CHUNK_TOKENS: Maximum tokens per chunk
        - OVERLAP_TOKENS: Overlap between chunks
        - MIN_CHUNK_TOKENS: Minimum chunk size

        Args:
            segments: List of segments to chunk
            max_chunk_tokens: Override max tokens (default from config)
            overlap_tokens: Override overlap (default from config)
            min_chunk_tokens: Override min tokens (default from config)

        Returns:
            List of segment chunks (each chunk is a list of segments)
        """
        # Use config defaults if not specified
        max_tokens = max_chunk_tokens or CHUNKING.MAX_CHUNK_TOKENS
        overlap = overlap_tokens or CHUNKING.OVERLAP_TOKENS
        min_tokens = min_chunk_tokens or CHUNKING.MIN_CHUNK_TOKENS

        # TODO: Implement full chunking logic (extracted from system2_orchestrator.py:1186-1350)
        # This is a placeholder for the ~164 line method to be extracted
        logger.warning("chunk_segments_by_tokens() not yet fully implemented")
        return []

    def rechunk_for_speaker_boundaries(
        self,
        segments: list[dict[str, Any]],
    ) -> list[list[dict[str, Any]]]:
        """
        Re-chunk segments respecting speaker boundaries.

        Ensures chunks don't split in the middle of a speaker's turn,
        which improves quality for speaker-attributed content.

        Args:
            segments: List of segments to chunk

        Returns:
            List of segment chunks respecting speaker boundaries
        """
        # TODO: Implement speaker-aware chunking
        logger.warning("rechunk_for_speaker_boundaries() not yet fully implemented")
        return []

    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses simple heuristic: ~4 characters per token on average.
        More accurate than word count for LLM context limits.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        return len(text) // 4

    def merge_segments(
        self,
        segments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Merge multiple segments into single segment.

        Combines text, spans timestamps, preserves speaker if consistent.

        Args:
            segments: Segments to merge

        Returns:
            Merged segment dictionary
        """
        if not segments:
            return {}

        if len(segments) == 1:
            return segments[0]

        # Merge text
        merged_text = " ".join(seg.get("text", "") for seg in segments)

        # Span timestamps
        start_time = segments[0].get("start_time", 0.0)
        end_time = segments[-1].get("end_time", 0.0)

        # Check if speaker is consistent
        speakers = {seg.get("speaker") for seg in segments if seg.get("speaker")}
        speaker = list(speakers)[0] if len(speakers) == 1 else None

        return {
            "start_time": start_time,
            "end_time": end_time,
            "text": merged_text,
            "speaker": speaker,
            "merged_count": len(segments),
        }
