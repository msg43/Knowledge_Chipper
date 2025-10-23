#!/usr/bin/env python3
"""
Migrate GUI Database: Add first_failure_at column

The GUI uses a different database location than the project directory:
- macOS: ~/Library/Application Support/Knowledge Chipper/knowledge_system.db
- Windows: %APPDATA%/Knowledge Chipper/knowledge_system.db
- Linux: ~/.knowledge_chipper/knowledge_system.db

This script migrates the CORRECT database that the GUI actually uses.
"""

import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime


def get_gui_db_path():
    """Get the database path that the GUI uses."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Knowledge Chipper" / "knowledge_system.db"
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "Knowledge Chipper" / "knowledge_system.db"
    else:
        return Path.home() / ".knowledge_chipper" / "knowledge_system.db"


def migrate_gui_database():
    """Add first_failure_at column to the GUI's database."""
    
    db_path = get_gui_db_path()
    
    print("=" * 70)
    print("GUI Database Migration: Add first_failure_at Column")
    print("=" * 70)
    print()
    print(f"📍 GUI Database Location: {db_path}")
    print()
    
    if not db_path.exists():
        print(f"❌ GUI database not found at: {db_path}")
        print("   The GUI may not have been run yet, or database is elsewhere.")
        print("   Run the GUI first to create the database, then run this migration.")
        return False
    
    print(f"✅ Found GUI database ({db_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print()
    
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
            return True
        
        print("📝 Adding 'first_failure_at' column to media_sources table...")
        
        # Add the new column
        cursor.execute("""
            ALTER TABLE media_sources 
            ADD COLUMN first_failure_at DATETIME
        """)
        
        # Commit changes
        conn.commit()
        
        # Checkpoint WAL to ensure changes are persisted
        print("📝 Checkpointing WAL...")
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
        
        # Verify column was added
        cursor.execute("PRAGMA table_info(media_sources)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'first_failure_at' in columns:
            print("✅ Successfully added 'first_failure_at' column")
            print(f"   Migration completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            print("=" * 70)
            print("✅ Migration Complete!")
            print("=" * 70)
            print()
            print("Next steps:")
            print("1. ✅ GUI database schema updated")
            print("2. 🔄 Restart your GUI (./launch_gui.command)")
            print("3. 📊 Test YouTube downloads to verify retry logic works")
            print()
            return True
        else:
            print("❌ Failed to add column - please check database manually")
            return False
        
        conn.close()
        
    except sqlite3.OperationalError as e:
        print(f"❌ Database error: {e}")
        print("   This might occur if the table structure is locked or incompatible")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = migrate_gui_database()
    exit(0 if success else 1)

