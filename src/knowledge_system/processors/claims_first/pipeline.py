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
    rejected_claims: list[dict] = field(default_factory=list)  # Claims rejected by evaluator
    candidates_count: int = 0  # Total candidates before evaluation
    
    @property
    def acceptance_rate(self) -> float:
        """Ratio of accepted claims to total candidates."""
        if self.candidates_count == 0:
            return 0.0
        return len(self.claims) / self.candidates_count
    
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
    
    @property
    def quality_assessment(self) -> dict:
        """
        Passive assessment of extraction quality.
        
        Returns a dict with:
        - acceptable: bool - Whether quality meets thresholds
        - transcript_quality: float - Raw quality score (0-1)
        - acceptance_rate: float - Ratio of accepted claims
        - suggestion: str | None - Action suggestion if quality is low
        - status: str - 'Good', 'Acceptable', 'Needs Review', or 'Poor'
        """
        transcript_quality = self.transcript.quality_score if self.transcript else 0.0
        acceptance = self.acceptance_rate
        
        # Determine if acceptable (both transcript and acceptance rate OK)
        acceptable = transcript_quality >= 0.7 and acceptance >= 0.15
        
        # Determine status
        if transcript_quality >= 0.8 and acceptance >= 0.25:
            status = "Good"
        elif transcript_quality >= 0.7 and acceptance >= 0.15:
            status = "Acceptable"
        elif transcript_quality >= 0.5 or acceptance >= 0.10:
            status = "Needs Review"
        else:
            status = "Poor"
        
        # Build suggestion
        suggestion = None
        if transcript_quality < 0.7:
            suggestion = "Consider re-extraction with Whisper for better transcript quality"
        elif acceptance < 0.15:
            suggestion = "Low acceptance rate - review rejected claims for false negatives"
        
        return {
            "acceptable": acceptable,
            "transcript_quality": transcript_quality,
            "acceptance_rate": acceptance,
            "suggestion": suggestion,
            "status": status,
        }


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
            from knowledge_system.processors.hce.models.llm_system2 import System2LLM
            
            # Check which providers are available
            def _is_google_available():
                try:
                    import google.generativeai
                    return True
                except ImportError:
                    return False
            
            # Determine provider from miner_model config
            configured_model = self.config.miner_model.lower()
            
            if "gemini" in configured_model:
                # Gemini requested - check if Google is available
                if _is_google_available():
                    provider = "google"
                    model = self.config.miner_model
                else:
                    # Fall back to OpenAI
                    logger.warning(
                        "Google AI not installed, falling back to OpenAI for miner"
                    )
                    provider = "openai"
                    model = "gpt-4o-mini"
            elif "claude" in configured_model:
                provider = "anthropic"
                model = self.config.miner_model
            elif "gpt" in configured_model:
                provider = "openai"
                model = self.config.miner_model
            else:
                # Default to OpenAI
                provider = "openai"
                model = "gpt-4o-mini"
            
            llm = System2LLM(
                provider=provider,
                model=model,
                temperature=0.3,
            )
            self._unified_miner = UnifiedMiner(llm=llm)
        return self._unified_miner
    
    def _get_flagship_evaluator(self):
        """Lazy-load FlagshipEvaluator."""
        if self._flagship_evaluator is None:
            from knowledge_system.processors.hce.flagship_evaluator import (
                FlagshipEvaluator,
                ConfigurableFlagshipEvaluator,
            )
            from knowledge_system.processors.hce.models.llm_system2 import System2LLM
            
            # Check which providers are available
            def _is_google_available():
                try:
                    import google.generativeai
                    return True
                except ImportError:
                    return False
            
            # Use ConfigurableFlagshipEvaluator for flexible model selection
            evaluator_model = self.config.evaluator_model.value
            
            if evaluator_model == "configurable":
                # Use auto-upgrade based on claim count
                self._flagship_evaluator = ConfigurableFlagshipEvaluator(
                    default_model="openai",  # Default to OpenAI
                    auto_upgrade_threshold=50,
                )
            else:
                # Determine provider from model name
                model_name = self.config.get_evaluator_model_name()
                
                if "gemini" in model_name.lower():
                    if _is_google_available():
                        provider = "google"
                    else:
                        logger.warning(
                            "Google AI not installed, falling back to OpenAI for evaluator"
                        )
                        provider = "openai"
                        model_name = "gpt-4o"
                elif "claude" in model_name.lower():
                    provider = "anthropic"
                else:
                    provider = "openai"
                    if not any(x in model_name.lower() for x in ["gpt", "openai"]):
                        model_name = "gpt-4o"  # Default to GPT-4o
                
                llm = System2LLM(
                    provider=provider,
                    model=model_name,
                    temperature=0.3,
                )
                self._flagship_evaluator = FlagshipEvaluator(llm=llm)
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
        candidates_count = len(candidates)
        
        logger.info(f"Extracted {len(candidates)} candidate claims")
        
        # Stage 3: Evaluate and filter claims
        stage_start = time.time()
        evaluated_claims, rejected_claims = self._evaluate_claims(candidates)
        stats['evaluation_time_seconds'] = time.time() - stage_start
        stats['claims_accepted'] = len(evaluated_claims)
        stats['claims_rejected'] = len(rejected_claims)
        
        logger.info(
            f"Evaluation complete: {len(evaluated_claims)} accepted, "
            f"{len(rejected_claims)} rejected"
        )
        
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
            rejected_claims=rejected_claims,
            candidates_count=candidates_count,
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
    
    def _evaluate_claims(self, candidates: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Evaluate and filter claims using FlagshipEvaluator.
        
        Returns:
            Tuple of (accepted_claims, rejected_claims)
        """
        if not candidates:
            return [], []
        
        evaluator = self._get_flagship_evaluator()
        
        # Evaluate claims
        evaluated = evaluator.evaluate(candidates)
        
        # Separate accepted and rejected claims
        accepted = []
        rejected = []
        
        for claim in evaluated:
            if claim.get('accepted', True):  # Default to accepted if not specified
                accepted.append(claim)
            else:
                rejected.append(claim)
        
        # Also try to get any additional rejected claims from evaluator
        if hasattr(evaluator, 'get_rejected_claims'):
            try:
                evaluator_rejected = evaluator.get_rejected_claims()
                # Convert to dicts if needed
                for claim in evaluator_rejected:
                    if hasattr(claim, '__dict__'):
                        rejected.append(vars(claim))
                    elif isinstance(claim, dict):
                        rejected.append(claim)
            except Exception as e:
                logger.debug(f"Could not get rejected claims from evaluator: {e}")
        
        return accepted, rejected
    
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
    
    def promote_claim(
        self,
        result: ClaimsFirstResult,
        claim_index: int,
    ) -> ClaimsFirstResult:
        """
        Promote a rejected claim back to accepted.
        
        The claim goes through TimestampMatcher and (if A/B tier) SpeakerAttributor,
        then is added to the accepted claims list.
        
        Args:
            result: The ClaimsFirstResult containing the rejected claim
            claim_index: Index of the claim in rejected_claims list
            
        Returns:
            Updated ClaimsFirstResult with claim moved to accepted
        """
        if claim_index < 0 or claim_index >= len(result.rejected_claims):
            logger.error(f"Invalid claim index: {claim_index}")
            return result
        
        # Pop the claim from rejected
        claim = result.rejected_claims.pop(claim_index)
        
        # Run through timestamp matching
        timestamp = self.timestamp_matcher.match_claim_to_timestamps(
            claim, 
            result.transcript
        )
        
        # Create ClaimWithMetadata
        claim_meta = ClaimWithMetadata(
            claim=claim,
            timestamp=timestamp,
        )
        
        # Check if A/B tier (importance >= 6)
        importance = claim.get('importance', 0)
        if importance >= self.config.lazy_attribution_min_importance:
            claim_meta.speaker = self.speaker_attributor.attribute_speaker(
                claim=claim,
                transcript=result.transcript.text,
                metadata=result.metadata,
            )
        
        # Add to accepted claims
        result.claims.append(claim_meta)
        
        logger.info(f"Promoted claim to accepted: {claim.get('claim_text', '')[:50]}...")
        
        return result
    
    def generate_summaries(
        self,
        result: ClaimsFirstResult,
        yt_ai_summary: Optional[str] = None,
        jargon: Optional[list[dict]] = None,
        people: Optional[list[dict]] = None,
        concepts: Optional[list[dict]] = None,
    ) -> dict[str, str]:
        """
        Generate KC short and long summaries from ALL available data.
        
        Short summary: 1-2 paragraphs, key takeaways
        Long summary: Executive-level, integrates all sources into 
                      condensed but highly informative artifact
        
        Args:
            result: The ClaimsFirstResult with claims and transcript
            yt_ai_summary: YouTube AI-generated summary if available
            jargon: Extracted jargon terms with definitions
            people: Mentioned people with context
            concepts: Mental models and concepts
        
        Returns:
            Dict with 'short' and 'long' summary strings
        """
        from pathlib import Path
        from knowledge_system.processors.hce.models.llm_system2 import System2LLM
        
        # Load prompt templates
        prompts_dir = Path(__file__).parent.parent / "hce" / "prompts"
        
        try:
            short_prompt_template = (prompts_dir / "short_summary.txt").read_text()
        except FileNotFoundError:
            short_prompt_template = """
            Generate a 1-2 paragraph summary of the content based on:
            - Title: {title}
            - Description: {description}
            - Key claims: {claims}
            Write in clear, analytical prose.
            """
        
        try:
            long_prompt_template = (prompts_dir / "long_summary.txt").read_text()
        except FileNotFoundError:
            long_prompt_template = """
            Generate a comprehensive 3-5 paragraph executive summary based on:
            - Short summary: {short_summary}
            - Top claims: {top_claims}
            - People: {people}
            - Jargon: {jargon}
            - Concepts: {mental_models}
            Write in clear, sophisticated analytical prose.
            """
        
        # Initialize LLM
        llm = System2LLM(
            provider="openai",
            model="gpt-4o-mini",
            temperature=0.3,
        )
        
        # Prepare data for short summary
        title = result.metadata.get('title', 'Unknown Title')
        description = result.metadata.get('description', '')[:500]
        channel = result.metadata.get('channel', result.metadata.get('uploader', ''))
        
        # Get top claims for summary (limit to top 10 by importance)
        sorted_claims = sorted(
            result.claims, 
            key=lambda c: c.importance, 
            reverse=True
        )[:10]
        
        claims_text = "\n".join([
            f"- [{c.tier}] {c.claim.get('claim_text', c.claim.get('canonical', ''))}"
            for c in sorted_claims
        ])
        
        # Generate short summary first
        short_content = f"""
Title: {title}
Channel: {channel}
Description: {description}

Key Claims:
{claims_text}

YouTube AI Summary (if available): {yt_ai_summary or 'Not available'}
"""
        
        short_prompt = short_prompt_template.replace("{content}", short_content)
        
        try:
            short_summary = llm.complete(short_prompt)
        except Exception as e:
            logger.error(f"Failed to generate short summary: {e}")
            short_summary = f"Summary not available. Error: {str(e)}"
        
        # Prepare data for long summary
        top_claims_text = "\n".join([
            f"- [Importance: {c.importance}] {c.claim.get('claim_text', c.claim.get('canonical', ''))}"
            f"\n  Evidence: {c.claim.get('evidence', c.claim.get('evidence_quote', 'N/A'))[:200]}"
            for c in sorted_claims
        ])
        
        # Format people
        people_text = "None identified"
        if people:
            people_text = "\n".join([
                f"- {p.get('name', 'Unknown')}: {p.get('context', p.get('description', ''))[:100]}"
                for p in people[:10]
            ])
        
        # Format jargon
        jargon_text = "None identified"
        if jargon:
            jargon_text = "\n".join([
                f"- {j.get('term', 'Unknown')}: {j.get('definition', j.get('description', ''))[:100]}"
                for j in jargon[:10]
            ])
        
        # Format concepts/mental models
        concepts_text = "None identified"
        if concepts:
            concepts_text = "\n".join([
                f"- {c.get('name', c.get('term', 'Unknown'))}: {c.get('description', '')[:100]}"
                for c in concepts[:10]
            ])
        
        # Build evaluation stats
        eval_stats = f"""
- Total candidates: {result.candidates_count}
- Claims accepted: {len(result.claims)}
- Claims rejected: {len(result.rejected_claims)}
- Acceptance rate: {result.acceptance_rate:.1%}
- Transcript quality: {result.transcript.quality_score:.2f}
"""
        
        # Build flagship assessment (summary of themes)
        flagship_assessment = f"""
Main themes based on extracted claims and metadata.
YouTube AI perspective: {yt_ai_summary or 'Not available'}
"""
        
        long_prompt = long_prompt_template
        long_prompt = long_prompt.replace("{short_summary}", short_summary)
        long_prompt = long_prompt.replace("{top_claims}", top_claims_text)
        long_prompt = long_prompt.replace("{flagship_assessment}", flagship_assessment)
        long_prompt = long_prompt.replace("{people}", people_text)
        long_prompt = long_prompt.replace("{mental_models}", concepts_text)
        long_prompt = long_prompt.replace("{jargon}", jargon_text)
        long_prompt = long_prompt.replace("{evaluation_stats}", eval_stats)
        
        try:
            long_summary = llm.complete(long_prompt)
        except Exception as e:
            logger.error(f"Failed to generate long summary: {e}")
            long_summary = f"Summary not available. Error: {str(e)}"
        
        logger.info("Generated KC summaries successfully")
        
        return {
            "short": short_summary,
            "long": long_summary,
        }
    
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

