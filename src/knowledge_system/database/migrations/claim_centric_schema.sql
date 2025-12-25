-- Claim-Centric Schema
-- Version: 3.0 (Claim-Centric Architecture)
-- Date: 2024-10-27
-- Purpose: Claims as the fundamental unit, sources as attribution metadata

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ============================================================================
-- CORE: Sources (Attribution Layer)
-- ============================================================================

-- Media sources: Where claims come from
CREATE TABLE IF NOT EXISTS media_sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL CHECK (source_type IN ('episode', 'document', 'youtube', 'pdf', 'article', 'podcast', 'rss')),
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT,

    -- Author/Creator info (from platform)
    uploader TEXT,
    uploader_id TEXT,
    author TEXT,
    organization TEXT,

    -- Temporal metadata (from platform)
    upload_date TEXT,
    recorded_at TEXT,
    published_at TEXT,

    -- Platform metrics (from platform)
    duration_seconds INTEGER,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER,

    -- Technical metadata
    privacy_status TEXT,
    caption_availability BOOLEAN,
    language TEXT,

    -- Local storage paths
    thumbnail_url TEXT,
    thumbnail_local_path TEXT,
    audio_file_path TEXT,

    -- Audio file tracking (for partial download detection and cleanup)
    audio_downloaded BOOLEAN DEFAULT 0,
    audio_file_size_bytes INTEGER,
    audio_format TEXT,

    -- Metadata completion tracking
    metadata_complete BOOLEAN DEFAULT 0,

    -- Retry tracking (for smart retry logic)
    needs_metadata_retry BOOLEAN DEFAULT 0,
    needs_audio_retry BOOLEAN DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    last_retry_at DATETIME,
    first_failure_at DATETIME,

    -- Failure tracking (after max retries exceeded)
    max_retries_exceeded BOOLEAN DEFAULT 0,
    failure_reason TEXT,

    -- Processing status
    status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    processed_at DATETIME,

    -- Episode-specific fields (for source_type='episode')
    -- Moved from episodes table - episode data is now stored directly in MediaSource
    subtitle TEXT,
    short_summary TEXT,
    long_summary TEXT,
    summary_generated_at DATETIME,
    summary_generated_by_model TEXT,

    -- Summary metrics
    input_length INTEGER,
    output_length INTEGER,
    compression_ratio REAL,

    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    fetched_at DATETIME,
    updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX idx_media_sources_type ON media_sources(source_type);
CREATE INDEX idx_media_sources_uploader ON media_sources(uploader);
CREATE INDEX idx_media_sources_upload_date ON media_sources(upload_date);

-- Segments: Temporal chunks for sources (typically source_type='episode')
-- Note: speaker field removed - speaker attribution now at entity level (claims, jargon, concepts)
CREATE TABLE IF NOT EXISTS segments (
    segment_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    text TEXT NOT NULL,
    topic_guess TEXT,

    sequence INTEGER,

    created_at DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE
);

CREATE INDEX idx_segments_source ON segments(source_id);
CREATE INDEX idx_segments_sequence ON segments(source_id, sequence);

-- ============================================================================
-- CORE: Claims (Fundamental Unit)
-- ============================================================================

-- Claims: The atomic unit of knowledge
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,

    -- Attribution (optional - some claims might be synthetic)
    source_id TEXT,

    -- Content
    canonical TEXT NOT NULL,
    original_text TEXT,
    claim_type TEXT CHECK (claim_type IN ('factual', 'causal', 'normative', 'forecast', 'definition')),
    domain TEXT,  -- Broad field classification (e.g., 'physics', 'economics', 'politics')

    -- System evaluation (from HCE)
    tier TEXT CHECK (tier IN ('A', 'B', 'C')),
    importance_score REAL CHECK (importance_score BETWEEN 0 AND 1),
    specificity_score REAL CHECK (specificity_score BETWEEN 0 AND 1),
    verifiability_score REAL CHECK (verifiability_score BETWEEN 0 AND 1),

    -- User curation
    user_tier_override TEXT CHECK (user_tier_override IN ('A', 'B', 'C')),
    user_confidence_override REAL CHECK (user_confidence_override BETWEEN 0 AND 1),
    evaluator_notes TEXT,

    -- Verification workflow
    verification_status TEXT CHECK (verification_status IN ('unverified', 'verified', 'disputed', 'false', 'unverifiable')) DEFAULT 'unverified',
    verification_source TEXT,
    verification_notes TEXT,

    -- Review workflow
    flagged_for_review BOOLEAN DEFAULT 0,
    reviewed_by TEXT,
    reviewed_at DATETIME,
    user_notes TEXT,

    -- Temporality analysis
    temporality_score INTEGER CHECK (temporality_score IN (1, 2, 3, 4, 5)) DEFAULT 3,
    temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1) DEFAULT 0.5,
    temporality_rationale TEXT,
    first_mention_ts TEXT,

    -- Export tracking
    upload_status TEXT DEFAULT 'pending',
    upload_timestamp DATETIME,
    upload_error TEXT,

    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE SET NULL
);

CREATE INDEX idx_claims_source ON claims(source_id);
CREATE INDEX idx_claims_tier ON claims(tier);
CREATE INDEX idx_claims_type ON claims(claim_type);
CREATE INDEX idx_claims_domain ON claims(domain);
CREATE INDEX idx_claims_verification ON claims(verification_status);
CREATE INDEX idx_claims_flagged ON claims(flagged_for_review) WHERE flagged_for_review = 1;
CREATE INDEX idx_claims_created ON claims(created_at);
CREATE INDEX idx_claims_user_notes ON claims(user_notes) WHERE user_notes IS NOT NULL;

-- ============================================================================
-- EVIDENCE & CONTEXT
-- ============================================================================

-- Evidence spans: Supporting quotes for claims
-- Uses canonical field names matching HCE schema and GetReceipts API
CREATE TABLE IF NOT EXISTS evidence_spans (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    segment_id TEXT,  -- Optional (only for episode sources)
    seq INTEGER NOT NULL,  -- Canonical: matches HCE schema and GetReceipts API

    -- Precise quote - canonical field names
    t0 TEXT,  -- Canonical: matches HCE schema and GetReceipts API
    t1 TEXT,  -- Canonical: matches HCE schema and GetReceipts API
    quote TEXT,

    -- Extended context - canonical field names
    context_t0 TEXT,  -- Canonical: matches HCE schema and GetReceipts API
    context_t1 TEXT,  -- Canonical: matches HCE schema and GetReceipts API
    context_text TEXT,
    context_type TEXT DEFAULT 'exact' CHECK (context_type IN ('exact', 'extended', 'segment')),

    -- For document sources (page numbers, etc.)
    page_number INTEGER,
    paragraph_number INTEGER,

    created_at DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (segment_id) REFERENCES segments(segment_id) ON DELETE SET NULL
);

CREATE INDEX idx_evidence_claim ON evidence_spans(claim_id);
CREATE INDEX idx_evidence_segment ON evidence_spans(segment_id);

-- Claim relations: How claims relate to each other
CREATE TABLE IF NOT EXISTS claim_relations (
    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_claim_id TEXT NOT NULL,
    target_claim_id TEXT NOT NULL,
    relation_type TEXT CHECK (relation_type IN ('supports', 'contradicts', 'depends_on', 'refines', 'related_to')),
    strength REAL CHECK (strength BETWEEN 0 AND 1),
    rationale TEXT,

    created_at DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (source_claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (target_claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    UNIQUE(source_claim_id, target_claim_id, relation_type)
);

CREATE INDEX idx_claim_relations_source ON claim_relations(source_claim_id);
CREATE INDEX idx_claim_relations_target ON claim_relations(target_claim_id);
CREATE INDEX idx_claim_relations_type ON claim_relations(relation_type);

-- ============================================================================
-- ENTITIES: People, Concepts, Jargon
-- ============================================================================

-- People/Organizations catalog
CREATE TABLE IF NOT EXISTS people (
    person_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    normalized_name TEXT,
    description TEXT,
    entity_type TEXT CHECK (entity_type IN ('person', 'organization')) DEFAULT 'person',
    confidence REAL CHECK (confidence BETWEEN 0 AND 1),

    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX idx_people_name ON people(name);
CREATE INDEX idx_people_normalized ON people(normalized_name);
CREATE INDEX idx_people_type ON people(entity_type);

-- Person mentions in claims
CREATE TABLE IF NOT EXISTS claim_people (
    claim_id TEXT NOT NULL,
    person_id TEXT NOT NULL,

    mention_context TEXT,
    first_mention_ts TEXT,
    role TEXT,  -- 'subject', 'object', 'mentioned'

    created_at DATETIME DEFAULT (datetime('now')),

    PRIMARY KEY (claim_id, person_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES people(person_id) ON DELETE CASCADE
);

CREATE INDEX idx_claim_people_claim ON claim_people(claim_id);
CREATE INDEX idx_claim_people_person ON claim_people(person_id);

-- External IDs for people (WikiData, Wikipedia, etc.)
CREATE TABLE IF NOT EXISTS person_external_ids (
    person_id TEXT NOT NULL,
    external_system TEXT NOT NULL,  -- 'wikidata', 'wikipedia', 'twitter', etc.
    external_id TEXT NOT NULL,

    PRIMARY KEY (person_id, external_system),
    FOREIGN KEY (person_id) REFERENCES people(person_id) ON DELETE CASCADE
);

CREATE INDEX idx_person_external_system ON person_external_ids(external_system);

-- Concepts / Mental Models catalog
CREATE TABLE IF NOT EXISTS concepts (
    concept_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    definition TEXT,

    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX idx_concepts_name ON concepts(name);

-- Concept mentions in claims
CREATE TABLE IF NOT EXISTS claim_concepts (
    claim_id TEXT NOT NULL,
    concept_id TEXT NOT NULL,

    first_mention_ts TEXT,
    context TEXT,

    created_at DATETIME DEFAULT (datetime('now')),

    PRIMARY KEY (claim_id, concept_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);

CREATE INDEX idx_claim_concepts_claim ON claim_concepts(claim_id);
CREATE INDEX idx_claim_concepts_concept ON claim_concepts(concept_id);

-- Concept aliases
CREATE TABLE IF NOT EXISTS concept_aliases (
    concept_id TEXT NOT NULL,
    alias TEXT NOT NULL,

    PRIMARY KEY (concept_id, alias),
    FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);

CREATE INDEX idx_concept_aliases_alias ON concept_aliases(alias);

-- Jargon terms catalog
CREATE TABLE IF NOT EXISTS jargon_terms (
    jargon_id TEXT PRIMARY KEY,
    term TEXT NOT NULL UNIQUE,
    definition TEXT,
    domain TEXT,  -- 'economics', 'technology', 'medical', etc.

    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX idx_jargon_term ON jargon_terms(term);
CREATE INDEX idx_jargon_domain ON jargon_terms(domain);

-- Jargon usage in claims
CREATE TABLE IF NOT EXISTS claim_jargon (
    claim_id TEXT NOT NULL,
    jargon_id TEXT NOT NULL,

    context TEXT,
    first_mention_ts TEXT,

    created_at DATETIME DEFAULT (datetime('now')),

    PRIMARY KEY (claim_id, jargon_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (jargon_id) REFERENCES jargon_terms(jargon_id) ON DELETE CASCADE
);

CREATE INDEX idx_claim_jargon_claim ON claim_jargon(claim_id);
CREATE INDEX idx_claim_jargon_term ON claim_jargon(jargon_id);

-- ============================================================================
-- CATEGORIES: WikiData Controlled Vocabulary
-- ============================================================================

-- WikiData categories vocabulary
CREATE TABLE IF NOT EXISTS wikidata_categories (
    wikidata_id TEXT PRIMARY KEY,  -- "Q186363"
    category_name TEXT NOT NULL UNIQUE,
    category_description TEXT,
    parent_wikidata_id TEXT,
    level TEXT CHECK (level IN ('general', 'specific')),

    -- For semantic matching
    embedding_vector BLOB,  -- Serialized numpy array for fast matching

    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (parent_wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);

CREATE INDEX idx_wikidata_name ON wikidata_categories(category_name);
CREATE INDEX idx_wikidata_parent ON wikidata_categories(parent_wikidata_id);
CREATE INDEX idx_wikidata_level ON wikidata_categories(level);

-- WikiData category aliases (for matching)
CREATE TABLE IF NOT EXISTS wikidata_aliases (
    wikidata_id TEXT NOT NULL,
    alias TEXT NOT NULL,

    PRIMARY KEY (wikidata_id, alias),
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id) ON DELETE CASCADE
);

CREATE INDEX idx_wikidata_aliases_alias ON wikidata_aliases(alias);

-- NOTE: Sources do NOT get their own WikiData categories
-- Episodes/sources are categorized by:
-- 1. Platform categories (from YouTube/RSS) - stored in platform_categories below
-- 2. Aggregated claim categories (what claims inside contain) - computed via JOIN, not stored

-- Claim categories (typically 1 specific topic)
CREATE TABLE IF NOT EXISTS claim_categories (
    claim_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,

    -- System scores
    relevance_score REAL CHECK (relevance_score BETWEEN 0 AND 1),
    confidence REAL CHECK (confidence BETWEEN 0 AND 1),

    -- Primary category flag
    is_primary BOOLEAN DEFAULT 0,

    -- User workflow
    user_approved BOOLEAN DEFAULT 0,
    user_rejected BOOLEAN DEFAULT 0,
    source TEXT DEFAULT 'system',  -- 'system' or 'user'

    -- Context
    context_quote TEXT,

    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),

    PRIMARY KEY (claim_id, wikidata_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);

CREATE INDEX idx_claim_categories_claim ON claim_categories(claim_id);
CREATE INDEX idx_claim_categories_category ON claim_categories(wikidata_id);
CREATE INDEX idx_claim_categories_primary ON claim_categories(is_primary) WHERE is_primary = 1;

-- Ensure only one primary category per claim
CREATE UNIQUE INDEX idx_claim_primary_category ON claim_categories(claim_id) WHERE is_primary = 1;

-- ============================================================================
-- USER TAGS (Separate from WikiData)
-- ============================================================================

-- User-defined tags
CREATE TABLE IF NOT EXISTS user_tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT UNIQUE NOT NULL,
    tag_color TEXT,
    description TEXT,

    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX idx_user_tags_name ON user_tags(tag_name);

-- Claim tags (many-to-many)
CREATE TABLE IF NOT EXISTS claim_tags (
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

-- ============================================================================
-- PLATFORM CATEGORIES (Uncontrolled - from YouTube, etc.)
-- ============================================================================

-- Platform categories (YouTube, iTunes, etc.)
CREATE TABLE IF NOT EXISTS platform_categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,  -- 'youtube', 'itunes', 'spotify', etc.
    category_name TEXT NOT NULL,

    UNIQUE(platform, category_name)
);

CREATE INDEX idx_platform_categories_platform ON platform_categories(platform);

-- Source platform categories (many-to-many)
CREATE TABLE IF NOT EXISTS source_platform_categories (
    source_id TEXT NOT NULL,
    category_id INTEGER NOT NULL,

    PRIMARY KEY (source_id, category_id),
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES platform_categories(category_id)
);

CREATE INDEX idx_source_platform_categories_source ON source_platform_categories(source_id);

-- Platform tags (YouTube tags, etc.)
CREATE TABLE IF NOT EXISTS platform_tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    tag_name TEXT NOT NULL,

    UNIQUE(platform, tag_name)
);

CREATE INDEX idx_platform_tags_platform ON platform_tags(platform);

-- Source platform tags (many-to-many)
CREATE TABLE IF NOT EXISTS source_platform_tags (
    source_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,

    PRIMARY KEY (source_id, tag_id),
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES platform_tags(tag_id)
);

CREATE INDEX idx_source_platform_tags_source ON source_platform_tags(source_id);

-- ============================================================================
-- EXPORT TRACKING
-- ============================================================================

-- Export destinations
CREATE TABLE IF NOT EXISTS export_destinations (
    destination_id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_name TEXT NOT NULL UNIQUE,  -- 'getreceipts', 'obsidian', 'notion', etc.
    destination_url TEXT,

    created_at DATETIME DEFAULT (datetime('now'))
);

-- Claim exports
CREATE TABLE IF NOT EXISTS claim_exports (
    claim_id TEXT NOT NULL,
    destination_id INTEGER NOT NULL,

    exported_at DATETIME DEFAULT (datetime('now')),
    export_url TEXT,
    export_status TEXT DEFAULT 'success',
    export_error TEXT,

    PRIMARY KEY (claim_id, destination_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (destination_id) REFERENCES export_destinations(destination_id)
);

CREATE INDEX idx_claim_exports_claim ON claim_exports(claim_id);
CREATE INDEX idx_claim_exports_destination ON claim_exports(destination_id);
CREATE INDEX idx_claim_exports_status ON claim_exports(export_status);

-- ============================================================================
-- VIEWS: Useful Query Helpers
-- ============================================================================

-- View: Claims with full attribution context
CREATE VIEW IF NOT EXISTS v_claims_with_context AS
SELECT
    c.*,
    ms.title AS source_title,
    ms.uploader AS source_author,
    ms.upload_date AS source_date,
    ms.source_type,
    e.short_summary AS episode_summary,
    e.long_summary AS episode_long_summary
FROM claims c
LEFT JOIN media_sources ms ON c.source_id = ms.source_id
LEFT JOIN episodes e ON c.source_id = e.source_id;

-- View: Claims with primary categories
CREATE VIEW IF NOT EXISTS v_claims_with_categories AS
SELECT
    c.*,
    cc.wikidata_id AS primary_category_id,
    wc.category_name AS primary_category_name
FROM claims c
LEFT JOIN claim_categories cc ON c.claim_id = cc.claim_id AND cc.is_primary = 1
LEFT JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id;

-- View: Source coverage (what categories does each source cover?)
CREATE VIEW IF NOT EXISTS v_source_coverage AS
SELECT
    ms.source_id,
    ms.title,
    GROUP_CONCAT(wc.category_name, ', ') AS categories,
    COUNT(DISTINCT c.claim_id) AS total_claims,
    COUNT(DISTINCT CASE WHEN c.tier = 'A' THEN c.claim_id END) AS tier_a_claims
FROM media_sources ms
LEFT JOIN source_categories sc ON ms.source_id = sc.source_id
LEFT JOIN wikidata_categories wc ON sc.wikidata_id = wc.wikidata_id
LEFT JOIN claims c ON ms.source_id = c.source_id
GROUP BY ms.source_id, ms.title;
