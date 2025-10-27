# Categories Architecture (CORRECTED)

## Two Category Systems (Not Three!)

### 1. **Platform Categories** (From Source - Uncontrolled)
- **What:** Categories that come WITH the source (if any)
- **Examples:** YouTube: "News & Politics", RSS: "Technology"
- **WikiData enforced?** ❌ NO - accept as-is
- **Sources:** YouTube (always), RSS (sometimes), PDF/Word (never)
- **Table:** `platform_categories` + `source_platform_categories`
- **Purpose:** What the platform said about this content

### 2. **Claim Categories** (Our Analysis - WikiData Enforced)
- **What:** Categories WE assign to individual claims
- **Examples:** "Monetary policy" (Q186363), "Geopolitics" (Q7188)
- **WikiData enforced?** ✅ YES - via two-stage pipeline
- **Sources:** Our HCE analysis
- **Table:** `claim_categories` + `wikidata_categories`
- **Purpose:** What topics this claim discusses

---

## Episode/Source Categorization (DERIVED, Not Stored)

### Sources DON'T Get Their Own WikiData Categories

**WRONG:**
```sql
CREATE TABLE source_categories (  -- ❌ DELETE THIS
    source_id TEXT,
    wikidata_id TEXT,
    rank INTEGER
);
```

**RIGHT:**
```
Episode categories are DERIVED from:
1. Platform categories (what YouTube said)
2. Aggregated claim categories (what claims inside contain)

NOT stored separately!
```

### How to Find Episode Categories

**Query: "What topics does this episode cover?"**

```sql
-- Option 1: Platform categories
SELECT pc.category_name
FROM source_platform_categories spc
JOIN platform_categories pc ON spc.category_id = pc.category_id
WHERE spc.source_id = 'video_abc123';

-- Result: ["News & Politics", "Education"]  (from YouTube)

-- Option 2: Claim categories (aggregated)
SELECT 
    wc.category_name,
    COUNT(DISTINCT c.claim_id) AS claim_count
FROM claims c
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id
WHERE c.source_id = 'video_abc123'
GROUP BY wc.wikidata_id, wc.category_name
ORDER BY claim_count DESC;

-- Result: 
--   Monetary policy (15 claims)
--   Economics (8 claims)
--   Geopolitics (3 claims)
```

**Combined view:**
```
Episode "Fed Policy Discussion"
  
  Platform said:
    - "News & Politics"
    - "Education"
  
  Contains claims about:
    - Monetary policy (15 claims)
    - Economics (8 claims)
    - Geopolitics (3 claims)
```

---

## Search/Browse Patterns

### Search Episodes by Platform Category

```sql
-- Find all YouTube videos in "News & Politics"
SELECT DISTINCT m.*
FROM media_sources m
JOIN source_platform_categories spc ON m.source_id = spc.source_id
JOIN platform_categories pc ON spc.category_id = pc.category_id
WHERE pc.category_name = 'News & Politics'
  AND pc.platform = 'youtube';
```

### Search Episodes by Claim Topics

```sql
-- Find episodes containing monetary policy claims
SELECT DISTINCT 
    m.title,
    m.uploader,
    COUNT(DISTINCT c.claim_id) AS mp_claims
FROM media_sources m
JOIN claims c ON m.source_id = c.source_id
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id
WHERE wc.category_name = 'Monetary policy'
GROUP BY m.source_id, m.title, m.uploader
ORDER BY mp_claims DESC;
```

**This searches episodes by their CONTENT (claims), not by separately-assigned episode categories.**

---

## UI Implications

### Source Detail View

```
┌─ SOURCE: "Fed Policy Discussion" ────────────┐
│                                               │
│ Platform: YouTube                             │
│ Uploader: CNBC                                │
│ Date: 2024-10-15                              │
│                                               │
│ ┌─ PLATFORM CATEGORIES ──────────────────┐   │
│ │ (From YouTube - read only)             │   │
│ │ • News & Politics                      │   │
│ │ • Education                            │   │
│ └────────────────────────────────────────┘   │
│                                               │
│ ┌─ CONTENT ANALYSIS ─────────────────────┐   │
│ │ (From claim analysis)                  │   │
│ │ Topics covered in this source:         │   │
│ │ • Monetary policy (15 claims)          │   │
│ │ • Economics (8 claims)                 │   │
│ │ • Geopolitics (3 claims)               │   │
│ │ • Interest rates (5 claims)            │   │
│ └────────────────────────────────────────┘   │
│                                               │
│ 26 claims extracted  [View Claims →]         │
└───────────────────────────────────────────────┘
```

**Key:** Episode topics are COMPUTED from its claims, not stored.

### Claim Detail View

```
┌─ CLAIM DETAIL ────────────────────────────────┐
│                                               │
│ "The Fed raised rates by 25 basis points"    │
│                                               │
│ ┌─ CLAIM CATEGORY (WikiData enforced) ────┐  │
│ │ Primary: [Monetary policy ▼] (Q186363)  │  │
│ │                                          │  │
│ │ System suggested: Monetary policy (95%)  │  │
│ │ Alternatives:                            │  │
│ │   • Economics (72%)                      │  │
│ │   • Federal Reserve (68%)                │  │
│ │                                          │  │
│ │ [✓ Approved] [ Change Category ]         │  │
│ └──────────────────────────────────────────┘  │
│                                               │
│ From: CNBC (YouTube)                          │
│ Platform categories: News & Politics          │
│                                               │
└───────────────────────────────────────────────┘
```

---

## Corrected Schema

### Remove `source_categories` Table

```sql
-- ❌ DELETE THIS TABLE (we don't create our own source-level WikiData categories)
DROP TABLE IF EXISTS source_categories;
```

### Keep These Tables

```sql
-- ✅ Platform categories (from YouTube, RSS, etc.)
CREATE TABLE platform_categories (
    category_id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    category_name TEXT NOT NULL
);

CREATE TABLE source_platform_categories (
    source_id TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (source_id, category_id)
);

-- ✅ Claim categories (WikiData enforced)
CREATE TABLE wikidata_categories (
    wikidata_id TEXT PRIMARY KEY,
    category_name TEXT NOT NULL
);

CREATE TABLE claim_categories (
    claim_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,
    is_primary BOOLEAN,
    PRIMARY KEY (claim_id, wikidata_id),
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);
```

---

## Example Data Flow

### Processing a YouTube Video

```python
# 1. YouTube gives us platform categories
source_data = {
    'source_id': 'video_abc123',
    'title': 'Fed Policy Discussion',
    'platform_categories': ['News & Politics', 'Education']  # From YouTube API
}

# Store platform categories as-is
db.store_platform_categories(source_id, ['News & Politics', 'Education'])

# 2. Extract claims via HCE
claims = hce_pipeline.process(transcript)

# 3. For EACH claim, assign WikiData category
for claim in claims:
    # Two-stage: free-form LLM → WikiData mapping
    claim_category = categorizer.categorize_claim(
        claim_text=claim.canonical,
        llm_generate_func=llm.generate
    )
    # Result: {'wikidata_id': 'Q186363', 'category_name': 'Monetary policy'}
    
    db.store_claim_category(claim.claim_id, claim_category)

# 4. Episode topics = aggregation of claim categories (not stored!)
```

### Searching Episodes

```python
# Search by platform category
episodes = db.find_sources_by_platform_category('News & Politics')

# Search by content (claim topics)
episodes = db.find_sources_with_claims_about('Monetary policy')

# Both work, different data sources!
```

---

## Summary

**Corrected understanding:**

1. **Platform categories** exist at source level (from YouTube/RSS)
2. **Claim categories** exist at claim level (WikiData enforced)
3. **NO separate user-created source-level categories**
4. **Episode topics are COMPUTED** from claim categories, not stored

**Changes needed:**
- Remove `source_categories` table
- Keep `platform_categories` 
- Keep `claim_categories`
- Episodes discovered via claim category aggregation

Should I update the schema to remove `source_categories`?
