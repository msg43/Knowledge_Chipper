-- Migration: Add subtitle column to media_sources table
-- Date: 2025-11-02
-- Purpose: Fix schema mismatch after ID unification

-- Add subtitle column if it doesn't exist
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN,
-- so we'll check if it exists first in the application code

ALTER TABLE media_sources ADD COLUMN subtitle TEXT;

