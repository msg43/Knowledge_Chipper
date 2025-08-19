#!/usr/bin/env python3
"""
Migrate existing database records for HCE compatibility.

This script:
1. Sets processing_type='legacy' for all existing summaries
2. Prepares MOC data for HCE migration
3. Creates backup before migration
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from ..logger import get_logger

logger = get_logger(__name__)


def backup_database(db_path: str) -> Path:
    """Create a backup of the database before migration."""
    backup_path = Path(f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    try:
        # Use SQLite's backup API
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(str(backup_path))

        with dest:
            source.backup(dest)

        source.close()
        dest.close()

        logger.info(f"Database backed up to: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"Failed to backup database: {e}")
        raise


def migrate_summaries(conn: sqlite3.Connection) -> int:
    """Update existing summaries to set processing_type='legacy'."""
    cursor = conn.cursor()

    try:
        # Count existing summaries
        cursor.execute("SELECT COUNT(*) FROM summaries WHERE processing_type IS NULL")
        count = cursor.fetchone()[0]

        if count == 0:
            logger.info("No summaries need migration")
            return 0

        # Update summaries without processing_type
        cursor.execute(
            """
            UPDATE summaries
            SET processing_type = 'legacy'
            WHERE processing_type IS NULL
        """
        )

        conn.commit()
        logger.info(f"Migrated {count} summaries to processing_type='legacy'")
        return count

    except Exception as e:
        logger.error(f"Failed to migrate summaries: {e}")
        conn.rollback()
        raise


def prepare_moc_for_hce(conn: sqlite3.Connection) -> dict:
    """Prepare MOC data for future HCE migration."""
    cursor = conn.cursor()
    stats = {"people": 0, "tags": 0, "models": 0, "jargon": 0}

    try:
        # Count MOC extractions
        cursor.execute("SELECT COUNT(*) FROM moc_extractions")
        total_mocs = cursor.fetchone()[0]

        if total_mocs == 0:
            logger.info("No MOC data to prepare")
            return stats

        # Analyze MOC data structure
        cursor.execute(
            """
            SELECT
                COUNT(CASE WHEN people_json IS NOT NULL THEN 1 END) as people_count,
                COUNT(CASE WHEN tags_json IS NOT NULL THEN 1 END) as tags_count,
                COUNT(CASE WHEN mental_models_json IS NOT NULL THEN 1 END) as models_count,
                COUNT(CASE WHEN jargon_json IS NOT NULL THEN 1 END) as jargon_count
            FROM moc_extractions
        """
        )

        result = cursor.fetchone()
        stats["people"] = result[0]
        stats["tags"] = result[1]
        stats["models"] = result[2]
        stats["jargon"] = result[3]

        logger.info(f"MOC data analysis: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Failed to analyze MOC data: {e}")
        raise


def create_migration_report(db_path: str, backup_path: Path, results: dict) -> None:
    """Create a migration report file."""
    report_path = Path(
        f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    report = {
        "migration_date": datetime.now().isoformat(),
        "database_path": db_path,
        "backup_path": str(backup_path),
        "results": results,
        "status": "success",
    }

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Migration report saved to: {report_path}")


def main():
    """Run the legacy data migration."""
    # Get database path
    db_path = sys.argv[1] if len(sys.argv) > 1 else "knowledge_system.db"

    if not Path(db_path).exists():
        logger.error(f"Database not found: {db_path}")
        return 1

    logger.info(f"Starting legacy data migration for: {db_path}")

    try:
        # Create backup
        backup_path = backup_database(db_path)

        # Connect to database
        conn = sqlite3.connect(db_path)

        results = {"summaries_migrated": 0, "moc_stats": {}}

        # Migrate summaries
        results["summaries_migrated"] = migrate_summaries(conn)

        # Analyze MOC data
        results["moc_stats"] = prepare_moc_for_hce(conn)

        # Close connection
        conn.close()

        # Create report
        create_migration_report(db_path, backup_path, results)

        logger.info("Legacy data migration completed successfully!")
        return 0

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
