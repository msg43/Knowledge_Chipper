"""
Database migration to add enhanced YouTube fields.

Adds support for:
- Related videos suggestions
- Detailed channel statistics
- Video chapters/timestamps

Migration: 003_add_enhanced_youtube_fields
Created: 2024-12-19
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class Migration003:
    """Add enhanced YouTube fields to media_sources table"""

    def __init__(self, engine):
        self.engine = engine
        self.Session = sessionmaker(bind=engine)

    def up(self) -> bool:
        """Apply migration: add enhanced YouTube fields"""
        try:
            with self.Session() as session:
                logger.info("Starting migration 003: Add enhanced YouTube fields")

                # Add new columns to media_sources table
                logger.info("Adding related_videos_json column...")
                session.execute(
                    text(
                        """
                    ALTER TABLE media_sources
                    ADD COLUMN related_videos_json TEXT
                """
                    )
                )

                logger.info("Adding channel_stats_json column...")
                session.execute(
                    text(
                        """
                    ALTER TABLE media_sources
                    ADD COLUMN channel_stats_json TEXT
                """
                    )
                )

                logger.info("Adding video_chapters_json column...")
                session.execute(
                    text(
                        """
                    ALTER TABLE media_sources
                    ADD COLUMN video_chapters_json TEXT
                """
                    )
                )

                session.commit()
                logger.info("✅ Migration 003 completed successfully")
                return True

        except Exception as e:
            logger.error(f"❌ Migration 003 failed: {e}")
            return False

    def down(self) -> bool:
        """Rollback migration: remove enhanced YouTube fields"""
        try:
            with self.Session() as session:
                logger.info(
                    "Rolling back migration 003: Remove enhanced YouTube fields"
                )

                # Remove the added columns
                logger.info("Removing related_videos_json column...")
                session.execute(
                    text(
                        """
                    ALTER TABLE media_sources
                    DROP COLUMN related_videos_json
                """
                    )
                )

                logger.info("Removing channel_stats_json column...")
                session.execute(
                    text(
                        """
                    ALTER TABLE media_sources
                    DROP COLUMN channel_stats_json
                """
                    )
                )

                logger.info("Removing video_chapters_json column...")
                session.execute(
                    text(
                        """
                    ALTER TABLE media_sources
                    DROP COLUMN video_chapters_json
                """
                    )
                )

                session.commit()
                logger.info("✅ Migration 003 rollback completed successfully")
                return True

        except Exception as e:
            logger.error(f"❌ Migration 003 rollback failed: {e}")
            return False

    @staticmethod
    def get_version() -> str:
        """Get migration version"""
        return "003"

    @staticmethod
    def get_description() -> str:
        """Get migration description"""
        return "Add enhanced YouTube fields (related videos, channel stats, video chapters)"


def run_migration(engine):
    """Run this migration"""
    migration = Migration003(engine)
    return migration.up()


def rollback_migration(engine):
    """Rollback this migration"""
    migration = Migration003(engine)
    return migration.down()
