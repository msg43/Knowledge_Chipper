# Storage Unification Master Plan
## Complete Path Consolidation with Full Testing & Documentation

**Objective:** Eliminate dual storage paths, integrate UnifiedHCEPipeline into System2Orchestrator, achieve 3-8x mining speed improvement, and maintain rich data (evidence, relations, categories).

**Timeline:** 2-3 days for implementation + testing  
**Risk Level:** Medium (breaking changes, but well-isolated)  
**Expected Benefits:**
- 3-8x faster mining (parallel processing)
- Rich evidence spans with timestamps
- Claim evaluation and ranking (A/B/C tiers)
- Relations between claims
- Structured categories
- Single, maintainable code path

---

## Table of Contents
1. [Pre-Flight Checks](#1-pre-flight-checks)
2. [Phase 1: Database Preparation](#2-phase-1-database-preparation)
3. [Phase 2: Integration Implementation](#3-phase-2-integration-implementation)
4. [Phase 3: Code Cleanup](#4-phase-3-code-cleanup)
5. [Phase 4: Testing](#5-phase-4-testing)
6. [Phase 5: Documentation](#6-phase-5-documentation)
7. [Phase 6: Deployment](#7-phase-6-deployment)
8. [Rollback Plan](#8-rollback-plan)

---

## 1. Pre-Flight Checks

### 1.1 Backup Everything
```bash
# Create backup branch
git checkout -b backup/before-unification
git commit -am "Backup before storage unification"
git push origin backup/before-unification

# Backup database
cp knowledge_system.db knowledge_system.db.backup.$(date +%Y%m%d_%H%M%S)
cp ~/.skip_the_podcast/hce_pipeline.db ~/.skip_the_podcast/hce_pipeline.db.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# Create tarball of entire project
cd ..
tar -czf Knowledge_Chipper_backup_$(date +%Y%m%d_%H%M%S).tar.gz Knowledge_Chipper/
cd Knowledge_Chipper
```

### 1.2 Document Current State
```bash
# Count existing data
sqlite3 knowledge_system.db "
SELECT 
  (SELECT COUNT(*) FROM episodes) as episodes,
  (SELECT COUNT(*) FROM claims) as claims,
  (SELECT COUNT(*) FROM jargon) as jargon,
  (SELECT COUNT(*) FROM people) as people,
  (SELECT COUNT(*) FROM concepts) as concepts
" > pre_migration_counts.txt

# Test current functionality
python scripts/test_context_quotes_simple.py > pre_migration_test.txt
```

### 1.3 Create Feature Branch
```bash
git checkout -b feature/unify-storage-layer
```

---

## 2. Phase 1: Database Preparation

**Duration:** 2-4 hours  
**Goal:** Prepare unified database schema and migration tools

### 2.1 Analyze Schema Differences

**File:** `scripts/analyze_schema_differences.py`
```python
#!/usr/bin/env python3
"""Analyze differences between main DB and HCE DB schemas."""

import sqlite3
from pathlib import Path

def get_table_schema(db_path, table_name):
    """Get CREATE TABLE statement for a table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def compare_schemas():
    """Compare schemas between databases."""
    main_db = Path("knowledge_system.db")
    hce_db = Path.home() / ".skip_the_podcast" / "hce_pipeline.db"
    
    tables_to_check = ["episodes", "claims", "people", "concepts", "jargon"]
    
    print("=" * 80)
    print("SCHEMA COMPARISON")
    print("=" * 80)
    
    for table in tables_to_check:
        print(f"\n{table.upper()}:")
        print("-" * 80)
        
        main_schema = get_table_schema(main_db, table) if main_db.exists() else None
        hce_schema = get_table_schema(hce_db, table) if hce_db.exists() else None
        
        if main_schema and hce_schema:
            if main_schema == hce_schema:
                print("✓ IDENTICAL")
            else:
                print("✗ DIFFERENT")
                print(f"\nMain DB:\n{main_schema}\n")
                print(f"\nHCE DB:\n{hce_schema}\n")
        elif main_schema:
            print(f"Only in Main DB:\n{main_schema}")
        elif hce_schema:
            print(f"Only in HCE DB:\n{hce_schema}")
        else:
            print("Missing in both")

if __name__ == "__main__":
    compare_schemas()
```

**Run:**
```bash
python scripts/analyze_schema_differences.py > schema_comparison_report.txt
```

### 2.2 Create Unified Schema

**File:** `src/knowledge_system/database/migrations/unified_schema.sql`
```sql
-- Unified HCE Schema - Combines best of both worlds
-- Version: 2.0 (Unification)
-- Date: 2025-10-23

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Episodes table (unified from both schemas)
CREATE TABLE IF NOT EXISTS episodes (
  episode_id TEXT PRIMARY KEY,
  video_id TEXT,
  title TEXT NOT NULL,
  subtitle TEXT,
  description TEXT,
  recorded_at TEXT,
  inserted_at TEXT DEFAULT (datetime('now')),
  processed_at DATETIME
);

-- Claims table (from HCE schema with enhancements)
CREATE TABLE IF NOT EXISTS claims (
  episode_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  canonical TEXT NOT NULL,
  original_text TEXT,
  claim_type TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
  tier TEXT CHECK (tier IN ('A','B','C')),
  first_mention_ts TEXT,
  scores_json TEXT NOT NULL,
  
  -- Evaluation metadata
  evaluator_notes TEXT,
  
  -- Temporality analysis
  temporality_score INTEGER CHECK (temporality_score IN (1,2,3,4,5)) DEFAULT 3,
  temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1) DEFAULT 0.5,
  temporality_rationale TEXT,
  
  -- Structured categories
  structured_categories_json TEXT,
  category_relevance_scores_json TEXT,
  
  -- Upload tracking
  upload_status TEXT DEFAULT 'pending',
  upload_timestamp DATETIME,
  upload_error TEXT,
  
  -- Timestamps
  created_at DATETIME DEFAULT (datetime('now')),
  updated_at DATETIME DEFAULT (datetime('now')),
  inserted_at TEXT DEFAULT (datetime('now')),
  
  PRIMARY KEY (episode_id, claim_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Evidence spans (from HCE schema)
CREATE TABLE IF NOT EXISTS evidence_spans (
  episode_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  segment_id TEXT,
  
  -- Precise quote level
  t0 TEXT,
  t1 TEXT,
  quote TEXT,
  
  -- Extended context level
  context_t0 TEXT,
  context_t1 TEXT,
  context_text TEXT,
  context_type TEXT DEFAULT 'exact' CHECK (context_type IN ('exact', 'extended', 'segment')),
  
  PRIMARY KEY (episode_id, claim_id, seq),
  FOREIGN KEY (episode_id, claim_id) REFERENCES claims(episode_id, claim_id) ON DELETE CASCADE
);

-- Relations between claims (from HCE schema)
CREATE TABLE IF NOT EXISTS relations (
  episode_id TEXT NOT NULL,
  source_claim_id TEXT NOT NULL,
  target_claim_id TEXT NOT NULL,
  type TEXT CHECK (type IN ('supports','contradicts','depends_on','refines')),
  strength REAL CHECK (strength BETWEEN 0 AND 1),
  rationale TEXT,
  PRIMARY KEY (episode_id, source_claim_id, target_claim_id, type),
  FOREIGN KEY (episode_id, source_claim_id) REFERENCES claims(episode_id, claim_id) ON DELETE CASCADE,
  FOREIGN KEY (episode_id, target_claim_id) REFERENCES claims(episode_id, claim_id) ON DELETE CASCADE
);

-- People table (unified)
CREATE TABLE IF NOT EXISTS people (
  episode_id TEXT NOT NULL,
  person_id TEXT NOT NULL,
  mention_id TEXT,
  span_segment_id TEXT,
  t0 TEXT,
  t1 TEXT,
  
  -- Person information
  name TEXT NOT NULL,
  surface TEXT,
  normalized TEXT,
  description TEXT,
  entity_type TEXT CHECK (entity_type IN ('person','org')) DEFAULT 'person',
  external_ids_json TEXT,
  confidence REAL,
  
  -- Context
  first_mention_ts TEXT,
  context_quote TEXT,
  
  -- Timestamps
  created_at DATETIME DEFAULT (datetime('now')),
  updated_at DATETIME DEFAULT (datetime('now')),
  
  PRIMARY KEY (episode_id, person_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Concepts table (unified)
CREATE TABLE IF NOT EXISTS concepts (
  episode_id TEXT NOT NULL,
  concept_id TEXT NOT NULL,
  model_id TEXT,
  
  -- Concept information
  name TEXT NOT NULL,
  description TEXT,
  definition TEXT,
  first_mention_ts TEXT,
  
  -- Additional metadata
  aliases_json TEXT,
  evidence_json TEXT,
  context_quote TEXT,
  
  -- Timestamps
  created_at DATETIME DEFAULT (datetime('now')),
  updated_at DATETIME DEFAULT (datetime('now')),
  
  PRIMARY KEY (episode_id, concept_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Jargon table (unified)
CREATE TABLE IF NOT EXISTS jargon (
  episode_id TEXT NOT NULL,
  term_id TEXT NOT NULL,
  
  -- Jargon information
  term TEXT NOT NULL,
  definition TEXT,
  category TEXT,
  first_mention_ts TEXT,
  
  -- Additional metadata
  evidence_json TEXT,
  context_quote TEXT,
  
  -- Timestamps
  created_at DATETIME DEFAULT (datetime('now')),
  updated_at DATETIME DEFAULT (datetime('now')),
  
  PRIMARY KEY (episode_id, term_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Structured categories (from HCE schema)
CREATE TABLE IF NOT EXISTS structured_categories (
  episode_id TEXT NOT NULL,
  category_id TEXT NOT NULL,
  category_name TEXT NOT NULL,
  wikidata_qid TEXT,
  coverage_confidence REAL CHECK (coverage_confidence BETWEEN 0 AND 1) DEFAULT 0.5,
  supporting_evidence_json TEXT,
  frequency_score REAL CHECK (frequency_score BETWEEN 0 AND 1) DEFAULT 0.0,
  PRIMARY KEY (episode_id, category_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Segments table (from HCE schema)
CREATE TABLE IF NOT EXISTS segments (
  episode_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  speaker TEXT,
  t0 TEXT,
  t1 TEXT,
  text TEXT,
  topic_guess TEXT,
  PRIMARY KEY (episode_id, segment_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_claims_episode_tier ON claims(episode_id, tier);
CREATE INDEX IF NOT EXISTS idx_claims_first_mention ON claims(first_mention_ts);
CREATE INDEX IF NOT EXISTS idx_claims_temporality ON claims(temporality_score, temporality_confidence);
CREATE INDEX IF NOT EXISTS idx_evidence_spans_segment ON evidence_spans(episode_id, segment_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(type);
CREATE INDEX IF NOT EXISTS idx_people_normalized ON people(normalized);
CREATE INDEX IF NOT EXISTS idx_people_name ON people(name);
CREATE INDEX IF NOT EXISTS idx_concepts_name ON concepts(name);
CREATE INDEX IF NOT EXISTS idx_jargon_term ON jargon(term);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT DEFAULT (datetime('now')),
  description TEXT
);

INSERT OR REPLACE INTO schema_version (version, description)
VALUES (2, 'Unified schema - Storage path consolidation');
```

### 2.3 Create Migration Script

**File:** `scripts/migrate_to_unified_schema.py`

```python
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
    unified_db = Path.home() / ".skip_the_podcast" / "unified_hce.db"
    unified_db.parent.mkdir(parents=True, exist_ok=True)
    
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
    print(f"   Original backup: {backup_path if main_db.exists() else 'N/A'}")
    
    return True

if __name__ == "__main__":
    success = migrate_to_unified()
    sys.exit(0 if success else 1)
```

---

## 3. Phase 2: Integration Implementation

**Duration:** 6-8 hours  
**Goal:** Integrate UnifiedHCEPipeline into System2Orchestrator

### 3.1 Update System2Orchestrator

**File:** `src/knowledge_system/core/system2_orchestrator.py`

**Changes to make:**

#### Step 1: Add imports at top of file
```python
# Add after existing imports (around line 15)
from pathlib import Path
from ..processors.hce.config_flex import PipelineConfigFlex, StageModelConfig
from ..processors.hce.types import EpisodeBundle
from ..processors.hce.unified_pipeline import UnifiedHCEPipeline
from ..processors.hce.storage_sqlite import upsert_pipeline_outputs, open_db
```

#### Step 2: Replace `_process_mine()` method

**Location:** Lines ~391-540

**BEFORE:**
```python
async def _process_mine(
    self,
    episode_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """Process mining job with checkpoint support."""
    # ... existing sequential mining code ...
```

**AFTER - Create new file for clarity:**

**File:** `src/knowledge_system/core/system2_orchestrator_mining.py`

```python
"""Mining integration for System2Orchestrator using UnifiedHCEPipeline."""

import logging
from pathlib import Path
from typing import Any

from ..processors.hce.config_flex import PipelineConfigFlex, StageModelConfig
from ..processors.hce.types import EpisodeBundle, Segment
from ..processors.hce.unified_pipeline import UnifiedHCEPipeline
from ..processors.hce.storage_sqlite import upsert_pipeline_outputs, open_db
from ..errors import ErrorCode, KnowledgeSystemError

logger = logging.getLogger(__name__)


async def process_mine_with_unified_pipeline(
    orchestrator,  # System2Orchestrator instance
    episode_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """
    Process mining job using UnifiedHCEPipeline for parallel processing and rich data.
    
    Benefits over old approach:
    - 3-8x faster via parallel processing
    - Evidence spans with timestamps
    - Claim evaluation and A/B/C ranking
    - Relations between claims
    - Structured categories
    """
    
    try:
        # 1. Load transcript
        if orchestrator.progress_callback:
            orchestrator.progress_callback("loading", 0, episode_id)
        
        file_path = config.get("file_path")
        if not file_path:
            raise KnowledgeSystemError(
                f"No file_path in config for episode {episode_id}",
                ErrorCode.INVALID_INPUT,
            )
        
        transcript_text = Path(file_path).read_text()
        
        # 2. Parse transcript to segments
        if orchestrator.progress_callback:
            orchestrator.progress_callback("parsing", 5, episode_id)
        
        segments = orchestrator._parse_transcript_to_segments(transcript_text, episode_id)
        
        if not segments:
            logger.warning(f"No segments parsed from transcript for {episode_id}")
            return {
                "status": "succeeded",
                "output_id": episode_id,
                "result": {
                    "claims_extracted": 0,
                    "evidence_spans": 0,
                    "jargon_extracted": 0,
                    "people_extracted": 0,
                    "mental_models_extracted": 0,
                    "relations": 0,
                    "categories": 0,
                },
            }
        
        logger.info(f"📄 Parsed {len(segments)} segments for mining")
        
        # 3. Create EpisodeBundle
        episode_bundle = EpisodeBundle(
            episode_id=episode_id,
            segments=segments
        )
        
        # 4. Configure HCE Pipeline
        miner_model = config.get("miner_model", "ollama:qwen2.5:7b-instruct")
        
        # Allow configuration of parallelization
        max_workers = config.get("max_workers", None)  # None = auto-calculate
        enable_parallel = config.get("enable_parallel_processing", True)
        
        hce_config = PipelineConfigFlex(
            models=StageModelConfig(
                miner=miner_model,
                judge=miner_model,  # Can be different model if needed
                flagship_judge=miner_model,  # Can be different model if needed
            ),
            max_workers=max_workers if enable_parallel else 1,
            enable_parallel_processing=enable_parallel,
            orchestrator_run_id=run_id,  # Link LLM tracking to job
        )
        
        logger.info(
            f"🔧 HCE Config: miner={miner_model}, "
            f"parallel={'auto' if max_workers is None and enable_parallel else max_workers}, "
            f"run_id={run_id}"
        )
        
        # 5. Initialize UnifiedHCEPipeline
        pipeline = UnifiedHCEPipeline(hce_config)
        
        # 6. Create progress callback wrapper
        def progress_wrapper(step, percent, details=""):
            """Wrap pipeline progress to orchestrator format."""
            if orchestrator.progress_callback:
                # Pipeline reports 0-100%, map to orchestrator's 10-95% range
                adjusted_percent = 10 + int(percent * 0.85)
                orchestrator.progress_callback(step, adjusted_percent, episode_id)
        
        # 7. Process with full pipeline (mining + evaluation + categories)
        logger.info(f"🚀 Starting UnifiedHCEPipeline for {len(segments)} segments")
        
        pipeline_outputs = pipeline.process(
            episode_bundle,
            progress_callback=progress_wrapper
        )
        
        logger.info(
            f"✅ Pipeline complete: {len(pipeline_outputs.claims)} claims, "
            f"{len(pipeline_outputs.evidence_spans)} evidence spans, "
            f"{len(pipeline_outputs.relations)} relations, "
            f"{len(pipeline_outputs.structured_categories)} categories"
        )
        
        # 8. Store rich outputs to unified database
        if orchestrator.progress_callback:
            orchestrator.progress_callback("storing", 90, episode_id)
        
        unified_db_path = Path.home() / ".skip_the_podcast" / "unified_hce.db"
        conn = open_db(unified_db_path)
        
        try:
            video_id = episode_id.replace("episode_", "")
            
            upsert_pipeline_outputs(
                conn,
                pipeline_outputs,
                episode_title=Path(file_path).stem,
                video_id=video_id
            )
            
            conn.commit()
            logger.info(f"💾 Stored to unified database: {unified_db_path}")
            
        except Exception as e:
            logger.error(f"❌ Database storage failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
        
        # 9. Create Summary record (keep existing functionality)
        if orchestrator.progress_callback:
            orchestrator.progress_callback("generating_summary", 95, episode_id)
        
        video_id = episode_id.replace("episode_", "")
        summary_id = orchestrator._create_summary_from_pipeline_outputs(
            video_id, episode_id, pipeline_outputs, config
        )
        logger.info(f"📋 Summary record created: {summary_id}")
        
        # 10. Generate summary markdown file
        summary_file_path = None
        try:
            from ..services.file_generation import FileGenerationService
            
            output_dir = config.get("output_dir")
            if output_dir:
                file_gen = FileGenerationService(output_dir=Path(output_dir))
            else:
                file_gen = FileGenerationService()
            
            summary_file_path = file_gen.generate_summary_markdown_from_pipeline(
                video_id, episode_id, pipeline_outputs
            )
            
            if summary_file_path:
                logger.info(f"✅ Summary file: {summary_file_path}")
                
        except Exception as e:
            logger.error(f"❌ Summary file generation failed: {e}")
        
        # 11. Return rich results
        return {
            "status": "succeeded",
            "output_id": episode_id,
            "summary_file": str(summary_file_path) if summary_file_path else None,
            "result": {
                # Claim metrics
                "claims_extracted": len(pipeline_outputs.claims),
                "claims_tier_a": len([c for c in pipeline_outputs.claims if c.tier == "A"]),
                "claims_tier_b": len([c for c in pipeline_outputs.claims if c.tier == "B"]),
                "claims_tier_c": len([c for c in pipeline_outputs.claims if c.tier == "C"]),
                "evidence_spans": sum(len(c.evidence) for c in pipeline_outputs.claims),
                
                # Entity metrics
                "jargon_extracted": len(pipeline_outputs.jargon),
                "people_extracted": len(pipeline_outputs.people),
                "mental_models_extracted": len(pipeline_outputs.concepts),
                
                # Rich data metrics
                "relations": len(pipeline_outputs.relations),
                "categories": len(pipeline_outputs.structured_categories),
                
                # Processing metrics
                "segments_processed": len(segments),
                "parallel_workers": hce_config.max_workers or "auto",
            },
        }
        
    except Exception as e:
        logger.error(f"❌ Mining failed for {episode_id}: {e}")
        raise
```

#### Step 3: Update System2Orchestrator to use new mining

**In:** `src/knowledge_system/core/system2_orchestrator.py`

**Replace the `_process_mine` method:**

```python
async def _process_mine(
    self,
    episode_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """
    Process mining job using UnifiedHCEPipeline.
    
    This replaces the old sequential mining with parallel processing
    and rich data capture (evidence, relations, categories).
    """
    from .system2_orchestrator_mining import process_mine_with_unified_pipeline
    
    return await process_mine_with_unified_pipeline(
        self, episode_id, config, checkpoint, run_id
    )
```

#### Step 4: Add helper method for creating summaries from PipelineOutputs

```python
def _create_summary_from_pipeline_outputs(
    self,
    video_id: str,
    episode_id: str,
    pipeline_outputs: Any,  # PipelineOutputs
    config: dict[str, Any],
) -> str:
    """
    Create summary record from rich pipeline outputs.
    
    This replaces _create_summary_from_mining() to work with
    PipelineOutputs instead of simple miner outputs.
    """
    from ..database.models import Summary
    from ..utils.id_generation import create_deterministic_id
    
    # Generate summary ID
    summary_id = create_deterministic_id(f"summary_{episode_id}")
    
    with self.db_service.get_session() as session:
        # Check if summary already exists
        existing = session.query(Summary).filter_by(summary_id=summary_id).first()
        if existing:
            logger.info(f"Summary {summary_id} already exists")
            return summary_id
        
        # Create new summary with rich data
        summary = Summary(
            summary_id=summary_id,
            video_id=video_id,
            llm_model=config.get("miner_model", "ollama:qwen2.5:7b-instruct"),
            llm_provider=config.get("provider", "ollama"),
            
            # Basic counts
            total_claims=len(pipeline_outputs.claims),
            total_jargon=len(pipeline_outputs.jargon),
            total_people=len(pipeline_outputs.people),
            total_concepts=len(pipeline_outputs.concepts),
            
            # Rich data indicators
            has_evidence_spans=sum(len(c.evidence) for c in pipeline_outputs.claims) > 0,
            has_relations=len(pipeline_outputs.relations) > 0,
            has_categories=len(pipeline_outputs.structured_categories) > 0,
            
            # Tier distribution
            tier_a_count=len([c for c in pipeline_outputs.claims if c.tier == "A"]),
            tier_b_count=len([c for c in pipeline_outputs.claims if c.tier == "B"]),
            tier_c_count=len([c for c in pipeline_outputs.claims if c.tier == "C"]),
            
            # Summaries
            short_summary=pipeline_outputs.short_summary,
            long_summary=pipeline_outputs.long_summary,
        )
        
        session.add(summary)
        session.commit()
        
        logger.info(f"Created summary {summary_id} with rich metadata")
        return summary_id
```

### 3.2 Update DatabaseService to Use Unified DB

**File:** `src/knowledge_system/database/service.py`

**Find the `__init__` method (around line 70):**

```python
def __init__(self, database_url: str | None = None):
    """Initialize the database service."""
    
    # NEW: Default to unified database
    if database_url is None:
        unified_db = Path.home() / ".skip_the_podcast" / "unified_hce.db"
        database_url = f"sqlite:///{unified_db}"
        logger.info(f"Using unified database: {unified_db}")
    
    # ... rest of existing code ...
```

### 3.3 Update File Generation Service

**File:** `src/knowledge_system/services/file_generation.py`

**Add new method:**

```python
def generate_summary_markdown_from_pipeline(
    self,
    video_id: str,
    episode_id: str,
    pipeline_outputs,  # PipelineOutputs
) -> Path | None:
    """
    Generate summary markdown from rich PipelineOutputs.
    
    This version includes evidence spans, relations, and categories
    that weren't available in the old simple format.
    """
    from ..processors.hce.export import export_markdown
    
    try:
        output_file = self.output_dir / f"{video_id}_summary.md"
        
        # Use HCE export functionality
        markdown_content = export_markdown(pipeline_outputs)
        
        output_file.write_text(markdown_content)
        logger.info(f"Generated rich summary: {output_file}")
        
        return output_file
        
    except Exception as e:
        logger.error(f"Failed to generate summary markdown: {e}")
        return None
```

---

**PART 2 CONTINUES IN NEXT FILE** (hitting token limits)

Let me create the second part:




