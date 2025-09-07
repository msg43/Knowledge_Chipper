-- HCE SQLite Schema with FTS5 for Full-Text Search
-- This schema provides comprehensive storage for HCE pipeline outputs
-- with support for cross-episode analytics and fast search

-- Enable WAL mode and foreign keys for performance and integrity
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Episodes table (maps to existing videos table)
CREATE TABLE IF NOT EXISTS episodes (
  episode_id TEXT PRIMARY KEY,
  video_id TEXT UNIQUE,              -- FK to existing videos table if available
  title TEXT,
  recorded_at TEXT,                  -- ISO8601 timestamp
  inserted_at TEXT DEFAULT (datetime('now'))
);

-- Segments table for storing transcript segments
CREATE TABLE IF NOT EXISTS segments (
  episode_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  speaker TEXT,
  t0 TEXT,                          -- Start timestamp
  t1 TEXT,                          -- End timestamp
  text TEXT,
  topic_guess TEXT,                 -- Optional topic inference
  PRIMARY KEY (episode_id, segment_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Milestones for episode chapters/sections
CREATE TABLE IF NOT EXISTS milestones (
  episode_id TEXT NOT NULL,
  milestone_id TEXT NOT NULL,
  t0 TEXT,
  t1 TEXT,
  summary TEXT,
  PRIMARY KEY (episode_id, milestone_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Claims table with scoring, tiering, and temporality analysis
CREATE TABLE IF NOT EXISTS claims (
  episode_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,           -- Cluster ID, stable within episode
  canonical TEXT NOT NULL,          -- Consolidated claim text
  claim_type TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
  tier TEXT CHECK (tier IN ('A','B','C')),
  first_mention_ts TEXT,            -- Timestamp of first occurrence
  scores_json TEXT NOT NULL,        -- JSON: {"importance":0.8, "novelty":0.7, "controversy":0.2}

  -- Temporality analysis (new)
  temporality_score INTEGER CHECK (temporality_score IN (1,2,3,4,5)) DEFAULT 3,  -- 1=Immediate, 5=Timeless
  temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1) DEFAULT 0.5,
  temporality_rationale TEXT,       -- Why this claim has this temporality

  -- Structured categories (new)
  structured_categories_json TEXT,  -- JSON array of category names
  category_relevance_scores_json TEXT,  -- JSON object mapping categories to relevance scores

  inserted_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (episode_id, claim_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Evidence spans linking claims to source quotes with dual-level context
CREATE TABLE IF NOT EXISTS evidence_spans (
  episode_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  seq INTEGER NOT NULL,             -- Sequence number (0..n)
  segment_id TEXT,                  -- Reference to segment

  -- Precise quote level
  t0 TEXT,                         -- Exact start timestamp of quote
  t1 TEXT,                         -- Exact end timestamp of quote
  quote TEXT,                      -- Precise verbatim quote

  -- Extended context level
  context_t0 TEXT,                 -- Extended context start timestamp
  context_t1 TEXT,                 -- Extended context end timestamp
  context_text TEXT,               -- Extended conversational context
  context_type TEXT DEFAULT 'exact' CHECK (context_type IN ('exact', 'extended', 'segment')),

  PRIMARY KEY (episode_id, claim_id, seq),
  FOREIGN KEY (episode_id, claim_id) REFERENCES claims(episode_id, claim_id) ON DELETE CASCADE,
  FOREIGN KEY (episode_id, segment_id) REFERENCES segments(episode_id, segment_id)
);

-- Relations between claims
CREATE TABLE IF NOT EXISTS relations (
  episode_id TEXT NOT NULL,
  source_claim_id TEXT NOT NULL,
  target_claim_id TEXT NOT NULL,
  type TEXT CHECK (type IN ('supports','contradicts','depends_on','refines')),
  strength REAL CHECK (strength BETWEEN 0 AND 1),
  rationale TEXT,
  PRIMARY KEY (episode_id, source_claim_id, target_claim_id, type),
  FOREIGN KEY (episode_id, source_claim_id) REFERENCES claims(episode_id, claim_id) ON DELETE CASCADE,
  FOREIGN KEY (episode_id, target_claim_id) REFERENCES claims(episode_id, claim_id) ON DELETE CASCADE
);

-- People and organization mentions
CREATE TABLE IF NOT EXISTS people (
  episode_id TEXT NOT NULL,
  mention_id TEXT NOT NULL,
  span_segment_id TEXT,
  t0 TEXT,
  t1 TEXT,
  surface TEXT NOT NULL,            -- As mentioned in text
  normalized TEXT,                  -- Canonical form
  entity_type TEXT CHECK (entity_type IN ('person','org')) DEFAULT 'person',
  external_ids_json TEXT,           -- JSON: {"wikipedia":"...", "wikidata":"Q..."}
  confidence REAL,
  PRIMARY KEY (episode_id, mention_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Mental models and concepts
CREATE TABLE IF NOT EXISTS concepts (
  episode_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  name TEXT NOT NULL,
  definition TEXT,
  first_mention_ts TEXT,
  aliases_json TEXT,                -- JSON array: ["barbell strategy", "barbell approach"]
  evidence_json TEXT,               -- JSON array of evidence spans
  PRIMARY KEY (episode_id, model_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Jargon and technical terms
CREATE TABLE IF NOT EXISTS jargon (
  episode_id TEXT NOT NULL,
  term_id TEXT NOT NULL,
  term TEXT NOT NULL,
  category TEXT,                    -- e.g., "technical", "industry", "acronym"
  definition TEXT,
  evidence_json TEXT,               -- JSON array of evidence spans
  PRIMARY KEY (episode_id, term_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Structured categories (Wikidata-style topic classification)
CREATE TABLE IF NOT EXISTS structured_categories (
  episode_id TEXT NOT NULL,
  category_id TEXT NOT NULL,
  category_name TEXT NOT NULL,
  wikidata_qid TEXT,                -- Wikidata Q-identifier if available
  coverage_confidence REAL CHECK (coverage_confidence BETWEEN 0 AND 1) DEFAULT 0.5,
  supporting_evidence_json TEXT,    -- JSON array of claim IDs supporting this categorization
  frequency_score REAL CHECK (frequency_score BETWEEN 0 AND 1) DEFAULT 0.0,
  PRIMARY KEY (episode_id, category_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- Full-text search tables (contentless for efficiency)
CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
  episode_id,
  claim_id,
  canonical,
  claim_type,
  content=''                        -- Contentless, data stored in claims table
);

CREATE VIRTUAL TABLE IF NOT EXISTS quotes_fts USING fts5(
  episode_id,
  claim_id,
  quote,
  content=''                        -- Contentless, data stored in evidence_spans
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_claims_episode_tier ON claims(episode_id, tier);
CREATE INDEX IF NOT EXISTS idx_claims_first_mention ON claims(first_mention_ts);
CREATE INDEX IF NOT EXISTS idx_claims_temporality ON claims(temporality_score, temporality_confidence);
CREATE INDEX IF NOT EXISTS idx_evidence_spans_segment ON evidence_spans(episode_id, segment_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(type);
CREATE INDEX IF NOT EXISTS idx_people_normalized ON people(normalized);
CREATE INDEX IF NOT EXISTS idx_concepts_name ON concepts(name);
CREATE INDEX IF NOT EXISTS idx_jargon_term ON jargon(term);
CREATE INDEX IF NOT EXISTS idx_structured_categories_name ON structured_categories(category_name);
CREATE INDEX IF NOT EXISTS idx_structured_categories_confidence ON structured_categories(coverage_confidence);

-- Useful views for common queries
CREATE VIEW IF NOT EXISTS v_episode_claims AS
SELECT
  c.episode_id,
  c.claim_id,
  c.canonical,
  c.claim_type,
  c.tier,
  c.first_mention_ts,
  json_extract(c.scores_json, '$.importance') as importance,
  json_extract(c.scores_json, '$.novelty') as novelty,
  json_extract(c.scores_json, '$.controversy') as controversy,
  COUNT(e.seq) as evidence_count
FROM claims c
LEFT JOIN evidence_spans e ON c.episode_id = e.episode_id AND c.claim_id = e.claim_id
GROUP BY c.episode_id, c.claim_id;

CREATE VIEW IF NOT EXISTS v_claim_relations AS
SELECT
  r.episode_id,
  r.source_claim_id,
  sc.canonical as source_claim,
  r.type as relation_type,
  r.target_claim_id,
  tc.canonical as target_claim,
  r.strength,
  r.rationale
FROM relations r
JOIN claims sc ON r.episode_id = sc.episode_id AND r.source_claim_id = sc.claim_id
JOIN claims tc ON r.episode_id = tc.episode_id AND r.target_claim_id = tc.claim_id;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT DEFAULT (datetime('now')),
  description TEXT
);

-- Insert initial version
INSERT OR IGNORE INTO schema_version (version, description)
VALUES (1, 'Initial HCE schema with FTS5 support');
