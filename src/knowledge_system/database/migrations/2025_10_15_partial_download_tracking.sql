-- Migration: Add partial download tracking to media_sources table
-- Date: 2025-10-15
-- Purpose: Track audio vs metadata download status separately for smart retries and cleanup

-- Add audio file tracking
ALTER TABLE media_sources ADD COLUMN audio_file_path TEXT DEFAULT NULL;
ALTER TABLE media_sources ADD COLUMN audio_downloaded BOOLEAN DEFAULT 0;
ALTER TABLE media_sources ADD COLUMN audio_file_size_bytes INTEGER DEFAULT NULL;
ALTER TABLE media_sources ADD COLUMN audio_format TEXT DEFAULT NULL;

-- Add metadata completion tracking
ALTER TABLE media_sources ADD COLUMN metadata_complete BOOLEAN DEFAULT 0;

-- Add retry tracking
ALTER TABLE media_sources ADD COLUMN needs_metadata_retry BOOLEAN DEFAULT 0;
ALTER TABLE media_sources ADD COLUMN needs_audio_retry BOOLEAN DEFAULT 0;
ALTER TABLE media_sources ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE media_sources ADD COLUMN last_retry_at TEXT DEFAULT NULL;  -- ISO format datetime

-- Add failure tracking
ALTER TABLE media_sources ADD COLUMN max_retries_exceeded BOOLEAN DEFAULT 0;
ALTER TABLE media_sources ADD COLUMN failure_reason TEXT DEFAULT NULL;

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_media_sources_audio_downloaded ON media_sources(audio_downloaded);
CREATE INDEX IF NOT EXISTS idx_media_sources_metadata_complete ON media_sources(metadata_complete);
CREATE INDEX IF NOT EXISTS idx_media_sources_needs_retry ON media_sources(needs_metadata_retry, needs_audio_retry);
CREATE INDEX IF NOT EXISTS idx_media_sources_retry_count ON media_sources(retry_count);

-- Create view for incomplete downloads (need retry)
CREATE VIEW IF NOT EXISTS incomplete_downloads AS
SELECT
    media_id,
    title,
    url,
    audio_downloaded,
    metadata_complete,
    needs_metadata_retry,
    needs_audio_retry,
    retry_count,
    last_retry_at,
    max_retries_exceeded,
    failure_reason,
    processed_at
FROM media_sources
WHERE (audio_downloaded = 0 OR metadata_complete = 0)
  AND max_retries_exceeded = 0
ORDER BY processed_at DESC;

-- Create view for orphaned files (audio downloaded but not in use)
CREATE VIEW IF NOT EXISTS orphaned_audio_files AS
SELECT
    media_id,
    title,
    url,
    audio_file_path,
    audio_downloaded,
    processed_at
FROM media_sources
WHERE audio_downloaded = 1
  AND audio_file_path IS NOT NULL
  AND media_id NOT IN (
      SELECT DISTINCT video_id FROM transcripts WHERE video_id IS NOT NULL
  )
ORDER BY processed_at DESC;

-- Create view for failed downloads (exceeded retry limit)
CREATE VIEW IF NOT EXISTS failed_downloads AS
SELECT
    media_id,
    title,
    url,
    audio_downloaded,
    metadata_complete,
    retry_count,
    last_retry_at,
    failure_reason,
    processed_at
FROM media_sources
WHERE max_retries_exceeded = 1
ORDER BY last_retry_at DESC;

