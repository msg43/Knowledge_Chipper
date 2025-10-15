#!/usr/bin/env python3
"""
Migration script to update jargon table schema.

Changes:
- Rename jargon_id to term_id
- Add category column
"""

import sqlite3
import sys
from pathlib import Path


def migrate_jargon_table(db_path: str):
    """Migrate jargon table to new schema."""
    print(f"Migrating jargon table in {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if migration is needed
        cursor.execute("PRAGMA table_info(jargon)")
        columns = {row[1]: row for row in cursor.fetchall()}
        
        if 'term_id' in columns:
            print("✓ Jargon table already migrated (has term_id column)")
            return
        
        if 'jargon_id' not in columns:
            print("✓ Jargon table doesn't exist or has unexpected schema")
            return
        
        print("Migrating jargon table...")
        
        # Create new table with correct schema
        cursor.execute("""
            CREATE TABLE jargon_new (
                episode_id VARCHAR NOT NULL,
                term_id VARCHAR NOT NULL,
                term VARCHAR NOT NULL,
                definition TEXT,
                category VARCHAR,
                first_mention_ts VARCHAR,
                created_at DATETIME,
                updated_at DATETIME,
                PRIMARY KEY (episode_id, term_id),
                FOREIGN KEY (episode_id) REFERENCES episodes(episode_id)
            )
        """)
        
        # Copy data from old table to new table
        cursor.execute("""
            INSERT INTO jargon_new (
                episode_id, term_id, term, definition, category,
                first_mention_ts, created_at, updated_at
            )
            SELECT 
                episode_id, jargon_id, term, definition, NULL,
                first_mention_ts, created_at, updated_at
            FROM jargon
        """)
        
        # Drop old table
        cursor.execute("DROP TABLE jargon")
        
        # Rename new table
        cursor.execute("ALTER TABLE jargon_new RENAME TO jargon")
        
        conn.commit()
        print("✓ Jargon table migrated successfully")
        
        # Verify migration
        cursor.execute("PRAGMA table_info(jargon)")
        new_columns = [row[1] for row in cursor.fetchall()]
        print(f"  New columns: {new_columns}")
        
        cursor.execute("SELECT COUNT(*) FROM jargon")
        count = cursor.fetchone()[0]
        print(f"  Migrated {count} jargon entries")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # Default to production database
    default_db = Path.home() / "Library" / "Application Support" / "KnowledgeChipper" / "knowledge_system.db"
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(default_db)
    
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    migrate_jargon_table(db_path)

