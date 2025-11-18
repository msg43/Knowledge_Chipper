"""
HCE Integration Module for Question Mapper

This module provides a hook for integrating Question Mapper into the HCE pipeline.
It can be called after claims are stored to automatically discover and assign questions.
"""

import logging
from typing import Any

from ...core.llm_adapter import LLMAdapter
from ...database.service import DatabaseService
from .orchestrator import QuestionMapperOrchestrator

logger = logging.getLogger(__name__)


def process_source_questions(
    source_id: str,
    llm_adapter: LLMAdapter | None = None,
    db_service: DatabaseService | None = None,
    auto_approve: bool = False,
    batch_size: int = 50,
    min_discovery_confidence: float = 0.6,
    min_merge_confidence: float = 0.7,
    min_relevance: float = 0.5,
) -> dict[str, Any]:
    """
    Process questions for a specific source after HCE claim extraction.

    This function should be called after HCE pipeline completes and claims
    are stored in the database. It will:
    1. Load claims for the source
    2. Discover questions from those claims
    3. Merge with existing questions
    4. Assign claims to questions
    5. Store results in database

    Args:
        source_id: Source ID to process questions for
        llm_adapter: Optional LLM adapter (creates default if None)
        db_service: Optional database service (creates default if None)
        auto_approve: If True, automatically approve questions without review
        batch_size: Claims per LLM call
        min_discovery_confidence: Minimum confidence for discovered questions
        min_merge_confidence: Minimum confidence for merge recommendations
        min_relevance: Minimum relevance for claim-question assignments

    Returns:
        Dict with results summary:
        {
            "success": bool,
            "source_id": str,
            "questions_discovered": int,
            "questions_finalized": int,
            "claims_assigned": int,
            "processing_time": float,
            "error": str (if success=False)
        }
    """
    try:
        # Initialize services if not provided
        if db_service is None:
            db_service = DatabaseService()

        if llm_adapter is None:
            # Create default LLM adapter (uses config from settings)
            from ...config import get_settings

            settings = get_settings()
            llm_provider = settings.llm.provider
            llm_model = settings.llm.model

            llm_adapter = LLMAdapter(provider=llm_provider, model=llm_model)

        # Load claims for source
        logger.info(f"Loading claims for source {source_id}")

        with db_service.get_session() as session:
            from ...database.models import Claim

            claims_query = session.query(Claim).filter_by(source_id=source_id)
            claims_orm = claims_query.all()

            if not claims_orm:
                logger.warning(f"No claims found for source {source_id}")
                return {
                    "success": True,
                    "source_id": source_id,
                    "questions_discovered": 0,
                    "questions_finalized": 0,
                    "claims_assigned": 0,
                    "processing_time": 0.0,
                    "message": "No claims to process",
                }

            # Convert to dict format for question mapper
            claims = [
                {
                    "claim_id": c.claim_id,
                    "claim_text": c.claim_text or c.canonical,
                    "source_id": c.source_id,
                }
                for c in claims_orm
            ]

        logger.info(f"Loaded {len(claims)} claims for question mapping")

        # Create orchestrator and process
        orchestrator = QuestionMapperOrchestrator(llm_adapter, db_service)

        result = orchestrator.process_claims(
            claims=claims,
            batch_size=batch_size,
            min_discovery_confidence=min_discovery_confidence,
            min_merge_confidence=min_merge_confidence,
            min_relevance=min_relevance,
            auto_approve=auto_approve,
        )

        # Return summary
        return {
            "success": True,
            "source_id": source_id,
            "questions_discovered": len(result.discovered_questions),
            "questions_finalized": len(
                set(m.question_id for m in result.claim_mappings)
            ),
            "claims_assigned": len(result.claim_mappings),
            "processing_time": result.processing_time_seconds,
            "llm_calls": result.llm_calls_made,
        }

    except Exception as e:
        logger.error(f"Question mapping failed for source {source_id}: {e}")
        return {
            "success": False,
            "source_id": source_id,
            "questions_discovered": 0,
            "questions_finalized": 0,
            "claims_assigned": 0,
            "processing_time": 0.0,
            "error": str(e),
        }


def process_all_unmapped_sources(
    llm_adapter: LLMAdapter | None = None,
    db_service: DatabaseService | None = None,
    auto_approve: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Process questions for all sources that have claims but no questions assigned.

    This is useful for batch processing existing data or catching up after
    enabling the question mapping feature.

    Args:
        llm_adapter: Optional LLM adapter
        db_service: Optional database service
        auto_approve: If True, automatically approve questions
        limit: Optional limit on number of sources to process

    Returns:
        List of result dicts (one per source)
    """
    if db_service is None:
        db_service = DatabaseService()

    try:
        # Find sources with claims but no questions
        with db_service.get_session() as session:
            from sqlalchemy import distinct, func

            from ...database.models import Claim, Question, QuestionClaim

            # Get all source_ids that have claims
            sources_with_claims = (
                session.query(distinct(Claim.source_id)).order_by(Claim.source_id).all()
            )

            # Get source_ids that already have questions assigned
            sources_with_questions = (
                session.query(distinct(Claim.source_id))
                .join(QuestionClaim, Claim.claim_id == QuestionClaim.claim_id)
                .all()
            )

            # Find unmapped sources
            all_source_ids = {s[0] for s in sources_with_claims}
            mapped_source_ids = {s[0] for s in sources_with_questions}
            unmapped_source_ids = list(all_source_ids - mapped_source_ids)

        logger.info(
            f"Found {len(unmapped_source_ids)} sources without question mappings"
        )

        if limit:
            unmapped_source_ids = unmapped_source_ids[:limit]
            logger.info(f"Processing first {limit} sources")

        # Process each source
        results = []
        for i, source_id in enumerate(unmapped_source_ids, 1):
            logger.info(
                f"Processing source {i}/{len(unmapped_source_ids)}: {source_id}"
            )

            result = process_source_questions(
                source_id=source_id,
                llm_adapter=llm_adapter,
                db_service=db_service,
                auto_approve=auto_approve,
            )

            results.append(result)

        return results

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        return [
            {
                "success": False,
                "error": str(e),
            }
        ]


# Integration hook that can be called from HCE orchestrator
def post_hce_hook(
    source_id: str,
    enable_question_mapping: bool = True,
    auto_approve: bool = False,
    **kwargs,
) -> dict[str, Any] | None:
    """
    Post-HCE processing hook for question mapping.

    This function is designed to be called by the HCE orchestrator after
    claims are stored to the database.

    Args:
        source_id: Source ID that was just processed
        enable_question_mapping: Whether to run question mapping
        auto_approve: Whether to auto-approve discovered questions
        **kwargs: Additional arguments (ignored for forward compatibility)

    Returns:
        Result dict if question mapping ran, None if disabled
    """
    if not enable_question_mapping:
        logger.debug("Question mapping disabled, skipping")
        return None

    logger.info(f"Running post-HCE question mapping for {source_id}")

    return process_source_questions(
        source_id=source_id, auto_approve=auto_approve
    )
