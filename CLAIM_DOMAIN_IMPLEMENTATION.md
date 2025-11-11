# Claim Domain Implementation

**Date**: 2025-11-08  
**Version**: 3.5.2

## Summary

Added `domain` field to claims for broad field classification, enabling filtering and search by domain alongside jargon terms. Updated all miner prompts to guide LLMs toward broad, searchable categories.

## Problem

Claims lacked domain classification, making it difficult to:
- Filter claims by field (e.g., "show me all physics claims")
- Aggregate source domains from claim content
- Search across related fields
- Understand content coverage at a glance

Jargon had domains, but claims didn't - creating an inconsistency.

## Solution

### 1. Database Schema Changes

**Added `domain` field to claims table:**

```sql
-- src/knowledge_system/database/migrations/claim_centric_schema.sql
CREATE TABLE IF NOT EXISTS claims (
    ...
    claim_type TEXT CHECK (claim_type IN ('factual', 'causal', 'normative', 'forecast', 'definition')),
    domain TEXT,  -- Broad field classification (e.g., 'physics', 'economics', 'politics')
    ...
);

CREATE INDEX idx_claims_domain ON claims(domain);
```

**Updated SQLAlchemy model:**
```python
# src/knowledge_system/database/models.py
class Claim(Base):
    ...
    domain = Column(String)  # Broad field classification
```

**Updated Pydantic types:**
```python
# src/knowledge_system/processors/hce/types.py
class ScoredClaim(BaseModel):
    ...
    domain: str | None = None  # Broad field classification
```

**Updated claim storage:**
```python
# src/knowledge_system/database/claim_store.py
claim.domain = getattr(claim_data, "domain", None)
```

### 2. JSON Schema Changes

**Made domain required for claims:**

```json
{
  "claims": {
    "items": {
      "required": ["claim_text", "claim_type", "domain", "stance", "evidence_spans"],
      "properties": {
        "domain": {
          "type": "string",
          "description": "Broad field classification for searchability (e.g., 'physics', 'economics', 'politics')"
        }
      }
    }
  }
}
```

### 3. Prompt Updates

Updated all 7 miner prompts with explicit domain guidance:

**For Claims:**
```
- **domain**: Broad field classification for searchability (e.g., "physics", "economics", "politics", "medicine", "technology"). Use general categories, NOT specific subfields.
```

**For Jargon:**
```
- **domain**: Broad field classification for searchability (e.g., "physics", "economics", "politics", "medicine", "technology"). Use general categories like "physics" not "quantum mechanics", "economics" not "monetary policy", "law" not "constitutional law". Choose the broadest relevant field.
```

**Files Updated:**
1. `unified_miner.txt`
2. `unified_miner_document.txt`
3. `unified_miner_liberal.txt`
4. `unified_miner_moderate.txt`
5. `unified_miner_conservative.txt`
6. `unified_miner_transcript_own.txt`
7. `unified_miner_transcript_third_party.txt`

## Design Decisions

### Open-Ended vs Controlled Vocabulary

**Decision**: Use open-ended free-form strings with prompt guidance

**Rationale**:
- **Flexibility**: Content evolves faster than controlled vocabularies
- **Accuracy**: LLM can naturally describe precise domains
- **Simplicity**: One system to maintain, not two (no WikiData mapping)
- **Personal Use**: Building personal knowledge base, not public knowledge graph
- **Modern Search**: Vector/semantic search handles variations well

**Trade-offs Accepted**:
- Some inconsistency in naming (e.g., "AI" vs "artificial intelligence")
- No standardization for cross-user sharing
- UI filters require fuzzy grouping for "top N domains"

### Broad vs Specific Categories

**Decision**: Guide LLMs toward broad categories via prompts

**Rationale**:
- **Searchability**: Users want to filter by "physics" not "quantum entanglement"
- **Aggregation**: Sources can be categorized by aggregating claim domains
- **Balance**: Specific enough to be useful, broad enough to group related content

**Examples**:
- ✅ "physics" (not "quantum mechanics")
- ✅ "economics" (not "monetary policy")
- ✅ "law" (not "constitutional law")
- ✅ "medicine" (not "cardiology")
- ✅ "technology" (not "machine learning")

## Architecture

### Three Separate Classification Systems

**1. Platform Tags** (Author-provided)
- **Tables**: `platform_tags` + `source_platform_tags`
- **Source**: YouTube video tags set by content creator
- **Example**: "economics", "federal reserve", "2024 election"
- **Purpose**: Author's categorization

**2. Platform Categories** (YouTube-provided)
- **Tables**: `platform_categories` + `source_platform_categories`
- **Source**: YouTube's category system
- **Example**: "News & Politics", "Science & Technology"
- **Purpose**: Platform's categorization

**3. LLM Domains** (System-generated, open-ended)
- **Claims**: `claims.domain` field
- **Jargon**: `jargon_terms.domain` field
- **Source**: LLM analyzes content and assigns broad field
- **Example**: "physics", "economics", "politics"
- **Purpose**: Content-based categorization for filtering/search

### Source-Level Domains

Sources don't have their own domain field. Instead:
- Sources get platform tags and categories (from YouTube/RSS)
- Source domains are computed by aggregating claim domains (via JOIN)
- This prevents duplication and keeps claims as the source of truth

## Testing

Created comprehensive tests to verify:

```python
✓ Test 1: Broad domains accepted for claims and jargon
  - Claim 1 domain: physics
  - Claim 2 domain: economics
  - Jargon 1 domain: economics
  - Jargon 2 domain: law

✓ Test 2: Domain is required for claims (validation correctly failed)
```

## Impact

### Before
- Claims had no domain classification
- Couldn't filter claims by field
- Source domains unclear
- Inconsistency between claims and jargon

### After
- Claims have broad domain classification
- Can filter/search by domain
- Source domains computed from claims
- Consistent architecture for both claims and jargon
- LLM guidance ensures broad, searchable categories

## Usage Examples

### Filtering Claims by Domain
```sql
-- Find all physics claims
SELECT * FROM claims WHERE domain = 'physics';

-- Find all economics claims from a specific source
SELECT * FROM claims WHERE domain = 'economics' AND source_id = 'yt_abc123';
```

### Aggregating Source Domains
```sql
-- What domains does this source cover?
SELECT domain, COUNT(*) as claim_count
FROM claims
WHERE source_id = 'yt_abc123'
GROUP BY domain
ORDER BY claim_count DESC;
```

### Filtering Jargon by Domain
```sql
-- Find all economics jargon terms
SELECT * FROM jargon_terms WHERE domain = 'economics';
```

## Files Modified

1. **Database Schema**:
   - `src/knowledge_system/database/migrations/claim_centric_schema.sql`
   - `src/knowledge_system/database/models.py`

2. **Types**:
   - `src/knowledge_system/processors/hce/types.py`

3. **Storage**:
   - `src/knowledge_system/database/claim_store.py`

4. **Schema**:
   - `schemas/miner_output.v1.json`

5. **Prompts** (7 files):
   - `src/knowledge_system/processors/hce/prompts/unified_miner.txt`
   - `src/knowledge_system/processors/hce/prompts/unified_miner_document.txt`
   - `src/knowledge_system/processors/hce/prompts/unified_miner_liberal.txt`
   - `src/knowledge_system/processors/hce/prompts/unified_miner_moderate.txt`
   - `src/knowledge_system/processors/hce/prompts/unified_miner_conservative.txt`
   - `src/knowledge_system/processors/hce/prompts/unified_miner_transcript_own.txt`
   - `src/knowledge_system/processors/hce/prompts/unified_miner_transcript_third_party.txt`

6. **Documentation**:
   - `CHANGELOG.md`
   - `MANIFEST.md`
   - `CLAIM_DOMAIN_IMPLEMENTATION.md` (this file)

## Future Enhancements

1. **UI Filtering**: Add domain filter to claim search/browse UI
2. **Domain Analytics**: Show domain distribution in source summaries
3. **Fuzzy Grouping**: Group similar domains (e.g., "AI" with "artificial intelligence")
4. **Domain Suggestions**: Auto-suggest domains based on existing data
5. **Cross-Source Analysis**: Compare domain coverage across sources

## Related Documentation

- `SCHEMA_VALIDATION_FIX.md` - Context_type enum fix and jargon domain enum removal
- `src/knowledge_system/database/migrations/claim_centric_schema.sql` - Database schema
- `schemas/miner_output.v1.json` - JSON schema for miner output
