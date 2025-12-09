-- Claim Groups System Migration
-- Version: 1.0
-- Date: 2025-12-07
-- Purpose: Add claim groups, group relations, thinker notes, and question sides
--          for the Knowledge Exploration Platform

PRAGMA foreign_keys=ON;

-- ============================================================================
-- CLAIM GROUPS: User-created collections for research/argumentation
-- ============================================================================

CREATE TABLE IF NOT EXISTS claim_groups (
    group_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    group_type TEXT CHECK (group_type IN (
        'research',        -- Academic/research collection
        'argument',        -- Building a specific argument
        'comparison',      -- Comparing related claims
        'reading_list',    -- Claims to review later
        'debate_position', -- Position in a debate
        'thesis',          -- Supporting a thesis
        'counterargument'  -- Collection of objections
    )),
    
    -- Visibility and sharing
    is_public BOOLEAN DEFAULT 0,
    share_slug TEXT UNIQUE,  -- For public sharing URLs
    
    -- Visual customization
    color TEXT,  -- Hex color for constellation view
    icon TEXT,   -- Icon identifier
    
    -- Metadata (denormalized for performance)
    claim_count INTEGER DEFAULT 0,
    
    -- User tracking
    created_by TEXT,  -- 'system' or user identifier
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX idx_claim_groups_type ON claim_groups(group_type);
CREATE INDEX idx_claim_groups_public ON claim_groups(is_public) WHERE is_public = 1;
CREATE INDEX idx_claim_groups_created_by ON claim_groups(created_by);
CREATE INDEX idx_claim_groups_share_slug ON claim_groups(share_slug) WHERE share_slug IS NOT NULL;

-- ============================================================================
-- CLAIM GROUP MEMBERS: Claims within groups with ordering and notes
-- ============================================================================

CREATE TABLE IF NOT EXISTS claim_group_members (
    group_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    
    -- Ordering and organization
    sequence INTEGER DEFAULT 0,
    role TEXT CHECK (role IN (
        'central',      -- Core claim of the group
        'supporting',   -- Supports the central claim(s)
        'counterpoint', -- Presents opposing view
        'context',      -- Provides background/context
        'member'        -- General member
    )) DEFAULT 'member',
    
    -- User annotations
    user_note TEXT,
    highlight_color TEXT,  -- For visual emphasis in UI
    
    -- Position in constellation view (optional pre-computed)
    position_x REAL,
    position_y REAL,
    
    -- Tracking
    added_by TEXT,
    added_at DATETIME DEFAULT (datetime('now')),
    
    PRIMARY KEY (group_id, claim_id),
    FOREIGN KEY (group_id) REFERENCES claim_groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
);

CREATE INDEX idx_claim_group_members_group ON claim_group_members(group_id);
CREATE INDEX idx_claim_group_members_claim ON claim_group_members(claim_id);
CREATE INDEX idx_claim_group_members_role ON claim_group_members(role);
CREATE INDEX idx_claim_group_members_sequence ON claim_group_members(group_id, sequence);

-- ============================================================================
-- GROUP RELATIONS: Relationships between claim groups
-- ============================================================================

CREATE TABLE IF NOT EXISTS group_relations (
    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_group_id TEXT NOT NULL,
    target_group_id TEXT NOT NULL,
    
    -- Relationship semantics
    relation_type TEXT CHECK (relation_type IN (
        'sympathetic',   -- Groups support similar conclusions
        'antagonistic',  -- Groups oppose each other
        'builds_upon',   -- Source extends/builds on target
        'responds_to',   -- Source is a response to target
        'parallel',      -- Groups address similar topics differently
        'extends',       -- Source is an extension of target
        'contradicts',   -- Groups contain contradictory claims
        'refines'        -- Source refines/improves target
    )) NOT NULL,
    strength REAL CHECK (strength BETWEEN 0 AND 1) DEFAULT 0.5,
    
    -- User explanation
    user_note TEXT,
    rationale TEXT,
    
    -- Visual properties for constellation view
    edge_color TEXT,
    edge_style TEXT CHECK (edge_style IN ('solid', 'dashed', 'dotted')) DEFAULT 'solid',
    
    -- Tracking
    created_by TEXT,
    created_at DATETIME DEFAULT (datetime('now')),
    
    FOREIGN KEY (source_group_id) REFERENCES claim_groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY (target_group_id) REFERENCES claim_groups(group_id) ON DELETE CASCADE,
    UNIQUE(source_group_id, target_group_id, relation_type)
);

CREATE INDEX idx_group_relations_source ON group_relations(source_group_id);
CREATE INDEX idx_group_relations_target ON group_relations(target_group_id);
CREATE INDEX idx_group_relations_type ON group_relations(relation_type);

-- ============================================================================
-- THINKER NOTES: User annotations on people/thinkers
-- ============================================================================

CREATE TABLE IF NOT EXISTS thinker_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    
    -- Note content
    title TEXT,
    content TEXT NOT NULL,
    note_type TEXT CHECK (note_type IN (
        'worldview',   -- Overall intellectual stance
        'critique',    -- Criticism or concern
        'summary',     -- Summary of positions
        'question',    -- Questions about their work
        'insight',     -- Personal insight/observation
        'comparison',  -- Comparing to other thinkers
        'evolution'    -- How their thinking has changed
    )),
    
    -- Visibility
    is_public BOOLEAN DEFAULT 0,
    
    -- User tracking
    created_by TEXT,
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),
    
    FOREIGN KEY (person_id) REFERENCES people(person_id) ON DELETE CASCADE
);

CREATE INDEX idx_thinker_notes_person ON thinker_notes(person_id);
CREATE INDEX idx_thinker_notes_type ON thinker_notes(note_type);
CREATE INDEX idx_thinker_notes_public ON thinker_notes(is_public) WHERE is_public = 1;

-- ============================================================================
-- QUESTION SIDES: Explicit positions within a debate/question
-- ============================================================================

CREATE TABLE IF NOT EXISTS question_sides (
    side_id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    
    -- Side definition
    name TEXT NOT NULL,  -- 'Affirmative', 'Negative', 'Qualified Yes', etc.
    description TEXT,
    position TEXT CHECK (position IN (
        'for',       -- Supports the proposition
        'against',   -- Opposes the proposition
        'nuanced',   -- Context-dependent answer
        'other'      -- Alternative framing
    )),
    
    -- Visual properties for debate arena
    color TEXT,            -- Hex color
    position_angle REAL,   -- Angle in polar view (0-360 degrees)
    
    -- Tracking
    created_by TEXT,
    created_at DATETIME DEFAULT (datetime('now')),
    
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE
);

CREATE INDEX idx_question_sides_question ON question_sides(question_id);
CREATE INDEX idx_question_sides_position ON question_sides(position);

-- ============================================================================
-- QUESTION SIDE CLAIMS: Claims assigned to sides
-- ============================================================================

CREATE TABLE IF NOT EXISTS question_side_claims (
    side_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    
    -- Relationship strength
    relevance_score REAL CHECK (relevance_score BETWEEN 0 AND 1),
    is_key_argument BOOLEAN DEFAULT 0,  -- Featured/highlighted argument
    
    -- User curation
    user_approved BOOLEAN DEFAULT 0,
    user_note TEXT,
    
    -- Tracking
    added_by TEXT,
    added_at DATETIME DEFAULT (datetime('now')),
    
    PRIMARY KEY (side_id, claim_id),
    FOREIGN KEY (side_id) REFERENCES question_sides(side_id) ON DELETE CASCADE,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
);

CREATE INDEX idx_question_side_claims_side ON question_side_claims(side_id);
CREATE INDEX idx_question_side_claims_claim ON question_side_claims(claim_id);
CREATE INDEX idx_question_side_claims_key ON question_side_claims(is_key_argument) WHERE is_key_argument = 1;

-- ============================================================================
-- VIEWS: Useful Query Helpers for Knowledge Exploration
-- ============================================================================

-- View: Claim groups with member counts and stats
CREATE VIEW IF NOT EXISTS v_claim_groups_with_stats AS
SELECT
    cg.*,
    COUNT(DISTINCT cgm.claim_id) AS actual_claim_count,
    COUNT(DISTINCT CASE WHEN cgm.role = 'central' THEN cgm.claim_id END) AS central_claims,
    COUNT(DISTINCT CASE WHEN cgm.role = 'supporting' THEN cgm.claim_id END) AS supporting_claims,
    COUNT(DISTINCT CASE WHEN cgm.role = 'counterpoint' THEN cgm.claim_id END) AS counterpoint_claims,
    GROUP_CONCAT(DISTINCT c.domain, ', ') AS domains
FROM claim_groups cg
LEFT JOIN claim_group_members cgm ON cg.group_id = cgm.group_id
LEFT JOIN claims c ON cgm.claim_id = c.claim_id
GROUP BY cg.group_id;

-- View: Question sides with claim counts
CREATE VIEW IF NOT EXISTS v_question_sides_with_claims AS
SELECT
    qs.*,
    q.question_text,
    q.status AS question_status,
    COUNT(DISTINCT qsc.claim_id) AS claim_count,
    COUNT(DISTINCT CASE WHEN qsc.is_key_argument = 1 THEN qsc.claim_id END) AS key_argument_count,
    AVG(qsc.relevance_score) AS avg_relevance
FROM question_sides qs
LEFT JOIN questions q ON qs.question_id = q.question_id
LEFT JOIN question_side_claims qsc ON qs.side_id = qsc.side_id
GROUP BY qs.side_id;

-- View: Thinkers with claim groups they participate in
CREATE VIEW IF NOT EXISTS v_thinker_group_participation AS
SELECT
    p.person_id,
    p.name AS thinker_name,
    cg.group_id,
    cg.name AS group_name,
    cg.group_type,
    COUNT(DISTINCT cgm.claim_id) AS claims_in_group
FROM people p
JOIN claim_people cp ON p.person_id = cp.person_id
JOIN claim_group_members cgm ON cp.claim_id = cgm.claim_id
JOIN claim_groups cg ON cgm.group_id = cg.group_id
GROUP BY p.person_id, cg.group_id;

-- View: Group relationships with full context
CREATE VIEW IF NOT EXISTS v_group_relations_full AS
SELECT
    gr.*,
    sg.name AS source_group_name,
    sg.group_type AS source_group_type,
    tg.name AS target_group_name,
    tg.group_type AS target_group_type
FROM group_relations gr
JOIN claim_groups sg ON gr.source_group_id = sg.group_id
JOIN claim_groups tg ON gr.target_group_id = tg.group_id;

-- View: Debate arena data for a question
CREATE VIEW IF NOT EXISTS v_debate_arena AS
SELECT
    q.question_id,
    q.question_text,
    qs.side_id,
    qs.name AS side_name,
    qs.position,
    qs.color AS side_color,
    qs.position_angle,
    c.claim_id,
    c.canonical AS claim_text,
    c.tier,
    c.importance_score,
    qsc.relevance_score,
    qsc.is_key_argument,
    p.person_id,
    p.name AS thinker_name
FROM questions q
JOIN question_sides qs ON q.question_id = qs.question_id
JOIN question_side_claims qsc ON qs.side_id = qsc.side_id
JOIN claims c ON qsc.claim_id = c.claim_id
LEFT JOIN claim_people cp ON c.claim_id = cp.claim_id
LEFT JOIN people p ON cp.person_id = p.person_id;
