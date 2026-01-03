-- ============================================================================
-- MIGRATION 100: Minimal Extraction Schema for Knowledge_Chipper
-- Date: 2026-01-02
-- Purpose: Strip down to essentials - only what's needed for extraction/upload
-- Philosophy: SQLite is for local processing, Supabase is the canonical storage
-- ============================================================================

PRAGMA foreign_keys=OFF;  -- Temporarily disable for table drops
PRAGMA journal_mode=WAL;

-- ============================================================================
-- STEP 1: DROP OLD TABLES (Clean Slate)
-- ============================================================================

-- Drop old HCE-prefixed tables
DROP TABLE IF EXISTS hce_claims_fts;
DROP TABLE IF EXISTS hce_quotes_fts;
DROP TABLE IF EXISTS hce_relations;
DROP TABLE IF EXISTS hce_evidence_spans;
DROP TABLE IF EXISTS hce_claims;
DROP TABLE IF EXISTS hce_people;
DROP TABLE IF EXISTS hce_concepts;
DROP TABLE IF EXISTS hce_jargon;
DROP TABLE IF EXISTS hce_structured_categories;
DROP TABLE IF EXISTS hce_milestones;
DROP TABLE IF EXISTS hce_segments;
DROP TABLE IF EXISTS hce_episodes;

-- Drop any non-HCE legacy tables that might conflict
DROP TABLE IF EXISTS claim_jargon;
DROP TABLE IF EXISTS claim_people;
DROP TABLE IF EXISTS claim_concepts;
DROP TABLE IF EXISTS evidence_spans;
DROP TABLE IF EXISTS claims;
DROP TABLE IF EXISTS people;
DROP TABLE IF EXISTS jargon;
DROP TABLE IF EXISTS concepts;
DROP TABLE IF EXISTS segments;
DROP TABLE IF EXISTS milestones;

-- Drop other processing tables
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS prediction_history;
DROP TABLE IF EXISTS prediction_evidence;
DROP TABLE IF EXISTS health_interventions;
DROP TABLE IF EXISTS health_metrics;
DROP TABLE IF EXISTS health_issues;

SELECT 'Old tables dropped successfully ✅' as status;

-- ============================================================================
-- STEP 2: CREATE CORE EXTRACTION TABLES
-- ============================================================================

-- Media Sources - What to process
CREATE TABLE IF NOT EXISTS media_sources (
  source_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL CHECK (source_type IN ('episode', 'document', 'youtube', 'pdf', 'article', 'podcast', 'rss')),
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  description TEXT,
  
  -- Media metadata
  uploader TEXT,
  author TEXT,
  organization TEXT,
  duration_seconds INTEGER,
  language TEXT,
  
  -- Download tracking
  audio_file_path TEXT,
  audio_downloaded BOOLEAN DEFAULT FALSE,
  audio_file_size_bytes INTEGER,
  
  -- Processing status
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  processed_at DATETIME,
  
  -- Upload tracking
  upload_status TEXT DEFAULT 'pending' CHECK (upload_status IN ('pending', 'uploading', 'uploaded', 'failed')),
  upload_timestamp DATETIME,
  upload_error TEXT,
  
  -- Timestamps
  created_at DATETIME DEFAULT (datetime('now')),
  updated_at DATETIME DEFAULT (datetime('now'))
);

SELECT 'media_sources table created ✅' as status;

-- Segments - Transcript data for processing
CREATE TABLE IF NOT EXISTS segments (
  segment_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES media_sources(source_id) ON DELETE CASCADE,
  speaker TEXT,
  t0 TEXT,  -- Start timestamp
  t1 TEXT,  -- End timestamp
  text TEXT NOT NULL,
  seq INTEGER,  -- Sequence order
  created_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_segments_source_id ON segments(source_id);
CREATE INDEX IF NOT EXISTS idx_segments_seq ON segments(source_id, seq);

SELECT 'segments table created ✅' as status;

-- Claims - Extracted knowledge claims
CREATE TABLE IF NOT EXISTS claims (
  claim_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES media_sources(source_id) ON DELETE CASCADE,
  canonical TEXT NOT NULL,
  original_text TEXT,
  
  -- Classification
  claim_type TEXT CHECK (claim_type IN ('factual', 'causal', 'normative', 'forecast', 'definition')),
  domain TEXT,
  tier TEXT CHECK (tier IN ('A', 'B', 'C')),
  
  -- Scores (stored as JSON string)
  scores_json TEXT,  -- {"importance": 0.8, "novelty": 0.6, ...}
  
  -- Temporality
  temporality_score INTEGER CHECK (temporality_score IN (1, 2, 3, 4, 5)) DEFAULT 3,
  temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1),
  temporality_rationale TEXT,
  first_mention_ts TEXT,
  
  -- Speaker attribution
  speaker TEXT,
  
  -- Upload tracking
  upload_status TEXT DEFAULT 'pending' CHECK (upload_status IN ('pending', 'uploading', 'uploaded', 'failed')),
  upload_timestamp DATETIME,
  upload_error TEXT,
  last_uploaded_at TEXT,
  
  -- Timestamps
  created_at DATETIME DEFAULT (datetime('now')),
  updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_claims_source_id ON claims(source_id);
CREATE INDEX IF NOT EXISTS idx_claims_upload_status ON claims(upload_status);
CREATE INDEX IF NOT EXISTS idx_claims_tier ON claims(tier);

SELECT 'claims table created ✅' as status;

-- Evidence Spans - Quote attribution for claims
CREATE TABLE IF NOT EXISTS evidence_spans (
  evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
  claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  
  -- Segment reference
  segment_id TEXT,
  
  -- Precise quote
  t0 TEXT,
  t1 TEXT,
  quote TEXT,
  
  -- Extended context
  context_t0 TEXT,
  context_t1 TEXT,
  context_text TEXT,
  context_type TEXT DEFAULT 'exact' CHECK (context_type IN ('exact', 'extended', 'segment')),
  
  created_at DATETIME DEFAULT (datetime('now')),
  UNIQUE(claim_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_evidence_spans_claim_id ON evidence_spans(claim_id);

SELECT 'evidence_spans table created ✅' as status;

-- People - Extracted person/organization mentions
CREATE TABLE IF NOT EXISTS people (
  person_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES media_sources(source_id) ON DELETE CASCADE,
  
  -- Identity
  name TEXT NOT NULL,
  normalized_name TEXT,
  entity_type TEXT DEFAULT 'person' CHECK (entity_type IN ('person', 'organization')),
  
  -- Mention details
  surface TEXT,  -- How they appeared in text
  t0 TEXT,
  t1 TEXT,
  confidence REAL CHECK (confidence BETWEEN 0 AND 1),
  
  -- Upload tracking
  upload_status TEXT DEFAULT 'pending',
  upload_timestamp DATETIME,
  upload_error TEXT,
  
  created_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_people_source_id ON people(source_id);
CREATE INDEX IF NOT EXISTS idx_people_upload_status ON people(upload_status);
CREATE INDEX IF NOT EXISTS idx_people_normalized_name ON people(normalized_name);

SELECT 'people table created ✅' as status;

-- Jargon - Technical terms and domain-specific terminology
CREATE TABLE IF NOT EXISTS jargon (
  jargon_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES media_sources(source_id) ON DELETE CASCADE,
  
  term TEXT NOT NULL,
  definition TEXT,
  category TEXT,
  
  -- Upload tracking
  upload_status TEXT DEFAULT 'pending',
  upload_timestamp DATETIME,
  upload_error TEXT,
  
  created_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jargon_source_id ON jargon(source_id);
CREATE INDEX IF NOT EXISTS idx_jargon_upload_status ON jargon(upload_status);
CREATE INDEX IF NOT EXISTS idx_jargon_term ON jargon(term);

SELECT 'jargon table created ✅' as status;

-- Concepts - Mental models and frameworks
CREATE TABLE IF NOT EXISTS concepts (
  concept_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES media_sources(source_id) ON DELETE CASCADE,
  
  name TEXT NOT NULL,
  definition TEXT,
  description TEXT,
  
  -- Upload tracking
  upload_status TEXT DEFAULT 'pending',
  upload_timestamp DATETIME,
  upload_error TEXT,
  
  created_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_concepts_source_id ON concepts(source_id);
CREATE INDEX IF NOT EXISTS idx_concepts_upload_status ON concepts(upload_status);
CREATE INDEX IF NOT EXISTS idx_concepts_name ON concepts(name);

SELECT 'concepts table created ✅' as status;

-- ============================================================================
-- STEP 3: CREATE JUNCTION TABLES
-- ============================================================================

-- Claim-Jargon relationships
CREATE TABLE IF NOT EXISTS claim_jargon (
  claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
  jargon_id TEXT NOT NULL REFERENCES jargon(jargon_id) ON DELETE CASCADE,
  context TEXT,
  first_mention_ts TEXT,
  created_at DATETIME DEFAULT (datetime('now')),
  PRIMARY KEY (claim_id, jargon_id)
);

CREATE INDEX IF NOT EXISTS idx_claim_jargon_claim_id ON claim_jargon(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_jargon_jargon_id ON claim_jargon(jargon_id);

SELECT 'claim_jargon junction table created ✅' as status;

-- Claim-People relationships
CREATE TABLE IF NOT EXISTS claim_people (
  claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
  person_id TEXT NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
  role TEXT,
  mention_context TEXT,
  first_mention_ts TEXT,
  created_at DATETIME DEFAULT (datetime('now')),
  PRIMARY KEY (claim_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_claim_people_claim_id ON claim_people(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_people_person_id ON claim_people(person_id);

SELECT 'claim_people junction table created ✅' as status;

-- Claim-Concepts relationships
CREATE TABLE IF NOT EXISTS claim_concepts (
  claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
  concept_id TEXT NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
  context TEXT,
  first_mention_ts TEXT,
  created_at DATETIME DEFAULT (datetime('now')),
  PRIMARY KEY (claim_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_claim_concepts_claim_id ON claim_concepts(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_concepts_concept_id ON claim_concepts(concept_id);

SELECT 'claim_concepts junction table created ✅' as status;

-- ============================================================================
-- STEP 4: RE-ENABLE FOREIGN KEYS
-- ============================================================================

PRAGMA foreign_keys=ON;

-- ============================================================================
-- STEP 5: VERIFICATION
-- ============================================================================

-- Count tables
SELECT 
  COUNT(*) as total_tables,
  (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='media_sources') as has_media_sources,
  (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='claims') as has_claims,
  (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='people') as has_people,
  (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='jargon') as has_jargon,
  (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='concepts') as has_concepts
FROM sqlite_master 
WHERE type='table' AND name IN ('media_sources', 'segments', 'claims', 'evidence_spans', 'people', 'jargon', 'concepts', 'claim_jargon', 'claim_people', 'claim_concepts');

SELECT '✅ MIGRATION 100 COMPLETE: Minimal extraction schema ready!' as status;
SELECT 'Tables: media_sources, segments, claims, evidence_spans, people, jargon, concepts + 3 junction tables' as summary;

