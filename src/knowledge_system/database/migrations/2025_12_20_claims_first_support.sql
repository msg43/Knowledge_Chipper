-- Claims-First Architecture Support Migration
-- Date: December 20, 2025
-- Purpose: Add columns and tables to support claims-first pipeline

-- =============================================================================
-- 1. Add claims-first columns to claims table
-- =============================================================================

-- Track timestamp precision (word-level or segment-level)
-- word: Whisper word timestamps (±0.5 sec)
-- segment: YouTube segment timestamps (±5 sec)
ALTER TABLE claims ADD COLUMN timestamp_precision TEXT DEFAULT 'word';

-- Track which transcript source was used
-- youtube: YouTube auto-generated transcript
-- whisper: Whisper transcription
-- manual: Manually provided transcript
ALTER TABLE claims ADD COLUMN transcript_source TEXT DEFAULT 'whisper';

-- Speaker attribution confidence for lazy attribution
-- NULL if speaker not attributed (C/D tier claims)
-- 0.0-1.0 for attributed claims
ALTER TABLE claims ADD COLUMN speaker_attribution_confidence REAL;

-- =============================================================================
-- 2. Add claims-first columns to media_sources table
-- =============================================================================

-- Track which transcript source was used for this source
ALTER TABLE media_sources ADD COLUMN transcript_source TEXT;

-- YouTube transcript quality score (0.0-1.0)
-- NULL if not YouTube or not assessed
ALTER TABLE media_sources ADD COLUMN transcript_quality_score REAL;

-- Whether this source was processed with claims-first pipeline
ALTER TABLE media_sources ADD COLUMN used_claims_first_pipeline BOOLEAN DEFAULT FALSE;

-- =============================================================================
-- 3. Create candidate_claims table for re-evaluation support
-- =============================================================================

-- Store candidate claims before filtering for later re-evaluation
-- This enables changing scoring methodology without re-extracting
CREATE TABLE IF NOT EXISTS candidate_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL,
    source_id TEXT,
    
    -- Claim content
    claim_text TEXT NOT NULL,
    evidence_quote TEXT,
    
    -- Timestamps
    timestamp_start REAL,
    timestamp_end REAL,
    timestamp_precision TEXT DEFAULT 'segment',
    
    -- Extraction metadata
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    miner_model TEXT,
    chunk_id TEXT,  -- Which chunk this was extracted from
    
    -- Evaluation results (filled in by evaluator)
    accepted BOOLEAN,
    rejection_reason TEXT,
    
    -- Dimension scores (JSON for flexibility)
    dimensions JSON,  -- {"epistemic_value": 8, "actionability": 6, ...}
    
    -- Final scoring
    importance REAL,
    tier TEXT,  -- A, B, C, D
    
    -- Reasoning from evaluator
    reasoning TEXT,
    
    -- Foreign key to accepted claim (if accepted)
    accepted_claim_id INTEGER,
    
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id)
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_candidate_claims_episode ON candidate_claims(episode_id);
CREATE INDEX IF NOT EXISTS idx_candidate_claims_source ON candidate_claims(source_id);
CREATE INDEX IF NOT EXISTS idx_candidate_claims_accepted ON candidate_claims(accepted);
CREATE INDEX IF NOT EXISTS idx_candidate_claims_importance ON candidate_claims(importance);

-- =============================================================================
-- 4. Create claims_first_processing_log table for tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS claims_first_processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    
    -- Processing timestamps
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Transcript info
    transcript_source TEXT,  -- youtube, whisper
    transcript_quality_score REAL,
    transcript_word_count INTEGER,
    
    -- Extraction stats
    candidates_extracted INTEGER,
    candidates_accepted INTEGER,
    acceptance_rate REAL,
    
    -- Attribution stats
    claims_attributed INTEGER,
    attribution_avg_confidence REAL,
    
    -- Timing breakdown (seconds)
    transcript_time REAL,
    extraction_time REAL,
    evaluation_time REAL,
    timestamp_matching_time REAL,
    attribution_time REAL,
    total_time REAL,
    
    -- Model info
    miner_model TEXT,
    evaluator_model TEXT,
    attribution_model TEXT,
    
    -- Configuration used
    config JSON,
    
    -- Error tracking
    errors JSON,
    
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id)
);

CREATE INDEX IF NOT EXISTS idx_claims_first_log_source ON claims_first_processing_log(source_id);
CREATE INDEX IF NOT EXISTS idx_claims_first_log_started ON claims_first_processing_log(started_at);

