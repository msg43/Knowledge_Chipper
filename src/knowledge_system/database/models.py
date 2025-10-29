"""
SQLAlchemy models for Knowledge System database.

Comprehensive database schema for storing YouTube videos, transcripts, summaries,
MOC extractions, file generation tracking, processing jobs, and Bright Data sessions.
Also includes claim-centric models where claims are the fundamental unit of knowledge.
"""

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.types import TypeDecorator

# Unified Base class - all models inherit from this
Base = declarative_base()


class JSONEncodedType(TypeDecorator):
    """Custom SQLAlchemy type for storing JSON data as TEXT."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> str | None:
        """Convert Python object to JSON string for database storage."""
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value: str, dialect) -> Any:
        """Convert JSON string from database back to Python object."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value


# ============================================================================
# CORE: Sources (Attribution Layer)
# ============================================================================


class MediaSource(Base):
    """Sources: Where claims come from (attribution metadata)."""

    __tablename__ = "media_sources"

    # Primary key
    source_id = Column(String, primary_key=True)
    source_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    description = Column(Text)

    # Author/Creator info (from platform)
    uploader = Column(String)
    uploader_id = Column(String)
    author = Column(String)
    organization = Column(String)

    # Temporal metadata (from platform)
    upload_date = Column(String)
    recorded_at = Column(String)
    published_at = Column(String)

    # Platform metrics (from platform)
    duration_seconds = Column(Integer)
    view_count = Column(Integer)
    like_count = Column(Integer)
    comment_count = Column(Integer)

    # Technical metadata
    privacy_status = Column(String)
    caption_availability = Column(Boolean)
    language = Column(String)

    # Local storage paths
    thumbnail_url = Column(String)
    thumbnail_local_path = Column(String)
    audio_file_path = Column(String)

    # Audio file tracking (for partial download detection and cleanup)
    audio_downloaded = Column(Boolean, default=False)
    audio_file_size_bytes = Column(Integer)
    audio_format = Column(String)

    # Metadata completion tracking
    metadata_complete = Column(Boolean, default=False)

    # Retry tracking (for smart retry logic)
    needs_metadata_retry = Column(Boolean, default=False)
    needs_audio_retry = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime)
    first_failure_at = Column(DateTime)

    # Failure tracking (after max retries exceeded)
    max_retries_exceeded = Column(Boolean, default=False)
    failure_reason = Column(Text)

    # Processing status
    status = Column(
        String, default="pending"
    )  # 'pending', 'processing', 'completed', 'failed'
    processed_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    fetched_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    claims = relationship(
        "Claim", back_populates="source", foreign_keys="Claim.source_id"
    )
    episodes = relationship("Episode", back_populates="source", uselist=False)
    platform_categories = relationship(
        "SourcePlatformCategory", back_populates="source", cascade="all, delete-orphan"
    )
    platform_tags = relationship(
        "SourcePlatformTag", back_populates="source", cascade="all, delete-orphan"
    )
    transcripts = relationship(
        "Transcript", back_populates="video", cascade="all, delete-orphan"
    )
    summaries = relationship(
        "Summary", back_populates="video", cascade="all, delete-orphan"
    )
    moc_extractions = relationship(
        "MOCExtraction", back_populates="video", cascade="all, delete-orphan"
    )
    generated_files = relationship(
        "GeneratedFile", back_populates="video", cascade="all, delete-orphan"
    )
    bright_data_sessions = relationship(
        "BrightDataSession", back_populates="video", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('episode', 'document', 'youtube', 'pdf', 'article', 'podcast', 'rss')",
            name="ck_source_type",
        ),
    )


class Episode(Base):
    """Episodes: Segmented sources (1-to-1 with media_sources where source_type='episode')."""

    __tablename__ = "episodes"

    # Primary key
    episode_id = Column(String, primary_key=True)
    source_id = Column(
        String,
        ForeignKey("media_sources.source_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Episode-specific metadata
    title = Column(String)
    subtitle = Column(String)
    description = Column(Text)
    recorded_at = Column(String)

    # Summaries (generated by us)
    short_summary = Column(Text)
    long_summary = Column(Text)
    summary_generated_at = Column(DateTime)
    summary_generated_by_model = Column(String)

    # Summary metrics
    input_length = Column(Integer)
    output_length = Column(Integer)
    compression_ratio = Column(Float)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source = relationship("MediaSource", back_populates="episodes")
    segments = relationship(
        "Segment", back_populates="episode", cascade="all, delete-orphan"
    )
    claims = relationship(
        "Claim", back_populates="episode", foreign_keys="Claim.episode_id"
    )


class Segment(Base):
    """Segments: Temporal chunks (only for episodes)."""

    __tablename__ = "segments"

    # Primary key
    segment_id = Column(String, primary_key=True)
    episode_id = Column(
        String, ForeignKey("episodes.episode_id", ondelete="CASCADE"), nullable=False
    )

    speaker = Column(String)
    start_time = Column(String)
    end_time = Column(String)
    text = Column(Text, nullable=False)
    topic_guess = Column(String)

    sequence = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    episode = relationship("Episode", back_populates="segments")
    evidence_spans = relationship("EvidenceSpan", back_populates="segment")


class Transcript(Base):
    """Transcript data with support for multiple versions per video."""

    __tablename__ = "transcripts"

    # Primary key
    transcript_id = Column(String(50), primary_key=True)
    video_id = Column(String(20), ForeignKey("media_sources.source_id"), nullable=False)

    # Transcript metadata
    language = Column(String(10), nullable=False)
    is_manual = Column(Boolean, nullable=False)  # Manual vs auto-generated
    transcript_type = Column(String(30))  # 'youtube_api', 'diarized', 'whisper', etc.

    # Full transcript content
    transcript_text = Column(Text, nullable=False)  # Clean full text without timestamps
    transcript_text_with_speakers = Column(
        Text
    )  # Text with speaker labels (if diarized)

    # Timestamped data (JSON array of segments)
    transcript_segments_json = Column(
        JSONEncodedType, nullable=False
    )  # [{start, end, text, duration}, ...]
    diarization_segments_json = Column(
        JSONEncodedType
    )  # [{start, end, text, speaker, confidence}, ...]

    # Processing details
    whisper_model = Column(String(30))  # If transcribed with Whisper
    device_used = Column(String(10))  # cpu, cuda, mps
    diarization_enabled = Column(Boolean, default=False)
    diarization_model = Column(String(50))  # pyannote model if used
    include_timestamps = Column(Boolean, default=True)
    strip_interjections = Column(Boolean, default=False)

    # Quality metrics
    confidence_score = Column(Float)
    segment_count = Column(Integer)
    total_duration = Column(Float)

    # Processing metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    processing_time_seconds = Column(Float)

    # Speaker assignment tracking
    speaker_assignments = Column(JSONEncodedType)  # {speaker_id: assigned_name}
    speaker_assignment_completed = Column(Boolean, default=False)
    speaker_assignment_completed_at = Column(DateTime)

    # Relationships
    video = relationship("MediaSource", back_populates="transcripts")
    summaries = relationship("Summary", back_populates="transcript")
    generated_files = relationship("GeneratedFile", back_populates="transcript")

    def __repr__(self) -> str:
        return f"<Transcript(transcript_id='{self.transcript_id}', video_id='{self.video_id}', language='{self.language}')>"


class Summary(Base):
    """Summaries with different models/templates per video."""

    __tablename__ = "summaries"

    # Primary key
    summary_id = Column(String(50), primary_key=True)
    video_id = Column(String(20), ForeignKey("media_sources.source_id"), nullable=False)
    transcript_id = Column(String(50), ForeignKey("transcripts.transcript_id"))

    # Summary content
    summary_text = Column(Text, nullable=False)
    summary_metadata_json = Column(JSONEncodedType)  # YAML frontmatter data as JSON

    # Processing type - HCE is the primary method
    processing_type = Column(String(10), default="hce")  # 'hce' or 'hce_unified'
    hce_data_json = Column(
        JSONEncodedType
    )  # HCE structured output (claims, entities, etc.)

    # LLM processing details
    llm_provider = Column(String(20), nullable=False)  # 'openai', 'anthropic', 'local'
    llm_model = Column(String(50), nullable=False)  # 'gpt-4o-mini', 'claude-3', etc.
    prompt_template_path = Column(String(200))
    focus_area = Column(String(100))  # Optional focus parameter

    # Token consumption and costs
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)
    processing_cost = Column(Float)

    # Performance metrics
    input_length = Column(Integer)  # Character count of input
    summary_length = Column(Integer)  # Character count of summary
    compression_ratio = Column(Float)
    processing_time_seconds = Column(Float)

    # Processing metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    template_used = Column(String(100))

    # Relationships
    video = relationship("MediaSource", back_populates="summaries")
    transcript = relationship("Transcript", back_populates="summaries")
    moc_extractions = relationship("MOCExtraction", back_populates="summary")
    generated_files = relationship("GeneratedFile", back_populates="summary")

    def __repr__(self) -> str:
        return f"<Summary(summary_id='{self.summary_id}', video_id='{self.video_id}', llm_model='{self.llm_model}')>"


class MOCExtraction(Base):
    """Maps of Content (MOC) data extractions."""

    __tablename__ = "moc_extractions"

    # Primary key
    moc_id = Column(String(50), primary_key=True)
    video_id = Column(String(20), ForeignKey("media_sources.source_id"), nullable=False)
    summary_id = Column(String(50), ForeignKey("summaries.summary_id"))

    # Extracted entities (JSON arrays)
    people_json = Column(
        JSONEncodedType
    )  # [{"name": "John Doe", "mentions": 3, "description": "..."}]
    tags_json = Column(
        JSONEncodedType
    )  # [{"tag": "ai", "count": 5, "contexts": [...]}]
    mental_models_json = Column(
        JSONEncodedType
    )  # [{"name": "Systems Thinking", "description": "..."}]
    jargon_json = Column(
        JSONEncodedType
    )  # [{"term": "API", "definition": "Application Programming Interface"}]
    beliefs_json = Column(
        JSONEncodedType
    )  # [{"claim": "...", "evidence": "...", "confidence": 0.8}]

    # MOC metadata
    theme = Column(String(20))  # 'topical', 'chronological', 'hierarchical'
    depth = Column(Integer)
    include_beliefs = Column(Boolean)

    # Processing metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    extraction_method = Column(String(30))

    # Relationships
    video = relationship("MediaSource", back_populates="moc_extractions")
    summary = relationship("Summary", back_populates="moc_extractions")
    generated_files = relationship("GeneratedFile", back_populates="moc_extraction")

    def __repr__(self) -> str:
        return f"<MOCExtraction(moc_id='{self.moc_id}', video_id='{self.video_id}', theme='{self.theme}')>"


class GeneratedFile(Base):
    """Tracking of generated output files."""

    __tablename__ = "generated_files"

    # Primary key
    file_id = Column(String(50), primary_key=True)
    video_id = Column(String(20), ForeignKey("media_sources.source_id"), nullable=False)
    transcript_id = Column(String(50), ForeignKey("transcripts.transcript_id"))
    summary_id = Column(String(50), ForeignKey("summaries.summary_id"))
    moc_id = Column(String(50), ForeignKey("moc_extractions.moc_id"))

    # File details
    file_path = Column(String(500), nullable=False)
    file_type = Column(
        String(30), nullable=False
    )  # 'transcript_md', 'transcript_srt', 'summary_md', 'moc_people', etc.
    file_format = Column(
        String(10), nullable=False
    )  # 'md', 'txt', 'srt', 'vtt', 'yaml'

    # Generation parameters
    generation_params_json = Column(
        JSONEncodedType
    )  # Parameters used to generate this file
    include_timestamps = Column(Boolean)
    include_analysis = Column(Boolean)
    vault_path = Column(String(500))  # Obsidian vault path if applicable

    # File metadata
    file_size_bytes = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_modified = Column(DateTime, default=datetime.utcnow)

    # Relationships
    video = relationship("MediaSource", back_populates="generated_files")
    transcript = relationship("Transcript", back_populates="generated_files")
    summary = relationship("Summary", back_populates="generated_files")
    moc_extraction = relationship("MOCExtraction", back_populates="generated_files")

    def __repr__(self) -> str:
        return f"<GeneratedFile(file_id='{self.file_id}', file_type='{self.file_type}', file_format='{self.file_format}')>"


class ProcessingJob(Base):
    """Batch processing jobs tracking."""

    __tablename__ = "processing_jobs"

    # Primary key
    job_id = Column(String(50), primary_key=True)
    job_type = Column(
        String(30), nullable=False
    )  # 'transcription', 'summarization', 'moc_generation'

    # Job details
    input_urls_json = Column(JSONEncodedType)  # JSON array of input URLs/paths
    config_json = Column(JSONEncodedType)  # Job configuration parameters

    # Status tracking
    status = Column(
        String(20), nullable=False, default="pending"
    )  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Progress tracking
    total_items = Column(Integer)
    completed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    skipped_items = Column(Integer, default=0)

    # Resource usage
    total_cost = Column(Float, default=0.0)
    total_tokens_consumed = Column(Integer, default=0)
    total_processing_time_seconds = Column(Float, default=0.0)

    # Error tracking
    error_message = Column(Text)
    failed_items_json = Column(
        JSONEncodedType
    )  # JSON array of failed items with errors

    def __repr__(self) -> str:
        return f"<ProcessingJob(job_id='{self.job_id}', job_type='{self.job_type}', status='{self.status}')>"


class BrightDataSession(Base):
    """Bright Data session tracking and cost management."""

    __tablename__ = "bright_data_sessions"

    # Primary key
    session_id = Column(String(100), primary_key=True)
    video_id = Column(String(20), ForeignKey("media_sources.source_id"), nullable=False)

    # Session details
    session_type = Column(
        String(30), nullable=False
    )  # 'audio_download', 'metadata_scrape', 'transcript_scrape'
    proxy_endpoint = Column(String(100))  # zproxy.lum-superproxy.io:22225
    customer_id = Column(String(50))
    zone_id = Column(String(50))

    # Usage tracking
    requests_count = Column(Integer, default=0)
    data_downloaded_bytes = Column(Integer, default=0)
    session_duration_seconds = Column(Integer)

    # Cost tracking
    cost_per_request = Column(Float)
    cost_per_gb = Column(Float)
    total_cost = Column(Float, default=0.0)

    # Session metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    ip_address = Column(String(45))  # Assigned IP for session (supports IPv6)

    # Relationships
    video = relationship("MediaSource", back_populates="bright_data_sessions")

    def __repr__(self) -> str:
        return f"<BrightDataSession(session_id='{self.session_id}', session_type='{self.session_type}', total_cost={self.total_cost})>"


class ClaimTierValidation(Base):
    """User validation of HCE claim tier assignments."""

    __tablename__ = "claim_tier_validations"

    # Primary key
    validation_id = Column(String(50), primary_key=True)

    # Claim identification
    claim_id = Column(String(50), nullable=False)  # HCE claim ID
    episode_id = Column(String(50))  # Episode/content ID

    # Tier validation
    original_tier = Column(
        String(1), nullable=False
    )  # Original LLM-assigned tier (A, B, C)
    validated_tier = Column(String(1), nullable=False)  # User-validated tier (A, B, C)
    is_modified = Column(Boolean, default=False)  # Whether user changed the tier

    # Claim content
    claim_text = Column(Text, nullable=False)  # The actual claim text
    claim_type = Column(String(30))  # Type of claim (factual, causal, etc.)

    # Validation context
    validated_by_user = Column(String(100))  # User identifier
    validated_at = Column(DateTime, default=datetime.utcnow)

    # Original LLM scoring context
    original_scores = Column(JSONEncodedType)  # Original confidence scores
    model_used = Column(String(50))  # HCE model/version used

    # Evidence and context
    evidence_spans = Column(JSONEncodedType)  # Evidence that supported the claim
    validation_session_id = Column(String(50))  # Group validations by session

    def __repr__(self) -> str:
        return f"<ClaimTierValidation(claim_id='{self.claim_id}', {self.original_tier}->{self.validated_tier}, modified={self.is_modified})>"


class QualityMetrics(Base):
    """Aggregated quality metrics for model performance tracking."""

    __tablename__ = "quality_metrics"

    # Primary key
    metric_id = Column(String(50), primary_key=True)
    model_name = Column(String(50), nullable=False)
    content_type = Column(String(30), nullable=False)

    # Aggregated statistics
    total_ratings = Column(Integer, default=0)
    user_corrected_count = Column(Integer, default=0)
    avg_llm_rating = Column(Float)
    avg_user_rating = Column(Float)
    rating_drift = Column(Float)  # Difference between LLM and user ratings

    # Performance by criteria
    criteria_performance = Column(JSONEncodedType)  # Detailed breakdown

    # Time window
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<QualityMetrics(metric_id='{self.metric_id}', model_name='{self.model_name}', avg_user_rating={self.avg_user_rating})>"


# ============================================================================
# CORE: Claims (Fundamental Unit)
# ============================================================================


class Claim(Base):
    """Claims: The atomic unit of knowledge."""

    __tablename__ = "claims"

    # Primary key
    claim_id = Column(String, primary_key=True)

    # Attribution (optional)
    source_id = Column(
        String, ForeignKey("media_sources.source_id", ondelete="SET NULL")
    )
    episode_id = Column(String, ForeignKey("episodes.episode_id", ondelete="SET NULL"))

    # Content
    canonical = Column(Text, nullable=False)
    original_text = Column(Text)
    claim_type = Column(String)

    # System evaluation (from HCE)
    tier = Column(String)
    importance_score = Column(Float)
    specificity_score = Column(Float)
    verifiability_score = Column(Float)

    # User curation
    user_tier_override = Column(String)
    user_confidence_override = Column(Float)
    evaluator_notes = Column(Text)

    # Verification workflow
    verification_status = Column(String, default="unverified")
    verification_source = Column(String)
    verification_notes = Column(Text)

    # Review workflow
    flagged_for_review = Column(Boolean, default=False)
    reviewed_by = Column(String)
    reviewed_at = Column(DateTime)

    # Temporality analysis
    temporality_score = Column(Integer, default=3)
    temporality_confidence = Column(Float, default=0.5)
    temporality_rationale = Column(Text)
    first_mention_ts = Column(String)

    # Export tracking
    upload_status = Column(String, default="pending")
    upload_timestamp = Column(DateTime)
    upload_error = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source = relationship(
        "MediaSource", back_populates="claims", foreign_keys=[source_id]
    )
    episode = relationship(
        "Episode", back_populates="claims", foreign_keys=[episode_id]
    )
    evidence_spans = relationship(
        "EvidenceSpan", back_populates="claim", cascade="all, delete-orphan"
    )
    relations_as_source = relationship(
        "ClaimRelation",
        foreign_keys="ClaimRelation.source_claim_id",
        back_populates="source_claim",
        cascade="all, delete-orphan",
    )
    relations_as_target = relationship(
        "ClaimRelation",
        foreign_keys="ClaimRelation.target_claim_id",
        back_populates="target_claim",
        cascade="all, delete-orphan",
    )
    categories = relationship(
        "ClaimCategory", back_populates="claim", cascade="all, delete-orphan"
    )
    tags = relationship(
        "ClaimTag", back_populates="claim", cascade="all, delete-orphan"
    )
    people = relationship(
        "ClaimPerson", back_populates="claim", cascade="all, delete-orphan"
    )
    concepts = relationship(
        "ClaimConcept", back_populates="claim", cascade="all, delete-orphan"
    )
    jargon = relationship(
        "ClaimJargon", back_populates="claim", cascade="all, delete-orphan"
    )
    exports = relationship(
        "ClaimExport", back_populates="claim", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "claim_type IN ('factual', 'causal', 'normative', 'forecast', 'definition')",
            name="ck_claim_type",
        ),
        CheckConstraint("tier IN ('A', 'B', 'C')", name="ck_tier"),
        CheckConstraint("user_tier_override IN ('A', 'B', 'C')", name="ck_user_tier"),
        CheckConstraint("importance_score BETWEEN 0 AND 1", name="ck_importance"),
        CheckConstraint("specificity_score BETWEEN 0 AND 1", name="ck_specificity"),
        CheckConstraint("verifiability_score BETWEEN 0 AND 1", name="ck_verifiability"),
        CheckConstraint(
            "user_confidence_override BETWEEN 0 AND 1", name="ck_user_confidence"
        ),
        CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'disputed', 'false')",
            name="ck_verification_status",
        ),
        CheckConstraint(
            "temporality_score IN (1, 2, 3, 4, 5)", name="ck_temporality_score"
        ),
        CheckConstraint(
            "temporality_confidence BETWEEN 0 AND 1", name="ck_temporality_confidence"
        ),
    )


# ============================================================================
# EVIDENCE & CONTEXT
# ============================================================================


class EvidenceSpan(Base):
    """Evidence spans: Supporting quotes for claims."""

    __tablename__ = "evidence_spans"

    # Primary key
    evidence_id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), nullable=False
    )
    segment_id = Column(String, ForeignKey("segments.segment_id", ondelete="SET NULL"))
    sequence = Column(Integer, nullable=False)

    # Precise quote
    start_time = Column(String)
    end_time = Column(String)
    quote = Column(Text)

    # Extended context
    context_start_time = Column(String)
    context_end_time = Column(String)
    context_text = Column(Text)
    context_type = Column(String, default="exact")

    # For document sources
    page_number = Column(Integer)
    paragraph_number = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="evidence_spans")
    segment = relationship("Segment", back_populates="evidence_spans")

    __table_args__ = (
        CheckConstraint(
            "context_type IN ('exact', 'extended', 'segment')", name="ck_context_type"
        ),
    )


class ClaimRelation(Base):
    """Claim relations: How claims relate to each other."""

    __tablename__ = "claim_relations"

    # Primary key
    relation_id = Column(Integer, primary_key=True, autoincrement=True)
    source_claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), nullable=False
    )
    target_claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), nullable=False
    )
    relation_type = Column(String, nullable=False)
    strength = Column(Float)
    rationale = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    source_claim = relationship(
        "Claim", foreign_keys=[source_claim_id], back_populates="relations_as_source"
    )
    target_claim = relationship(
        "Claim", foreign_keys=[target_claim_id], back_populates="relations_as_target"
    )

    __table_args__ = (
        CheckConstraint(
            "relation_type IN ('supports', 'contradicts', 'depends_on', 'refines', 'related_to')",
            name="ck_relation_type",
        ),
        CheckConstraint("strength BETWEEN 0 AND 1", name="ck_strength"),
        UniqueConstraint(
            "source_claim_id",
            "target_claim_id",
            "relation_type",
            name="uq_claim_relation",
        ),
    )


# ============================================================================
# ENTITIES: People, Concepts, Jargon
# ============================================================================


class Person(Base):
    """People/Organizations catalog."""

    __tablename__ = "people"

    # Primary key
    person_id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    normalized_name = Column(String)
    description = Column(Text)
    entity_type = Column(String, default="person")
    confidence = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    claim_mentions = relationship(
        "ClaimPerson", back_populates="person", cascade="all, delete-orphan"
    )
    external_ids = relationship(
        "PersonExternalId", back_populates="person", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('person', 'organization')", name="ck_entity_type"
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_confidence"),
    )


class ClaimPerson(Base):
    """Person mentions in claims."""

    __tablename__ = "claim_people"

    # Composite primary key
    claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    person_id = Column(
        String, ForeignKey("people.person_id", ondelete="CASCADE"), primary_key=True
    )

    mention_context = Column(Text)
    first_mention_ts = Column(String)
    role = Column(String)  # 'subject', 'object', 'mentioned'

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="people")
    person = relationship("Person", back_populates="claim_mentions")


class PersonExternalId(Base):
    """External IDs for people (WikiData, Wikipedia, etc.)."""

    __tablename__ = "person_external_ids"

    # Composite primary key
    person_id = Column(
        String, ForeignKey("people.person_id", ondelete="CASCADE"), primary_key=True
    )
    external_system = Column(String, primary_key=True)
    external_id = Column(String, nullable=False)

    # Relationships
    person = relationship("Person", back_populates="external_ids")


class PersonEvidence(Base):
    """All mentions of a person with timestamps (not just first mention)."""

    __tablename__ = "person_evidence"

    # Composite primary key
    person_id = Column(
        String, ForeignKey("people.person_id", ondelete="CASCADE"), primary_key=True
    )
    claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    sequence = Column(Integer, primary_key=True)  # Order of mentions

    # Timing
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)

    # Content
    quote = Column(Text, nullable=False)  # How they were mentioned
    surface_form = Column(String)  # Exact text used
    segment_id = Column(String)

    # Context (extended window)
    context_start_time = Column(String)
    context_end_time = Column(String)
    context_text = Column(Text)
    context_type = Column(String, default="exact")

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    person = relationship("Person")
    claim = relationship("Claim")


class Concept(Base):
    """Concepts / Mental Models catalog."""

    __tablename__ = "concepts"

    # Primary key
    concept_id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    definition = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    claim_mentions = relationship(
        "ClaimConcept", back_populates="concept", cascade="all, delete-orphan"
    )
    aliases = relationship(
        "ConceptAlias", back_populates="concept", cascade="all, delete-orphan"
    )


class ClaimConcept(Base):
    """Concept mentions in claims."""

    __tablename__ = "claim_concepts"

    # Composite primary key
    claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    concept_id = Column(
        String, ForeignKey("concepts.concept_id", ondelete="CASCADE"), primary_key=True
    )

    first_mention_ts = Column(String)
    context = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="concepts")
    concept = relationship("Concept", back_populates="claim_mentions")


class ConceptAlias(Base):
    """Concept aliases."""

    __tablename__ = "concept_aliases"

    # Composite primary key
    concept_id = Column(
        String, ForeignKey("concepts.concept_id", ondelete="CASCADE"), primary_key=True
    )
    alias = Column(String, primary_key=True)

    # Relationships
    concept = relationship("Concept", back_populates="aliases")


class ConceptEvidence(Base):
    """All mentions of a concept with timestamps (not just first mention)."""

    __tablename__ = "concept_evidence"

    # Composite primary key
    concept_id = Column(
        String, ForeignKey("concepts.concept_id", ondelete="CASCADE"), primary_key=True
    )
    claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    sequence = Column(Integer, primary_key=True)  # Order of mentions

    # Timing
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)

    # Content
    quote = Column(Text, nullable=False)  # Example/usage of the concept
    segment_id = Column(String)

    # Context (extended window)
    context_start_time = Column(String)
    context_end_time = Column(String)
    context_text = Column(Text)
    context_type = Column(String, default="exact")

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    concept = relationship("Concept")
    claim = relationship("Claim")


class JargonTerm(Base):
    """Jargon terms catalog."""

    __tablename__ = "jargon_terms"

    # Primary key
    jargon_id = Column(String, primary_key=True)
    term = Column(String, nullable=False, unique=True)
    definition = Column(Text)
    domain = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    claim_mentions = relationship(
        "ClaimJargon", back_populates="jargon_term", cascade="all, delete-orphan"
    )


class ClaimJargon(Base):
    """Jargon usage in claims."""

    __tablename__ = "claim_jargon"

    # Composite primary key
    claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    jargon_id = Column(
        String,
        ForeignKey("jargon_terms.jargon_id", ondelete="CASCADE"),
        primary_key=True,
    )

    context = Column(Text)
    first_mention_ts = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="jargon")
    jargon_term = relationship("JargonTerm", back_populates="claim_mentions")


class JargonEvidence(Base):
    """All usages of jargon with timestamps (not just first mention)."""

    __tablename__ = "jargon_evidence"

    # Composite primary key
    jargon_id = Column(
        String,
        ForeignKey("jargon_terms.jargon_id", ondelete="CASCADE"),
        primary_key=True,
    )
    claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    sequence = Column(Integer, primary_key=True)  # Order of mentions

    # Timing
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)

    # Content
    quote = Column(Text, nullable=False)  # Usage of the jargon term
    segment_id = Column(String)

    # Context (extended window)
    context_start_time = Column(String)
    context_end_time = Column(String)
    context_text = Column(Text)
    context_type = Column(String, default="exact")

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    jargon_term = relationship("JargonTerm")
    claim = relationship("Claim")


# ============================================================================
# CATEGORIES: WikiData Controlled Vocabulary
# ============================================================================


class WikiDataCategory(Base):
    """WikiData categories vocabulary."""

    __tablename__ = "wikidata_categories"

    # Primary key
    wikidata_id = Column(String, primary_key=True)
    category_name = Column(String, nullable=False, unique=True)
    category_description = Column(Text)
    parent_wikidata_id = Column(String, ForeignKey("wikidata_categories.wikidata_id"))
    level = Column(String)

    # For semantic matching
    embedding_vector = Column(LargeBinary)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parent = relationship(
        "WikiDataCategory", remote_side=[wikidata_id], backref="children"
    )
    claim_categories = relationship(
        "ClaimCategory",
        back_populates="wikidata_category",
        cascade="all, delete-orphan",
    )
    aliases = relationship(
        "WikiDataAlias",
        back_populates="wikidata_category",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("level IN ('general', 'specific')", name="ck_level"),
    )


class WikiDataAlias(Base):
    """WikiData category aliases (for matching)."""

    __tablename__ = "wikidata_aliases"

    # Composite primary key
    wikidata_id = Column(
        String,
        ForeignKey("wikidata_categories.wikidata_id", ondelete="CASCADE"),
        primary_key=True,
    )
    alias = Column(String, primary_key=True)

    # Relationships
    wikidata_category = relationship("WikiDataCategory", back_populates="aliases")


class ClaimCategory(Base):
    """Claim categories (typically 1 specific topic)."""

    __tablename__ = "claim_categories"

    # Composite primary key
    claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    wikidata_id = Column(
        String, ForeignKey("wikidata_categories.wikidata_id"), primary_key=True
    )

    # System scores
    relevance_score = Column(Float)
    confidence = Column(Float)

    # Primary category flag
    is_primary = Column(Boolean, default=False)

    # User workflow
    user_approved = Column(Boolean, default=False)
    user_rejected = Column(Boolean, default=False)
    source = Column(String, default="system")

    # Context
    context_quote = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="categories")
    wikidata_category = relationship(
        "WikiDataCategory", back_populates="claim_categories"
    )

    __table_args__ = (
        CheckConstraint("relevance_score BETWEEN 0 AND 1", name="ck_cc_relevance"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_cc_confidence"),
    )


# ============================================================================
# USER TAGS (Separate from WikiData)
# ============================================================================


class UserTag(Base):
    """User-defined tags."""

    __tablename__ = "user_tags"

    # Primary key
    tag_id = Column(Integer, primary_key=True, autoincrement=True)
    tag_name = Column(String, unique=True, nullable=False)
    tag_color = Column(String)
    description = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claim_tags = relationship(
        "ClaimTag", back_populates="tag", cascade="all, delete-orphan"
    )


class ClaimTag(Base):
    """Claim tags (many-to-many)."""

    __tablename__ = "claim_tags"

    # Composite primary key
    claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    tag_id = Column(
        Integer, ForeignKey("user_tags.tag_id", ondelete="CASCADE"), primary_key=True
    )

    added_by = Column(String)
    added_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="tags")
    tag = relationship("UserTag", back_populates="claim_tags")


# ============================================================================
# PLATFORM CATEGORIES (Uncontrolled - from YouTube, etc.)
# ============================================================================


class PlatformCategory(Base):
    """Platform categories (YouTube, iTunes, etc.)."""

    __tablename__ = "platform_categories"

    # Primary key
    category_id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String, nullable=False)
    category_name = Column(String, nullable=False)

    # Relationships
    source_categories = relationship(
        "SourcePlatformCategory",
        back_populates="category",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("platform", "category_name", name="uq_platform_category"),
    )


class SourcePlatformCategory(Base):
    """Source platform categories (many-to-many)."""

    __tablename__ = "source_platform_categories"

    # Composite primary key
    source_id = Column(
        String,
        ForeignKey("media_sources.source_id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id = Column(
        Integer, ForeignKey("platform_categories.category_id"), primary_key=True
    )

    # Relationships
    source = relationship("MediaSource", back_populates="platform_categories")
    category = relationship("PlatformCategory", back_populates="source_categories")


class PlatformTag(Base):
    """Platform tags (YouTube tags, etc.)."""

    __tablename__ = "platform_tags"

    # Primary key
    tag_id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String, nullable=False)
    tag_name = Column(String, nullable=False)

    # Relationships
    source_tags = relationship(
        "SourcePlatformTag", back_populates="tag", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("platform", "tag_name", name="uq_platform_tag"),)


class SourcePlatformTag(Base):
    """Source platform tags (many-to-many)."""

    __tablename__ = "source_platform_tags"

    # Composite primary key
    source_id = Column(
        String,
        ForeignKey("media_sources.source_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id = Column(Integer, ForeignKey("platform_tags.tag_id"), primary_key=True)

    # Relationships
    source = relationship("MediaSource", back_populates="platform_tags")
    tag = relationship("PlatformTag", back_populates="source_tags")


# ============================================================================
# EXPORT TRACKING
# ============================================================================


class ExportDestination(Base):
    """Export destinations."""

    __tablename__ = "export_destinations"

    # Primary key
    destination_id = Column(Integer, primary_key=True, autoincrement=True)
    destination_name = Column(String, nullable=False, unique=True)
    destination_url = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claim_exports = relationship(
        "ClaimExport", back_populates="destination", cascade="all, delete-orphan"
    )


class ClaimExport(Base):
    """Claim exports."""

    __tablename__ = "claim_exports"

    # Composite primary key
    claim_id = Column(
        String, ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    destination_id = Column(
        Integer, ForeignKey("export_destinations.destination_id"), primary_key=True
    )

    exported_at = Column(DateTime, default=datetime.utcnow)
    export_url = Column(String)
    export_status = Column(String, default="success")
    export_error = Column(Text)

    # Relationships
    claim = relationship("Claim", back_populates="exports")
    destination = relationship("ExportDestination", back_populates="claim_exports")


# ============================================================================
# Speaker Identification Models
# ============================================================================


class SpeakerVoice(Base):
    """Database model for learned speaker voices and characteristics."""

    __tablename__ = "speaker_voices"
    __table_args__ = {"extend_existing": True}

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
    def fingerprint_data(self) -> dict[str, Any]:
        """Get voice fingerprint as dictionary."""
        if self.voice_fingerprint:
            try:
                return json.loads(self.voice_fingerprint)
            except json.JSONDecodeError:
                return {}
        return {}

    @fingerprint_data.setter
    def fingerprint_data(self, data: dict[str, Any]):
        """Set voice fingerprint from dictionary."""
        self.voice_fingerprint = json.dumps(data)


class SpeakerAssignment(Base):
    """Database model for speaker assignments in recordings."""

    __tablename__ = "speaker_assignments"
    __table_args__ = {"extend_existing": True}

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
    suggestion_method = Column(
        String(100), nullable=True
    )  # 'content_analysis', 'pattern_matching', 'manual'
    sample_segments_json = Column(Text, nullable=True)  # JSON array of first 5 segments
    total_duration = Column(Float, default=0.0)  # Total speaking time
    segment_count = Column(Integer, default=0)  # Number of segments
    processing_metadata_json = Column(Text, nullable=True)  # Additional metadata
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign key to speaker voice (optional)
    voice_id = Column(Integer, ForeignKey("speaker_voices.id"), nullable=True)
    voice = relationship("SpeakerVoice", back_populates="assignments")

    @property
    def sample_segments(self) -> list[dict[str, Any]]:
        """Get sample segments as list of dictionaries."""
        if self.sample_segments_json:
            try:
                return json.loads(self.sample_segments_json)
            except json.JSONDecodeError:
                return []
        return []

    @sample_segments.setter
    def sample_segments(self, data: list[dict[str, Any]]):
        """Set sample segments from list of dictionaries."""
        self.sample_segments_json = json.dumps(data)

    @property
    def processing_metadata(self) -> dict[str, Any]:
        """Get processing metadata as dictionary."""
        if self.processing_metadata_json:
            try:
                return json.loads(self.processing_metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}

    @processing_metadata.setter
    def processing_metadata(self, data: dict[str, Any]):
        """Set processing metadata from dictionary."""
        self.processing_metadata_json = json.dumps(data)

    def __repr__(self):
        return f"<SpeakerAssignment(id={self.id}, speaker_id='{self.speaker_id}', assigned_name='{self.assigned_name}')>"


class SpeakerLearningHistory(Base):
    """Database model for tracking learning from user corrections."""

    __tablename__ = "speaker_learning_history"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    original_suggestion = Column(String(255))
    user_correction = Column(String(255), nullable=False)
    context_data = Column(Text)  # JSON string of context information
    learning_weight = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Foreign key to speaker voice
    voice_id = Column(Integer, ForeignKey("speaker_voices.id"), nullable=True)
    voice = relationship("SpeakerVoice", back_populates="learning_history")

    def __repr__(self):
        return f"<SpeakerLearningHistory(id={self.id}, correction='{self.user_correction}')>"

    @property
    def context(self) -> dict[str, Any]:
        """Get context data as dictionary."""
        if self.context_data:
            try:
                return json.loads(self.context_data)
            except json.JSONDecodeError:
                return {}
        return {}

    @context.setter
    def context(self, data: dict[str, Any]):
        """Set context data from dictionary."""
        self.context_data = json.dumps(data)


class SpeakerSession(Base):
    """Database model for tracking speaker sessions across recordings."""

    __tablename__ = "speaker_sessions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    session_name = Column(
        String(255), nullable=False
    )  # e.g., "Team Meeting 2024-01-15"
    folder_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SpeakerSession(id={self.id}, name='{self.session_name}')>"


class ChannelHostMapping(Base):
    """Database model for storing channel-to-host name mappings."""

    __tablename__ = "channel_host_mappings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    channel_name = Column(String(255), nullable=False, index=True, unique=True)
    host_name = Column(String(255), nullable=False)
    confidence = Column(Float, default=1.0)  # How confident we are in this mapping
    created_by = Column(
        String(50), default="user_correction"
    )  # 'user_correction', 'llm_suggestion', 'manual'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    use_count = Column(Integer, default=1)  # How many times this mapping has been used

    def __repr__(self):
        return f"<ChannelHostMapping(id={self.id}, channel='{self.channel_name}', host='{self.host_name}')>"


class SpeakerProcessingSession(Base):
    """Database model for tracking speaker processing sessions and learning data."""

    __tablename__ = "speaker_processing_sessions"
    __table_args__ = {"extend_existing": True}

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
    def ai_suggestions(self) -> dict[str, Any]:
        """Get AI suggestions as dictionary."""
        if self.ai_suggestions_json:
            try:
                return json.loads(self.ai_suggestions_json)
            except json.JSONDecodeError:
                return {}
        return {}

    @ai_suggestions.setter
    def ai_suggestions(self, data: dict[str, Any]):
        """Set AI suggestions from dictionary."""
        self.ai_suggestions_json = json.dumps(data)

    @property
    def user_corrections(self) -> dict[str, Any]:
        """Get user corrections as dictionary."""
        if self.user_corrections_json:
            try:
                return json.loads(self.user_corrections_json)
            except json.JSONDecodeError:
                return {}
        return {}

    @user_corrections.setter
    def user_corrections(self, data: dict[str, Any]):
        """Set user corrections from dictionary."""
        self.user_corrections_json = json.dumps(data)

    @property
    def confidence_scores(self) -> dict[str, float]:
        """Get confidence scores as dictionary."""
        if self.confidence_scores_json:
            try:
                return json.loads(self.confidence_scores_json)
            except json.JSONDecodeError:
                return {}
        return {}

    @confidence_scores.setter
    def confidence_scores(self, data: dict[str, float]):
        """Set confidence scores from dictionary."""
        self.confidence_scores_json = json.dumps(data)

    def __repr__(self):
        return f"<SpeakerProcessingSession(session_id='{self.session_id}', recording_path='{self.recording_path}')>"


# Database initialization functions
def create_database_engine(database_url: str = "sqlite:///knowledge_system.db"):
    """Create SQLAlchemy engine for the database with foreign key enforcement."""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    engine = create_engine(database_url, echo=False)

    # Enable foreign key constraints for SQLite
    if database_url.startswith("sqlite"):

        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_all_tables(engine):
    """Create all database tables."""
    Base.metadata.create_all(engine)


def get_session_maker(engine):
    """Get SQLAlchemy session maker."""
    return sessionmaker(bind=engine)
