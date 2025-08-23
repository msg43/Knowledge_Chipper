"""
Database models for speaker identification and voice learning system.

This module defines the database schema and models for storing speaker
voice patterns, assignments, and learning history.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
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
    
    # Foreign key to speaker voice (optional)
    voice_id = Column(Integer, ForeignKey('speaker_voices.id'), nullable=True)
    voice = relationship("SpeakerVoice", back_populates="assignments")
    
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


class SpeakerDatabaseService:
    """Service class for managing speaker database operations."""
    
    def __init__(self, database_url: str = "sqlite:///knowledge_system.db"):
        """Initialize the database service."""
        self.engine = create_engine(database_url)
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
