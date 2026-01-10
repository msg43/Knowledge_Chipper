"""Two-Pass integration for System2Orchestrator."""

import logging
from pathlib import Path
from typing import Any

from ..errors import ErrorCode, KnowledgeSystemError

logger = logging.getLogger(__name__)


async def process_with_two_pass_pipeline(
    orchestrator,  # System2Orchestrator instance
    source_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """
    Process source using TwoPassPipeline.
    
    Benefits over old two-step approach:
    - Whole-document processing (no segmentation)
    - Only 2 API calls per source
    - Preserves complete argument structures
    - Absolute importance scoring (globally comparable)
    - Speaker inference without diarization
    - World-class narrative synthesis
    
    Checkpoint structure:
    {
        "stage": "loading" | "extraction" | "synthesis" | "storing" | "completed",
        "extraction_result": {...},  # Partial results if interrupted
        "synthesis_result": {...},
        "final_result": {...}
    }
    """
    from ..gui.queue_event_bus import QueueEventBus
    from ..processors.two_pass import TwoPassPipeline
    from ..core.llm_adapter import LLMAdapter
    
    event_bus = QueueEventBus()
    
    # Update stage status
    orchestrator.db_service.upsert_stage_status(
        source_id=source_id,
        stage="two_pass_processing",
        status="in_progress",
        metadata={"job_run_id": run_id},
    )
    event_bus.emit_stage_update(source_id, "two_pass_processing", "in_progress")
    
    try:
        # Check if already completed
        if checkpoint and checkpoint.get("stage") == "completed":
            logger.info(f"Two-pass processing already completed (from checkpoint)")
            return checkpoint.get(
                "final_result", {"status": "succeeded", "output_id": source_id}
            )
        
        # Save initial checkpoint
        orchestrator.save_checkpoint(run_id, {"stage": "loading"})
        
        # 1. Load transcript
        logger.info(f"Loading transcript for source {source_id}")
        
        # Get transcript from database
        with orchestrator.db_service.get_session() as session:
            from ..database.models import Transcript
            transcript_record = (
                session.query(Transcript)
                .filter(Transcript.source_id == source_id)
                .first()
            )
            
            if not transcript_record:
                raise KnowledgeSystemError(
                    f"No transcript found for source {source_id}",
                    ErrorCode.TRANSCRIPT_NOT_FOUND,
                )
            
            transcript_text = transcript_record.transcript_text
            
            # Get source metadata
            from ..database.models import MediaSource
            source = session.query(MediaSource).filter(
                MediaSource.source_id == source_id
            ).first()
            
            if not source:
                raise KnowledgeSystemError(
                    f"No media source found for {source_id}",
                    ErrorCode.SOURCE_NOT_FOUND,
                )
            
            metadata = {
                "title": source.title or "Unknown Title",
                "channel": source.channel or source.uploader or "Unknown Channel",
                "description": source.description or "",
                "duration": source.duration or 0,
                "upload_date": source.upload_date.isoformat() if source.upload_date else None,
                "tags": source.tags or [],
                "chapters": [],  # TODO: Load chapters if available
            }
            
            # Try to get YouTube AI summary if available
            youtube_ai_summary = source.youtube_ai_summary
        
        logger.info(f"Loaded transcript: {len(transcript_text)} characters")
        
        # Save checkpoint
        orchestrator.save_checkpoint(run_id, {"stage": "extraction"})
        
        # 2. Initialize LLM adapter - use settings if no model specified in config
        from ..config import get_settings
        settings = get_settings()
        
        model_config = config.get("model")
        if model_config:
            # Config explicitly specifies model
            if ":" in model_config:
                provider, model = model_config.split(":", 1)
            else:
                # No provider specified, use settings provider
                provider = settings.llm.provider
                model = model_config
        else:
            # No model in config, use settings
            provider = settings.llm.provider
            if provider == "local":
                model = settings.llm.local_model
            else:
                model = settings.llm.model
        
        logger.info(f"Using LLM from settings: {provider}/{model}")
        
        llm = LLMAdapter(
            provider=provider,
            model=model,
            temperature=config.get("temperature", 0.3),
        )
        
        # 3. Initialize two-pass pipeline
        importance_threshold = config.get("importance_threshold", 7.0)
        pipeline = TwoPassPipeline(
            llm_adapter=llm,
            importance_threshold=importance_threshold,
        )
        
        # 4. Run two-pass processing
        logger.info("Starting two-pass processing...")
        
        result = pipeline.process(
            source_id=source_id,
            transcript=transcript_text,
            metadata=metadata,
            youtube_ai_summary=youtube_ai_summary,
        )
        
        logger.info(
            f"Two-pass processing complete: "
            f"{result.total_claims} claims extracted, "
            f"{len(result.high_importance_claims)} high-importance"
        )
        
        # Save checkpoint with results
        orchestrator.save_checkpoint(run_id, {
            "stage": "storing",
            "extraction_result": {
                "total_claims": result.total_claims,
                "high_importance_count": len(result.high_importance_claims),
            },
            "synthesis_result": {
                "summary_length": len(result.long_summary),
                "theme_count": len(result.synthesis.key_themes),
            },
        })
        
        # 5. Store results to database
        logger.info("Storing results to database...")
        
        summary_id = _store_two_pass_results(
            orchestrator=orchestrator,
            source_id=source_id,
            result=result,
            config=config,
        )
        
        logger.info(f"Results stored with summary_id: {summary_id}")
        
        # 6. Generate markdown file (optional)
        output_dir = config.get("output_directory")
        if output_dir:
            _generate_markdown_file(
                source_id=source_id,
                result=result,
                output_dir=Path(output_dir),
            )
        
        # Update stage status to completed
        orchestrator.db_service.upsert_stage_status(
            source_id=source_id,
            stage="two_pass_processing",
            status="completed",
            metadata={
                "job_run_id": run_id,
                "summary_id": summary_id,
                "total_claims": result.total_claims,
                "high_importance_claims": len(result.high_importance_claims),
            },
        )
        event_bus.emit_stage_update(source_id, "two_pass_processing", "completed")
        
        # Build final result
        final_result = {
            "status": "succeeded",
            "output_id": summary_id,
            "source_id": source_id,
            "result": {
                "total_claims": result.total_claims,
                "high_importance_claims": len(result.high_importance_claims),
                "flagged_claims": len(result.flagged_claims),
                "jargon_terms": len(result.extraction.jargon),
                "people_mentioned": len(result.extraction.people),
                "mental_models": len(result.extraction.mental_models),
                "summary_length": len(result.long_summary),
                "key_themes": result.synthesis.key_themes,
                "processing_time_seconds": result.processing_time_seconds,
            },
        }
        
        # Save completion checkpoint
        orchestrator.save_checkpoint(run_id, {
            "stage": "completed",
            "final_result": final_result,
        })
        
        return final_result
    
    except Exception as e:
        logger.error(f"Two-pass processing failed: {e}", exc_info=True)
        
        # Update stage status to failed
        orchestrator.db_service.upsert_stage_status(
            source_id=source_id,
            stage="two_pass_processing",
            status="failed",
            metadata={"job_run_id": run_id, "error": str(e)},
        )
        event_bus.emit_stage_update(source_id, "two_pass_processing", "failed")
        
        raise


def _store_two_pass_results(
    orchestrator,
    source_id: str,
    result,  # TwoPassResult
    config: dict[str, Any],
) -> str:
    """Store two-pass results to database."""
    import uuid
    from datetime import datetime
    from ..database.models import Summary, Claim, Jargon, Person, Concept
    
    # Generate summary ID
    summary_id = f"summary_{uuid.uuid4().hex[:12]}"
    
    # Create Summary record
    with orchestrator.db_service.get_session() as session:
        # Prepare HCE data JSON
        hce_data_json = {
            "claims": [
                {
                    "claim_text": c.get("claim_text", ""),
                    "speaker": c.get("speaker", "Unknown"),
                    "speaker_confidence": c.get("speaker_confidence", 0),
                    "speaker_rationale": c.get("speaker_rationale", ""),
                    "flag_for_review": c.get("flag_for_review", False),
                    "timestamp": c.get("timestamp", "00:00"),
                    "evidence_quote": c.get("evidence_quote", ""),
                    "claim_type": c.get("claim_type", "factual"),
                    "dimensions": c.get("dimensions", {}),
                    "importance": c.get("importance", 0),
                }
                for c in result.extraction.claims
            ],
            "jargon": [
                {
                    "term": j.get("term", ""),
                    "definition": j.get("definition", ""),
                    "domain": j.get("domain", ""),
                    "first_mention_ts": j.get("first_mention_ts", "00:00"),
                }
                for j in result.extraction.jargon
            ],
            "people": [
                {
                    "name": p.get("name", ""),
                    "role": p.get("role", ""),
                    "context": p.get("context", ""),
                    "first_mention_ts": p.get("first_mention_ts", "00:00"),
                }
                for p in result.extraction.people
            ],
            "mental_models": [
                {
                    "name": m.get("name", ""),
                    "description": m.get("description", ""),
                    "implications": m.get("implications", ""),
                    "first_mention_ts": m.get("first_mention_ts", "00:00"),
                }
                for m in result.extraction.mental_models
            ],
        }
        
        # Get LLM info from config - use settings if not specified
        from ..config import get_settings
        settings = get_settings()
        
        model_config = config.get("model")
        if model_config:
            if ":" in model_config:
                provider, model = model_config.split(":", 1)
            else:
                provider = settings.llm.provider
                model = model_config
        else:
            # Use settings
            provider = settings.llm.provider
            if provider == "local":
                model = settings.llm.local_model
            else:
                model = settings.llm.model
        
        summary = Summary(
            summary_id=summary_id,
            source_id=source_id,
            transcript_id=None,
            summary_text=result.long_summary,
            summary_metadata_json={
                "source_id": source_id,
                "processing_timestamp": datetime.now().isoformat(),
                "architecture": "two-pass",
                "key_themes": result.synthesis.key_themes,
                "synthesis_quality": result.synthesis.synthesis_quality,
                "extraction_metadata": result.extraction.metadata,
            },
            processing_type="two_pass",
            hce_data_json=hce_data_json,
            llm_provider=provider,
            llm_model=model,
            prompt_template_path=None,
            focus_area=config.get("source", "manual_summarization"),
            prompt_tokens=0,  # TODO: Track if available
            completion_tokens=0,
            total_tokens=0,
            processing_cost=0.0,
        )
        
        session.add(summary)
        session.commit()
        
        logger.info(f"Created Summary record: {summary_id}")
    
    # Store claims to claims table
    _store_claims_to_database(orchestrator, source_id, result.extraction.claims)
    
    return summary_id


def _store_claims_to_database(orchestrator, source_id: str, claims: list[dict]):
    """Store claims to claims table."""
    from ..database.models import Claim
    import uuid
    
    with orchestrator.db_service.get_session() as session:
        for claim_data in claims:
            claim_id = f"claim_{uuid.uuid4().hex[:12]}"
            
            claim = Claim(
                claim_id=claim_id,
                source_id=source_id,
                canonical=claim_data.get("claim_text", ""),
                evidence_quote=claim_data.get("evidence_quote", ""),
                first_mention_ts=claim_data.get("timestamp", "00:00"),
                importance_score=claim_data.get("importance", 0),
                scores_json=claim_data.get("dimensions", {}),
                speaker_attribution_confidence=claim_data.get("speaker_confidence", 0),
                speaker_rationale=claim_data.get("speaker_rationale", ""),
                flagged_for_review=claim_data.get("flag_for_review", False),
                claim_type=claim_data.get("claim_type", "factual"),
            )
            
            session.add(claim)
        
        session.commit()
        logger.info(f"Stored {len(claims)} claims to database")


def _generate_markdown_file(source_id: str, result, output_dir: Path):
    """Generate markdown file with results."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    filename = f"{source_id}_two_pass_summary.md"
    filepath = output_dir / filename
    
    # Build markdown content
    content = f"""# Two-Pass Analysis: {result.metadata.get('title', 'Unknown Title')}

**Channel:** {result.metadata.get('channel', 'Unknown')}  
**Source ID:** {source_id}  
**Processing Time:** {result.processing_time_seconds:.1f}s

---

## Long Summary

{result.long_summary}

---

## Key Themes

{chr(10).join(f'- {theme}' for theme in result.synthesis.key_themes)}

---

## Extraction Statistics

- **Total Claims:** {result.total_claims}
- **High-Importance Claims (≥7.0):** {len(result.high_importance_claims)}
- **Flagged for Review:** {len(result.flagged_claims)}
- **Jargon Terms:** {len(result.extraction.jargon)}
- **People Mentioned:** {len(result.extraction.people)}
- **Mental Models:** {len(result.extraction.mental_models)}
- **Average Importance:** {result.extraction.avg_importance:.2f}

---

## High-Importance Claims

"""
    
    for i, claim in enumerate(result.high_importance_claims, 1):
        content += f"""
### Claim {i} (Importance: {claim.get('importance', 0):.1f})

**Speaker:** {claim.get('speaker', 'Unknown')} (Confidence: {claim.get('speaker_confidence', 0)}/10)  
**Timestamp:** {claim.get('timestamp', '00:00')}  
**Type:** {claim.get('claim_type', 'factual')}

{claim.get('claim_text', '')}

**Evidence:** {claim.get('evidence_quote', '')[:200]}...

**Dimensions:**
- Epistemic: {claim.get('dimensions', {}).get('epistemic', 0)}/10
- Actionability: {claim.get('dimensions', {}).get('actionability', 0)}/10
- Novelty: {claim.get('dimensions', {}).get('novelty', 0)}/10
- Verifiability: {claim.get('dimensions', {}).get('verifiability', 0)}/10
- Understandability: {claim.get('dimensions', {}).get('understandability', 0)}/10
- Temporal Stability: {claim.get('dimensions', {}).get('temporal_stability', 0)}/10

"""
    
    # Write to file
    filepath.write_text(content)
    logger.info(f"Generated markdown file: {filepath}")

