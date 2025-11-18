"""
Question Mapper Orchestrator - Main pipeline coordinator.

This module orchestrates the complete question mapping workflow:
1. Discover questions from new claims
2. Merge/deduplicate against existing questions
3. Assign claims to finalized questions
4. Store results in database

Usage:
    mapper = QuestionMapperOrchestrator(llm_adapter, db_service)
    result = mapper.process_claims(claims, batch_size=50)
"""

import logging
import time
from typing import Any

from ...core.llm_adapter import LLMAdapter
from ...database.service import DatabaseService
from .assignment import ClaimAssignment
from .discovery import QuestionDiscovery
from .merger import QuestionMerger
from .models import (
    MergeAction,
    QuestionMapperResult,
)

logger = logging.getLogger(__name__)


class QuestionMapperOrchestrator:
    """Orchestrates the complete question mapping pipeline."""

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        db_service: DatabaseService,
    ):
        """Initialize with dependencies.

        Args:
            llm_adapter: Configured LLM adapter for processors
            db_service: Database service for reading/writing questions
        """
        self.llm = llm_adapter
        self.db = db_service

        # Initialize processors
        self.discovery = QuestionDiscovery(llm_adapter)
        self.merger = QuestionMerger(llm_adapter)
        self.assignment = ClaimAssignment(llm_adapter)

    def process_claims(
        self,
        claims: list[dict[str, Any]],
        batch_size: int = 50,
        min_discovery_confidence: float = 0.6,
        min_merge_confidence: float = 0.7,
        min_relevance: float = 0.5,
        auto_approve: bool = False,
    ) -> QuestionMapperResult:
        """Process a batch of claims through the complete pipeline.

        Args:
            claims: List of claim dicts with 'claim_id' and 'claim_text'
            batch_size: Claims per LLM call (default: 50)
            min_discovery_confidence: Threshold for discovered questions
            min_merge_confidence: Threshold for merge recommendations
            min_relevance: Threshold for claim-question assignments
            auto_approve: If True, automatically create questions without review

        Returns:
            QuestionMapperResult with all discovered questions, recommendations,
            and mappings, plus processing metrics
        """
        start_time = time.time()
        total_llm_calls = 0
        result = QuestionMapperResult()

        logger.info(f"Processing {len(claims)} claims through question mapper")

        try:
            # STAGE 1: DISCOVERY
            logger.info("Stage 1: Discovering questions from claims")
            discovered_questions = self.discovery.discover_questions_batched(
                claims=claims,
                batch_size=batch_size,
                min_confidence=min_discovery_confidence,
            )
            result.discovered_questions = discovered_questions
            total_llm_calls += (len(claims) // batch_size) + 1

            if not discovered_questions:
                logger.info("No questions discovered - pipeline complete")
                result.processing_time_seconds = time.time() - start_time
                result.llm_calls_made = total_llm_calls
                return result

            logger.info(f"Discovered {len(discovered_questions)} questions")

            # STAGE 2: MERGING
            logger.info("Stage 2: Analyzing merges with existing questions")

            # Get existing questions from database
            # We'll get all domains mentioned in discovered questions
            domains = {q.domain for q in discovered_questions if q.domain}
            existing_questions = []

            for domain in domains:
                domain_questions = self.db.get_questions_by_domain(
                    domain, status_filter=["open", "answered", "contested"]
                )
                existing_questions.extend(domain_questions)

            logger.info(
                f"Loaded {len(existing_questions)} existing questions for comparison"
            )

            # Convert discovered questions to dicts for merger
            new_q_dicts = [
                {
                    "question_text": q.question_text,
                    "question_type": q.question_type.value,
                    "domain": q.domain,
                    "claim_ids": q.claim_ids,
                }
                for q in discovered_questions
            ]

            merge_recs = self.merger.analyze_merges(
                new_questions=new_q_dicts,
                existing_questions=existing_questions,
                min_confidence=min_merge_confidence,
            )
            result.merge_recommendations = merge_recs
            total_llm_calls += 1

            logger.info(f"Generated {len(merge_recs)} merge recommendations")

            # STAGE 3: QUESTION FINALIZATION
            # Create mapping of new question text -> final question ID
            finalized_questions = self._finalize_questions(
                discovered_questions, merge_recs, auto_approve
            )

            if not finalized_questions:
                logger.info("No questions finalized - skipping assignment")
                result.processing_time_seconds = time.time() - start_time
                result.llm_calls_made = total_llm_calls
                return result

            logger.info(f"Finalized {len(finalized_questions)} questions")

            # STAGE 4: CLAIM ASSIGNMENT
            logger.info("Stage 4: Assigning claims to finalized questions")

            # Convert finalized questions to format for assignment
            question_dicts = [
                {"question_id": qid, "question_text": qtext}
                for qtext, qid in finalized_questions.items()
            ]

            mappings = self.assignment.assign_claims_batched(
                claims=claims,
                questions=question_dicts,
                claims_per_batch=batch_size,
                min_relevance=min_relevance,
            )
            result.claim_mappings = mappings
            total_llm_calls += (len(claims) // batch_size) + 1

            logger.info(f"Created {len(mappings)} claim-question mappings")

            # STAGE 5: DATABASE STORAGE
            logger.info("Stage 5: Storing assignments in database")
            stored_count = 0

            for mapping in mappings:
                success = self.db.assign_claim_to_question(
                    claim_id=mapping.claim_id,
                    question_id=mapping.question_id,
                    relation_type=mapping.relation_type.value,
                    relevance_score=mapping.relevance_score,
                    rationale=mapping.rationale,
                )
                if success:
                    stored_count += 1

            logger.info(f"Stored {stored_count} assignments to database")

            # Finalize result
            result.processing_time_seconds = time.time() - start_time
            result.llm_calls_made = total_llm_calls

            logger.info(
                f"Question mapping complete in {result.processing_time_seconds:.2f}s "
                f"({total_llm_calls} LLM calls)"
            )

            return result

        except Exception as e:
            logger.error(f"Question mapping pipeline failed: {e}", exc_info=True)
            result.processing_time_seconds = time.time() - start_time
            result.llm_calls_made = total_llm_calls
            return result

    def _finalize_questions(
        self,
        discovered_questions,
        merge_recommendations,
        auto_approve: bool,
    ) -> dict[str, str]:
        """Finalize questions based on merge recommendations.

        Args:
            discovered_questions: List of DiscoveredQuestion objects
            merge_recommendations: List of MergeRecommendation objects
            auto_approve: If True, create questions automatically

        Returns:
            Dict mapping question_text -> question_id for finalized questions
        """
        finalized = {}  # question_text -> question_id

        # Create mapping of new question text -> recommendation
        rec_map = {rec.new_question_text: rec for rec in merge_recommendations}

        for q in discovered_questions:
            rec = rec_map.get(q.question_text)

            if not rec:
                # No recommendation (shouldn't happen, but handle it)
                if auto_approve:
                    qid = self._create_question_in_db(q)
                    if qid:
                        finalized[q.question_text] = qid
                continue

            if rec.action == MergeAction.KEEP_DISTINCT:
                # Create new question
                if auto_approve:
                    qid = self._create_question_in_db(q)
                    if qid:
                        finalized[q.question_text] = qid
                else:
                    # Mark as pending review
                    qid = self._create_question_in_db(q, reviewed=False)
                    if qid:
                        finalized[q.question_text] = qid

            elif rec.action == MergeAction.MERGE_INTO_EXISTING:
                # Use existing question
                if rec.target_question_id:
                    finalized[q.question_text] = rec.target_question_id
                    logger.debug(
                        f"Merged '{q.question_text}' into existing {rec.target_question_id}"
                    )

            elif rec.action == MergeAction.MERGE_EXISTING_INTO_NEW:
                # Create new question and merge existing into it
                if auto_approve and rec.target_question_id:
                    new_qid = self._create_question_in_db(q)
                    if new_qid:
                        # Merge existing into new
                        self.db.merge_questions(rec.target_question_id, new_qid)
                        finalized[q.question_text] = new_qid
                        logger.info(
                            f"Created new question {new_qid} and merged "
                            f"{rec.target_question_id} into it"
                        )
                else:
                    # Create as pending review
                    qid = self._create_question_in_db(q, reviewed=False)
                    if qid:
                        finalized[q.question_text] = qid

            elif rec.action == MergeAction.LINK_AS_RELATED:
                # Create new question (will be linked via question_relations later)
                if auto_approve:
                    qid = self._create_question_in_db(q)
                    if qid:
                        finalized[q.question_text] = qid
                        # TODO: Create question_relations entry
                else:
                    qid = self._create_question_in_db(q, reviewed=False)
                    if qid:
                        finalized[q.question_text] = qid

        return finalized

    def _create_question_in_db(self, question, reviewed: bool = True) -> str | None:
        """Create a question in the database.

        Args:
            question: DiscoveredQuestion object
            reviewed: Whether to mark as reviewed

        Returns:
            Question ID if successful, None otherwise
        """
        try:
            qid = self.db.create_question(
                question_text=question.question_text,
                question_type=question.question_type.value,
                domain=question.domain,
                importance_score=question.confidence,  # Use discovery confidence as importance
                reviewed=reviewed,
                notes=question.rationale,
            )
            return qid
        except ValueError as e:
            # Question already exists
            logger.debug(f"Question already exists: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to create question in DB: {e}")
            return None
