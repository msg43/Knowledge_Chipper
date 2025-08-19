-- HCE schema migration
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS hce_claims (
  claim_id TEXT PRIMARY KEY,
  video_id TEXT NOT NULL,
  episode_id TEXT,
  canonical_text TEXT NOT NULL,
  claim_type TEXT,
  evidence_json TEXT,
  scores_json TEXT,
  tier TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE TABLE IF NOT EXISTS hce_relations (
  relation_id TEXT PRIMARY KEY,
  source_claim_id TEXT NOT NULL,
  target_claim_id TEXT NOT NULL,
  relation_type TEXT,
  strength REAL,
  rationale TEXT,
  FOREIGN KEY (source_claim_id) REFERENCES hce_claims(claim_id),
  FOREIGN KEY (target_claim_id) REFERENCES hce_claims(claim_id)
);

CREATE TABLE IF NOT EXISTS hce_entities (
  entity_id TEXT PRIMARY KEY,
  episode_id TEXT,
  video_id TEXT,
  type TEXT, -- person, org, concept, jargon
  surface TEXT,
  normalized TEXT,
  data_json TEXT,
  FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
  claim_id, video_id, episode_id, canonical_text, claim_type, content=''
);
CREATE VIRTUAL TABLE IF NOT EXISTS quotes_fts USING fts5(
  claim_id, video_id, quote, content=''
);
