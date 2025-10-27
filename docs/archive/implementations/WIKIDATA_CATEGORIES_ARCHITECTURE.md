# WikiData Categories in Claim-Centric Architecture

## The Three Types of Metadata

### 1. **Source Metadata** (Attribution - WHO/WHEN/WHERE)
**Table:** `media_sources`  
**Purpose:** "Who said this? When? Where?"  
**Examples:** `uploader`, `upload_date`, `view_count`  
**Mutability:** Immutable (from platform)

### 2. **Claim Metadata** (Curation - YOUR ANALYSIS)
**Table:** `hce_claims`  
**Purpose:** "How important? Verified? Reviewed?"  
**Examples:** `tier`, `evaluator_notes`, `verification_status`  
**Mutability:** User-editable

### 3. **Semantic Metadata** (Classification - WHAT IS THIS ABOUT?)
**Table:** `hce_structured_categories` (new) OR `hce_claims.structured_categories_json`  
**Purpose:** "What topics/domains does this claim discuss?"  
**Examples:** WikiData categories like "Monetary Policy", "Federal Reserve System", "Economics"  
**Mutability:** System-generated, user-refinable

---

## WikiData Categories Are Semantic Metadata

### What They Represent

WikiData categories classify the **content/topic** of a claim, not the source or your workflow.

**Example:**
```
Claim: "The Fed raised rates by 25 basis points"

Source Metadata (WHO/WHEN/WHERE):
  - uploader: "CNBC"
  - upload_date: "2024-10-15"
  - source_type: "youtube"

Claim Metadata (YOUR ANALYSIS):
  - tier: "A"
  - verification_status: "verified"
  - user_tags: ["urgent"]

Semantic Metadata (WHAT IT'S ABOUT):  ← WikiData categories go here
  - "Monetary policy" (Q186363)
  - "Federal Reserve System" (Q53536)
  - "Interest rate" (Q82580)
  - "Central banking" (Q66344)
```

---

## Current Implementation

Looking at your existing schema (`unified_schema.sql`):

```sql
CREATE TABLE IF NOT EXISTS hce_claims (
  ...
  -- Structured categories (WikiData)
  structured_categories_json TEXT,
  category_relevance_scores_json TEXT,
  ...
);
```

**Problem:** This embeds categories as JSON, making them hard to query.

---

## Recommended Architecture: Separate Categories Table

### Why Separate?

1. **Queryability:** "Find all claims about 'Monetary Policy'"
2. **Normalization:** Same category used across many claims
3. **Relationships:** Categories have hierarchies (parent/child)
4. **Metadata about categories:** Relevance scores, confidence, user overrides

### Proposed Schema

```sql
-- 1. Categories table (catalog of all WikiData categories)
CREATE TABLE hce_categories (
    category_id TEXT PRIMARY KEY,           -- "Q186363" (WikiData ID)
    category_name TEXT NOT NULL,            -- "Monetary policy"
    category_description TEXT,              -- WikiData description
    parent_category_id TEXT,                -- For hierarchies
    wikidata_url TEXT,                      -- https://www.wikidata.org/wiki/Q186363
    aliases_json TEXT,                      -- Alternative names
    created_at DATETIME DEFAULT (datetime('now')),
    FOREIGN KEY (parent_category_id) REFERENCES hce_categories(category_id)
);

CREATE INDEX idx_hce_categories_name ON hce_categories(category_name);

-- 2. Claim-Category mapping (many-to-many)
CREATE TABLE hce_claim_categories (
    claim_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    
    -- System-generated scores
    relevance_score REAL,                   -- 0.0 to 1.0 (how relevant is this category?)
    confidence REAL,                        -- 0.0 to 1.0 (how confident is the system?)
    source TEXT DEFAULT 'system',           -- 'system' or 'user'
    
    -- User overrides
    user_approved BOOLEAN DEFAULT 0,        -- User confirmed this category
    user_rejected BOOLEAN DEFAULT 0,        -- User rejected this category
    user_relevance_override REAL,          -- User can override relevance score
    
    -- Context
    context_quote TEXT,                     -- Which part of claim triggered this category?
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),
    
    PRIMARY KEY (claim_id, category_id),
    FOREIGN KEY (claim_id) REFERENCES hce_claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES hce_categories(category_id) ON DELETE CASCADE
);

CREATE INDEX idx_claim_categories_category ON hce_claim_categories(category_id);
CREATE INDEX idx_claim_categories_relevance ON hce_claim_categories(relevance_score DESC);
```

---

## How Categories Work at Different Levels

### Claim-Level Categories (Primary)

**Most granular - what is THIS specific claim about?**

```sql
-- Find all claims about "Monetary policy"
SELECT 
    c.canonical,
    c.tier,
    cc.relevance_score,
    cat.category_name
FROM hce_claims c
JOIN hce_claim_categories cc ON c.claim_id = cc.claim_id
JOIN hce_categories cat ON cc.category_id = cat.category_id
WHERE cat.category_name = 'Monetary policy'
  AND cc.relevance_score > 0.7
ORDER BY cc.relevance_score DESC;
```

### Source-Level Categories (Aggregated)

**What topics does this entire video/document cover?**

```sql
-- Get top categories for a source
SELECT 
    cat.category_name,
    COUNT(*) AS claim_count,
    AVG(cc.relevance_score) AS avg_relevance
FROM hce_claims c
JOIN hce_claim_categories cc ON c.claim_id = cc.claim_id
JOIN hce_categories cat ON cc.category_id = cat.category_id
WHERE c.source_id = 'video_abc123'
GROUP BY cat.category_id, cat.category_name
ORDER BY claim_count DESC, avg_relevance DESC
LIMIT 10;
```

**Result:**
```
category_name           | claim_count | avg_relevance
----------------------- | ----------- | -------------
Monetary policy         | 15          | 0.89
Federal Reserve System  | 12          | 0.85
Interest rate          | 10          | 0.82
Inflation              | 8           | 0.78
Central banking        | 7           | 0.75
```

This tells you: **"This video is primarily about monetary policy and the Federal Reserve"**

### Global Categories (Knowledge Base)

**What topics does your entire knowledge base cover?**

```sql
-- Top categories across all claims
SELECT 
    cat.category_name,
    COUNT(DISTINCT cc.claim_id) AS total_claims,
    COUNT(DISTINCT c.source_id) AS total_sources,
    AVG(cc.relevance_score) AS avg_relevance
FROM hce_categories cat
JOIN hce_claim_categories cc ON cat.category_id = cc.category_id
JOIN hce_claims c ON cc.claim_id = c.claim_id
GROUP BY cat.category_id, cat.category_name
ORDER BY total_claims DESC
LIMIT 20;
```

---

## Complete Metadata Picture for a Claim

```json
{
  "claim": {
    "id": "claim_abc123",
    "text": "The Fed raised rates by 25 basis points",
    
    // === CLAIM METADATA (user-editable) ===
    "tier": "A",
    "verification_status": "verified",
    "evaluator_notes": "Confirmed by Fed press release",
    "user_tags": ["urgent", "monetary-policy"],
    
    // === SEMANTIC METADATA (system + user refinable) ===
    "categories": [
      {
        "id": "Q186363",
        "name": "Monetary policy",
        "relevance": 0.95,
        "user_approved": true,
        "source": "system"
      },
      {
        "id": "Q53536",
        "name": "Federal Reserve System",
        "relevance": 0.92,
        "user_approved": true,
        "source": "system"
      },
      {
        "id": "Q82580",
        "name": "Interest rate",
        "relevance": 0.88,
        "user_approved": false,
        "source": "system"
      }
    ],
    
    // === SOURCE METADATA (immutable, via JOIN) ===
    "source": {
      "id": "video_xyz",
      "title": "CNBC Fed Meeting Coverage",
      "uploader": "CNBC",
      "upload_date": "2024-10-15",
      "view_count": 120000,
      "source_type": "youtube"
    }
  }
}
```

---

## Category Hierarchy Example

WikiData categories have **parent-child relationships**:

```
Economics (Q8134)
  └─ Monetary economics (Q1369832)
      └─ Monetary policy (Q186363)
          ├─ Interest rate policy (Q...)
          ├─ Quantitative easing (Q185038)
          └─ Central bank policy (Q...)
```

**Query for hierarchical navigation:**

```sql
-- Get category hierarchy for a claim
WITH RECURSIVE category_tree AS (
  -- Start with claim's direct categories
  SELECT 
    cc.claim_id,
    c.category_id,
    c.category_name,
    c.parent_category_id,
    1 AS depth
  FROM hce_claim_categories cc
  JOIN hce_categories c ON cc.category_id = c.category_id
  WHERE cc.claim_id = 'claim_abc123'
  
  UNION ALL
  
  -- Get parent categories
  SELECT 
    ct.claim_id,
    p.category_id,
    p.category_name,
    p.parent_category_id,
    ct.depth + 1
  FROM category_tree ct
  JOIN hce_categories p ON ct.parent_category_id = p.category_id
  WHERE ct.depth < 5  -- Limit depth
)
SELECT * FROM category_tree
ORDER BY depth, category_name;
```

**Result:**
```
depth | category_name
----- | -----------------------
1     | Interest rate policy       ← Direct category
1     | Monetary policy            ← Direct category
2     | Monetary economics         ← Parent of "Monetary policy"
3     | Economics                  ← Grandparent
```

---

## User Workflow with Categories

### System Auto-Generates

When a claim is extracted, the HCE pipeline automatically:
1. Analyzes the claim text
2. Identifies relevant WikiData categories
3. Assigns relevance scores
4. Stores in `hce_claim_categories`

### User Can Refine

```
┌─ CLAIM CATEGORIES (System + User) ────────────────┐
│                                                    │
│ ✓ Monetary policy              [95%] [✓ Approved] │
│ ✓ Federal Reserve System        [92%] [✓ Approved] │
│ ✓ Interest rate                 [88%] [ Approve? ] │
│ ✗ Banking regulation            [45%] [✗ Reject  ] │
│                                                    │
│ [+ Add Category Manually]                         │
│                                                    │
│ Suggested:                                         │
│   • Quantitative easing (72%)  [+ Add]            │
│   • Central banking (68%)      [+ Add]            │
└────────────────────────────────────────────────────┘
```

**User actions:**
- ✓ Approve system-suggested categories (sets `user_approved = 1`)
- ✗ Reject incorrect categories (sets `user_rejected = 1`, excludes from queries)
- Override relevance scores (sets `user_relevance_override`)
- Manually add missing categories (sets `source = 'user'`)

---

## Query Examples

### Find Related Claims via Shared Categories

```sql
-- Find claims similar to claim_abc123 by category overlap
SELECT 
    c.claim_id,
    c.canonical,
    COUNT(DISTINCT cc.category_id) AS shared_categories,
    AVG(cc.relevance_score) AS avg_relevance
FROM hce_claims c
JOIN hce_claim_categories cc ON c.claim_id = cc.claim_id
WHERE cc.category_id IN (
    -- Categories of the original claim
    SELECT category_id 
    FROM hce_claim_categories 
    WHERE claim_id = 'claim_abc123'
)
AND c.claim_id != 'claim_abc123'
GROUP BY c.claim_id, c.canonical
HAVING shared_categories >= 2
ORDER BY shared_categories DESC, avg_relevance DESC
LIMIT 10;
```

### Browse Claims by Topic

```sql
-- Browse all claims about "Monetary policy" with context
SELECT 
    c.canonical,
    c.tier,
    m.uploader AS author,
    m.upload_date,
    cc.relevance_score,
    cc.user_approved
FROM hce_claims c
JOIN hce_claim_categories cc ON c.claim_id = cc.claim_id
JOIN hce_categories cat ON cc.category_id = cat.category_id
JOIN media_sources m ON c.source_id = m.media_id
WHERE cat.category_name = 'Monetary policy'
  AND cc.relevance_score > 0.7
  AND (cc.user_rejected IS NULL OR cc.user_rejected = 0)
ORDER BY c.tier ASC, cc.relevance_score DESC;
```

### Topic Coverage Analysis

```sql
-- What topics does source X cover?
SELECT 
    cat.category_name,
    cat.parent_category_id,
    COUNT(DISTINCT c.claim_id) AS claim_count,
    AVG(cc.relevance_score) AS avg_relevance,
    SUM(CASE WHEN cc.user_approved = 1 THEN 1 ELSE 0 END) AS user_approved_count
FROM hce_claims c
JOIN hce_claim_categories cc ON c.claim_id = cc.claim_id
JOIN hce_categories cat ON cc.category_id = cat.category_id
WHERE c.source_id = 'video_xyz'
GROUP BY cat.category_id, cat.category_name
HAVING claim_count >= 2
ORDER BY claim_count DESC, avg_relevance DESC;
```

---

## Migration from Current Schema

### Current (embedded JSON)
```sql
hce_claims:
  structured_categories_json: '[
    {"id": "Q186363", "name": "Monetary policy", "relevance": 0.95},
    {"id": "Q53536", "name": "Federal Reserve", "relevance": 0.92}
  ]'
```

### Migrate to Normalized Tables

```sql
-- 1. Extract unique categories from all claims
INSERT INTO hce_categories (category_id, category_name)
SELECT DISTINCT 
    json_extract(value, '$.id') AS category_id,
    json_extract(value, '$.name') AS category_name
FROM hce_claims,
     json_each(structured_categories_json)
WHERE structured_categories_json IS NOT NULL;

-- 2. Create claim-category mappings
INSERT INTO hce_claim_categories (claim_id, category_id, relevance_score, source)
SELECT 
    c.claim_id,
    json_extract(value, '$.id') AS category_id,
    json_extract(value, '$.relevance') AS relevance_score,
    'system' AS source
FROM hce_claims c,
     json_each(c.structured_categories_json)
WHERE c.structured_categories_json IS NOT NULL;

-- 3. Drop old JSON columns (after verification)
ALTER TABLE hce_claims DROP COLUMN structured_categories_json;
ALTER TABLE hce_claims DROP COLUMN category_relevance_scores_json;
```

---

## Summary: Where Categories Fit

### The Complete Metadata Layers

```
CLAIM
  │
  ├─ Source Metadata (WHO/WHEN/WHERE)
  │    └─ via JOIN to media_sources
  │         └─ uploader, upload_date, view_count (immutable)
  │
  ├─ Claim Metadata (YOUR CURATION)
  │    └─ in hce_claims table
  │         └─ tier, notes, verification, tags (user-editable)
  │
  └─ Semantic Metadata (WHAT IT'S ABOUT)
       └─ via JOIN to hce_claim_categories → hce_categories
            └─ WikiData categories, relevance scores (system + user refinable)
```

### Query Pattern

```sql
SELECT 
    -- CLAIM TEXT
    c.canonical,
    
    -- CLAIM METADATA (yours)
    c.tier, c.verification_status,
    
    -- SOURCE METADATA (platform)
    m.uploader, m.upload_date,
    
    -- SEMANTIC METADATA (categories)
    cat.category_name, cc.relevance_score
    
FROM hce_claims c
JOIN media_sources m ON c.source_id = m.media_id
JOIN hce_claim_categories cc ON c.claim_id = cc.claim_id
JOIN hce_categories cat ON cc.category_id = cat.category_id;
```

**One query, complete context!**

---

## Recommendation

**Normalize categories into separate tables:**

✅ Better queryability ("find all claims about X topic")  
✅ User can approve/reject/refine categories  
✅ Supports hierarchical browsing  
✅ Enables topic-based discovery  
✅ No JSON parsing in queries  

Would you like me to implement this normalized category schema?
