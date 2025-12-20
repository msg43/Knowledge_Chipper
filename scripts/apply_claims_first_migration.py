#!/usr/bin/env python3
"""
Apply Claims-First Architecture Migration

This script applies the database schema changes needed to support
the claims-first pipeline architecture.

Usage:
    python scripts/apply_claims_first_migration.py
    python scripts/apply_claims_first_migration.py --dry-run
    python scripts/apply_claims_first_migration.py --database /path/to/db
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def get_default_database_path() -> Path:
    """Get the default database path."""
    # Try standard locations
    locations = [
        Path(__file__).parent.parent / "data" / "knowledge_system.db",
        Path(__file__).parent.parent / "knowledge_system.db",
        Path.home() / ".knowledge_chipper" / "knowledge_system.db",
    ]
    
    for loc in locations:
        if loc.exists():
            return loc
    
    # Return first location for creation
    return locations[0]


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    """Check if a table exists."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def apply_migration(db_path: Path, dry_run: bool = False) -> bool:
    """
    Apply the claims-first migration to the database.
    
    Args:
        db_path: Path to the SQLite database
        dry_run: If True, only show what would be done
    
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Applying claims-first migration to: {db_path}")
    
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        changes_made = []
        
        # 1. Add columns to claims table
        claims_columns = [
            ("timestamp_precision", "TEXT DEFAULT 'word'"),
            ("transcript_source", "TEXT DEFAULT 'whisper'"),
            ("speaker_attribution_confidence", "REAL"),
        ]
        
        for col_name, col_def in claims_columns:
            if not column_exists(cursor, "claims", col_name):
                sql = f"ALTER TABLE claims ADD COLUMN {col_name} {col_def}"
                changes_made.append(f"Add column claims.{col_name}")
                if not dry_run:
                    cursor.execute(sql)
                    logger.info(f"✅ Added claims.{col_name}")
            else:
                logger.info(f"⏭️  Column claims.{col_name} already exists")
        
        # 2. Add columns to media_sources table
        media_columns = [
            ("transcript_source", "TEXT"),
            ("transcript_quality_score", "REAL"),
            ("used_claims_first_pipeline", "BOOLEAN DEFAULT FALSE"),
        ]
        
        for col_name, col_def in media_columns:
            if not column_exists(cursor, "media_sources", col_name):
                sql = f"ALTER TABLE media_sources ADD COLUMN {col_name} {col_def}"
                changes_made.append(f"Add column media_sources.{col_name}")
                if not dry_run:
                    cursor.execute(sql)
                    logger.info(f"✅ Added media_sources.{col_name}")
            else:
                logger.info(f"⏭️  Column media_sources.{col_name} already exists")
        
        # 3. Create candidate_claims table
        if not table_exists(cursor, "candidate_claims"):
            sql = """
            CREATE TABLE candidate_claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id TEXT NOT NULL,
                source_id TEXT,
                claim_text TEXT NOT NULL,
                evidence_quote TEXT,
                timestamp_start REAL,
                timestamp_end REAL,
                timestamp_precision TEXT DEFAULT 'segment',
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                miner_model TEXT,
                chunk_id TEXT,
                accepted BOOLEAN,
                rejection_reason TEXT,
                dimensions JSON,
                importance REAL,
                tier TEXT,
                reasoning TEXT,
                accepted_claim_id INTEGER,
                FOREIGN KEY (source_id) REFERENCES media_sources(source_id)
            )
            """
            changes_made.append("Create table candidate_claims")
            if not dry_run:
                cursor.execute(sql)
                logger.info("✅ Created candidate_claims table")
                
                # Create indexes
                cursor.execute(
                    "CREATE INDEX idx_candidate_claims_episode ON candidate_claims(episode_id)"
                )
                cursor.execute(
                    "CREATE INDEX idx_candidate_claims_source ON candidate_claims(source_id)"
                )
                cursor.execute(
                    "CREATE INDEX idx_candidate_claims_accepted ON candidate_claims(accepted)"
                )
                cursor.execute(
                    "CREATE INDEX idx_candidate_claims_importance ON candidate_claims(importance)"
                )
                logger.info("✅ Created candidate_claims indexes")
        else:
            logger.info("⏭️  Table candidate_claims already exists")
        
        # 4. Create claims_first_processing_log table
        if not table_exists(cursor, "claims_first_processing_log"):
            sql = """
            CREATE TABLE claims_first_processing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                transcript_source TEXT,
                transcript_quality_score REAL,
                transcript_word_count INTEGER,
                candidates_extracted INTEGER,
                candidates_accepted INTEGER,
                acceptance_rate REAL,
                claims_attributed INTEGER,
                attribution_avg_confidence REAL,
                transcript_time REAL,
                extraction_time REAL,
                evaluation_time REAL,
                timestamp_matching_time REAL,
                attribution_time REAL,
                total_time REAL,
                miner_model TEXT,
                evaluator_model TEXT,
                attribution_model TEXT,
                config JSON,
                errors JSON,
                FOREIGN KEY (source_id) REFERENCES media_sources(source_id)
            )
            """
            changes_made.append("Create table claims_first_processing_log")
            if not dry_run:
                cursor.execute(sql)
                logger.info("✅ Created claims_first_processing_log table")
                
                # Create indexes
                cursor.execute(
                    "CREATE INDEX idx_claims_first_log_source ON claims_first_processing_log(source_id)"
                )
                cursor.execute(
                    "CREATE INDEX idx_claims_first_log_started ON claims_first_processing_log(started_at)"
                )
                logger.info("✅ Created claims_first_processing_log indexes")
        else:
            logger.info("⏭️  Table claims_first_processing_log already exists")
        
        # Commit changes
        if not dry_run:
            conn.commit()
            logger.info(f"✅ Migration complete: {len(changes_made)} changes applied")
        else:
            logger.info(f"🔍 Dry run: would apply {len(changes_made)} changes:")
            for change in changes_made:
                logger.info(f"   - {change}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Apply claims-first architecture database migration"
    )
    parser.add_argument(
        "--database", "-d",
        type=Path,
        default=None,
        help="Path to SQLite database (default: auto-detect)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    db_path = args.database or get_default_database_path()
    
    success = apply_migration(db_path, dry_run=args.dry_run)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

