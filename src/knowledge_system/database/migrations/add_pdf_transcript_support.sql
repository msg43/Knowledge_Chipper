-- Migration: Add PDF Transcript Support
-- Date: 2025-12-25
-- Purpose: Enable multiple transcript versions per source with quality tracking

-- Add new fields to transcripts table for quality tracking
ALTER TABLE transcripts ADD COLUMN quality_score REAL;
ALTER TABLE transcripts ADD COLUMN has_speaker_labels BOOLEAN DEFAULT 0;
ALTER TABLE transcripts ADD COLUMN has_timestamps BOOLEAN DEFAULT 0;
ALTER TABLE transcripts ADD COLUMN source_file_path TEXT;
ALTER TABLE transcripts ADD COLUMN extraction_metadata TEXT; -- JSON

-- Add preferred transcript tracking to media_sources
ALTER TABLE media_sources ADD COLUMN preferred_transcript_id TEXT;

-- Create index for fast transcript lookups by type
CREATE INDEX IF NOT EXISTS idx_transcripts_type ON transcripts(transcript_type);
CREATE INDEX IF NOT EXISTS idx_transcripts_source_type ON transcripts(source_id, transcript_type);

-- Create index for preferred transcript lookups
CREATE INDEX IF NOT EXISTS idx_media_sources_preferred_transcript ON media_sources(preferred_transcript_id);

-- Note: Foreign key constraint for preferred_transcript_id will be added in the model
-- SQLite doesn't support adding foreign keys to existing tables via ALTER TABLE

