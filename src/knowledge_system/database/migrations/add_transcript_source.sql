-- Migration: Add transcript_source field to transcripts table
-- Date: 2025-12-25
-- Purpose: Track the source of transcripts (youtube_api, whisper_fallback, whisper_forced)

-- Add transcript_source column to track where transcript came from
-- Note: Will error if column already exists, but error is caught by migration framework
ALTER TABLE transcripts ADD COLUMN transcript_source VARCHAR(50);

-- Set default value for existing records (only runs if column was just added)
UPDATE transcripts 
SET transcript_source = 'unknown' 
WHERE transcript_source IS NULL OR transcript_source = '';

-- Note: Comment explaining the field (SQLite doesn't support COMMENT ON COLUMN)
-- transcript_source values:
--   - 'youtube_api': from YouTube API
--   - 'whisper_fallback': Whisper after YouTube API failed
--   - 'whisper_forced': user forced Whisper
--   - 'unknown': legacy data

