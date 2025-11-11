#!/usr/bin/env python3
"""
Add domain column to claims table.

This migration adds the missing 'domain' column that was added to the
Claim model for broad field classification (e.g., 'physics', 'economics').
"""

import sqlite3
from pathlib import Path


def add_domain_column(db_path: str = None) -> None:
    """
    Add domain column to claims table if it doesn't exist.

    Args:
        db_path: Path to the SQLite database. If None, uses the default location.
    """
    if db_path is None:
        # Use the default application support location
        import sys
        from pathlib import Path

        if sys.platform == "darwin":  # macOS
            app_support = (
                Path.home() / "Library" / "Application Support" / "Knowledge Chipper"
            )
        elif sys.platform == "win32":  # Windows
            import os

            app_support = (
                Path(os.environ.get("APPDATA", Path.home())) / "Knowledge Chipper"
            )
        else:  # Linux
            app_support = Path.home() / ".local" / "share" / "Knowledge Chipper"

        db_file = app_support / "knowledge_system.db"
    else:
        db_file = Path(db_path)

    if not db_file.exists():
        print(f"Database does not exist yet: {db_file}")
        print("No migration needed - database will be created with correct schema")
        return

    print(f"Checking database schema: {db_file}")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    try:
        # Check if claims table exists
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='claims'
            """
        )
        if not cursor.fetchone():
            print("claims table does not exist yet - no migration needed")
            return

        # Check if domain column exists
        cursor.execute("PRAGMA table_info(claims)")
        columns = [row[1] for row in cursor.fetchall()]

        if "domain" in columns:
            print("✅ domain column already exists - no migration needed")
            return

        # Add the column
        print("Adding domain column to claims table...")
        cursor.execute("ALTER TABLE claims ADD COLUMN domain TEXT")
        conn.commit()
        print("✅ Successfully added domain column")
        print(
            "   This column stores broad field classification (e.g., 'physics', 'economics')"
        )

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 70)
    print("Adding domain column to claims table")
    print("=" * 70)
    add_domain_column()
    print("=" * 70)
    print("Migration complete!")
    print("=" * 70)
