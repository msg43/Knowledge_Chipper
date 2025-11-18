-- Fix verification_status to include 'unverifiable'
-- Version: 1.0
-- Date: 2025-11-16
-- Purpose: Add 'unverifiable' status for claims that cannot be verified

PRAGMA foreign_keys=ON;

-- SQLite doesn't support ALTER COLUMN, so we need to:
-- 1. Create new table with correct constraint
-- 2. Copy data
-- 3. Drop old table
-- 4. Rename new table

-- Create new claims table with updated constraint
CREATE TABLE IF NOT EXISTS claims_new (
    claim_id TEXT PRIMARY KEY,

    -- Attribution (optional - some claims might be synthetic)
    source_id TEXT,

    -- Content
    canonical TEXT NOT NULL,
    original_text TEXT,
    claim_type TEXT CHECK (claim_type IN ('factual', 'causal', 'normative', 'forecast', 'definition')),
    domain TEXT,

    -- System evaluation (from HCE)
    tier TEXT CHECK (tier IN ('A', 'B', 'C')),
    importance_score REAL CHECK (importance_score BETWEEN 0 AND 1),
    specificity_score REAL CHECK (specificity_score BETWEEN 0 AND 1),
    verifiability_score REAL CHECK (verifiability_score BETWEEN 0 AND 1),

    -- User curation
    user_tier_override TEXT CHECK (user_tier_override IN ('A', 'B', 'C')),
    user_confidence_override REAL CHECK (user_confidence_override BETWEEN 0 AND 1),
    evaluator_notes TEXT,

    -- Verification workflow (UPDATED: added 'unverifiable')
    verification_status TEXT CHECK (verification_status IN ('unverified', 'verified', 'disputed', 'false', 'unverifiable')) DEFAULT 'unverified',
    verification_source TEXT,
    verification_notes TEXT,

    -- Review workflow
    flagged_for_review BOOLEAN DEFAULT 0,
    reviewed_by TEXT,
    reviewed_at DATETIME,

    -- Temporality analysis
    temporality_score INTEGER CHECK (temporality_score IN (1, 2, 3, 4, 5)) DEFAULT 3,
    temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1) DEFAULT 0.5,
    temporality_rationale TEXT,
    first_mention_ts TEXT,

    -- Export tracking
    upload_status TEXT DEFAULT 'pending',
    upload_timestamp DATETIME,
    upload_error TEXT,

    -- User notes (NEW)
    user_notes TEXT,

    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE SET NULL
);

-- Copy data from old table (only if it exists)
INSERT INTO claims_new
SELECT
    claim_id,
    source_id,
    canonical,
    original_text,
    claim_type,
    domain,
    tier,
    importance_score,
    specificity_score,
    verifiability_score,
    user_tier_override,
    user_confidence_override,
    evaluator_notes,
    verification_status,
    verification_source,
    verification_notes,
    flagged_for_review,
    reviewed_by,
    reviewed_at,
    temporality_score,
    temporality_confidence,
    temporality_rationale,
    first_mention_ts,
    upload_status,
    upload_timestamp,
    upload_error,
    NULL,  -- user_notes (new field)
    created_at,
    updated_at
FROM claims
WHERE EXISTS (SELECT 1 FROM sqlite_master WHERE type='table' AND name='claims');

-- Drop old table
DROP TABLE IF EXISTS claims;

-- Rename new table
ALTER TABLE claims_new RENAME TO claims;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_claims_source ON claims(source_id);
CREATE INDEX IF NOT EXISTS idx_claims_tier ON claims(tier);
CREATE INDEX IF NOT EXISTS idx_claims_type ON claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_claims_domain ON claims(domain);
CREATE INDEX IF NOT EXISTS idx_claims_verification ON claims(verification_status);
CREATE INDEX IF NOT EXISTS idx_claims_flagged ON claims(flagged_for_review) WHERE flagged_for_review = 1;
CREATE INDEX IF NOT EXISTS idx_claims_created ON claims(created_at);
CREATE INDEX IF NOT EXISTS idx_claims_user_notes ON claims(user_notes) WHERE user_notes IS NOT NULL;
