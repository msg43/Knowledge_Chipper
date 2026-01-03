#!/usr/bin/env python3
"""
Fix media_sources Upload Tracking Columns

Adds the missing upload_status, upload_timestamp, and upload_error columns
to the media_sources table that are needed for tracking uploads to Supabase.
"""

import sqlite3
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.logger import get_logger
from knowledge_system.utils.macos_paths import get_application_support_dir

logger = get_logger(__name__)


def get_database_path() -> Path:
    """Get the default Knowledge_Chipper database path."""
    return get_application_support_dir() / "knowledge_system.db"


def fix_upload_columns(db_path: Path):
    """Add missing upload tracking columns to media_sources."""
    
    logger.info("=" * 80)
    logger.info("Fix media_sources Upload Tracking Columns")
    logger.info("=" * 80)
    logger.info(f"Database: {db_path}")
    logger.info("")
    
    if not db_path.exists():
        logger.error(f"❌ Database does not exist: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current columns
        cursor.execute("PRAGMA table_info(media_sources)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        logger.info(f"Current media_sources columns: {len(existing_columns)}")
        
        # Add missing columns
        columns_to_add = []
        
        if 'upload_status' not in existing_columns:
            columns_to_add.append(("upload_status", "TEXT DEFAULT 'pending'"))
        
        if 'upload_timestamp' not in existing_columns:
            columns_to_add.append(("upload_timestamp", "DATETIME"))
        
        if 'upload_error' not in existing_columns:
            columns_to_add.append(("upload_error", "TEXT"))
        
        if not columns_to_add:
            logger.info("✅ All upload tracking columns already exist!")
            conn.close()
            return True
        
        logger.info(f"Adding {len(columns_to_add)} missing columns...")
        
        for col_name, col_def in columns_to_add:
            sql = f"ALTER TABLE media_sources ADD COLUMN {col_name} {col_def}"
            logger.info(f"  Adding: {col_name}")
            cursor.execute(sql)
        
        conn.commit()
        
        # Verify
        cursor.execute("PRAGMA table_info(media_sources)")
        new_columns = [row[1] for row in cursor.fetchall()]
        
        logger.info("")
        logger.info(f"✅ Added {len(columns_to_add)} columns successfully")
        logger.info(f"Total columns now: {len(new_columns)}")
        
        # Verify all required columns exist
        required = ['upload_status', 'upload_timestamp', 'upload_error']
        missing = [col for col in required if col not in new_columns]
        
        if missing:
            logger.error(f"❌ Still missing: {', '.join(missing)}")
            conn.close()
            return False
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ SUCCESS! Upload tracking columns ready")
        logger.info("=" * 80)
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    db_path = get_database_path()
    success = fix_upload_columns(db_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

