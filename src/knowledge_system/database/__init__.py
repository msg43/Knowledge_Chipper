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
    PlatformCategory,
    PlatformTag,
    ProcessingJob,
    Segment,
    SourcePlatformCategory,
    SourcePlatformTag,
    Summary,
    Transcript,
    UserTag,
    WikiDataAlias,
    WikiDataCategory,
)

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
    "Base",
    "DatabaseService",
    # HCE models
    "Claim",
    "EvidenceSpan",
    "ClaimRelation",
    "Person",
    "Concept",
    "JargonTerm",
]

# Add System 2 models to exports if available
if SYSTEM2_AVAILABLE:
    __all__.extend(["Job", "JobRun", "LLMRequest", "LLMResponse"])
