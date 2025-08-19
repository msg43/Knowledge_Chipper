"""
HCE (Hybrid Claim Extractor) SQLAlchemy models for Knowledge System.

Adds claim extraction, evidence tracking, and entity resolution tables to the database.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .models import Base, JSONEncodedType


class Episode(Base):
    """Maps videos to episodes for HCE processing."""

    __tablename__ = "episodes"

    episode_id = Column(String(100), primary_key=True)
    video_id = Column(String(20), ForeignKey("videos.video_id"), unique=True)
    title = Column(Text)
    recorded_at = Column(String(20))
    inserted_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    video = relationship("Video", back_populates="episode")
    claims = relationship(
        "Claim", back_populates="episode", cascade="all, delete-orphan"
    )
    people = relationship(
        "Person", back_populates="episode", cascade="all, delete-orphan"
    )
    concepts = relationship(
        "Concept", back_populates="episode", cascade="all, delete-orphan"
    )
    jargon_terms = relationship(
        "JargonTerm", back_populates="episode", cascade="all, delete-orphan"
    )


class Claim(Base):
    """Structured claims extracted from content."""

    __tablename__ = "claims"

    episode_id = Column(
        String(100), ForeignKey("episodes.episode_id"), primary_key=True
    )
    claim_id = Column(String(100), primary_key=True)
    canonical = Column(Text, nullable=False)
    claim_type = Column(String(20))
    tier = Column(String(1))
    first_mention_ts = Column(String(20))
    scores_json = Column(JSONEncodedType, nullable=False)
    inserted_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "claim_type IN ('factual','causal','normative','forecast','definition')"
        ),
        CheckConstraint("tier IN ('A','B','C')"),
    )

    # Relationships
    episode = relationship("Episode", back_populates="claims")
    evidence_spans = relationship(
        "EvidenceSpan", back_populates="claim", cascade="all, delete-orphan"
    )
    source_relations = relationship(
        "Relation",
        foreign_keys="Relation.source_claim_id",
        back_populates="source_claim",
    )
    target_relations = relationship(
        "Relation",
        foreign_keys="Relation.target_claim_id",
        back_populates="target_claim",
    )


class EvidenceSpan(Base):
    """Evidence quotes supporting claims."""

    __tablename__ = "evidence_spans"

    episode_id = Column(
        String(100), ForeignKey("episodes.episode_id"), primary_key=True
    )
    claim_id = Column(String(100), primary_key=True)
    seq = Column(Integer, primary_key=True)
    segment_id = Column(String(100))
    t0 = Column(String(20))
    t1 = Column(String(20))
    quote = Column(Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["episode_id", "claim_id"], ["claims.episode_id", "claims.claim_id"]
        ),
    )

    # Relationships
    claim = relationship("Claim", back_populates="evidence_spans")


class Relation(Base):
    """Relationships between claims."""

    __tablename__ = "relations"

    episode_id = Column(
        String(100), ForeignKey("episodes.episode_id"), primary_key=True
    )
    source_claim_id = Column(String(100), primary_key=True)
    target_claim_id = Column(String(100), primary_key=True)
    type = Column(String(20), primary_key=True)
    strength = Column(Float)
    rationale = Column(Text)

    __table_args__ = (
        ForeignKey(
            ["episode_id", "source_claim_id"], ["claims.episode_id", "claims.claim_id"]
        ),
        ForeignKey(
            ["episode_id", "target_claim_id"], ["claims.episode_id", "claims.claim_id"]
        ),
        CheckConstraint("type IN ('supports','contradicts','depends_on','refines')"),
        CheckConstraint("strength BETWEEN 0 AND 1"),
    )

    # Relationships
    source_claim = relationship(
        "Claim",
        foreign_keys=[episode_id, source_claim_id],
        back_populates="source_relations",
    )
    target_claim = relationship(
        "Claim",
        foreign_keys=[episode_id, target_claim_id],
        back_populates="target_relations",
    )


class Person(Base):
    """People and organizations mentioned in content."""

    __tablename__ = "people"

    episode_id = Column(
        String(100), ForeignKey("episodes.episode_id"), primary_key=True
    )
    mention_id = Column(String(100), primary_key=True)
    span_segment_id = Column(String(100))
    t0 = Column(String(20))
    t1 = Column(String(20))
    surface = Column(Text, nullable=False)
    normalized = Column(Text)
    entity_type = Column(String(10), default="person")
    external_ids_json = Column(JSONEncodedType)
    confidence = Column(Float)

    __table_args__ = (CheckConstraint("entity_type IN ('person','org')"),)

    # Relationships
    episode = relationship("Episode", back_populates="people")


class Concept(Base):
    """Mental models and concepts extracted from content."""

    __tablename__ = "concepts"

    episode_id = Column(
        String(100), ForeignKey("episodes.episode_id"), primary_key=True
    )
    model_id = Column(String(100), primary_key=True)
    name = Column(Text, nullable=False)
    definition = Column(Text)
    first_mention_ts = Column(String(20))
    aliases_json = Column(JSONEncodedType)
    evidence_json = Column(JSONEncodedType)

    # Relationships
    episode = relationship("Episode", back_populates="concepts")


class JargonTerm(Base):
    """Technical jargon and specialized terms."""

    __tablename__ = "jargon"

    episode_id = Column(
        String(100), ForeignKey("episodes.episode_id"), primary_key=True
    )
    term_id = Column(String(100), primary_key=True)
    term = Column(Text, nullable=False)
    category = Column(String(50))
    definition = Column(Text)
    evidence_json = Column(JSONEncodedType)

    # Relationships
    episode = relationship("Episode", back_populates="jargon_terms")


# Add relationship to Video model
def extend_video_model():
    """Add HCE relationship to existing Video model."""
    from .models import Video

    Video.episode = relationship("Episode", back_populates="video", uselist=False)
