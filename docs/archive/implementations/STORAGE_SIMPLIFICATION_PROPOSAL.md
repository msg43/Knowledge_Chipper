# Storage Simplification Proposal

## Current Dual Storage Architecture

### 1. **HCE Tables** (Main Knowledge Store)
Located in unified HCE schema:
- `claims` - Individual claims with tier rankings
- `evidence_spans` - Timestamped evidence supporting claims
- `jargon` - Technical terms with definitions
- `people` - Person mentions with context
- `concepts` - Mental models and frameworks
- `relations` - Relationships between claims
- `categories` - WikiData topic categorization

**Purpose:** Queryable knowledge graph for research and analysis

### 2. **Summaries Table** (Legacy)
Located in main database schema:
- `summary_id` - Primary key
- `video_id` - Link to MediaSource
- `summary_text` - Long narrative summary (TEXT)
- `summary_metadata_json` - HCE statistics
- `llm_provider` - Which LLM used
- `llm_model` - Model name
- `prompt_tokens`, `completion_tokens`, `total_tokens` - Usage metrics
- `processing_cost` - Cost in dollars
- `processing_time_seconds` - Performance metrics
- `compression_ratio` - Input/output size ratio
- `template_used` - Prompt template identifier

**Purpose:** Job metadata and user-facing narrative text

---

## Analysis: Should We Merge?

### ❌ **Arguments AGAINST Merging**

1. **Different Query Patterns**
   - HCE tables: "Find all claims about inflation by economist X"
   - Summaries: "Show me the full narrative summary for this video"

2. **Different Data Structures**
   - HCE: Highly normalized (one claim per row, with FK relationships)
   - Summaries: Denormalized (one big text blob per video)

3. **Job Metadata Doesn't Fit HCE Model**
   - Cost accounting (tokens, dollars) isn't knowledge
   - Processing metrics are operational, not semantic

4. **Already Have Job Tracking**
   - `jobs` and `job_runs` tables track execution
   - Metadata could live there instead

### ✅ **Arguments FOR Simplification**

1. **Redundant Storage**
   - `long_summary` is stored in both:
     - `summaries.summary_text` 
     - `pipeline_outputs.long_summary` (in code, could be persisted)

2. **Maintenance Burden**
   - Two schema updates for storage changes
   - Two write paths to maintain in sync

3. **No Live Data**
   - Perfect time for breaking schema changes
   - No migration needed

4. **Unclear Value**
   - The `summary_metadata_json` duplicates HCE table stats
   - LLM metadata could move to `job_runs`

---

## ✅ **RECOMMENDED APPROACH: Eliminate Summaries Table**

### Migration Plan

#### **Phase 1: Move Data to Correct Homes**

1. **Move long_summary to HCE tables**
   - Add `long_summary` TEXT column to HCE `episodes` table (or create new `episode_summaries` table)
   - Add `short_summary` TEXT column as well

2. **Move LLM metadata to job_runs**
   - `job_runs.metrics_json` already exists
   - Store: `{provider, model, prompt_tokens, completion_tokens, total_tokens, cost, processing_time}`

3. **Keep compression/quality metrics in episodes**
   - Add columns to episodes: `input_length`, `summary_length`, `compression_ratio`

#### **Phase 2: Update Code**

1. **Modify `_create_summary_from_pipeline_outputs()`**
   - Instead of creating `Summary` record
   - Update HCE `episodes` table with long_summary
   - Update `job_runs.metrics_json` with LLM metadata

2. **Update FileGenerationService**
   - Read from HCE tables + episodes instead of summaries table

3. **Update any summary queries**
   - Change from `session.query(Summary)` 
   - To join between episodes and HCE data

#### **Phase 3: Schema Changes**

```sql
-- Add to HCE schema
ALTER TABLE episodes ADD COLUMN short_summary TEXT;
ALTER TABLE episodes ADD COLUMN long_summary TEXT;
ALTER TABLE episodes ADD COLUMN input_length INTEGER;
ALTER TABLE episodes ADD COLUMN summary_length INTEGER;
ALTER TABLE episodes ADD COLUMN compression_ratio REAL;
ALTER TABLE episodes ADD COLUMN generated_at TIMESTAMP;

-- Drop old table (after migration)
DROP TABLE summaries;
```

---

## Alternative: Keep Lightweight Summaries Table

If you want to preserve the concept but simplify:

```sql
CREATE TABLE episode_summaries (
    episode_id TEXT PRIMARY KEY,
    short_summary TEXT NOT NULL,
    long_summary TEXT NOT NULL,
    generated_at TIMESTAMP NOT NULL,
    generated_by_model TEXT,  -- e.g., "ollama:qwen2.5:7b-instruct"
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id)
);
```

**Rationale:**
- Keeps summaries separate from structured HCE data
- Much simpler than current summaries table
- No redundant metadata
- Job metadata stays in job_runs

---

## Impact Assessment

### Files to Modify

1. **Schema**
   - `src/knowledge_system/database/migrations/unified_schema.sql`
   - Add episodes.long_summary, episodes.short_summary

2. **Models**
   - `src/knowledge_system/database/models.py`
   - Remove or deprecate `Summary` class
   - Or keep as lightweight `EpisodeSummary`

3. **Storage**
   - `src/knowledge_system/database/hce_store.py`
   - Add method to upsert summaries

4. **Orchestrator**
   - `src/knowledge_system/core/system2_orchestrator.py`
   - Replace `_create_summary_from_pipeline_outputs()` 
   - Store to episodes instead of summaries

5. **File Generation**
   - `src/knowledge_system/services/file_generation.py`
   - Update queries to read from episodes instead of summaries

### Breaking Changes

- ✅ No live data, so safe
- ✅ Old markdown files still readable
- ⚠️ Any code querying `Summary` table will break
- ⚠️ Need to update all SQL joins

---

## Recommended Decision Tree

```
Do you need summaries separate from HCE data?
├─ YES → Keep lightweight `episode_summaries` table
│         Store ONLY: episode_id, short_summary, long_summary, generated_at, model
│         Move LLM metrics to job_runs.metrics_json
│
└─ NO  → Add summary columns to `episodes` table
          Store: short_summary, long_summary as TEXT columns
          Eliminate summaries table entirely
```

---

## My Recommendation: **Add to Episodes Table**

### Why?

1. **Simplest architecture**
   - One row per episode
   - All episode data together (segments + summaries)
   - No joins needed for common queries

2. **Natural fit**
   - Summaries ARE part of the episode
   - Not a separate entity

3. **Easy to implement**
   - Just add 2-3 columns
   - Update one write path
   - Update one read path

4. **Future-proof**
   - Can always split later if needed
   - Can't easily merge if kept separate

### Implementation Steps

```python
# 1. Update episodes table
ALTER TABLE episodes ADD COLUMN short_summary TEXT;
ALTER TABLE episodes ADD COLUMN long_summary TEXT;
ALTER TABLE episodes ADD COLUMN summary_generated_at TIMESTAMP;

# 2. Modify HCEStore.upsert_pipeline_outputs()
def upsert_pipeline_outputs(self, pipeline_outputs, episode_title, video_id):
    # ... existing code to store claims, evidence, etc ...
    
    # NEW: Store summaries
    with self.db.get_session() as session:
        episode = session.query(Episode).filter_by(
            episode_id=pipeline_outputs.episode_id
        ).first()
        
        if episode:
            episode.short_summary = pipeline_outputs.short_summary
            episode.long_summary = pipeline_outputs.long_summary
            episode.summary_generated_at = datetime.utcnow()
            session.commit()

# 3. Update job_runs metrics
job_run.metrics_json = {
    'llm_provider': 'ollama',
    'llm_model': 'qwen2.5:7b-instruct',
    'prompt_tokens': 1234,
    'completion_tokens': 567,
    'total_tokens': 1801,
    'processing_cost': 0.0,
    'processing_time_seconds': 45.2,
    'compression_ratio': 0.15,
}

# 4. Delete summaries table creation
DROP TABLE summaries;
```

---

## Timeline Estimate

- Schema update: **5 minutes**
- Code changes: **30-60 minutes**
- Testing: **15-30 minutes**
- Total: **~1 hour**

Since there's no live data, this is **zero risk**.

---

## Verdict: ✅ **MERGE INTO EPISODES TABLE**

**Benefits:**
- Simpler codebase
- Fewer tables to maintain
- Natural data organization
- Easy to understand
- Zero migration risk (no data)

**Minimal Downside:**
- Slightly larger episodes table (2 TEXT columns)
- But queries are faster (no joins needed)

Ready to implement this now if you approve!
