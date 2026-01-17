-- Migration: Feedback System Tables
-- Date: 2026-01-17
-- Description: Creates tables for async feedback processing

-- Audit trail table for all feedback synced from web
-- This is separate from ChromaDB which stores the vector embeddings
CREATE TABLE IF NOT EXISTS feedback_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,  -- claim, person, jargon, concept
    entity_text TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('accept', 'reject')),
    reason_category TEXT NOT NULL,
    user_notes TEXT DEFAULT '',
    source_id TEXT DEFAULT '',  -- Episode/source reference
    web_feedback_id TEXT UNIQUE,  -- ID from GetReceipts.org
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,  -- When added to ChromaDB
    is_processed BOOLEAN DEFAULT 0
);

-- Index for finding unprocessed feedback
CREATE INDEX IF NOT EXISTS idx_feedback_unprocessed 
ON feedback_examples(is_processed) WHERE is_processed = 0;

-- Index for querying by entity type
CREATE INDEX IF NOT EXISTS idx_feedback_entity_type 
ON feedback_examples(entity_type);

-- Pending feedback queue for async processing
-- Raw JSON from web is stored here until processed
CREATE TABLE IF NOT EXISTS pending_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_json TEXT NOT NULL,  -- Full JSON payload from web
    source TEXT DEFAULT 'web',  -- web, api, import
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

-- Index for finding unprocessed items
CREATE INDEX IF NOT EXISTS idx_pending_unprocessed 
ON pending_feedback(processed_at) WHERE processed_at IS NULL;

-- Feedback sync metadata
CREATE TABLE IF NOT EXISTS feedback_sync_metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Single row table
    last_sync_at TIMESTAMP,
    last_sync_count INTEGER DEFAULT 0,
    total_synced INTEGER DEFAULT 0,
    last_error TEXT
);

-- Initialize sync metadata
INSERT OR IGNORE INTO feedback_sync_metadata (id, total_synced) VALUES (1, 0);
