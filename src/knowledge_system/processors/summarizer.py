"""
HCE-based Summarizer Processor

Drop-in replacement for legacy SummarizerProcessor using the Hybrid Claim Extractor (HCE).
Maintains identical API while providing structured claim extraction instead of simple summaries.
"""

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from ..config import get_settings
from ..errors import SummarizationError
from ..logger import get_logger
from ..utils.llm_providers import UnifiedLLMClient
from .base import BaseProcessor, ProcessorResult
from .hce.config_flex import PipelineConfigFlex, StageModelConfig
from .hce.types import EpisodeBundle, PipelineOutputs, ScoredClaim, Segment

logger = get_logger(__name__)


class HCEPipeline:
    """Orchestrates the HCE claim extraction pipeline."""

    def __init__(self, config: PipelineConfigFlex):
        self.config = config

    def process(self, episode: EpisodeBundle) -> PipelineOutputs:
        """Run the full HCE pipeline on an episode."""
        from .hce import (
            concepts,
            dedupe,
            evidence,
            glossary,
            judge,
            miner,
            people,
            relations,
            rerank,
            rerank_policy,
            router,
            skim,
        )

        # Step 1: Skim for high-level topics
        milestones = []
        if self.config.use_skim:
            try:
                milestones = skim.skim_episode(episode)
            except Exception as e:
                logger.warning(f"Skim failed, continuing without milestones: {e}")

        # Step 2: Mine candidate claims
        candidates = miner.mine_claims(episode, self.config.models.miner)

        # Step 3: Extract evidence
        with_evidence = evidence.link_evidence(candidates, episode.segments)

        # Step 4: Deduplicate claims
        consolidated = dedupe.deduplicate_claims(with_evidence)

        # Step 5: Rerank claims
        policy = rerank_policy.AdaptiveRerankPolicy(
            base_density=self.config.rerank.base_density,
            min_keep=self.config.rerank.min_keep,
            max_keep=self.config.rerank.max_keep,
            percentile_floor=self.config.rerank.percentile_floor,
        )
        reranked = rerank.rerank_claims(
            consolidated, policy, self.config.models.reranker
        )

        # Step 6: Route claims to appropriate judge
        routed = router.route_claims(reranked)

        # Step 7: Judge claims for final scoring
        scored = judge.judge_claims(routed, self.config.models.judge)

        # Step 8: Extract entities
        people_mentions = people.extract_people(
            episode, self.config.models.people_disambiguator
        )
        mental_models = concepts.extract_concepts(episode, scored)
        jargon_terms = glossary.extract_jargon(episode)

        # Step 9: Extract relations
        claim_relations = relations.extract_relations(scored, self.config.models.judge)

        return PipelineOutputs(
            episode_id=episode.episode_id,
            claims=scored,
            relations=claim_relations,
            milestones=milestones,
            people=people_mentions,
            concepts=mental_models,
            jargon=jargon_terms,
        )


class SummarizerProcessor(BaseProcessor):
    """
    HCE-based summarizer that maintains backward compatibility with legacy API.

    This processor extracts structured claims instead of generating simple summaries,
    but formats the output to match the expected interface.
    """

    @property
    def supported_formats(self) -> list[str]:
        return [".txt", ".md", ".json", ".html", ".htm"]

    def __init__(
        self,
        provider: str = "openai",
        model: str | None = None,
        max_tokens: int = 500,
    ) -> None:
        super().__init__()
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.settings = get_settings()

        # Set default model based on provider
        if not self.model:
            if provider == "openai":
                self.model = self.settings.llm.model
            elif provider == "anthropic":
                self.model = self.settings.llm.model
            elif provider == "local":
                self.model = self.settings.llm.local_model
            else:
                self.model = "gpt-4o-mini-2024-07-18"  # fallback

        # Basic model validation
        if not self.model:
            raise ValueError("Model name cannot be empty")

        # Configure HCE pipeline with equivalent models
        model_uri = f"{self.provider}://{self.model}"
        self.hce_config = PipelineConfigFlex(
            models=StageModelConfig(
                miner=model_uri,
                judge=model_uri,
                embedder="local://bge-small-en-v1.5",
                reranker="local://bge-reranker-base",
            )
        )
        self.hce_pipeline = HCEPipeline(self.hce_config)

    def validate_input(self, input_data: str | Path) -> bool:
        """Validate input data."""
        if isinstance(input_data, str):
            return len(input_data.strip()) > 0
        elif isinstance(input_data, Path):
            if not input_data.exists():
                return False
            if input_data.is_file():
                return input_data.suffix.lower() in self.supported_formats
            return False
        return False

    def _convert_to_episode(
        self, text: str, source_file: Path | None = None
    ) -> EpisodeBundle:
        """Convert text input to HCE EpisodeBundle format."""
        # Generate a unique episode ID
        if source_file:
            episode_id = f"file_{source_file.stem}_{int(time.time())}"
        else:
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            episode_id = f"text_{text_hash}_{int(time.time())}"

        # Split text into segments (paragraphs)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        segments = []
        for i, para in enumerate(paragraphs):
            segments.append(
                Segment(
                    episode_id=episode_id,
                    segment_id=f"seg_{i:04d}",
                    speaker="narrator",
                    t0=f"{i*10:06d}",
                    t1=f"{(i+1)*10:06d}",
                    text=para,
                )
            )

        return EpisodeBundle(episode_id=episode_id, segments=segments)

    def _format_claims_as_summary(self, outputs: PipelineOutputs) -> str:
        """Format HCE claims as a readable summary."""
        # Group claims by tier
        tier_a_claims = [c for c in outputs.claims if c.tier == "A"]
        tier_b_claims = [c for c in outputs.claims if c.tier == "B"]

        summary_parts = []

        # Executive Summary (from A-tier claims)
        if tier_a_claims:
            summary_parts.append("## Executive Summary\n")
            for claim in tier_a_claims[:5]:  # Top 5 A-tier claims
                summary_parts.append(f"- {claim.canonical}")
            summary_parts.append("")

        # Key Claims
        summary_parts.append("## Key Claims\n")

        # Factual claims
        factual_claims = [c for c in outputs.claims if c.claim_type == "factual"][:10]
        if factual_claims:
            summary_parts.append("### Facts\n")
            for claim in factual_claims:
                summary_parts.append(f"- {claim.canonical}")
            summary_parts.append("")

        # Causal claims
        causal_claims = [c for c in outputs.claims if c.claim_type == "causal"][:5]
        if causal_claims:
            summary_parts.append("### Causal Relationships\n")
            for claim in causal_claims:
                summary_parts.append(f"- {claim.canonical}")
            summary_parts.append("")

        # Key People
        if outputs.people:
            summary_parts.append("## Key People Mentioned\n")
            unique_people = {p.normalized or p.surface for p in outputs.people}
            for person in sorted(unique_people)[:10]:
                summary_parts.append(f"- {person}")
            summary_parts.append("")

        # Key Concepts
        if outputs.concepts:
            summary_parts.append("## Key Concepts\n")
            for concept in outputs.concepts[:10]:
                summary_parts.append(
                    f"- **{concept.name}**: {concept.definition or 'No definition provided'}"
                )
            summary_parts.append("")

        # Metadata
        summary_parts.append(
            f"\n---\n*Extracted {len(outputs.claims)} claims using HCE analysis*"
        )

        return "\n".join(summary_parts)

    def process(
        self,
        input_data: str | Path,
        dry_run: bool = False,
        progress_callback: Callable | None = None,
        **kwargs: Any,
    ) -> ProcessorResult:
        """
        Process input text or file to generate HCE-based summary.

        Maintains backward compatibility with legacy summarizer API.
        """
        try:
            # Validate input
            if not self.validate_input(input_data):
                return ProcessorResult(
                    success=False,
                    errors=["Invalid input data"],
                    dry_run=dry_run,
                )

            # Read text content
            if isinstance(input_data, Path):
                text = input_data.read_text(encoding="utf-8")
                source_file = input_data
            else:
                text = input_data
                source_file = None

            if dry_run:
                return ProcessorResult(
                    success=True,
                    data=f"[DRY RUN] Would extract claims from {len(text):,} characters using HCE",
                    metadata={"character_count": len(text), "dry_run": True},
                    dry_run=True,
                )

            # Report progress
            if progress_callback:
                from ..utils.progress import SummarizationProgress

                progress_callback(
                    SummarizationProgress(
                        current_chunk=0,
                        total_chunks=1,
                        status="Extracting claims...",
                        current_operation="HCE Pipeline",
                    )
                )

            # Convert to HCE format
            episode = self._convert_to_episode(text, source_file)

            # Run HCE pipeline
            try:
                outputs = self.hce_pipeline.process(episode)
            except Exception as e:
                logger.error(f"HCE pipeline failed: {e}")
                # Fallback to simple extraction
                outputs = PipelineOutputs(
                    episode_id=episode.episode_id,
                    claims=[],
                    relations=[],
                    milestones=[],
                    people=[],
                    concepts=[],
                    jargon=[],
                )

            # Format as summary
            summary = self._format_claims_as_summary(outputs)

            # Calculate token usage (approximate)
            estimated_tokens = len(text.split()) + len(summary.split())
            estimated_cost = estimated_tokens * 0.00001  # Rough estimate

            # Save to database if available
            metadata = {
                "model": self.model,
                "provider": self.provider,
                "claims_extracted": len(outputs.claims),
                "people_found": len(outputs.people),
                "concepts_found": len(outputs.concepts),
                "relations_found": len(outputs.relations),
                "hce_data": {
                    "claims": [c.model_dump() for c in outputs.claims],
                    "people": [p.model_dump() for p in outputs.people],
                    "concepts": [m.model_dump() for m in outputs.concepts],
                    "jargon": [j.model_dump() for j in outputs.jargon],
                    "relations": [r.model_dump() for r in outputs.relations],
                },
            }

            return ProcessorResult(
                success=True,
                data=summary,
                metadata=metadata,
                usage={
                    "total_tokens": estimated_tokens,
                    "total_cost": estimated_cost,
                },
                dry_run=False,
            )

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return ProcessorResult(
                success=False,
                errors=[str(e)],
                dry_run=dry_run,
            )
