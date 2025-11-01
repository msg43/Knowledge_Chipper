"""
System 2 database models for job orchestration and LLM tracking.

This module adds tables for job management, LLM request/response tracking,
and extends existing tables with updated_at columns for concurrency control.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .models import Base, JSONEncodedType


class Job(Base):
    """Top-level job records for orchestrating work across the pipeline."""

    __tablename__ = "job"
    __table_args__ = {"extend_existing": True}

    job_id = Column(String(100), primary_key=True)
    job_type = Column(
        String(50), nullable=False
    )  # 'transcribe', 'mine', 'flagship', 'upload'
    input_id = Column(String(100), nullable=False)  # source_id or source_id
    config_json = Column(JSONEncodedType)  # Job configuration
    auto_process = Column(String(5), default="false")  # Whether to chain to next stage
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    runs = relationship("JobRun", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('transcribe','mine','flagship','upload','pipeline')"
        ),
    )


class JobRun(Base):
    """Individual execution attempts of a job with metrics and status."""

    __tablename__ = "job_run"
    __table_args__ = {"extend_existing": True}

    run_id = Column(String(100), primary_key=True)
    job_id = Column(String(100), ForeignKey("job.job_id"), nullable=False)
    attempt_number = Column(Integer, default=1)
    status = Column(String(20), nullable=False, default="queued")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_code = Column(String(50))
    error_message = Column(Text)
    checkpoint_json = Column(JSONEncodedType)  # Resume state
    metrics_json = Column(JSONEncodedType)  # Performance metrics
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job = relationship("Job", back_populates="runs")
    llm_requests = relationship(
        "LLMRequest", back_populates="job_run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')"
        ),
    )


class LLMRequest(Base):
    """Tracks all LLM API requests for auditing and cost tracking."""

    __tablename__ = "llm_request"
    __table_args__ = {"extend_existing": True}

    request_id = Column(String(100), primary_key=True)
    job_run_id = Column(String(100), ForeignKey("job_run.run_id"), nullable=False)
    provider = Column(String(50), nullable=False)  # 'openai', 'anthropic', 'google'
    model = Column(String(100), nullable=False)
    endpoint = Column(String(100))  # API endpoint used
    prompt_tokens = Column(Integer)
    max_tokens = Column(Integer)
    temperature = Column(Float)
    request_json = Column(JSONEncodedType, nullable=False)  # Full request payload
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    job_run = relationship("JobRun", back_populates="llm_requests")
    response = relationship("LLMResponse", back_populates="request", uselist=False)


class LLMResponse(Base):
    """Stores LLM API responses with metrics."""

    __tablename__ = "llm_response"
    __table_args__ = {"extend_existing": True}

    response_id = Column(String(100), primary_key=True)
    request_id = Column(String(100), ForeignKey("llm_request.request_id"), unique=True)
    status_code = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)
    latency_ms = Column(Float)
    cost_usd = Column(Float)
    response_json = Column(JSONEncodedType, nullable=False)  # Full response payload
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    request = relationship("LLMRequest", back_populates="response")
