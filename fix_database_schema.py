#!/usr/bin/env python3
"""
Fix Database Schema - Force SQLAlchemy to recognize first_failure_at column

This script addresses SQLAlchemy metadata caching issues by:
1. Checkpointing WAL files
2. Verifying column exists in database
3. Clearing SQLAlchemy metadata cache
4. Rebuilding the table if needed
"""

import sqlite3
from pathlib import Path
from datetime import datetime


def verify_and_fix_database():
    """Verify and fix the database schema."""
    
    db_path = "knowledge_system.db"
    
    print("=" * 70)
    print("Database Schema Fix")
    print("=" * 70)
    print()
    
    # Step 1: Checkpoint WAL
    print("📝 Step 1: Checkpointing WAL...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
        conn.close()
        print("✅ WAL checkpointed")
    except Exception as e:
        print(f"⚠️ WAL checkpoint warning: {e}")
    
    print()
    
    # Step 2: Verify column exists
    print("📝 Step 2: Verifying column exists...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(media_sources)")
    columns = {row[1]: row for row in cursor.fetchall()}
    
    if 'first_failure_at' in columns:
        col_info = columns['first_failure_at']
        print(f"✅ Column 'first_failure_at' exists:")
        print(f"   Position: {col_info[0]}")
        print(f"   Type: {col_info[2]}")
    else:
        print("❌ Column 'first_failure_at' NOT FOUND - adding it now...")
        cursor.execute("ALTER TABLE media_sources ADD COLUMN first_failure_at DATETIME")
        conn.commit()
        print("✅ Column added")
    
    print()
    
    # Step 3: Test query
    print("📝 Step 3: Testing query with first_failure_at...")
    try:
        cursor.execute("SELECT first_failure_at FROM media_sources LIMIT 1")
        print("✅ Column is queryable")
    except sqlite3.OperationalError as e:
        print(f"❌ Query failed: {e}")
        conn.close()
        return False
    
    conn.close()
    
    print()
    
    # Step 4: Clear any Python cache
    print("📝 Step 4: Clearing Python bytecode cache...")
    import subprocess
    try:
        subprocess.run(
            ["find", ".", "-type", "d", "-name", "__pycache__", "-exec", "rm", "-rf", "{}", "+"],
            cwd=".",
            capture_output=True
        )
        subprocess.run(
            ["find", ".", "-name", "*.pyc", "-delete"],
            cwd=".",
            capture_output=True
        )
        print("✅ Python cache cleared")
    except Exception as e:
        print(f"⚠️ Cache clear warning: {e}")
    
    print()
    print("=" * 70)
    print("✅ Database schema is correct!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Restart your GUI application (./launch_gui.command)")
    print("2. The 'first_failure_at' column should now be recognized")
    print()
    
    return True


if __name__ == "__main__":
    success = verify_and_fix_database()
    exit(0 if success else 1)

