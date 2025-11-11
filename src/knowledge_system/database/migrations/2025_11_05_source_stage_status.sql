-- Migration: Add source_stage_statuses table for queue visibility
-- Date: 2025-11-05
-- Purpose: Track pipeline stage status for each source in a unified view

CREATE TABLE IF NOT EXISTS source_stage_statuses (
    source_id VARCHAR(50) NOT NULL,
    stage VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    progress_percent REAL DEFAULT 0.0,
    assigned_worker VARCHAR(100),
    metadata_json TEXT,

    -- Composite primary key
    PRIMARY KEY (source_id, stage),

    -- Foreign key to media_sources
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id) ON DELETE CASCADE,

    -- Check constraints
    CONSTRAINT ck_stage_type CHECK (stage IN ('download', 'transcription', 'summarization', 'hce_mining', 'flagship_evaluation')),
    CONSTRAINT ck_status_type CHECK (status IN ('pending', 'queued', 'scheduled', 'in_progress', 'completed', 'failed', 'blocked', 'not_applicable', 'skipped')),
    CONSTRAINT ck_priority_range CHECK (priority BETWEEN 1 AND 10),
    CONSTRAINT ck_progress_range CHECK (progress_percent BETWEEN 0 AND 100)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_stage_status ON source_stage_statuses(stage, status);
CREATE INDEX IF NOT EXISTS idx_source_stage ON source_stage_statuses(source_id, stage);

-- Add trigger to update last_updated on row changes (SQLite compatible)
CREATE TRIGGER IF NOT EXISTS update_source_stage_status_timestamp
    AFTER UPDATE ON source_stage_statuses
BEGIN
    UPDATE source_stage_statuses
    SET last_updated = CURRENT_TIMESTAMP
    WHERE source_id = NEW.source_id AND stage = NEW.stage;
END;
