# Storage Simplification Proposal v2 (Claim-Centric)

## Correct Architecture: Claims → Sources → Summaries

### Mental Model

```
CLAIM (atomic unit)
  ├─ claim_text
  ├─ evidence_spans
  ├─ tier (A/B/C)
  └─ source_id ──→ SOURCE
                     ├─ title
                     ├─ author
                     ├─ date
                     ├─ source_type (video, pdf, article, tweet)
                     ├─ url
                     └─ summary_id ──→ SUMMARY
                                        ├─ short_summary
                                        └─ long_summary
```

**Key Insight:** 
- **Claims are the knowledge** (searchable, citable, verifiable)
- **Sources are metadata** (where did this claim come from?)
- **Summaries describe sources** (not claims, not episodes)

---

## Current Reality Check

Looking at your existing schema, you already have `media_sources` table:
- `video_id` / `media_id` (primary key)
- `title`, `url`, `source_type`
- Used for: YouTube videos, local files, etc.

Your `summaries` table currently links to `video_id` (FK to media_sources), which is **already correct**!

The problem is NOT the FK relationship - it's that the `summaries` table has too much irrelevant metadata (job tracking, LLM costs, etc.).

---

## ✅ Recommended Approach: Lightweight Source Summaries

### 1. **Keep Source-Level Summaries** (Not Episode-Level)

Create a clean summaries table that links to **media_sources** (the source of claims):

```sql
CREATE TABLE content_summaries (
    summary_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,           -- FK to media_sources.video_id
    source_type TEXT NOT NULL,          -- 'video', 'pdf', 'article', 'document'
    short_summary TEXT,                 -- Pre-mining contextual overview
    long_summary TEXT NOT NULL,         -- Post-analysis comprehensive summary
    generated_at TIMESTAMP NOT NULL,
    generated_by_model TEXT,            -- e.g., "ollama:qwen2.5:7b-instruct"
    summary_type TEXT DEFAULT 'hce',    -- 'hce', 'extractive', 'abstractive', 'custom'
    input_length INTEGER,               -- Character count of source
    output_length INTEGER,              -- Character count of summary
    compression_ratio REAL,             -- output/input
    FOREIGN KEY (source_id) REFERENCES media_sources(video_id)
);
```

### 2. **Move LLM Metadata to Job Runs**

The `job_runs.metrics_json` already exists and is the right place for operational metadata:

```python
job_run.metrics_json = {
    # LLM usage tracking
    'llm_provider': 'ollama',
    'llm_model': 'qwen2.5:7b-instruct',
    'prompt_tokens': 1234,
    'completion_tokens': 567,
    'total_tokens': 1801,
    'processing_cost': 0.0015,  # dollars
    'processing_time_seconds': 45.2,
    
    # HCE-specific metrics
    'claims_extracted': 87,
    'claims_tier_a': 12,
    'claims_tier_b': 34,
    'claims_tier_c': 41,
    'evidence_spans': 156,
    'people_extracted': 8,
    'concepts_extracted': 15,
}
```

### 3. **Claims Point to Sources** (Already Correct)

Your HCE tables already have this right:

```sql
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,  -- This links to the source
    canonical TEXT NOT NULL,
    tier TEXT,
    ...
);
```

**Just need to clarify:** `episode_id` should really be `source_id` to be more general.

---

## Why This Works for All Content Types

### YouTube Video
```
media_sources: {video_id: "abc123", source_type: "video", title: "Fed Policy Talk"}
  └─ content_summaries: {source_id: "abc123", long_summary: "This video discusses..."}
      └─ claims: {source_id: "abc123", canonical: "The Fed raised rates by 25bps"}
```

### PDF Document
```
media_sources: {video_id: "doc_xyz", source_type: "pdf", title: "Inflation Report"}
  └─ content_summaries: {source_id: "doc_xyz", long_summary: "This report analyzes..."}
      └─ claims: {source_id: "doc_xyz", canonical: "Inflation reached 3.7% in Q2"}
```

### Blog Article
```
media_sources: {video_id: "article_789", source_type: "article", title: "AI Safety"}
  └─ content_summaries: {source_id: "article_789", long_summary: "The author argues..."}
      └─ claims: {source_id: "article_789", canonical: "Alignment is unsolved"}
```

---

## Claim-Centric Query Examples

### "Find all claims about inflation"
```sql
SELECT c.canonical, c.evidence, m.title, m.author, m.date
FROM claims c
JOIN media_sources m ON c.episode_id = m.video_id
WHERE c.canonical LIKE '%inflation%'
ORDER BY c.tier ASC;
```

### "Get summary and top claims for this source"
```sql
-- Get summary
SELECT cs.long_summary 
FROM content_summaries cs
WHERE cs.source_id = 'abc123';

-- Get top claims
SELECT canonical, tier, evidence
FROM claims
WHERE episode_id = 'abc123'
  AND tier = 'A'
ORDER BY importance_score DESC;
```

### "Find all claims by author X"
```sql
SELECT c.canonical, c.tier, m.title
FROM claims c
JOIN media_sources m ON c.episode_id = m.video_id
WHERE m.author = 'Paul Krugman'
  AND c.tier IN ('A', 'B');
```

**Claims are queried, sources are metadata, summaries are descriptions.**

---

## Recommended Schema Changes

### Rename for Clarity

1. **Rename `episode_id` to `source_id` in claims table**
   ```sql
   ALTER TABLE claims RENAME COLUMN episode_id TO source_id;
   ```

2. **Rename `video_id` to `source_id` in media_sources** (or keep as is if you prefer)
   ```sql
   -- Optional: makes it clearer this isn't just for videos
   ALTER TABLE media_sources RENAME COLUMN video_id TO source_id;
   ```

3. **Create new lightweight summaries table**
   ```sql
   DROP TABLE summaries;  -- Old bloated version
   
   CREATE TABLE content_summaries (
       summary_id TEXT PRIMARY KEY,
       source_id TEXT NOT NULL,
       source_type TEXT NOT NULL,
       short_summary TEXT,
       long_summary TEXT NOT NULL,
       generated_at TIMESTAMP NOT NULL,
       generated_by_model TEXT,
       summary_type TEXT DEFAULT 'hce',
       input_length INTEGER,
       output_length INTEGER,
       compression_ratio REAL,
       FOREIGN KEY (source_id) REFERENCES media_sources(video_id)
   );
   ```

---

## Implementation Plan

### Phase 1: Schema Update

```sql
-- 1. Rename for clarity (optional but recommended)
ALTER TABLE claims RENAME COLUMN episode_id TO source_id;

-- 2. Drop old summaries table
DROP TABLE summaries;

-- 3. Create new lightweight summaries
CREATE TABLE content_summaries (
    summary_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    short_summary TEXT,
    long_summary TEXT NOT NULL,
    generated_at TIMESTAMP NOT NULL,
    generated_by_model TEXT,
    summary_type TEXT DEFAULT 'hce',
    input_length INTEGER,
    output_length INTEGER,
    compression_ratio REAL,
    FOREIGN KEY (source_id) REFERENCES media_sources(video_id)
);

-- 4. Create index for fast lookups
CREATE INDEX idx_content_summaries_source ON content_summaries(source_id);
```

### Phase 2: Code Updates

#### File: `src/knowledge_system/core/system2_orchestrator.py`

Replace `_create_summary_from_pipeline_outputs()`:

```python
def _create_summary_from_pipeline_outputs(
    self,
    source_id: str,  # Changed from video_id
    source_type: str,  # 'video', 'pdf', 'article'
    pipeline_outputs: Any,
    config: dict[str, Any],
) -> str:
    """Create content summary record from pipeline outputs."""
    from ..database.models import ContentSummary  # New model
    from datetime import datetime
    import uuid
    
    summary_id = f"summary_{uuid.uuid4().hex[:12]}"
    
    # Get model info
    miner_model = config.get("miner_model", "ollama:qwen2.5:7b-instruct")
    
    # Calculate lengths
    input_length = config.get("input_length", 0)
    long_summary = pipeline_outputs.long_summary
    output_length = len(long_summary) if long_summary else 0
    compression_ratio = output_length / input_length if input_length > 0 else 0
    
    with self.db_service.get_session() as session:
        summary = ContentSummary(
            summary_id=summary_id,
            source_id=source_id,
            source_type=source_type,
            short_summary=pipeline_outputs.short_summary,
            long_summary=long_summary,
            generated_at=datetime.utcnow(),
            generated_by_model=miner_model,
            summary_type='hce',
            input_length=input_length,
            output_length=output_length,
            compression_ratio=compression_ratio,
        )
        session.add(summary)
        session.commit()
    
    return summary_id
```

#### File: `src/knowledge_system/database/models.py`

Add new model:

```python
class ContentSummary(Base):
    """Summaries of content from any source type (video, PDF, article, etc.)"""
    __tablename__ = 'content_summaries'
    
    summary_id = Column(String, primary_key=True)
    source_id = Column(String, ForeignKey('media_sources.video_id'), nullable=False)
    source_type = Column(String, nullable=False)  # video, pdf, article, document
    short_summary = Column(Text)
    long_summary = Column(Text, nullable=False)
    generated_at = Column(DateTime, nullable=False)
    generated_by_model = Column(String)
    summary_type = Column(String, default='hce')
    input_length = Column(Integer)
    output_length = Column(Integer)
    compression_ratio = Column(Float)
    
    # Relationship
    source = relationship("MediaSource", back_populates="summaries")
```

Update MediaSource model:

```python
class MediaSource(Base):
    """Media sources (videos, PDFs, articles, etc.)"""
    __tablename__ = 'media_sources'
    
    # ... existing columns ...
    
    # Add relationship
    summaries = relationship("ContentSummary", back_populates="source")
    claims = relationship("Claim", back_populates="source")
```

#### File: `src/knowledge_system/services/file_generation.py`

Update query:

```python
def generate_summary_markdown_from_pipeline(
    self, source_id: str, pipeline_outputs
) -> Path | None:
    """Generate summary markdown from pipeline outputs."""
    
    # Get source metadata
    with self.db.get_session() as session:
        source = session.query(MediaSource).filter_by(
            video_id=source_id
        ).first()
        
        if not source:
            logger.warning(f"No source found for {source_id}")
            return None
        
        # Generate markdown
        output_file = self.summaries_dir / f"{source_id}_summary.md"
        
        # ... rest of markdown generation ...
```

---

## Why This is Claim-Centric

1. **Claims are queryable independently**
   - Search by topic, person, concept
   - Filter by tier, confidence, evidence strength
   - No need to know which source they came from

2. **Sources provide context**
   - Author credibility
   - Publication date
   - Source type (academic paper vs tweet)
   - All attached as metadata to claims

3. **Summaries describe sources, not claims**
   - A summary is "what is this source about?"
   - Claims are "what specific knowledge does it contain?"
   - Different abstraction levels

4. **Works for any content type**
   - YouTube video → extract claims → summarize video
   - PDF → extract claims → summarize document
   - Article → extract claims → summarize article
   - Same pattern, different source types

---

## Files to Modify

1. **Schema**
   - `src/knowledge_system/database/migrations/unified_schema.sql`

2. **Models**
   - `src/knowledge_system/database/models.py`
   - Add `ContentSummary`, update `MediaSource`

3. **Orchestrator**
   - `src/knowledge_system/core/system2_orchestrator.py`
   - Rename `video_id` → `source_id` throughout
   - Update `_create_summary_from_pipeline_outputs()`

4. **Mining**
   - `src/knowledge_system/core/system2_orchestrator_mining.py`
   - Pass `source_type` to summary creation

5. **HCE Store**
   - `src/knowledge_system/database/hce_store.py`
   - Update to use `source_id` instead of `episode_id`

6. **File Generation**
   - `src/knowledge_system/services/file_generation.py`
   - Query `content_summaries` instead of `summaries`

---

## Timeline

- Schema changes: **10 minutes**
- Model updates: **15 minutes**
- Code refactoring: **45-60 minutes**
- Testing: **30 minutes**
- **Total: ~2 hours**

---

## Verdict: ✅ **Source-Level Summaries (Claim-Centric)**

**Architecture:**
```
Claims (atomic knowledge)
  └─ point to →
      Sources (metadata)
        └─ have →
            Summaries (descriptions)
            
Not: Episodes → Claims (episode-centric ❌)
But: Claims → Sources (claim-centric ✅)
```

**Benefits:**
- ✅ Claims are the primary unit
- ✅ Works for videos, PDFs, articles, tweets, etc.
- ✅ Sources provide context to claims
- ✅ Summaries describe sources
- ✅ Clean separation of concerns
- ✅ Queryable knowledge graph

Ready to implement this claim-centric architecture!
