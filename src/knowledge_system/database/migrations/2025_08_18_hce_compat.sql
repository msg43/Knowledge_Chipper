-- Backward-compatibility views to preserve existing readers while HCE replaces legacy.

DROP VIEW IF EXISTS legacy_claims;
CREATE VIEW legacy_claims AS
SELECT
  c.claim_id               AS claim_id,
  e.source_id             AS source_id,
  c.canonical              AS text,
  c.claim_type             AS type,
  c.scores_json            AS score_json,
  c.inserted_at            AS created_at
FROM claims c
LEFT JOIN evidence_spans e
  ON e.source_id = c.source_id AND e.claim_id = c.claim_id AND e.seq = 0;

DROP VIEW IF EXISTS legacy_relations;
CREATE VIEW legacy_relations AS
SELECT
  r.source_claim_id        AS source_id,
  r.target_claim_id        AS target_id,
  r.type                   AS kind,
  r.strength               AS weight,
  r.rationale              AS rationale,
  r.source_id             AS source_id
FROM relations r;

DROP VIEW IF EXISTS legacy_entities_people;
CREATE VIEW legacy_entities_people AS
SELECT
  mention_id               AS entity_id,
  source_id,
  normalized               AS name,
  'person'                 AS category,
  COALESCE(external_ids_json, '{}') AS data_json
FROM people;

DROP VIEW IF EXISTS legacy_entities_concepts;
CREATE VIEW legacy_entities_concepts AS
SELECT
  model_id                 AS entity_id,
  source_id,
  name                     AS name,
  'concept'                AS category,
  COALESCE(evidence_json, '[]') AS data_json
FROM concepts;

DROP VIEW IF EXISTS legacy_entities_jargon;
CREATE VIEW legacy_entities_jargon AS
SELECT
  term_id                  AS entity_id,
  source_id,
  term                     AS name,
  'jargon'                 AS category,
  COALESCE(evidence_json, '[]') AS data_json
FROM jargon;

-- Optional aliases for FTS
DROP VIEW IF EXISTS legacy_claims_fts;
CREATE VIEW legacy_claims_fts AS SELECT * FROM claims_fts;

DROP VIEW IF EXISTS legacy_quotes_fts;
CREATE VIEW legacy_quotes_fts AS SELECT * FROM quotes_fts;
