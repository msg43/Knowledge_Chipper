# Final Claim-Centric Architecture

## Core Principles (CORRECTED)

### 1. Claims Are the Fundamental Unit
```
CLAIMS (atomic knowledge)
  └─ attributed to → SOURCES (where claims came from)
                       ├─ Episodes (segmented: videos, podcasts)
                       └─ Documents (non-segmented: PDFs, articles)
```

### 2. Two Types of Metadata (Not Three!)

**Platform Metadata:**
- Everything FROM the source
- Includes: uploader, upload_date, view_count
- Includes: Platform categories ("News & Politics")
- Mutability: Immutable (what the platform said)

**Our Metadata:**
- Everything WE add through analysis
- Includes: tier, verification_status, evaluator_notes
- Includes: Claim categories (WikiData enforced)
- Includes: User tags (custom tags)
- Mutability: User-editable

**Categories are PART of "our metadata"** - not a separate third type!

### 3. Two Category Systems

**Platform Categories (Source Level):**
- From YouTube, RSS, etc.
- NOT WikiData enforced
- Some sources don't have any (PDFs, Word docs)
- Stored in: `platform_categories` + `source_platform_categories`

**Claim Categories (Claim Level):**
- From our HCE analysis
- WikiData enforced
- Every claim gets one
- Stored in: `claim_categories` + `wikidata_categories`

### 4. Episodes Are Discovered (Not Categorized)

**Sources/episodes do NOT get their own WikiData categories.**

Instead, discover episodes by:
1. Platform categories (direct: "Show me YouTube 'News & Politics' videos")
2. Claim topics (aggregated: "Show me episodes with monetary policy claims")

**Episode topics = aggregation of claim categories** (computed via JOIN, not stored)

---

## Complete Data Model

```
media_sources
  ├─ source_id, title, uploader, upload_date  (platform metadata)
  ├─ platform_categories → "News & Politics"   (platform metadata)
  └─ claims
       ├─ canonical, tier, verification        (our metadata)
       └─ claim_categories → "Monetary policy" (our metadata, WikiData enforced)

Episode topics = GROUP BY claim_categories (computed, not stored)
```

---

## Schema Tables

### Core Tables
```sql
-- Sources (attribution)
media_sources
episodes (1-to-1 with media_sources where source_type='episode')
segments (temporal chunks for episodes)

-- Claims (fundamental unit)
claims (global IDs, reference sources)
evidence_spans
claim_relations
```

### Entity Tables (Normalized)
```sql
people → claim_people
concepts → claim_concepts
jargon_terms → claim_jargon
```

### Category Tables
```sql
-- Platform categories (NOT WikiData)
platform_categories
source_platform_categories

-- WikiData vocabulary (controlled)
wikidata_categories
wikidata_aliases

-- Claim categories (WikiData enforced)
claim_categories

-- NO source_categories table!
```

### User Workflow
```sql
user_tags → claim_tags
export_destinations → claim_exports
```

---

## Query Examples

### 1. Find Episodes by Platform Category

```sql
SELECT m.title
FROM media_sources m
JOIN source_platform_categories spc ON m.source_id = spc.source_id
JOIN platform_categories pc ON spc.category_id = pc.category_id
WHERE pc.category_name = 'News & Politics';
```

### 2. Find Episodes by Claim Topics

```sql
-- Episodes with monetary policy claims
SELECT 
    m.title,
    COUNT(DISTINCT c.claim_id) AS mp_claims
FROM media_sources m
JOIN claims c ON m.source_id = c.source_id
JOIN claim_categories cc ON c.claim_id = cc.claim_id
WHERE cc.wikidata_id = 'Q186363'
GROUP BY m.source_id, m.title;
```

### 3. Episode Topic Analysis

```sql
-- What does this episode cover? (aggregated from claims)
SELECT 
    wc.category_name AS topic,
    COUNT(DISTINCT c.claim_id) AS claims_about_topic
FROM claims c
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id
WHERE c.source_id = 'video_abc123'
GROUP BY wc.wikidata_id, wc.category_name
ORDER BY claims_about_topic DESC;
```

### 4. Cross-Platform Topic Search

```sql
-- Find all sources (YouTube, PDF, RSS) with monetary policy claims
SELECT 
    m.source_id,
    m.title,
    m.source_type,
    COUNT(DISTINCT c.claim_id) AS mp_claims
FROM media_sources m
JOIN claims c ON m.source_id = c.source_id
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
WHERE cc.wikidata_id = 'Q186363'
GROUP BY m.source_id, m.title, m.source_type
ORDER BY mp_claims DESC;
```

**Works for YouTube, PDFs, RSS - same query!**

---

## WikiData Enforcement (Claim Level Only)

### Two-Stage Pipeline (For Claims)

```python
# Stage 1: Free-form LLM
claim = "The Fed raised rates by 25 basis points"
response = llm.generate("What topic is this claim about?")
# Output: "Central banking policy"

# Stage 2: Map to WikiData
categorizer = WikiDataCategorizer()
match = categorizer.find_closest_categories("Central banking policy", top_k=1)
# Output: {'wikidata_id': 'Q66344', 'category_name': 'Central banking', 'similarity': 0.94}

# Store (FK constraint enforces WikiData)
db.store_claim_category(claim_id, wikidata_id='Q66344')
```

### Platform Categories (No Enforcement)

```python
# Accept whatever YouTube says
youtube_categories = ["News & Politics", "Education"]

# Store as-is (no WikiData mapping)
for cat_name in youtube_categories:
    db.store_platform_category(
        source_id='video_abc123',
        platform='youtube',
        category_name=cat_name  # Not mapped to WikiData
    )
```

---

## Summary

### Corrected Architecture

**Two category systems:**
1. Platform categories (source level, not WikiData)
2. Claim categories (claim level, WikiData enforced)

**NO:**
- ❌ Separate source-level WikiData categories
- ❌ "Semantic metadata" as a third type
- ❌ Stored episode/source categorization

**YES:**
- ✅ Platform categories stored (if source has them)
- ✅ Claim categories stored (WikiData enforced)
- ✅ Episode topics computed from claims (not stored)

### Two Types of Metadata

1. **Platform metadata** (from source)
   - uploader, dates, metrics
   - Platform categories
   
2. **Our metadata** (our analysis)
   - tier, verification, notes
   - Claim categories (WikiData enforced)
   - User tags

**Categories are part of "our metadata" - not a separate type!**

### Benefits

✅ **Simpler** - one less table to maintain  
✅ **More accurate** - episode topics reflect actual content  
✅ **Flexible** - works for YouTube (has platform cats) AND PDFs (doesn't)  
✅ **Queryable** - can search by platform OR content  
✅ **Claim-centric** - claims drive topic discovery  

Schema is now correct!

