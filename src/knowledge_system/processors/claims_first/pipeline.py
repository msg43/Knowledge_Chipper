"""
Claims-First Pipeline Orchestrator

Main orchestrator for the claims-first architecture.
Coordinates transcript fetching, claim extraction, evaluation, and speaker attribution.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from knowledge_system.logger import get_logger

from .config import ClaimsFirstConfig, EvaluatorModel, TranscriptSource
from .lazy_speaker_attribution import LazySpeakerAttributor, SpeakerAttribution
from .timestamp_matcher import TimestampMatcher, TimestampResult
from .transcript_fetcher import TranscriptFetcher, TranscriptResult, TranscriptSourceType

logger = get_logger(__name__)


@dataclass
class ClaimWithMetadata:
    """A claim with all associated metadata from claims-first pipeline."""
    claim: dict  # Original claim dict from miner/evaluator
    timestamp: Optional[TimestampResult] = None
    speaker: Optional[SpeakerAttribution] = None
    
    @property
    def canonical(self) -> str:
        return self.claim.get('canonical', '')
    
    @property
    def importance(self) -> float:
        return self.claim.get('importance', 0.0)
    
    @property
    def tier(self) -> str:
        importance = self.importance
        if importance >= 8:
            return "A"
        elif importance >= 6:
            return "B"
        elif importance >= 4:
            return "C"
        else:
            return "D"


@dataclass
class ClaimsFirstResult:
    """
    Complete result from claims-first pipeline.
    
    Contains all claims with timestamps and speaker attributions,
    plus metadata about the processing.
    """
    claims: list[ClaimWithMetadata]
    transcript: TranscriptResult
    metadata: dict
    processing_stats: dict = field(default_factory=dict)
    
    @property
    def a_tier_claims(self) -> list[ClaimWithMetadata]:
        """Claims with importance >= 8."""
        return [c for c in self.claims if c.importance >= 8]
    
    @property
    def b_tier_claims(self) -> list[ClaimWithMetadata]:
        """Claims with importance 6-7."""
        return [c for c in self.claims if 6 <= c.importance < 8]
    
    @property
    def attributed_claims(self) -> list[ClaimWithMetadata]:
        """Claims with speaker attribution."""
        return [c for c in self.claims if c.speaker is not None]
    
    @property
    def total_claims(self) -> int:
        return len(self.claims)
    
    @property
    def processing_time_seconds(self) -> float:
        return self.processing_stats.get('total_time_seconds', 0.0)


class ClaimsFirstPipeline:
    """
    Main orchestrator for claims-first processing.
    
    Pipeline stages:
    1. Fetch transcript (YouTube or Whisper)
    2. Extract candidate claims (UnifiedMiner)
    3. Evaluate and filter claims (FlagshipEvaluator)
    4. Match timestamps to claims
    5. Attribute speakers to high-value claims (lazy)
    
    Usage:
        pipeline = ClaimsFirstPipeline(config)
        result = pipeline.process(
            source_url="https://youtube.com/watch?v=...",
            audio_path="/path/to/audio.mp3",
            metadata={"title": "...", "description": "..."}
        )
    """
    
    def __init__(
        self,
        config: Optional[ClaimsFirstConfig] = None,
    ):
        """
        Initialize claims-first pipeline.
        
        Args:
            config: Pipeline configuration (uses defaults if not provided)
        """
        self.config = config or ClaimsFirstConfig()
        
        # Initialize components
        self.transcript_fetcher = TranscriptFetcher()
        self.timestamp_matcher = TimestampMatcher(
            default_threshold=self.config.fuzzy_match_threshold
        )
        self.speaker_attributor = LazySpeakerAttributor(
            model=self.config.attribution_model,
            context_window_seconds=self.config.context_window_seconds,
        )
        
        # Lazy-loaded components
        self._unified_miner = None
        self._flagship_evaluator = None
    
    def _get_unified_miner(self):
        """Lazy-load UnifiedMiner."""
        if self._unified_miner is None:
            from knowledge_system.processors.hce.unified_miner import UnifiedMiner
            self._unified_miner = UnifiedMiner(
                llm_provider="gemini",
                model=self.config.miner_model,
            )
        return self._unified_miner
    
    def _get_flagship_evaluator(self):
        """Lazy-load FlagshipEvaluator."""
        if self._flagship_evaluator is None:
            from knowledge_system.processors.hce.flagship_evaluator import FlagshipEvaluator
            
            # Determine which model to use
            model = self.config.get_evaluator_model_name()
            provider = "gemini" if "gemini" in model else "anthropic"
            
            self._flagship_evaluator = FlagshipEvaluator(
                llm_provider=provider,
                model=model,
            )
        return self._flagship_evaluator
    
    def process(
        self,
        source_url: str,
        audio_path: Optional[Path] = None,
        metadata: Optional[dict] = None,
    ) -> ClaimsFirstResult:
        """
        Process a source through the claims-first pipeline.
        
        Args:
            source_url: URL of the source (YouTube URL or other)
            audio_path: Path to audio file (required for Whisper)
            metadata: Episode metadata (title, description, etc.)
        
        Returns:
            ClaimsFirstResult with all claims and metadata
        """
        start_time = time.time()
        stats = {}
        metadata = metadata or {}
        
        logger.info(f"Starting claims-first pipeline for: {source_url}")
        
        # Stage 1: Fetch transcript
        stage_start = time.time()
        transcript = self._fetch_transcript(source_url, audio_path)
        stats['transcript_time_seconds'] = time.time() - stage_start
        stats['transcript_source'] = transcript.source_type.value
        stats['transcript_quality'] = transcript.quality_score
        
        logger.info(
            f"Transcript fetched: source={transcript.source_type.value}, "
            f"quality={transcript.quality_score:.2f}, "
            f"time={stats['transcript_time_seconds']:.1f}s"
        )
        
        # Stage 2: Extract candidate claims
        stage_start = time.time()
        candidates = self._extract_candidates(transcript.text, metadata)
        stats['extraction_time_seconds'] = time.time() - stage_start
        stats['candidates_extracted'] = len(candidates)
        
        logger.info(f"Extracted {len(candidates)} candidate claims")
        
        # Stage 3: Evaluate and filter claims
        stage_start = time.time()
        evaluated_claims = self._evaluate_claims(candidates)
        stats['evaluation_time_seconds'] = time.time() - stage_start
        stats['claims_accepted'] = len(evaluated_claims)
        
        logger.info(f"Accepted {len(evaluated_claims)} claims after evaluation")
        
        # Stage 4: Match timestamps
        stage_start = time.time()
        claims_with_timestamps = self._match_timestamps(evaluated_claims, transcript)
        stats['timestamp_time_seconds'] = time.time() - stage_start
        
        # Stage 5: Lazy speaker attribution
        stage_start = time.time()
        final_claims = self._attribute_speakers(
            claims_with_timestamps, 
            transcript.text, 
            metadata
        )
        stats['attribution_time_seconds'] = time.time() - stage_start
        
        attributed_count = sum(1 for c in final_claims if c.speaker is not None)
        stats['claims_attributed'] = attributed_count
        
        logger.info(f"Attributed speakers to {attributed_count} claims")
        
        # Calculate totals
        stats['total_time_seconds'] = time.time() - start_time
        
        logger.info(
            f"Claims-first pipeline complete: "
            f"{len(final_claims)} claims, "
            f"{attributed_count} attributed, "
            f"total time={stats['total_time_seconds']:.1f}s"
        )
        
        return ClaimsFirstResult(
            claims=final_claims,
            transcript=transcript,
            metadata=metadata,
            processing_stats=stats,
        )
    
    def _fetch_transcript(
        self,
        source_url: str,
        audio_path: Optional[Path],
    ) -> TranscriptResult:
        """Fetch transcript based on config."""
        
        prefer_youtube = self.config.transcript_source in [
            TranscriptSource.AUTO, 
            TranscriptSource.YOUTUBE
        ]
        force_whisper = self.config.transcript_source == TranscriptSource.WHISPER
        
        return self.transcript_fetcher.get_transcript(
            source_url=source_url,
            audio_path=audio_path,
            prefer_youtube=prefer_youtube,
            quality_threshold=self.config.youtube_quality_threshold,
            force_whisper=force_whisper,
        )
    
    def _extract_candidates(
        self,
        transcript_text: str,
        metadata: dict,
    ) -> list[dict]:
        """Extract candidate claims using UnifiedMiner."""
        miner = self._get_unified_miner()
        
        # Call miner with plain text (claims-first mode)
        result = miner.mine(transcript_text, metadata)
        
        # Extract claims from result
        if isinstance(result, dict):
            return result.get('claims', [])
        elif hasattr(result, 'claims'):
            return result.claims
        else:
            return []
    
    def _evaluate_claims(self, candidates: list[dict]) -> list[dict]:
        """Evaluate and filter claims using FlagshipEvaluator."""
        if not candidates:
            return []
        
        evaluator = self._get_flagship_evaluator()
        
        # Evaluate claims
        evaluated = evaluator.evaluate(candidates)
        
        # Filter to accepted claims
        accepted = [
            claim for claim in evaluated
            if claim.get('accepted', True)  # Default to accepted if not specified
        ]
        
        return accepted
    
    def _match_timestamps(
        self,
        claims: list[dict],
        transcript: TranscriptResult,
    ) -> list[ClaimWithMetadata]:
        """Match claims to timestamps."""
        results = []
        
        for claim in claims:
            timestamp = self.timestamp_matcher.match_claim_to_timestamps(
                claim, 
                transcript
            )
            
            results.append(ClaimWithMetadata(
                claim=claim,
                timestamp=timestamp,
            ))
        
        return results
    
    def _attribute_speakers(
        self,
        claims: list[ClaimWithMetadata],
        transcript_text: str,
        metadata: dict,
    ) -> list[ClaimWithMetadata]:
        """Attribute speakers to high-value claims."""
        min_importance = self.config.lazy_attribution_min_importance
        
        for claim_meta in claims:
            if claim_meta.importance >= min_importance:
                claim_meta.speaker = self.speaker_attributor.attribute_speaker(
                    claim=claim_meta.claim,
                    transcript=transcript_text,
                    metadata=metadata,
                )
            # Low-importance claims keep speaker=None
        
        return claims
    
    def process_batch(
        self,
        sources: list[dict],
    ) -> list[ClaimsFirstResult]:
        """
        Process multiple sources through the pipeline.
        
        Args:
            sources: List of dicts with 'url', 'audio_path', 'metadata' keys
        
        Returns:
            List of ClaimsFirstResult for each source
        """
        results = []
        
        for i, source in enumerate(sources, 1):
            logger.info(f"Processing source {i}/{len(sources)}: {source.get('url', 'unknown')}")
            
            try:
                result = self.process(
                    source_url=source.get('url', ''),
                    audio_path=source.get('audio_path'),
                    metadata=source.get('metadata', {}),
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process source {i}: {e}")
                # Continue with other sources
        
        return results
    
    def get_pipeline_info(self) -> dict[str, Any]:
        """Get information about pipeline configuration."""
        return {
            "enabled": self.config.enabled,
            "transcript_source": self.config.transcript_source.value,
            "youtube_quality_threshold": self.config.youtube_quality_threshold,
            "evaluator_model": self.config.evaluator_model.value,
            "evaluator_model_name": self.config.get_evaluator_model_name(),
            "miner_model": self.config.miner_model,
            "lazy_attribution_min_importance": self.config.lazy_attribution_min_importance,
            "store_candidates": self.config.store_candidates,
        }

