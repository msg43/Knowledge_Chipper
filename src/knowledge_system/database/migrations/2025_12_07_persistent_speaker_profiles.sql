-- Migration: Add persistent speaker profiles table
-- Date: 2025-12-07
-- Purpose: Store speaker voice profiles across episodes for instant recognition
--          Enables 97%+ accuracy for recurring podcast hosts by accumulating
--          voice fingerprints from multiple episodes.

-- Create speaker_profiles table for persistent voice fingerprints
CREATE TABLE IF NOT EXISTS speaker_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Speaker identification
    name TEXT NOT NULL,                          -- Speaker's name (e.g., "Lex Fridman")
    channel_id TEXT,                             -- YouTube channel ID for channel-specific lookup
    channel_name TEXT,                           -- Human-readable channel name
    
    -- Voice fingerprint data (JSON blob containing averaged embeddings)
    -- Contains: mfcc, spectral, prosodic, wav2vec2, ecapa features
    fingerprint_embedding TEXT,                  -- JSON: averaged voice embedding
    
    -- Profile quality metrics
    sample_count INTEGER DEFAULT 0,              -- Number of episodes contributing to profile
    total_duration_seconds REAL DEFAULT 0.0,     -- Total audio duration used for profile
    confidence_score REAL DEFAULT 0.0,           -- Overall profile reliability (0.0-1.0)
    
    -- Feature availability tracking (not all episodes have all features)
    has_wav2vec2 INTEGER DEFAULT 0,              -- 1 if wav2vec2 embeddings available
    has_ecapa INTEGER DEFAULT 0,                 -- 1 if ECAPA-TDNN embeddings available
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,                      -- Last time profile was matched
    
    -- Source tracking
    source_episodes TEXT                         -- JSON: list of source_ids that contributed
);

-- Index for fast channel-based lookups (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_speaker_profiles_channel 
ON speaker_profiles(channel_id, name);

-- Index for name-based lookups across all channels
CREATE INDEX IF NOT EXISTS idx_speaker_profiles_name 
ON speaker_profiles(name);

-- Index for finding high-confidence profiles
CREATE INDEX IF NOT EXISTS idx_speaker_profiles_confidence 
ON speaker_profiles(confidence_score DESC);

-- Unique constraint: one profile per speaker per channel
-- (same speaker can have different profiles on different channels due to audio quality)
CREATE UNIQUE INDEX IF NOT EXISTS idx_speaker_profiles_unique 
ON speaker_profiles(channel_id, name) WHERE channel_id IS NOT NULL;

-- For speakers without channel association, allow one global profile per name
CREATE UNIQUE INDEX IF NOT EXISTS idx_speaker_profiles_global_unique 
ON speaker_profiles(name) WHERE channel_id IS NULL;
