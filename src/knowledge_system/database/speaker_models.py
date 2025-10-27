"""
Speaker models - Re-exports from unified models.py for backward compatibility.

This module maintains the old import paths while using the unified Base.
The database models now live in models.py, but the service class and Pydantic
models remain here.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..logger import get_logger

# Re-export models from unified models.py
from .models import (
    Base,
    ChannelHostMapping,
    SpeakerAssignment,
    SpeakerLearningHistory,
    SpeakerProcessingSession,
    SpeakerSession,
    SpeakerVoice,
)

logger = get_logger(__name__)

__all__ = [
    "Base",
    "SpeakerVoice",
    "SpeakerAssignment",
    "SpeakerLearningHistory",
    "SpeakerSession",
    "ChannelHostMapping",
    "SpeakerProcessingSession",
    "SpeakerVoiceModel",
    "SpeakerAssignmentModel",
    "SpeakerLearningModel",
    "SpeakerProcessingSessionModel",
    "SpeakerDatabaseService",
    "get_speaker_db_service",
    "init_speaker_database",
]


# Pydantic models for API/service layer
class SpeakerVoiceModel(BaseModel):
    """Pydantic model for speaker voice data."""

    id: int | None = None
    name: str = Field(..., description="Speaker's name")
    voice_fingerprint: dict[str, Any] = Field(
        default_factory=dict, description="Audio characteristics"
    )
    confidence_threshold: float = Field(
        default=0.7, description="Confidence threshold for matching"
    )
    usage_count: int = Field(
        default=0, description="Number of times this voice was used"
    )
    last_used: datetime | None = Field(
        default=None, description="Last time this voice was matched"
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SpeakerAssignmentModel(BaseModel):
    """Pydantic model for speaker assignment data."""

    id: int | None = None
    recording_path: str = Field(..., description="Path to the recording file")
    speaker_id: str = Field(..., description="Original speaker ID")
    assigned_name: str = Field(..., description="User-assigned name")
    confidence: float = Field(default=1.0, description="Confidence in assignment")
    user_confirmed: bool = Field(
        default=True, description="Whether user confirmed this assignment"
    )
    voice_id: int | None = Field(
        default=None, description="Associated voice profile ID"
    )
    created_at: datetime | None = None

    # Enhanced fields for sidecar file migration
    suggested_name: str | None = Field(default=None, description="AI suggested name")
    suggestion_confidence: float = Field(default=0.0, description="AI confidence score")
    suggestion_method: str | None = Field(
        default=None, description="Method used for suggestion"
    )
    sample_segments: list[dict[str, Any]] = Field(
        default_factory=list, description="Sample segments for preview"
    )
    total_duration: float = Field(default=0.0, description="Total speaking time")
    segment_count: int = Field(default=0, description="Number of segments")
    processing_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SpeakerLearningModel(BaseModel):
    """Pydantic model for speaker learning history."""

    id: int | None = None
    original_suggestion: str | None = Field(
        default=None, description="Original AI suggestion"
    )
    user_correction: str = Field(..., description="User's correction")
    context_data: dict[str, Any] = Field(
        default_factory=dict, description="Context information"
    )
    learning_weight: float = Field(
        default=1.0, description="Weight for learning algorithm"
    )
    voice_id: int | None = Field(
        default=None, description="Associated voice profile ID"
    )
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class SpeakerProcessingSessionModel(BaseModel):
    """Pydantic model for speaker processing session data."""

    session_id: str = Field(..., description="Unique session identifier")
    recording_path: str = Field(..., description="Path to the recording file")
    processing_method: str | None = Field(
        default=None, description="Processing method used"
    )
    total_speakers: int | None = Field(
        default=None, description="Total number of speakers"
    )
    total_duration: float | None = Field(
        default=None, description="Total duration of recording"
    )
    ai_suggestions: dict[str, Any] = Field(
        default_factory=dict, description="AI suggestions before user input"
    )
    user_corrections: dict[str, Any] = Field(
        default_factory=dict, description="User corrections to AI suggestions"
    )
    confidence_scores: dict[str, float] = Field(
        default_factory=dict, description="Confidence scores for assignments"
    )
    created_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class SpeakerDatabaseService:
    """Service class for managing speaker database operations."""

    def __init__(self, database_url: str = "sqlite:///knowledge_system.db"):
        """Initialize the database service.

        Resolves SQLite paths to a per-user writable directory when a relative
        path is provided, mirroring the behavior of the primary DatabaseService.
        This avoids permission errors when running from /Applications.
        """

        # Resolve default/writable database path for SQLite
        resolved_url = database_url
        db_path: Path | None = None

        def _user_data_dir() -> Path:
            # Use the standard application support directory
            from ..utils.macos_paths import get_application_support_dir

            return get_application_support_dir()

        if database_url.startswith("sqlite:///"):
            raw_path = Path(database_url[10:])  # after 'sqlite:///'
            if not raw_path.is_absolute():
                # Use per-user app data directory for relative defaults
                # Keep the same filename from the URL to align with main DB by default
                filename = raw_path.name if raw_path.name else "knowledge_system.db"
                db_path = _user_data_dir() / filename
                db_path.parent.mkdir(parents=True, exist_ok=True)
                resolved_url = f"sqlite:///{db_path}"
            else:
                db_path = raw_path
                db_path.parent.mkdir(parents=True, exist_ok=True)
        elif database_url.startswith("sqlite://"):
            raw_path = Path(database_url[9:])  # after 'sqlite://'
            if not raw_path.is_absolute():
                filename = raw_path.name if raw_path.name else "knowledge_system.db"
                db_path = _user_data_dir() / filename
                db_path.parent.mkdir(parents=True, exist_ok=True)
                resolved_url = f"sqlite:///{db_path}"
            else:
                db_path = raw_path
                db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            db_path = None

        self.database_url = resolved_url
        if db_path is not None:
            logger.info(
                f"Resolved speaker database location: url={self.database_url} path={db_path}"
            )
        else:
            logger.info(
                f"Resolved speaker database location: url={self.database_url} path=None"
            )

        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Speaker database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating speaker database tables: {e}")

    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()

    def create_speaker_voice(
        self, voice_data: SpeakerVoiceModel
    ) -> SpeakerVoice | None:
        """Create a new speaker voice profile."""
        try:
            with self.get_session() as session:
                # Check if speaker already exists
                existing = (
                    session.query(SpeakerVoice).filter_by(name=voice_data.name).first()
                )
                if existing:
                    logger.warning(f"Speaker voice '{voice_data.name}' already exists")
                    return existing

                voice = SpeakerVoice(
                    name=voice_data.name,
                    confidence_threshold=voice_data.confidence_threshold,
                    usage_count=voice_data.usage_count,
                )
                voice.fingerprint_data = voice_data.voice_fingerprint

                session.add(voice)
                session.commit()
                session.refresh(voice)

                logger.info(f"Created speaker voice profile for '{voice_data.name}'")
                return voice

        except Exception as e:
            logger.error(f"Error creating speaker voice: {e}")
            return None

    def get_speaker_voice_by_name(self, name: str) -> SpeakerVoice | None:
        """Get speaker voice by name."""
        try:
            with self.get_session() as session:
                return session.query(SpeakerVoice).filter_by(name=name).first()
        except Exception as e:
            logger.error(f"Error getting speaker voice by name: {e}")
            return None

    def get_all_voices(self) -> list[SpeakerVoice]:
        """Get all speaker voice profiles."""
        try:
            with self.get_session() as session:
                return session.query(SpeakerVoice).all()
        except Exception as e:
            logger.error(f"Error getting all voices: {e}")
            return []

    def find_matching_voices(
        self, audio_features: dict[str, Any], threshold: float = 0.7
    ) -> list[tuple[SpeakerVoice, float]]:
        """
        Find speaker voices matching given audio features.

        Args:
            audio_features: Voice fingerprint dictionary with feature types
            threshold: Minimum similarity threshold for matching

        Returns:
            List of tuples (SpeakerVoice, similarity_score) sorted by similarity
        """
        try:
            import numpy as np
            from scipy.spatial.distance import cosine

            with self.get_session() as session:
                all_voices = session.query(SpeakerVoice).all()

                if not all_voices:
                    return []

                matches = []

                # Calculate similarity for each stored voice profile
                for voice in all_voices:
                    try:
                        stored_features = voice.fingerprint_data
                        if not stored_features:
                            continue

                        # Calculate weighted similarity across feature types
                        similarities = []
                        weights = {
                            "mfcc": 0.2,
                            "spectral": 0.1,
                            "prosodic": 0.1,
                            "wav2vec2": 0.3,
                            "ecapa": 0.3,
                        }

                        for feature_type, weight in weights.items():
                            if (
                                feature_type in audio_features
                                and feature_type in stored_features
                                and audio_features[feature_type]
                                and stored_features[feature_type]
                            ):
                                try:
                                    vec1 = np.array(audio_features[feature_type])
                                    vec2 = np.array(stored_features[feature_type])

                                    # Ensure same dimensionality
                                    if vec1.shape == vec2.shape:
                                        # Use cosine similarity
                                        similarity = 1 - cosine(vec1, vec2)
                                        similarities.append((similarity, weight))
                                except Exception as e:
                                    logger.debug(f"Error comparing {feature_type}: {e}")
                                    continue

                        if similarities:
                            # Weighted average similarity
                            total_weight = sum(weight for _, weight in similarities)
                            if total_weight > 0:
                                weighted_similarity = (
                                    sum(sim * weight for sim, weight in similarities)
                                    / total_weight
                                )
                                # Clamp to [0, 1]
                                weighted_similarity = max(
                                    0.0, min(1.0, weighted_similarity)
                                )

                                if weighted_similarity >= threshold:
                                    matches.append((voice, weighted_similarity))

                    except Exception as e:
                        logger.debug(f"Error processing voice {voice.name}: {e}")
                        continue

                # Sort by similarity score (highest first)
                matches.sort(key=lambda x: x[1], reverse=True)
                return matches

        except Exception as e:
            logger.error(f"Error finding matching voices: {e}")
            return []

    def create_speaker_assignment(
        self, assignment_data: SpeakerAssignmentModel
    ) -> SpeakerAssignment | None:
        """Create a new speaker assignment."""
        try:
            with self.get_session() as session:
                assignment = SpeakerAssignment(
                    recording_path=assignment_data.recording_path,
                    speaker_id=assignment_data.speaker_id,
                    assigned_name=assignment_data.assigned_name,
                    confidence=assignment_data.confidence,
                    user_confirmed=assignment_data.user_confirmed,
                    voice_id=assignment_data.voice_id,
                )

                session.add(assignment)
                session.commit()
                session.refresh(assignment)

                logger.info(
                    f"Created speaker assignment: {assignment_data.speaker_id} -> {assignment_data.assigned_name}"
                )
                return assignment

        except Exception as e:
            logger.error(f"Error creating speaker assignment: {e}")
            return None

    def get_assignments_for_recording(
        self, recording_path: str
    ) -> list[SpeakerAssignment]:
        """Get all speaker assignments for a recording with robust path matching."""
        try:
            with self.get_session() as session:
                # Try exact match first
                assignments = (
                    session.query(SpeakerAssignment)
                    .filter_by(recording_path=recording_path)
                    .all()
                )

                if assignments:
                    logger.debug(
                        f"Found {len(assignments)} assignments with exact path match"
                    )
                    return assignments

                # Try normalized absolute path
                try:
                    from pathlib import Path

                    normalized_path = str(Path(recording_path).resolve())
                    if normalized_path != recording_path:
                        assignments = (
                            session.query(SpeakerAssignment)
                            .filter_by(recording_path=normalized_path)
                            .all()
                        )
                        if assignments:
                            logger.info(
                                f"Found {len(assignments)} assignments with normalized path"
                            )
                            return assignments
                except Exception:
                    pass

                # Try filename-only matching as fallback for moved files
                from pathlib import Path

                filename = Path(recording_path).name
                if filename:
                    assignments = (
                        session.query(SpeakerAssignment)
                        .filter(SpeakerAssignment.recording_path.like(f"%{filename}"))
                        .order_by(
                            SpeakerAssignment.updated_at.desc()
                        )  # Most recent first
                        .all()
                    )

                    if assignments:
                        logger.info(
                            f"Found {len(assignments)} assignments using filename fallback: {filename}"
                        )
                        return assignments

                logger.debug(f"No assignments found for recording: {recording_path}")
                return []

        except Exception as e:
            logger.error(f"Error getting assignments for recording: {e}")
            return []

    def get_channel_host_mapping(self, channel_name: str) -> str | None:
        """Get the host name for a given channel, if we have a mapping."""
        try:
            with self.get_session() as session:
                mapping = (
                    session.query(ChannelHostMapping)
                    .filter_by(channel_name=channel_name)
                    .first()
                )
                if mapping:
                    # Increment use count
                    mapping.use_count += 1
                    session.commit()
                    logger.debug(
                        f"Found channel mapping: {channel_name} -> {mapping.host_name}"
                    )
                    return mapping.host_name
                return None
        except Exception as e:
            logger.error(f"Error getting channel mapping: {e}")
            return None

    def create_or_update_channel_mapping(
        self,
        channel_name: str,
        host_name: str,
        created_by: str = "user_correction",
        confidence: float = 1.0,
    ) -> bool:
        """Create or update a channel-to-host mapping."""
        try:
            with self.get_session() as session:
                # Check if mapping already exists
                existing = (
                    session.query(ChannelHostMapping)
                    .filter_by(channel_name=channel_name)
                    .first()
                )

                if existing:
                    # Update existing mapping
                    existing.host_name = host_name
                    existing.confidence = confidence
                    existing.created_by = created_by
                    existing.updated_at = datetime.utcnow()
                    existing.use_count += 1
                    logger.info(
                        f"Updated channel mapping: {channel_name} -> {host_name}"
                    )
                else:
                    # Create new mapping
                    mapping = ChannelHostMapping(
                        channel_name=channel_name,
                        host_name=host_name,
                        confidence=confidence,
                        created_by=created_by,
                    )
                    session.add(mapping)
                    logger.info(
                        f"Created new channel mapping: {channel_name} -> {host_name}"
                    )

                session.commit()
                return True

        except Exception as e:
            logger.error(f"Error creating/updating channel mapping: {e}")
            return False

    def get_all_channel_mappings(self) -> list[ChannelHostMapping]:
        """Get all channel-to-host mappings."""
        try:
            with self.get_session() as session:
                return (
                    session.query(ChannelHostMapping)
                    .order_by(ChannelHostMapping.use_count.desc())
                    .all()
                )
        except Exception as e:
            logger.error(f"Error getting all channel mappings: {e}")
            return []

    def create_learning_entry(
        self, learning_data: SpeakerLearningModel
    ) -> SpeakerLearningHistory | None:
        """Create a new learning history entry."""
        try:
            with self.get_session() as session:
                learning = SpeakerLearningHistory(
                    original_suggestion=learning_data.original_suggestion,
                    user_correction=learning_data.user_correction,
                    learning_weight=learning_data.learning_weight,
                    voice_id=learning_data.voice_id,
                )
                learning.context = learning_data.context_data

                session.add(learning)
                session.commit()
                session.refresh(learning)

                logger.info(
                    f"Created learning entry: {learning_data.original_suggestion} -> {learning_data.user_correction}"
                )
                return learning

        except Exception as e:
            logger.error(f"Error creating learning entry: {e}")
            return None

    def update_voice_usage(self, voice_id: int):
        """Update usage statistics for a voice profile."""
        try:
            with self.get_session() as session:
                voice = session.query(SpeakerVoice).filter_by(id=voice_id).first()
                if voice:
                    voice.usage_count += 1
                    voice.last_used = datetime.utcnow()
                    session.commit()
                    logger.debug(f"Updated usage for voice {voice_id}")
        except Exception as e:
            logger.error(f"Error updating voice usage: {e}")

    def get_speaker_statistics(self) -> dict[str, Any]:
        """Get statistics about speaker data."""
        try:
            with self.get_session() as session:
                voice_count = session.query(SpeakerVoice).count()
                assignment_count = session.query(SpeakerAssignment).count()
                learning_count = session.query(SpeakerLearningHistory).count()

                return {
                    "total_voices": voice_count,
                    "total_assignments": assignment_count,
                    "total_learning_entries": learning_count,
                    "most_used_voices": self._get_most_used_voices(session),
                }
        except Exception as e:
            logger.error(f"Error getting speaker statistics: {e}")
            return {}

    def _get_most_used_voices(
        self, session: Session, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Get most frequently used voice profiles."""
        try:
            voices = (
                session.query(SpeakerVoice)
                .order_by(SpeakerVoice.usage_count.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "name": voice.name,
                    "usage_count": voice.usage_count,
                    "last_used": (
                        voice.last_used.isoformat() if voice.last_used else None
                    ),
                }
                for voice in voices
            ]
        except Exception as e:
            logger.error(f"Error getting most used voices: {e}")
            return []

    def cleanup_old_data(self, days_old: int = 90):
        """Clean up old learning history entries."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            with self.get_session() as session:
                deleted = (
                    session.query(SpeakerLearningHistory)
                    .filter(SpeakerLearningHistory.created_at < cutoff_date)
                    .delete()
                )

                session.commit()
                logger.info(f"Cleaned up {deleted} old learning entries")

        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")

    # Enhanced methods for sidecar file migration

    def get_unconfirmed_recordings(self) -> list[str]:
        """Get list of recording paths with unconfirmed speaker assignments."""
        try:
            with self.get_session() as session:
                results = (
                    session.query(SpeakerAssignment.recording_path)
                    .filter(SpeakerAssignment.user_confirmed.is_(False))
                    .distinct()
                    .all()
                )
                return [result[0] for result in results]
        except Exception as e:
            logger.error(f"Error getting unconfirmed recordings: {e}")
            return []

    def get_recordings_needing_review(self) -> list[dict]:
        """Get recordings with AI suggestions but no user confirmation."""
        try:
            with self.get_session() as session:
                assignments = (
                    session.query(SpeakerAssignment)
                    .filter(
                        SpeakerAssignment.user_confirmed.is_(False),
                        SpeakerAssignment.suggested_name.isnot(None),
                    )
                    .all()
                )

                recordings = {}
                for assignment in assignments:
                    path = assignment.recording_path
                    if path not in recordings:
                        recordings[path] = {
                            "recording_path": path,
                            "assignments": [],
                            "total_speakers": 0,
                            "total_duration": 0.0,
                        }

                    recordings[path]["assignments"].append(
                        {
                            "speaker_id": assignment.speaker_id,
                            "suggested_name": assignment.suggested_name,
                            "suggestion_confidence": assignment.suggestion_confidence,
                            "suggestion_method": assignment.suggestion_method,
                            "sample_segments": assignment.sample_segments,
                        }
                    )
                    recordings[path]["total_speakers"] += 1
                    recordings[path]["total_duration"] += assignment.total_duration

                return list(recordings.values())
        except Exception as e:
            logger.error(f"Error getting recordings needing review: {e}")
            return []

    def get_speaker_assignment_summary(self, recording_path: str) -> dict:
        """Get complete assignment summary with samples for a recording."""
        try:
            with self.get_session() as session:
                assignments = (
                    session.query(SpeakerAssignment)
                    .filter_by(recording_path=recording_path)
                    .all()
                )

                if not assignments:
                    return {}

                summary = {
                    "recording_path": recording_path,
                    "assignments": [],
                    "user_confirmed": all(a.user_confirmed for a in assignments),
                    "total_speakers": len(assignments),
                    "total_duration": sum(a.total_duration for a in assignments),
                    "created_at": min(a.created_at for a in assignments),
                    "updated_at": max(
                        a.updated_at for a in assignments if a.updated_at
                    ),
                }

                for assignment in assignments:
                    summary["assignments"].append(
                        {
                            "speaker_id": assignment.speaker_id,
                            "assigned_name": assignment.assigned_name,
                            "suggested_name": assignment.suggested_name,
                            "confidence": assignment.confidence,
                            "suggestion_confidence": assignment.suggestion_confidence,
                            "suggestion_method": assignment.suggestion_method,
                            "sample_segments": assignment.sample_segments,
                            "total_duration": assignment.total_duration,
                            "segment_count": assignment.segment_count,
                            "user_confirmed": assignment.user_confirmed,
                        }
                    )

                return summary
        except Exception as e:
            logger.error(f"Error getting speaker assignment summary: {e}")
            return {}

    def create_processing_session(
        self, session_data: SpeakerProcessingSessionModel
    ) -> SpeakerProcessingSession | None:
        """Create a new speaker processing session."""
        try:
            with self.get_session() as session:
                processing_session = SpeakerProcessingSession(
                    session_id=session_data.session_id,
                    recording_path=session_data.recording_path,
                    processing_method=session_data.processing_method,
                    total_speakers=session_data.total_speakers,
                    total_duration=session_data.total_duration,
                    completed_at=session_data.completed_at,
                )
                processing_session.ai_suggestions = session_data.ai_suggestions
                processing_session.user_corrections = session_data.user_corrections
                processing_session.confidence_scores = session_data.confidence_scores

                session.add(processing_session)
                session.commit()
                session.refresh(processing_session)

                logger.info(f"Created processing session: {session_data.session_id}")
                return processing_session

        except Exception as e:
            logger.error(f"Error creating processing session: {e}")
            return None

    def update_assignment_with_enhancement(self, assignment_id: int, **kwargs) -> bool:
        """Update an existing assignment with enhanced data."""
        try:
            with self.get_session() as session:
                assignment = (
                    session.query(SpeakerAssignment).filter_by(id=assignment_id).first()
                )
                if not assignment:
                    logger.warning(f"Assignment {assignment_id} not found")
                    return False

                # Update fields if provided
                for field, value in kwargs.items():
                    if hasattr(assignment, field):
                        if field == "sample_segments" and isinstance(value, list):
                            assignment.sample_segments = value
                        elif field == "processing_metadata" and isinstance(value, dict):
                            assignment.processing_metadata = value
                        else:
                            setattr(assignment, field, value)

                assignment.updated_at = datetime.utcnow()
                session.commit()

                logger.info(f"Updated assignment {assignment_id} with enhanced data")
                return True

        except Exception as e:
            logger.error(f"Error updating assignment with enhancement: {e}")
            return False


# Global database service instance
_db_service: SpeakerDatabaseService | None = None


def get_speaker_db_service() -> SpeakerDatabaseService:
    """Get the global speaker database service instance."""
    global _db_service
    if _db_service is None:
        _db_service = SpeakerDatabaseService()
    return _db_service


def init_speaker_database(database_url: str = "sqlite:///knowledge_system.db"):
    """Initialize the speaker database with custom URL."""
    global _db_service
    _db_service = SpeakerDatabaseService(database_url)
    return _db_service
