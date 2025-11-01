-- Migration: Add upload tracking to claims table
-- Date: 2025-08-31
-- Purpose: Track upload status for Cloud Uploads functionality

-- Add upload tracking columns to claims table
ALTER TABLE claims ADD COLUMN last_uploaded_at TEXT DEFAULT NULL;
ALTER TABLE claims ADD COLUMN upload_status TEXT DEFAULT 'pending' CHECK (upload_status IN ('pending', 'uploaded', 'failed'));

-- Create index for efficient querying of upload status
CREATE INDEX IF NOT EXISTS idx_claims_upload_status ON claims(upload_status);
CREATE INDEX IF NOT EXISTS idx_claims_last_uploaded ON claims(last_uploaded_at);

-- Create view for unuploaded claims
CREATE VIEW IF NOT EXISTS unuploaded_claims AS
SELECT
    c.*,
    e.title as episode_title,
    e.source_id
FROM claims c
LEFT JOIN episodes e ON c.source_id = e.source_id
WHERE c.upload_status = 'pending' OR c.last_uploaded_at IS NULL
ORDER BY c.inserted_at DESC;
