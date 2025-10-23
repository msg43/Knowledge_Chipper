#!/usr/bin/env python3
"""
Database Migration: Add first_failure_at column to media_sources table

This migration adds the first_failure_at column to support time-based retry logic
for YouTube metadata extraction improvements.

Usage:
    python migrate_add_first_failure_at.py
"""

import sqlite3
from pathlib import Path
from datetime import datetime


def migrate_database(db_path: str = "knowledge_system.db"):
    """Add first_failure_at column to media_sources table."""
    
    db_file = Path(db_path)
    
    if not db_file.exists():
        print(f"❌ Database file not found: {db_path}")
        print("   No migration needed - column will be created when database is first used.")
        return
    
    print(f"🔍 Checking database: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(media_sources)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'first_failure_at' in columns:
            print("✅ Column 'first_failure_at' already exists - no migration needed")
            conn.close()
            return
        
        print("📝 Adding 'first_failure_at' column to media_sources table...")
        
        # Add the new column
        cursor.execute("""
            ALTER TABLE media_sources 
            ADD COLUMN first_failure_at DATETIME
        """)
        
        # Commit changes
        conn.commit()
        
        # Verify column was added
        cursor.execute("PRAGMA table_info(media_sources)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'first_failure_at' in columns:
            print("✅ Successfully added 'first_failure_at' column")
            print(f"   Migration completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("❌ Failed to add column - please check database manually")
        
        conn.close()
        
    except sqlite3.OperationalError as e:
        print(f"❌ Database error: {e}")
        print("   This might occur if the table structure is locked or incompatible")
        return
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return


if __name__ == "__main__":
    print("=" * 70)
    print("Database Migration: Add first_failure_at Column")
    print("=" * 70)
    print()
    
    # Migrate the main database
    migrate_database("knowledge_system.db")
    
    print()
    print("=" * 70)
    print("Migration Complete")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. ✅ Database schema updated")
    print("2. 🔄 Restart your application to use the new column")
    print("3. 📊 Test YouTube downloads to verify retry logic works")
    print()

