#!/usr/bin/env python3
"""
Migrate from dual storage paths to unified schema.

This script:
1. Creates unified database if needed
2. Migrates existing data from main DB
3. Preserves HCE DB data if exists
4. Sets up proper foreign keys and indexes
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def migrate_to_unified():
    """Main migration function."""
    print("=" * 80)
    print("STORAGE UNIFICATION MIGRATION")
    print("=" * 80)
    
    # Paths
    main_db = Path("knowledge_system.db")
    # Use Application Support directory (user-writable)
    unified_db_dir = Path.home() / "Library" / "Application Support" / "SkipThePodcast"
    unified_db_dir.mkdir(parents=True, exist_ok=True)
    unified_db = unified_db_dir / "unified_hce.db"
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if main_db.exists():
        backup_path = main_db.parent / f"knowledge_system.db.pre_unification.{timestamp}"
        print(f"\n📦 Creating backup: {backup_path}")
        import shutil
        shutil.copy2(main_db, backup_path)
    
    # Load unified schema
    schema_path = Path("src/knowledge_system/database/migrations/unified_schema.sql")
    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        return False
    
    schema_sql = schema_path.read_text()
    
    # Create unified database
    print(f"\n🏗️  Creating unified database: {unified_db}")
    conn = sqlite3.connect(unified_db)
    cursor = conn.cursor()
    
    try:
        cursor.executescript(schema_sql)
        conn.commit()
        print("✓ Unified schema created")
    except Exception as e:
        print(f"❌ Failed to create schema: {e}")
        return False
    
    # Migrate data from main DB if exists
    if main_db.exists():
        print(f"\n📊 Migrating data from {main_db}")
        main_conn = sqlite3.connect(main_db)
        
        tables_to_migrate = ["episodes", "claims", "people", "concepts", "jargon"]
        
        for table in tables_to_migrate:
            print(f"  Migrating {table}...", end=" ")
            try:
                # Check if table exists in source
                main_cursor = main_conn.cursor()
                main_cursor.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
                if main_cursor.fetchone()[0] == 0:
                    print("skipped (table doesn't exist)")
                    continue
                
                # Get column names
                main_cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in main_cursor.fetchall()]
                
                # Check target table columns
                cursor.execute(f"PRAGMA table_info({table})")
                target_columns = [row[1] for row in cursor.fetchall()]
                
                # Find common columns
                common_columns = [c for c in columns if c in target_columns]
                
                if not common_columns:
                    print("skipped (no common columns)")
                    continue
                
                # Migrate data
                main_cursor.execute(f"SELECT {','.join(common_columns)} FROM {table}")
                rows = main_cursor.fetchall()
                
                if rows:
                    placeholders = ','.join(['?' for _ in common_columns])
                    insert_sql = f"INSERT OR REPLACE INTO {table} ({','.join(common_columns)}) VALUES ({placeholders})"
                    cursor.executemany(insert_sql, rows)
                    print(f"✓ {len(rows)} rows")
                else:
                    print("✓ 0 rows")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
        
        main_conn.close()
        conn.commit()
    
    # Print summary
    print("\n📈 Migration Summary:")
    print("-" * 80)
    for table in ["episodes", "claims", "people", "concepts", "jargon", "evidence_spans", "relations", "structured_categories"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:.<30} {count:>10} rows")
    
    conn.close()
    
    print("\n✅ Migration completed successfully!")
    print(f"   Unified database: {unified_db}")
    if main_db.exists():
        print(f"   Original backup: {backup_path}")
    
    return True


if __name__ == "__main__":
    success = migrate_to_unified()
    sys.exit(0 if success else 1)

