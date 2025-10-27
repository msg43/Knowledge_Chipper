# Final Category Architecture (CORRECTED)

## Two Category Systems (Not Three!)

### 1. **Platform Categories** (From Source - Optional)
- **What:** Categories that COME WITH the source (if any)
- **Examples:** 
  - YouTube: "News & Politics", "Education"
  - RSS: "Technology", "Business"
  - PDF/Word: None (don't have platform categories)
- **WikiData enforced?** ❌ NO
- **Storage:** `platform_categories` + `source_platform_categories`
- **Who creates:** The platform (YouTube, iTunes, etc.)

### 2. **Claim Categories** (Our Analysis - WikiData Enforced)
- **What:** Categories WE assign to individual claims
- **Examples:** "Monetary policy" (Q186363), "Geopolitics" (Q7188)
- **WikiData enforced?** ✅ YES
- **Storage:** `claim_categories` + `wikidata_categories`
- **Who creates:** Our HCE pipeline (via two-stage process)

---

## Sources Are Discovered TWO Ways

### Method 1: By Platform Categories

**Query:** "Find YouTube videos in 'News & Politics'"

```sql
SELECT m.*
FROM media_sources m
JOIN source_platform_categories spc ON m.source_id = spc.source_id
JOIN platform_categories pc ON spc.category_id = pc.category_id
WHERE pc.category_name = 'News & Politics'
  AND pc.platform = 'youtube';
```

### Method 2: By Claim Content (Aggregated)

**Query:** "Find episodes containing monetary policy claims"

```sql
SELECT 
    m.source_id,
    m.title,
    COUNT(DISTINCT c.claim_id) AS mp_claim_count
FROM media_sources m
JOIN claims c ON m.source_id = c.source_id
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id
WHERE wc.category_name = 'Monetary policy'
GROUP BY m.source_id, m.title
HAVING mp_claim_count > 0
ORDER BY mp_claim_count DESC;
```

**This computes episode topics from claims - doesn't require stored source categories!**

---

## Episode Detail View

```
┌─ EPISODE: "Fed Policy Discussion" ───────────┐
│                                               │
│ Source: YouTube (CNBC)                        │
│ Date: 2024-10-15                              │
│                                               │
│ ┌─ PLATFORM CATEGORIES ──────────────────┐   │
│ │ (What YouTube said)                    │   │
│ │ • News & Politics                      │   │
│ │ • Education                            │   │
│ └────────────────────────────────────────┘   │
│                                               │
│ ┌─ CONTENT ANALYSIS ─────────────────────┐   │
│ │ (Aggregated from claim categories)     │   │
│ │ Topics discussed in claims:            │   │
│ │ • Monetary policy (15 claims)          │   │
│ │ • Economics (8 claims)                 │   │
│ │ • Geopolitics (3 claims)               │   │
│ │ • Interest rates (5 claims)            │   │
│ └────────────────────────────────────────┘   │
│                                               │
│ 26 total claims  [Browse Claims by Topic →]  │
└───────────────────────────────────────────────┘
```

**Key insight:** Episode topics are DERIVED from claims, not stored separately!

---

## Data Flow

### Processing YouTube Video

```python
# 1. Get source metadata from YouTube
youtube_data = {
    'source_id': 'video_abc123',
    'title': 'Fed Policy Discussion',
    'uploader': 'CNBC',
    'platform_categories': ['News & Politics', 'Education'],  # From YouTube API
    'platform_tags': ['finance', 'fed', 'economics'],
}

# Store platform metadata
db.create_source(
    source_id='video_abc123',
    title='Fed Policy Discussion',
    source_type='youtube',
    uploader='CNBC',
)

# Store platform categories (NOT WikiData)
for platform_cat in youtube_data['platform_categories']:
    db.add_platform_category(
        source_id='video_abc123',
        platform='youtube',
        category_name=platform_cat  # "News & Politics" - as-is from YouTube
    )

# 2. Extract claims via HCE
claims = hce_pipeline.process(transcript)

# 3. Categorize EACH CLAIM (WikiData enforced)
for claim in claims:
    # Two-stage: free-form LLM → WikiData matching
    claim_category = categorizer.categorize_claim(
        claim_text=claim.canonical,
        llm_generate_func=llm.generate
    )
    # Result: {'wikidata_id': 'Q186363', 'category_name': 'Monetary policy'}
    
    db.store_claim_category(
        claim_id=claim.claim_id,
        wikidata_id=claim_category['wikidata_id']
    )

# 4. Episode topics = computed on-demand from claim categories
```

### Processing PDF Document

```python
# 1. PDF has NO platform categories
db.create_source(
    source_id='doc_xyz',
    title='Inflation Report',
    source_type='pdf',
    author='Bureau of Labor Statistics',
)

# NO platform categories to store (PDFs don't have them)

# 2. Extract claims via HCE
claims = hce_pipeline.process(pdf_text)

# 3. Categorize EACH CLAIM (WikiData enforced)
for claim in claims:
    claim_category = categorizer.categorize_claim(
        claim_text=claim.canonical,
        llm_generate_func=llm.generate
    )
    
    db.store_claim_category(
        claim_id=claim.claim_id,
        wikidata_id=claim_category['wikidata_id']
    )

# 4. Document topics = computed from claim categories (no platform categories to aggregate)
```

---

## Schema (Corrected)

```sql
-- Platform categories (from YouTube, RSS, etc.)
CREATE TABLE platform_categories (
    category_id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,           -- 'youtube', 'itunes', 'rss'
    category_name TEXT NOT NULL       -- "News & Politics" (whatever platform said)
);

CREATE TABLE source_platform_categories (
    source_id TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (source_id, category_id)
);

-- WikiData vocabulary (our controlled list)
CREATE TABLE wikidata_categories (
    wikidata_id TEXT PRIMARY KEY,
    category_name TEXT NOT NULL
);

-- Claim categories (ONLY place where WikiData is used)
CREATE TABLE claim_categories (
    claim_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,         -- WikiData enforced!
    is_primary BOOLEAN,
    relevance_score REAL,
    PRIMARY KEY (claim_id, wikidata_id),
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);

-- NO source_categories table!
-- Sources discovered via aggregating claim categories
```

---

## Query Patterns

### Find Episodes by Platform Category

```sql
-- What YouTube videos are in "News & Politics"?
SELECT m.title, m.uploader
FROM media_sources m
JOIN source_platform_categories spc ON m.source_id = spc.source_id
JOIN platform_categories pc ON spc.category_id = pc.category_id
WHERE pc.category_name = 'News & Politics'
  AND pc.platform = 'youtube';
```

### Find Episodes by Claim Topics (Aggregated)

```sql
-- What episodes have monetary policy claims?
SELECT 
    m.title,
    COUNT(DISTINCT c.claim_id) AS mp_claim_count
FROM media_sources m
JOIN claims c ON m.source_id = c.source_id
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
WHERE cc.wikidata_id = 'Q186363'  -- Monetary policy
GROUP BY m.source_id, m.title
HAVING mp_claim_count > 0;
```

### Episode Topic Distribution

```sql
-- What topics does this episode cover? (aggregated from claims)
SELECT 
    wc.category_name,
    COUNT(DISTINCT c.claim_id) AS claim_count,
    AVG(cc.relevance_score) AS avg_relevance
FROM claims c
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id
WHERE c.source_id = 'video_abc123'
GROUP BY wc.wikidata_id, wc.category_name
ORDER BY claim_count DESC;
```

**Result:**
```
category_name      | claim_count | avg_relevance
------------------ | ----------- | -------------
Monetary policy    | 15          | 0.89
Economics          | 8           | 0.82
Geopolitics        | 3           | 0.76
```

**This tells you what the episode covers based on its CLAIMS, not separate categorization!**

---

## Simplified View Creation

```sql
-- Materialized view for fast episode topic lookup
CREATE VIEW v_episode_topics AS
SELECT 
    m.source_id,
    m.title,
    wc.wikidata_id,
    wc.category_name,
    COUNT(DISTINCT c.claim_id) AS claim_count,
    AVG(cc.relevance_score) AS avg_relevance
FROM media_sources m
JOIN claims c ON m.source_id = c.source_id
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id
GROUP BY m.source_id, m.title, wc.wikidata_id, wc.category_name;

-- Now you can quickly query:
SELECT * FROM v_episode_topics WHERE category_name = 'Monetary policy';
```

---

## Summary

### What Changed

**REMOVED:**
- ❌ `source_categories` table (don't store WikiData categories at source level)
- ❌ "Semantic metadata" concept (confusing third category)

**KEPT:**
- ✅ `platform_categories` (what YouTube/RSS said)
- ✅ `claim_categories` (WikiData enforced)

### Categorization Logic

**Platform categories:**
- Stored at source level
- Come FROM the platform (YouTube, RSS)
- NOT WikiData enforced
- Some sources don't have any (PDFs)

**Claim categories:**
- Stored at claim level
- Created BY our HCE pipeline
- WikiData enforced (two-stage)
- Every claim should have one

**Episode/source discovery:**
- By platform category (direct lookup)
- By claim topics (aggregated via JOIN)
- NO separately stored source-level WikiData categories

### Two Types of Metadata (Not Three)

1. **Platform metadata** (from source)
   - uploader, upload_date, view_count
   - Platform categories, platform tags
   
2. **Our metadata** (our analysis)
   - tier, verification_status, notes
   - **Claim categories** (WikiData enforced) ← Part of "our metadata"
   - User tags (custom)
   - Workflow tracking

**Categories aren't a third type - they're part of "our metadata"!**

---

Is this now correct?
