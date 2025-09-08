"""
HCE-based Summarizer Processor

Drop-in replacement for legacy SummarizerProcessor using the Hybrid Claim Extractor (HCE).
Maintains identical API while providing structured claim extraction instead of simple summaries.
"""

import hashlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..logger import get_logger
from ..processors.html import fetch_html_text
from ..utils.llm_providers import UnifiedLLMClient
from .base import BaseProcessor, ProcessorResult
from .hce.config_flex import PipelineConfigFlex, StageModelConfig
from .hce.health import HCEValidationError, validate_hce_or_raise
from .hce.types import EpisodeBundle, PipelineOutputs, Segment

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
                # Allow explicit skim model override
                skim_model_uri = (
                    self.config.models.skim
                    if hasattr(self.config.models, "skim")
                    else None
                )
                milestones = skim.skim_episode(episode, skim_model_uri)
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
        to_flagship, keep_local = router.route_claims(
            reranked, self.config.router_uncertainty_threshold
        )

        # Optional cap on flagship volume
        if (
            self.config.flagship_max_claims_per_file is not None
            and len(to_flagship) > self.config.flagship_max_claims_per_file
        ):
            to_flagship = to_flagship[: self.config.flagship_max_claims_per_file]

        # Step 7: Judge claims for final scoring (dual-judge routing if configured)
        flagship_model_uri = (
            self.config.models.flagship_judge
            if hasattr(self.config.models, "flagship_judge")
            else None
        )
        combined = keep_local + to_flagship
        scored = judge.judge_claims(
            combined,
            self.config.models.judge,
            flagship_claims=to_flagship if flagship_model_uri else None,
            flagship_model_uri=flagship_model_uri,
        )

        # Step 8: Extract entities
        people_mentions = people.extract_people(
            episode, self.config.models.people_disambiguator
        )
        mental_models = concepts.extract_concepts(episode, scored)
        jargon_terms = glossary.extract_jargon(episode)

        # Step 9: Analyze claim temporality
        from .hce.temporality import analyze_temporality

        scored_with_temporality = analyze_temporality(scored, self.config.models.judge)

        # Step 10: Extract relations
        claim_relations = relations.extract_relations(
            scored_with_temporality, self.config.models.judge
        )

        # Create initial pipeline outputs for category analysis
        initial_outputs = PipelineOutputs(
            episode_id=episode.episode_id,
            claims=scored_with_temporality,
            relations=claim_relations,
            milestones=milestones,
            people=people_mentions,
            concepts=mental_models,
            jargon=jargon_terms,
        )

        # Step 11: Analyze structured categories
        from .hce.structured_categories import analyze_structured_categories

        episode_categories = analyze_structured_categories(
            initial_outputs, self.config.models.judge
        )

        # Return final outputs with categories
        return PipelineOutputs(
            episode_id=episode.episode_id,
            claims=scored_with_temporality,
            relations=claim_relations,
            milestones=milestones,
            people=people_mentions,
            concepts=mental_models,
            jargon=jargon_terms,
            structured_categories=episode_categories,
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
        hce_options: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.hce_options = hce_options or {}
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

        # Determine flagship judge model
        flagship_judge_uri = model_uri  # Default to same model
        if self.hce_options.get("enable_routing", True):
            # Could be configured differently in advanced UI
            flagship_judge_uri = model_uri

        self.hce_config = PipelineConfigFlex(
            models=StageModelConfig(
                miner=model_uri,
                judge=model_uri,
                flagship_judge=flagship_judge_uri
                if self.hce_options.get("enable_routing", True)
                else None,
                embedder="local://bge-small-en-v1.5",
                reranker="local://bge-reranker-base",
            ),
            use_skim=self.hce_options.get("use_skim", True),
            router_uncertainty_threshold=self.hce_options.get(
                "routing_threshold", 0.35
            ),
            flagship_max_claims_per_file=self.hce_options.get(
                "flagship_file_tokens", None
            ),
        )
        # Per-stage model overrides
        try:
            miner_override = self.hce_options.get("miner_model")
            if miner_override:
                self.hce_config.models.miner = str(miner_override)
        except Exception:
            pass
        try:
            heavy_miner = self.hce_options.get("heavy_miner_model")
            if heavy_miner:
                self.hce_config.models.heavy_miner = str(heavy_miner)
        except Exception:
            pass
        try:
            embedder_override = self.hce_options.get("embedder_model")
            if embedder_override:
                self.hce_config.models.embedder = str(embedder_override)
        except Exception:
            pass
        try:
            reranker_override = self.hce_options.get("reranker_model")
            if reranker_override:
                self.hce_config.models.reranker = str(reranker_override)
        except Exception:
            pass
        # Judge routing and model overrides
        try:
            thr = self.hce_options.get("router_uncertainty_threshold")
            if isinstance(thr, (float, int)):
                self.hce_config.router_uncertainty_threshold = float(thr)
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
        try:
            fcap = self.hce_options.get("flagship_max_claims_per_file")
            if isinstance(fcap, int):
                self.hce_config.flagship_max_claims_per_file = fcap
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
        """Convert text input to HCE EpisodeBundle format."""
        # Generate a unique episode ID
        if source_file:
            episode_id = f"file_{source_file.stem}_{int(time.time())}"
        else:
            text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[
                :8
            ]
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
        # Filter claims based on tier
        min_tier = self.hce_options.get("min_claim_tier", "all")
        if min_tier == "all":
            filtered_claims = outputs.claims
        else:
            # Filter by minimum tier (A > B > C)
            tier_order = {"A": 3, "B": 2, "C": 1}
            min_tier_value = tier_order.get(min_tier, 0)
            filtered_claims = [
                c for c in outputs.claims if tier_order.get(c.tier, 0) >= min_tier_value
            ]

        # Apply max claims limit
        max_claims = self.hce_options.get("max_claims")
        if max_claims and len(filtered_claims) > max_claims:
            filtered_claims = filtered_claims[:max_claims]

        # Group claims by tier
        tier_a_claims = [c for c in filtered_claims if c.tier == "A"]
        tier_b_claims = [c for c in filtered_claims if c.tier == "B"]

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

        # Relations (if enabled)
        if self.hce_options.get("include_relations", True) and outputs.relations:
            summary_parts.append("## Relationships\n")
            for rel in outputs.relations[:10]:
                summary_parts.append(
                    f"- {rel.subject} → {rel.predicate} → {rel.object}"
                )
            summary_parts.append("")

        # Contradictions (if enabled)
        if self.hce_options.get("include_contradictions", True):
            # Check for contradicting claims
            contradictions = []
            for i, claim1 in enumerate(outputs.claims):
                for claim2 in outputs.claims[i + 1 :]:
                    if (
                        hasattr(claim1, "contradicts")
                        and claim1.contradicts == claim2.claim_id
                    ):
                        contradictions.append((claim1, claim2))

            if contradictions:
                summary_parts.append("## Potential Contradictions\n")
                for c1, c2 in contradictions[:5]:
                    summary_parts.append(f"- **Claim 1**: {c1.canonical}")
                    summary_parts.append(f"  **Claim 2**: {c2.canonical}")
                    summary_parts.append("")

        # Metadata
        summary_parts.append(
            f"\n---\n*Extracted {len(filtered_claims)} claims using HCE analysis*"
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
                # If HTML, extract readable text instead of raw markup
                if input_data.suffix.lower() in {".html", ".htm"}:
                    try:
                        text = fetch_html_text(input_data)
                    except Exception as e:
                        logger.warning(
                            f"HTML extraction failed, using raw file text: {e}"
                        )
                        text = input_data.read_text(encoding="utf-8")
                else:
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

            # Enforce HCE availability
            try:
                validate_hce_or_raise()
            except HCEValidationError as e:
                return ProcessorResult(
                    success=False,
                    errors=[
                        "HCE is required for summarization and is not fully available.",
                        str(e),
                    ],
                    metadata={"provider": self.provider, "model": self.model},
                    dry_run=dry_run,
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

            # Format as summary (HCE). If empty, still try LLM summary ONLY if explicitly allowed
            summary = self._format_claims_as_summary(outputs)

            def _build_prompt(template_path: Path | None, body_text: str) -> str:
                # Load template if provided; otherwise use a generic instruction
                try:
                    if template_path and Path(template_path).exists():
                        tmpl = Path(template_path).read_text(encoding="utf-8").strip()
                    else:
                        tmpl = (
                            "Summarize the document into key sections: Executive Summary, Key Claims, Key People, "
                            "Key Concepts, and Notable Relationships. Be concise and faithful to the source."
                        )
                except Exception:
                    tmpl = (
                        "Summarize the document into key sections: Executive Summary, Key Claims, Key People, "
                        "Key Concepts, and Notable Relationships. Be concise and faithful to the source."
                    )

                # Trim very long inputs for local models (smaller to avoid timeouts)
                max_chars = 8000
                body = (
                    body_text if len(body_text) <= max_chars else body_text[:max_chars]
                )
                # If template contains {text}, substitute directly; otherwise append content block
                if "{text}" in tmpl:
                    try:
                        return tmpl.replace("{text}", body)
                    except Exception:
                        return f"{tmpl}\n\n---\nCONTENT:\n{body}"
                return f"{tmpl}\n\n---\nCONTENT:\n{body}"

            # If HCE produced no content, use LLM fallback
            used_llm_fallback = False
            # Prompt-driven summary mode: if prefer_template_summary is True, bypass HCE formatting
            prefer_template = bool(kwargs.get("prefer_template_summary", False))
            allow_llm_fallback = (
                bool(kwargs.get("allow_llm_fallback", False)) or prefer_template
            )
            if allow_llm_fallback and (
                prefer_template
                or (not summary.strip())
                or ("Extracted 0 claims" in summary)
            ):
                try:
                    prompt = _build_prompt(kwargs.get("prompt_template"), text)
                    client = UnifiedLLMClient(provider=self.provider, model=self.model)
                    llm_resp = client.generate(prompt)
                    summary = llm_resp.content.strip()
                    used_llm_fallback = True
                except Exception as e:
                    logger.error(f"LLM fallback summarization failed: {e}")

            # Calculate token usage (approximate)
            estimated_tokens = len(text.split()) + len(summary.split())
            estimated_cost = estimated_tokens * 0.00001  # Rough estimate

            # Prepare metadata
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

            # Save to database if available
            video_id = kwargs.get("video_id")
            if video_id:
                try:
                    from ..database import DatabaseService

                    db = DatabaseService()

                    # Generate summary ID
                    import uuid

                    summary_id = str(uuid.uuid4())

                    # Save summary with HCE data
                    db.create_summary(
                        summary_id=summary_id,
                        video_id=video_id,
                        transcript_id=kwargs.get("transcript_id"),
                        summary_text=summary,
                        llm_provider=self.provider,
                        llm_model=self.model,
                        processing_type="hce",
                        hce_data_json=metadata["hce_data"],
                        total_tokens=estimated_tokens,
                        total_cost=estimated_cost,
                        metadata=metadata,
                    )

                    # Save HCE entities to separate tables
                    if hasattr(db, "save_hce_data"):
                        db.save_hce_data(video_id, outputs)

                    metadata["summary_id"] = summary_id

                except Exception as e:
                    logger.warning(f"Failed to save HCE data to database: {e}")

            # Prefer actual usage from LLM fallback if available
            usage_block = {
                "total_tokens": estimated_tokens,
                "total_cost": estimated_cost,
            }
            if used_llm_fallback:
                # We don't have exact tokens from local provider API; keep estimates
                metadata["fallback"] = "llm"

            return ProcessorResult(
                success=True,
                data=summary,
                metadata=metadata,
                usage=usage_block,
                dry_run=False,
            )

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return ProcessorResult(
                success=False,
                errors=[str(e)],
                dry_run=dry_run,
            )

    def _build_summary_index(self, output_dir: Path) -> dict[str, Any]:
        """
        Build an index of existing summary files for skip detection.

        Scans the output directory for existing summary files and builds
        a mapping of source files to their summary metadata.

        Args:
            output_dir: Directory to scan for existing summaries

        Returns:
            Dictionary mapping source file paths to summary metadata
        """
        import json
        import os
        from datetime import datetime

        summary_index = {}

        if not output_dir.exists():
            return summary_index

        try:
            # Look for summary files (both .md and .txt)
            summary_extensions = [".md", ".txt"]

            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    if any(file.endswith(ext) for ext in summary_extensions):
                        summary_path = Path(root) / file

                        try:
                            # Get file modification time
                            mtime = summary_path.stat().st_mtime

                            # Try to determine the source file from the summary filename
                            # Remove common summary suffixes
                            base_name = file
                            for suffix in [
                                "_summary",
                                "_Summary",
                                "-summary",
                                "-Summary",
                            ]:
                                if suffix in base_name:
                                    base_name = base_name.replace(suffix, "")
                                    break

                            # Remove extension and add back original extension possibilities
                            name_without_ext = Path(base_name).stem

                            # Store in index
                            summary_index[str(summary_path)] = {
                                "source_file_stem": name_without_ext,
                                "summary_path": str(summary_path),
                                "modification_time": mtime,
                                "creation_date": datetime.fromtimestamp(
                                    mtime
                                ).isoformat(),
                            }

                        except (OSError, ValueError) as e:
                            logger.warning(
                                f"Could not process summary file {summary_path}: {e}"
                            )
                            continue

        except Exception as e:
            logger.warning(f"Error building summary index: {e}")

        return summary_index

    def _save_index_to_file(
        self, index_file: Path, summary_index: dict[str, Any]
    ) -> None:
        """
        Save the summary index to a JSON file.

        Args:
            index_file: Path where to save the index
            summary_index: Index data to save
        """
        import json

        try:
            index_file.parent.mkdir(parents=True, exist_ok=True)

            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(summary_index, f, indent=2, ensure_ascii=False)

            logger.debug(
                f"Saved summary index with {len(summary_index)} entries to {index_file}"
            )

        except Exception as e:
            logger.error(f"Failed to save summary index to {index_file}: {e}")

    def _check_needs_summarization(
        self, file_path: Path, summary_index: dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Check if a file needs to be summarized based on existing summaries.

        Args:
            file_path: Path to the source file to check
            summary_index: Index of existing summaries

        Returns:
            Tuple of (needs_summary: bool, reason: str)
        """
        try:
            # If no index, always summarize
            if not summary_index:
                return True, "No existing summary index"

            # Get file modification time
            if not file_path.exists():
                return True, "Source file does not exist"

            source_mtime = file_path.stat().st_mtime
            file_stem = file_path.stem

            # Look for existing summaries that match this file
            matching_summaries = []
            for summary_path, summary_info in summary_index.items():
                if summary_info.get("source_file_stem") == file_stem:
                    matching_summaries.append((summary_path, summary_info))

            if not matching_summaries:
                return True, "No existing summary found"

            # Check if any existing summary is newer than the source file
            for summary_path, summary_info in matching_summaries:
                summary_mtime = summary_info.get("modification_time", 0)

                # If summary is newer than source, no need to re-summarize
                if summary_mtime > source_mtime:
                    return (
                        False,
                        f"Up-to-date summary exists: {Path(summary_path).name}",
                    )

            # All existing summaries are older than source file
            return True, "Source file is newer than existing summaries"

        except Exception as e:
            logger.warning(f"Error checking summarization needs for {file_path}: {e}")
            # On error, err on the side of caution and summarize
            return True, f"Error checking summary status: {e}"
