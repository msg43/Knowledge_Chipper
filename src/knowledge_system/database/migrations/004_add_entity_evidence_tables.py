"""
Migration 004: Add Evidence Tables for People, Concepts, and Jargon

Adds three new tables to store ALL mentions/usages of entities with timestamps,
not just the first mention.

Tables:
- person_evidence: All mentions of people with timestamps
- concept_evidence: All usages of concepts with timestamps
- jargon_evidence: All usages of jargon with timestamps
"""

import logging

logger = logging.getLogger(__name__)


def upgrade(db_service):
    """Add entity evidence tables."""
    connection = db_service.engine.raw_connection()
    try:
        cursor = connection.cursor()

        logger.info("Creating person_evidence table...")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS person_evidence (
                person_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,

                -- Timing
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,

                -- Content
                quote TEXT NOT NULL,
                surface_form TEXT,
                segment_id TEXT,

                -- Context (extended window)
                context_start_time TEXT,
                context_end_time TEXT,
                context_text TEXT,
                context_type TEXT DEFAULT 'exact',

                created_at DATETIME DEFAULT (datetime('now')),

                PRIMARY KEY (person_id, claim_id, sequence),
                FOREIGN KEY (person_id) REFERENCES people(person_id) ON DELETE CASCADE,
                FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
            )
        """
        )

        logger.info("Creating concept_evidence table...")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS concept_evidence (
                concept_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,

                -- Timing
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,

                -- Content
                quote TEXT NOT NULL,
                segment_id TEXT,

                -- Context (extended window)
                context_start_time TEXT,
                context_end_time TEXT,
                context_text TEXT,
                context_type TEXT DEFAULT 'exact',

                created_at DATETIME DEFAULT (datetime('now')),

                PRIMARY KEY (concept_id, claim_id, sequence),
                FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE,
                FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
            )
        """
        )

        logger.info("Creating jargon_evidence table...")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jargon_evidence (
                jargon_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,

                -- Timing
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,

                -- Content
                quote TEXT NOT NULL,
                segment_id TEXT,

                -- Context (extended window)
                context_start_time TEXT,
                context_end_time TEXT,
                context_text TEXT,
                context_type TEXT DEFAULT 'exact',

                created_at DATETIME DEFAULT (datetime('now')),

                PRIMARY KEY (jargon_id, claim_id, sequence),
                FOREIGN KEY (jargon_id) REFERENCES jargon_terms(jargon_id) ON DELETE CASCADE,
                FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
            )
        """
        )

        # Create indexes for performance
        logger.info("Creating indexes...")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_person_evidence_claim ON person_evidence(claim_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_person_evidence_time ON person_evidence(start_time)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_concept_evidence_claim ON concept_evidence(claim_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_concept_evidence_time ON concept_evidence(start_time)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_jargon_evidence_claim ON jargon_evidence(claim_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_jargon_evidence_time ON jargon_evidence(start_time)"
        )

        connection.commit()
        logger.info("✅ Migration 004 complete: Entity evidence tables created")

    except Exception as e:
        connection.rollback()
        logger.error(f"❌ Migration 004 failed: {e}")
        raise
    finally:
        connection.close()


def downgrade(db_service):
    """Remove entity evidence tables."""
    connection = db_service.engine.raw_connection()
    try:
        cursor = connection.cursor()

        logger.info("Removing entity evidence tables...")
        cursor.execute("DROP TABLE IF EXISTS person_evidence")
        cursor.execute("DROP TABLE IF EXISTS concept_evidence")
        cursor.execute("DROP TABLE IF EXISTS jargon_evidence")

        connection.commit()
        logger.info("✅ Migration 004 rollback complete")

    except Exception as e:
        connection.rollback()
        logger.error(f"❌ Migration 004 rollback failed: {e}")
        raise
    finally:
        connection.close()


def get_migration_info():
    """Return migration metadata."""
    return {
        "version": "004",
        "name": "add_entity_evidence_tables",
        "description": "Add evidence tables for people, concepts, and jargon to track ALL mentions with timestamps",
    }
