"""
Two-Pass Processing System

Modern claim extraction architecture using whole-document processing:
- Pass 1: Extract and score ALL entities from complete document
- Pass 2: Generate world-class summary from extracted entities

This replaces the legacy two-step (mining + evaluation) system.

Architecture:
    Transcript (complete document)
        ↓
    Pass 1: Extraction Pass
        - Extract claims with 6-dimension scoring
        - Extract jargon terms with definitions
        - Extract people mentioned with context
        - Extract mental models with implications
        - Infer speakers with confidence scoring
        - Calculate absolute importance scores (0-10)
        ↓
    Pass 2: Synthesis Pass
        - Filter high-importance claims (≥7.0)
        - Integrate all entities (claims, jargon, people, models)
        - Generate world-class long summary
        - Organize thematically, not chronologically
        ↓
    Output: Complete structured knowledge + narrative synthesis

Key Benefits:
- Whole-document processing (no segmentation)
- Preserves complete argument structures
- Only 2 API calls per source
- Absolute importance scoring (globally comparable)
- Speaker inference without diarization
- World-class narrative synthesis
"""

from .extraction_pass import ExtractionPass, ExtractionResult
from .synthesis_pass import SynthesisPass, SynthesisResult
from .pipeline import TwoPassPipeline, TwoPassResult

__all__ = [
    "ExtractionPass",
    "ExtractionResult",
    "SynthesisPass",
    "SynthesisResult",
    "TwoPassPipeline",
    "TwoPassResult",
]

