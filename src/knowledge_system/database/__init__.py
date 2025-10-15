"""
Database module for Knowledge System SQLite integration.

This module provides SQLAlchemy models and database services for storing
YouTube video records, transcripts, summaries, MOC data, and processing tracking.
"""

# HCE models are optional and imported separately to avoid SQLAlchemy issues
try:
    from .hce_models import extend_video_model

    HCE_AVAILABLE = True
except Exception:
    # If HCE models fail to import, continue without them
    HCE_AVAILABLE = False

    # Define dummy function to avoid errors
    def extend_video_model():
        pass


from .models import (
    Base,
    BrightDataSession,
    GeneratedFile,
    MediaSource,
    MOCExtraction,
    ProcessingJob,
    Summary,
    Transcript,
)

# System 2 models
try:
    from .system2_models import Job, JobRun, LLMRequest, LLMResponse

    SYSTEM2_AVAILABLE = True
except Exception:
    SYSTEM2_AVAILABLE = False

# Backward-compatibility: export legacy symbol `Video` even if models renamed
Video = MediaSource
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
]

# Add System 2 models to exports if available
if SYSTEM2_AVAILABLE:
    __all__.extend(["Job", "JobRun", "LLMRequest", "LLMResponse"])

# Add HCE models to exports if available
if HCE_AVAILABLE:
    __all__.extend(
        [
            "Episode",
            "Claim",
            "EvidenceSpan",
            "Relation",
            "Person",
            "Concept",
            "JargonTerm",
        ]
    )
