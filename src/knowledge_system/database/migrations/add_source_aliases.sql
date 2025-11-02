-- Add source_id aliases table for multi-source deduplication
-- Version: 3.1
-- Date: 2025-11-01
-- Purpose: Link YouTube and podcast source_ids for the same content

PRAGMA foreign_keys=ON;

-- Source ID aliases: Link different source_ids that refer to the same content
-- Example: YouTube video "dQw4w9WgXcQ" = Podcast episode "podcast_abc12345_def67890"
CREATE TABLE IF NOT EXISTS source_id_aliases (
    alias_id TEXT PRIMARY KEY,
    primary_source_id TEXT NOT NULL,
    alias_source_id TEXT NOT NULL,
    alias_type TEXT NOT NULL CHECK (alias_type IN ('youtube_to_podcast', 'podcast_to_youtube', 'manual')),

    -- Matching metadata (how we determined they're the same)
    match_confidence REAL CHECK (match_confidence BETWEEN 0 AND 1),
    match_method TEXT CHECK (match_method IN ('title_fuzzy', 'title_exact', 'date_proximity', 'manual', 'guid')),
    match_metadata TEXT,  -- JSON with title similarity, date diff, etc.

    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    verified_by TEXT,  -- 'system' or user ID

    -- Foreign keys
    FOREIGN KEY (primary_source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (alias_source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE,

    -- Ensure no duplicate aliases
    UNIQUE(primary_source_id, alias_source_id)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_source_aliases_primary ON source_id_aliases(primary_source_id);
CREATE INDEX IF NOT EXISTS idx_source_aliases_alias ON source_id_aliases(alias_source_id);
CREATE INDEX IF NOT EXISTS idx_source_aliases_type ON source_id_aliases(alias_type);

-- View for bidirectional alias lookups
CREATE VIEW IF NOT EXISTS source_id_all_aliases AS
SELECT
    primary_source_id AS source_id,
    alias_source_id AS related_source_id,
    alias_type,
    match_confidence,
    match_method,
    created_at
FROM source_id_aliases
UNION ALL
SELECT
    alias_source_id AS source_id,
    primary_source_id AS related_source_id,
    CASE
        WHEN alias_type = 'youtube_to_podcast' THEN 'podcast_to_youtube'
        WHEN alias_type = 'podcast_to_youtube' THEN 'youtube_to_podcast'
        ELSE alias_type
    END AS alias_type,
    match_confidence,
    match_method,
    created_at
FROM source_id_aliases;
