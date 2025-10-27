# Architecture: Unified Storage Layer

## Overview

The system uses a single, unified storage path for all HCE (Hybrid Claim Extraction) data:

```
User Action (GUI/CLI)
    ↓
System2Orchestrator
    ↓
UnifiedHCEPipeline
    ├─> Mining (parallel)
    ├─> Evaluation (flagship)
    ├─> Categorization
    └─> Storage (unified DB)
```

## Components

### System2Orchestrator
**Location:** `src/knowledge_system/core/system2_orchestrator.py`

**Responsibilities:**
- Job creation and tracking
- Progress callbacks to GUI
- LLM request/response logging
- Auto-process chaining
- Error handling and retry

**Does NOT:**
- Mine segments directly
- Store data directly

**Key Methods:**
- `_process_mine()` - Delegates to `system2_orchestrator_mining.py`
- `_create_summary_from_pipeline_outputs()` - Creates Summary records with rich metadata

### UnifiedHCEPipeline
**Location:** `src/knowledge_system/processors/hce/unified_pipeline.py`

**Responsibilities:**
- Parallel segment mining
- Claim evaluation and ranking
- Relation extraction
- Category identification
- Progress reporting

**Phases:**
1. Short summary generation
2. Parallel mining (3-8x faster)
3. Flagship evaluation (A/B/C tiers)
4. Long summary generation
5. Category analysis

### Mining Integration Module
**Location:** `src/knowledge_system/core/system2_orchestrator_mining.py`

**Function:** `process_mine_with_unified_pipeline()`

**Responsibilities:**
- Loads transcript and parses to segments
- Creates `EpisodeBundle` from segments
- Configures `UnifiedHCEPipeline` with parallel workers
- Processes full pipeline (mining + evaluation + categories)
- Stores to unified DB using `storage_sqlite.upsert_pipeline_outputs()`
- Creates Summary record with rich metrics
- Generates markdown file
- Returns comprehensive results with tier distribution

### Storage Layer
**Location:** `src/knowledge_system/processors/hce/storage_sqlite.py`

**Responsibilities:**
- Bulk SQL inserts (optimized)
- Evidence span storage
- Relation storage
- Category storage
- FTS index maintenance

**Database:** `~/Library/Application Support/SkipThePodcast/unified_hce.db`

## Data Flow

```
Transcript File
    ↓
Parse to Segments
    ↓
UnifiedHCEPipeline.process()
    ├─> mine_episode_unified() [PARALLEL]
    │   └─> Returns: UnifiedMinerOutput[] 
    ├─> evaluate_claims_flagship()
    │   └─> Returns: EvaluatedClaim[]
    ├─> analyze_structured_categories()
    │   └─> Returns: StructuredCategory[]
    └─> Returns: PipelineOutputs
        ├─> claims: ScoredClaim[] (with tier A/B/C)
        ├─> evidence: EvidenceSpan[] (with t0/t1/quote)
        ├─> relations: Relation[]
        ├─> categories: StructuredCategory[]
        ├─> people: PersonMention[]
        ├─> concepts: MentalModel[]
        └─> jargon: JargonTerm[]
    ↓
storage_sqlite.upsert_pipeline_outputs()
    └─> Unified Database
```

## Performance

### Parallel Processing

**Auto-calculation:**
- M2 Ultra (24 cores): 8 workers
- M2 Max (12 cores): 6 workers  
- M2 Pro (10 cores): 4 workers
- M1/M2 (8 cores): 3 workers

**Speed improvement:** 3-8x faster than sequential

**Memory safety:** Automatic throttling if RAM > 80%

### Benchmarks

| Hardware | Sequential | Parallel | Speedup |
|----------|-----------|----------|---------|
| M2 Ultra | 15 min | 2 min | 7.5x |
| M2 Max | 15 min | 2.5 min | 6x |
| M2 Pro | 15 min | 4 min | 3.75x |

## Database Schema

**Location:** `src/knowledge_system/database/migrations/unified_schema.sql`

### Key Tables

#### claims
- **Primary Key:** `(episode_id, claim_id)`
- **Foreign Keys:** `episode_id → episodes(episode_id)`
- **Key Fields:**
  - `canonical` - Claim text
  - `claim_type` - factual/causal/normative/forecast/definition
  - `tier` - A/B/C ranking
  - `scores_json` - importance/novelty/controversy/fragility
  - `temporality_score` - 1 (immediate) to 5 (timeless)
  - `first_mention_ts` - Timestamp

#### evidence_spans
- **Primary Key:** `(episode_id, claim_id, seq)`
- **Foreign Keys:** 
  - `(episode_id, claim_id) → claims`
  - `(episode_id, segment_id) → segments`
- **Key Fields:**
  - `t0`, `t1` - Exact quote timestamps
  - `quote` - Verbatim text
  - `context_t0`, `context_t1` - Extended context
  - `context_text` - Full context
  - `context_type` - exact/extended/segment

#### relations
- **Primary Key:** `(episode_id, source_claim_id, target_claim_id, type)`
- **Foreign Keys:** Both claim IDs link to `claims`
- **Key Fields:**
  - `type` - supports/contradicts/depends_on/refines
  - `strength` - 0.0 to 1.0
  - `rationale` - Explanation

#### structured_categories
- **Primary Key:** `(episode_id, category_id)`
- **Foreign Keys:** `episode_id → episodes`
- **Key Fields:**
  - `category_name` - Topic name
  - `wikidata_qid` - WikiData Q-identifier
  - `coverage_confidence` - 0.0 to 1.0
  - `frequency_score` - How often topic appears

#### people
- **Primary Key:** `(episode_id, person_id)`
- **Key Fields:**
  - `name` - Person name
  - `surface` - As mentioned
  - `normalized` - Canonical form
  - `context_quote` - Quote showing mention
  - `entity_type` - person/org
  - `t0`, `t1` - Mention timestamps

#### concepts
- **Primary Key:** `(episode_id, concept_id)`
- **Key Fields:**
  - `name` - Concept name
  - `definition` - Explanation
  - `context_quote` - Illustrative quote
  - `first_mention_ts` - Timestamp

#### jargon
- **Primary Key:** `(episode_id, term_id)`
- **Key Fields:**
  - `term` - Technical term
  - `definition` - Explanation
  - `context_quote` - Usage example
  - `category` - technical/industry/acronym

### Indexes

- `idx_claims_episode_tier` - Fast tier-based queries
- `idx_claims_first_mention` - Timestamp-based lookups
- `idx_claims_temporality` - Temporality filtering
- `idx_evidence_spans_segment` - Evidence by segment
- `idx_relations_type` - Relation type filtering
- `idx_people_normalized` - Person name lookups
- `idx_concepts_name` - Concept searches
- `idx_jargon_term` - Jargon lookups

### Full-Text Search

- `claims_fts` - Search claim text
- `quotes_fts` - Search evidence quotes

## Migration from Old System

### Old System
- Sequential segment-by-segment mining
- Simple ORM storage (SQLAlchemy)
- No evidence spans
- No claim evaluation
- No relations
- No categories
- Dual storage paths (confusing)

### New System
- Parallel batch mining
- Optimized SQL storage
- Full evidence with timestamps
- Flagship evaluation (A/B/C)
- Claim relations
- Structured categories
- Single unified database

### Migration Script
**Location:** `scripts/migrate_to_unified_schema.py`

**Usage:**
```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 scripts/migrate_to_unified_schema.py
```

**What it does:**
1. Creates backup of existing database
2. Creates unified database with new schema
3. Migrates existing data (episodes, claims, people, concepts, jargon)
4. Reports migration statistics

## Configuration

### Parallel Processing Control

**In config:**
```python
config = {
    "miner_model": "ollama:qwen2.5:7b-instruct",
    "max_workers": None,  # Auto-calculate based on hardware
    "enable_parallel_processing": True,
}
```

**Force sequential (for debugging):**
```python
config = {
    "max_workers": 1,
    "enable_parallel_processing": False,
}
```

### Database Location

Default: `~/Library/Application Support/SkipThePodcast/unified_hce.db`

This location is:
- User-writable (no permission issues)
- Standard macOS location for app data
- Automatically created if missing

## File Generation

### Summary Markdown
**Location:** `src/knowledge_system/services/file_generation.py`

**Method:** `generate_summary_markdown_from_pipeline()`

**Output includes:**
- Overview statistics (claims by tier, evidence count, etc.)
- Short summary (pre-mining)
- Top Tier A claims with evidence quotes
- People mentioned with context
- Mental models/concepts with definitions
- Jargon terms with explanations
- Claim relations
- Categories with confidence scores
- Long summary (post-evaluation)

**Output location:** `output/summaries/{video_id}_summary.md`

## Error Handling

### Database Errors
- Automatic rollback on failure
- Detailed error logging
- Connection cleanup in finally blocks

### Pipeline Errors
- Graceful degradation (e.g., short summary failure doesn't stop mining)
- Comprehensive error messages
- Progress callback updates even on errors

### Progress Tracking
- Loading: 0-5%
- Parsing: 5-10%
- Mining: 10-90% (via pipeline callback)
- Storing: 90-95%
- Summary generation: 95-100%

## Testing

### Unit Tests
**Location:** `tests/system2/test_unified_hce_operations.py`

**Coverage:**
- Mining creates rich data
- Context quotes populated
- Database schema correct
- Evidence spans have timestamps

### Integration Tests
**Location:** `tests/integration/test_unified_pipeline_integration.py`

**Coverage:**
- Parallel vs sequential performance
- Rich data extraction
- Progress callbacks
- End-to-end workflow

## Rollback Plan

See `_deprecated/README.md` for detailed rollback instructions.

**Quick rollback:**
```bash
# Restore code
git checkout backup/before-unification

# Restore database
cp knowledge_system.db.pre_unification.TIMESTAMP knowledge_system.db
```

## Future Enhancements

1. **Cross-episode analytics** - Query claims across all episodes
2. **Claim deduplication** - Identify similar claims across episodes
3. **Entity linking** - Link people/concepts to external knowledge bases
4. **Temporal analysis** - Track how claims evolve over time
5. **Relation visualization** - Graph view of claim relationships
6. **Category hierarchies** - Organize categories into taxonomy

## References

- `UNIFICATION_MASTER_PLAN.md` - Implementation plan
- `UNIFICATION_MASTER_PLAN_PART2.md` - Testing and deployment
- `docs/guides/USER_GUIDE_UNIFIED.md` - User documentation
- `src/knowledge_system/processors/hce/unified_pipeline.py` - Pipeline implementation
- `src/knowledge_system/processors/hce/storage_sqlite.py` - Storage implementation
