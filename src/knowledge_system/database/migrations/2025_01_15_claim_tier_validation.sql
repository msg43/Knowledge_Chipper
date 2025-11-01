-- Migration: Add claim tier validation table
-- Date: 2025-01-15
-- Purpose: Support user validation of HCE claim tier assignments

-- Create claim tier validation table
CREATE TABLE IF NOT EXISTS claim_tier_validations (
    validation_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    source_id TEXT,
    original_tier TEXT NOT NULL CHECK (original_tier IN ('A', 'B', 'C')),
    validated_tier TEXT NOT NULL CHECK (validated_tier IN ('A', 'B', 'C')),
    is_modified BOOLEAN DEFAULT FALSE,
    claim_text TEXT NOT NULL,
    claim_type TEXT,
    validated_by_user TEXT,
    validated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    original_scores TEXT, -- JSON
    model_used TEXT,
    evidence_spans TEXT, -- JSON
    validation_session_id TEXT
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_claim_validations_claim_id ON claim_tier_validations(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_validations_episode_id ON claim_tier_validations(source_id);
CREATE INDEX IF NOT EXISTS idx_claim_validations_session_id ON claim_tier_validations(validation_session_id);
CREATE INDEX IF NOT EXISTS idx_claim_validations_tiers ON claim_tier_validations(original_tier, validated_tier);
CREATE INDEX IF NOT EXISTS idx_claim_validations_modified ON claim_tier_validations(is_modified);
CREATE INDEX IF NOT EXISTS idx_claim_validations_date ON claim_tier_validations(validated_at);

-- Create view for validation analytics
CREATE VIEW IF NOT EXISTS claim_validation_analytics AS
SELECT
    COUNT(*) as total_validations,
    SUM(CASE WHEN is_modified THEN 1 ELSE 0 END) as modified_count,
    SUM(CASE WHEN is_modified THEN 0 ELSE 1 END) as confirmed_count,
    ROUND(100.0 * SUM(CASE WHEN is_modified THEN 0 ELSE 1 END) / COUNT(*), 2) as accuracy_rate,

    -- Tier-specific accuracy
    SUM(CASE WHEN original_tier = 'A' AND NOT is_modified THEN 1 ELSE 0 END) as tier_a_correct,
    SUM(CASE WHEN original_tier = 'A' THEN 1 ELSE 0 END) as tier_a_total,

    SUM(CASE WHEN original_tier = 'B' AND NOT is_modified THEN 1 ELSE 0 END) as tier_b_correct,
    SUM(CASE WHEN original_tier = 'B' THEN 1 ELSE 0 END) as tier_b_total,

    SUM(CASE WHEN original_tier = 'C' AND NOT is_modified THEN 1 ELSE 0 END) as tier_c_correct,
    SUM(CASE WHEN original_tier = 'C' THEN 1 ELSE 0 END) as tier_c_total,

    -- Common corrections
    SUM(CASE WHEN original_tier = 'A' AND validated_tier = 'B' THEN 1 ELSE 0 END) as a_to_b_corrections,
    SUM(CASE WHEN original_tier = 'A' AND validated_tier = 'C' THEN 1 ELSE 0 END) as a_to_c_corrections,
    SUM(CASE WHEN original_tier = 'B' AND validated_tier = 'A' THEN 1 ELSE 0 END) as b_to_a_corrections,
    SUM(CASE WHEN original_tier = 'B' AND validated_tier = 'C' THEN 1 ELSE 0 END) as b_to_c_corrections,
    SUM(CASE WHEN original_tier = 'C' AND validated_tier = 'A' THEN 1 ELSE 0 END) as c_to_a_corrections,
    SUM(CASE WHEN original_tier = 'C' AND validated_tier = 'B' THEN 1 ELSE 0 END) as c_to_b_corrections,

    model_used,
    DATE(validated_at) as validation_date
FROM claim_tier_validations
GROUP BY model_used, DATE(validated_at);
