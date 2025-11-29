-- Migration: Add scores_json column to claims table (canonical format)
-- Date: 2025-11-27
-- Purpose: Add scores_json column matching HCE schema and GetReceipts API
--          This is the canonical format - no mapping needed

-- Add scores_json column if it doesn't exist
-- Note: SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN
-- So we'll check programmatically or use a try/catch pattern

-- For existing claims, populate scores_json from individual columns
-- This migration assumes scores_json column will be added by SQLAlchemy
-- We just need to backfill data for existing claims

-- Backfill scores_json from individual columns (if scores_json is NULL)
UPDATE claims 
SET scores_json = json_object(
    'importance', COALESCE(importance_score, 0.5),
    'specificity', COALESCE(specificity_score, 0.5),
    'verifiability', COALESCE(verifiability_score, 0.5)
)
WHERE scores_json IS NULL AND (importance_score IS NOT NULL OR specificity_score IS NOT NULL OR verifiability_score IS NOT NULL);

-- Note: After this migration, scores_json is the canonical format
-- Individual columns are kept for backward compatibility and querying
-- But scores_json is what gets sent to GetReceipts API (no mapping needed)

