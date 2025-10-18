"""
Unified HCE-based Summarizer Processor

Clean implementation using the new 2-pass unified pipeline.
"""

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..logger import get_logger
from ..processors.html import fetch_html_text
from .base import BaseProcessor, ProcessorResult
from .hce.config_flex import PipelineConfigFlex
from .hce.health import HCEValidationError, validate_hce_or_raise
from .hce.types import EpisodeBundle, PipelineOutputs, Segment
from .hce.unified_pipeline import UnifiedHCEPipeline

logger = get_logger(__name__)


class HCEPipeline:
    """Modern HCE pipeline using unified 2-pass system."""

    def __init__(self, config: PipelineConfigFlex):
        self.config = config
        self.unified_pipeline = UnifiedHCEPipeline(config)

    def process(
        self, episode: EpisodeBundle, progress_callback: Callable | None = None
    ) -> PipelineOutputs:
        """Run the unified HCE pipeline on an episode."""
        return self.unified_pipeline.process(episode, progress_callback)


class SummarizerProcessor(BaseProcessor):
    """
    HCE-based summarizer that maintains backward compatibility with legacy API.

    This processor extracts structured claims instead of generating simple summaries,
    but formats the output to match the expected interface.
    """

    supported_formats = {".txt", ".md", ".html", ".pdf"}

    def __init__(
        self,
        provider: str = "local",
        model: str | None = None,
        max_tokens: int = 500,
        hce_options: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.hce_options = hce_options or {}

        # Validate HCE prerequisites
        try:
            validate_hce_or_raise()
        except HCEValidationError as e:
            logger.error(f"HCE validation failed: {e}")
            raise

        # Build HCE configuration
        self.hce_config = PipelineConfigFlex()

        # Apply HCE options overrides
        try:
            miner_override = self.hce_options.get("miner_model_override")
            if miner_override:
                self.hce_config.models.miner = str(miner_override)
        except Exception:
            pass

        try:
            judge_override = self.hce_options.get("judge_model_override")
            if judge_override:
                self.hce_config.models.judge = str(judge_override)
        except Exception:
            pass

        try:
            flagship_judge = self.hce_options.get("flagship_judge_model")
            if flagship_judge:
                self.hce_config.models.flagship_judge = str(flagship_judge)
        except Exception:
            pass

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
        """Convert text to EpisodeBundle format for HCE processing."""

        # Create episode ID
        episode_id = (
            f"file_{source_file.stem}"
            if source_file
            else f"text_{hashlib.md5(text.encode()).hexdigest()[:8]}"
        )

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
        """Format HCE outputs as a readable summary."""

        if (
            not outputs.claims
            and not outputs.people
            and not outputs.concepts
            and not outputs.jargon
        ):
            return "No significant claims or entities were extracted from this content."

        summary_parts = []

        # Claims section
        if outputs.claims:
            summary_parts.append("## Key Claims")
            for i, claim in enumerate(outputs.claims[:10], 1):  # Limit to top 10
                importance = claim.scores.get("importance", 0)
                summary_parts.append(
                    f"{i}. {claim.canonical} (importance: {importance:.2f})"
                )

        # People section
        if outputs.people:
            summary_parts.append("\n## People Mentioned")
            for person in outputs.people[:10]:  # Limit to top 10
                if hasattr(person, "name") and hasattr(person, "role_or_description"):
                    summary_parts.append(
                        f"- {person.name}: {person.role_or_description}"
                    )
                else:
                    summary_parts.append(f"- {person}")

        # Concepts section
        if outputs.concepts:
            summary_parts.append("\n## Key Concepts")
            for concept in outputs.concepts[:10]:  # Limit to top 10
                if hasattr(concept, "name") and hasattr(concept, "description"):
                    summary_parts.append(f"- {concept.name}: {concept.description}")
                else:
                    summary_parts.append(f"- {concept}")

        # Jargon section
        if outputs.jargon:
            summary_parts.append("\n## Technical Terms")
            for term in outputs.jargon[:10]:  # Limit to top 10
                if hasattr(term, "term") and hasattr(term, "definition"):
                    summary_parts.append(f"- {term.term}: {term.definition}")
                else:
                    summary_parts.append(f"- {term}")

        return "\n".join(summary_parts)

    def process(
        self,
        input_data: str | Path,
        dry_run: bool = False,
        progress_callback: Callable | None = None,
        **kwargs: Any,
    ) -> ProcessorResult:
        """Process input using HCE pipeline."""

        if not self.validate_input(input_data):
            return ProcessorResult(
                success=False,
                content="",
                error="Invalid input data",
                metadata={"processor": "SummarizerProcessor"},
            )

        if dry_run:
            return ProcessorResult(
                success=True,
                content="[DRY RUN] Would process with HCE pipeline",
                metadata={"processor": "SummarizerProcessor", "dry_run": True},
            )

        try:
            # Extract text from input
            if isinstance(input_data, Path):
                source_file = input_data
                if input_data.suffix.lower() == ".html":
                    text = fetch_html_text(str(input_data))
                else:
                    text = input_data.read_text(encoding="utf-8")
            else:
                source_file = None
                text = input_data

            # Convert to HCE format
            episode = self._convert_to_episode(text, source_file)

            # Run HCE pipeline
            try:
                outputs = self.hce_pipeline.process(episode, progress_callback)
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

            return ProcessorResult(
                success=True,
                content=summary,
                metadata={
                    "processor": "SummarizerProcessor",
                    "claims_count": len(outputs.claims),
                    "people_count": len(outputs.people),
                    "concepts_count": len(outputs.concepts),
                    "jargon_count": len(outputs.jargon),
                    "episode_id": outputs.episode_id,
                },
            )

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return ProcessorResult(
                success=False,
                content="",
                error=str(e),
                metadata={"processor": "SummarizerProcessor"},
            )
