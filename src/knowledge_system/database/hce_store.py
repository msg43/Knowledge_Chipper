"""
Unified HCE storage for the main application database.

Writes rich HCE pipeline outputs (claims, evidence spans, relations, people,
concepts, jargon, categories, milestones) into the main DB using the unified
schema ensured by DatabaseService._ensure_unified_hce_schema().
"""

from __future__ import annotations

import json
from typing import Any

from ..processors.hce.types import PipelineOutputs
from .service import DatabaseService


class HCEStore:
    """Facade for persisting HCE PipelineOutputs into the main DB."""

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def upsert_pipeline_outputs(
        self,
        outputs: PipelineOutputs,
        *,
        episode_title: str | None = None,
        recorded_at: str | None = None,
        video_id: str | None = None,
    ) -> None:
        """Persist pipeline outputs into the unified HCE schema in main DB.

        This is idempotent via INSERT ... ON CONFLICT DO UPDATE clauses that
        align with composite primary keys in the unified schema.
        """
        # Use the raw DB-API connection to execute the idempotent SQL script
        conn = self.db_service.engine.raw_connection()
        try:
            cur = conn.cursor()
            # Begin transaction
            cur.execute("BEGIN")

            # Episodes
            cur.execute(
                """
                INSERT INTO hce_episodes(episode_id, video_id, title, recorded_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(episode_id) DO UPDATE SET
                    video_id = COALESCE(excluded.video_id, video_id),
                    title = COALESCE(excluded.title, title),
                    recorded_at = COALESCE(excluded.recorded_at, recorded_at)
                """,
                (outputs.episode_id, video_id, episode_title, recorded_at),
            )

            # Clear FTS rows for clean reindexing
            cur.execute(
                "DELETE FROM hce_claims_fts WHERE episode_id = ?", (outputs.episode_id,)
            )
            cur.execute(
                "DELETE FROM hce_quotes_fts WHERE episode_id = ?", (outputs.episode_id,)
            )

            # Milestones
            for m in outputs.milestones:
                cur.execute(
                    """
                    INSERT INTO hce_milestones(episode_id, milestone_id, t0, t1, summary)
                    VALUES(?, ?, ?, ?, ?)
                    ON CONFLICT(episode_id, milestone_id) DO UPDATE SET
                        t0 = excluded.t0,
                        t1 = excluded.t1,
                        summary = excluded.summary
                    """,
                    (outputs.episode_id, m.milestone_id, m.t0, m.t1, m.summary),
                )

            # Claims and evidence spans
            for claim in outputs.claims:
                first_mention_ts = claim.evidence[0].t0 if claim.evidence else None
                cur.execute(
                    """
                    INSERT INTO hce_claims(
                        episode_id, claim_id, canonical, claim_type, tier,
                        first_mention_ts, scores_json,
                        temporality_score, temporality_confidence, temporality_rationale,
                        structured_categories_json, category_relevance_scores_json
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(episode_id, claim_id) DO UPDATE SET
                        canonical = excluded.canonical,
                        claim_type = excluded.claim_type,
                        tier = excluded.tier,
                        first_mention_ts = excluded.first_mention_ts,
                        scores_json = excluded.scores_json,
                        temporality_score = excluded.temporality_score,
                        temporality_confidence = excluded.temporality_confidence,
                        temporality_rationale = excluded.temporality_rationale,
                        structured_categories_json = excluded.structured_categories_json,
                        category_relevance_scores_json = excluded.category_relevance_scores_json
                    """,
                    (
                        outputs.episode_id,
                        claim.claim_id,
                        claim.canonical,
                        claim.claim_type,
                        claim.tier,
                        first_mention_ts,
                        json.dumps(claim.scores),
                        claim.temporality_score,
                        claim.temporality_confidence,
                        claim.temporality_rationale,
                        json.dumps(claim.structured_categories),
                        json.dumps(claim.category_relevance_scores),
                    ),
                )

                # Replace existing evidence spans for this claim
                cur.execute(
                    "DELETE FROM hce_evidence_spans WHERE episode_id = ? AND claim_id = ?",
                    (outputs.episode_id, claim.claim_id),
                )

                for i, ev in enumerate(claim.evidence):
                    cur.execute(
                        """
                    INSERT INTO hce_evidence_spans(
                            episode_id, claim_id, seq, segment_id,
                            t0, t1, quote,
                            context_t0, context_t1, context_text, context_type
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            outputs.episode_id,
                            claim.claim_id,
                            i,
                            ev.segment_id,
                            ev.t0,
                            ev.t1,
                            ev.quote,
                            ev.context_t0,
                            ev.context_t1,
                            ev.context_text,
                            ev.context_type,
                        ),
                    )

                    # Index quotes in FTS
                    cur.execute(
                        "INSERT INTO hce_quotes_fts(episode_id, claim_id, quote) VALUES(?, ?, ?)",
                        (outputs.episode_id, claim.claim_id, ev.quote),
                    )

                # Index claim in FTS
                cur.execute(
                    "INSERT INTO hce_claims_fts(episode_id, claim_id, canonical, claim_type) VALUES(?, ?, ?, ?)",
                    (
                        outputs.episode_id,
                        claim.claim_id,
                        claim.canonical,
                        claim.claim_type,
                    ),
                )

            # Relations
            for rel in outputs.relations:
                cur.execute(
                    """
                    INSERT INTO hce_relations(episode_id, source_claim_id, target_claim_id, type, strength, rationale)
                    VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(episode_id, source_claim_id, target_claim_id, type) DO UPDATE SET
                        strength = excluded.strength,
                        rationale = excluded.rationale
                    """,
                    (
                        outputs.episode_id,
                        rel.source_claim_id,
                        rel.target_claim_id,
                        rel.type,
                        rel.strength,
                        rel.rationale,
                    ),
                )

            # People (map mention_id -> person_id for now)
            for p in outputs.people:
                context_quote = p.normalized or p.surface
                person_id = p.mention_id  # until person clustering exists
                cur.execute(
                    """
                    INSERT INTO hce_people(
                        episode_id, person_id, mention_id, span_segment_id, t0, t1,
                        name, surface, normalized, description, entity_type, external_ids_json,
                        confidence, first_mention_ts, context_quote
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(episode_id, person_id) DO UPDATE SET
                        mention_id = excluded.mention_id,
                        span_segment_id = excluded.span_segment_id,
                        t0 = excluded.t0,
                        t1 = excluded.t1,
                        name = excluded.name,
                        surface = excluded.surface,
                        normalized = excluded.normalized,
                        description = excluded.description,
                        entity_type = excluded.entity_type,
                        external_ids_json = excluded.external_ids_json,
                        confidence = excluded.confidence,
                        first_mention_ts = excluded.first_mention_ts,
                        context_quote = excluded.context_quote
                    """,
                    (
                        outputs.episode_id,
                        person_id,
                        p.mention_id,
                        p.span_segment_id,
                        p.t0,
                        p.t1,
                        p.normalized or p.surface,
                        p.surface,
                        p.normalized,
                        None,
                        p.entity_type,
                        json.dumps(p.external_ids or {}),
                        p.confidence,
                        p.t0,
                        context_quote,
                    ),
                )

            # Concepts (map model_id -> concept_id)
            for c in outputs.concepts:
                evidence_json = json.dumps([e.model_dump() for e in c.evidence_spans])
                context_quote = c.evidence_spans[0].quote if c.evidence_spans else None
                concept_id = c.model_id
                cur.execute(
                    """
                    INSERT INTO hce_concepts(
                        episode_id, concept_id, model_id, name, description, definition,
                        first_mention_ts, aliases_json, evidence_json, context_quote
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(episode_id, concept_id) DO UPDATE SET
                        model_id = excluded.model_id,
                        name = excluded.name,
                        description = excluded.description,
                        definition = excluded.definition,
                        first_mention_ts = excluded.first_mention_ts,
                        aliases_json = excluded.aliases_json,
                        evidence_json = excluded.evidence_json,
                        context_quote = excluded.context_quote
                    """,
                    (
                        outputs.episode_id,
                        concept_id,
                        c.model_id,
                        c.name,
                        None,
                        c.definition,
                        c.first_mention_ts,
                        json.dumps(c.aliases or []),
                        evidence_json,
                        context_quote,
                    ),
                )

            # Jargon
            for j in outputs.jargon:
                evidence_json = json.dumps([e.model_dump() for e in j.evidence_spans])
                context_quote = j.evidence_spans[0].quote if j.evidence_spans else None
                cur.execute(
                    """
                    INSERT INTO hce_jargon(
                        episode_id, term_id, term, definition, category, first_mention_ts, evidence_json, context_quote
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(episode_id, term_id) DO UPDATE SET
                        term = excluded.term,
                        definition = excluded.definition,
                        category = excluded.category,
                        first_mention_ts = excluded.first_mention_ts,
                        evidence_json = excluded.evidence_json,
                        context_quote = excluded.context_quote
                    """,
                    (
                        outputs.episode_id,
                        j.term_id,
                        j.term,
                        j.definition,
                        j.category,
                        j.evidence_spans[0].t0 if j.evidence_spans else None,
                        evidence_json,
                        context_quote,
                    ),
                )

            # Structured categories
            for cat in outputs.structured_categories:
                cur.execute(
                    """
                    INSERT INTO hce_structured_categories(
                        episode_id, category_id, category_name, wikidata_qid,
                        coverage_confidence, supporting_evidence_json, frequency_score
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(episode_id, category_id) DO UPDATE SET
                        category_name = excluded.category_name,
                        wikidata_qid = excluded.wikidata_qid,
                        coverage_confidence = excluded.coverage_confidence,
                        supporting_evidence_json = excluded.supporting_evidence_json,
                        frequency_score = excluded.frequency_score
                    """,
                    (
                        outputs.episode_id,
                        cat.category_id,
                        cat.category_name,
                        cat.wikidata_qid,
                        cat.coverage_confidence,
                        json.dumps(cat.supporting_evidence),
                        cat.frequency_score,
                    ),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
