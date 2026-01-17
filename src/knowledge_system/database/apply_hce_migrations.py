#!/usr/bin/env python3
"""
Apply HCE database migrations for Knowledge System.

This script applies the HCE schema and compatibility views to the existing database.
"""

import sqlite3
import sys
from pathlib import Path

from ..logger import get_logger

logger = get_logger(__name__)


def apply_migration(db_path: str, migration_file: Path) -> bool:
    """Apply a single migration file to the database."""
    try:
        # Read migration SQL
        with open(migration_file) as f:
            migration_sql = f.read()

        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.executescript(migration_sql)
        conn.commit()
        conn.close()

        logger.info(f"Successfully applied migration: {migration_file.name}")
        return True

    except Exception as e:
        logger.error(f"Failed to apply migration {migration_file.name}: {e}")
        return False


def main():
    """Apply HCE migrations to the database."""
    # Get database path from settings or use default
    db_path = "knowledge_system.db"

    # Get migrations directory
    migrations_dir = Path(__file__).parent / "migrations"

    # Apply migrations in order
    migrations = [
        "2025_08_18_hce.sql",
        "2025_08_18_hce_compat.sql",
        "2025_08_18_hce_columns.sql",
        "2025_12_20_claims_first_support.sql",  # Claims-first architecture support
        "2026_01_feedback_system.sql",  # Dynamic Learning System feedback tables
    ]

    success = True
    for migration_name in migrations:
        migration_file = migrations_dir / migration_name
        if not migration_file.exists():
            logger.error(f"Migration file not found: {migration_file}")
            success = False
            continue

        if not apply_migration(db_path, migration_file):
            success = False
            break

    if success:
        logger.info("All HCE migrations applied successfully!")
        return 0
    else:
        logger.error("Failed to apply all migrations")
        return 1


if __name__ == "__main__":
    sys.exit(main())
