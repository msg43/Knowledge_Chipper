"""Mining integration for System2Orchestrator using UnifiedHCEPipeline."""

import logging
import os
from pathlib import Path
from typing import Any

from ..database.hce_store import HCEStore
from ..errors import ErrorCode, KnowledgeSystemError
from ..processors.hce.config_flex import PipelineConfigFlex, StageModelConfig
from ..processors.hce.types import EpisodeBundle, Segment
from ..processors.hce.unified_pipeline import UnifiedHCEPipeline

logger = logging.getLogger(__name__)


async def process_mine_with_unified_pipeline(
    orchestrator,  # System2Orchestrator instance
    episode_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """
    Process mining job using UnifiedHCEPipeline for parallel processing and rich data.

    Benefits over old approach:
    - 3-8x faster via parallel processing
    - Evidence spans with timestamps
    - Claim evaluation and A/B/C ranking
    - Relations between claims
    - Structured categories
    """

    try:
        # 1. Load transcript
        if orchestrator.progress_callback:
            orchestrator.progress_callback("loading", 0, episode_id)

        file_path = config.get("file_path")
        if not file_path:
            raise KnowledgeSystemError(
                f"No file_path in config for episode {episode_id}",
                ErrorCode.INVALID_INPUT,
            )

        transcript_text = Path(file_path).read_text()

        # 2. Parse transcript to segments
        if orchestrator.progress_callback:
            orchestrator.progress_callback("parsing", 5, episode_id)

        segments = orchestrator._parse_transcript_to_segments(
            transcript_text, episode_id
        )

        if not segments:
            logger.warning(f"No segments parsed from transcript for {episode_id}")
            return {
                "status": "succeeded",
                "output_id": episode_id,
                "result": {
                    "claims_extracted": 0,
                    "evidence_spans": 0,
                    "jargon_extracted": 0,
                    "people_extracted": 0,
                    "mental_models_extracted": 0,
                    "relations": 0,
                    "categories": 0,
                },
            }

        logger.info(f"📄 Parsed {len(segments)} segments for mining")

        # 3. Create EpisodeBundle
        episode_bundle = EpisodeBundle(episode_id=episode_id, segments=segments)

        # 4. Configure HCE Pipeline
        miner_model = config.get("miner_model", "ollama:qwen2.5:7b-instruct")

        # Allow configuration of parallelization
        max_workers = config.get("max_workers", None)  # None = auto-calculate
        enable_parallel = config.get("enable_parallel_processing", True)

        hce_config = PipelineConfigFlex(
            models=StageModelConfig(
                miner=miner_model,
                judge=miner_model,  # Can be different model if needed
                flagship_judge=miner_model,  # Can be different model if needed
            ),
            max_workers=max_workers if enable_parallel else 1,
            enable_parallel_processing=enable_parallel,
        )

        logger.info(
            f"🔧 HCE Config: miner={miner_model}, "
            f"parallel={'auto' if max_workers is None and enable_parallel else max_workers}, "
            f"run_id={run_id}"
        )

        # 5. Initialize UnifiedHCEPipeline
        pipeline = UnifiedHCEPipeline(hce_config)

        # 6. Create progress callback wrapper
        def progress_wrapper(progress_obj):
            """Wrap pipeline progress to orchestrator format."""
            if orchestrator.progress_callback:
                # Pipeline reports SummarizationProgress objects
                # Map to orchestrator's callback format
                step = (
                    progress_obj.current_step
                    if hasattr(progress_obj, "current_step")
                    else "processing"
                )
                percent = (
                    progress_obj.file_percent
                    if hasattr(progress_obj, "file_percent")
                    else 0
                )
                # Map 0-100% to orchestrator's 10-95% range
                adjusted_percent = 10 + int(percent * 0.85)
                orchestrator.progress_callback(step, adjusted_percent, episode_id)

        # 7. Process with full pipeline (mining + evaluation + categories)
        logger.info(f"🚀 Starting UnifiedHCEPipeline for {len(segments)} segments")

        # Align adapter local concurrency with pipeline workers for this run
        try:
            effective_workers = hce_config.max_workers if enable_parallel else 1
            if effective_workers:
                os.environ["HCE_EFFECTIVE_MAX_WORKERS"] = str(effective_workers)
                logger.info(
                    f"Concurrency alignment: HCE_EFFECTIVE_MAX_WORKERS={effective_workers}"
                )
        except Exception:
            pass

        pipeline_outputs = pipeline.process(
            episode_bundle, progress_callback=progress_wrapper
        )

        logger.info(
            f"✅ Pipeline complete: {len(pipeline_outputs.claims)} claims, "
            f"{sum(len(c.evidence) for c in pipeline_outputs.claims)} evidence spans, "
            f"{len(pipeline_outputs.relations)} relations, "
            f"{len(pipeline_outputs.structured_categories)} categories"
        )

        # 8. Store rich outputs to main database (claim-centric schema)
        if orchestrator.progress_callback:
            orchestrator.progress_callback("storing", 90, episode_id)

        try:
            # Determine source_id (strip episode_ prefix if present)
            source_id = episode_id.replace("episode_", "")
            
            # Use ClaimStore for claim-centric storage
            from ..database.claim_store import ClaimStore
            claim_store = ClaimStore(orchestrator.db_service)
            claim_store.upsert_pipeline_outputs(
                pipeline_outputs,
                source_id=source_id,
                source_type='episode',
                episode_title=Path(file_path).stem,
            )
            logger.info("💾 Stored claims with evidence to claim-centric database")
        except Exception as e:
            logger.error(f"❌ Database storage failed: {e}")
            raise

        # 9. Summaries now stored in episodes table (via ClaimStore)
        if orchestrator.progress_callback:
            orchestrator.progress_callback("generating_summary", 95, episode_id)
        
        # Note: Summary text (short_summary, long_summary) is already stored
        # in the episodes table by ClaimStore.upsert_pipeline_outputs()
        logger.info(f"📋 Episode summaries stored in episodes table")

        # 10. Generate summary markdown file
        summary_file_path = None
        try:
            from ..services.file_generation import FileGenerationService

            output_dir = config.get("output_dir")
            if output_dir:
                file_gen = FileGenerationService(output_dir=Path(output_dir))
            else:
                file_gen = FileGenerationService()

            summary_file_path = file_gen.generate_summary_markdown_from_pipeline(
                video_id, episode_id, pipeline_outputs
            )

            if summary_file_path:
                logger.info(f"✅ Summary file: {summary_file_path}")

        except Exception as e:
            logger.error(f"❌ Summary file generation failed: {e}")

        # 11. Return rich results
        return {
            "status": "succeeded",
            "output_id": episode_id,
            "summary_file": str(summary_file_path) if summary_file_path else None,
            "result": {
                # Claim metrics
                "claims_extracted": len(pipeline_outputs.claims),
                "claims_tier_a": len(
                    [c for c in pipeline_outputs.claims if c.tier == "A"]
                ),
                "claims_tier_b": len(
                    [c for c in pipeline_outputs.claims if c.tier == "B"]
                ),
                "claims_tier_c": len(
                    [c for c in pipeline_outputs.claims if c.tier == "C"]
                ),
                "evidence_spans": sum(len(c.evidence) for c in pipeline_outputs.claims),
                # Entity metrics
                "jargon_extracted": len(pipeline_outputs.jargon),
                "people_extracted": len(pipeline_outputs.people),
                "mental_models_extracted": len(pipeline_outputs.concepts),
                # Rich data metrics
                "relations": len(pipeline_outputs.relations),
                "categories": len(pipeline_outputs.structured_categories),
                # Processing metrics
                "segments_processed": len(segments),
                "parallel_workers": hce_config.max_workers or "auto",
            },
        }

    except Exception as e:
        logger.error(f"❌ Mining failed for {episode_id}: {e}")
        raise
