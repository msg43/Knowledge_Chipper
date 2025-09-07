"""
SQLAlchemy models for Knowledge System database.

Comprehensive database schema for storing YouTube videos, transcripts, summaries,
MOC extractions, file generation tracking, processing jobs, and Bright Data sessions.
"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, synonym
from sqlalchemy.types import TypeDecorator

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


class MediaSource(Base):
    """Core media source records with complete metadata (replaces legacy 'videos')."""

    __tablename__ = "media_sources"

    # Primary key
    media_id = Column(String(20), primary_key=True)
    # Back-compat attribute: many modules still expect 'video_id'
    video_id = synonym("media_id")
    source_type = Column(
        String(50), nullable=False, default="youtube"
    )  # 'youtube', 'upload', 'rss'
    title = Column(String(500), nullable=False)
    url = Column(String(200), nullable=False)

    # YouTube metadata (from yt-dlp/Bright Data)
    description = Column(Text)
    uploader = Column(String(200))
    uploader_id = Column(String(50))
    upload_date = Column(String(8))  # YYYYMMDD format
    duration_seconds = Column(Integer)
    view_count = Column(Integer)
    like_count = Column(Integer)
    comment_count = Column(Integer)
    categories_json = Column(JSONEncodedType)  # JSON array of categories
    privacy_status = Column(String(20))
    caption_availability = Column(Boolean)

    # Thumbnails
    thumbnail_url = Column(String(500))  # Original YouTube thumbnail URL
    thumbnail_local_path = Column(String(500))  # Local downloaded thumbnail path

    # Tags and keywords (searchable)
    tags_json = Column(JSONEncodedType)  # JSON array of video tags
    extracted_keywords_json = Column(
        JSONEncodedType
    )  # JSON array of AI-extracted keywords

    # Related content and recommendations
    related_videos_json = Column(JSONEncodedType)  # JSON array of related video data

    # Detailed channel statistics
    channel_stats_json = Column(JSONEncodedType)  # JSON object with channel metrics

    # Video chapters/timestamps
    video_chapters_json = Column(
        JSONEncodedType
    )  # JSON array of chapter data with timestamps

    # Processing metadata
    extraction_method = Column(String(50))  # 'bright_data_api', 'yt_dlp', etc.
    processed_at = Column(DateTime, default=datetime.utcnow)
    bright_data_session_id = Column(String(100))
    processing_cost = Column(Float)
    status = Column(
        String(20), default="pending"
    )  # 'pending', 'processing', 'completed', 'failed'

    # Relationships
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

    def __repr__(self) -> str:
        return (
            f"<MediaSource(media_id='{self.media_id}', title='{self.title[:50]}...')>"
        )


# Backward-compatibility: many modules still import/use `Video`
# Map the legacy symbol to the new class to avoid breaking imports
Video = MediaSource


class Transcript(Base):
    """Transcript data with support for multiple versions per video."""

    __tablename__ = "transcripts"

    # Primary key
    transcript_id = Column(String(50), primary_key=True)
    video_id = Column(String(20), ForeignKey("media_sources.media_id"), nullable=False)

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
    video_id = Column(String(20), ForeignKey("media_sources.media_id"), nullable=False)
    transcript_id = Column(String(50), ForeignKey("transcripts.transcript_id"))

    # Summary content
    summary_text = Column(Text, nullable=False)
    summary_metadata_json = Column(JSONEncodedType)  # YAML frontmatter data as JSON

    # Processing type - legacy or HCE
    processing_type = Column(String(10), default="legacy")  # 'legacy' or 'hce'
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
    video_id = Column(String(20), ForeignKey("media_sources.media_id"), nullable=False)
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
    video_id = Column(String(20), ForeignKey("media_sources.media_id"), nullable=False)
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
    video_id = Column(String(20), ForeignKey("media_sources.media_id"), nullable=False)

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


class QualityRating(Base):
    """Legacy quality ratings table - kept for backward compatibility."""

    __tablename__ = "quality_ratings"

    # Primary key
    rating_id = Column(String(50), primary_key=True)

    # What's being rated
    content_type = Column(
        String(30), nullable=False
    )  # 'summary', 'transcript', 'moc_extraction', 'claim_tier'
    content_id = Column(String(50), nullable=False)  # ID of the rated content

    # Rating details
    llm_rating = Column(Float)  # Original LLM-assigned rating (0.0-1.0)
    user_rating = Column(Float)  # User-corrected rating (0.0-1.0)
    is_user_corrected = Column(Boolean, default=False)

    # Rating criteria (JSON object with detailed scores)
    criteria_scores = Column(
        JSONEncodedType
    )  # {"accuracy": 0.8, "completeness": 0.9, "relevance": 0.7}

    # Feedback details
    user_feedback = Column(Text)  # Optional text feedback from user
    rating_reason = Column(Text)  # Why this rating was given

    # Context
    rated_by_user = Column(String(100))  # User identifier
    rated_at = Column(DateTime, default=datetime.utcnow)

    # Model context for learning
    model_used = Column(String(50))  # Which model generated the content
    prompt_template = Column(String(200))  # Which template was used
    input_characteristics = Column(JSONEncodedType)  # Input length, complexity, etc.

    def __repr__(self) -> str:
        return f"<QualityRating(rating_id='{self.rating_id}', content_type='{self.content_type}', user_rating={self.user_rating})>"


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


# Database initialization functions
def create_database_engine(database_url: str = "sqlite:///knowledge_system.db"):
    """Create SQLAlchemy engine for the database."""
    return create_engine(database_url, echo=False)


def create_all_tables(engine):
    """Create all database tables."""
    Base.metadata.create_all(engine)


def get_session_maker(engine):
    """Get SQLAlchemy session maker."""
    return sessionmaker(bind=engine)
