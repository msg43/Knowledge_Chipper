#!/usr/bin/env python3
"""
Migration script to add context_quote columns to people, concepts, and jargon tables.

This script adds the context_quote field to support storing contextual quotes
from the mining process.
"""

import sqlite3
import sys
from pathlib import Path


def migrate_add_context_quotes(db_path: str) -> None:
    """
    Add context_quote columns to people, concepts, and jargon tables.
    Also adds missing episodes columns for model compatibility.

    Args:
        db_path: Path to the SQLite database file
    """
    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Fix episodes table to match model
        cursor.execute("PRAGMA table_info(episodes)")
        episodes_columns = [row[1] for row in cursor.fetchall()]

        if len(episodes_columns) > 0:
            if "subtitle" not in episodes_columns:
                print("Adding subtitle column to episodes table...")
                cursor.execute("ALTER TABLE episodes ADD COLUMN subtitle TEXT")
                print("✓ Added subtitle to episodes")

            if "description" not in episodes_columns:
                print("Adding description column to episodes table...")
                cursor.execute("ALTER TABLE episodes ADD COLUMN description TEXT")
                print("✓ Added description to episodes")

            if "processed_at" not in episodes_columns:
                print("Adding processed_at column to episodes table...")
                cursor.execute("ALTER TABLE episodes ADD COLUMN processed_at DATETIME")
                print("✓ Added processed_at to episodes")

        # Check if people table exists and if context_quote column is missing
        cursor.execute("PRAGMA table_info(people)")
        people_columns = [row[1] for row in cursor.fetchall()]

        if "context_quote" not in people_columns and len(people_columns) > 0:
            print("Adding context_quote column to people table...")
            cursor.execute("ALTER TABLE people ADD COLUMN context_quote TEXT")
            print("✓ Added context_quote to people")
        elif len(people_columns) > 0:
            print("✓ people.context_quote already exists")

        # Check if concepts table exists and if context_quote column is missing
        cursor.execute("PRAGMA table_info(concepts)")
        concepts_columns = [row[1] for row in cursor.fetchall()]

        if "context_quote" not in concepts_columns and len(concepts_columns) > 0:
            print("Adding context_quote column to concepts table...")
            cursor.execute("ALTER TABLE concepts ADD COLUMN context_quote TEXT")
            print("✓ Added context_quote to concepts")
        elif len(concepts_columns) > 0:
            print("✓ concepts.context_quote already exists")

        # Check if jargon table exists and if context_quote column is missing
        cursor.execute("PRAGMA table_info(jargon)")
        jargon_columns = [row[1] for row in cursor.fetchall()]

        if "context_quote" not in jargon_columns and len(jargon_columns) > 0:
            print("Adding context_quote column to jargon table...")
            cursor.execute("ALTER TABLE jargon ADD COLUMN context_quote TEXT")
            print("✓ Added context_quote to jargon")
        elif len(jargon_columns) > 0:
            print("✓ jargon.context_quote already exists")

        conn.commit()
        print("\n✅ Migration completed successfully!")

    except sqlite3.Error as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    # Default to the main database in the project root
    default_db = Path(__file__).parent.parent / "knowledge_system.db"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = str(default_db)

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    migrate_add_context_quotes(db_path)
