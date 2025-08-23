-- Quality Rating System Migration
-- Created: 2025-01-15
-- Description: Add quality rating tables for LLM output evaluation and user feedback

-- Create quality_ratings table
CREATE TABLE IF NOT EXISTS quality_ratings (
    rating_id VARCHAR(50) PRIMARY KEY,
    content_type VARCHAR(30) NOT NULL,
    content_id VARCHAR(50) NOT NULL,
    llm_rating REAL,
    user_rating REAL,
    is_user_corrected BOOLEAN DEFAULT FALSE,
    criteria_scores TEXT,  -- JSON encoded
    user_feedback TEXT,
    rating_reason TEXT,
    rated_by_user VARCHAR(100),
    rated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    model_used VARCHAR(50),
    prompt_template VARCHAR(200),
    input_characteristics TEXT  -- JSON encoded
);

-- Create quality_metrics table
CREATE TABLE IF NOT EXISTS quality_metrics (
    metric_id VARCHAR(50) PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL,
    content_type VARCHAR(30) NOT NULL,
    total_ratings INTEGER DEFAULT 0,
    user_corrected_count INTEGER DEFAULT 0,
    avg_llm_rating REAL,
    avg_user_rating REAL,
    rating_drift REAL,
    criteria_performance TEXT,  -- JSON encoded
    period_start DATETIME,
    period_end DATETIME,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_quality_ratings_content ON quality_ratings(content_type, content_id);
CREATE INDEX IF NOT EXISTS idx_quality_ratings_model ON quality_ratings(model_used);
CREATE INDEX IF NOT EXISTS idx_quality_ratings_user_corrected ON quality_ratings(is_user_corrected);
CREATE INDEX IF NOT EXISTS idx_quality_ratings_rated_at ON quality_ratings(rated_at);

CREATE INDEX IF NOT EXISTS idx_quality_metrics_model_content ON quality_metrics(model_name, content_type);
CREATE INDEX IF NOT EXISTS idx_quality_metrics_updated ON quality_metrics(last_updated);

-- Add constraints
CREATE UNIQUE INDEX IF NOT EXISTS idx_quality_metrics_unique ON quality_metrics(model_name, content_type, period_start, period_end);
