-- Add Health Tracking System Tables (Web-Canonical Pattern)
-- Date: 2026-01-02
-- Purpose: Personal health tracking for interventions, metrics, and health issues
--          Local is ephemeral, web is source of truth

-- ============================================================================
-- Health Interventions Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS health_interventions (
    intervention_id TEXT PRIMARY KEY,
    
    -- Privacy (web-canonical)
    privacy_status TEXT DEFAULT 'private',  -- private, public
    
    -- Status
    active BOOLEAN DEFAULT 1,
    
    -- Core fields
    name TEXT NOT NULL,
    body_system TEXT,  -- Skeletal System, Muscular System, etc.
    organs TEXT,       -- Brain, Heart, Lungs, etc.
    author TEXT,
    frequency TEXT,
    metric TEXT,
    
    -- Peter Attia categorization
    pete_attia_category TEXT,  -- Metabolic dysfunction, Cancer, Cardiovascular disease, Neurodegenerative disease
    pa_subcategory TEXT,
    
    -- Sources
    source_1 TEXT,
    source_2 TEXT,
    source_3 TEXT,
    
    -- Notes
    matt_notes TEXT,
    
    -- Sync tracking (web-canonical)
    synced_to_web BOOLEAN DEFAULT 0,
    web_id TEXT,  -- UUID from Supabase
    last_synced_at DATETIME,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_health_interventions_active ON health_interventions(active);
CREATE INDEX IF NOT EXISTS idx_health_interventions_category ON health_interventions(pete_attia_category);
CREATE INDEX IF NOT EXISTS idx_health_interventions_synced ON health_interventions(synced_to_web);

-- ============================================================================
-- Health Metrics Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS health_metrics (
    metric_id TEXT PRIMARY KEY,
    
    -- Privacy (web-canonical)
    privacy_status TEXT DEFAULT 'private',
    
    -- Status
    active BOOLEAN DEFAULT 1,
    
    -- Core fields
    name TEXT NOT NULL,
    body_system TEXT,
    organs TEXT,
    author TEXT,
    frequency TEXT,
    metric TEXT,
    
    -- Peter Attia categorization
    pete_attia_category TEXT,
    pa_subcategory TEXT,
    
    -- Sources
    source_1 TEXT,
    source_2 TEXT,
    
    -- Sync tracking (web-canonical)
    synced_to_web BOOLEAN DEFAULT 0,
    web_id TEXT,
    last_synced_at DATETIME,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_health_metrics_active ON health_metrics(active);
CREATE INDEX IF NOT EXISTS idx_health_metrics_category ON health_metrics(pete_attia_category);
CREATE INDEX IF NOT EXISTS idx_health_metrics_synced ON health_metrics(synced_to_web);

-- ============================================================================
-- Health Issues Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS health_issues (
    issue_id TEXT PRIMARY KEY,
    
    -- Privacy (web-canonical)
    privacy_status TEXT DEFAULT 'private',
    
    -- Status
    active BOOLEAN DEFAULT 1,
    
    -- Core fields
    name TEXT NOT NULL,
    body_system TEXT,
    organs TEXT,
    author TEXT,
    frequency TEXT,
    metric TEXT,
    
    -- Peter Attia categorization
    pete_attia_category TEXT,
    pa_subcategory TEXT,
    
    -- Sources
    source_1 TEXT,
    source_2 TEXT,
    
    -- Notes
    matt_notes TEXT,
    
    -- Sync tracking (web-canonical)
    synced_to_web BOOLEAN DEFAULT 0,
    web_id TEXT,
    last_synced_at DATETIME,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_health_issues_active ON health_issues(active);
CREATE INDEX IF NOT EXISTS idx_health_issues_category ON health_issues(pete_attia_category);
CREATE INDEX IF NOT EXISTS idx_health_issues_synced ON health_issues(synced_to_web);
