-- Prediction System Schema
-- Date: 2026-01-02
-- Purpose: Personal forecasting system for tracking predictions with confidence/deadline history

PRAGMA foreign_keys=ON;

-- ============================================================================
-- PREDICTIONS: User-made predictions about future events
-- ============================================================================

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id TEXT PRIMARY KEY,
    
    -- Core prediction content
    title TEXT NOT NULL,
    description TEXT,
    
    -- Current values (tracked over time in prediction_history)
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    deadline DATE NOT NULL,
    
    -- Resolution tracking
    resolution_status TEXT DEFAULT 'pending' CHECK (resolution_status IN ('pending', 'correct', 'incorrect', 'ambiguous', 'cancelled')),
    resolution_notes TEXT,
    resolved_at DATETIME,
    
    -- User's reasoning
    user_notes TEXT,
    
    -- Privacy (follows same pattern as claims)
    privacy_status TEXT DEFAULT 'private' CHECK (privacy_status IN ('public', 'private')),
    
    -- Sync tracking (for future GetReceipts integration)
    uploaded BOOLEAN DEFAULT 0,
    uploaded_at DATETIME,
    hidden BOOLEAN DEFAULT 0,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX idx_predictions_deadline ON predictions(deadline);
CREATE INDEX idx_predictions_status ON predictions(resolution_status);
CREATE INDEX idx_predictions_privacy ON predictions(privacy_status);
CREATE INDEX idx_predictions_created ON predictions(created_at);

-- ============================================================================
-- PREDICTION_HISTORY: Track confidence and deadline changes over time
-- ============================================================================

CREATE TABLE IF NOT EXISTS prediction_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT NOT NULL,
    
    -- Values at this point in time
    timestamp DATETIME DEFAULT (datetime('now')),
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    deadline DATE NOT NULL,
    
    -- Why did the user update?
    change_reason TEXT,
    
    FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id) ON DELETE CASCADE
);

CREATE INDEX idx_prediction_history_prediction ON prediction_history(prediction_id);
CREATE INDEX idx_prediction_history_timestamp ON prediction_history(timestamp);

-- ============================================================================
-- PREDICTION_EVIDENCE: Link predictions to claims, jargon, people, concepts
-- ============================================================================

CREATE TABLE IF NOT EXISTS prediction_evidence (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT NOT NULL,
    
    -- What entity is this evidence from?
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ('claim', 'jargon', 'concept', 'person')),
    entity_id TEXT NOT NULL,
    
    -- User's classification of this evidence
    stance TEXT DEFAULT 'neutral' CHECK (stance IN ('pro', 'con', 'neutral')),
    
    -- User's notes about why this evidence matters
    user_notes TEXT,
    
    -- Timestamp
    added_at DATETIME DEFAULT (datetime('now')),
    
    FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id) ON DELETE CASCADE,
    
    -- Ensure no duplicate evidence entries
    UNIQUE(prediction_id, evidence_type, entity_id)
);

CREATE INDEX idx_prediction_evidence_prediction ON prediction_evidence(prediction_id);
CREATE INDEX idx_prediction_evidence_type ON prediction_evidence(evidence_type);
CREATE INDEX idx_prediction_evidence_entity ON prediction_evidence(entity_id);
CREATE INDEX idx_prediction_evidence_stance ON prediction_evidence(stance);

-- ============================================================================
-- TRIGGERS: Auto-update timestamps
-- ============================================================================

-- Trigger to update predictions.updated_at
CREATE TRIGGER IF NOT EXISTS update_predictions_timestamp
AFTER UPDATE ON predictions
FOR EACH ROW
BEGIN
    UPDATE predictions SET updated_at = datetime('now') WHERE prediction_id = NEW.prediction_id;
END;

-- Trigger to create history entry when confidence or deadline changes
CREATE TRIGGER IF NOT EXISTS create_prediction_history
AFTER UPDATE OF confidence, deadline ON predictions
FOR EACH ROW
WHEN OLD.confidence != NEW.confidence OR OLD.deadline != NEW.deadline
BEGIN
    INSERT INTO prediction_history (prediction_id, confidence, deadline, change_reason)
    VALUES (NEW.prediction_id, NEW.confidence, NEW.deadline, 'Auto-saved on update');
END;

-- Trigger to create initial history entry when prediction is created
CREATE TRIGGER IF NOT EXISTS create_initial_prediction_history
AFTER INSERT ON predictions
FOR EACH ROW
BEGIN
    INSERT INTO prediction_history (prediction_id, confidence, deadline, change_reason)
    VALUES (NEW.prediction_id, NEW.confidence, NEW.deadline, 'Initial prediction created');
END;

