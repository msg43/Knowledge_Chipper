-- Migration: Align EvidenceSpan fields to canonical format (PostgreSQL/Supabase version)
-- Date: 2025-11-27
-- Purpose: Check if migration is needed and only run if old columns exist
--
-- IMPORTANT: Supabase already uses canonical field names (seq, t0, t1, etc.)
--            This migration should only run if old columns (sequence, start_time, etc.) exist
--            In most cases, this migration will do nothing because columns are already canonical

DO $$
BEGIN
    -- Check if old columns exist
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'evidence_spans' 
        AND column_name = 'sequence'
    ) THEN
        -- Old columns exist - perform migration
        RAISE NOTICE 'Old columns found - performing migration...';
        
        -- Add new columns if they don't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'evidence_spans' 
            AND column_name = 'seq'
        ) THEN
            ALTER TABLE evidence_spans ADD COLUMN seq INTEGER;
            ALTER TABLE evidence_spans ADD COLUMN t0 TEXT;
            ALTER TABLE evidence_spans ADD COLUMN t1 TEXT;
            ALTER TABLE evidence_spans ADD COLUMN context_t0 TEXT;
            ALTER TABLE evidence_spans ADD COLUMN context_t1 TEXT;
        END IF;
        
        -- Copy data from old columns
        UPDATE evidence_spans SET 
            seq = sequence,
            t0 = start_time,
            t1 = end_time,
            context_t0 = context_start_time,
            context_t1 = context_end_time
        WHERE sequence IS NOT NULL;
        
        -- Drop old columns
        ALTER TABLE evidence_spans DROP COLUMN IF EXISTS sequence;
        ALTER TABLE evidence_spans DROP COLUMN IF EXISTS start_time;
        ALTER TABLE evidence_spans DROP COLUMN IF EXISTS end_time;
        ALTER TABLE evidence_spans DROP COLUMN IF EXISTS context_start_time;
        ALTER TABLE evidence_spans DROP COLUMN IF EXISTS context_end_time;
        
        RAISE NOTICE 'Migration completed successfully';
    ELSE
        -- Old columns don't exist - canonical columns already in place
        RAISE NOTICE 'Canonical columns already exist - migration not needed';
    END IF;
END $$;

