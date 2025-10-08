"""Database models for HCE (Hybrid Claim Extraction) system."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Create a separate Base for HCE models to avoid conflicts
Base = declarative_base()

# Import MediaSource separately to avoid circular imports
try:
    from .models import MediaSource
except ImportError:
    # If MediaSource is not available, define a placeholder
    MediaSource = None


def extend_video_model():
    """
    Extend the MediaSource model with a relationship to episodes.

    This function adds the episodes relationship to the MediaSource model
    to support HCE functionality.
    """
    # For now, we'll skip the relationship to avoid conflicts
    # The relationship can be added later if needed
    pass


class Episode(Base):
    """Episode extracted from a media source during HCE processing."""

    __tablename__ = "episodes"
    __table_args__ = {"extend_existing": True}  # Fix for duplicate table error

    # Primary key
    episode_id = Column(String, primary_key=True)

    # Foreign key to media source
    video_id = Column(String, ForeignKey("media_sources.media_id"), nullable=False)

    # Episode metadata
    title = Column(String, nullable=False)
    subtitle = Column(String)
    description = Column(Text)

    # Processing metadata
    recorded_at = Column(String)  # ISO format datetime string
    processed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claims = relationship(
        "Claim", back_populates="episode", cascade="all, delete-orphan"
    )
    people = relationship(
        "Person", back_populates="episode", cascade="all, delete-orphan"
    )
    concepts = relationship(
        "Concept", back_populates="episode", cascade="all, delete-orphan"
    )
    jargon = relationship(
        "Jargon", back_populates="episode", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Episode(episode_id='{self.episode_id}', title='{self.title}')>"


class Claim(Base):
    """Claim extracted from an episode."""

    __tablename__ = "claims"
    __table_args__ = {"extend_existing": True}  # Fix for duplicate table error

    # Composite primary key
    episode_id = Column(String, ForeignKey("episodes.episode_id"), primary_key=True)
    claim_id = Column(String, primary_key=True)

    # Claim content
    canonical = Column(Text, nullable=False)  # The canonical form of the claim
    original_text = Column(Text)  # Original text from transcript

    # Claim metadata
    claim_type = Column(String)  # factual, causal, normative, forecast, definition
    tier = Column(String)  # A, B, C
    first_mention_ts = Column(String)  # Timestamp of first mention

    # Scores and evaluation
    scores_json = Column(
        JSON
    )  # Dictionary of various scores (importance, novelty, etc.)
    evaluator_notes = Column(Text)  # Notes from the evaluator

    # Upload tracking
    upload_status = Column(String, default="pending")  # pending, uploaded, failed
    upload_timestamp = Column(DateTime)
    upload_error = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    episode = relationship("Episode", back_populates="claims")

    def __repr__(self):
        return f"<Claim(claim_id='{self.claim_id}', tier='{self.tier}', type='{self.claim_type}')>"


class Person(Base):
    """Person mentioned in an episode."""

    __tablename__ = "people"
    __table_args__ = {"extend_existing": True}  # Fix for duplicate table error

    # Composite primary key
    episode_id = Column(String, ForeignKey("episodes.episode_id"), primary_key=True)
    person_id = Column(String, primary_key=True)

    # Person information
    name = Column(String, nullable=False)
    description = Column(Text)
    first_mention_ts = Column(String)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    episode = relationship("Episode", back_populates="people")

    def __repr__(self):
        return f"<Person(person_id='{self.person_id}', name='{self.name}')>"


class Concept(Base):
    """Mental model or concept extracted from an episode."""

    __tablename__ = "concepts"
    __table_args__ = {"extend_existing": True}  # Fix for duplicate table error

    # Composite primary key
    episode_id = Column(String, ForeignKey("episodes.episode_id"), primary_key=True)
    concept_id = Column(String, primary_key=True)

    # Concept information
    name = Column(String, nullable=False)
    description = Column(Text)
    first_mention_ts = Column(String)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    episode = relationship("Episode", back_populates="concepts")

    def __repr__(self):
        return f"<Concept(concept_id='{self.concept_id}', name='{self.name}')>"


class Jargon(Base):
    """Jargon term extracted from an episode."""

    __tablename__ = "jargon"
    __table_args__ = {"extend_existing": True}  # Fix for duplicate table error

    # Composite primary key
    episode_id = Column(String, ForeignKey("episodes.episode_id"), primary_key=True)
    jargon_id = Column(String, primary_key=True)

    # Jargon information
    term = Column(String, nullable=False)
    definition = Column(Text)
    first_mention_ts = Column(String)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    episode = relationship("Episode", back_populates="jargon")

    def __repr__(self):
        return f"<Jargon(jargon_id='{self.jargon_id}', term='{self.term}')>"
