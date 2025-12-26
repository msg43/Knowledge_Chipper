"""
Two-Pass Pipeline Orchestrator

Main orchestrator for the two-pass architecture:
- Pass 1: Extraction (extract and score all entities from complete document)
- Pass 2: Synthesis (generate world-class summary from extracted entities)

This replaces the old two-step (mining + evaluation) system.
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .extraction_pass import ExtractionPass, ExtractionResult
from .synthesis_pass import SynthesisPass, SynthesisResult

logger = logging.getLogger(__name__)


@dataclass
class TwoPassResult:
    """Complete result from two-pass pipeline."""
    # Pass 1 results
    extraction: ExtractionResult
    
    # Pass 2 results
    synthesis: SynthesisResult
    
    # Metadata
    source_id: str
    metadata: dict = field(default_factory=dict)
    processing_stats: dict = field(default_factory=dict)
    
    @property
    def total_claims(self) -> int:
        return self.extraction.total_claims
    
    @property
    def high_importance_claims(self) -> list[dict]:
        return self.extraction.high_importance_claims
    
    @property
    def flagged_claims(self) -> list[dict]:
        return self.extraction.flagged_claims
    
    @property
    def long_summary(self) -> str:
        return self.synthesis.long_summary
    
    @property
    def processing_time_seconds(self) -> float:
        return self.processing_stats.get('total_time_seconds', 0.0)


class TwoPassPipeline:
    """
    Two-Pass Pipeline Orchestrator.
    
    Coordinates the two-pass processing:
    1. Extraction Pass: Extract and score all entities from complete document
    2. Synthesis Pass: Generate world-class summary from extracted entities
    
    Usage:
        from knowledge_system.core.llm_adapter import LLMAdapter
        
        llm = LLMAdapter(provider="openai", model="gpt-4o")
        pipeline = TwoPassPipeline(llm_adapter=llm)
        
        result = pipeline.process(
            source_id="video_id",
            transcript="Complete transcript...",
            metadata={"title": "...", "channel": "..."},
            youtube_ai_summary="Optional YouTube AI summary"
        )
    """
    
    def __init__(
        self,
        llm_adapter,
        importance_threshold: float = 7.0,
    ):
        """
        Initialize two-pass pipeline.
        
        Args:
            llm_adapter: LLM adapter instance (supports complete() method)
            importance_threshold: Minimum importance for claims in synthesis (default: 7.0)
        """
        self.llm = llm_adapter
        self.importance_threshold = importance_threshold
        
        # Initialize passes
        self.extraction_pass = ExtractionPass(llm_adapter)
        self.synthesis_pass = SynthesisPass(llm_adapter)
    
    def process(
        self,
        source_id: str,
        transcript: str = None,
        metadata: dict[str, Any] = None,
        youtube_ai_summary: Optional[str] = None,
    ) -> TwoPassResult:
        """
        Process source through two-pass pipeline.
        
        Args:
            source_id: Unique identifier for source (e.g., YouTube video ID)
            transcript: Complete transcript text (optional - will be auto-selected if not provided)
            metadata: Source metadata (title, channel, description, etc.)
            youtube_ai_summary: Optional YouTube AI-generated summary
        
        Returns:
            TwoPassResult with extraction and synthesis results
        """
        start_time = time.time()
        stats = {}
        
        logger.info(f"Starting two-pass pipeline for source: {source_id}")
        
        # If transcript not provided, get best available using TranscriptManager
        if transcript is None:
            from ...services.transcript_manager import TranscriptManager
            from ...database import DatabaseService
            
            db_service = DatabaseService()
            transcript_manager = TranscriptManager(db_service=db_service)
            
            best_transcript = transcript_manager.get_best_transcript(source_id)
            
            if not best_transcript:
                raise ValueError(f"No transcript found for source: {source_id}")
            
            transcript = best_transcript.transcript_text
            
            logger.info(
                f"📄 Auto-selected transcript type: {best_transcript.transcript_type} "
                f"(quality: {best_transcript.quality_score if best_transcript.quality_score else 'N/A'})"
            )
            
            stats['transcript_type'] = best_transcript.transcript_type
            stats['transcript_quality'] = best_transcript.quality_score
            
            # Get metadata from source if not provided
            if metadata is None:
                source = db_service.get_source(source_id)
                if source:
                    metadata = {
                        "title": source.title,
                        "channel": source.uploader,
                        "description": source.description,
                        "upload_date": source.upload_date,
                    }
                else:
                    metadata = {}
        
        if metadata is None:
            metadata = {}
        
        # Pass 1: Extraction
        logger.info("=" * 60)
        logger.info("PASS 1: EXTRACTION")
        logger.info("=" * 60)
        
        pass1_start = time.time()
        try:
            extraction_result = self.extraction_pass.extract(
                transcript=transcript,
                metadata=metadata,
            )
            stats['extraction_time_seconds'] = time.time() - pass1_start
            stats['extraction_success'] = True
            
            logger.info(
                f"Pass 1 complete: {extraction_result.total_claims} claims, "
                f"{len(extraction_result.jargon)} jargon terms, "
                f"{len(extraction_result.people)} people, "
                f"{len(extraction_result.mental_models)} mental models "
                f"({stats['extraction_time_seconds']:.1f}s)"
            )
        except Exception as e:
            logger.error(f"Pass 1 (extraction) failed: {e}")
            stats['extraction_time_seconds'] = time.time() - pass1_start
            stats['extraction_success'] = False
            stats['extraction_error'] = str(e)
            raise
        
        # Pass 2: Synthesis
        logger.info("=" * 60)
        logger.info("PASS 2: SYNTHESIS")
        logger.info("=" * 60)
        
        pass2_start = time.time()
        try:
            synthesis_result = self.synthesis_pass.synthesize(
                extraction_result=extraction_result,
                metadata=metadata,
                youtube_ai_summary=youtube_ai_summary,
                importance_threshold=self.importance_threshold,
            )
            stats['synthesis_time_seconds'] = time.time() - pass2_start
            stats['synthesis_success'] = True
            
            logger.info(
                f"Pass 2 complete: Generated summary with "
                f"{len(synthesis_result.key_themes)} themes "
                f"({stats['synthesis_time_seconds']:.1f}s)"
            )
        except Exception as e:
            logger.error(f"Pass 2 (synthesis) failed: {e}")
            stats['synthesis_time_seconds'] = time.time() - pass2_start
            stats['synthesis_success'] = False
            stats['synthesis_error'] = str(e)
            raise
        
        # Calculate totals
        stats['total_time_seconds'] = time.time() - start_time
        stats['total_api_calls'] = 2  # Always 2 calls in two-pass system
        
        logger.info("=" * 60)
        logger.info(
            f"Two-pass pipeline complete: "
            f"{extraction_result.total_claims} claims, "
            f"{len(extraction_result.high_importance_claims)} high-importance, "
            f"total time={stats['total_time_seconds']:.1f}s"
        )
        logger.info("=" * 60)
        
        return TwoPassResult(
            extraction=extraction_result,
            synthesis=synthesis_result,
            source_id=source_id,
            metadata=metadata,
            processing_stats=stats,
        )
    
    def process_batch(
        self,
        sources: list[dict],
    ) -> list[TwoPassResult]:
        """
        Process multiple sources through the pipeline.
        
        Args:
            sources: List of dicts with keys:
                - source_id: Unique identifier
                - transcript: Complete transcript
                - metadata: Source metadata
                - youtube_ai_summary: Optional YouTube AI summary
        
        Returns:
            List of TwoPassResult for each source
        """
        results = []
        total_sources = len(sources)
        
        logger.info(f"Starting batch processing: {total_sources} sources")
        
        for i, source in enumerate(sources, 1):
            source_id = source.get('source_id', f'source_{i}')
            logger.info(f"\nProcessing source {i}/{total_sources}: {source_id}")
            
            try:
                result = self.process(
                    source_id=source_id,
                    transcript=source.get('transcript', ''),
                    metadata=source.get('metadata', {}),
                    youtube_ai_summary=source.get('youtube_ai_summary'),
                )
                results.append(result)
                logger.info(f"✓ Source {i}/{total_sources} complete")
            
            except Exception as e:
                logger.error(f"✗ Source {i}/{total_sources} failed: {e}")
                # Continue with other sources
        
        logger.info(
            f"\nBatch complete: {len(results)}/{total_sources} sources processed"
        )
        
        return results
    
    def get_pipeline_info(self) -> dict[str, Any]:
        """Get information about pipeline configuration."""
        return {
            "architecture": "two-pass",
            "passes": [
                {
                    "name": "extraction",
                    "description": "Extract and score all entities from complete document",
                    "outputs": ["claims", "jargon", "people", "mental_models"],
                },
                {
                    "name": "synthesis",
                    "description": "Generate world-class summary from extracted entities",
                    "outputs": ["long_summary", "key_themes"],
                },
            ],
            "importance_threshold": self.importance_threshold,
            "total_api_calls_per_source": 2,
        }

