"""
SQLite storage module for HCE pipeline outputs.

Provides idempotent upsert operations for persisting claims, relations,
and entity extractions with full-text search support.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .types import PipelineOutputs


def open_db(path: str | Path) -> sqlite3.Connection:
    """Open SQLite database with optimized settings."""
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    # Enable query optimization
    conn.execute("PRAGMA optimize;")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create database schema from SQL file."""
    schema_path = Path(__file__).parent / "sqlite_schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    conn.executescript(schema_path.read_text())
    conn.commit()


def upsert_pipeline_outputs(
    conn: sqlite3.Connection,
    out: PipelineOutputs,
    episode_title: str | None = None,
    recorded_at: str | None = None,
    video_id: str | None = None,
) -> None:
    """
    Persist pipeline outputs to SQLite with idempotent upserts.

    Args:
        conn: SQLite connection
        out: Pipeline outputs to persist
        episode_title: Optional episode title
        recorded_at: Optional recording timestamp (ISO8601)
        video_id: Optional reference to existing video_id in videos table
    """
    cur = conn.cursor()

    try:
        # Begin transaction
        cur.execute("BEGIN")

        # Upsert episode
        cur.execute(
            """
            INSERT INTO episodes(episode_id, video_id, title, recorded_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(episode_id) DO UPDATE SET
                video_id = COALESCE(excluded.video_id, video_id),
                title = COALESCE(excluded.title, title),
                recorded_at = COALESCE(excluded.recorded_at, recorded_at)
        """,
            (out.episode_id, video_id, episode_title, recorded_at),
        )

        # Clear existing FTS entries for this episode (for clean reindex)
        cur.execute("DELETE FROM claims_fts WHERE episode_id = ?", (out.episode_id,))
        cur.execute("DELETE FROM quotes_fts WHERE episode_id = ?", (out.episode_id,))

        # Upsert milestones
        for milestone in out.milestones:
            cur.execute(
                """
                INSERT INTO milestones(episode_id, milestone_id, t0, t1, summary)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(episode_id, milestone_id) DO UPDATE SET
                    t0 = excluded.t0,
                    t1 = excluded.t1,
                    summary = excluded.summary
            """,
                (
                    out.episode_id,
                    milestone.milestone_id,
                    milestone.t0,
                    milestone.t1,
                    milestone.summary,
                ),
            )

        # Upsert claims
        for claim in out.claims:
            # Get first mention timestamp from evidence
            first_mention_ts = claim.evidence[0].t0 if claim.evidence else None

            cur.execute(
                """
                INSERT INTO claims(episode_id, claim_id, canonical, claim_type, tier, first_mention_ts, scores_json, temporality_score, temporality_confidence, temporality_rationale, structured_categories_json, category_relevance_scores_json)
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
                    out.episode_id,
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

            # Delete existing evidence spans for clean update
            cur.execute(
                """
                DELETE FROM evidence_spans
                WHERE episode_id = ? AND claim_id = ?
            """,
                (out.episode_id, claim.claim_id),
            )

            # Insert evidence spans with dual-level context
            for i, evidence in enumerate(claim.evidence):
                cur.execute(
                    """
                    INSERT INTO evidence_spans(episode_id, claim_id, seq, segment_id, t0, t1, quote, context_t0, context_t1, context_text, context_type)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        out.episode_id,
                        claim.claim_id,
                        i,
                        evidence.segment_id,
                        evidence.t0,
                        evidence.t1,
                        evidence.quote,
                        evidence.context_t0,
                        evidence.context_t1,
                        evidence.context_text,
                        evidence.context_type,
                    ),
                )

                # Index quote in FTS
                cur.execute(
                    """
                    INSERT INTO quotes_fts(episode_id, claim_id, quote)
                    VALUES(?, ?, ?)
                """,
                    (out.episode_id, claim.claim_id, evidence.quote),
                )

            # Index claim in FTS
            cur.execute(
                """
                INSERT INTO claims_fts(episode_id, claim_id, canonical, claim_type)
                VALUES(?, ?, ?, ?)
            """,
                (out.episode_id, claim.claim_id, claim.canonical, claim.claim_type),
            )

        # Upsert relations
        for relation in out.relations:
            cur.execute(
                """
                INSERT INTO relations(episode_id, source_claim_id, target_claim_id, type, strength, rationale)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id, source_claim_id, target_claim_id, type) DO UPDATE SET
                    strength = excluded.strength,
                    rationale = excluded.rationale
            """,
                (
                    out.episode_id,
                    relation.source_claim_id,
                    relation.target_claim_id,
                    relation.type,
                    relation.strength,
                    relation.rationale,
                ),
            )

        # Upsert people mentions
        for person in out.people:
            cur.execute(
                """
                INSERT INTO people(episode_id, mention_id, span_segment_id, t0, t1, surface, normalized, entity_type, external_ids_json, confidence)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id, mention_id) DO UPDATE SET
                    span_segment_id = excluded.span_segment_id,
                    t0 = excluded.t0,
                    t1 = excluded.t1,
                    surface = excluded.surface,
                    normalized = excluded.normalized,
                    entity_type = excluded.entity_type,
                    external_ids_json = excluded.external_ids_json,
                    confidence = excluded.confidence
            """,
                (
                    out.episode_id,
                    person.mention_id,
                    person.span_segment_id,
                    person.t0,
                    person.t1,
                    person.surface,
                    person.normalized,
                    person.entity_type,
                    json.dumps(person.external_ids or {}),
                    person.confidence,
                ),
            )

        # Upsert concepts
        for concept in out.concepts:
            evidence_json = json.dumps([e.model_dump() for e in concept.evidence_spans])
            cur.execute(
                """
                INSERT INTO concepts(episode_id, model_id, name, definition, first_mention_ts, aliases_json, evidence_json)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id, model_id) DO UPDATE SET
                    name = excluded.name,
                    definition = excluded.definition,
                    first_mention_ts = excluded.first_mention_ts,
                    aliases_json = excluded.aliases_json,
                    evidence_json = excluded.evidence_json
            """,
                (
                    out.episode_id,
                    concept.model_id,
                    concept.name,
                    concept.definition,
                    concept.first_mention_ts,
                    json.dumps(concept.aliases or []),
                    evidence_json,
                ),
            )

        # Upsert jargon
        for term in out.jargon:
            evidence_json = json.dumps([e.model_dump() for e in term.evidence_spans])
            cur.execute(
                """
                INSERT INTO jargon(episode_id, term_id, term, category, definition, evidence_json)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id, term_id) DO UPDATE SET
                    term = excluded.term,
                    category = excluded.category,
                    definition = excluded.definition,
                    evidence_json = excluded.evidence_json
            """,
                (
                    out.episode_id,
                    term.term_id,
                    term.term,
                    term.category,
                    term.definition,
                    evidence_json,
                ),
            )

        # Upsert structured categories
        for category in out.structured_categories:
            supporting_evidence_json = json.dumps(category.supporting_evidence)
            cur.execute(
                """
                INSERT INTO structured_categories(episode_id, category_id, category_name, wikidata_qid, coverage_confidence, supporting_evidence_json, frequency_score)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id, category_id) DO UPDATE SET
                    category_name = excluded.category_name,
                    wikidata_qid = excluded.wikidata_qid,
                    coverage_confidence = excluded.coverage_confidence,
                    supporting_evidence_json = excluded.supporting_evidence_json,
                    frequency_score = excluded.frequency_score
            """,
                (
                    out.episode_id,
                    category.category_id,
                    category.category_name,
                    category.wikidata_qid,
                    category.coverage_confidence,
                    supporting_evidence_json,
                    category.frequency_score,
                ),
            )

        # Commit transaction
        conn.commit()

    except Exception as e:
        # Rollback on error
        conn.rollback()
        raise e


def store_segments(conn: sqlite3.Connection, episode_id: str, segments: list) -> None:
    """Store episode segments for reference."""
    cur = conn.cursor()

    try:
        cur.execute("BEGIN")

        # Clear existing segments
        cur.execute("DELETE FROM segments WHERE episode_id = ?", (episode_id,))

        # Insert new segments
        for segment in segments:
            cur.execute(
                """
                INSERT INTO segments(episode_id, segment_id, speaker, t0, t1, text, topic_guess)
                VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    episode_id,
                    segment.segment_id,
                    segment.speaker,
                    segment.t0,
                    segment.t1,
                    segment.text,
                    getattr(segment, "topic_guess", None),
                ),
            )

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e


# Common query utilities


def get_top_claims(
    conn: sqlite3.Connection, episode_id: str, tier: str = "A", limit: int = 10
) -> list:
    """Get top claims by importance score."""
    cur = conn.cursor()
    return cur.execute(
        """
        SELECT claim_id, canonical,
               json_extract(scores_json, '$.importance') AS importance
        FROM claims
        WHERE episode_id = ? AND tier = ?
        ORDER BY importance DESC
        LIMIT ?
    """,
        (episode_id, tier, limit),
    ).fetchall()


def find_contradictions(conn: sqlite3.Connection, episode_id: str) -> list:
    """Find all contradiction relations in an episode."""
    cur = conn.cursor()
    return cur.execute(
        """
        SELECT r.source_claim_id, r.target_claim_id, r.strength, r.rationale,
               sc.canonical as source_claim, tc.canonical as target_claim
        FROM relations r
        JOIN claims sc ON r.episode_id = sc.episode_id AND r.source_claim_id = sc.claim_id
        JOIN claims tc ON r.episode_id = tc.episode_id AND r.target_claim_id = tc.claim_id
        WHERE r.episode_id = ? AND r.type = 'contradicts'
        ORDER BY r.strength DESC
    """,
        (episode_id,),
    ).fetchall()


def search_claims(conn: sqlite3.Connection, query: str, limit: int = 50) -> list:
    """Full-text search across claims."""
    cur = conn.cursor()
    return cur.execute(
        """
        SELECT c.episode_id, c.claim_id, c.canonical, c.claim_type,
               snippet(claims_fts, 2, '<mark>', '</mark>', '...', 32) as snippet
        FROM claims_fts
        JOIN claims c ON claims_fts.episode_id = c.episode_id AND claims_fts.claim_id = c.claim_id
        WHERE claims_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """,
        (query, limit),
    ).fetchall()


def get_person_claims(conn: sqlite3.Connection, normalized_name: str) -> list:
    """Get all claims associated with a person."""
    cur = conn.cursor()
    return cur.execute(
        """
        SELECT DISTINCT c.episode_id, c.claim_id, c.canonical
        FROM claims c
        JOIN quotes_fts q ON c.episode_id = q.episode_id AND c.claim_id = q.claim_id
        JOIN people p ON p.episode_id = c.episode_id
        WHERE p.normalized = ? AND q.quote LIKE '%' || p.surface || '%'
        ORDER BY c.episode_id, c.claim_id
    """,
        (normalized_name,),
    ).fetchall()


def get_cross_episode_concepts(conn: sqlite3.Connection, limit: int = 50) -> list:
    """Get most referenced concepts across all episodes."""
    cur = conn.cursor()
    return cur.execute(
        """
        SELECT name, COUNT(*) as uses,
               GROUP_CONCAT(DISTINCT episode_id) as episodes
        FROM concepts
        GROUP BY name
        ORDER BY uses DESC
        LIMIT ?
    """,
        (limit,),
    ).fetchall()


def get_jargon_glossary(
    conn: sqlite3.Connection, episode_id: str | None = None
) -> list:
    """Get jargon glossary for an episode or all episodes."""
    cur = conn.cursor()
    if episode_id:
        return cur.execute(
            """
            SELECT term, category, definition
            FROM jargon
            WHERE episode_id = ?
            ORDER BY term
        """,
            (episode_id,),
        ).fetchall()
    else:
        return cur.execute(
            """
            SELECT DISTINCT term, category, definition
            FROM jargon
            ORDER BY term
        """
        ).fetchall()
