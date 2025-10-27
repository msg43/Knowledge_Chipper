# Two-Level Category Architecture

## The Correct Model: Categories at Episode AND Claim Level

### Episode Categories (Broad - Max 3)
**Purpose:** "What is this entire source generally about?"  
**Constraint:** Maximum 3 categories per episode (forced by UI/validation)  
**Granularity:** GENERAL topics

### Claim Categories (Specific - Typically 1)
**Purpose:** "What is THIS specific claim about?"  
**Constraint:** Typically 1 primary category per claim  
**Granularity:** SPECIFIC topics

### WikiData's Role
**NOT a separate layer** - it's the **controlled vocabulary** that both episode and claim categories draw from. It provides:
- Standardized category names
- Category hierarchies (parent/child)
- Category descriptions
- Prevents LLM from inventing categories

---

## Example: Episode about Finance with Geopolitics Claim

```
Source: "CNBC Financial Report: Fed Policy & China Trade"

Episode Categories (max 3, GENERAL):
  1. Finance (Q43015)
  2. Monetary policy (Q186363)
  3. International trade (Q159810)

Claims from this episode:

Claim 1: "The Fed raised rates by 25 basis points"
  └─ Claim Category: Monetary policy (Q186363)
  └─ Episode Context: Finance, Monetary policy, International trade
  
Claim 2: "China's export growth slowed to 2.1%"
  └─ Claim Category: International trade (Q159810)
  └─ Episode Context: Finance, Monetary policy, International trade
  
Claim 3: "Taiwan tensions increase semiconductor supply risk"
  └─ Claim Category: Geopolitics (Q7163)  ← Different from episode!
  └─ Episode Context: Finance, Monetary policy, International trade
```

**Key insight:** Claim 3 is about geopolitics BUT it's from an episode primarily about finance. This dual context is valuable!

---

## Query Examples

### Find Claims with Category Context

```sql
-- Find geopolitics claims from finance episodes
SELECT 
    c.canonical AS claim_text,
    cc_claim.wikidata_id AS claim_category,
    wc_claim.category_name AS claim_category_name,
    
    -- Episode categories (inherited context)
    GROUP_CONCAT(wc_episode.category_name, ', ') AS episode_categories
    
FROM claims c
-- Claim's primary category
JOIN claim_categories cc_claim ON c.claim_id = cc_claim.claim_id AND cc_claim.is_primary = 1
JOIN wikidata_categories wc_claim ON cc_claim.wikidata_id = wc_claim.wikidata_id

-- Episode's categories (inherited context)
LEFT JOIN episode_categories ec ON c.episode_id = ec.episode_id
LEFT JOIN wikidata_categories wc_episode ON ec.wikidata_id = wc_episode.wikidata_id

WHERE wc_claim.category_name = 'Geopolitics'  -- Claim is about geopolitics
  AND EXISTS (
      SELECT 1 FROM episode_categories ec2
      JOIN wikidata_categories wc2 ON ec2.wikidata_id = wc2.wikidata_id
      WHERE ec2.episode_id = c.episode_id
        AND wc2.category_name = 'Finance'  -- But episode is about finance
  )
  
GROUP BY c.claim_id, c.canonical, cc_claim.wikidata_id, wc_claim.category_name;
```

**Result:**
```
claim_text                                  | claim_category | claim_category_name | episode_categories
------------------------------------------- | -------------- | ------------------- | ----------------------------------
Taiwan tensions increase semiconductor risk | Q7163          | Geopolitics        | Finance, Monetary policy, Int'l trade
```

**This tells you:** "This is a geopolitics claim from an episode that was primarily about finance" - valuable cross-domain signal!

---

## Schema (From Fully Normalized)

### WikiData Vocabulary (The Controlled List)

```sql
CREATE TABLE wikidata_categories (
    wikidata_id TEXT PRIMARY KEY,          -- "Q186363"
    category_name TEXT NOT NULL,           -- "Monetary policy"
    category_description TEXT,
    parent_wikidata_id TEXT,               -- For hierarchies
    level TEXT,                            -- 'general', 'specific' (hints for UI)
    
    FOREIGN KEY (parent_wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);
```

### Episode Categories (GENERAL - Max 3)

```sql
CREATE TABLE episode_categories (
    episode_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,             -- References wikidata_categories
    
    relevance_score REAL,
    confidence REAL,
    
    user_approved BOOLEAN DEFAULT 0,
    user_rejected BOOLEAN DEFAULT 0,
    source TEXT DEFAULT 'system',
    
    rank INTEGER CHECK (rank BETWEEN 1 AND 3),  -- Enforce max 3
    
    PRIMARY KEY (episode_id, wikidata_id),
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE,
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);

-- Trigger to enforce max 3 categories per episode
CREATE TRIGGER enforce_episode_category_limit
BEFORE INSERT ON episode_categories
WHEN (SELECT COUNT(*) FROM episode_categories WHERE episode_id = NEW.episode_id) >= 3
BEGIN
    SELECT RAISE(ABORT, 'Episode already has 3 categories');
END;
```

### Claim Categories (SPECIFIC - Typically 1)

```sql
CREATE TABLE claim_categories (
    claim_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,             -- References wikidata_categories
    
    relevance_score REAL,
    confidence REAL,
    
    user_approved BOOLEAN DEFAULT 0,
    user_rejected BOOLEAN DEFAULT 0,
    source TEXT DEFAULT 'system',
    
    is_primary BOOLEAN DEFAULT 0,          -- The main category
    
    PRIMARY KEY (claim_id, wikidata_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);

-- Ensure only one primary category per claim
CREATE UNIQUE INDEX idx_claim_primary_category 
ON claim_categories(claim_id) 
WHERE is_primary = 1;
```

---

## LLM Workflow with Constraints

### Episode Categorization

**Prompt to LLM:**
```
Analyze this episode and select the 3 most relevant general categories from the following WikiData categories:

[List of general WikiData categories]
- Finance (Q43015)
- Economics (Q8134)
- Politics (Q7163)
- Technology (Q11016)
- Science (Q336)
...

Choose exactly 3 categories that best describe the overall content.
Rank them 1-3 by relevance.
```

**LLM Response (constrained):**
```json
{
  "categories": [
    {"wikidata_id": "Q43015", "name": "Finance", "rank": 1, "relevance": 0.95},
    {"wikidata_id": "Q186363", "name": "Monetary policy", "rank": 2, "relevance": 0.89},
    {"wikidata_id": "Q159810", "name": "International trade", "rank": 3, "relevance": 0.72}
  ]
}
```

### Claim Categorization

**Prompt to LLM:**
```
Analyze this claim and select the single most specific WikiData category:

Claim: "Taiwan tensions increase semiconductor supply risk"

Choose from the following specific WikiData categories:
- Geopolitics (Q7163)
- Semiconductors (Q83958)
- Supply chain (Q507619)
- International relations (Q184827)
...

Choose the ONE most specific category that describes this claim.
```

**LLM Response (constrained):**
```json
{
  "category": {
    "wikidata_id": "Q7163",
    "name": "Geopolitics",
    "relevance": 0.92,
    "rationale": "The claim is about geopolitical tensions affecting supply"
  }
}
```

---

## Hierarchy: Episode → Claim Categories

### Relationship

```
Episode: "CNBC Financial Report"
  ├─ Categories (max 3, GENERAL):
  │    1. Finance
  │    2. Monetary policy
  │    3. International trade
  │
  └─ Claims:
       ├─ Claim 1: "Fed raised rates 25bps"
       │    └─ Category: Monetary policy (matches episode)
       │
       ├─ Claim 2: "China exports slowed"
       │    └─ Category: International trade (matches episode)
       │
       └─ Claim 3: "Taiwan tensions affect chips"
            └─ Category: Geopolitics (NEW - not in episode categories!)
```

**The value:** You can see that Claim 3 introduces a NEW topic (geopolitics) not in the episode's main categories. This is a cross-domain insight!

---

## Query Patterns

### 1. Episode Coverage Analysis

```sql
-- What does this episode cover?
SELECT 
    e.title,
    wc.category_name,
    ec.rank,
    ec.relevance_score,
    COUNT(DISTINCT c.claim_id) AS claim_count
FROM episodes e
JOIN episode_categories ec ON e.episode_id = ec.episode_id
JOIN wikidata_categories wc ON ec.wikidata_id = wc.wikidata_id
LEFT JOIN claims c ON e.episode_id = c.episode_id
LEFT JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.wikidata_id = ec.wikidata_id
WHERE e.episode_id = 'episode_abc123'
GROUP BY e.title, wc.category_name, ec.rank, ec.relevance_score
ORDER BY ec.rank;
```

**Result:**
```
title                        | category_name      | rank | relevance | claim_count
---------------------------- | ------------------ | ---- | --------- | -----------
CNBC Financial Report        | Finance            | 1    | 0.95      | 8
CNBC Financial Report        | Monetary policy    | 2    | 0.89      | 5
CNBC Financial Report        | International trade| 3    | 0.72      | 3
```

### 2. Cross-Domain Claims

```sql
-- Find claims that introduce topics NOT in the episode categories
SELECT 
    c.canonical,
    wc_claim.category_name AS claim_topic,
    GROUP_CONCAT(wc_episode.category_name, ', ') AS episode_topics
FROM claims c
JOIN claim_categories cc_claim ON c.claim_id = cc_claim.claim_id AND cc_claim.is_primary = 1
JOIN wikidata_categories wc_claim ON cc_claim.wikidata_id = wc_claim.wikidata_id
LEFT JOIN episode_categories ec ON c.episode_id = ec.episode_id
LEFT JOIN wikidata_categories wc_episode ON ec.wikidata_id = wc_episode.wikidata_id
WHERE cc_claim.wikidata_id NOT IN (
    -- Claim category is NOT in episode categories
    SELECT ec2.wikidata_id 
    FROM episode_categories ec2 
    WHERE ec2.episode_id = c.episode_id
)
GROUP BY c.claim_id, c.canonical, wc_claim.category_name;
```

**Result:**
```
canonical                                  | claim_topic  | episode_topics
------------------------------------------ | ------------ | ----------------------------------
Taiwan tensions affect semiconductor risk  | Geopolitics  | Finance, Monetary policy, Int'l trade
```

### 3. Topic Distribution

```sql
-- How do claim categories relate to episode categories?
SELECT 
    wc_episode.category_name AS episode_category,
    wc_claim.category_name AS claim_category,
    COUNT(*) AS claim_count
FROM claims c
JOIN episode_categories ec ON c.episode_id = ec.episode_id
JOIN wikidata_categories wc_episode ON ec.wikidata_id = wc_episode.wikidata_id
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
JOIN wikidata_categories wc_claim ON cc.wikidata_id = wc_claim.wikidata_id
GROUP BY wc_episode.category_name, wc_claim.category_name
ORDER BY claim_count DESC;
```

**Result:**
```
episode_category    | claim_category       | claim_count
------------------- | -------------------- | -----------
Finance             | Monetary policy      | 45
Finance             | Banking              | 23
Finance             | Stock markets        | 18
Finance             | Geopolitics          | 3  ← Cross-domain!
Monetary policy     | Interest rates       | 34
Monetary policy     | Inflation            | 28
```

---

## UI Workflow

### Episode Categorization

```
┌─ EPISODE CATEGORIES (max 3) ─────────────┐
│                                           │
│ Primary Topics (Rank 1-3):                │
│                                           │
│ 1. [Finance ▼]              [95%] ✓      │
│ 2. [Monetary policy ▼]      [89%] ✓      │
│ 3. [International trade ▼]  [72%] ✓      │
│                                           │
│ System suggestions:                       │
│   • Economics (85%)   [Replace #3?]       │
│   • Banking (67%)     [Replace #3?]       │
│                                           │
│ [Save Episode Categories]                 │
└───────────────────────────────────────────┘
```

### Claim Categorization

```
┌─ CLAIM CATEGORY ─────────────────────────┐
│                                           │
│ Claim: "Taiwan tensions affect chips"    │
│                                           │
│ Primary Category:                         │
│   [Geopolitics ▼]  [92%] ✓               │
│                                           │
│ Episode Context:                          │
│   • Finance (episode category)            │
│   • Monetary policy (episode category)    │
│   • International trade (episode category)│
│                                           │
│ ⚠️  This claim introduces a new topic!    │
│                                           │
│ Suggested alternatives:                   │
│   • Semiconductors (78%)  [Change?]       │
│   • Supply chain (71%)    [Change?]       │
│                                           │
│ [Save Claim Category]                     │
└───────────────────────────────────────────┘
```

---

## Benefits of Two-Level Categories

### 1. **Contextual Discovery**
"Show me geopolitics claims from finance episodes" - find cross-domain insights

### 2. **Granular Search**
"Find monetary policy claims" - specific claim-level search

### 3. **Broad Browse**
"Show me all finance episodes" - episode-level browsing

### 4. **Topic Evolution**
Track when episodes start mentioning new topics not in their main categories

### 5. **Recommendation**
"If you liked this finance episode that mentioned geopolitics, try these geopolitics episodes"

---

## Summary

### Three-Part System

1. **WikiData Categories** = Controlled vocabulary (the constraint)
   - Provides standardized category names
   - Prevents LLM hallucination
   - Enables hierarchies

2. **Episode Categories** = Broad topics (max 3)
   - "What is this episode generally about?"
   - General/high-level
   - Sets context for all claims

3. **Claim Categories** = Specific topics (typically 1)
   - "What is THIS claim specifically about?"
   - Specific/granular
   - Can differ from episode categories (cross-domain signals!)

### Architecture

```
wikidata_categories (vocabulary)
    ↑
    ├─ episode_categories (max 3, general)
    │    └─ "Episode is about Finance, Monetary Policy, Trade"
    │
    └─ claim_categories (typically 1, specific)
         └─ "Claim is about Geopolitics"
              └─ But episode context is Finance!
```

**Claims inherit episode context** while having their own specific category!

Is this the correct architecture?


