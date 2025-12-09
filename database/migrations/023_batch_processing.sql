-- Migration 023: Batch Processing Tables
-- Adds tables for tracking batch API jobs and requests with cache metrics

-- Batch jobs table with cache tracking
CREATE TABLE IF NOT EXISTS batch_jobs (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL CHECK (provider IN ('openai', 'anthropic')),
    model TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN ('mining', 'flagship', 'remine')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'validating', 'in_progress', 'finalizing', 
        'completed', 'failed', 'expired', 'cancelled'
    )),
    batch_api_id TEXT,                    -- Provider's batch ID
    request_count INTEGER NOT NULL,
    completed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    
    -- File IDs (OpenAI)
    input_file_id TEXT,                   -- OpenAI input file ID
    output_file_id TEXT,                  -- OpenAI output file ID
    
    -- Cache metrics
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    cached_tokens INTEGER DEFAULT 0,
    cache_hit_rate REAL DEFAULT 0,
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Cost tracking
    estimated_cost REAL,
    actual_cost REAL,
    cost_savings_from_batch REAL,         -- Savings from 50% batch discount
    cost_savings_from_cache REAL,         -- Savings from prompt caching
    
    -- Metadata and errors
    error_message TEXT,
    metadata JSON
);

-- Batch requests table (individual requests within a batch)
CREATE TABLE IF NOT EXISTS batch_requests (
    id TEXT PRIMARY KEY,
    batch_job_id TEXT NOT NULL REFERENCES batch_jobs(id) ON DELETE CASCADE,
    custom_id TEXT NOT NULL,              -- "source_id:segment_id" or "claim_id"
    source_id TEXT,
    segment_id TEXT,
    
    -- Request/Response payloads
    request_payload JSON NOT NULL,
    response_payload JSON,
    
    -- Status
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
    error_message TEXT,
    
    -- Token usage
    tokens_input INTEGER,
    tokens_output INTEGER,
    tokens_cached INTEGER DEFAULT 0,
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Indexes for batch_jobs
CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_stage ON batch_jobs(stage);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_provider ON batch_jobs(provider);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_created ON batch_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_batch_api_id ON batch_jobs(batch_api_id);

-- Indexes for batch_requests
CREATE INDEX IF NOT EXISTS idx_batch_requests_job ON batch_requests(batch_job_id);
CREATE INDEX IF NOT EXISTS idx_batch_requests_source ON batch_requests(source_id);
CREATE INDEX IF NOT EXISTS idx_batch_requests_segment ON batch_requests(segment_id);
CREATE INDEX IF NOT EXISTS idx_batch_requests_status ON batch_requests(status);
CREATE INDEX IF NOT EXISTS idx_batch_requests_custom_id ON batch_requests(custom_id);

-- View for batch job summaries
CREATE VIEW IF NOT EXISTS batch_job_summary AS
SELECT 
    bj.id,
    bj.provider,
    bj.model,
    bj.stage,
    bj.status,
    bj.request_count,
    bj.completed_count,
    bj.failed_count,
    bj.cache_hit_rate,
    bj.estimated_cost,
    bj.actual_cost,
    bj.cost_savings_from_batch + COALESCE(bj.cost_savings_from_cache, 0) AS total_savings,
    bj.created_at,
    bj.completed_at,
    CASE 
        WHEN bj.completed_at IS NOT NULL 
        THEN (julianday(bj.completed_at) - julianday(bj.created_at)) * 24 * 60 
        ELSE NULL 
    END AS duration_minutes
FROM batch_jobs bj;

-- Trigger to update cache_hit_rate when tokens are updated
CREATE TRIGGER IF NOT EXISTS update_cache_hit_rate
AFTER UPDATE OF total_input_tokens, cached_tokens ON batch_jobs
FOR EACH ROW
WHEN NEW.total_input_tokens > 0
BEGIN
    UPDATE batch_jobs 
    SET cache_hit_rate = CAST(NEW.cached_tokens AS REAL) / NEW.total_input_tokens
    WHERE id = NEW.id;
END;

