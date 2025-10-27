# Claim-Centric Storage Architecture

## Current State Analysis

### Existing Tables

**Main Schema (source tracking):**
- `media_sources` - Videos, PDFs, articles (PRIMARY: `media_id`, SYNONYM: `video_id`)
- `summaries` - Summaries of media sources (FK: `media_sources.media_id`)

**HCE Schema (knowledge extraction):**
- `hce_episodes` - Episode organization (has `episode_id` and `video_id`)
- `hce_claims` - Claims extracted (FK: `hce_episodes.episode_id`)
- `hce_evidence_spans`, `hce_people`, `hce_concepts`, etc.

### The Problem

Claims link to `hce_episodes`, which then link to `media_sources` via `video_id`, creating an **unnecessary intermediary**:

```
media_sources (source metadata)
    ↓
hce_episodes (intermediary - why?)
    ↓
hce_claims (knowledge)
```

This is **episode-centric**, not **claim-centric**.

---

## ✅ Claim-Centric Architecture

### Correct Model

```
media_sources (source: video, PDF, article)
    ├─ summaries (what is this source about?)
    └─ hce_claims (what knowledge does it contain?)
            ├─ hce_evidence_spans
            ├─ hce_people
            ├─ hce_concepts
            └─ hce_relations
```

**Episodes are just organizational** (for chunking transcripts into segments), not a fundamental unit.

---

## Recommended Changes

### 1. **Add `source_id` to HCE Claims** (Direct Link to Sources)

```sql
-- Add source_id column to claims
ALTER TABLE hce_claims ADD COLUMN source_id TEXT;

-- Create FK to media_sources
-- Note: Can't add FK immediately if data exists, so do in migration

-- Create index for fast lookups
CREATE INDEX idx_hce_claims_source ON hce_claims(source_id);

-- Backfill from existing episode_id → video_id → source_id
UPDATE hce_claims
SET source_id = (
    SELECT he.video_id 
    FROM hce_episodes he 
    WHERE he.episode_id = hce_claims.episode_id
);

-- Make it required after backfill
-- ALTER TABLE hce_claims ALTER COLUMN source_id SET NOT NULL;  -- SQLite doesn't support this
```

### 2. **Deprecate `hce_episodes` as Primary Link**

Keep `hce_episodes` for:
- Organizing transcript segments (temporal chunks)
- Storing episode metadata (title, subtitle, recorded_at)

But **claims no longer require an episode** - they link directly to `source_id`:

```sql
-- Keep episode_id for backwards compatibility, but it's optional now
ALTER TABLE hce_claims RENAME COLUMN episode_id TO episode_id_legacy;
```

### 3. **Simplify Summaries Table**

Replace bloated `summaries` with lean `content_summaries`:

```sql
-- Drop old summaries table
DROP TABLE summaries;

-- Create new lightweight summaries
CREATE TABLE content_summaries (
    summary_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,                -- FK to media_sources.media_id
    short_summary TEXT,                     -- Pre-mining overview
    long_summary TEXT NOT NULL,             -- Post-analysis synthesis
    generated_at TIMESTAMP NOT NULL,
    generated_by_model TEXT,                -- e.g., "ollama:qwen2.5:7b-instruct"
    summary_type TEXT DEFAULT 'hce',        -- 'hce', 'extractive', 'custom'
    input_length INTEGER,
    output_length INTEGER,
    compression_ratio REAL,
    FOREIGN KEY (source_id) REFERENCES media_sources(media_id) ON DELETE CASCADE
);

CREATE INDEX idx_content_summaries_source ON content_summaries(source_id);
```

### 4. **Move LLM Metadata to Job Runs**

`job_runs.metrics_json` already exists - store there:

```python
job_run.metrics_json = {
    'llm_provider': 'ollama',
    'llm_model': 'qwen2.5:7b-instruct',
    'prompt_tokens': 1234,
    'completion_tokens': 567,
    'total_tokens': 1801,
    'processing_cost': 0.0,
    'processing_time_seconds': 45.2,
}
```

---

## Claim-Centric Query Examples

### Find all claims about "inflation"
```sql
SELECT 
    c.canonical,
    c.tier,
    c.evidence_spans,
    m.title AS source_title,
    m.uploader AS author,
    m.upload_date
FROM hce_claims c
JOIN media_sources m ON c.source_id = m.media_id
WHERE c.canonical LIKE '%inflation%'
  AND c.tier IN ('A', 'B')
ORDER BY c.tier ASC, c.scores_json->>'importance' DESC;
```

### Get summary + top claims for a source
```sql
-- Summary
SELECT long_summary 
FROM content_summaries 
WHERE source_id = 'abc123';

-- Top claims
SELECT canonical, tier, evidence_spans
FROM hce_claims
WHERE source_id = 'abc123'
  AND tier = 'A'
ORDER BY scores_json->>'importance' DESC;
```

### Find claims by author across all sources
```sql
SELECT 
    c.canonical,
    c.tier,
    m.title,
    m.upload_date
FROM hce_claims c
JOIN media_sources m ON c.source_id = m.media_id
WHERE m.uploader = 'Paul Krugman'
ORDER BY m.upload_date DESC;
```

---

## Updated HCE Claims Schema

```sql
CREATE TABLE IF NOT EXISTS hce_claims (
  claim_id TEXT PRIMARY KEY,                    -- Global unique claim ID
  source_id TEXT NOT NULL,                      -- Direct link to media_sources
  episode_id_legacy TEXT,                       -- Backwards compat (nullable)
  
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
  
  FOREIGN KEY (source_id) REFERENCES media_sources(media_id) ON DELETE CASCADE
);

CREATE INDEX idx_hce_claims_source ON hce_claims(source_id);
CREATE INDEX idx_hce_claims_tier ON hce_claims(tier);
CREATE INDEX idx_hce_claims_type ON hce_claims(claim_type);
```

**Key changes:**
- `claim_id` is now PRIMARY KEY (global, not per-episode)
- `source_id` is the main FK (to `media_sources`)
- `episode_id` renamed to `episode_id_legacy` (nullable, for migration)

---

## Updated Evidence Spans Schema

```sql
CREATE TABLE IF NOT EXISTS hce_evidence_spans (
  claim_id TEXT NOT NULL,                       -- Global claim ID
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
  
  PRIMARY KEY (claim_id, seq),
  FOREIGN KEY (claim_id) REFERENCES hce_claims(claim_id) ON DELETE CASCADE
);
```

**Simplified:** Just `claim_id`, no composite keys.

---

## Migration Strategy

### Phase 1: Add New Columns

```sql
-- 1. Add source_id to claims
ALTER TABLE hce_claims ADD COLUMN source_id TEXT;

-- 2. Backfill from episodes
UPDATE hce_claims
SET source_id = (
    SELECT video_id FROM hce_episodes WHERE episode_id = hce_claims.episode_id
);

-- 3. Create index
CREATE INDEX idx_hce_claims_source ON hce_claims(source_id);
```

### Phase 2: Update Primary Keys

This is tricky in SQLite. Better approach: **create new tables** and migrate:

```sql
-- Create new claims table with better schema
CREATE TABLE hce_claims_v2 (
    claim_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    canonical TEXT NOT NULL,
    -- ... rest of columns ...
    FOREIGN KEY (source_id) REFERENCES media_sources(media_id) ON DELETE CASCADE
);

-- Migrate data
INSERT INTO hce_claims_v2
SELECT 
    episode_id || '_' || claim_id AS claim_id,  -- Make globally unique
    source_id,
    canonical,
    -- ... rest of columns ...
FROM hce_claims;

-- Rename tables
ALTER TABLE hce_claims RENAME TO hce_claims_old;
ALTER TABLE hce_claims_v2 RENAME TO hce_claims;

-- Drop old table after verification
DROP TABLE hce_claims_old;
```

### Phase 3: Create New Summaries Table

```sql
DROP TABLE summaries;

CREATE TABLE content_summaries (
    summary_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    short_summary TEXT,
    long_summary TEXT NOT NULL,
    generated_at TIMESTAMP NOT NULL,
    generated_by_model TEXT,
    summary_type TEXT DEFAULT 'hce',
    input_length INTEGER,
    output_length INTEGER,
    compression_ratio REAL,
    FOREIGN KEY (source_id) REFERENCES media_sources(media_id) ON DELETE CASCADE
);
```

### Phase 4: Update Code

**Files to modify:**

1. **`src/knowledge_system/database/migrations/unified_schema.sql`**
   - Update schema with new tables

2. **`src/knowledge_system/database/models.py`**
   - Update `HCEClaim` model (new primary key)
   - Add `ContentSummary` model
   - Remove old `Summary` model

3. **`src/knowledge_system/database/hce_store.py`**
   - Update `upsert_pipeline_outputs()` to use `source_id`
   - Generate global `claim_id` (not per-episode)

4. **`src/knowledge_system/core/system2_orchestrator.py`**
   - Update `_create_summary_from_pipeline_outputs()`
   - Use `ContentSummary` instead of `Summary`

5. **`src/knowledge_system/services/file_generation.py`**
   - Query `content_summaries` instead of `summaries`

---

## Works for All Content Types

### YouTube Video
```
media_sources: {
  media_id: "abc123",
  source_type: "youtube",
  title: "Fed Policy Discussion",
  uploader: "Economic Forum"
}
  ├─ content_summaries: {long_summary: "This video discusses..."}
  └─ hce_claims: [
      {source_id: "abc123", canonical: "Fed raised rates 25bps"},
      {source_id: "abc123", canonical: "Inflation peaked at 3.7%"}
     ]
```

### PDF Document
```
media_sources: {
  media_id: "doc_xyz",
  source_type: "pdf",
  title: "Inflation Analysis 2024",
  uploader: "Bureau of Labor Statistics"
}
  ├─ content_summaries: {long_summary: "This report analyzes..."}
  └─ hce_claims: [
      {source_id: "doc_xyz", canonical: "CPI increased 0.3% in March"},
      {source_id: "doc_xyz", canonical: "Core inflation remains elevated"}
     ]
```

### Blog Article
```
media_sources: {
  media_id: "article_789",
  source_type: "article",
  title: "AI Safety Concerns",
  uploader: "Eliezer Yudkowsky"
}
  ├─ content_summaries: {long_summary: "The author argues..."}
  └─ hce_claims: [
      {source_id: "article_789", canonical: "Alignment problem is unsolved"}
     ]
```

---

## Why This is Truly Claim-Centric

1. **Claims are independent entities**
   - Global `claim_id` (not scoped to episode)
   - Can search/filter/aggregate without knowing source
   - Direct link to `media_sources` (no intermediary)

2. **Sources provide attribution**
   - "Who said this?" → Check `source_id`
   - "When?" → `media_sources.upload_date`
   - "Where?" → `media_sources.url`
   - All metadata, not structure

3. **Episodes are optional organizational units**
   - Used for temporal segmentation (transcripts)
   - Not required for claims from PDFs, articles, etc.
   - Legacy field for backwards compatibility

4. **Summaries describe sources**
   - "What is this source about overall?"
   - Different from claims (specific knowledge units)
   - Linked at source level, not claim level

---

## Timeline

Given you have **no live data**:

- Schema redesign: **1 hour**
- Code updates: **2-3 hours**
- Testing: **1 hour**
- **Total: ~4-5 hours**

Worth it for a **clean, claim-centric architecture** that will last.

---

## Summary

**Before (Episode-Centric):**
```
media_sources → hce_episodes → hce_claims
                     ↓
               [intermediary layer]
```

**After (Claim-Centric):**
```
media_sources ─┬─→ content_summaries
               └─→ hce_claims ─┬─→ hce_evidence_spans
                               ├─→ hce_people
                               └─→ hce_concepts
```

**Benefits:**
- ✅ Claims as first-class entities
- ✅ Works for any source type (video, PDF, article, tweet)
- ✅ Direct queries without joins
- ✅ Clean separation: source metadata vs knowledge
- ✅ Future-proof architecture

Ready to implement?
