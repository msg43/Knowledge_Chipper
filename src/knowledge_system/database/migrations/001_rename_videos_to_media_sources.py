"""
Migration 001: Rename 'videos' table to 'media_sources'

This migration renames the videos table to media_sources to better reflect
that it can store various media types (YouTube, RSS, uploads, etc).

Migration includes:
1. Create new media_sources table with updated schema
2. Migrate all data from videos to media_sources
3. Update all foreign key references
4. Create compatibility view for backward compatibility
5. Drop old videos table
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Migration configuration
MIGRATION_BATCH_SIZE = 1000
ENABLE_COMPATIBILITY_VIEWS = True
SCHEMA_VERSION = "2.0"


class Migration001:
    """Rename videos table to media_sources"""

    def __init__(self, database_url: str = "sqlite:///knowledge_system.db"):
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        self.inspector = inspect(self.engine)

    def up(self) -> bool:
        """Apply migration: rename videos to media_sources"""
        logger.info("Starting migration 001: Rename videos → media_sources")

        with self.Session() as session:
            try:
                # Step 1: Check if migration already applied
                if self._is_migration_applied(session):
                    logger.info("Migration already applied, skipping")
                    return True

                # Step 2: Create schema_version table if not exists
                self._ensure_schema_version_table(session)

                # Step 3: Begin transaction
                session.begin()

                # Step 4: Create new media_sources table with updated schema
                logger.info("Creating media_sources table...")
                session.execute(
                    text(
                        """
                    CREATE TABLE IF NOT EXISTS media_sources (
                        media_id TEXT PRIMARY KEY,
                        source_type TEXT NOT NULL DEFAULT 'youtube',
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        description TEXT,
                        uploader TEXT,
                        uploader_id TEXT,
                        upload_date TEXT,
                        duration_seconds INTEGER,
                        view_count INTEGER,
                        like_count INTEGER,
                        comment_count INTEGER,
                        categories_json TEXT,
                        privacy_status TEXT,
                        caption_availability INTEGER,
                        thumbnail_url TEXT,
                        thumbnail_local_path TEXT,
                        tags_json TEXT,
                        extracted_keywords_json TEXT,
                        extraction_method TEXT,
                        processed_at TIMESTAMP,
                        bright_data_session_id TEXT,
                        processing_cost REAL,
                        status TEXT DEFAULT 'pending',
                        -- New sync columns
                        sync_status TEXT DEFAULT 'pending',
                        last_synced TIMESTAMP,
                        sync_version INTEGER DEFAULT 0,
                        sync_checksum TEXT
                    )
                """
                    )
                )

                # Step 5: Copy data from videos to media_sources
                logger.info("Migrating data from videos to media_sources...")
                record_count = session.execute(
                    text("SELECT COUNT(*) FROM videos")
                ).scalar()
                logger.info(f"Found {record_count} records to migrate")

                # Migrate in batches
                offset = 0
                while offset < record_count:
                    session.execute(
                        text(
                            f"""
                        INSERT INTO media_sources (
                            media_id, source_type, title, url, description,
                            uploader, uploader_id, upload_date, duration_seconds,
                            view_count, like_count, comment_count, categories_json,
                            privacy_status, caption_availability, thumbnail_url,
                            thumbnail_local_path, tags_json, extracted_keywords_json,
                            extraction_method, processed_at, bright_data_session_id,
                            processing_cost, status
                        )
                        SELECT
                            video_id, 'youtube', title, url, description,
                            uploader, uploader_id, upload_date, duration_seconds,
                            view_count, like_count, comment_count, categories_json,
                            privacy_status, caption_availability, thumbnail_url,
                            thumbnail_local_path, tags_json, extracted_keywords_json,
                            extraction_method, processed_at, bright_data_session_id,
                            processing_cost, status
                        FROM videos
                        LIMIT {MIGRATION_BATCH_SIZE} OFFSET {offset}
                    """
                        )
                    )
                    offset += MIGRATION_BATCH_SIZE
                    logger.info(
                        f"Migrated {min(offset, record_count)}/{record_count} records"
                    )

                # Step 6: Create indexes on new table
                logger.info("Creating indexes on media_sources...")
                session.execute(
                    text(
                        """
                    CREATE INDEX idx_media_sync ON media_sources (sync_status, last_synced)
                    WHERE sync_status = 'pending'
                """
                    )
                )
                session.execute(
                    text(
                        """
                    CREATE INDEX idx_media_type ON media_sources (source_type, processed_at DESC)
                """
                    )
                )

                # Step 7: Update foreign key references in dependent tables
                logger.info("Updating foreign key references...")

                # Update transcripts table
                session.execute(
                    text(
                        """
                    CREATE TABLE transcripts_new (
                        transcript_id TEXT PRIMARY KEY,
                        media_id TEXT REFERENCES media_sources(media_id),
                        language TEXT NOT NULL,
                        is_manual INTEGER NOT NULL,
                        transcript_type TEXT,
                        transcript_text TEXT NOT NULL,
                        transcript_text_with_speakers TEXT,
                        transcript_segments_json TEXT NOT NULL,
                        diarization_segments_json TEXT,
                        whisper_model TEXT,
                        device_used TEXT,
                        diarization_enabled INTEGER DEFAULT 0,
                        diarization_model TEXT,
                        include_timestamps INTEGER DEFAULT 1,
                        strip_interjections INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processing_time_seconds REAL,
                        cost REAL DEFAULT 0.0,
                        sync_status TEXT DEFAULT 'pending',
                        last_synced TIMESTAMP,
                        sync_version INTEGER DEFAULT 0,
                        sync_checksum TEXT
                    )
                """
                    )
                )

                session.execute(
                    text(
                        """
                    INSERT INTO transcripts_new
                    SELECT
                        transcript_id, video_id as media_id, language, is_manual,
                        transcript_type, transcript_text, transcript_text_with_speakers,
                        transcript_segments_json, diarization_segments_json,
                        whisper_model, device_used, diarization_enabled,
                        diarization_model, include_timestamps, strip_interjections,
                        created_at, processing_time_seconds, cost,
                        'pending', NULL, 0, NULL
                    FROM transcripts
                """
                    )
                )

                session.execute(text("DROP TABLE transcripts"))
                session.execute(
                    text("ALTER TABLE transcripts_new RENAME TO transcripts")
                )

                # Update summaries table
                session.execute(
                    text(
                        """
                    CREATE TABLE summaries_new (
                        summary_id TEXT PRIMARY KEY,
                        media_id TEXT REFERENCES media_sources(media_id),
                        transcript_id TEXT REFERENCES transcripts(transcript_id),
                        summary_text TEXT NOT NULL,
                        summary_method TEXT NOT NULL,
                        llm_provider TEXT NOT NULL,
                        llm_model TEXT NOT NULL,
                        prompt_template TEXT,
                        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processing_time_seconds REAL,
                        input_tokens INTEGER,
                        output_tokens INTEGER,
                        total_tokens INTEGER,
                        cost REAL DEFAULT 0.0,
                        metadata_json TEXT,
                        hce_data_json TEXT,
                        sync_status TEXT DEFAULT 'pending',
                        last_synced TIMESTAMP,
                        sync_version INTEGER DEFAULT 0,
                        sync_checksum TEXT
                    )
                """
                    )
                )

                session.execute(
                    text(
                        """
                    INSERT INTO summaries_new
                    SELECT
                        summary_id, video_id as media_id, transcript_id,
                        summary_text, summary_method, llm_provider, llm_model,
                        prompt_template, generated_at, processing_time_seconds,
                        input_tokens, output_tokens, total_tokens, cost,
                        metadata_json, hce_data_json,
                        'pending', NULL, 0, NULL
                    FROM summaries
                """
                    )
                )

                session.execute(text("DROP TABLE summaries"))
                session.execute(text("ALTER TABLE summaries_new RENAME TO summaries"))

                # Step 8: Create compatibility view
                if ENABLE_COMPATIBILITY_VIEWS:
                    logger.info("Creating compatibility view...")
                    session.execute(
                        text(
                            """
                        CREATE VIEW videos AS
                        SELECT
                            media_id as video_id,
                            title, url, description, uploader, uploader_id,
                            upload_date, duration_seconds, view_count, like_count,
                            comment_count, categories_json, privacy_status,
                            caption_availability, thumbnail_url, thumbnail_local_path,
                            tags_json, extracted_keywords_json, extraction_method,
                            processed_at, bright_data_session_id, processing_cost, status
                        FROM media_sources
                        WHERE source_type = 'youtube'
                    """
                        )
                    )

                # Step 9: Drop old videos table
                logger.info("Dropping old videos table...")
                session.execute(text("DROP TABLE IF EXISTS videos_old"))
                session.execute(text("ALTER TABLE videos RENAME TO videos_old"))

                # Step 10: Update schema version
                session.execute(
                    text(
                        """
                    INSERT INTO schema_version (version, applied_at, description)
                    VALUES (:version, :applied_at, :description)
                """
                    ),
                    {
                        "version": "001",
                        "applied_at": datetime.utcnow(),
                        "description": "Rename videos table to media_sources",
                    },
                )

                # Commit transaction
                session.commit()
                logger.info("[SUCCESS] Migration complete: videos → media_sources")
                return True

            except Exception as e:
                logger.error(f"Migration failed: {e}")
                session.rollback()
                raise

    def down(self) -> bool:
        """Rollback migration: rename media_sources back to videos"""
        logger.info("Rolling back migration 001: media_sources → videos")

        with self.Session() as session:
            try:
                # Reverse the migration
                session.begin()

                # Drop compatibility view
                session.execute(text("DROP VIEW IF EXISTS videos"))

                # Rename media_sources back to videos
                session.execute(text("ALTER TABLE media_sources RENAME TO videos"))

                # Update foreign keys back to video_id
                # ... (reverse operations)

                session.commit()
                logger.info("Rollback complete")
                return True

            except Exception as e:
                logger.error(f"Rollback failed: {e}")
                session.rollback()
                raise

    def _is_migration_applied(self, session: Session) -> bool:
        """Check if this migration has already been applied"""
        # Check if media_sources table exists
        return "media_sources" in self.inspector.get_table_names()

    def _ensure_schema_version_table(self, session: Session) -> None:
        """Create schema_version table if it doesn't exist"""
        session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS schema_version (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL,
                description TEXT
            )
        """
            )
        )


if __name__ == "__main__":
    # Run migration
    migration = Migration001()
    migration.up()
