-- Add user_notes field to claims table
-- Version: 1.0
-- Date: 2025-11-16
-- Purpose: Allow users to add freeform notes to claims

PRAGMA foreign_keys=ON;

-- Add user_notes field for general user annotations
ALTER TABLE claims ADD COLUMN user_notes TEXT;

-- Create index for searching notes
CREATE INDEX IF NOT EXISTS idx_claims_user_notes ON claims(user_notes)
    WHERE user_notes IS NOT NULL;
