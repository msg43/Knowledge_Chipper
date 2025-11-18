-- Questions System Migration
-- Version: 1.0
-- Date: 2025-11-16
-- Purpose: Add questions feature for organizing claims by inquiry

PRAGMA foreign_keys=ON;

-- ============================================================================
-- QUESTIONS: Core questioning system
-- ============================================================================

CREATE TABLE IF NOT EXISTS questions (
    question_id TEXT PRIMARY KEY,

    -- Core content
    question_text TEXT NOT NULL UNIQUE,
    normalized_text TEXT,  -- For matching similar questions
    question_type TEXT CHECK (question_type IN (
        'factual',      -- "What is X?"
        'causal',       -- "Why does X happen?"
        'normative',    -- "Should we do X?"
        'comparative',  -- "What's better: X or Y?"
        'procedural',   -- "How do you do X?"
        'forecasting'   -- "Will X happen?"
    )),

    -- Context and framing
    description TEXT,  -- Additional context or clarification
    scope TEXT,        -- Boundaries: "in the context of climate policy"
    domain TEXT,       -- Same as claim domain: 'physics', 'economics', etc.

    -- Question status
    status TEXT DEFAULT 'open' CHECK (status IN (
        'open',         -- Actively collecting answers
        'answered',     -- Has sufficient answer(s)
        'contested',    -- Multiple conflicting answers
        'abandoned',    -- No longer pursuing
        'merged'        -- Combined into another question
    )),

    -- Answer completeness tracking
    answer_confidence REAL CHECK (answer_confidence BETWEEN 0 AND 1) DEFAULT 0,
    answer_completeness REAL CHECK (answer_completeness BETWEEN 0 AND 1) DEFAULT 0,
    has_consensus BOOLEAN DEFAULT 0,

    -- Importance and prioritization
    importance_score REAL CHECK (importance_score BETWEEN 0 AND 1),
    user_priority INTEGER,  -- 1-5 user rating

    -- Temporal tracking
    first_asked_at DATETIME,
    last_updated_at DATETIME DEFAULT (datetime('now')),

    -- User curation
    created_by TEXT,  -- 'system' or 'user'
    reviewed BOOLEAN DEFAULT 0,
    notes TEXT,

    -- If merged
    merged_into_question_id TEXT,

    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (merged_into_question_id) REFERENCES questions(question_id)
);

CREATE INDEX idx_questions_status ON questions(status);
CREATE INDEX idx_questions_domain ON questions(domain);
CREATE INDEX idx_questions_type ON questions(question_type);
CREATE INDEX idx_questions_importance ON questions(importance_score);
CREATE INDEX idx_questions_normalized ON questions(normalized_text);
CREATE INDEX idx_questions_created_by ON questions(created_by);
CREATE INDEX idx_questions_reviewed ON questions(reviewed) WHERE reviewed = 0;

-- ============================================================================
-- QUESTION-CLAIM RELATIONSHIPS
-- ============================================================================

CREATE TABLE IF NOT EXISTS question_claims (
    question_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,

    -- Relationship type: how does this claim relate to the question?
    relation_type TEXT CHECK (relation_type IN (
        'answers',           -- Direct answer
        'partial_answer',    -- Addresses part of the question
        'supports_answer',   -- Evidence for an answer
        'contradicts',       -- Conflicts with proposed answer
        'prerequisite',      -- Background needed to understand answer
        'follow_up',         -- Raises related question
        'context'            -- Provides framing/background
    )) DEFAULT 'answers',

    -- Strength and confidence
    relevance_score REAL CHECK (relevance_score BETWEEN 0 AND 1),
    confidence REAL CHECK (confidence BETWEEN 0 AND 1),

    -- User curation
    user_approved BOOLEAN DEFAULT 0,
    user_rejected BOOLEAN DEFAULT 0,
    source TEXT DEFAULT 'system',  -- 'system' or 'user'

    -- Ordering (for answer sequence)
    sequence INTEGER,

    -- Notes
    rationale TEXT,  -- Why this claim relates to this question

    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),

    PRIMARY KEY (question_id, claim_id),
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
);

CREATE INDEX idx_question_claims_question ON question_claims(question_id);
CREATE INDEX idx_question_claims_claim ON question_claims(claim_id);
CREATE INDEX idx_question_claims_relation ON question_claims(relation_type);
CREATE INDEX idx_question_claims_relevance ON question_claims(relevance_score);
CREATE INDEX idx_question_claims_pending ON question_claims(user_approved, user_rejected)
    WHERE user_approved = 0 AND user_rejected = 0;

-- ============================================================================
-- QUESTION RELATIONSHIPS
-- ============================================================================

CREATE TABLE IF NOT EXISTS question_relations (
    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_question_id TEXT NOT NULL,
    target_question_id TEXT NOT NULL,

    relation_type TEXT CHECK (relation_type IN (
        'prerequisite',   -- Must answer target before source
        'follow_up',      -- Source naturally follows from target
        'alternative',    -- Different framing of same inquiry
        'sub_question',   -- Source is component of target
        'super_question', -- Source is broader than target
        'related',        -- Generally connected
        'conflicts_with'  -- Mutually exclusive framings
    )),

    strength REAL CHECK (strength BETWEEN 0 AND 1),
    rationale TEXT,

    created_at DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (source_question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    FOREIGN KEY (target_question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    UNIQUE(source_question_id, target_question_id, relation_type)
);

CREATE INDEX idx_question_relations_source ON question_relations(source_question_id);
CREATE INDEX idx_question_relations_target ON question_relations(target_question_id);
CREATE INDEX idx_question_relations_type ON question_relations(relation_type);

-- ============================================================================
-- QUESTION CATEGORIZATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS question_categories (
    question_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,

    -- System scores
    relevance_score REAL CHECK (relevance_score BETWEEN 0 AND 1),
    confidence REAL CHECK (confidence BETWEEN 0 AND 1),

    -- Primary category flag
    is_primary BOOLEAN DEFAULT 0,

    created_at DATETIME DEFAULT (datetime('now')),

    PRIMARY KEY (question_id, wikidata_id),
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);

CREATE INDEX idx_question_categories_question ON question_categories(question_id);
CREATE INDEX idx_question_categories_category ON question_categories(wikidata_id);
CREATE UNIQUE INDEX idx_question_primary_category ON question_categories(question_id)
    WHERE is_primary = 1;

-- ============================================================================
-- QUESTION TAGS
-- ============================================================================

CREATE TABLE IF NOT EXISTS question_tags (
    question_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,

    added_by TEXT,
    added_at DATETIME DEFAULT (datetime('now')),

    PRIMARY KEY (question_id, tag_id),
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES user_tags(tag_id) ON DELETE CASCADE
);

CREATE INDEX idx_question_tags_question ON question_tags(question_id);
CREATE INDEX idx_question_tags_tag ON question_tags(tag_id);

-- ============================================================================
-- QUESTION ENTITIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS question_people (
    question_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    role TEXT,  -- 'subject', 'mentioned'

    PRIMARY KEY (question_id, person_id),
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES people(person_id) ON DELETE CASCADE
);

CREATE INDEX idx_question_people_question ON question_people(question_id);
CREATE INDEX idx_question_people_person ON question_people(person_id);

CREATE TABLE IF NOT EXISTS question_concepts (
    question_id TEXT NOT NULL,
    concept_id TEXT NOT NULL,

    PRIMARY KEY (question_id, concept_id),
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);

CREATE INDEX idx_question_concepts_question ON question_concepts(question_id);
CREATE INDEX idx_question_concepts_concept ON question_concepts(concept_id);

CREATE TABLE IF NOT EXISTS question_jargon (
    question_id TEXT NOT NULL,
    jargon_id TEXT NOT NULL,

    PRIMARY KEY (question_id, jargon_id),
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    FOREIGN KEY (jargon_id) REFERENCES jargon_terms(jargon_id) ON DELETE CASCADE
);

CREATE INDEX idx_question_jargon_question ON question_jargon(question_id);
CREATE INDEX idx_question_jargon_term ON question_jargon(jargon_id);

-- ============================================================================
-- VIEWS: Useful Query Helpers
-- ============================================================================

-- View: Questions with answer summaries
CREATE VIEW IF NOT EXISTS v_questions_with_answers AS
SELECT
    q.*,
    COUNT(DISTINCT qc.claim_id) AS total_claims,
    COUNT(DISTINCT CASE WHEN qc.relation_type = 'answers' THEN qc.claim_id END) AS direct_answers,
    COUNT(DISTINCT CASE WHEN qc.relation_type = 'contradicts' THEN qc.claim_id END) AS contradictions,
    COUNT(DISTINCT CASE WHEN qc.user_approved = 1 THEN qc.claim_id END) AS approved_claims,
    GROUP_CONCAT(DISTINCT wc.category_name, ', ') AS categories
FROM questions q
LEFT JOIN question_claims qc ON q.question_id = qc.question_id
LEFT JOIN question_categories qcat ON q.question_id = qcat.question_id
LEFT JOIN wikidata_categories wc ON qcat.wikidata_id = wc.wikidata_id
GROUP BY q.question_id;

-- View: Question hierarchy (prerequisites and follow-ups)
CREATE VIEW IF NOT EXISTS v_question_hierarchy AS
SELECT
    q1.question_id,
    q1.question_text,
    qr.relation_type,
    q2.question_id AS related_question_id,
    q2.question_text AS related_question_text,
    qr.strength
FROM questions q1
JOIN question_relations qr ON q1.question_id = qr.source_question_id
JOIN questions q2 ON qr.target_question_id = q2.question_id;

-- View: Claims answering multiple questions (interesting overlap)
CREATE VIEW IF NOT EXISTS v_claims_multi_question AS
SELECT
    c.claim_id,
    c.canonical,
    COUNT(DISTINCT qc.question_id) AS question_count,
    GROUP_CONCAT(DISTINCT q.question_text, ' | ') AS questions
FROM claims c
JOIN question_claims qc ON c.claim_id = qc.claim_id
JOIN questions q ON qc.question_id = q.question_id
GROUP BY c.claim_id
HAVING question_count > 1;

-- View: Pending question assignments (for review)
CREATE VIEW IF NOT EXISTS v_pending_question_assignments AS
SELECT
    q.question_id,
    q.question_text,
    q.created_by,
    qc.claim_id,
    c.canonical AS claim_text,
    qc.relation_type,
    qc.relevance_score,
    qc.created_at
FROM questions q
JOIN question_claims qc ON q.question_id = qc.question_id
JOIN claims c ON qc.claim_id = c.claim_id
WHERE qc.user_approved = 0 AND qc.user_rejected = 0
ORDER BY qc.created_at DESC;
