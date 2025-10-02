"""
Unified HCE Pipeline - Simplified 2-pass system using UnifiedMiner and FlagshipEvaluator.
"""

from collections.abc import Callable
from typing import List

from ...logger import get_logger
from .config_flex import PipelineConfigFlex
from .flagship_evaluator import FlagshipEvaluationOutput, evaluate_claims_flagship
from .types import (
    EpisodeBundle,
    EvidenceSpan,
    JargonTerm,
    MentalModel,
    PersonMention,
    PipelineOutputs,
    ScoredClaim,
)
from .unified_miner import UnifiedMinerOutput, mine_episode_unified

logger = get_logger(__name__)


class UnifiedHCEPipeline:
    """
    Simplified HCE pipeline with just 2 passes:
    1. UnifiedMiner: Extract claims, jargon, people, mental models
    2. FlagshipEvaluator: Rank and filter claims
    """

    def __init__(self, config: PipelineConfigFlex):
        self.config = config

    def process(
        self, episode: EpisodeBundle, progress_callback: Callable | None = None
    ) -> PipelineOutputs:
        """Run the unified 2-pass HCE pipeline on an episode."""

        # Report progress
        def report_progress(step: str, percent: float, details: str = ""):
            if progress_callback:
                from ...utils.progress import SummarizationProgress

                progress_callback(
                    SummarizationProgress(
                        current_step=step,
                        file_percent=percent,
                        status=f"{step}: {details}" if details else step,
                    )
                )

        # Step 1: Unified Mining
        report_progress(
            "Extracting knowledge",
            25.0,
            "Mining claims, jargon, people, and mental models",
        )

        try:
            miner_outputs = mine_episode_unified(episode, self.config.models.miner)

            # Count total extractions
            total_claims = sum(len(output.claims) for output in miner_outputs)
            total_jargon = sum(len(output.jargon) for output in miner_outputs)
            total_people = sum(len(output.people) for output in miner_outputs)
            total_mental_models = sum(
                len(output.mental_models) for output in miner_outputs
            )

            logger.info(
                f"Unified mining extracted: {total_claims} claims, {total_jargon} jargon terms, "
                f"{total_people} people, {total_mental_models} mental models"
            )

        except Exception as e:
            logger.error(f"Unified mining failed: {e}")
            miner_outputs = []

        report_progress(
            "Knowledge extraction complete",
            50.0,
            f"Extracted {total_claims} claims and {total_jargon + total_people + total_mental_models} entities",
        )

        # Step 2: Create content summary for flagship evaluation
        report_progress(
            "Preparing evaluation", 60.0, "Creating content summary for flagship review"
        )

        content_summary = self._create_content_summary(episode, miner_outputs)

        # Step 3: Flagship Evaluation
        report_progress(
            "Evaluating claims", 75.0, f"Flagship review of {total_claims} claims"
        )

        try:
            flagship_model_uri = getattr(
                self.config.models, "flagship_judge", self.config.models.judge
            )
            evaluation_output = evaluate_claims_flagship(
                content_summary, miner_outputs, flagship_model_uri
            )

            logger.info(
                f"Flagship evaluation: {evaluation_output.claims_accepted} accepted, "
                f"{evaluation_output.claims_rejected} rejected from {evaluation_output.total_claims_processed} total"
            )

        except Exception as e:
            logger.error(f"Flagship evaluation failed: {e}")
            # Create empty evaluation output
            evaluation_output = FlagshipEvaluationOutput(
                {
                    "evaluated_claims": [],
                    "summary_assessment": {
                        "total_claims_processed": 0,
                        "claims_accepted": 0,
                        "claims_rejected": 0,
                        "key_themes": [],
                        "overall_quality": "error",
                        "recommendations": f"Evaluation failed: {e}",
                    },
                }
            )

        # Step 4: Convert to final output format
        report_progress("Finalizing results", 90.0, "Converting to final output format")

        final_outputs = self._convert_to_pipeline_outputs(
            episode, miner_outputs, evaluation_output
        )

        report_progress(
            "Processing complete",
            100.0,
            f"Final: {len(final_outputs.claims)} claims, {len(final_outputs.jargon)} terms",
        )

        logger.info(
            f"Pipeline complete: {len(final_outputs.claims)} final claims, "
            f"{len(final_outputs.people)} people, {len(final_outputs.concepts)} concepts, "
            f"{len(final_outputs.jargon)} jargon terms"
        )

        return final_outputs

    def _create_content_summary(
        self, episode: EpisodeBundle, miner_outputs: list[UnifiedMinerOutput]
    ) -> str:
        """Create a high-level summary of the content for flagship evaluation."""

        # Basic summary from episode
        total_segments = len(episode.segments)
        total_text_length = sum(len(seg.text) for seg in episode.segments)

        # Extract key themes from miner outputs
        all_claims = []
        for output in miner_outputs:
            all_claims.extend([claim.get("claim_text", "") for claim in output.claims])

        # Create summary
        summary_parts = [
            f"Content Analysis Summary:",
            f"- Total segments: {total_segments}",
            f"- Total text length: {total_text_length:,} characters",
            f"- Claims extracted: {len(all_claims)}",
        ]

        if all_claims:
            # Add sample claims for context
            sample_claims = all_claims[:3]
            summary_parts.append("- Sample claims:")
            for i, claim in enumerate(sample_claims, 1):
                summary_parts.append(
                    f"  {i}. {claim[:100]}{'...' if len(claim) > 100 else ''}"
                )

        return "\n".join(summary_parts)

    def _convert_to_pipeline_outputs(
        self,
        episode: EpisodeBundle,
        miner_outputs: list[UnifiedMinerOutput],
        evaluation_output: FlagshipEvaluationOutput,
    ) -> PipelineOutputs:
        """Convert unified pipeline results to the standard PipelineOutputs format."""

        # Convert accepted claims to ScoredClaim format
        scored_claims = []
        accepted_claims = evaluation_output.get_claims_by_rank()

        for eval_claim in accepted_claims:
            # Find the original claim data to get evidence
            original_claim = None
            for output in miner_outputs:
                for claim in output.claims:
                    if claim.get("claim_text", "") == eval_claim.original_claim_text:
                        original_claim = claim
                        break
                if original_claim:
                    break

            if not original_claim:
                continue

            # Convert evidence spans
            evidence_spans = []
            for evidence in original_claim.get("evidence_spans", []):
                evidence_spans.append(
                    EvidenceSpan(
                        t0=evidence.get("t0", ""),
                        t1=evidence.get("t1", ""),
                        quote=evidence.get("quote", ""),
                        segment_id=None,  # Could be enhanced later
                        context_t0=None,
                        context_t1=None,
                        context_text=None,
                        context_type="exact",
                    )
                )

            # Create scored claim
            scored_claim = ScoredClaim(
                episode_id=episode.episode_id,
                claim_id=f"claim_{len(scored_claims):04d}",
                canonical=eval_claim.get_final_claim_text(),
                claim_type=original_claim.get("claim_type", "factual"),
                evidence=evidence_spans,
                tier="A"
                if eval_claim.importance >= 8
                else "B"
                if eval_claim.importance >= 5
                else "C",
                scores={
                    "importance": eval_claim.importance
                    / 10.0,  # Convert back to 0-1 scale
                    "novelty": eval_claim.novelty / 10.0,
                    "confidence_final": eval_claim.confidence_final / 10.0,
                },
                temporality_score=3,  # Default medium-term
                temporality_confidence=0.5,
                temporality_rationale="Default temporality assignment",
                structured_categories=[],
                category_relevance_scores={},
            )

            scored_claims.append(scored_claim)

        # Convert other entities from miner outputs to proper Pydantic models

        all_jargon = []
        all_people = []
        all_mental_models = []

        for output in miner_outputs:
            # Convert jargon terms
            for i, jargon_data in enumerate(output.jargon):
                if isinstance(jargon_data, dict):
                    jargon_term = JargonTerm(
                        episode_id=episode.episode_id,
                        term_id=f"jargon_{len(all_jargon):04d}",
                        term=jargon_data.get("term", ""),
                        definition=jargon_data.get("definition"),
                        evidence_spans=[
                            EvidenceSpan(
                                t0=jargon_data.get("timestamp", "00:00"),
                                t1=jargon_data.get("timestamp", "00:00"),
                                quote=jargon_data.get("context_quote", ""),
                                segment_id=None,
                            )
                        ]
                        if jargon_data.get("context_quote")
                        else [],
                    )
                    all_jargon.append(jargon_term)

            # Convert people mentions
            for i, person_data in enumerate(output.people):
                if isinstance(person_data, dict):
                    person_mention = PersonMention(
                        episode_id=episode.episode_id,
                        mention_id=f"person_{len(all_people):04d}",
                        span_segment_id="unknown",
                        t0=person_data.get("timestamp", "00:00"),
                        t1=person_data.get("timestamp", "00:00"),
                        surface=person_data.get("name", ""),
                        normalized=person_data.get("name", ""),
                    )
                    all_people.append(person_mention)

            # Convert mental models
            for i, model_data in enumerate(output.mental_models):
                if isinstance(model_data, dict):
                    mental_model = MentalModel(
                        episode_id=episode.episode_id,
                        model_id=f"model_{len(all_mental_models):04d}",
                        name=model_data.get("name", ""),
                        definition=model_data.get("description"),
                        first_mention_ts=model_data.get("timestamp", "00:00"),
                        evidence_spans=[
                            EvidenceSpan(
                                t0=model_data.get("timestamp", "00:00"),
                                t1=model_data.get("timestamp", "00:00"),
                                quote=model_data.get("context_quote", ""),
                                segment_id=None,
                            )
                        ]
                        if model_data.get("context_quote")
                        else [],
                    )
                    all_mental_models.append(mental_model)

        # Create final pipeline outputs
        return PipelineOutputs(
            episode_id=episode.episode_id,
            claims=scored_claims,
            relations=[],  # Relations not implemented in unified pipeline yet
            milestones=[],  # Milestones not implemented in unified pipeline yet
            people=all_people,  # Raw people data for now
            concepts=all_mental_models,  # Mental models as concepts
            jargon=all_jargon,  # Raw jargon data for now
            structured_categories=[],  # Not implemented in unified pipeline yet
        )
