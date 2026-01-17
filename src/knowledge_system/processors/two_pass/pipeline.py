"""
Two-Pass Pipeline Orchestrator

Main orchestrator for the two-pass architecture:
- Pass 1: Extraction (extract and score all entities from complete document)
- Pass 1.5a: Taste Filter (vector-based style validation)
- Pass 1.5b: Truth Critic (LLM-based logic validation)
- Pass 2: Synthesis (generate world-class summary from extracted entities)

This replaces the old two-step (mining + evaluation) system.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .extraction_pass import ExtractionPass, ExtractionResult
from .synthesis_pass import SynthesisPass, SynthesisResult
from .taste_filter import TasteFilter, FilterResult
from .truth_critic import TruthCritic, CriticResult

logger = logging.getLogger(__name__)


@dataclass
class TwoPassResult:
    """Complete result from two-pass pipeline."""
    # Pass 1 results
    extraction: ExtractionResult
    
    # Pass 1.5a results (optional)
    taste_filter: Optional[FilterResult] = None
    
    # Pass 1.5b results (optional)
    truth_critic: Optional[CriticResult] = None
    
    # Pass 2 results
    synthesis: SynthesisResult = None
    
    # Metadata
    source_id: str = ""
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
        from knowledge_system.config import get_settings
        
        settings = get_settings()
        provider = settings.llm.provider
        model = settings.llm.local_model if provider == "local" else settings.llm.model
        
        llm = LLMAdapter(provider=provider, model=model)
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
        enable_taste_filter: bool = True,
        enable_truth_critic: bool = True,
    ):
        """
        Initialize two-pass pipeline.
        
        Args:
            llm_adapter: LLM adapter instance (supports complete() method)
            importance_threshold: Minimum importance for claims in synthesis (default: 7.0)
            enable_taste_filter: Enable Pass 1.5a vector-based style validation
            enable_truth_critic: Enable Pass 1.5b LLM-based logic validation
        """
        self.llm = llm_adapter
        self.importance_threshold = importance_threshold
        self.enable_taste_filter = enable_taste_filter
        self.enable_truth_critic = enable_truth_critic
        
        # Initialize passes
        self.extraction_pass = ExtractionPass(llm_adapter)
        self.synthesis_pass = SynthesisPass(llm_adapter)
        
        # Initialize validation passes (lazy-loaded when needed)
        self._taste_filter: Optional[TasteFilter] = None
        self._truth_critic: Optional[TruthCritic] = None
    
    @property
    def taste_filter(self) -> TasteFilter:
        """Lazy-load the taste filter."""
        if self._taste_filter is None:
            self._taste_filter = TasteFilter()
        return self._taste_filter
    
    @property
    def truth_critic(self) -> TruthCritic:
        """Lazy-load the truth critic."""
        if self._truth_critic is None:
            self._truth_critic = TruthCritic(llm_adapter=self.llm)
        return self._truth_critic
    
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
        
        # Pass 1.5a: Taste Filter (Vector-based style validation)
        filter_result = None
        if self.enable_taste_filter:
            logger.info("=" * 60)
            logger.info("PASS 1.5a: TASTE FILTER (Vector Validation)")
            logger.info("=" * 60)
            
            pass15a_start = time.time()
            try:
                # Convert extraction result to dict for filtering
                extraction_dict = {
                    "claims": extraction_result.claims,
                    "people": extraction_result.people,
                    "jargon": extraction_result.jargon,
                    "concepts": extraction_result.mental_models,
                }
                
                filter_result = self.taste_filter.filter(extraction_dict)
                
                # Apply filtered results back to extraction_result
                extraction_result = self._apply_filter_results(
                    extraction_result, filter_result
                )
                
                stats['taste_filter_time_seconds'] = time.time() - pass15a_start
                stats['taste_filter_stats'] = filter_result.stats
                
                logger.info(
                    f"Pass 1.5a complete: {filter_result.stats['discarded']} discarded, "
                    f"{filter_result.stats['flagged']} flagged, "
                    f"{filter_result.stats['boosted']} boosted "
                    f"({stats['taste_filter_time_seconds']:.1f}s)"
                )
            except Exception as e:
                logger.warning(f"Pass 1.5a (taste filter) failed: {e} - continuing without filtering")
                stats['taste_filter_error'] = str(e)
        
        # Pass 1.5b: Truth Critic (LLM-based logic validation)
        critic_result = None
        if self.enable_truth_critic:
            logger.info("=" * 60)
            logger.info("PASS 1.5b: TRUTH CRITIC (LLM Validation)")
            logger.info("=" * 60)
            
            pass15b_start = time.time()
            try:
                # Convert extraction result to dict for critic
                extraction_dict = {
                    "claims": extraction_result.claims,
                    "people": extraction_result.people,
                    "jargon": extraction_result.jargon,
                    "concepts": extraction_result.mental_models,
                }
                
                # Run async validation (CRITICAL: pass full transcript for entity-local context)
                critic_result = asyncio.get_event_loop().run_until_complete(
                    self.truth_critic.validate(
                        extraction_dict,
                        full_transcript=transcript  # Pass full transcript, not truncated!
                    )
                )
                
                # Apply critic verdicts to extraction_result
                extraction_result = self._apply_critic_verdicts(
                    extraction_result, critic_result
                )
                
                stats['truth_critic_time_seconds'] = time.time() - pass15b_start
                stats['truth_critic_stats'] = critic_result.stats
                
                logger.info(
                    f"Pass 1.5b complete: {critic_result.stats['reviewed']} reviewed, "
                    f"{critic_result.stats['overridden']} overridden, "
                    f"{critic_result.stats['flagged']} flagged "
                    f"({stats['truth_critic_time_seconds']:.1f}s)"
                )
            except Exception as e:
                logger.warning(f"Pass 1.5b (truth critic) failed: {e} - continuing without validation")
                stats['truth_critic_error'] = str(e)
        
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
            taste_filter=filter_result,
            truth_critic=critic_result,
            synthesis=synthesis_result,
            source_id=source_id,
            metadata=metadata,
            processing_stats=stats,
        )
    
    def _apply_filter_results(
        self,
        extraction_result: ExtractionResult,
        filter_result: FilterResult
    ) -> ExtractionResult:
        """Apply taste filter results to extraction result."""
        # Replace entity lists with filtered versions
        extraction_result.claims = filter_result.claims
        extraction_result.people = filter_result.people
        extraction_result.jargon = filter_result.jargon
        extraction_result.mental_models = filter_result.concepts
        
        return extraction_result
    
    def _apply_critic_verdicts(
        self,
        extraction_result: ExtractionResult,
        critic_result: CriticResult
    ) -> ExtractionResult:
        """Apply truth critic verdicts to extraction result."""
        # Build lookup of verdicts by entity text
        verdict_lookup = {}
        for verdict in critic_result.verdicts:
            # The entity_id contains the type and hash
            verdict_lookup[verdict.entity_id] = verdict
        
        # Apply overrides and flags to entities
        for verdict in critic_result.verdicts:
            if verdict.action == "override":
                # Mark entity as overridden (will be filtered or reclassified)
                self._mark_entity_overridden(extraction_result, verdict)
            elif verdict.action == "flag":
                # Mark entity as flagged for review
                self._mark_entity_flagged(extraction_result, verdict)
        
        return extraction_result
    
    def _mark_entity_overridden(
        self,
        extraction_result: ExtractionResult,
        verdict
    ) -> None:
        """Mark an entity as overridden by the critic."""
        entity_type = verdict.original_type
        
        # Get the appropriate list
        if entity_type == "claim":
            entities = extraction_result.claims
        elif entity_type == "person":
            entities = extraction_result.people
        elif entity_type == "jargon":
            entities = extraction_result.jargon
        elif entity_type == "concept":
            entities = extraction_result.mental_models
        else:
            return
        
        # Find and mark the entity
        for entity in entities:
            entity_text = self._get_entity_text(entity, entity_type)
            if entity_text and hash(entity_text) % 10000 == int(verdict.entity_id.split('_')[-1]):
                entity["_critic_override"] = True
                entity["_critic_reasoning"] = verdict.reasoning
                entity["_critic_warning"] = verdict.warning_message
                if verdict.corrected_type:
                    entity["_corrected_type"] = verdict.corrected_type
                break
    
    def _mark_entity_flagged(
        self,
        extraction_result: ExtractionResult,
        verdict
    ) -> None:
        """Mark an entity as flagged by the critic."""
        entity_type = verdict.original_type
        
        # Get the appropriate list
        if entity_type == "claim":
            entities = extraction_result.claims
        elif entity_type == "person":
            entities = extraction_result.people
        elif entity_type == "jargon":
            entities = extraction_result.jargon
        elif entity_type == "concept":
            entities = extraction_result.mental_models
        else:
            return
        
        # Find and mark the entity
        for entity in entities:
            entity_text = self._get_entity_text(entity, entity_type)
            if entity_text and hash(entity_text) % 10000 == int(verdict.entity_id.split('_')[-1]):
                entity["_critic_flagged"] = True
                entity["_critic_reasoning"] = verdict.reasoning
                entity["_critic_warning"] = verdict.warning_message
                break
    
    def _get_entity_text(self, entity: dict, entity_type: str) -> Optional[str]:
        """Extract the text content from an entity."""
        if entity_type == "claim":
            return entity.get("canonical") or entity.get("text")
        elif entity_type == "person":
            return entity.get("name")
        elif entity_type == "jargon":
            return entity.get("term")
        elif entity_type == "concept":
            return entity.get("name")
        return None
    
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
        passes = [
            {
                "name": "extraction",
                "description": "Extract and score all entities from complete document",
                "outputs": ["claims", "jargon", "people", "mental_models"],
            },
        ]
        
        if self.enable_taste_filter:
            passes.append({
                "name": "taste_filter",
                "description": "Vector-based style validation (discard/flag/boost)",
                "outputs": ["filtered_entities", "filter_stats"],
            })
        
        if self.enable_truth_critic:
            passes.append({
                "name": "truth_critic",
                "description": "LLM-based logic validation for high-importance entities",
                "outputs": ["critic_verdicts", "critic_stats"],
            })
        
        passes.append({
            "name": "synthesis",
            "description": "Generate world-class summary from extracted entities",
            "outputs": ["long_summary", "key_themes"],
        })
        
        return {
            "architecture": "two-pass-with-validation",
            "passes": passes,
            "importance_threshold": self.importance_threshold,
            "enable_taste_filter": self.enable_taste_filter,
            "enable_truth_critic": self.enable_truth_critic,
            "total_api_calls_per_source": 2 + (1 if self.enable_truth_critic else 0),
        }

