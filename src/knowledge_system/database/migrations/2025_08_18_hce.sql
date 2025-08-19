-- 2025-08-18: Initial HCE schema (SQLite)
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS episodes (
  episode_id   TEXT PRIMARY KEY,
  video_id     TEXT UNIQUE,
  title        TEXT,
  recorded_at  TEXT,
  inserted_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS claims (
  episode_id       TEXT NOT NULL,
  claim_id         TEXT NOT NULL,
  canonical        TEXT NOT NULL,
  claim_type       TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
  tier             TEXT CHECK (tier IN ('A','B','C')),
  first_mention_ts TEXT,
  scores_json      TEXT NOT NULL,
  inserted_at      TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (episode_id, claim_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence_spans (
  episode_id  TEXT NOT NULL,
  claim_id    TEXT NOT NULL,
  seq         INTEGER NOT NULL,
  segment_id  TEXT,
  t0          TEXT,
  t1          TEXT,
  quote       TEXT,
  PRIMARY KEY (episode_id, claim_id, seq),
  FOREIGN KEY (episode_id, claim_id) REFERENCES claims(episode_id, claim_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relations (
  episode_id       TEXT NOT NULL,
  source_claim_id  TEXT NOT NULL,
  target_claim_id  TEXT NOT NULL,
  type             TEXT CHECK (type IN ('supports','contradicts','depends_on','refines')),
  strength         REAL CHECK (strength BETWEEN 0 AND 1),
  rationale        TEXT,
  PRIMARY KEY (episode_id, source_claim_id, target_claim_id, type),
  FOREIGN KEY (episode_id, source_claim_id) REFERENCES claims(episode_id, claim_id) ON DELETE CASCADE,
  FOREIGN KEY (episode_id, target_claim_id) REFERENCES claims(episode_id, claim_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS people (
  episode_id        TEXT NOT NULL,
  mention_id        TEXT NOT NULL,
  span_segment_id   TEXT,
  t0                TEXT,
  t1                TEXT,
  surface           TEXT NOT NULL,
  normalized        TEXT,
  entity_type       TEXT CHECK (entity_type IN ('person','org')) DEFAULT 'person',
  external_ids_json TEXT,
  confidence        REAL,
  PRIMARY KEY (episode_id, mention_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS concepts (
  episode_id        TEXT NOT NULL,
  model_id          TEXT NOT NULL,
  name              TEXT NOT NULL,
  definition        TEXT,
  first_mention_ts  TEXT,
  aliases_json      TEXT,
  evidence_json     TEXT,
  PRIMARY KEY (episode_id, model_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jargon (
  episode_id    TEXT NOT NULL,
  term_id       TEXT NOT NULL,
  term          TEXT NOT NULL,
  category      TEXT,
  definition    TEXT,
  evidence_json TEXT,
  PRIMARY KEY (episode_id, term_id),
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
  episode_id, claim_id, canonical, claim_type, content=''
);
CREATE VIRTUAL TABLE IF NOT EXISTS quotes_fts USING fts5(
  episode_id, claim_id, quote, content=''
);

CREATE INDEX IF NOT EXISTS idx_claims_episode_tier ON claims(episode_id, tier);
CREATE INDEX IF NOT EXISTS idx_people_normalized ON people(normalized);
CREATE INDEX IF NOT EXISTS idx_concepts_name ON concepts(name);
CREATE INDEX IF NOT EXISTS idx_jargon_term ON jargon(term);
