# Fully Normalized Schema - Zero JSON

## Design Principle: Everything is a Table

**NO JSON fields.** Every piece of data should be:
- ✅ Queryable with SQL
- ✅ Indexed for performance
- ✅ Enforced with foreign keys
- ✅ Updatable without JSON parsing

---

## Core Tables

### 1. Sources (Attribution)

```sql
CREATE TABLE media_sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,  -- 'youtube', 'pdf', 'article', 'podcast'
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    
    -- Author info
    uploader TEXT,
    uploader_id TEXT,
    author TEXT,
    organization TEXT,
    
    -- Temporal
    upload_date TEXT,
    recorded_at TEXT,
    published_at TEXT,
    
    -- Metrics (from platform)
    duration_seconds INTEGER,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER,
    
    -- Technical
    privacy_status TEXT,
    caption_availability BOOLEAN,
    language TEXT,
    
    -- Local storage
    thumbnail_url TEXT,
    thumbnail_local_path TEXT,
    audio_file_path TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    fetched_at DATETIME
);
```

### 2. Episodes (Organizational Units for Segmented Content)

```sql
CREATE TABLE episodes (
    episode_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    subtitle TEXT,
    description TEXT,
    recorded_at TEXT,
    
    -- Summaries (moved from separate table)
    short_summary TEXT,      -- Pre-mining overview
    long_summary TEXT,       -- Post-analysis synthesis
    summary_generated_at DATETIME,
    summary_generated_by_model TEXT,
    
    -- Metrics
    input_length INTEGER,
    output_length INTEGER,
    compression_ratio REAL,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    processed_at DATETIME,
    
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE
);

CREATE INDEX idx_episodes_source ON episodes(source_id);
```

### 3. Segments (Temporal Chunks)

```sql
CREATE TABLE segments (
    segment_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    speaker TEXT,
    start_time TEXT,
    end_time TEXT,
    text TEXT NOT NULL,
    topic_guess TEXT,
    
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

CREATE INDEX idx_segments_episode ON segments(episode_id);
```

### 4. Claims (Atomic Knowledge Units)

```sql
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,          -- Direct link to source
    episode_id TEXT,                  -- Optional (for segmented content)
    
    -- Content
    canonical TEXT NOT NULL,
    original_text TEXT,
    claim_type TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
    
    -- System evaluation
    tier TEXT CHECK (tier IN ('A','B','C')),
    importance_score REAL,
    specificity_score REAL,
    verifiability_score REAL,
    
    -- User curation
    user_tier_override TEXT,
    user_confidence_override REAL,
    evaluator_notes TEXT,
    
    -- Verification workflow
    verification_status TEXT CHECK (verification_status IN ('unverified','verified','disputed','false')),
    verification_source TEXT,
    verification_notes TEXT,
    
    -- Review workflow
    flagged_for_review BOOLEAN DEFAULT 0,
    reviewed_by TEXT,
    reviewed_at DATETIME,
    
    -- Temporality
    temporality_score INTEGER CHECK (temporality_score IN (1,2,3,4,5)),
    temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1),
    temporality_rationale TEXT,
    first_mention_ts TEXT,
    
    -- Export tracking
    upload_status TEXT DEFAULT 'pending',
    upload_timestamp DATETIME,
    upload_error TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),
    
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE SET NULL
);

CREATE INDEX idx_claims_source ON claims(source_id);
CREATE INDEX idx_claims_episode ON claims(episode_id);
CREATE INDEX idx_claims_tier ON claims(tier);
CREATE INDEX idx_claims_verification ON claims(verification_status);
```

---

## Categories: TWO LEVELS (Episode + Claim)

### WikiData Category Vocabulary (The Controlled List)

```sql
-- Master list of WikiData categories (the vocabulary)
CREATE TABLE wikidata_categories (
    wikidata_id TEXT PRIMARY KEY,          -- "Q186363"
    category_name TEXT NOT NULL,           -- "Monetary policy"
    category_description TEXT,
    parent_wikidata_id TEXT,               -- Hierarchy
    wikidata_url TEXT,
    level TEXT,                            -- 'general', 'specific' (for UI hints)
    
    created_at DATETIME DEFAULT (datetime('now')),
    
    FOREIGN KEY (parent_wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);

CREATE INDEX idx_wikidata_categories_name ON wikidata_categories(category_name);
CREATE INDEX idx_wikidata_categories_parent ON wikidata_categories(parent_wikidata_id);
```

### Episode Categories (Broad - Max 3)

```sql
-- Episode-level categories: "This episode is generally about X"
CREATE TABLE episode_categories (
    episode_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,
    
    -- System scores
    relevance_score REAL,              -- How relevant is this category?
    confidence REAL,                   -- How confident is the system?
    
    -- User workflow
    user_approved BOOLEAN DEFAULT 0,
    user_rejected BOOLEAN DEFAULT 0,
    source TEXT DEFAULT 'system',      -- 'system' or 'user'
    
    -- Ranking (for the 3-category limit)
    rank INTEGER,                      -- 1, 2, or 3
    
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),
    
    PRIMARY KEY (episode_id, wikidata_id),
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE,
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id),
    
    CHECK (rank IS NULL OR rank BETWEEN 1 AND 3)
);

CREATE INDEX idx_episode_categories_episode ON episode_categories(episode_id);
CREATE INDEX idx_episode_categories_category ON episode_categories(wikidata_id);
CREATE INDEX idx_episode_categories_rank ON episode_categories(rank);
```

### Claim Categories (Specific - Typically 1)

```sql
-- Claim-level category: "This claim is specifically about Y"
CREATE TABLE claim_categories (
    claim_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,
    
    -- System scores
    relevance_score REAL,
    confidence REAL,
    
    -- User workflow
    user_approved BOOLEAN DEFAULT 0,
    user_rejected BOOLEAN DEFAULT 0,
    source TEXT DEFAULT 'system',
    
    -- Context
    is_primary BOOLEAN DEFAULT 0,     -- The main category for this claim
    context_quote TEXT,                -- Which part triggered this?
    
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),
    
    PRIMARY KEY (claim_id, wikidata_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);

CREATE INDEX idx_claim_categories_claim ON claim_categories(claim_id);
CREATE INDEX idx_claim_categories_category ON claim_categories(wikidata_id);
CREATE INDEX idx_claim_categories_primary ON claim_categories(is_primary) WHERE is_primary = 1;
```

---

## User Tags (Separate Table - Not JSON)

```sql
-- User-defined tags (completely separate from WikiData categories)
CREATE TABLE user_tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT UNIQUE NOT NULL,
    tag_color TEXT,                    -- For UI
    description TEXT,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX idx_user_tags_name ON user_tags(tag_name);

-- Claim tags (many-to-many)
CREATE TABLE claim_tags (
    claim_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    added_by TEXT,
    added_at DATETIME DEFAULT (datetime('now')),
    
    PRIMARY KEY (claim_id, tag_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES user_tags(tag_id) ON DELETE CASCADE
);

CREATE INDEX idx_claim_tags_claim ON claim_tags(claim_id);
CREATE INDEX idx_claim_tags_tag ON claim_tags(tag_id);
```

---

## Evidence, People, Concepts (All Normalized)

### Evidence Spans

```sql
CREATE TABLE evidence_spans (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    segment_id TEXT,
    sequence INTEGER NOT NULL,
    
    -- Precise quote
    start_time TEXT,
    end_time TEXT,
    quote TEXT,
    
    -- Extended context
    context_start_time TEXT,
    context_end_time TEXT,
    context_text TEXT,
    context_type TEXT DEFAULT 'exact' CHECK (context_type IN ('exact', 'extended', 'segment')),
    
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (segment_id) REFERENCES segments(segment_id)
);

CREATE INDEX idx_evidence_claim ON evidence_spans(claim_id);
CREATE INDEX idx_evidence_segment ON evidence_spans(segment_id);
```

### People

```sql
CREATE TABLE people (
    person_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    normalized_name TEXT,
    description TEXT,
    entity_type TEXT CHECK (entity_type IN ('person','organization')) DEFAULT 'person',
    confidence REAL
);

CREATE INDEX idx_people_name ON people(name);
CREATE INDEX idx_people_normalized ON people(normalized_name);

-- Person mentions in claims
CREATE TABLE claim_people (
    claim_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    mention_context TEXT,              -- How they're mentioned
    first_mention_ts TEXT,
    
    PRIMARY KEY (claim_id, person_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES people(person_id)
);

CREATE INDEX idx_claim_people_claim ON claim_people(claim_id);
CREATE INDEX idx_claim_people_person ON claim_people(person_id);

-- External IDs for people (not JSON)
CREATE TABLE person_external_ids (
    person_id TEXT NOT NULL,
    external_system TEXT NOT NULL,     -- 'wikidata', 'wikipedia', 'twitter'
    external_id TEXT NOT NULL,
    
    PRIMARY KEY (person_id, external_system),
    FOREIGN KEY (person_id) REFERENCES people(person_id) ON DELETE CASCADE
);
```

### Concepts / Mental Models

```sql
CREATE TABLE concepts (
    concept_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    definition TEXT
);

CREATE INDEX idx_concepts_name ON concepts(name);

-- Concept mentions in claims
CREATE TABLE claim_concepts (
    claim_id TEXT NOT NULL,
    concept_id TEXT NOT NULL,
    first_mention_ts TEXT,
    context TEXT,
    
    PRIMARY KEY (claim_id, concept_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
);

-- Concept aliases (not JSON)
CREATE TABLE concept_aliases (
    concept_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    
    PRIMARY KEY (concept_id, alias),
    FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);
```

### Jargon Terms

```sql
CREATE TABLE jargon_terms (
    jargon_id TEXT PRIMARY KEY,
    term TEXT NOT NULL UNIQUE,
    definition TEXT,
    domain TEXT                        -- 'economics', 'tech', 'medical'
);

CREATE INDEX idx_jargon_term ON jargon_terms(term);

-- Jargon usage in claims
CREATE TABLE claim_jargon (
    claim_id TEXT NOT NULL,
    jargon_id TEXT NOT NULL,
    context TEXT,
    first_mention_ts TEXT,
    
    PRIMARY KEY (claim_id, jargon_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (jargon_id) REFERENCES jargon_terms(jargon_id)
);
```

---

## Relations Between Claims

```sql
CREATE TABLE claim_relations (
    source_claim_id TEXT NOT NULL,
    target_claim_id TEXT NOT NULL,
    relation_type TEXT CHECK (relation_type IN ('supports','contradicts','depends_on','refines')),
    strength REAL CHECK (strength BETWEEN 0 AND 1),
    rationale TEXT,
    
    PRIMARY KEY (source_claim_id, target_claim_id, relation_type),
    FOREIGN KEY (source_claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (target_claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
);

CREATE INDEX idx_claim_relations_source ON claim_relations(source_claim_id);
CREATE INDEX idx_claim_relations_target ON claim_relations(target_claim_id);
```

---

## Platform-Specific Metadata (Not JSON)

### YouTube Categories (from platform)

```sql
CREATE TABLE youtube_categories (
    category_id INTEGER PRIMARY KEY,
    category_name TEXT NOT NULL UNIQUE
);

-- Source categories (many-to-many)
CREATE TABLE source_platform_categories (
    source_id TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    
    PRIMARY KEY (source_id, category_id),
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES youtube_categories(category_id)
);
```

### YouTube Tags (from platform)

```sql
CREATE TABLE youtube_tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT NOT NULL UNIQUE
);

-- Source tags (many-to-many)
CREATE TABLE source_platform_tags (
    source_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    
    PRIMARY KEY (source_id, tag_id),
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES youtube_tags(tag_id)
);
```

---

## Export Tracking (Not JSON)

```sql
CREATE TABLE export_destinations (
    destination_id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_name TEXT NOT NULL UNIQUE  -- 'getreceipts', 'obsidian', 'notion'
);

CREATE TABLE claim_exports (
    claim_id TEXT NOT NULL,
    destination_id INTEGER NOT NULL,
    exported_at DATETIME DEFAULT (datetime('now')),
    export_url TEXT,
    export_status TEXT DEFAULT 'success',
    
    PRIMARY KEY (claim_id, destination_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (destination_id) REFERENCES export_destinations(destination_id)
);
```

---

## Summary: Zero JSON, Pure SQL

**Every piece of data is:**
- ✅ A proper table with proper types
- ✅ Queryable with SQL WHERE/JOIN
- ✅ Indexed for performance
- ✅ Enforced with FK constraints
- ✅ Updateable without JSON parsing

**No more:**
- ❌ `user_tags_json TEXT`
- ❌ `aliases_json TEXT`
- ❌ `external_ids_json TEXT`
- ❌ `structured_categories_json TEXT`
- ❌ `scores_json TEXT`

**Everything is normalized!**
