-- Add YouTube AI Summary field to media_sources table
-- Date: 2025-12-21
-- Purpose: Store YouTube's AI-generated summaries alongside local LLM summaries

-- Add new column for YouTube AI summary
ALTER TABLE media_sources ADD COLUMN youtube_ai_summary TEXT;

-- Add metadata about when/how it was fetched
ALTER TABLE media_sources ADD COLUMN youtube_ai_summary_fetched_at DATETIME;
ALTER TABLE media_sources ADD COLUMN youtube_ai_summary_method TEXT; -- 'playwright_scraper' or 'api'

-- Create index for queries
CREATE INDEX IF NOT EXISTS idx_media_sources_has_yt_ai_summary 
ON media_sources(source_id) WHERE youtube_ai_summary IS NOT NULL;

