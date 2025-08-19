"""
Database module for Knowledge System SQLite integration.

This module provides SQLAlchemy models and database services for storing
YouTube video records, transcripts, summaries, MOC data, and processing tracking.
"""

from .hce_models import (
    Claim,
    Concept,
    Episode,
    EvidenceSpan,
    JargonTerm,
    Person,
    Relation,
    extend_video_model,
)
from .models import (
    Base,
    BrightDataSession,
    GeneratedFile,
    MOCExtraction,
    ProcessingJob,
    Summary,
    Transcript,
    Video,
)
from .service import DatabaseService

# Extend Video model with HCE relationship
extend_video_model()

__all__ = [
    "Video",
    "Transcript",
    "Summary",
    "MOCExtraction",
    "GeneratedFile",
    "ProcessingJob",
    "BrightDataSession",
    "Base",
    "DatabaseService",
    # HCE models
    "Episode",
    "Claim",
    "EvidenceSpan",
    "Relation",
    "Person",
    "Concept",
    "JargonTerm",
]
