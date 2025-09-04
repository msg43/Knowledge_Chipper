"""
Database models for speaker identification and voice learning system.

This module defines the database schema and models for storing speaker
voice patterns, assignments, and learning history.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import os
import sys
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session

from ..logger import get_logger

logger = get_logger(__name__)

Base = declarative_base()


class SpeakerVoice(Base):
    """Database model for learned speaker voices and characteristics."""
    
    __tablename__ = 'speaker_voices'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    voice_fingerprint = Column(Text)  # JSON string of audio characteristics
    confidence_threshold = Column(Float, default=0.7)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime)
    
    # Relationships
    assignments = relationship("SpeakerAssignment", back_populates="voice")
    learning_history = relationship("SpeakerLearningHistory", back_populates="voice")
    
    def __repr__(self):
        return f"<SpeakerVoice(id={self.id}, name='{self.name}', usage_count={self.usage_count})>"
    
    @property
    def fingerprint_data(self) -> Dict[str, Any]:
        """Get voice fingerprint as dictionary."""
        if self.voice_fingerprint:
            try:
                return json.loads(self.voice_fingerprint)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in voice fingerprint for speaker {self.name}")
                return {}
        return {}
    
    @fingerprint_data.setter
    def fingerprint_data(self, data: Dict[str, Any]):
        """Set voice fingerprint from dictionary."""
        self.voice_fingerprint = json.dumps(data)


class SpeakerAssignment(Base):
    """Database model for speaker assignments in recordings."""
    
    __tablename__ = 'speaker_assignments'
    
    id = Column(Integer, primary_key=True)
    recording_path = Column(String(500), nullable=False, index=True)
    speaker_id = Column(String(50), nullable=False)  # Original ID like SPEAKER_00
    assigned_name = Column(String(255), nullable=False, index=True)
    confidence = Column(Float, default=1.0)
    user_confirmed = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Enhanced columns for sidecar file migration
    suggested_name = Column(String(255), nullable=True)  # AI suggested name
    suggestion_confidence = Column(Float, default=0.0)  # AI confidence score
    suggestion_method = Column(String(100), nullable=True)  # 'content_analysis', 'pattern_matching', 'manual'
    sample_segments_json = Column(Text, nullable=True)  # JSON array of first 5 segments
    total_duration = Column(Float, default=0.0)  # Total speaking time
    segment_count = Column(Integer, default=0)  # Number of segments
    processing_metadata_json = Column(Text, nullable=True)  # Additional metadata
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign key to speaker voice (optional)
    voice_id = Column(Integer, ForeignKey('speaker_voices.id'), nullable=True)
    voice = relationship("SpeakerVoice", back_populates="assignments")
    
    @property
    def sample_segments(self) -> List[Dict[str, Any]]:
        """Get sample segments as list of dictionaries."""
        if self.sample_segments_json:
            try:
                return json.loads(self.sample_segments_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in sample_segments for assignment {self.id}")
                return []
        return []
    
    @sample_segments.setter
    def sample_segments(self, data: List[Dict[str, Any]]):
        """Set sample segments from list of dictionaries."""
        self.sample_segments_json = json.dumps(data)
    
    @property
    def processing_metadata(self) -> Dict[str, Any]:
        """Get processing metadata as dictionary."""
        if self.processing_metadata_json:
            try:
                return json.loads(self.processing_metadata_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in processing_metadata for assignment {self.id}")
                return {}
        return {}
    
    @processing_metadata.setter
    def processing_metadata(self, data: Dict[str, Any]):
        """Set processing metadata from dictionary."""
        self.processing_metadata_json = json.dumps(data)

    def __repr__(self):
        return f"<SpeakerAssignment(id={self.id}, speaker_id='{self.speaker_id}', assigned_name='{self.assigned_name}')>"


class SpeakerLearningHistory(Base):
    """Database model for tracking learning from user corrections."""
    
    __tablename__ = 'speaker_learning_history'
    
    id = Column(Integer, primary_key=True)
    original_suggestion = Column(String(255))
    user_correction = Column(String(255), nullable=False)
    context_data = Column(Text)  # JSON string of context information
    learning_weight = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Foreign key to speaker voice
    voice_id = Column(Integer, ForeignKey('speaker_voices.id'), nullable=True)
    voice = relationship("SpeakerVoice", back_populates="learning_history")
    
    def __repr__(self):
        return f"<SpeakerLearningHistory(id={self.id}, correction='{self.user_correction}')>"
    
    @property
    def context(self) -> Dict[str, Any]:
        """Get context data as dictionary."""
        if self.context_data:
            try:
                return json.loads(self.context_data)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in context data for learning history {self.id}")
                return {}
        return {}
    
    @context.setter
    def context(self, data: Dict[str, Any]):
        """Set context data from dictionary."""
        self.context_data = json.dumps(data)


class SpeakerSession(Base):
    """Database model for tracking speaker sessions across recordings."""
    
    __tablename__ = 'speaker_sessions'
    
    id = Column(Integer, primary_key=True)
    session_name = Column(String(255), nullable=False)  # e.g., "Team Meeting 2024-01-15"
    folder_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SpeakerSession(id={self.id}, name='{self.session_name}')>"


class SpeakerProcessingSession(Base):
    """Database model for tracking speaker processing sessions and learning data."""
    
    __tablename__ = 'speaker_processing_sessions'
    
    session_id = Column(String(50), primary_key=True)
    recording_path = Column(String(500), nullable=False, index=True)
    processing_method = Column(String(100))  # 'diarization', 'manual', 'imported'
    total_speakers = Column(Integer)
    total_duration = Column(Float)
    ai_suggestions_json = Column(Text)  # All AI suggestions before user input
    user_corrections_json = Column(Text)  # What user changed from AI suggestions
    confidence_scores_json = Column(Text)  # Confidence in each assignment
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    @property
    def ai_suggestions(self) -> Dict[str, Any]:
        """Get AI suggestions as dictionary."""
        if self.ai_suggestions_json:
            try:
                return json.loads(self.ai_suggestions_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in ai_suggestions for session {self.session_id}")
                return {}
        return {}
    
    @ai_suggestions.setter
    def ai_suggestions(self, data: Dict[str, Any]):
        """Set AI suggestions from dictionary."""
        self.ai_suggestions_json = json.dumps(data)
    
    @property
    def user_corrections(self) -> Dict[str, Any]:
        """Get user corrections as dictionary."""
        if self.user_corrections_json:
            try:
                return json.loads(self.user_corrections_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in user_corrections for session {self.session_id}")
                return {}
        return {}
    
    @user_corrections.setter
    def user_corrections(self, data: Dict[str, Any]):
        """Set user corrections from dictionary."""
        self.user_corrections_json = json.dumps(data)
    
    @property
    def confidence_scores(self) -> Dict[str, float]:
        """Get confidence scores as dictionary."""
        if self.confidence_scores_json:
            try:
                return json.loads(self.confidence_scores_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in confidence_scores for session {self.session_id}")
                return {}
        return {}
    
    @confidence_scores.setter
    def confidence_scores(self, data: Dict[str, float]):
        """Set confidence scores from dictionary."""
        self.confidence_scores_json = json.dumps(data)

    def __repr__(self):
        return f"<SpeakerProcessingSession(session_id='{self.session_id}', recording_path='{self.recording_path}')>"


# Pydantic models for API/service layer
class SpeakerVoiceModel(BaseModel):
    """Pydantic model for speaker voice data."""
    
    id: Optional[int] = None
    name: str = Field(..., description="Speaker's name")
    voice_fingerprint: Dict[str, Any] = Field(default_factory=dict, description="Audio characteristics")
    confidence_threshold: float = Field(default=0.7, description="Confidence threshold for matching")
    usage_count: int = Field(default=0, description="Number of times this voice was used")
    last_used: Optional[datetime] = Field(default=None, description="Last time this voice was matched")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SpeakerAssignmentModel(BaseModel):
    """Pydantic model for speaker assignment data."""
    
    id: Optional[int] = None
    recording_path: str = Field(..., description="Path to the recording file")
    speaker_id: str = Field(..., description="Original speaker ID")
    assigned_name: str = Field(..., description="User-assigned name")
    confidence: float = Field(default=1.0, description="Confidence in assignment")
    user_confirmed: bool = Field(default=True, description="Whether user confirmed this assignment")
    voice_id: Optional[int] = Field(default=None, description="Associated voice profile ID")
    created_at: Optional[datetime] = None
    
    # Enhanced fields for sidecar file migration
    suggested_name: Optional[str] = Field(default=None, description="AI suggested name")
    suggestion_confidence: float = Field(default=0.0, description="AI confidence score")
    suggestion_method: Optional[str] = Field(default=None, description="Method used for suggestion")
    sample_segments: List[Dict[str, Any]] = Field(default_factory=list, description="Sample segments for preview")
    total_duration: float = Field(default=0.0, description="Total speaking time")
    segment_count: int = Field(default=0, description="Number of segments")
    processing_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SpeakerLearningModel(BaseModel):
    """Pydantic model for speaker learning history."""
    
    id: Optional[int] = None
    original_suggestion: Optional[str] = Field(default=None, description="Original AI suggestion")
    user_correction: str = Field(..., description="User's correction")
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Context information")
    learning_weight: float = Field(default=1.0, description="Weight for learning algorithm")
    voice_id: Optional[int] = Field(default=None, description="Associated voice profile ID")
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SpeakerProcessingSessionModel(BaseModel):
    """Pydantic model for speaker processing session data."""
    
    session_id: str = Field(..., description="Unique session identifier")
    recording_path: str = Field(..., description="Path to the recording file")
    processing_method: Optional[str] = Field(default=None, description="Processing method used")
    total_speakers: Optional[int] = Field(default=None, description="Total number of speakers")
    total_duration: Optional[float] = Field(default=None, description="Total duration of recording")
    ai_suggestions: Dict[str, Any] = Field(default_factory=dict, description="AI suggestions before user input")
    user_corrections: Dict[str, Any] = Field(default_factory=dict, description="User corrections to AI suggestions")
    confidence_scores: Dict[str, float] = Field(default_factory=dict, description="Confidence scores for assignments")
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
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
            if sys.platform == "darwin":
                return Path.home() / "Library" / "Application Support" / "KnowledgeChipper"
            elif os.name == "nt":
                appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
                return Path(appdata) / "KnowledgeChipper"
            else:
                return Path.home() / ".knowledge_chipper"

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
            logger.info(f"Resolved speaker database location: url={self.database_url} path={db_path}")
        else:
            logger.info(f"Resolved speaker database location: url={self.database_url} path=None")

        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
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
    
    def create_speaker_voice(self, voice_data: SpeakerVoiceModel) -> Optional[SpeakerVoice]:
        """Create a new speaker voice profile."""
        try:
            with self.get_session() as session:
                # Check if speaker already exists
                existing = session.query(SpeakerVoice).filter_by(name=voice_data.name).first()
                if existing:
                    logger.warning(f"Speaker voice '{voice_data.name}' already exists")
                    return existing
                
                voice = SpeakerVoice(
                    name=voice_data.name,
                    confidence_threshold=voice_data.confidence_threshold,
                    usage_count=voice_data.usage_count
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
    
    def get_speaker_voice_by_name(self, name: str) -> Optional[SpeakerVoice]:
        """Get speaker voice by name."""
        try:
            with self.get_session() as session:
                return session.query(SpeakerVoice).filter_by(name=name).first()
        except Exception as e:
            logger.error(f"Error getting speaker voice by name: {e}")
            return None
    
    def find_matching_voices(self, audio_features: Dict[str, Any], threshold: float = 0.7) -> List[SpeakerVoice]:
        """Find speaker voices matching given audio features."""
        try:
            with self.get_session() as session:
                voices = session.query(SpeakerVoice).filter(
                    SpeakerVoice.confidence_threshold <= threshold
                ).all()
                
                # TODO: Implement actual audio feature matching
                # For now, return all voices as potential matches
                return voices
                
        except Exception as e:
            logger.error(f"Error finding matching voices: {e}")
            return []
    
    def create_speaker_assignment(self, assignment_data: SpeakerAssignmentModel) -> Optional[SpeakerAssignment]:
        """Create a new speaker assignment."""
        try:
            with self.get_session() as session:
                assignment = SpeakerAssignment(
                    recording_path=assignment_data.recording_path,
                    speaker_id=assignment_data.speaker_id,
                    assigned_name=assignment_data.assigned_name,
                    confidence=assignment_data.confidence,
                    user_confirmed=assignment_data.user_confirmed,
                    voice_id=assignment_data.voice_id
                )
                
                session.add(assignment)
                session.commit()
                session.refresh(assignment)
                
                logger.info(f"Created speaker assignment: {assignment_data.speaker_id} -> {assignment_data.assigned_name}")
                return assignment
                
        except Exception as e:
            logger.error(f"Error creating speaker assignment: {e}")
            return None
    
    def get_assignments_for_recording(self, recording_path: str) -> List[SpeakerAssignment]:
        """Get all speaker assignments for a recording."""
        try:
            with self.get_session() as session:
                return session.query(SpeakerAssignment).filter_by(
                    recording_path=recording_path
                ).all()
        except Exception as e:
            logger.error(f"Error getting assignments for recording: {e}")
            return []
    
    def create_learning_entry(self, learning_data: SpeakerLearningModel) -> Optional[SpeakerLearningHistory]:
        """Create a new learning history entry."""
        try:
            with self.get_session() as session:
                learning = SpeakerLearningHistory(
                    original_suggestion=learning_data.original_suggestion,
                    user_correction=learning_data.user_correction,
                    learning_weight=learning_data.learning_weight,
                    voice_id=learning_data.voice_id
                )
                learning.context = learning_data.context_data
                
                session.add(learning)
                session.commit()
                session.refresh(learning)
                
                logger.info(f"Created learning entry: {learning_data.original_suggestion} -> {learning_data.user_correction}")
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
    
    def get_speaker_statistics(self) -> Dict[str, Any]:
        """Get statistics about speaker data."""
        try:
            with self.get_session() as session:
                voice_count = session.query(SpeakerVoice).count()
                assignment_count = session.query(SpeakerAssignment).count()
                learning_count = session.query(SpeakerLearningHistory).count()
                
                return {
                    'total_voices': voice_count,
                    'total_assignments': assignment_count,
                    'total_learning_entries': learning_count,
                    'most_used_voices': self._get_most_used_voices(session)
                }
        except Exception as e:
            logger.error(f"Error getting speaker statistics: {e}")
            return {}
    
    def _get_most_used_voices(self, session: Session, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most frequently used voice profiles."""
        try:
            voices = session.query(SpeakerVoice).order_by(
                SpeakerVoice.usage_count.desc()
            ).limit(limit).all()
            
            return [
                {
                    'name': voice.name,
                    'usage_count': voice.usage_count,
                    'last_used': voice.last_used.isoformat() if voice.last_used else None
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
                deleted = session.query(SpeakerLearningHistory).filter(
                    SpeakerLearningHistory.created_at < cutoff_date
                ).delete()
                
                session.commit()
                logger.info(f"Cleaned up {deleted} old learning entries")
                
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    # Enhanced methods for sidecar file migration
    
    def get_unconfirmed_recordings(self) -> List[str]:
        """Get list of recording paths with unconfirmed speaker assignments."""
        try:
            with self.get_session() as session:
                results = session.query(SpeakerAssignment.recording_path).filter(
                    SpeakerAssignment.user_confirmed == False
                ).distinct().all()
                return [result[0] for result in results]
        except Exception as e:
            logger.error(f"Error getting unconfirmed recordings: {e}")
            return []
    
    def get_recordings_needing_review(self) -> List[Dict]:
        """Get recordings with AI suggestions but no user confirmation."""
        try:
            with self.get_session() as session:
                assignments = session.query(SpeakerAssignment).filter(
                    SpeakerAssignment.user_confirmed == False,
                    SpeakerAssignment.suggested_name.isnot(None)
                ).all()
                
                recordings = {}
                for assignment in assignments:
                    path = assignment.recording_path
                    if path not in recordings:
                        recordings[path] = {
                            'recording_path': path,
                            'assignments': [],
                            'total_speakers': 0,
                            'total_duration': 0.0
                        }
                    
                    recordings[path]['assignments'].append({
                        'speaker_id': assignment.speaker_id,
                        'suggested_name': assignment.suggested_name,
                        'suggestion_confidence': assignment.suggestion_confidence,
                        'suggestion_method': assignment.suggestion_method,
                        'sample_segments': assignment.sample_segments
                    })
                    recordings[path]['total_speakers'] += 1
                    recordings[path]['total_duration'] += assignment.total_duration
                
                return list(recordings.values())
        except Exception as e:
            logger.error(f"Error getting recordings needing review: {e}")
            return []
    
    def get_speaker_assignment_summary(self, recording_path: str) -> Dict:
        """Get complete assignment summary with samples for a recording."""
        try:
            with self.get_session() as session:
                assignments = session.query(SpeakerAssignment).filter_by(
                    recording_path=recording_path
                ).all()
                
                if not assignments:
                    return {}
                
                summary = {
                    'recording_path': recording_path,
                    'assignments': [],
                    'user_confirmed': all(a.user_confirmed for a in assignments),
                    'total_speakers': len(assignments),
                    'total_duration': sum(a.total_duration for a in assignments),
                    'created_at': min(a.created_at for a in assignments),
                    'updated_at': max(a.updated_at for a in assignments if a.updated_at)
                }
                
                for assignment in assignments:
                    summary['assignments'].append({
                        'speaker_id': assignment.speaker_id,
                        'assigned_name': assignment.assigned_name,
                        'suggested_name': assignment.suggested_name,
                        'confidence': assignment.confidence,
                        'suggestion_confidence': assignment.suggestion_confidence,
                        'suggestion_method': assignment.suggestion_method,
                        'sample_segments': assignment.sample_segments,
                        'total_duration': assignment.total_duration,
                        'segment_count': assignment.segment_count,
                        'user_confirmed': assignment.user_confirmed
                    })
                
                return summary
        except Exception as e:
            logger.error(f"Error getting speaker assignment summary: {e}")
            return {}
    
    def create_processing_session(self, session_data: SpeakerProcessingSessionModel) -> Optional[SpeakerProcessingSession]:
        """Create a new speaker processing session."""
        try:
            with self.get_session() as session:
                processing_session = SpeakerProcessingSession(
                    session_id=session_data.session_id,
                    recording_path=session_data.recording_path,
                    processing_method=session_data.processing_method,
                    total_speakers=session_data.total_speakers,
                    total_duration=session_data.total_duration,
                    completed_at=session_data.completed_at
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
                assignment = session.query(SpeakerAssignment).filter_by(id=assignment_id).first()
                if not assignment:
                    logger.warning(f"Assignment {assignment_id} not found")
                    return False
                
                # Update fields if provided
                for field, value in kwargs.items():
                    if hasattr(assignment, field):
                        if field == 'sample_segments' and isinstance(value, list):
                            assignment.sample_segments = value
                        elif field == 'processing_metadata' and isinstance(value, dict):
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
_db_service: Optional[SpeakerDatabaseService] = None


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
