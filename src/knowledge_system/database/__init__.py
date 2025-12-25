"""
Database module for Knowledge System SQLite integration.

This module provides SQLAlchemy models and database services for storing
YouTube video records, transcripts, summaries, MOC data, and processing tracking.
"""

from .models import (
    Base,
    BrightDataSession,
    Claim,
    ClaimCategory,
    ClaimConcept,
    ClaimExport,
    ClaimJargon,
    ClaimPerson,
    ClaimRelation,
    ClaimTag,
    Concept,
    ConceptAlias,
    ConceptEvidence,
    EvidenceSpan,
    ExportDestination,
    GeneratedFile,
    JargonEvidence,
    JargonTerm,
    MediaSource,
    MOCExtraction,
    Person,
    PersonEvidence,
    PersonExternalId,
    PersistentSpeakerProfile,
    PlatformCategory,
    PlatformTag,
    ProcessingJob,
    ReviewQueueItem,
    Segment,
    SourcePlatformCategory,
    SourcePlatformTag,
    SourceStageStatus,
    Summary,
    Transcript,
    UserTag,
    WikiDataAlias,
    WikiDataCategory,
)
from .review_queue_service import ReviewQueueService

# HCE models are available (imported directly from models)
HCE_AVAILABLE = True

# System 2 models
try:
    pass

    SYSTEM2_AVAILABLE = True
except Exception:
    SYSTEM2_AVAILABLE = False
from .service import DatabaseService  # noqa: E402

__all__ = [
    "MediaSource",
    "Transcript",
    "Summary",
    "MOCExtraction",
    "GeneratedFile",
    "ProcessingJob",
    "BrightDataSession",
    "SourceStageStatus",
    "Base",
    "DatabaseService",
    # HCE models
    "Claim",
    "EvidenceSpan",
    "ClaimRelation",
    "Person",
    "Concept",
    "JargonTerm",
    # Speaker models
    "PersistentSpeakerProfile",
    # Review workflow
    "ReviewQueueItem",
    "ReviewQueueService",
]

# Add System 2 models to exports if available
if SYSTEM2_AVAILABLE:
    __all__.extend(["Job", "JobRun", "LLMRequest", "LLMResponse"])
