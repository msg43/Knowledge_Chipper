# All Timestamps Implementation - Complete

**Date:** October 27, 2025  
**Issue:** Store ALL timestamps for entity mentions, not just first mention

---

## Problem Statement

**Before Fix:**
- ❌ Claims: Stored ALL evidence spans with timestamps ✅
- ❌ People: Only stored first_mention_ts, lost all other mentions
- ❌ Concepts: Only stored first_mention_ts, ignored evidence_spans array
- ❌ Jargon: Only stored first_mention_ts, ignored evidence_spans array

**Example Loss:**
```
"Jerome Powell" mentioned at:
- 00:02:15 (introduction)
- 00:15:30 (policy discussion)
- 00:23:45 (conclusion)

OLD: Only stored 00:02:15 ❌
NEW: Stores all 3 timestamps ✅
```

---

## Solution: Entity Evidence Tables

Created three new tables parallel to `evidence_spans` (which tracks claim evidence):

### 1. `person_evidence`
Stores ALL mentions of a person across the episode.

**Schema:**
```sql
CREATE TABLE person_evidence (
    person_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    
    -- Timing
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    
    -- Content
    quote TEXT NOT NULL,           -- How they were mentioned
    surface_form TEXT,             -- Exact text used
    segment_id TEXT,
    
    -- Context
    context_start_time TEXT,
    context_end_time TEXT,
    context_text TEXT,
    context_type TEXT DEFAULT 'exact',
    
    PRIMARY KEY (person_id, claim_id, sequence)
);
```

**Example Data:**
```
person_id: "person_jerome_powell"
claim_id: "abc123_claim_001"
sequence: 0
start_time: "00:02:15"
end_time: "00:02:18"
quote: "Jerome Powell announced the rate decision"
segment_id: "seg_0023"
```

---

### 2. `concept_evidence`
Stores ALL usages of a concept/mental model.

**Schema:**
```sql
CREATE TABLE concept_evidence (
    concept_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    
    -- Timing
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    
    -- Content
    quote TEXT NOT NULL,           -- Example/usage of the concept
    segment_id TEXT,
    
    -- Context
    context_start_time TEXT,
    context_end_time TEXT,
    context_text TEXT,
    context_type TEXT DEFAULT 'exact',
    
    PRIMARY KEY (concept_id, claim_id, sequence)
);
```

**Example Data:**
```
concept_id: "concept_monetary_policy"
claim_id: "abc123_claim_005"
sequence: 0
start_time: "00:08:45"
end_time: "00:08:52"
quote: "The Fed's monetary policy aims to balance inflation and employment"
```

---

### 3. `jargon_evidence`
Stores ALL usages of jargon terms.

**Schema:**
```sql
CREATE TABLE jargon_evidence (
    jargon_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    
    -- Timing
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    
    -- Content
    quote TEXT NOT NULL,           -- Usage of the jargon term
    segment_id TEXT,
    
    -- Context
    context_start_time TEXT,
    context_end_time TEXT,
    context_text TEXT,
    context_type TEXT DEFAULT 'exact',
    
    PRIMARY KEY (jargon_id, claim_id, sequence)
);
```

**Example Data:**
```
jargon_id: "jargon_quantitative_easing"
claim_id: "abc123_claim_012"
sequence: 0
start_time: "00:12:30"
end_time: "00:12:35"
quote: "They used quantitative easing to inject liquidity into the system"
```

---

## Implementation Details

### Files Modified

1. **`claim_models.py`** - Added 3 new SQLAlchemy models:
   - `PersonEvidence`
   - `ConceptEvidence`
   - `JargonEvidence`

2. **`claim_store.py`** - Updated storage logic:
   - Import new models
   - Store ALL evidence spans for concepts (from `concept_data.evidence_spans`)
   - Store ALL evidence spans for jargon (from `jargon_data.evidence_spans`)
   - Store ALL mentions of people (grouped by normalized name)
   - Enhanced logging to show total evidence counts

3. **`migrations/004_add_entity_evidence_tables.py`** - Created migration:
   - Creates 3 new tables
   - Adds performance indexes
   - Includes upgrade/downgrade functions

---

## Data Flow

### What the Miner Outputs

```python
PipelineOutputs(
    people=[
        PersonMention(name="Jerome Powell", t0="00:02:15", t1="00:02:18", ...),
        PersonMention(name="Jerome Powell", t0="00:15:30", t1="00:15:33", ...),
        PersonMention(name="Jerome Powell", t0="00:23:45", t1="00:23:48", ...),
    ],
    concepts=[
        MentalModel(
            name="Monetary Policy",
            evidence_spans=[
                EvidenceSpan(t0="00:08:45", t1="00:08:52", quote="..."),
                EvidenceSpan(t0="00:16:20", t1="00:16:28", quote="..."),
            ]
        )
    ],
    jargon=[
        JargonTerm(
            term="quantitative easing",
            evidence_spans=[
                EvidenceSpan(t0="00:12:30", t1="00:12:35", quote="..."),
                EvidenceSpan(t0="00:19:10", t1="00:19:15", quote="..."),
            ]
        )
    ]
)
```

### What Gets Stored (NEW)

**People:**
```sql
-- people table (normalized entity)
INSERT INTO people (person_id, name) VALUES ('person_jerome_powell', 'Jerome Powell');

-- claim_people table (which claims mention this person)
INSERT INTO claim_people (claim_id, person_id, first_mention_ts) 
VALUES ('abc123_claim_001', 'person_jerome_powell', '00:02:15');

-- person_evidence table (ALL mentions with timestamps) ← NEW!
INSERT INTO person_evidence (person_id, claim_id, sequence, start_time, end_time, quote)
VALUES 
    ('person_jerome_powell', 'abc123_claim_001', 0, '00:02:15', '00:02:18', 'Jerome Powell announced...'),
    ('person_jerome_powell', 'abc123_claim_008', 1, '00:15:30', '00:15:33', 'As Powell noted...'),
    ('person_jerome_powell', 'abc123_claim_015', 2, '00:23:45', '00:23:48', 'Powell concluded...');
```

**Concepts:**
```sql
-- concepts table (normalized entity)
INSERT INTO concepts (concept_id, name, definition) 
VALUES ('concept_monetary_policy', 'Monetary Policy', '...');

-- concept_evidence table (ALL usages with timestamps) ← NEW!
INSERT INTO concept_evidence (concept_id, claim_id, sequence, start_time, end_time, quote)
VALUES 
    ('concept_monetary_policy', 'abc123_claim_005', 0, '00:08:45', '00:08:52', 'The Fed\'s monetary policy...'),
    ('concept_monetary_policy', 'abc123_claim_009', 1, '00:16:20', '00:16:28', 'Effective monetary policy requires...');
```

**Jargon:**
```sql
-- jargon_terms table (normalized entity)
INSERT INTO jargon_terms (jargon_id, term, definition)
VALUES ('jargon_quantitative_easing', 'quantitative easing', '...');

-- jargon_evidence table (ALL usages with timestamps) ← NEW!
INSERT INTO jargon_evidence (jargon_id, claim_id, sequence, start_time, end_time, quote)
VALUES 
    ('jargon_quantitative_easing', 'abc123_claim_012', 0, '00:12:30', '00:12:35', 'They used quantitative easing...'),
    ('jargon_quantitative_easing', 'abc123_claim_018', 1, '00:19:10', '00:19:15', 'QE has been controversial...');
```

---

## Query Examples

### Find all mentions of a person
```sql
SELECT 
    pe.start_time,
    pe.quote,
    c.canonical AS claim_text
FROM person_evidence pe
JOIN claims c ON pe.claim_id = c.claim_id
WHERE pe.person_id = 'person_jerome_powell'
ORDER BY pe.start_time;
```

**Returns:**
```
00:02:15 | "Jerome Powell announced..." | "The Fed raised rates by 25bp"
00:15:30 | "As Powell noted..." | "Powell emphasized the data-dependent approach"
00:23:45 | "Powell concluded..." | "Future policy decisions will be cautious"
```

### Find all usages of a concept across sources
```sql
SELECT 
    ce.start_time,
    ce.quote,
    c.canonical,
    ms.title AS source_title
FROM concept_evidence ce
JOIN claims c ON ce.claim_id = c.claim_id
JOIN media_sources ms ON c.source_id = ms.source_id
WHERE ce.concept_id = 'concept_monetary_policy'
ORDER BY ms.upload_date DESC, ce.start_time;
```

### Track jargon term evolution over time
```sql
SELECT 
    ms.upload_date,
    je.start_time,
    je.quote,
    ms.title
FROM jargon_evidence je
JOIN claims c ON je.claim_id = c.claim_id
JOIN media_sources ms ON c.source_id = ms.source_id
WHERE je.jargon_id = 'jargon_quantitative_easing'
ORDER BY ms.upload_date;
```

---

## Benefits

1. **Complete Temporal Tracking** - Know when every entity was mentioned
2. **Context Preservation** - Each mention has its surrounding quote
3. **Claim Attribution** - Each mention linked to specific claim
4. **Cross-Source Analysis** - Track how people/concepts are discussed across sources
5. **Duplicate Detection** - Can identify repeated mentions and deduplicate intelligently
6. **Timeline Visualization** - Can create timelines of when entities appear

---

## Storage Comparison

### Old System (First Mention Only)
```
Jerome Powell: first_mention_ts="00:02:15"
Total timestamps stored: 1
```

### New System (All Mentions)
```
Jerome Powell:
  - person_evidence row 1: 00:02:15-00:02:18
  - person_evidence row 2: 00:15:30-00:15:33
  - person_evidence row 3: 00:23:45-00:23:48
Total timestamps stored: 3 (100% data preserved)
```

---

## Migration Instructions

### To Apply Migration

```python
from knowledge_system.database.service import DatabaseService
from knowledge_system.database.migrations.004_add_entity_evidence_tables import upgrade

db_service = DatabaseService()
upgrade(db_service)
```

### To Rollback Migration

```python
from knowledge_system.database.migrations.004_add_entity_evidence_tables import downgrade

downgrade(db_service)
```

---

## Status

✅ **Schema Updated** - 3 new models added to `claim_models.py`  
✅ **Storage Logic Updated** - `claim_store.py` now stores all evidence spans  
✅ **Migration Created** - `004_add_entity_evidence_tables.py`  
✅ **No Linter Errors** - All code passes validation  
⏳ **Migration Not Run** - Database tables not yet created (pending user approval)

---

## Next Steps

1. **Run migration** to create tables in database
2. **Test** with a sample episode that mentions same person multiple times
3. **Verify** all timestamps are stored
4. **Update queries** to utilize new evidence tables

---

## Verification Query

After running migration, verify with:

```sql
-- Check if tables exist
SELECT name FROM sqlite_master WHERE type='table' 
AND name IN ('person_evidence', 'concept_evidence', 'jargon_evidence');

-- After processing an episode, check mention counts
SELECT 
    p.name,
    COUNT(*) AS total_mentions
FROM people p
LEFT JOIN person_evidence pe ON p.person_id = pe.person_id
GROUP BY p.person_id, p.name
HAVING total_mentions > 1
ORDER BY total_mentions DESC;
```

This will show which people are mentioned multiple times and how many mentions were captured.

---

**Status:** ✅ **IMPLEMENTATION COMPLETE - READY FOR MIGRATION**

