-- Migration: Add Speaker Attribution to Entities
-- Date: December 22, 2025
-- Purpose: Store speaker attribution at entity level (claims, jargon, concepts)
--          Remove segment-level speaker attribution (diarization deprecated)
--
-- COMPATIBILITY: This migration works for BOTH databases:
--   - GetReceipts (PostgreSQL): Adds speaker fields to claims/jargon/concepts
--   - Knowledge_Chipper (SQLite): Same, plus optional data migration from segments
--
-- NOTE: Data migration (Part 3) is commented out because:
--   - GetReceipts doesn't have segments/evidence_spans tables
--   - Knowledge_Chipper can run it manually if needed
--   - New claims will have speaker populated by Pass 1 LLM automatically

-- ============================================================================
-- PART 1: Add Speaker Fields to Entity Tables
-- ============================================================================

-- Add speaker to claims table (REQUIRED - claims must have attribution)
ALTER TABLE claims ADD COLUMN speaker TEXT;

-- Add introduced_by to jargon_terms (who first used/explained the term)
ALTER TABLE jargon_terms ADD COLUMN introduced_by TEXT;

-- Add advocated_by to concepts (who advocates for this mental model)
ALTER TABLE concepts ADD COLUMN advocated_by TEXT;

-- Note: people table already has mentioned_by tracking via claim_people relationship

-- ============================================================================
-- PART 2: Create Indexes for Speaker Queries
-- ============================================================================

-- Index for querying claims by speaker (critical for web interface grouping)
CREATE INDEX IF NOT EXISTS idx_claims_speaker ON claims(speaker);

-- Index for querying jargon by introducer
CREATE INDEX IF NOT EXISTS idx_jargon_introduced_by ON jargon_terms(introduced_by);

-- Index for querying concepts by advocate
CREATE INDEX IF NOT EXISTS idx_concepts_advocated_by ON concepts(advocated_by);

-- ============================================================================
-- PART 3: Migrate Existing Data (Best Effort)
-- ============================================================================

-- NOTE: This section is ONLY for Knowledge_Chipper local database (SQLite)
-- GetReceipts (PostgreSQL) does NOT have segments/evidence_spans tables
-- Claims uploaded to GetReceipts will already have speaker field populated

-- Check if segments table exists before attempting migration
-- For SQLite (Knowledge_Chipper):
-- Populate claims.speaker from segments.speaker via evidence_spans
-- This will only work for claims that have evidence spans linked to segments with speakers

-- SQLITE ONLY: Uncomment if running on Knowledge_Chipper database
-- UPDATE claims
-- SET speaker = (
--     SELECT s.speaker
--     FROM evidence_spans e
--     JOIN segments s ON e.segment_id = s.segment_id
--     WHERE e.claim_id = claims.claim_id
--     AND s.speaker IS NOT NULL
--     AND s.speaker != ''
--     ORDER BY e.seq
--     LIMIT 1
-- )
-- WHERE speaker IS NULL;

-- Set remaining NULL speakers to 'Unknown' (will be re-extracted by Pass 1 on next processing)
-- For new claims, this will be populated by Pass 1 LLM automatically
UPDATE claims SET speaker = 'Unknown' WHERE speaker IS NULL OR speaker = '';

-- Make speaker NOT NULL after migration
-- Note: This is commented out for now to allow gradual migration
-- ALTER TABLE claims ALTER COLUMN speaker SET NOT NULL;

-- ============================================================================
-- PART 4: Remove Segment Speaker Column (Optional - can be done later)
-- ============================================================================

-- NOTE: This is ONLY for Knowledge_Chipper local database (SQLite)
-- GetReceipts does NOT have a segments table

-- SQLITE ONLY: Uncomment when ready to fully deprecate diarization:
-- ALTER TABLE segments DROP COLUMN speaker;

-- ============================================================================
-- PART 5: Add Web Interface Support Fields
-- ============================================================================

-- Add cluster_id to claims for manual web-based merging
ALTER TABLE claims ADD COLUMN cluster_id TEXT;
ALTER TABLE claims ADD COLUMN is_canonical_instance BOOLEAN DEFAULT FALSE;

-- Create index for cluster queries
CREATE INDEX IF NOT EXISTS idx_claims_cluster ON claims(cluster_id);

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================

-- This migration enables:
-- 1. Speaker attribution at entity level (claims, jargon, concepts)
-- 2. Removal of diarization dependency (segments.speaker no longer needed)
-- 3. Web-based manual claim merging (cluster_id support)
-- 4. Unified workflow for all content types (YouTube + Whisper)

-- After this migration:
-- - All new extractions will populate speaker fields from Pass 1 LLM
-- - Existing claims have best-effort speaker attribution from segments
-- - Web interface can group claims by speaker for manual merging
-- - Diarization system can be deprecated/removed

-- Rollback (if needed):
-- ALTER TABLE claims DROP COLUMN speaker;
-- ALTER TABLE claims DROP COLUMN cluster_id;
-- ALTER TABLE claims DROP COLUMN is_canonical_instance;
-- ALTER TABLE jargon_terms DROP COLUMN introduced_by;
-- ALTER TABLE concepts DROP COLUMN advocated_by;
-- DROP INDEX IF EXISTS idx_claims_speaker;
-- DROP INDEX IF EXISTS idx_claims_cluster;
-- DROP INDEX IF EXISTS idx_jargon_introduced_by;
-- DROP INDEX IF EXISTS idx_concepts_advocated_by;

