# Claim-Centric Implementation Complete

## What Was Implemented

### ✅ 1. Claim-Centric Database Schema

**File:** `src/knowledge_system/database/migrations/claim_centric_schema.sql`

**Architecture:**
```
Claims (fundamental unit)
  └─ attribute to → Sources (organizational)
                      ├─ Episodes (segmented)
                      └─ Documents (non-segmented)
```

**Key Changes:**
- Claims have **global unique IDs** (not scoped to episodes)
- Claims reference `source_id` (direct link)
- Episodes are **1-to-1 with sources** where `source_type='episode'`
- **Zero JSON fields** - everything is normalized tables
- **Two-level categories**: `source_categories` (max 3) + `claim_categories` (typically 1)

**Tables Created:**
- `media_sources` - Attribution metadata
- `episodes` - Segmented sources (with summaries)
- `segments` - Temporal chunks
- `claims` - Atomic knowledge units ⭐
- `evidence_spans` - Supporting quotes
- `claim_relations` - Claim-to-claim relationships
- `people` + `claim_people` - Normalized person catalog + mentions
- `concepts` + `claim_concepts` - Normalized concept catalog + mentions
- `jargon_terms` + `claim_jargon` - Normalized jargon catalog + usage
- `wikidata_categories` - Controlled vocabulary
- `source_categories` - Source WikiData categories (max 3)
- `claim_categories` - Claim WikiData categories (typically 1)
- `user_tags` + `claim_tags` - User tagging system
- `platform_categories` + `source_platform_categories` - YouTube/etc. categories
- `export_destinations` + `claim_exports` - Export tracking

### ✅ 2. SQLAlchemy Models

**File:** `src/knowledge_system/database/claim_models.py`

**Key Models:**
- `Claim` - The fundamental model with relationships to everything
- `MediaSource` - Attribution metadata
- `Episode` - Summaries stored here (not separate table)
- `WikiDataCategory` - Controlled vocabulary for categorization
- `ClaimCategory` / `SourceCategory` - Two-level categorization
- All entities normalized (Person, Concept, JargonTerm)

**Relationships:**
- Claims have many-to-many with people, concepts, jargon, categories, tags
- Evidence and relations are one-to-many from claims
- Sources have one-to-many to claims

### ✅ 3. WikiData Vocabulary & Enforcement

**Files:**
- `src/knowledge_system/database/wikidata_seed.json` - Initial vocabulary (40 categories)
- `src/knowledge_system/database/load_wikidata_vocab.py` - Loader script
- `src/knowledge_system/services/wikidata_categorizer.py` - Two-stage pipeline

**Two-Stage Pipeline:**

**Stage 1: Free-Form LLM**
```python
# Clean prompt (no category list!)
prompt = "Identify the 3 most important topics in this content"
response = llm.generate(prompt)
# Output: ["Economics", "Central banking", "Monetary policy"]
```

**Stage 2: Embedding-Based Matching**
```python
# Map to WikiData via semantic similarity
categorizer = WikiDataCategorizer()
matches = categorizer.find_closest_categories("Central banking", top_k=3)
# Output: [
#   {'wikidata_id': 'Q66344', 'name': 'Central banking', 'similarity': 0.98}
# ]
```

**Auto-Approval:**
- Similarity > 0.85: ✅ Auto-accept
- Similarity 0.6-0.85: ⚠️ User review
- Similarity < 0.6: ❌ Flag for vocabulary expansion

**Benefits:**
- ✅ Clean prompts (no 200-category lists)
- ✅ Fast (no token masking)
- ✅ Dynamic (update JSON file anytime)
- ✅ Scalable (works with thousands of categories)

### ✅ 4. Claim-Centric Storage

**File:** `src/knowledge_system/database/claim_store.py`

**Replaces:** Old `HCEStore` (which was episode-centric)

**Key Method:**
```python
claim_store.upsert_pipeline_outputs(
    outputs,
    source_id='video_abc123',
    source_type='episode',
    episode_title='Fed Policy Discussion'
)
```

**What it does:**
- Stores claims with global IDs: `{source_id}_{claim_id}`
- Links claims to sources (not vice versa)
- Normalizes people, concepts, jargon (no JSON)
- Maps categories to WikiData vocabulary
- Stores summaries in episodes table (not separate summaries table)

**Query Methods:**
- `get_claim(claim_id)` - Get claim with source context
- `get_claims_by_category(wikidata_id)` - Topic-based search
- `get_claims_by_source(source_id)` - Source attribution

### ✅ 5. Integration with System2Orchestrator

**File:** `src/knowledge_system/core/system2_orchestrator_mining.py`

**Updated to:**
- Use `ClaimStore` instead of `HCEStore`
- Pass `source_id` instead of `video_id`
- Remove old Summary table creation
- Summaries now stored in episodes table

### ✅ 6. Migration Script

**File:** `src/knowledge_system/database/migrate_to_claim_centric.py`

**Usage:**
```bash
python -m src.knowledge_system.database.migrate_to_claim_centric old.db new.db
```

**What it migrates:**
- media_sources → media_sources (1-to-1)
- hce_episodes → episodes (1-to-1)
- hce_segments → segments (1-to-1)
- hce_claims → claims (WITH GLOBAL IDs)
- hce_evidence_spans → evidence_spans
- hce_relations → claim_relations (WITH GLOBAL IDs)
- hce_people → people + claim_people (NORMALIZED)
- hce_concepts → concepts + claim_concepts (NORMALIZED)
- hce_jargon → jargon_terms + claim_jargon (NORMALIZED)

---

## Key Architecture Decisions

### 1. Claims Are Fundamental

**Query pattern:**
```sql
-- Primary query (claim-centric)
SELECT canonical FROM claims WHERE tier = 'A';

-- Add source context (when needed)
SELECT c.canonical, m.uploader, m.upload_date
FROM claims c
LEFT JOIN media_sources m ON c.source_id = m.source_id;
```

Claims are queryable independently. Sources are optional context.

### 2. Sources Are Attribution

Sources answer: "Where did this claim come from?"
- Uploader/author
- Publication date
- Platform metrics (views, likes)
- Source type (episode vs document)

**NOT:** "What claims does this source contain?" (source-centric ❌)
**BUT:** "What source is this claim from?" (claim-centric ✅)

### 3. Episodes Are a Source Type

```
media_sources (source_type='episode')
  ↓ 1-to-1
episodes (has summaries + metrics)
  ↓ 1-to-many
segments (temporal chunks)
```

**NOT all sources are episodes** - documents don't have episodes or segments.

### 4. Two-Level Categories

**Source Categories (max 3, general):**
- "This source is generally about Finance, Monetary Policy, Trade"
- Stored in `source_categories`
- WikiData enforced via two-stage pipeline

**Claim Categories (typically 1, specific):**
- "This claim is specifically about Geopolitics"
- Stored in `claim_categories`
- Can differ from source categories (cross-domain signals!)

### 5. WikiData as Controlled Vocabulary

**NOT a third metadata layer** - it's the constraint mechanism:
- Prevents LLM from hallucinating categories
- Provides standardized names
- Enables hierarchies (Monetary Policy → Economics)
- Enforced via foreign keys

**Two-Stage Enforcement:**
1. LLM generates free-form (clean prompt)
2. Map to WikiData via embeddings (fast matching)
3. Auto-approve high confidence, flag low confidence for review

### 6. No JSON Fields

**Everything is normalized:**
- ❌ `user_tags_json` → ✅ `user_tags` + `claim_tags` tables
- ❌ `scores_json` → ✅ `importance_score`, `specificity_score`, `verifiability_score` columns
- ❌ `external_ids_json` → ✅ `person_external_ids` table
- ❌ `aliases_json` → ✅ `concept_aliases` table
- ❌ `structured_categories_json` → ✅ `claim_categories` table

**Benefits:**
- Queryable with SQL WHERE/JOIN
- Indexed for performance
- FK constraints enforced
- No JSON parsing needed

---

## File Structure

```
src/knowledge_system/database/
  ├── migrations/
  │   └── claim_centric_schema.sql       ⭐ New schema
  ├── claim_models.py                    ⭐ New models
  ├── claim_store.py                     ⭐ New storage layer
  ├── wikidata_seed.json                 ⭐ Category vocabulary
  ├── load_wikidata_vocab.py             ⭐ Vocab loader
  └── migrate_to_claim_centric.py        ⭐ Migration script

src/knowledge_system/services/
  └── wikidata_categorizer.py            ⭐ Two-stage categorization

src/knowledge_system/core/
  └── system2_orchestrator_mining.py     ✏️ Updated to use ClaimStore

.cursor/rules/
  └── claim-centric-architecture.mdc     ✏️ Updated rule
```

---

## Usage Examples

### Store Pipeline Outputs (Claim-Centric)

```python
from src.knowledge_system.database import DatabaseService
from src.knowledge_system.database.claim_store import ClaimStore

db = DatabaseService()
claim_store = ClaimStore(db)

# Store outputs
claim_store.upsert_pipeline_outputs(
    pipeline_outputs,
    source_id='video_abc123',
    source_type='episode',
    episode_title='Fed Policy Discussion'
)
```

### Query Claims by Topic

```python
# Find all monetary policy claims
claims = claim_store.get_claims_by_category(
    wikidata_id='Q186363',  # Monetary policy
    tier_filter=['A', 'B'],
    limit=50
)

for claim in claims:
    print(f"{claim['tier']}: {claim['canonical']}")
    print(f"   From: {claim['source_author']} ({claim['source_title']})")
```

### Query Claims by Source

```python
# Find all claims from a source
claims = claim_store.get_claims_by_source(
    source_id='video_abc123',
    include_evidence=True
)

for claim in claims:
    print(f"{claim['canonical']}")
    for evidence in claim.get('evidence', []):
        print(f"  Evidence: {evidence['quote']}")
```

### Categorize Content (Two-Stage)

```python
from src.knowledge_system.services.wikidata_categorizer import WikiDataCategorizer

categorizer = WikiDataCategorizer()

def llm_generate(prompt):
    # Your LLM call here
    return llm.generate_structured(prompt)

# Categorize source
source_categories = categorizer.categorize_source(
    source_content="Transcript about Fed policy...",
    llm_generate_func=llm_generate,
    auto_approve_threshold=0.85
)

# Results:
# [
#   {
#     'wikidata_id': 'Q186363',
#     'category_name': 'Monetary policy',
#     'rank': 1,
#     'relevance_score': 0.92,
#     'auto_approved': True,  # > 0.85
#     'freeform_input': 'Central banking policy'
#   },
#   ...
# ]
```

---

## Next Steps

### 1. Load WikiData Vocabulary

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python -m src.knowledge_system.database.load_wikidata_vocab
```

This loads the 40 seed categories into `wikidata_categories` table.

### 2. Test the Schema

```bash
# Create new database with claim-centric schema
sqlite3 knowledge_system_claim_centric.db < src/knowledge_system/database/migrations/claim_centric_schema.sql

# Test queries
sqlite3 knowledge_system_claim_centric.db "SELECT * FROM wikidata_categories;"
```

### 3. Test Two-Stage Categorization

```bash
# Test WikiData matching
python -m src.knowledge_system.services.wikidata_categorizer
```

This will test matching free-form categories to WikiData.

### 4. Update DatabaseService

Update `src/knowledge_system/database/service.py` to use the new schema:
- Point `_ensure_unified_hce_schema()` to `claim_centric_schema.sql`
- Or create new `_ensure_claim_centric_schema()` method

### 5. Migrate Existing Data (When Needed)

Since you have no live data currently, you can skip migration. When you do have data:

```bash
python -m src.knowledge_system.database.migrate_to_claim_centric \
    old_knowledge_system.db \
    new_knowledge_system.db
```

### 6. Update Application Code

**Replace:**
```python
from ..database.hce_store import HCEStore
hce_store = HCEStore(db_service)
```

**With:**
```python
from ..database.claim_store import ClaimStore
claim_store = ClaimStore(db_service)
```

Already updated in:
- ✅ `system2_orchestrator_mining.py`

Still need to update:
- ⏳ `unified_pipeline.py` (if it writes to DB directly)
- ⏳ Any other modules using HCEStore

---

## Benefits Achieved

### ✅ Claim-Centric Architecture
- Claims are queryable independently
- Sources provide optional context
- Follows the fundamental principle: claims → sources

### ✅ Source Types Supported
- Episodes (segmented: videos, podcasts)
- Documents (non-segmented: PDFs, articles)
- Same schema works for both

### ✅ Zero JSON Fields
- Everything is normalized tables
- Queryable with SQL
- Indexed for performance
- FK constraints enforced

### ✅ Two-Level Categories
- Source: "Generally about X" (max 3)
- Claim: "Specifically about Y" (typically 1)
- Cross-domain detection enabled

### ✅ WikiData Enforcement Without Prompt Bloat
- Clean prompts (no category lists)
- Fast (embedding matching, not token masking)
- Dynamic (update vocab file anytime)
- Scalable (works with thousands of categories)

### ✅ User Metadata Separate from Platform Metadata
- Source metadata: Immutable (from platform)
- Claim metadata: User-editable (your curation)
- Semantic metadata: WikiData categories (system + user refinable)

---

## Schema Comparison

### Old Schema (Episode-Centric)
```sql
hce_episodes
  └─ hce_claims (composite PK: episode_id, claim_id)
       └─ scores_json TEXT
       └─ structured_categories_json TEXT
```

**Problems:**
- Episode-centric (not claim-centric)
- Composite primary keys (claims not globally unique)
- JSON fields (not queryable)
- Sources contain claims (wrong direction)

### New Schema (Claim-Centric)
```sql
claims (PK: claim_id - globally unique)
  ├─ source_id FK → media_sources
  ├─ episode_id FK → episodes (optional)
  ├─ importance_score REAL (no JSON)
  └─ claim_categories → wikidata_categories
```

**Benefits:**
- Claim-centric (claims are fundamental)
- Global claim IDs (unique across all sources)
- No JSON (everything queryable)
- Claims reference sources (correct direction)

---

## Example Queries

### Find Claims About Topic

```sql
-- Find all monetary policy claims
SELECT 
    c.canonical,
    c.tier,
    m.uploader AS author,
    m.upload_date
FROM claims c
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id
LEFT JOIN media_sources m ON c.source_id = m.source_id
WHERE wc.category_name = 'Monetary policy'
  AND c.tier IN ('A', 'B')
ORDER BY c.tier, c.importance_score DESC;
```

### Cross-Domain Discovery

```sql
-- Find geopolitics claims from finance sources
SELECT 
    c.canonical AS claim_text,
    wc_claim.category_name AS claim_topic,
    GROUP_CONCAT(wc_source.category_name) AS source_topics
FROM claims c
JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
JOIN wikidata_categories wc_claim ON cc.wikidata_id = wc_claim.wikidata_id
JOIN source_categories sc ON c.source_id = sc.source_id
JOIN wikidata_categories wc_source ON sc.wikidata_id = wc_source.wikidata_id
WHERE wc_claim.category_name = 'Geopolitics'
  AND EXISTS (
      SELECT 1 FROM source_categories sc2
      JOIN wikidata_categories wc2 ON sc2.wikidata_id = wc2.wikidata_id
      WHERE sc2.source_id = c.source_id AND wc2.category_name = 'Finance'
  )
GROUP BY c.claim_id;
```

### Find Related Claims

```sql
-- Find claims similar to claim_abc123 (same categories)
SELECT 
    c2.canonical,
    COUNT(*) AS shared_categories
FROM claims c1
JOIN claim_categories cc1 ON c1.claim_id = cc1.claim_id
JOIN claim_categories cc2 ON cc1.wikidata_id = cc2.wikidata_id
JOIN claims c2 ON cc2.claim_id = c2.claim_id
WHERE c1.claim_id = 'claim_abc123'
  AND c2.claim_id != 'claim_abc123'
GROUP BY c2.claim_id, c2.canonical
HAVING shared_categories >= 1
ORDER BY shared_categories DESC;
```

---

## Files Created/Modified

**Created:**
- ✅ `src/knowledge_system/database/migrations/claim_centric_schema.sql`
- ✅ `src/knowledge_system/database/claim_models.py`
- ✅ `src/knowledge_system/database/claim_store.py`
- ✅ `src/knowledge_system/database/wikidata_seed.json`
- ✅ `src/knowledge_system/database/load_wikidata_vocab.py`
- ✅ `src/knowledge_system/database/migrate_to_claim_centric.py`
- ✅ `src/knowledge_system/services/wikidata_categorizer.py`

**Modified:**
- ✅ `src/knowledge_system/core/system2_orchestrator_mining.py`
- ✅ `.cursor/rules/claim-centric-architecture.mdc`

**Documentation:**
- ✅ `CLAIM_CENTRIC_CORRECTED.md`
- ✅ `WIKIDATA_TWO_STAGE_PIPELINE.md`
- ✅ `FULLY_NORMALIZED_SCHEMA.md`
- ✅ `TWO_LEVEL_CATEGORIES.md`
- ✅ `WIKIDATA_ENFORCEMENT_STRATEGY.md`
- ✅ `METADATA_ARCHITECTURE.md`

---

## Testing Checklist

- [ ] Load WikiData vocabulary
- [ ] Create new database with claim-centric schema
- [ ] Test ClaimStore.upsert_pipeline_outputs()
- [ ] Test WikiDataCategorizer matching
- [ ] Run a full summarization workflow
- [ ] Verify claims have global IDs
- [ ] Verify summaries in episodes table
- [ ] Test category queries
- [ ] Test cross-domain discovery
- [ ] Verify no JSON fields remain

---

## Summary

**Implemented a complete claim-centric architecture** where:

1. **Claims are the fundamental unit** (not episodes, not sources)
2. **Sources provide attribution** (who, when, where)
3. **Episodes are a source type** (for segmented content)
4. **Categories at two levels** (source: general, claim: specific)
5. **WikiData enforcement** (two-stage pipeline, no prompt bloat)
6. **Zero JSON** (everything normalized and queryable)
7. **User metadata separate** (claim curation vs platform metadata)

Ready to test and deploy!
