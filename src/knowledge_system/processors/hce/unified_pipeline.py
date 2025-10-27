"""
Unified HCE Pipeline - 4-pass system: Short Summary → Mining → Evaluation → Long Summary + Categories
"""

from collections.abc import Callable
from pathlib import Path

from ...logger import get_logger
from .config_flex import PipelineConfigFlex
from .flagship_evaluator import FlagshipEvaluationOutput, evaluate_claims_flagship
from .structured_categories import analyze_structured_categories
from .types import (
    EpisodeBundle,
    EvidenceSpan,
    JargonTerm,
    MentalModel,
    PersonMention,
    PipelineOutputs,
    ScoredClaim,
    StructuredCategory,
)
from .unified_miner import UnifiedMinerOutput, mine_episode_unified

logger = get_logger(__name__)


class UnifiedHCEPipeline:
    """
    4-pass HCE pipeline:
    0. Short Summary: Generate pre-mining contextual overview
    1. UnifiedMiner: Extract claims, jargon, people, mental models
    2. FlagshipEvaluator: Rank and filter claims
    3. Long Summary: Generate comprehensive post-evaluation analysis
    4. Categories: Analyze WikiData topic categories
    """

    def __init__(self, config: PipelineConfigFlex):
        self.config = config

    def process(
        self, episode: EpisodeBundle, progress_callback: Callable | None = None
    ) -> PipelineOutputs:
        """Run the unified 4-pass HCE pipeline on an episode."""

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

        # Step 0: Short Summary (Pre-Mining)
        report_progress(
            "Generating overview",
            10.0,
            "Creating contextual summary for evaluation",
        )

        try:
            short_summary = self._generate_short_summary(episode)
            logger.info(f"Generated short summary: {len(short_summary)} characters")
        except Exception as e:
            logger.error(f"Short summary generation failed: {e}")
            short_summary = f"Episode {episode.episode_id} content analysis."

        # Step 1: Unified Mining
        report_progress(
            "Extracting knowledge",
            30.0,
            "Mining claims, jargon, people, and mental models",
        )

        # Initialize counters
        total_claims = 0
        total_jargon = 0
        total_people = 0
        total_mental_models = 0

        try:
            # Determine max_workers based on configuration
            max_workers = None
            if (
                hasattr(self.config, "max_workers")
                and self.config.max_workers is not None
            ):
                max_workers = self.config.max_workers
            elif (
                hasattr(self.config, "enable_parallel_processing")
                and not self.config.enable_parallel_processing
            ):
                max_workers = 1  # Force sequential processing

            miner_outputs = mine_episode_unified(
                episode,
                self.config.models.miner,
                max_workers=max_workers,
                progress_callback=lambda msg: report_progress(
                    "Mining segments", 40.0, msg
                ),
                selectivity=self.config.miner_selectivity,  # NEW: Pass selectivity
            )

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
            55.0,
            f"Extracted {total_claims} claims and {total_jargon + total_people + total_mental_models} entities",
        )

        # Step 2: Prepare content summary for flagship evaluation (using short summary)
        report_progress(
            "Preparing evaluation", 60.0, "Preparing content for flagship review"
        )

        content_summary = short_summary  # Use the pre-generated short summary

        # Step 3: Parallel Evaluation of ALL Entity Types
        report_progress(
            "Evaluating all entities",
            70.0,
            f"Evaluating {total_claims} claims, {total_jargon} jargon, {total_people} people, {total_mental_models} concepts",
        )

        try:
            flagship_model_uri = getattr(
                self.config.models, "flagship_judge", self.config.models.judge
            )

            # Evaluate all entity types in parallel
            evaluation_results = self._evaluate_all_entities_parallel(
                miner_outputs, content_summary, flagship_model_uri
            )

            # Extract individual results
            claims_evaluation = evaluation_results["claims"]
            jargon_evaluation = evaluation_results["jargon"]
            people_evaluation = evaluation_results["people"]
            concepts_evaluation = evaluation_results["concepts"]

            logger.info(
                f"Evaluation complete: "
                f"Claims: {claims_evaluation.claims_accepted}/{claims_evaluation.total_claims_processed}, "
                f"Jargon: {jargon_evaluation.terms_accepted}/{jargon_evaluation.total_terms_processed}, "
                f"People: {people_evaluation.people_accepted}/{people_evaluation.total_mentions_processed}, "
                f"Concepts: {concepts_evaluation.concepts_accepted}/{concepts_evaluation.total_concepts_processed}"
            )

        except Exception as e:
            logger.error(f"Entity evaluation failed: {e}")
            # Create fallback evaluation outputs
            claims_evaluation = FlagshipEvaluationOutput(
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
            # Use miner outputs as-is for other entities (no evaluation)
            jargon_evaluation = None
            people_evaluation = None
            concepts_evaluation = None

        # Step 4: Convert to final output format (using evaluated entities)
        report_progress("Converting results", 80.0, "Converting to final output format")

        final_outputs = self._convert_to_pipeline_outputs(
            episode,
            miner_outputs,
            claims_evaluation,
            jargon_evaluation,
            people_evaluation,
            concepts_evaluation,
        )

        # Step 5: Long Summary (Post-Evaluation)
        report_progress(
            "Generating comprehensive summary",
            90.0,
            "Creating final analysis integrating all insights",
        )

        try:
            long_summary = self._generate_long_summary(
                episode, miner_outputs, claims_evaluation, short_summary, final_outputs
            )
            final_outputs.long_summary = long_summary
            logger.info(f"Generated long summary: {len(long_summary)} characters")
        except Exception as e:
            logger.error(f"Long summary generation failed: {e}")
            # Fallback to a basic summary
            final_outputs.long_summary = (
                f"{short_summary}\n\n"
                f"Analysis extracted {len(final_outputs.claims)} claims, "
                f"{len(final_outputs.people)} people mentioned, "
                f"{len(final_outputs.concepts)} mental models, "
                f"and {len(final_outputs.jargon)} technical terms."
            )

        # Step 6: Structured Categories (WikiData Topics)
        report_progress(
            "Analyzing topics",
            95.0,
            "Identifying WikiData category coverage",
        )

        try:
            categories = self._analyze_structured_categories(final_outputs)
            final_outputs.structured_categories = categories
            logger.info(f"Identified {len(categories)} structured categories")
        except Exception as e:
            logger.error(f"Category analysis failed: {e}")
            final_outputs.structured_categories = []

        # Store short summary in outputs as well
        final_outputs.short_summary = short_summary

        report_progress(
            "Processing complete",
            100.0,
            f"Final: {len(final_outputs.claims)} claims, {len(final_outputs.structured_categories)} topics",
        )

        logger.info(
            f"Pipeline complete: {len(final_outputs.claims)} final claims, "
            f"{len(final_outputs.people)} people, {len(final_outputs.concepts)} concepts, "
            f"{len(final_outputs.jargon)} jargon terms, {len(final_outputs.structured_categories)} categories"
        )

        return final_outputs

    def _evaluate_all_entities_parallel(
        self,
        miner_outputs: list,
        content_summary: str,
        evaluator_model_uri: str,
    ) -> dict:
        """
        Evaluate all entity types in parallel.

        Returns dict with keys: claims, jargon, people, concepts
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Collect all entities by type
        all_claims_raw = [c for output in miner_outputs for c in output.claims]
        all_jargon_raw = [j for output in miner_outputs for j in output.jargon]
        all_people_raw = [p for output in miner_outputs for p in output.people]
        all_concepts_raw = [m for output in miner_outputs for m in output.mental_models]

        logger.info(
            f"Starting parallel evaluation: {len(all_claims_raw)} claims, "
            f"{len(all_jargon_raw)} jargon, {len(all_people_raw)} people, {len(all_concepts_raw)} concepts"
        )

        # Import evaluators
        from .evaluators.concepts_evaluator import evaluate_concepts
        from .evaluators.jargon_evaluator import evaluate_jargon
        from .evaluators.people_evaluator import evaluate_people

        # Run all 4 evaluators in parallel
        results = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    evaluate_claims_flagship,
                    content_summary,
                    miner_outputs,
                    evaluator_model_uri,
                ): "claims",
                executor.submit(
                    evaluate_jargon,
                    content_summary,
                    all_jargon_raw,
                    evaluator_model_uri,
                ): "jargon",
                executor.submit(
                    evaluate_people,
                    content_summary,
                    all_people_raw,
                    evaluator_model_uri,
                ): "people",
                executor.submit(
                    evaluate_concepts,
                    content_summary,
                    all_concepts_raw,
                    evaluator_model_uri,
                ): "concepts",
            }

            for future in as_completed(futures):
                entity_type = futures[future]
                try:
                    results[entity_type] = future.result()
                    logger.info(f"✅ {entity_type.capitalize()} evaluation complete")
                except Exception as e:
                    logger.error(f"❌ {entity_type.capitalize()} evaluation failed: {e}")
                    # Create fallback for failed entity type
                    if entity_type == "claims":
                        results[entity_type] = FlagshipEvaluationOutput(
                            {"evaluated_claims": [], "summary_assessment": {}}
                        )
                    # Other entity types will be handled in conversion

        return results

    def _generate_short_summary(self, episode: EpisodeBundle) -> str:
        """Generate pre-mining short summary of episode content."""
        try:
            # Load short summary prompt
            prompt_path = Path(__file__).parent / "prompts" / "short_summary.txt"

            if not prompt_path.exists():
                logger.warning(f"Short summary prompt not found at {prompt_path}")
                return f"Episode {episode.episode_id}: Content analysis in progress."

            prompt_template = prompt_path.read_text()

            # Concatenate all segment texts with speaker attribution
            content_parts = []
            for seg in episode.segments:
                speaker_label = f"[{seg.speaker}] " if seg.speaker else ""
                content_parts.append(f"{speaker_label}{seg.text}")

            full_content = "\n\n".join(content_parts)

            # Create the full prompt
            full_prompt = prompt_template.replace("{content}", full_content)

            # Call LLM with miner model
            from .model_uri_parser import parse_model_uri
            from .models.llm_system2 import create_system2_llm

            # Parse model URI using the centralized parser
            model_uri = self.config.models.miner
            provider, model = parse_model_uri(model_uri)

            llm = create_system2_llm(provider=provider, model=model)
            response = llm.generate_json(full_prompt)

            # Extract text from response (handle both string and dict)
            if isinstance(response, str):
                summary_text = response
            elif isinstance(response, dict):
                summary_text = response.get("summary", str(response))
            elif isinstance(response, list) and len(response) > 0:
                summary_text = (
                    response[0] if isinstance(response[0], str) else str(response[0])
                )
            else:
                summary_text = str(response)

            return summary_text.strip()

        except Exception as e:
            logger.error(f"Failed to generate short summary: {e}")
            return f"Episode {episode.episode_id}: {len(episode.segments)} segments of content."

    def _generate_long_summary(
        self,
        episode: EpisodeBundle,
        miner_outputs: list[UnifiedMinerOutput],
        claims_evaluation: FlagshipEvaluationOutput,
        short_summary: str,
        final_outputs: PipelineOutputs,
    ) -> str:
        """Generate post-evaluation comprehensive summary with source context."""
        try:
            # Load long summary prompt
            prompt_path = Path(__file__).parent / "prompts" / "long_summary.txt"

            if not prompt_path.exists():
                logger.warning(f"Long summary prompt not found at {prompt_path}")
                return short_summary

            prompt_template = prompt_path.read_text()

            # Add source metadata context if available
            context_parts = []
            if episode.video_metadata:
                if title := episode.video_metadata.get("title"):
                    context_parts.append(f"Source Title: {title}")
                if uploader := episode.video_metadata.get("uploader"):
                    context_parts.append(f"Author/Channel: {uploader}")
                if desc := episode.video_metadata.get("description"):
                    context_parts.append(f"Description: {desc[:300]}...")
                if chapters := episode.video_metadata.get("chapters"):
                    chapter_titles = [c.get("title", "Unknown") for c in chapters[:5]]
                    context_parts.append(f"Topics Covered: {', '.join(chapter_titles)}")

            source_context = (
                "\n".join(context_parts)
                if context_parts
                else "No source metadata available"
            )

            # Format top-ranked claims
            top_claims_text = []
            for i, claim in enumerate(final_outputs.claims[:10], 1):
                importance = claim.scores.get("importance", 0) * 10
                top_claims_text.append(f"{i}. [{importance:.1f}/10] {claim.canonical}")

            # Format flagship assessment
            flagship_themes = ", ".join(claims_evaluation.key_themes)
            flagship_text = (
                f"Quality: {claims_evaluation.overall_quality}\n"
                f"Key Themes: {flagship_themes}\n"
                f"Claims Processed: {claims_evaluation.total_claims_processed}\n"
                f"Accepted: {claims_evaluation.claims_accepted}\n"
                f"Rejected: {claims_evaluation.claims_rejected}"
            )

            # Format people
            people_text = ", ".join([p.surface for p in final_outputs.people[:15]])

            # Format mental models
            models_text = ", ".join([m.name for m in final_outputs.concepts[:10]])

            # Format jargon
            jargon_text = ", ".join([j.term for j in final_outputs.jargon[:15]])

            # Format evaluation stats
            eval_stats = (
                f"Total Claims: {claims_evaluation.total_claims_processed}\n"
                f"Acceptance Rate: {claims_evaluation.claims_accepted / max(claims_evaluation.total_claims_processed, 1) * 100:.1f}%\n"
                f"Recommendations: {claims_evaluation.recommendations or 'None'}"
            )

            # Create the full prompt with source context
            full_prompt = (
                prompt_template.replace("{short_summary}", short_summary)
                .replace("{source_context}", source_context)
                .replace("{top_claims}", "\n".join(top_claims_text))
                .replace("{flagship_assessment}", flagship_text)
                .replace("{people}", people_text or "None identified")
                .replace("{mental_models}", models_text or "None identified")
                .replace("{jargon}", jargon_text or "None identified")
                .replace("{evaluation_stats}", eval_stats)
            )

            # Call LLM with flagship model
            from .model_uri_parser import parse_model_uri
            from .models.llm_system2 import create_system2_llm

            flagship_model_uri = getattr(
                self.config.models, "flagship_judge", self.config.models.judge
            )

            # Parse model URI with proper handling of local:// and other formats
            provider, model = parse_model_uri(flagship_model_uri)

            llm = create_system2_llm(provider=provider, model=model)
            response = llm.generate_json(full_prompt)

            # Extract text from response robustly
            try:
                if isinstance(response, str):
                    summary_text = response
                elif isinstance(response, dict):
                    # Prefer a 'summary' field; otherwise serialize compactly
                    summary_text = response.get("summary")
                    if summary_text is None:
                        import json as _json

                        summary_text = _json.dumps(response, ensure_ascii=False)
                elif isinstance(response, list) and len(response) > 0:
                    summary_text = (
                        response[0]
                        if isinstance(response[0], str)
                        else str(response[0])
                    )
                else:
                    summary_text = str(response)
                return (
                    summary_text.strip()
                    if isinstance(summary_text, str)
                    else str(summary_text)
                )
            except Exception:
                # As a last resort, stringify the entire object
                return str(response)

        except Exception as e:
            logger.error(f"Failed to generate long summary: {e}")
            # Return enhanced short summary as fallback
            return (
                f"{short_summary}\n\n"
                f"This analysis identified {len(final_outputs.claims)} significant claims, "
                f"with {claims_evaluation.claims_accepted} accepted by evaluation. "
                f"Key participants include {len(final_outputs.people)} individuals, "
                f"and {len(final_outputs.concepts)} mental models or frameworks were discussed."
            )

    def _analyze_structured_categories(
        self, outputs: PipelineOutputs
    ) -> list[StructuredCategory]:
        """Analyze WikiData categories for the episode."""
        try:
            # Use the miner model for category analysis
            return analyze_structured_categories(outputs, self.config.models.miner)
        except Exception as e:
            logger.error(f"Failed to analyze structured categories: {e}")
            return []

    def _convert_to_pipeline_outputs(
        self,
        episode: EpisodeBundle,
        miner_outputs: list[UnifiedMinerOutput],
        claims_evaluation,  # FlagshipEvaluationOutput
        jargon_evaluation,  # JargonEvaluationOutput | None
        people_evaluation,  # PeopleEvaluationOutput | None
        concepts_evaluation,  # ConceptsEvaluationOutput | None
    ) -> PipelineOutputs:
        """Convert unified pipeline results to the standard PipelineOutputs format using evaluated entities."""

        # Convert accepted claims to ScoredClaim format
        scored_claims = []
        accepted_claims = claims_evaluation.get_claims_by_rank()

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
                tier=(
                    "A"
                    if eval_claim.importance >= 8
                    else "B"
                    if eval_claim.importance >= 5
                    else "C"
                ),
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

        # Convert EVALUATED entities (with deduplication and filtering)
        all_jargon = []
        all_people = []
        all_mental_models = []

        # Process evaluated jargon (if evaluation succeeded)
        if jargon_evaluation:
            for eval_jargon in jargon_evaluation.get_accepted_jargon():
                jargon_term = JargonTerm(
                    episode_id=episode.episode_id,
                    term_id=f"jargon_{len(all_jargon):04d}",
                    term=eval_jargon.canonical_term,
                    definition=eval_jargon.definition,
                    category=eval_jargon.category
                    if hasattr(eval_jargon, "category")
                    else None,
                )
                all_jargon.append(jargon_term)
        else:
            # Fallback: Use raw miner outputs (no deduplication)
            for output in miner_outputs:
                for jargon_data in output.jargon:
                    if isinstance(jargon_data, dict):
                        jargon_term = JargonTerm(
                            episode_id=episode.episode_id,
                            term_id=f"jargon_{len(all_jargon):04d}",
                            term=jargon_data.get("term", ""),
                            definition=jargon_data.get("definition"),
                        )
                        all_jargon.append(jargon_term)

        # Process evaluated people (if evaluation succeeded)
        if people_evaluation:
            for eval_person in people_evaluation.get_accepted_people():
                person_mention = PersonMention(
                    episode_id=episode.episode_id,
                    mention_id=f"person_{len(all_people):04d}",
                    span_segment_id="unknown",
                    t0="00:00",
                    t1="00:00",
                    surface=eval_person.canonical_name,
                    normalized=eval_person.canonical_name,
                    entity_type="person",
                    role_description=eval_person.role
                    if hasattr(eval_person, "role")
                    else None,
                )
                all_people.append(person_mention)
        else:
            # Fallback: Use raw miner outputs (no deduplication)
            for output in miner_outputs:
                for person_data in output.people:
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

        # Process evaluated concepts (if evaluation succeeded)
        if concepts_evaluation:
            for eval_concept in concepts_evaluation.get_accepted_concepts():
                mental_model = MentalModel(
                    episode_id=episode.episode_id,
                    model_id=f"concept_{len(all_mental_models):04d}",
                    name=eval_concept.canonical_name,
                    definition=eval_concept.description,
                    first_mention_ts="00:00",
                    aliases=[],
                )
                all_mental_models.append(mental_model)
        else:
            # Fallback: Use raw miner outputs (no deduplication)
            for output in miner_outputs:
                for model_data in output.mental_models:
                    if isinstance(model_data, dict):
                        mental_model = MentalModel(
                            episode_id=episode.episode_id,
                            model_id=f"concept_{len(all_mental_models):04d}",
                            name=model_data.get("name", ""),
                            definition=model_data.get("description"),
                            first_mention_ts=model_data.get("timestamp", "00:00"),
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
