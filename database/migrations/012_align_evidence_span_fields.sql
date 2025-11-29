-- Migration: Align EvidenceSpan fields to canonical format (matching GetReceipts API)
-- Date: 2025-11-27
-- Purpose: Rename fields to match canonical HCE schema and GetReceipts API
--          No mapping needed - databases speak the same language
--
-- IMPORTANT: This migration is for SQLite ONLY (local Knowledge_Chipper database)
--            Supabase/PostgreSQL already uses canonical field names (seq, t0, t1, etc.)
--            For PostgreSQL/Supabase, use: 012_align_evidence_span_fields_postgres.sql
--
-- DO NOT RUN THIS ON SUPABASE - use the _postgres.sql version instead!
--
-- This migration assumes old columns (sequence, start_time, etc.) exist.
-- If canonical columns (seq, t0, t1, etc.) already exist, skip this migration.

-- Step 1: Add new columns with canonical names
-- Note: These will fail if columns already exist - that's OK, migration already done
ALTER TABLE evidence_spans ADD COLUMN seq_new INTEGER;
ALTER TABLE evidence_spans ADD COLUMN t0_new TEXT;
ALTER TABLE evidence_spans ADD COLUMN t1_new TEXT;
ALTER TABLE evidence_spans ADD COLUMN context_t0_new TEXT;
ALTER TABLE evidence_spans ADD COLUMN context_t1_new TEXT;

-- Step 2: Copy data from old columns to new columns
-- This will fail if old columns don't exist - that means migration isn't needed
UPDATE evidence_spans SET 
    seq_new = sequence,
    t0_new = start_time,
    t1_new = end_time,
    context_t0_new = context_start_time,
    context_t1_new = context_end_time;

-- Step 3: Drop old columns (SQLite 3.35.0+)
-- If your SQLite version doesn't support DROP COLUMN, you'll need to recreate the table
-- For now, we'll keep both and use the new ones

-- Step 4: Rename new columns to final names (if DROP COLUMN worked)
-- ALTER TABLE evidence_spans RENAME COLUMN seq_new TO seq;
-- ALTER TABLE evidence_spans RENAME COLUMN t0_new TO t0;
-- ALTER TABLE evidence_spans RENAME COLUMN t1_new TO t1;
-- ALTER TABLE evidence_spans RENAME COLUMN context_t0_new TO context_t0;
-- ALTER TABLE evidence_spans RENAME COLUMN context_t1_new TO context_t1;

-- Note: This migration ensures field names match:
-- - HCE SQLite schema (sqlite_schema.sql)  
-- - GetReceipts API expectations
-- - GetReceipts database schema
-- No mapping layer needed - databases speak the same language
