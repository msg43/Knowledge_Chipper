-- Unified HCE Schema - Combines best of both worlds
-- Version: 2.0 (Unification)
-- Date: 2025-10-23
-- Purpose: Single source of truth for all HCE data with rich evidence and relations

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Episodes table (namespaced for HCE)
CREATE TABLE IF NOT EXISTS hce_episodes (
  source_id TEXT PRIMARY KEY,
  source_id TEXT,
  title TEXT NOT NULL,
  subtitle TEXT,
  description TEXT,
  recorded_at TEXT,
  inserted_at TEXT DEFAULT (datetime('now')),
  processed_at DATETIME
);

-- Segments table for storing transcript segments (HCE)
CREATE TABLE IF NOT EXISTS hce_segments (
  source_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  speaker TEXT,
  t0 TEXT,                          -- Start timestamp
  t1 TEXT,                          -- End timestamp
  text TEXT,
  topic_guess TEXT,                 -- Optional topic inference
  PRIMARY KEY (source_id, segment_id),
  FOREIGN KEY (source_id) REFERENCES hce_episodes(source_id) ON DELETE CASCADE
);

-- Claims table (HCE)
CREATE TABLE IF NOT EXISTS hce_claims (
  source_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  canonical TEXT NOT NULL,
  original_text TEXT,
  claim_type TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
  tier TEXT CHECK (tier IN ('A','B','C')),
  first_mention_ts TEXT,
  scores_json TEXT NOT NULL,

  -- Evaluation metadata
  evaluator_notes TEXT,

  -- Temporality analysis
  temporality_score INTEGER CHECK (temporality_score IN (1,2,3,4,5)) DEFAULT 3,
  temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1) DEFAULT 0.5,
  temporality_rationale TEXT,

  -- Structured categories
  structured_categories_json TEXT,
  category_relevance_scores_json TEXT,

  -- Upload tracking
  upload_status TEXT DEFAULT 'pending',
  upload_timestamp DATETIME,
  upload_error TEXT,

  -- Timestamps
  created_at DATETIME DEFAULT (datetime('now')),
  updated_at DATETIME DEFAULT (datetime('now')),
  inserted_at TEXT DEFAULT (datetime('now')),

  PRIMARY KEY (source_id, claim_id),
  FOREIGN KEY (source_id) REFERENCES hce_episodes(source_id) ON DELETE CASCADE
);

-- Evidence spans (HCE)
CREATE TABLE IF NOT EXISTS hce_evidence_spans (
  source_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  segment_id TEXT,

  -- Precise quote level
  t0 TEXT,
  t1 TEXT,
  quote TEXT,

  -- Extended context level
  context_t0 TEXT,
  context_t1 TEXT,
  context_text TEXT,
  context_type TEXT DEFAULT 'exact' CHECK (context_type IN ('exact', 'extended', 'segment')),

  PRIMARY KEY (source_id, claim_id, seq),
  FOREIGN KEY (source_id, claim_id) REFERENCES hce_claims(source_id, claim_id) ON DELETE CASCADE,
  FOREIGN KEY (source_id, segment_id) REFERENCES hce_segments(source_id, segment_id)
);

-- Relations between claims (HCE)
CREATE TABLE IF NOT EXISTS hce_relations (
  source_id TEXT NOT NULL,
  source_claim_id TEXT NOT NULL,
  target_claim_id TEXT NOT NULL,
  type TEXT CHECK (type IN ('supports','contradicts','depends_on','refines')),
  strength REAL CHECK (strength BETWEEN 0 AND 1),
  rationale TEXT,
  PRIMARY KEY (source_id, source_claim_id, target_claim_id, type),
  FOREIGN KEY (source_id, source_claim_id) REFERENCES hce_claims(source_id, claim_id) ON DELETE CASCADE,
  FOREIGN KEY (source_id, target_claim_id) REFERENCES hce_claims(source_id, claim_id) ON DELETE CASCADE
);

-- People table (HCE)
CREATE TABLE IF NOT EXISTS hce_people (
  source_id TEXT NOT NULL,
  person_id TEXT NOT NULL,
  mention_id TEXT,
  span_segment_id TEXT,
  t0 TEXT,
  t1 TEXT,

  -- Person information
  name TEXT NOT NULL,
  surface TEXT,
  normalized TEXT,
  description TEXT,
  entity_type TEXT CHECK (entity_type IN ('person','org')) DEFAULT 'person',
  external_ids_json TEXT,
  confidence REAL,

  -- Context
  first_mention_ts TEXT,
  context_quote TEXT,

  -- Timestamps
  created_at DATETIME DEFAULT (datetime('now')),
  updated_at DATETIME DEFAULT (datetime('now')),

  PRIMARY KEY (source_id, person_id),
  FOREIGN KEY (source_id) REFERENCES hce_episodes(source_id) ON DELETE CASCADE
);

-- Concepts table (HCE)
CREATE TABLE IF NOT EXISTS hce_concepts (
  source_id TEXT NOT NULL,
  concept_id TEXT NOT NULL,
  model_id TEXT,

  -- Concept information
  name TEXT NOT NULL,
  description TEXT,
  definition TEXT,
  first_mention_ts TEXT,

  -- Additional metadata
  aliases_json TEXT,
  evidence_json TEXT,
  context_quote TEXT,

  -- Timestamps
  created_at DATETIME DEFAULT (datetime('now')),
  updated_at DATETIME DEFAULT (datetime('now')),

  PRIMARY KEY (source_id, concept_id),
  FOREIGN KEY (source_id) REFERENCES hce_episodes(source_id) ON DELETE CASCADE
);

-- Jargon table (HCE)
CREATE TABLE IF NOT EXISTS hce_jargon (
  source_id TEXT NOT NULL,
  term_id TEXT NOT NULL,

  -- Jargon information
  term TEXT NOT NULL,
  definition TEXT,
  category TEXT,
  first_mention_ts TEXT,

  -- Additional metadata
  evidence_json TEXT,
  context_quote TEXT,

  -- Timestamps
  created_at DATETIME DEFAULT (datetime('now')),
  updated_at DATETIME DEFAULT (datetime('now')),

  PRIMARY KEY (source_id, term_id),
  FOREIGN KEY (source_id) REFERENCES hce_episodes(source_id) ON DELETE CASCADE
);

-- Structured categories (HCE)
CREATE TABLE IF NOT EXISTS hce_structured_categories (
  source_id TEXT NOT NULL,
  category_id TEXT NOT NULL,
  category_name TEXT NOT NULL,
  wikidata_qid TEXT,
  coverage_confidence REAL CHECK (coverage_confidence BETWEEN 0 AND 1) DEFAULT 0.5,
  supporting_evidence_json TEXT,
  frequency_score REAL CHECK (frequency_score BETWEEN 0 AND 1) DEFAULT 0.0,
  PRIMARY KEY (source_id, category_id),
  FOREIGN KEY (source_id) REFERENCES hce_episodes(source_id) ON DELETE CASCADE
);

-- Milestones for episode chapters/sections (HCE)
CREATE TABLE IF NOT EXISTS hce_milestones (
  source_id TEXT NOT NULL,
  milestone_id TEXT NOT NULL,
  t0 TEXT,
  t1 TEXT,
  summary TEXT,
  PRIMARY KEY (source_id, milestone_id),
  FOREIGN KEY (source_id) REFERENCES hce_episodes(source_id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS hce_claims_fts USING fts5(
  source_id,
  claim_id,
  canonical,
  claim_type,
  content=''                        -- Contentless, data stored in claims table
);

CREATE VIRTUAL TABLE IF NOT EXISTS hce_quotes_fts USING fts5(
  source_id,
  claim_id,
  quote,
  content=''                        -- Contentless, data stored in evidence_spans
);

CREATE INDEX IF NOT EXISTS idx_hce_claims_episode_tier ON hce_claims(source_id, tier);
CREATE INDEX IF NOT EXISTS idx_hce_claims_first_mention ON hce_claims(first_mention_ts);
CREATE INDEX IF NOT EXISTS idx_hce_claims_temporality ON hce_claims(temporality_score, temporality_confidence);
CREATE INDEX IF NOT EXISTS idx_hce_evidence_spans_segment ON hce_evidence_spans(source_id, segment_id);
CREATE INDEX IF NOT EXISTS idx_hce_relations_type ON hce_relations(type);
CREATE INDEX IF NOT EXISTS idx_hce_people_normalized ON hce_people(normalized);
CREATE INDEX IF NOT EXISTS idx_hce_people_name ON hce_people(name);
CREATE INDEX IF NOT EXISTS idx_hce_concepts_name ON hce_concepts(name);
CREATE INDEX IF NOT EXISTS idx_hce_jargon_term ON hce_jargon(term);
CREATE INDEX IF NOT EXISTS idx_hce_structured_categories_name ON hce_structured_categories(category_name);
CREATE INDEX IF NOT EXISTS idx_hce_structured_categories_confidence ON hce_structured_categories(coverage_confidence);

CREATE VIEW IF NOT EXISTS hce_v_episode_claims AS
SELECT
  c.source_id,
  c.claim_id,
  c.canonical,
  c.claim_type,
  c.tier,
  c.first_mention_ts,
  json_extract(c.scores_json, '$.importance') as importance,
  json_extract(c.scores_json, '$.novelty') as novelty,
  json_extract(c.scores_json, '$.controversy') as controversy,
  COUNT(e.seq) as evidence_count
FROM hce_claims c
LEFT JOIN hce_evidence_spans e ON c.source_id = e.source_id AND c.claim_id = e.claim_id
GROUP BY c.source_id, c.claim_id;

CREATE VIEW IF NOT EXISTS hce_v_claim_relations AS
SELECT
  r.source_id,
  r.source_claim_id,
  sc.canonical as source_claim,
  r.type as relation_type,
  r.target_claim_id,
  tc.canonical as target_claim,
  r.strength,
  r.rationale
FROM hce_relations r
JOIN hce_claims sc ON r.source_id = sc.source_id AND r.source_claim_id = sc.claim_id
JOIN hce_claims tc ON r.source_id = tc.source_id AND r.target_claim_id = tc.claim_id;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT DEFAULT (datetime('now')),
  description TEXT
);

INSERT OR REPLACE INTO schema_version (version, description)
VALUES (2, 'Unified schema - Storage path consolidation');
