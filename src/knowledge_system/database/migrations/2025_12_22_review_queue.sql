-- Migration: Add review_queue_items table for persistent review workflow
-- Date: December 22, 2025
-- Purpose: Store pending review items across sessions until user confirms sync to GetReceipts

-- Review Queue Items table
-- Stores all extracted items (claims, jargon, people, concepts) pending user review
CREATE TABLE IF NOT EXISTS review_queue_items (
    -- Primary key
    item_id TEXT PRIMARY KEY,
    
    -- Entity type: 'claim', 'jargon', 'person', 'concept'
    entity_type TEXT NOT NULL CHECK (entity_type IN ('claim', 'jargon', 'person', 'concept')),
    
    -- Review status: 'pending', 'accepted', 'rejected'
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'accepted', 'rejected')),
    
    -- Source attribution
    source_id TEXT,
    source_title TEXT,
    
    -- Content (display text)
    content TEXT NOT NULL,
    
    -- Quality scores
    tier TEXT DEFAULT 'C',
    importance REAL DEFAULT 0,
    
    -- Raw data JSON (stores all entity-specific fields)
    raw_data TEXT,
    
    -- Reference to actual entity (if already created in respective table)
    entity_ref_id TEXT,
    
    -- Sync tracking
    synced_at DATETIME,
    sync_error TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    reviewed_at DATETIME,
    
    -- Foreign key to source
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE SET NULL
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue_items(review_status);
CREATE INDEX IF NOT EXISTS idx_review_queue_entity_type ON review_queue_items(entity_type);
CREATE INDEX IF NOT EXISTS idx_review_queue_source ON review_queue_items(source_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_pending ON review_queue_items(review_status) WHERE review_status = 'pending';
CREATE INDEX IF NOT EXISTS idx_review_queue_unsynced ON review_queue_items(review_status, synced_at) WHERE review_status = 'accepted' AND synced_at IS NULL;

