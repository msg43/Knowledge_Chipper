#!/usr/bin/env python3
"""
Verify SQLite Schema (Migration 100)

Checks that Knowledge_Chipper's SQLite database has the correct
minimal extraction schema with all expected tables and columns.
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


EXPECTED_SCHEMA = {
    "media_sources": [
        "source_id", "source_type", "title", "url", "description",
        "uploader", "author", "organization", "duration_seconds", "language",
        "audio_file_path", "audio_downloaded", "audio_file_size_bytes",
        "status", "processed_at", "upload_status", "upload_timestamp", 
        "upload_error", "created_at", "updated_at"
    ],
    "segments": [
        "segment_id", "source_id", "speaker", "t0", "t1", "text", "seq", "created_at"
    ],
    "claims": [
        "claim_id", "source_id", "canonical", "original_text", "claim_type",
        "domain", "tier", "scores_json", "temporality_score",
        "temporality_confidence", "temporality_rationale", "first_mention_ts",
        "speaker", "upload_status", "upload_timestamp", "upload_error",
        "last_uploaded_at", "created_at", "updated_at"
    ],
    "evidence_spans": [
        "evidence_id", "claim_id", "seq", "segment_id", "t0", "t1",
        "quote", "context_t0", "context_t1", "context_text", "context_type", "created_at"
    ],
    "people": [
        "person_id", "source_id", "name", "normalized_name", "entity_type",
        "confidence", "surface", "t0", "t1", "upload_status",
        "upload_timestamp", "upload_error", "created_at"
    ],
    "jargon": [
        "jargon_id", "source_id", "term", "definition", "category",
        "upload_status", "upload_timestamp", "upload_error", "created_at"
    ],
    "concepts": [
        "concept_id", "source_id", "name", "definition", "description",
        "upload_status", "upload_timestamp", "upload_error", "created_at"
    ],
    "claim_jargon": [
        "claim_id", "jargon_id", "context", "first_mention_ts", "created_at"
    ],
    "claim_people": [
        "claim_id", "person_id", "role", "mention_context", "first_mention_ts", "created_at"
    ],
    "claim_concepts": [
        "claim_id", "concept_id", "context", "first_mention_ts", "created_at"
    ],
}

EXPECTED_PRIMARY_KEYS = {
    "media_sources": "source_id",
    "segments": "segment_id",
    "claims": "claim_id",
    "evidence_spans": "evidence_id",  # AUTOINCREMENT
    "people": "person_id",
    "jargon": "jargon_id",
    "concepts": "concept_id",
    "claim_jargon": ["claim_id", "jargon_id"],  # Composite
    "claim_people": ["claim_id", "person_id"],  # Composite
    "claim_concepts": ["claim_id", "concept_id"],  # Composite
}


def verify_schema(db_path: Path):
    """Verify the database schema matches expectations."""
    
    logger.info("=" * 80)
    logger.info("SQLite Schema Verification (Migration 100)")
    logger.info("=" * 80)
    logger.info(f"Database: {db_path}")
    logger.info("")
    
    if not db_path.exists():
        logger.error(f"❌ Database does not exist: {db_path}")
        logger.error("Run: python scripts/apply_minimal_schema_migration.py")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        all_tables = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"Found {len(all_tables)} total tables")
        
        # Check expected tables exist
        missing_tables = []
        for table_name in EXPECTED_SCHEMA.keys():
            if table_name not in all_tables:
                missing_tables.append(table_name)
        
        if missing_tables:
            logger.error(f"❌ Missing expected tables: {', '.join(missing_tables)}")
            return False
        
        logger.info(f"✅ All 10 expected tables exist\n")
        
        # Verify each table's schema
        all_passed = True
        for table_name, expected_columns in EXPECTED_SCHEMA.items():
            logger.info(f"Checking table: {table_name}")
            
            # Get actual columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            actual_columns = [row[1] for row in cursor.fetchall()]
            
            # Check columns
            missing_cols = set(expected_columns) - set(actual_columns)
            extra_cols = set(actual_columns) - set(expected_columns)
            
            if missing_cols:
                logger.error(f"  ❌ Missing columns: {', '.join(missing_cols)}")
                all_passed = False
            
            if extra_cols:
                logger.warning(f"  ⚠️  Extra columns: {', '.join(extra_cols)}")
            
            if not missing_cols and not extra_cols:
                logger.info(f"  ✅ Schema matches ({len(actual_columns)} columns)")
            elif not missing_cols:
                logger.info(f"  ✅ All expected columns present ({len(expected_columns)} required)")
            
            # Check primary key
            cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            create_sql = cursor.fetchone()[0]
            
            expected_pk = EXPECTED_PRIMARY_KEYS[table_name]
            if isinstance(expected_pk, list):
                pk_check = all(f"{col}" in create_sql for col in expected_pk)
                pk_desc = f"({', '.join(expected_pk)})"
            else:
                pk_check = f"{expected_pk} TEXT PRIMARY KEY" in create_sql or \
                          f"{expected_pk} INTEGER PRIMARY KEY" in create_sql
                pk_desc = expected_pk
            
            if pk_check:
                logger.info(f"  ✅ Primary key: {pk_desc}")
            else:
                logger.warning(f"  ⚠️  Primary key may not match: {pk_desc}")
            
            # Check row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            logger.info(f"  📊 Row count: {count}")
            logger.info("")
        
        # Check indexes
        logger.info("Checking indexes...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
        indexes = [row[0] for row in cursor.fetchall()]
        
        expected_indexes = [
            'idx_segments_source_id',
            'idx_segments_seq',
            'idx_claims_source_id',
            'idx_claims_upload_status',
            'idx_claims_tier',
            'idx_evidence_spans_claim_id',
            'idx_people_source_id',
            'idx_people_upload_status',
            'idx_people_normalized_name',
            'idx_jargon_source_id',
            'idx_jargon_upload_status',
            'idx_jargon_term',
            'idx_concepts_source_id',
            'idx_concepts_upload_status',
            'idx_concepts_name',
            'idx_claim_jargon_claim_id',
            'idx_claim_jargon_jargon_id',
            'idx_claim_people_claim_id',
            'idx_claim_people_person_id',
            'idx_claim_concepts_claim_id',
            'idx_claim_concepts_concept_id',
        ]
        
        found_indexes = [idx for idx in expected_indexes if idx in indexes]
        missing_indexes = [idx for idx in expected_indexes if idx not in indexes]
        
        logger.info(f"  ✅ Found {len(found_indexes)}/{len(expected_indexes)} expected indexes")
        if missing_indexes:
            logger.warning(f"  ⚠️  Missing indexes: {', '.join(missing_indexes[:5])}")
        logger.info("")
        
        conn.close()
        
        if all_passed:
            logger.info("=" * 80)
            logger.info("✅ VERIFICATION PASSED!")
            logger.info("=" * 80)
            logger.info("SQLite database has correct minimal extraction schema")
            logger.info("Ready for Knowledge_Chipper processing and uploads")
            return True
        else:
            logger.error("=" * 80)
            logger.error("❌ VERIFICATION FAILED")
            logger.error("=" * 80)
            logger.error("Some schema mismatches found (see above)")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    db_path = get_database_path()
    success = verify_schema(db_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

