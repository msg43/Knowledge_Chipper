#!/usr/bin/env python3
"""
Apply Minimal Extraction Schema Migration (Migration 100)

This script applies the migration to convert Knowledge_Chipper's database
to a minimal extraction-only schema (removing web-canonical tables).

Usage:
    python scripts/apply_minimal_schema_migration.py
    python scripts/apply_minimal_schema_migration.py --dry-run
"""

import argparse
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


def apply_migration(db_path: Path, dry_run: bool = False):
    """Apply the migration SQL."""
    migration_file = Path(__file__).parent.parent / "src" / "knowledge_system" / "database" / "migrations" / "100_minimal_extraction_schema.sql"
    
    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        return False
    
    logger.info(f"Reading migration from: {migration_file}")
    migration_sql = migration_file.read_text()
    
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info(f"Would apply migration to: {db_path}")
        logger.info(f"Migration size: {len(migration_sql)} characters")
        return True
    
    try:
        logger.info(f"Applying migration to: {db_path}")
        
        # Backup database first
        backup_path = db_path.with_suffix('.db.backup')
        if db_path.exists():
            import shutil
            shutil.copy2(db_path, backup_path)
            logger.info(f"✅ Backup created: {backup_path}")
        
        # Connect and apply migration
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Execute migration (split by statement for better error handling)
        statements = []
        current_statement = []
        
        for line in migration_sql.split('\n'):
            stripped = line.strip()
            
            # Skip comments and empty lines
            if not stripped or stripped.startswith('--'):
                continue
            
            current_statement.append(line)
            
            # Execute when we hit a semicolon
            if stripped.endswith(';'):
                statement = '\n'.join(current_statement)
                statements.append(statement)
                current_statement = []
        
        # Execute all statements
        success_count = 0
        for i, statement in enumerate(statements, 1):
            try:
                cursor.execute(statement)
                
                # Try to fetch result if it's a SELECT
                if statement.strip().upper().startswith('SELECT'):
                    result = cursor.fetchone()
                    if result:
                        # Log the result
                        row_dict = dict(result)
                        for key, value in row_dict.items():
                            if 'status' in key.lower() or 'summary' in key.lower():
                                logger.info(f"  {value}")
                
                success_count += 1
            except sqlite3.Error as e:
                logger.warning(f"Statement {i} error (may be expected): {e}")
                # Continue - some errors are expected (like DROP TABLE IF NOT EXISTS on non-existent tables)
        
        conn.commit()
        logger.info(f"\n✅ Migration complete! {success_count}/{len(statements)} statements executed")
        
        # Verify new tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"\n📋 Current tables ({len(tables)}):")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            logger.info(f"  - {table}: {count} rows")
        
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Apply minimal extraction schema migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--database", type=Path, help="Override database path")
    args = parser.parse_args()
    
    db_path = args.database if args.database else get_database_path()
    
    logger.info("=" * 80)
    logger.info("Knowledge_Chipper Minimal Extraction Schema Migration (100)")
    logger.info("=" * 80)
    logger.info(f"Database: {db_path}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY'}")
    logger.info("")
    
    if not db_path.exists() and not args.dry_run:
        logger.warning(f"Database does not exist yet: {db_path}")
        logger.info("Creating new database...")
        db_path.parent.mkdir(parents=True, exist_ok=True)
    
    success = apply_migration(db_path, dry_run=args.dry_run)
    
    if success:
        logger.info("\n✅ SUCCESS!")
        sys.exit(0)
    else:
        logger.error("\n❌ FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()

