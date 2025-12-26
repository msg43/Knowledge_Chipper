"""
Transcript Manager Service

Manages multiple transcript versions per source with quality-based selection
and configurable priority ordering.
"""

import logging
import uuid
from typing import Any, Optional

from ..database import DatabaseService
from ..database.models import Transcript
from ..logger import get_logger

logger = get_logger(__name__)


class TranscriptManager:
    """
    Manage multiple transcripts per source.
    
    Features:
    - Store multiple transcript versions (PDF, YouTube, Whisper)
    - Select best transcript based on config priority
    - Calculate quality scores
    - Track which transcript was used for processing
    """
    
    # Default priority order (highest to lowest)
    DEFAULT_PRIORITY = [
        "pdf_provided",  # Podcaster-provided PDFs (best quality)
        "youtube_api",   # YouTube official transcripts
        "whisper",       # Whisper-generated transcripts
        "diarized",      # Diarized transcripts
    ]
    
    def __init__(
        self,
        db_service: DatabaseService = None,
        priority_list: list[str] = None
    ):
        """
        Initialize transcript manager.
        
        Args:
            db_service: Database service instance
            priority_list: Custom priority order (overrides default)
        """
        self.db_service = db_service or DatabaseService()
        self.priority_list = priority_list or self.DEFAULT_PRIORITY

    def get_best_transcript(
        self,
        source_id: str,
        priority_list: list[str] = None
    ) -> Transcript | None:
        """
        Get best available transcript for source.
        
        Priority order (from config):
        1. pdf_provided (highest quality, explicit speakers)
        2. youtube_api (good quality, no speakers)
        3. whisper (fallback, generated)
        
        Returns the first available transcript in priority order.
        
        Args:
            source_id: Source identifier
            priority_list: Optional custom priority order
        
        Returns:
            Best transcript or None if no transcripts exist
        """
        priority = priority_list or self.priority_list
        
        # Get all transcripts for source
        transcripts = self.get_transcripts_for_source(source_id)
        
        if not transcripts:
            logger.warning(f"No transcripts found for source: {source_id}")
            return None
        
        # Group by type
        transcripts_by_type = {}
        for transcript in transcripts:
            t_type = transcript.transcript_type or "unknown"
            if t_type not in transcripts_by_type:
                transcripts_by_type[t_type] = []
            transcripts_by_type[t_type].append(transcript)
        
        # Select by priority
        for transcript_type in priority:
            if transcript_type in transcripts_by_type:
                # If multiple transcripts of same type, choose highest quality
                candidates = transcripts_by_type[transcript_type]
                best = max(
                    candidates,
                    key=lambda t: t.quality_score if t.quality_score else 0.0
                )
                
                logger.info(
                    f"Selected transcript type '{transcript_type}' for source {source_id} "
                    f"(quality: {best.quality_score if best.quality_score else 'N/A'})"
                )
                
                return best
        
        # Fallback: return any transcript (highest quality)
        best_overall = max(
            transcripts,
            key=lambda t: t.quality_score if t.quality_score else 0.0
        )
        
        logger.info(
            f"No priority match, using best available transcript: "
            f"{best_overall.transcript_type} (quality: {best_overall.quality_score})"
        )
        
        return best_overall

    def get_transcripts_for_source(self, source_id: str) -> list[Transcript]:
        """Get all transcript versions for a source."""
        try:
            session = self.db_service.Session()
            transcripts = session.query(Transcript).filter(
                Transcript.source_id == source_id
            ).all()
            session.close()
            return transcripts
        except Exception as e:
            logger.error(f"Failed to get transcripts for source {source_id}: {e}")
            return []

    def get_transcript_by_type(
        self,
        source_id: str,
        transcript_type: str
    ) -> Transcript | None:
        """Get specific transcript type for source."""
        try:
            session = self.db_service.Session()
            transcript = session.query(Transcript).filter(
                Transcript.source_id == source_id,
                Transcript.transcript_type == transcript_type
            ).first()
            session.close()
            return transcript
        except Exception as e:
            logger.error(
                f"Failed to get transcript type {transcript_type} for source {source_id}: {e}"
            )
            return None

    def store_transcript(
        self,
        source_id: str,
        transcript_text: str,
        transcript_type: str,
        metadata: dict[str, Any],
        language: str = "en",
        is_manual: bool = False
    ) -> Transcript | None:
        """
        Store new transcript version.
        
        - Checks for duplicates (same type already exists)
        - Calculates quality score
        - Updates preferred_transcript_id if higher quality
        
        Args:
            source_id: Source identifier
            transcript_text: Full transcript text
            transcript_type: Type of transcript (pdf_provided, youtube_api, whisper, etc.)
            metadata: Additional metadata
            language: Language code (default: en)
            is_manual: Whether transcript is manually created
        
        Returns:
            Created transcript record or None on failure
        """
        try:
            # Check if transcript of this type already exists
            existing = self.get_transcript_by_type(source_id, transcript_type)
            if existing:
                logger.warning(
                    f"Transcript type '{transcript_type}' already exists for source {source_id}. "
                    f"Updating existing record."
                )
                # Update existing transcript
                return self._update_transcript(existing, transcript_text, metadata)
            
            # Calculate quality score from metadata
            quality_score = self.calculate_transcript_quality(metadata)
            
            # Create transcript record
            transcript_id = str(uuid.uuid4())
            
            # Prepare transcript segments
            segments = metadata.get("segments", [])
            if not segments:
                segments = [{
                    "start": "00:00",
                    "end": "00:00",
                    "text": transcript_text,
                    "duration": 0
                }]
            
            # Create transcript
            transcript = self.db_service.create_transcript(
                source_id=source_id,
                text=transcript_text,
                language=language,
                source=transcript_type,
                metadata={
                    "transcript_type": transcript_type,
                    "quality_score": quality_score,
                    "has_speaker_labels": metadata.get("has_speaker_labels", False),
                    "has_timestamps": metadata.get("has_timestamps", False),
                    "source_file_path": metadata.get("source_file_path"),
                    "extraction_metadata": metadata.get("extraction_metadata", {}),
                    **metadata
                }
            )
            
            if transcript:
                logger.info(
                    f"✅ Stored transcript type '{transcript_type}' for source {source_id} "
                    f"(quality: {quality_score:.2f})"
                )
                
                # Update preferred transcript if this is higher quality
                self._update_preferred_transcript(source_id, transcript, quality_score)
            
            return transcript
        
        except Exception as e:
            logger.error(f"Failed to store transcript: {e}", exc_info=True)
            return None

    def _update_transcript(
        self,
        transcript: Transcript,
        new_text: str,
        metadata: dict[str, Any]
    ) -> Transcript:
        """Update existing transcript record."""
        try:
            session = self.db_service.Session()
            
            transcript.transcript_text = new_text
            transcript.quality_score = self.calculate_transcript_quality(metadata)
            transcript.has_speaker_labels = metadata.get("has_speaker_labels", False)
            transcript.has_timestamps = metadata.get("has_timestamps", False)
            transcript.source_file_path = metadata.get("source_file_path")
            transcript.extraction_metadata = metadata.get("extraction_metadata", {})
            
            session.commit()
            session.close()
            
            logger.info(f"Updated transcript: {transcript.transcript_id}")
            return transcript
        
        except Exception as e:
            logger.error(f"Failed to update transcript: {e}")
            return transcript

    def _update_preferred_transcript(
        self,
        source_id: str,
        new_transcript: Transcript,
        quality_score: float
    ) -> None:
        """Update preferred transcript if new one is higher quality."""
        try:
            source = self.db_service.get_source(source_id)
            if not source:
                return
            
            # If no preferred transcript set, use this one
            if not source.preferred_transcript_id:
                self.set_preferred_transcript(source_id, new_transcript.transcript_id)
                return
            
            # Get current preferred transcript
            session = self.db_service.Session()
            current_preferred = session.query(Transcript).filter(
                Transcript.transcript_id == source.preferred_transcript_id
            ).first()
            
            if not current_preferred:
                self.set_preferred_transcript(source_id, new_transcript.transcript_id)
                session.close()
                return
            
            # Compare quality scores
            current_quality = current_preferred.quality_score or 0.0
            
            if quality_score > current_quality:
                self.set_preferred_transcript(source_id, new_transcript.transcript_id)
                logger.info(
                    f"Updated preferred transcript for {source_id}: "
                    f"{current_preferred.transcript_type} ({current_quality:.2f}) → "
                    f"{new_transcript.transcript_type} ({quality_score:.2f})"
                )
            
            session.close()
        
        except Exception as e:
            logger.error(f"Failed to update preferred transcript: {e}")

    def set_preferred_transcript(
        self,
        source_id: str,
        transcript_id: str
    ) -> bool:
        """Set which transcript to use for processing."""
        try:
            session = self.db_service.Session()
            from ..database.models import MediaSource
            
            source = session.query(MediaSource).filter(
                MediaSource.source_id == source_id
            ).first()
            
            if not source:
                logger.error(f"Source not found: {source_id}")
                session.close()
                return False
            
            source.preferred_transcript_id = transcript_id
            session.commit()
            session.close()
            
            logger.info(f"Set preferred transcript for {source_id}: {transcript_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to set preferred transcript: {e}")
            return False

    def calculate_transcript_quality(self, metadata: dict[str, Any]) -> float:
        """
        Calculate quality score for transcript.
        
        Factors:
        - Has speaker labels: +0.3
        - Has timestamps: +0.2
        - Formatting quality: +0.3
        - Length/completeness: +0.2
        
        Args:
            metadata: Transcript metadata
        
        Returns:
            Quality score (0.0 - 1.0)
        """
        score = 0.0
        
        # Speaker labels
        if metadata.get("has_speaker_labels", False):
            score += 0.3
        
        # Timestamps
        if metadata.get("has_timestamps", False):
            score += 0.2
        
        # Formatting quality (if available)
        extraction_meta = metadata.get("extraction_metadata", {})
        if extraction_meta.get("page_count", 0) > 1:
            score += 0.15
        
        # Length/completeness
        word_count = metadata.get("word_count", 0)
        if word_count > 1000:
            score += 0.2
        elif word_count > 500:
            score += 0.1
        
        # PDF provided transcripts get bonus (assumed higher quality)
        if metadata.get("transcript_type") == "pdf_provided":
            score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    def get_transcript_summary(self, source_id: str) -> dict[str, Any]:
        """
        Get summary of all transcripts for a source.
        
        Returns:
            {
                "total_transcripts": int,
                "types": list[str],
                "preferred": str,
                "quality_scores": dict[str, float]
            }
        """
        transcripts = self.get_transcripts_for_source(source_id)
        
        summary = {
            "total_transcripts": len(transcripts),
            "types": [],
            "preferred": None,
            "quality_scores": {}
        }
        
        for transcript in transcripts:
            t_type = transcript.transcript_type or "unknown"
            summary["types"].append(t_type)
            summary["quality_scores"][t_type] = transcript.quality_score or 0.0
        
        # Get preferred transcript
        try:
            source = self.db_service.get_source(source_id)
            if source and source.preferred_transcript_id:
                preferred = next(
                    (t for t in transcripts if t.transcript_id == source.preferred_transcript_id),
                    None
                )
                if preferred:
                    summary["preferred"] = preferred.transcript_type
        except Exception:
            pass
        
        return summary

