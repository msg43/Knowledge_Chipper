-- Migration: Multi-Profile Scoring System
-- Date: 2025-12-22
-- Description: Add dimension-based scoring with 6 dimensions and 12 user profile scores

-- Add dimension and profile columns to claims table
ALTER TABLE claims ADD COLUMN dimensions JSON;
ALTER TABLE claims ADD COLUMN profile_scores JSON;
ALTER TABLE claims ADD COLUMN best_profile TEXT;
ALTER TABLE claims ADD COLUMN temporal_stability REAL;  -- Extracted for filtering (0-10)
ALTER TABLE claims ADD COLUMN scope REAL;               -- Extracted for filtering (0-10)

-- Add tier column if it doesn't exist (for A/B/C/D classification)
-- Note: Some tables may already have this from previous migrations
-- ALTER TABLE claims ADD COLUMN tier TEXT CHECK(tier IN ('A', 'B', 'C', 'D'));

-- Create indexes for filtering and querying
CREATE INDEX IF NOT EXISTS idx_claims_temporal_stability ON claims(temporal_stability);
CREATE INDEX IF NOT EXISTS idx_claims_scope ON claims(scope);
CREATE INDEX IF NOT EXISTS idx_claims_best_profile ON claims(best_profile);
CREATE INDEX IF NOT EXISTS idx_claims_tier ON claims(tier);

-- Add comments to document the new columns
-- dimensions: JSON object with 6 dimension scores
--   Example: {"epistemic_value": 9, "actionability": 6, "novelty": 8, 
--             "verifiability": 8, "understandability": 7, "temporal_stability": 8, "scope": 6}
--
-- profile_scores: JSON object with importance scores for each of 12 user profiles
--   Example: {"scientist": 8.4, "investor": 7.1, "philosopher": 8.2, ...}
--
-- best_profile: Name of the user profile that gave the highest importance score
--   Values: scientist, philosopher, educator, student, skeptic, investor, 
--           policy_maker, tech_professional, health_professional, journalist, 
--           generalist, pragmatist
--
-- temporal_stability: Extracted from dimensions.temporal_stability for easy filtering
--   Scale: 1-2 (ephemeral), 3-4 (short-term), 5-6 (medium-term), 7-8 (long-lasting), 9-10 (timeless)
--
-- scope: Extracted from dimensions.scope for easy filtering
--   Scale: 1-2 (specific edge case), 3-4 (narrow), 5-6 (domain-specific), 7-8 (broad), 9-10 (universal)

-- Note: The 'importance' column now represents the composite importance score
-- calculated as max(profile_scores) using the max-scoring aggregation method.
-- This rescues niche-but-valuable claims that score high for at least one user profile.

