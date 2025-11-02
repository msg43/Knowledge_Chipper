#!/usr/bin/env python3
"""
Add subtitle column to media_sources table (standalone version).

This migration adds the missing 'subtitle' column that was added to the
MediaSource model during ID unification but not present in existing databases.
"""

import sqlite3
from pathlib import Path


def add_subtitle_column(db_path: str = "data/knowledge_system.db") -> None:
    """
    Add subtitle column to media_sources table if it doesn't exist.

    Args:
        db_path: Path to the SQLite database
    """
    project_root = Path(__file__).parent.parent
    db_file = project_root / db_path

    if not db_file.exists():
        print(f"Database does not exist yet: {db_file}")
        print("No migration needed - database will be created with correct schema")
        return

    print(f"Checking database schema: {db_file}")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    try:
        # Check if media_sources table exists
        cursor.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='media_sources'
            """
        )
        if not cursor.fetchone():
            print("media_sources table does not exist yet - no migration needed")
            return

        # Check if subtitle column exists
        cursor.execute("PRAGMA table_info(media_sources)")
        columns = [row[1] for row in cursor.fetchall()]

        if "subtitle" in columns:
            print("✅ subtitle column already exists - no migration needed")
            return

        # Add the column
        print("Adding subtitle column to media_sources table...")
        cursor.execute("ALTER TABLE media_sources ADD COLUMN subtitle TEXT")
        conn.commit()
        print("✅ Successfully added subtitle column")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 70)
    print("Adding subtitle column to media_sources table")
    print("=" * 70)

    try:
        add_subtitle_column()
        print("=" * 70)
        print("✅ Migration completed successfully!")
        print("=" * 70)
    except Exception as e:
        print("=" * 70)
        print(f"❌ Migration failed: {e}")
        print("=" * 70)
        exit(1)

