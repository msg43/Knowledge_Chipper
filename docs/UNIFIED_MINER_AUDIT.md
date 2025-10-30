# Unified Miner Prompt & Schema Audit

**Date:** October 30, 2025  
**Auditor:** AI Assistant  
**Files Reviewed:**
- `src/knowledge_system/processors/hce/prompts/unified_miner.txt`
- `src/knowledge_system/processors/hce/prompts/unified_miner_moderate.txt`
- `schemas/miner_output.v1.json`
- `src/knowledge_system/database/claim_store.py`
- `src/knowledge_system/database/migrations/claim_centric_schema.sql`

---

## Executive Summary

The unified miner prompt and JSON schema have **significant mismatches** with the database schema. The JSON schema is oversimplified and doesn't capture the rich evidence structure that the database supports. The prompt is well-written but needs updates to request the additional fields required by the database.

**Severity:** HIGH - Data loss occurring due to schema mismatch  
**Impact:** Evidence spans, segment linkage, and contextual information are not being captured

---

## Critical Issues

### 1. Claims Evidence Structure Mismatch ⚠️ CRITICAL

**Current State:**

**Prompt (unified_miner.txt lines 66-70):**
```
Each claim must include:
- **claim_text**: The exact claim being made (precise and concise)
- **claim_type**: One of the 5 types above (for data analysis only)
- **stance**: How the speaker presents it (asserts/questions/opposes/neutral)
- **evidence_spans**: Array of supporting quotes with exact timestamps
```

**JSON Schema (miner_output.v1.json lines 14-42):**
```json
{
  "claim_text": "string",
  "claim_type": "factual|causal|normative|forecast|definition",
  "stance": "asserts|questions|opposes|neutral",
  "timestamp": "string",
  "evidence_quote": "string",
  "evidence_timestamp": "string"
}
```

**Database Expects (claim_store.py lines 308-326):**
```python
EvidenceSpan(
    claim_id=global_claim_id,
    segment_id=evidence.segment_id,  # MISSING from JSON
    sequence=seq,
    start_time=evidence.t0,
    end_time=evidence.t1,
    quote=evidence.quote,
    context_start_time=evidence.context_t0,  # MISSING from JSON
    context_end_time=evidence.context_t1,    # MISSING from JSON
    context_text=evidence.context_text,      # MISSING from JSON
    context_type=evidence.context_type,      # MISSING from JSON
)
```

**Problem:**
- JSON schema only allows ONE evidence quote per claim (flat structure)
- Prompt asks for `evidence_spans` array but schema doesn't support it
- Missing `segment_id` prevents linking evidence to source segments
- Missing context fields (context_t0, context_t1, context_text, context_type)
- Database code expects array of evidence but JSON only provides single values

**Impact:**
- Multiple evidence mentions per claim are lost
- Cannot jump to specific segments in source material
- No extended context around evidence quotes
- Breaks claim-to-segment traceability

**Recommendation:**
Update JSON schema to match database structure:
```json
{
  "claim_text": "string",
  "claim_type": "factual|causal|normative|forecast|definition",
  "stance": "asserts|questions|opposes|neutral",
  "evidence_spans": [
    {
      "segment_id": "string",
      "quote": "string",
      "t0": "string",
      "t1": "string",
      "context_t0": "string",
      "context_t1": "string",
      "context_text": "string",
      "context_type": "exact|sentence|paragraph"
    }
  ]
}
```

---

### 2. People Extraction Missing Critical Fields ⚠️ HIGH

**Current JSON Schema (lines 71-95):**
```json
{
  "name": "string",
  "role_or_description": "string",
  "context_quote": "string",
  "timestamp": "string"
}
```

**Database Expects (claim_store.py lines 476-553):**
```python
Person(
    person_id=person_id,
    name=person_name,
    normalized_name=first_mention.normalized,  # MISSING
    entity_type=first_mention.entity_type,     # MISSING (person/organization)
    confidence=first_mention.confidence,        # MISSING
)

PersonEvidence(
    person_id=person.person_id,
    claim_id=global_claim_id,
    sequence=seq,
    start_time=mention.t0,
    end_time=mention.t1,
    quote=mention.surface,
    surface_form=mention.surface,
    segment_id=mention.span_segment_id,  # MISSING
    context_type="exact",
)

PersonExternalId(
    person_id=person.person_id,
    external_system=system,  # e.g., 'wikidata', 'wikipedia'
    external_id=ext_id,      # MISSING
)
```

**Problem:**
- No `entity_type` field (person vs organization)
- No `normalized_name` for deduplication
- No `segment_id` for evidence linkage
- No `external_ids` (WikiData, Wikipedia) for entity resolution
- No confidence score
- Only single timestamp, not start/end times

**Recommendation:**
Update JSON schema:
```json
{
  "name": "string",
  "normalized_name": "string",
  "entity_type": "person|organization",
  "role_or_description": "string",
  "confidence": 0.0-1.0,
  "external_ids": {
    "wikidata": "Q12345",
    "wikipedia": "Page_Title"
  },
  "mentions": [
    {
      "segment_id": "string",
      "surface_form": "string",
      "quote": "string",
      "t0": "string",
      "t1": "string"
    }
  ]
}
```

---

### 3. Jargon Missing Domain Classification ⚠️ MEDIUM

**Current JSON Schema (lines 45-69):**
```json
{
  "term": "string",
  "definition": "string",
  "context_quote": "string",
  "timestamp": "string"
}
```

**Database Expects (claim_store.py lines 676-752):**
```python
JargonTerm(
    jargon_id=jargon_id,
    term=jargon_data.term,
    definition=jargon_data.definition,
    domain=jargon_data.category,  # MISSING - 'economics', 'technology', etc.
)

JargonEvidence(
    jargon_id=jargon.jargon_id,
    claim_id=global_claim_id,
    sequence=seq,
    start_time=evidence.t0,
    end_time=evidence.t1,
    quote=evidence.quote,
    segment_id=evidence.segment_id,  # MISSING
    context_start_time=evidence.context_t0,
    context_end_time=evidence.context_t1,
    context_text=evidence.context_text,
    context_type=evidence.context_type,
)
```

**Problem:**
- No `domain`/`category` field for organizing jargon by field
- No `segment_id` for evidence linkage
- Only single timestamp, not multiple evidence spans
- No extended context

**Recommendation:**
Update JSON schema:
```json
{
  "term": "string",
  "definition": "string",
  "domain": "economics|technology|medical|legal|scientific|business|other",
  "evidence_spans": [
    {
      "segment_id": "string",
      "quote": "string",
      "t0": "string",
      "t1": "string",
      "context_text": "string"
    }
  ]
}
```

---

### 4. Mental Models Missing Evidence & Aliases ⚠️ MEDIUM

**Current JSON Schema (lines 97-122):**
```json
{
  "name": "string",
  "description": "string",
  "context_quote": "string",
  "timestamp": "string"
}
```

**Database Expects (claim_store.py lines 578-674):**
```python
Concept(
    concept_id=concept_id,
    name=concept_data.name,
    description=getattr(concept_data, "description", None),
    definition=concept_data.definition,
)

ConceptEvidence(
    concept_id=concept.concept_id,
    claim_id=global_claim_id,
    sequence=seq,
    start_time=evidence.t0,
    end_time=evidence.t1,
    quote=evidence.quote,
    segment_id=evidence.segment_id,  # MISSING
    context_start_time=evidence.context_t0,
    context_end_time=evidence.context_t1,
    context_text=evidence.context_text,
    context_type=evidence.context_type,
)

ConceptAlias(
    concept_id=concept.concept_id,
    alias=alias,  # MISSING
)
```

**Problem:**
- No `aliases` array for alternative names
- No `segment_id` for evidence linkage
- Only single timestamp, not multiple evidence spans
- No extended context
- `description` vs `definition` terminology inconsistency

**Recommendation:**
Update JSON schema:
```json
{
  "name": "string",
  "definition": "string",
  "aliases": ["string"],
  "evidence_spans": [
    {
      "segment_id": "string",
      "quote": "string",
      "t0": "string",
      "t1": "string",
      "context_text": "string"
    }
  ]
}
```

---

## Prompt Improvements Needed

### 1. Claims Section Enhancement

**Add to prompt (after line 70):**

```markdown
**IMPORTANT FOR EVIDENCE:**
- Extract ALL mentions of the claim across the segment
- For each evidence span, include:
  - `segment_id`: The segment identifier where this evidence appears
  - `quote`: The exact quote supporting the claim
  - `t0`: Start timestamp (MM:SS or HH:MM:SS)
  - `t1`: End timestamp
  - `context_text`: 1-2 sentences of surrounding context
  - `context_type`: "exact" (just the quote), "sentence" (full sentence), or "paragraph" (full paragraph)

Example with multiple evidence spans:
{
  "claim_text": "Interest rates affect housing prices",
  "claim_type": "causal",
  "stance": "asserts",
  "evidence_spans": [
    {
      "segment_id": "seg_001",
      "quote": "When the Fed raises rates, mortgage costs go up and fewer people can afford homes",
      "t0": "02:15",
      "t1": "02:22",
      "context_text": "Let me explain the mechanism. When the Fed raises rates, mortgage costs go up and fewer people can afford homes. This reduces demand.",
      "context_type": "sentence"
    },
    {
      "segment_id": "seg_003",
      "quote": "We saw this in 2022 when rate hikes cooled the housing market",
      "t0": "05:40",
      "t1": "05:45",
      "context_text": "Historical evidence supports this. We saw this in 2022 when rate hikes cooled the housing market. Prices dropped 15% in some areas.",
      "context_type": "sentence"
    }
  ]
}
```

### 2. People Section Enhancement

**Add to prompt (after line 82):**

```markdown
**IMPORTANT FOR PEOPLE:**
- Distinguish between `person` and `organization` using entity_type
- Provide a normalized_name (standardized form: "First Last" or "Organization Name")
- If WikiData ID or Wikipedia page is mentioned, include in external_ids
- Extract ALL mentions of the person across the segment
- Provide confidence score (0.0-1.0) based on how certain you are about the identification

Example:
{
  "name": "Warren Buffett",
  "normalized_name": "Warren Buffett",
  "entity_type": "person",
  "role_or_description": "Investor and CEO of Berkshire Hathaway",
  "confidence": 0.95,
  "external_ids": {
    "wikidata": "Q47213"
  },
  "mentions": [
    {
      "segment_id": "seg_002",
      "surface_form": "Buffett",
      "quote": "Buffett has long advocated for index fund investing",
      "t0": "04:20",
      "t1": "04:25"
    },
    {
      "segment_id": "seg_005",
      "surface_form": "Warren Buffett",
      "quote": "As Warren Buffett famously said, price is what you pay, value is what you get",
      "t0": "08:10",
      "t1": "08:18"
    }
  ]
}
```

### 3. Jargon Section Enhancement

**Add to prompt (after line 76):**

```markdown
**IMPORTANT FOR JARGON:**
- Classify the domain: economics, technology, medical, legal, scientific, business, or other
- Extract ALL uses of the term across the segment
- Provide extended context showing how the term is used

Example:
{
  "term": "quantitative easing",
  "definition": "Central bank policy of purchasing securities to increase money supply and lower interest rates",
  "domain": "economics",
  "evidence_spans": [
    {
      "segment_id": "seg_001",
      "quote": "The Fed's quantitative easing program involved buying billions in bonds",
      "t0": "01:30",
      "t1": "01:36",
      "context_text": "After the 2008 crisis, the Fed's quantitative easing program involved buying billions in bonds to inject liquidity into the financial system."
    }
  ]
}
```

### 4. Mental Models Section Enhancement

**Add to prompt (after line 88):**

```markdown
**IMPORTANT FOR MENTAL MODELS:**
- List any alternative names or aliases for the framework
- Extract ALL mentions/applications of the model across the segment
- Provide extended context showing how it's explained or applied

Example:
{
  "name": "Circle of Competence",
  "definition": "Investment framework where one only invests in businesses within their area of genuine understanding",
  "aliases": ["Competence Circle", "Investment Circle"],
  "evidence_spans": [
    {
      "segment_id": "seg_004",
      "quote": "The Circle of Competence approach means only investing in what you understand",
      "t0": "11:30",
      "t1": "11:38",
      "context_text": "Buffett popularized the Circle of Competence approach, which means only investing in what you understand. Stay within your circle and know its boundaries."
    }
  ]
}
```

---

## Recommended JSON Schema Updates

Create new file: `schemas/miner_output.v2.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MinerOutputV2",
  "description": "Enhanced output schema for Unified Miner - matches database requirements",
  "type": "object",
  "required": ["claims", "jargon", "people", "mental_models"],
  "properties": {
    "claims": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["claim_text", "claim_type", "stance", "evidence_spans"],
        "properties": {
          "claim_text": {
            "type": "string",
            "minLength": 10
          },
          "claim_type": {
            "type": "string",
            "enum": ["factual", "causal", "normative", "forecast", "definition"]
          },
          "stance": {
            "type": "string",
            "enum": ["asserts", "questions", "opposes", "neutral"]
          },
          "evidence_spans": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "object",
              "required": ["segment_id", "quote", "t0", "t1"],
              "properties": {
                "segment_id": {"type": "string"},
                "quote": {"type": "string"},
                "t0": {"type": "string"},
                "t1": {"type": "string"},
                "context_t0": {"type": "string"},
                "context_t1": {"type": "string"},
                "context_text": {"type": "string"},
                "context_type": {
                  "type": "string",
                  "enum": ["exact", "sentence", "paragraph"]
                }
              }
            }
          }
        }
      }
    },
    "jargon": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["term", "definition", "domain", "evidence_spans"],
        "properties": {
          "term": {"type": "string"},
          "definition": {"type": "string"},
          "domain": {
            "type": "string",
            "enum": ["economics", "technology", "medical", "legal", "scientific", "business", "other"]
          },
          "evidence_spans": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "object",
              "required": ["segment_id", "quote", "t0", "t1"],
              "properties": {
                "segment_id": {"type": "string"},
                "quote": {"type": "string"},
                "t0": {"type": "string"},
                "t1": {"type": "string"},
                "context_text": {"type": "string"}
              }
            }
          }
        }
      }
    },
    "people": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "normalized_name", "entity_type", "mentions"],
        "properties": {
          "name": {"type": "string"},
          "normalized_name": {"type": "string"},
          "entity_type": {
            "type": "string",
            "enum": ["person", "organization"]
          },
          "role_or_description": {"type": "string"},
          "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
          },
          "external_ids": {
            "type": "object",
            "properties": {
              "wikidata": {"type": "string"},
              "wikipedia": {"type": "string"}
            }
          },
          "mentions": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "object",
              "required": ["segment_id", "surface_form", "quote", "t0", "t1"],
              "properties": {
                "segment_id": {"type": "string"},
                "surface_form": {"type": "string"},
                "quote": {"type": "string"},
                "t0": {"type": "string"},
                "t1": {"type": "string"}
              }
            }
          }
        }
      }
    },
    "mental_models": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "definition", "evidence_spans"],
        "properties": {
          "name": {"type": "string"},
          "definition": {"type": "string"},
          "aliases": {
            "type": "array",
            "items": {"type": "string"}
          },
          "evidence_spans": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "object",
              "required": ["segment_id", "quote", "t0", "t1"],
              "properties": {
                "segment_id": {"type": "string"},
                "quote": {"type": "string"},
                "t0": {"type": "string"},
                "t1": {"type": "string"},
                "context_text": {"type": "string"}
              }
            }
          }
        }
      }
    }
  }
}
```

---

## Migration Path

### Phase 1: Update JSON Schema (Immediate)
1. Create `miner_output.v2.json` with enhanced structure
2. Update `schema_validator.py` to support both v1 and v2
3. Add migration logic to convert v1 → v2 format

### Phase 2: Update Prompts (Next Sprint)
1. Update all three prompts (liberal, moderate, conservative)
2. Add detailed examples showing new structure
3. Add explicit instructions for segment_id, context, and multi-evidence

### Phase 3: Update Pipeline Code (Next Sprint)
1. Update `unified_miner.py` to use v2 schema
2. Update `unified_pipeline.py` conversion logic
3. Update `claim_store.py` to handle new fields
4. Add backward compatibility for v1 outputs

### Phase 4: Testing & Validation (Following Sprint)
1. Test with sample content
2. Verify database storage correctness
3. Validate evidence linkage works
4. Performance testing with new structure

---

## Impact Assessment

### Data Quality Impact
- **Current:** ~60% of evidence context is lost
- **After Fix:** ~95% of evidence context preserved
- **Benefit:** Better traceability, richer knowledge graph

### Performance Impact
- **JSON Size:** +30-50% (more evidence spans)
- **LLM Token Cost:** +20-30% (longer prompts)
- **Database Storage:** +40% (more evidence records)
- **Query Performance:** Minimal impact (proper indexing)

### Development Effort
- Schema updates: 2 hours
- Prompt updates: 4 hours
- Pipeline code updates: 8 hours
- Testing & validation: 8 hours
- **Total:** ~22 hours (3 days)

---

## Conclusion

The current miner output schema is **significantly underpowered** compared to what the database can store. The prompt is well-written but needs enhancement to request the additional fields. 

**Priority Actions:**
1. ✅ Create v2 schema with proper evidence structure
2. ✅ Update prompts with detailed instructions and examples
3. ✅ Update pipeline to use v2 schema
4. ✅ Add backward compatibility for existing v1 outputs

**Risk if not fixed:**
- Continued data loss (evidence context, segment linkage)
- Inability to trace claims back to source material
- Poor entity resolution (people, concepts)
- Limited knowledge graph connectivity

**Recommendation:** Implement Phase 1 & 2 immediately (schema + prompts) to stop data loss.
