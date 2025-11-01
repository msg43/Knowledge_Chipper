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
    source_id: str | None = None,
) -> None:
    """
    Persist pipeline outputs to SQLite with idempotent upserts.

    Args:
        conn: SQLite connection
        out: Pipeline outputs to persist
        episode_title: Optional episode title
        recorded_at: Optional recording timestamp (ISO8601)
        source_id: Optional reference to existing source_id in videos table
    """
    cur = conn.cursor()

    try:
        # Begin transaction
        cur.execute("BEGIN")

        # Upsert episode
        cur.execute(
            """
            INSERT INTO episodes(source_id, source_id, title, recorded_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                source_id = COALESCE(excluded.source_id, source_id),
                title = COALESCE(excluded.title, title),
                recorded_at = COALESCE(excluded.recorded_at, recorded_at)
        """,
            (out.source_id, source_id, episode_title, recorded_at),
        )

        # Clear existing FTS entries for this episode (for clean reindex)
        cur.execute("DELETE FROM claims_fts WHERE source_id = ?", (out.source_id,))
        cur.execute("DELETE FROM quotes_fts WHERE source_id = ?", (out.source_id,))

        # Upsert milestones
        for milestone in out.milestones:
            cur.execute(
                """
                INSERT INTO milestones(source_id, milestone_id, t0, t1, summary)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(source_id, milestone_id) DO UPDATE SET
                    t0 = excluded.t0,
                    t1 = excluded.t1,
                    summary = excluded.summary
            """,
                (
                    out.source_id,
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
                INSERT INTO claims(source_id, claim_id, canonical, claim_type, tier, first_mention_ts, scores_json, temporality_score, temporality_confidence, temporality_rationale, structured_categories_json, category_relevance_scores_json)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, claim_id) DO UPDATE SET
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
                    out.source_id,
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
                WHERE source_id = ? AND claim_id = ?
            """,
                (out.source_id, claim.claim_id),
            )

            # Insert evidence spans with dual-level context
            for i, evidence in enumerate(claim.evidence):
                cur.execute(
                    """
                    INSERT INTO evidence_spans(source_id, claim_id, seq, segment_id, t0, t1, quote, context_t0, context_t1, context_text, context_type)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        out.source_id,
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
                    INSERT INTO quotes_fts(source_id, claim_id, quote)
                    VALUES(?, ?, ?)
                """,
                    (out.source_id, claim.claim_id, evidence.quote),
                )

            # Index claim in FTS
            cur.execute(
                """
                INSERT INTO claims_fts(source_id, claim_id, canonical, claim_type)
                VALUES(?, ?, ?, ?)
            """,
                (out.source_id, claim.claim_id, claim.canonical, claim.claim_type),
            )

        # Upsert relations
        for relation in out.relations:
            cur.execute(
                """
                INSERT INTO relations(source_id, source_claim_id, target_claim_id, type, strength, rationale)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, source_claim_id, target_claim_id, type) DO UPDATE SET
                    strength = excluded.strength,
                    rationale = excluded.rationale
            """,
                (
                    out.source_id,
                    relation.source_claim_id,
                    relation.target_claim_id,
                    relation.type,
                    relation.strength,
                    relation.rationale,
                ),
            )

        # Upsert people mentions
        for person in out.people:
            # Extract context_quote from the person's surface text (as a fallback)
            # In the future, this could be enhanced to include actual quote context
            context_quote = person.normalized or person.surface

            cur.execute(
                """
                INSERT INTO people(source_id, mention_id, span_segment_id, t0, t1, surface, normalized, entity_type, external_ids_json, confidence, context_quote)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, mention_id) DO UPDATE SET
                    span_segment_id = excluded.span_segment_id,
                    t0 = excluded.t0,
                    t1 = excluded.t1,
                    surface = excluded.surface,
                    normalized = excluded.normalized,
                    entity_type = excluded.entity_type,
                    external_ids_json = excluded.external_ids_json,
                    confidence = excluded.confidence,
                    context_quote = excluded.context_quote
            """,
                (
                    out.source_id,
                    person.mention_id,
                    person.span_segment_id,
                    person.t0,
                    person.t1,
                    person.surface,
                    person.normalized,
                    person.entity_type,
                    json.dumps(person.external_ids or {}),
                    person.confidence,
                    context_quote,
                ),
            )

        # Upsert concepts
        for concept in out.concepts:
            evidence_json = json.dumps([e.model_dump() for e in concept.evidence_spans])
            # Extract context_quote from first evidence span if available
            context_quote = (
                concept.evidence_spans[0].quote if concept.evidence_spans else None
            )

            cur.execute(
                """
                INSERT INTO concepts(source_id, model_id, name, definition, first_mention_ts, aliases_json, evidence_json, context_quote)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, model_id) DO UPDATE SET
                    name = excluded.name,
                    definition = excluded.definition,
                    first_mention_ts = excluded.first_mention_ts,
                    aliases_json = excluded.aliases_json,
                    evidence_json = excluded.evidence_json,
                    context_quote = excluded.context_quote
            """,
                (
                    out.source_id,
                    concept.model_id,
                    concept.name,
                    concept.definition,
                    concept.first_mention_ts,
                    json.dumps(concept.aliases or []),
                    evidence_json,
                    context_quote,
                ),
            )

        # Upsert jargon
        for term in out.jargon:
            evidence_json = json.dumps([e.model_dump() for e in term.evidence_spans])
            # Extract context_quote from first evidence span if available
            context_quote = (
                term.evidence_spans[0].quote if term.evidence_spans else None
            )

            cur.execute(
                """
                INSERT INTO jargon(source_id, term_id, term, category, definition, evidence_json, context_quote)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, term_id) DO UPDATE SET
                    term = excluded.term,
                    category = excluded.category,
                    definition = excluded.definition,
                    evidence_json = excluded.evidence_json,
                    context_quote = excluded.context_quote
            """,
                (
                    out.source_id,
                    term.term_id,
                    term.term,
                    term.category,
                    term.definition,
                    evidence_json,
                    context_quote,
                ),
            )

        # Upsert structured categories
        for category in out.structured_categories:
            supporting_evidence_json = json.dumps(category.supporting_evidence)
            cur.execute(
                """
                INSERT INTO structured_categories(source_id, category_id, category_name, wikidata_qid, coverage_confidence, supporting_evidence_json, frequency_score)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, category_id) DO UPDATE SET
                    category_name = excluded.category_name,
                    wikidata_qid = excluded.wikidata_qid,
                    coverage_confidence = excluded.coverage_confidence,
                    supporting_evidence_json = excluded.supporting_evidence_json,
                    frequency_score = excluded.frequency_score
            """,
                (
                    out.source_id,
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


def store_segments(conn: sqlite3.Connection, source_id: str, segments: list) -> None:
    """Store episode segments for reference."""
    cur = conn.cursor()

    try:
        cur.execute("BEGIN")

        # Clear existing segments
        cur.execute("DELETE FROM segments WHERE source_id = ?", (source_id,))

        # Insert new segments
        for segment in segments:
            cur.execute(
                """
                INSERT INTO segments(source_id, segment_id, speaker, t0, t1, text, topic_guess)
                VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    source_id,
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


def episode_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    """
    Check if episode exists in HCE database.

    Args:
        conn: SQLite connection
        source_id: Episode ID to check

    Returns:
        True if episode exists, False otherwise
    """
    cur = conn.cursor()
    result = cur.execute(
        "SELECT 1 FROM episodes WHERE source_id = ? LIMIT 1", (source_id,)
    )
    return result.fetchone() is not None


def update_speaker_names(
    conn: sqlite3.Connection, source_id: str, speaker_mappings: dict[str, str]
) -> tuple[bool, str]:
    """
    Update speaker names throughout HCE database for an episode.

    This function updates the speaker names in the segments table. Note that
    claims, evidence spans, and other extracted data reference segments by ID,
    not by speaker name, so those don't need updating. However, the segments
    table is used for lookups and context display.

    Args:
        conn: SQLite connection
        source_id: Episode ID to update
        speaker_mappings: Dict of {old_speaker_name: new_speaker_name}

    Returns:
        Tuple of (success: bool, message: str)
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        cur = conn.cursor()
        cur.execute("BEGIN")

        updated_count = 0
        for old_speaker, new_speaker in speaker_mappings.items():
            # Update segments table
            cur.execute(
                """
                UPDATE segments
                SET speaker = ?
                WHERE source_id = ? AND speaker = ?
            """,
                (new_speaker, source_id, old_speaker),
            )
            rows_updated = cur.rowcount
            updated_count += rows_updated

            if rows_updated > 0:
                logger.info(
                    f"Updated {rows_updated} segments: '{old_speaker}' -> '{new_speaker}' "
                    f"for episode {source_id}"
                )

        conn.commit()

        if updated_count == 0:
            return (
                True,
                f"No segments found matching the old speaker names for episode {source_id}",
            )

        return (
            True,
            f"Successfully updated {updated_count} segments with new speaker names",
        )

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update speaker names for episode {source_id}: {e}")
        return (False, f"Failed to update speaker names: {str(e)}")


def delete_episode_hce_data(
    conn: sqlite3.Connection, source_id: str
) -> tuple[bool, str]:
    """
    Delete all HCE extracted data for an episode (claims, evidence, entities).

    Keeps the episode and segments records, but removes all extracted analysis
    so it can be reprocessed with updated speaker names.

    Args:
        conn: SQLite connection
        source_id: Episode ID to clear

    Returns:
        Tuple of (success: bool, message: str)
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        cur = conn.cursor()
        cur.execute("BEGIN")

        # Delete in order respecting foreign keys
        # Evidence spans reference claims
        cur.execute("DELETE FROM evidence_spans WHERE source_id = ?", (source_id,))
        evidence_count = cur.rowcount

        # Relations reference claims
        cur.execute("DELETE FROM relations WHERE source_id = ?", (source_id,))
        relations_count = cur.rowcount

        # Delete main entity tables
        cur.execute("DELETE FROM claims WHERE source_id = ?", (source_id,))
        claims_count = cur.rowcount

        cur.execute("DELETE FROM people WHERE source_id = ?", (source_id,))
        people_count = cur.rowcount

        cur.execute("DELETE FROM concepts WHERE source_id = ?", (source_id,))
        concepts_count = cur.rowcount

        cur.execute("DELETE FROM jargon WHERE source_id = ?", (source_id,))
        jargon_count = cur.rowcount

        cur.execute("DELETE FROM mental_models WHERE source_id = ?", (source_id,))
        mental_models_count = cur.rowcount

        # Delete milestones
        cur.execute("DELETE FROM milestones WHERE source_id = ?", (source_id,))
        milestones_count = cur.rowcount

        # Delete FTS entries
        cur.execute("DELETE FROM claims_fts WHERE source_id = ?", (source_id,))
        cur.execute("DELETE FROM quotes_fts WHERE source_id = ?", (source_id,))

        conn.commit()

        message = (
            f"Deleted HCE data for episode {source_id}: "
            f"{claims_count} claims, {evidence_count} evidence spans, "
            f"{relations_count} relations, {people_count} people, "
            f"{concepts_count} concepts, {jargon_count} jargon terms, "
            f"{mental_models_count} mental models, {milestones_count} milestones"
        )

        logger.info(message)
        return (True, message)

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to delete HCE data for episode {source_id}: {e}")
        return (False, f"Failed to delete HCE data: {str(e)}")


def get_top_claims(
    conn: sqlite3.Connection, source_id: str, tier: str = "A", limit: int = 10
) -> list:
    """Get top claims by importance score."""
    cur = conn.cursor()
    return cur.execute(
        """
        SELECT claim_id, canonical,
               json_extract(scores_json, '$.importance') AS importance
        FROM claims
        WHERE source_id = ? AND tier = ?
        ORDER BY importance DESC
        LIMIT ?
    """,
        (source_id, tier, limit),
    ).fetchall()


def find_contradictions(conn: sqlite3.Connection, source_id: str) -> list:
    """Find all contradiction relations in an episode."""
    cur = conn.cursor()
    return cur.execute(
        """
        SELECT r.source_claim_id, r.target_claim_id, r.strength, r.rationale,
               sc.canonical as source_claim, tc.canonical as target_claim
        FROM relations r
        JOIN claims sc ON r.source_id = sc.source_id AND r.source_claim_id = sc.claim_id
        JOIN claims tc ON r.source_id = tc.source_id AND r.target_claim_id = tc.claim_id
        WHERE r.source_id = ? AND r.type = 'contradicts'
        ORDER BY r.strength DESC
    """,
        (source_id,),
    ).fetchall()


def search_claims(conn: sqlite3.Connection, query: str, limit: int = 50) -> list:
    """Full-text search across claims."""
    cur = conn.cursor()
    return cur.execute(
        """
        SELECT c.source_id, c.claim_id, c.canonical, c.claim_type,
               snippet(claims_fts, 2, '<mark>', '</mark>', '...', 32) as snippet
        FROM claims_fts
        JOIN claims c ON claims_fts.source_id = c.source_id AND claims_fts.claim_id = c.claim_id
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
        SELECT DISTINCT c.source_id, c.claim_id, c.canonical
        FROM claims c
        JOIN quotes_fts q ON c.source_id = q.source_id AND c.claim_id = q.claim_id
        JOIN people p ON p.source_id = c.source_id
        WHERE p.normalized = ? AND q.quote LIKE '%' || p.surface || '%'
        ORDER BY c.source_id, c.claim_id
    """,
        (normalized_name,),
    ).fetchall()


def get_cross_episode_concepts(conn: sqlite3.Connection, limit: int = 50) -> list:
    """Get most referenced concepts across all episodes."""
    cur = conn.cursor()
    return cur.execute(
        """
        SELECT name, COUNT(*) as uses,
               GROUP_CONCAT(DISTINCT source_id) as episodes
        FROM concepts
        GROUP BY name
        ORDER BY uses DESC
        LIMIT ?
    """,
        (limit,),
    ).fetchall()


def get_jargon_glossary(
    conn: sqlite3.Connection, source_id: str | None = None
) -> list:
    """Get jargon glossary for an episode or all episodes."""
    cur = conn.cursor()
    if source_id:
        return cur.execute(
            """
            SELECT term, category, definition
            FROM jargon
            WHERE source_id = ?
            ORDER BY term
        """,
            (source_id,),
        ).fetchall()
    else:
        return cur.execute(
            """
            SELECT DISTINCT term, category, definition
            FROM jargon
            ORDER BY term
        """
        ).fetchall()
