# Claim-Centric Architecture (Corrected)

## The Correct Hierarchy

```
CLAIMS (fundamental unit - atomic knowledge)
  │
  └─── attributed to ────→ SOURCES (organizational - where claims come from)
                              │
                              ├─ Episodes (type of source - segmented audio/video)
                              └─ Documents (type of source - PDFs, articles, etc.)
```

### What Each Layer Represents

**Claims:**
- **The atomic unit of knowledge**
- Queryable, citable, verifiable facts/arguments
- Stand alone as knowledge units
- Example: "The Fed raised rates by 25 basis points"

**Sources:**
- **Organizational layer** providing attribution
- Answer: "Where did this claim come from?"
- Provide context (author, date, platform)
- NOT the fundamental unit - just metadata

**Source Types:**
- **Episodes:** Segmented content (videos, podcasts with transcripts)
  - Have segments (temporal chunks)
  - Example: YouTube video, podcast episode
- **Documents:** Non-segmented content (PDFs, articles)
  - No segments (just continuous text)
  - Example: Research paper, blog post

---

## Correct Mental Model

### WRONG (Episode-Centric):
```
Episodes → Claims
```
This makes episodes the primary unit, claims secondary.

### WRONG (Source-Centric):
```
Sources → Claims
```
This makes sources the primary unit, claims secondary.

### ✅ CORRECT (Claim-Centric):
```
Claims → Sources
```
Claims are primary. Sources provide attribution.

---

## Architecture Implications

### Database Design

```sql
-- Claims are the primary table
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,           -- Global unique ID
    canonical TEXT NOT NULL,             -- The claim itself
    
    -- Attribution (optional - some claims might be synthetic)
    source_id TEXT,                      -- Which source is this from?
    
    -- Content
    claim_type TEXT,
    tier TEXT,
    ...
    
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id)
);

-- Sources are metadata for claims
CREATE TABLE media_sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,           -- 'episode' or 'document'
    title TEXT NOT NULL,
    uploader TEXT,                       -- Attribution
    upload_date TEXT,                    -- Attribution
    ...
);

-- Episodes are a TYPE of source (for segmented content)
CREATE TABLE episodes (
    episode_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL UNIQUE,      -- 1-to-1 with source
    
    -- Episode-specific fields
    short_summary TEXT,
    long_summary TEXT,
    ...
    
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id)
);

-- Segments belong to episodes (not all sources have segments)
CREATE TABLE segments (
    segment_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,            -- Only episodes have segments
    
    speaker TEXT,
    start_time TEXT,
    end_time TEXT,
    text TEXT NOT NULL,
    
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id)
);
```

### Query Examples

**Primary query (claim-centric):**
```sql
-- Find claims about "inflation"
SELECT c.canonical, c.tier
FROM claims c
WHERE c.canonical LIKE '%inflation%';

-- Claims are queryable on their own
```

**Add attribution context (when needed):**
```sql
-- Find claims about "inflation" WITH source context
SELECT 
    c.canonical,
    c.tier,
    ms.uploader AS author,
    ms.upload_date,
    ms.title AS source_title
FROM claims c
LEFT JOIN media_sources ms ON c.source_id = ms.source_id
WHERE c.canonical LIKE '%inflation%';

-- Source is optional context via LEFT JOIN
```

**Episode-specific queries (when you need segment timing):**
```sql
-- Find claims with their evidence timestamps
SELECT 
    c.canonical,
    es.start_time,
    es.quote
FROM claims c
JOIN evidence_spans es ON c.claim_id = es.claim_id
JOIN segments s ON es.segment_id = s.segment_id
WHERE c.claim_id = 'claim_abc123';

-- Episodes/segments are used when you need temporal data
```

---

## Source Types

### Type 1: Episodes (Segmented Content)

**Characteristics:**
- Has temporal structure (timestamps)
- Divided into segments
- Example: YouTube video, podcast

**Schema:**
```
media_sources (source_id, source_type='episode', ...)
    ↓ 1-to-1
episodes (episode_id=source_id, short_summary, ...)
    ↓ 1-to-many
segments (segment_id, episode_id, start_time, end_time, text, ...)
    ↓ referenced by
evidence_spans (claim_id, segment_id, start_time, end_time, quote, ...)
```

### Type 2: Documents (Non-Segmented Content)

**Characteristics:**
- No temporal structure
- Continuous text (no segments)
- Example: PDF paper, blog article

**Schema:**
```
media_sources (source_id, source_type='document', ...)
    ↓ attributes to
claims (claim_id, source_id, ...)
    ↓ has
evidence_spans (claim_id, segment_id=NULL, quote, page_number, ...)
```

**Key difference:** Documents don't have segments, but claims still have evidence (via page numbers, paragraphs, etc.)

---

## Categories: Claim-Level and Source-Level

### Claim Categories (Primary)
**The main categorization** - what is THIS claim about?

```sql
CREATE TABLE claim_categories (
    claim_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,
    is_primary BOOLEAN DEFAULT 0,
    ...
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);
```

### Source Categories (Context)
**Secondary categorization** - what is this source generally about?

```sql
CREATE TABLE source_categories (
    source_id TEXT NOT NULL,              -- Can be episode or document
    wikidata_id TEXT NOT NULL,
    rank INTEGER CHECK (rank BETWEEN 1 AND 3),
    ...
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id)
);
```

**Note:** NOT `episode_categories` - it's `source_categories` because documents also have categories!

---

## Claim Queries (The Primary Use Case)

### 1. Find claims by topic
```sql
SELECT c.canonical
FROM claims c
JOIN claim_categories cc ON c.claim_id = cc.claim_id
JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id
WHERE wc.category_name = 'Monetary policy'
  AND cc.is_primary = 1;
```

### 2. Find claims by author
```sql
SELECT c.canonical, ms.uploader
FROM claims c
JOIN media_sources ms ON c.source_id = ms.source_id
WHERE ms.uploader = 'Paul Krugman';
```

### 3. Find related claims (same topic)
```sql
SELECT c2.canonical
FROM claims c1
JOIN claim_categories cc1 ON c1.claim_id = cc1.claim_id
JOIN claim_categories cc2 ON cc1.wikidata_id = cc2.wikidata_id
JOIN claims c2 ON cc2.claim_id = c2.claim_id
WHERE c1.claim_id = 'claim_abc123'
  AND c2.claim_id != 'claim_abc123';
```

### 4. Cross-domain claims (topic differs from source)
```sql
-- Find geopolitics claims from finance sources
SELECT c.canonical
FROM claims c
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
JOIN wikidata_categories wc_claim ON cc.wikidata_id = wc_claim.wikidata_id
JOIN source_categories sc ON c.source_id = sc.source_id
JOIN wikidata_categories wc_source ON sc.wikidata_id = wc_source.wikidata_id
WHERE wc_claim.category_name = 'Geopolitics'
  AND wc_source.category_name = 'Finance';
```

---

## Summary

### Hierarchy (Corrected)

```
Claims (fundamental unit)
  │
  ├─ Claim Categories (what is this claim about?)
  │
  └─ Source (attribution)
       │
       ├─ Source Categories (what is this source about?)
       │
       └─ Source Type:
            ├─ Episode → Segments → Evidence with timestamps
            └─ Document → Evidence with page numbers
```

### Key Principles

1. **Claims are the fundamental unit**
   - Everything queries claims
   - Sources are just attribution metadata

2. **Sources are organizational**
   - Provide context (who, when, where)
   - Two types: Episodes (segmented) or Documents (non-segmented)

3. **Episodes ≠ Primary Unit**
   - Episodes are just one type of source
   - Not all sources are episodes (documents exist too)

4. **Categories at both levels**
   - Claim categories: specific topics
   - Source categories: general topics
   - Both use WikiData vocabulary

### Architecture

**NOT:**
- ~~Episodes → Claims~~ (episode-centric)
- ~~Sources → Claims~~ (source-centric)

**YES:**
- **Claims → Sources** (claim-centric)
- Claims are queryable on their own
- Sources provide optional context via JOIN

This is a **claim-first knowledge base**, not a source library!

