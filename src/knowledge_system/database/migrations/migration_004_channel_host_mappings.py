"""
Migration 004: Add Channel Host Mappings Table

This migration adds a table to store channel-to-host name mappings that are learned
from user corrections in speaker assignments. This allows the system to remember
that "Eurodollar University" channel = "Jeff Snider" host, for example.
"""

from sqlalchemy import text

from ..service import DatabaseService
from ..models import Base


class Migration004:
    """Add channel_host_mappings table for learning channel-to-host relationships."""

    @staticmethod
    def migrate():
        """Run the migration."""
        db_service = DatabaseService()

        # Create the table using SQLAlchemy metadata
        # The table is already defined in speaker_models.py as ChannelHostMapping
        Base.metadata.create_all(
            db_service.engine, tables=[Base.metadata.tables["channel_host_mappings"]]
        )

        print("Migration 004: Added channel_host_mappings table")

    @staticmethod
    def rollback():
        """Rollback the migration."""
        db_service = DatabaseService()

        with db_service.engine.connect() as connection:
            connection.execute(text("DROP TABLE IF EXISTS channel_host_mappings"))
            connection.commit()

        print("Migration 004: Removed channel_host_mappings table")


if __name__ == "__main__":
    Migration004.migrate()
