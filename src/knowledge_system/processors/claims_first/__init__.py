"""
Claims-First Pipeline Module

This module implements the claims-first architecture where claim extraction
happens before speaker attribution, inverting the traditional speaker-first approach.

Key Components:
- TranscriptFetcher: Unified interface for YouTube/Whisper transcripts
- TimestampMatcher: Fuzzy matching of claims to transcript timestamps
- LazySpeakerAttributor: Targeted speaker attribution for high-value claims only
- ClaimsFirstPipeline: Main orchestrator for the claims-first workflow

Architecture:
    Transcript (YouTube/Whisper)
        ↓
    Stage 1: UnifiedMiner (extract 50-80 candidates)
        ↓
    Stage 2: FlagshipEvaluator (filter to 12-20 high-value claims)
        ↓
    Stage 3: LazySpeakerAttribution (importance >= 7 only)
        ↓
    Output: High-quality claims with targeted speaker attribution
"""

from .config import ClaimsFirstConfig
from .transcript_fetcher import TranscriptFetcher, TranscriptResult
from .timestamp_matcher import TimestampMatcher, TimestampResult
from .lazy_speaker_attribution import LazySpeakerAttributor, SpeakerAttribution
from .pipeline import ClaimsFirstPipeline

__all__ = [
    "ClaimsFirstConfig",
    "TranscriptFetcher",
    "TranscriptResult",
    "TimestampMatcher",
    "TimestampResult",
    "LazySpeakerAttributor",
    "SpeakerAttribution",
    "ClaimsFirstPipeline",
]

