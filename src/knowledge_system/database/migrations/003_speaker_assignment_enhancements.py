"""
Database Migration 003: Speaker Assignment Enhancements

Adds enhanced columns to speaker_assignments table and creates speaker_processing_sessions table
to support comprehensive speaker attribution learning and eliminate sidecar file dependency.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from ...logger import get_logger

logger = get_logger(__name__)

Base = declarative_base()


class Migration003:
    """Migration 003: Speaker Assignment Enhancements"""

    version = "003"
    description = (
        "Add enhanced speaker assignment columns and processing sessions table"
    )

    def upgrade(self, session: Session) -> bool:
        """Apply the migration."""
        try:
            logger.info("Starting Migration 003: Speaker Assignment Enhancements")

            # 1. Add new columns to speaker_assignments table
            self._add_speaker_assignment_columns(session)

            # 2. Create speaker_processing_sessions table
            self._create_processing_sessions_table(session)

            # 3. Add database indexes for performance
            self._add_database_indexes(session)

            session.commit()
            logger.info("Migration 003 completed successfully")
            return True

        except Exception as e:
            logger.error(f"Migration 003 failed: {e}")
            session.rollback()
            return False

    def downgrade(self, session: Session) -> bool:
        """Reverse the migration."""
        try:
            logger.info("Starting Migration 003 downgrade")

            # 1. Drop speaker_processing_sessions table
            session.execute("DROP TABLE IF EXISTS speaker_processing_sessions")

            # 2. Remove added columns from speaker_assignments (if possible)
            # Note: SQLite doesn't support DROP COLUMN, so we'd need to recreate the table
            # For safety, we'll log a warning instead
            logger.warning(
                "Cannot remove columns from speaker_assignments in SQLite - manual cleanup required"
            )

            session.commit()
            logger.info("Migration 003 downgrade completed")
            return True

        except Exception as e:
            logger.error(f"Migration 003 downgrade failed: {e}")
            session.rollback()
            return False

    def _add_speaker_assignment_columns(self, session: Session):
        """Add new columns to speaker_assignments table."""
        columns_to_add = [
            "ALTER TABLE speaker_assignments ADD COLUMN suggested_name VARCHAR(255)",
            "ALTER TABLE speaker_assignments ADD COLUMN suggestion_confidence FLOAT DEFAULT 0.0",
            "ALTER TABLE speaker_assignments ADD COLUMN suggestion_method VARCHAR(100)",
            "ALTER TABLE speaker_assignments ADD COLUMN sample_segments_json TEXT",
            "ALTER TABLE speaker_assignments ADD COLUMN total_duration FLOAT DEFAULT 0.0",
            "ALTER TABLE speaker_assignments ADD COLUMN segment_count INTEGER DEFAULT 0",
            "ALTER TABLE speaker_assignments ADD COLUMN processing_metadata_json TEXT",
            "ALTER TABLE speaker_assignments ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        ]

        for sql in columns_to_add:
            try:
                session.execute(sql)
                logger.debug(f"Added column: {sql}")
            except Exception as e:
                # Column might already exist, log and continue
                logger.debug(f"Column addition skipped (might already exist): {e}")

    def _create_processing_sessions_table(self, session: Session):
        """Create speaker_processing_sessions table."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS speaker_processing_sessions (
            session_id VARCHAR(50) PRIMARY KEY,
            recording_path VARCHAR(500) NOT NULL,
            processing_method VARCHAR(100),
            total_speakers INTEGER,
            total_duration FLOAT,
            ai_suggestions_json TEXT,
            user_corrections_json TEXT,
            confidence_scores_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME
        )
        """

        session.execute(create_table_sql)
        logger.info("Created speaker_processing_sessions table")

    def _add_database_indexes(self, session: Session):
        """Add database indexes for performance."""
        indexes_to_create = [
            "CREATE INDEX IF NOT EXISTS idx_speaker_assignments_recording_path ON speaker_assignments(recording_path)",
            "CREATE INDEX IF NOT EXISTS idx_speaker_assignments_assigned_name ON speaker_assignments(assigned_name)",
            "CREATE INDEX IF NOT EXISTS idx_speaker_assignments_user_confirmed ON speaker_assignments(user_confirmed)",
            "CREATE INDEX IF NOT EXISTS idx_speaker_assignments_created_at ON speaker_assignments(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_speaker_assignments_suggestion_method ON speaker_assignments(suggestion_method)",
            "CREATE INDEX IF NOT EXISTS idx_processing_sessions_recording_path ON speaker_processing_sessions(recording_path)",
            "CREATE INDEX IF NOT EXISTS idx_processing_sessions_created_at ON speaker_processing_sessions(created_at)",
        ]

        for sql in indexes_to_create:
            try:
                session.execute(sql)
                logger.debug(f"Created index: {sql}")
            except Exception as e:
                logger.debug(f"Index creation skipped (might already exist): {e}")


def run_migration(session: Session) -> bool:
    """Run migration 003."""
    migration = Migration003()
    return migration.upgrade(session)


def rollback_migration(session: Session) -> bool:
    """Rollback migration 003."""
    migration = Migration003()
    return migration.downgrade(session)


if __name__ == "__main__":
    # Test the migration
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///test_migration.db")
    Session = sessionmaker(bind=engine)

    with Session() as session:
        success = run_migration(session)
        print(f"Migration test: {'SUCCESS' if success else 'FAILED'}")
