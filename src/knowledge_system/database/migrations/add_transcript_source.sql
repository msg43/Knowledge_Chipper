-- Migration: Add transcript_source field to transcripts table
-- Date: 2025-12-25
-- Purpose: Track the source of transcripts (youtube_api, whisper_fallback, whisper_forced)

-- Add transcript_source column to track where transcript came from
ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS transcript_source VARCHAR(50);

-- Set default value for existing records
UPDATE transcripts 
SET transcript_source = 'unknown' 
WHERE transcript_source IS NULL;

-- Add comment explaining the field
COMMENT ON COLUMN transcripts.transcript_source IS 
'Source of the transcript: youtube_api (from YouTube API), whisper_fallback (Whisper after YouTube API failed), whisper_forced (user forced Whisper), unknown (legacy data)';

