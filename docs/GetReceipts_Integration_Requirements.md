# GetReceipts Integration Requirements for Knowledge_Chipper

## Overview

This document specifies the exact requirements for GetReceipts to receive direct SQLite data uploads from Knowledge_Chipper with seamless authentication integration.

## 🎯 **Integration Principles**

1. **Direct Data Transfer**: SQLite → Supabase with zero transformation
2. **Mirror Schema**: GetReceipts tables match Knowledge_Chipper SQLite structure exactly
3. **Add User Ownership**: Only addition is `created_by` fields for RLS
4. **Seamless Auth**: Browser-based OAuth flow with token handoff

**Source Database**: All schemas below mirror Knowledge_Chipper's production database (`knowledge_system.db`), which is the single source of truth.

## 🔐 **Authentication Flow Requirements**

### Step 1: Knowledge_Chipper Initiates Upload
User clicks "Upload to GetReceipts" button in Knowledge_Chipper application.

### Step 2: Browser Authentication
Knowledge_Chipper opens user's browser to:
```
https://getreceipts.org/auth/signin?redirect_to=knowledge_chipper&return_url=http://localhost:8080/auth/callback
```

### Step 3: GetReceipts Authentication
- User signs in or creates account on GetReceipts.org
- GetReceipts handles all authentication (including 2FA, social login, etc.)
- User stays on trusted GetReceipts domain throughout auth process

### Step 4: Token Handoff
After successful authentication, GetReceipts redirects to:
```
http://localhost:8080/auth/callback?access_token=<jwt_token>&refresh_token=<refresh_token>&user_id=<uuid>
```

### Step 5: Knowledge_Chipper Upload
Knowledge_Chipper receives tokens and performs direct Supabase uploads using:
```python
supabase = create_client(supabase_url, supabase_anon_key)
supabase.auth.set_session(access_token, refresh_token)
# Direct table inserts with user_id as created_by
```

## 📊 **Required Supabase Schema**

### Core Principle: Mirror SQLite Structure Exactly

**Knowledge_Chipper SQLite Schema** → **GetReceipts Supabase Schema**

### 1. Episodes Table

**SQLite Source:**
```sql
CREATE TABLE episodes (
  episode_id   TEXT PRIMARY KEY,
  video_id     TEXT UNIQUE,
  title        TEXT,
  recorded_at  TEXT,
  inserted_at  TEXT DEFAULT (datetime('now'))
);
```

**Required Supabase Table:**
```sql
CREATE TABLE public.episodes (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  
  -- Mirror SQLite fields exactly
  episode_id TEXT UNIQUE NOT NULL,
  video_id TEXT,
  title TEXT,
  recorded_at TEXT,
  inserted_at TEXT,
  
  -- User ownership (only addition)
  created_by UUID REFERENCES auth.users(id) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.episodes ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Anyone can view episodes" ON public.episodes 
  FOR SELECT USING (true);
  
CREATE POLICY "Authenticated users can insert episodes" ON public.episodes 
  FOR INSERT TO authenticated 
  WITH CHECK (auth.uid() = created_by);
```

### 2. Claims Table

**SQLite Source:**
```sql
CREATE TABLE claims (
  episode_id       TEXT NOT NULL,
  claim_id         TEXT NOT NULL,
  canonical        TEXT NOT NULL,
  claim_type       TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
  tier             TEXT CHECK (tier IN ('A','B','C')),
  first_mention_ts TEXT,
  scores_json      TEXT NOT NULL,
  
  -- Temporality analysis
  temporality_score INTEGER CHECK (temporality_score IN (1,2,3,4,5)) DEFAULT 3,  -- 1=Immediate, 5=Timeless
  temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1) DEFAULT 0.5,
  temporality_rationale TEXT,       -- Why this claim has this temporality
  
  -- Structured categories
  structured_categories_json TEXT,  -- JSON array of category names
  category_relevance_scores_json TEXT,  -- JSON object mapping categories to relevance scores
  
  inserted_at      TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (episode_id, claim_id)
);
```

**Required Supabase Table:**
```sql
CREATE TABLE public.claims (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  
  -- Mirror SQLite fields exactly
  episode_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  canonical TEXT NOT NULL,
  claim_type TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
  tier TEXT CHECK (tier IN ('A','B','C')),
  first_mention_ts TEXT,
  scores_json TEXT NOT NULL,
  
  -- Temporality analysis (mirror SQLite exactly)
  temporality_score INTEGER CHECK (temporality_score IN (1,2,3,4,5)) DEFAULT 3,  -- 1=Immediate, 5=Timeless
  temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1) DEFAULT 0.5,
  temporality_rationale TEXT,       -- Why this claim has this temporality
  
  -- Structured categories (mirror SQLite exactly)
  structured_categories_json TEXT,  -- JSON array of category names
  category_relevance_scores_json TEXT,  -- JSON object mapping categories to relevance scores
  
  inserted_at TEXT,
  
  -- User ownership (only addition)
  created_by UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Preserve SQLite composite key as unique constraint
  UNIQUE(episode_id, claim_id)
);

-- Enable RLS
ALTER TABLE public.claims ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Anyone can view claims" ON public.claims 
  FOR SELECT USING (true);
  
CREATE POLICY "Authenticated users can insert claims" ON public.claims 
  FOR INSERT TO authenticated 
  WITH CHECK (auth.uid() = created_by);
```

### 3. Evidence Spans Table

**SQLite Source:**
```sql
CREATE TABLE evidence_spans (
  episode_id  TEXT NOT NULL,
  claim_id    TEXT NOT NULL,
  seq         INTEGER NOT NULL,
  segment_id  TEXT,
  t0          TEXT,
  t1          TEXT,
  quote       TEXT,
  context_t0  TEXT,
  context_t1  TEXT,
  context_text TEXT,
  context_type TEXT DEFAULT 'exact',
  PRIMARY KEY (episode_id, claim_id, seq)
);
```

**Required Supabase Table:**
```sql
CREATE TABLE public.evidence_spans (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  
  -- Mirror SQLite fields exactly
  episode_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  segment_id TEXT,
  t0 TEXT,
  t1 TEXT,
  quote TEXT,
  context_t0 TEXT,
  context_t1 TEXT,
  context_text TEXT,
  context_type TEXT DEFAULT 'exact',
  
  -- User ownership (only addition)
  created_by UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Preserve SQLite composite key
  UNIQUE(episode_id, claim_id, seq)
);

-- Enable RLS
ALTER TABLE public.evidence_spans ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Anyone can view evidence" ON public.evidence_spans 
  FOR SELECT USING (true);
  
CREATE POLICY "Authenticated users can insert evidence" ON public.evidence_spans 
  FOR INSERT TO authenticated 
  WITH CHECK (auth.uid() = created_by);
```

### 4. People Table

**SQLite Source:**
```sql
CREATE TABLE people (
  episode_id        TEXT NOT NULL,
  mention_id        TEXT NOT NULL,
  span_segment_id   TEXT,
  t0                TEXT,
  t1                TEXT,
  surface           TEXT NOT NULL,
  normalized        TEXT,
  entity_type       TEXT CHECK (entity_type IN ('person','org')) DEFAULT 'person',
  external_ids_json TEXT,
  confidence        REAL,
  PRIMARY KEY (episode_id, mention_id)
);
```

**Required Supabase Table:**
```sql
CREATE TABLE public.people (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  
  -- Mirror SQLite fields exactly
  episode_id TEXT NOT NULL,
  mention_id TEXT NOT NULL,
  span_segment_id TEXT,
  t0 TEXT,
  t1 TEXT,
  surface TEXT NOT NULL,
  normalized TEXT,
  entity_type TEXT CHECK (entity_type IN ('person','org')) DEFAULT 'person',
  external_ids_json TEXT,
  confidence REAL,
  
  -- User ownership (only addition)
  created_by UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Preserve SQLite composite key
  UNIQUE(episode_id, mention_id)
);

-- Enable RLS
ALTER TABLE public.people ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Anyone can view people" ON public.people 
  FOR SELECT USING (true);
  
CREATE POLICY "Authenticated users can insert people" ON public.people 
  FOR INSERT TO authenticated 
  WITH CHECK (auth.uid() = created_by);
```

### 5. Concepts Table

**SQLite Source:**
```sql
CREATE TABLE concepts (
  episode_id        TEXT NOT NULL,
  model_id          TEXT NOT NULL,
  name              TEXT NOT NULL,
  definition        TEXT,
  first_mention_ts  TEXT,
  aliases_json      TEXT,
  evidence_json     TEXT,
  PRIMARY KEY (episode_id, model_id)
);
```

**Required Supabase Table:**
```sql
CREATE TABLE public.concepts (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  
  -- Mirror SQLite fields exactly
  episode_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  name TEXT NOT NULL,
  definition TEXT,
  first_mention_ts TEXT,
  aliases_json TEXT,
  evidence_json TEXT,
  
  -- User ownership (only addition)
  created_by UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Preserve SQLite composite key
  UNIQUE(episode_id, model_id)
);

-- Enable RLS
ALTER TABLE public.concepts ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Anyone can view concepts" ON public.concepts 
  FOR SELECT USING (true);
  
CREATE POLICY "Authenticated users can insert concepts" ON public.concepts 
  FOR INSERT TO authenticated 
  WITH CHECK (auth.uid() = created_by);
```

### 6. Jargon Table

**SQLite Source:**
```sql
CREATE TABLE jargon (
  episode_id    TEXT NOT NULL,
  term_id       TEXT NOT NULL,
  term          TEXT NOT NULL,
  category      TEXT,
  definition    TEXT,
  evidence_json TEXT,
  PRIMARY KEY (episode_id, term_id)
);
```

**Required Supabase Table:**
```sql
CREATE TABLE public.jargon (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  
  -- Mirror SQLite fields exactly
  episode_id TEXT NOT NULL,
  term_id TEXT NOT NULL,
  term TEXT NOT NULL,
  category TEXT,
  definition TEXT,
  evidence_json TEXT,
  
  -- User ownership (only addition)
  created_by UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Preserve SQLite composite key
  UNIQUE(episode_id, term_id)
);

-- Enable RLS
ALTER TABLE public.jargon ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Anyone can view jargon" ON public.jargon 
  FOR SELECT USING (true);
  
CREATE POLICY "Authenticated users can insert jargon" ON public.jargon 
  FOR INSERT TO authenticated 
  WITH CHECK (auth.uid() = created_by);
```

### 7. Relations Table

**SQLite Source:**
```sql
CREATE TABLE relations (
  episode_id       TEXT NOT NULL,
  source_claim_id  TEXT NOT NULL,
  target_claim_id  TEXT NOT NULL,
  type             TEXT CHECK (type IN ('supports','contradicts','depends_on','refines')),
  strength         REAL CHECK (strength BETWEEN 0 AND 1),
  rationale        TEXT,
  PRIMARY KEY (episode_id, source_claim_id, target_claim_id, type)
);
```

**Required Supabase Table:**
```sql
CREATE TABLE public.relations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  
  -- Mirror SQLite fields exactly
  episode_id TEXT NOT NULL,
  source_claim_id TEXT NOT NULL,
  target_claim_id TEXT NOT NULL,
  type TEXT CHECK (type IN ('supports','contradicts','depends_on','refines')),
  strength REAL CHECK (strength BETWEEN 0 AND 1),
  rationale TEXT,
  
  -- User ownership (only addition)
  created_by UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Preserve SQLite composite key
  UNIQUE(episode_id, source_claim_id, target_claim_id, type)
);

-- Enable RLS
ALTER TABLE public.relations ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Anyone can view relations" ON public.relations 
  FOR SELECT USING (true);
  
CREATE POLICY "Authenticated users can insert relations" ON public.relations 
  FOR INSERT TO authenticated 
  WITH CHECK (auth.uid() = created_by);
```

### 8. Milestones Table (Optional - May Be Empty)

**SQLite Source:**
```sql
CREATE TABLE milestones (
  episode_id    TEXT NOT NULL,
  milestone_id  TEXT NOT NULL,
  t0            TEXT,
  t1            TEXT,
  summary       TEXT,
  PRIMARY KEY (episode_id, milestone_id)
);
```

**Required Supabase Table:**
```sql
CREATE TABLE public.milestones (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  
  -- Mirror SQLite fields exactly
  episode_id TEXT NOT NULL,
  milestone_id TEXT NOT NULL,
  t0 TEXT,
  t1 TEXT,
  summary TEXT,
  
  -- User ownership (only addition)
  created_by UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Preserve SQLite composite key
  UNIQUE(episode_id, milestone_id)
);

-- Enable RLS
ALTER TABLE public.milestones ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Anyone can view milestones" ON public.milestones 
  FOR SELECT USING (true);
  
CREATE POLICY "Authenticated users can insert milestones" ON public.milestones 
  FOR INSERT TO authenticated 
  WITH CHECK (auth.uid() = created_by);
```

## 🔧 **Required Supabase Configuration**

### Implementation Order

**CRITICAL: Tables must be created in this exact order due to foreign key dependencies:**

1. **episodes** (no dependencies)
2. **milestones** (depends on episodes)
3. **claims** (depends on episodes) 
4. **evidence_spans** (depends on episodes + claims)
5. **people** (depends on episodes)
6. **concepts** (depends on episodes)
7. **jargon** (depends on episodes)
8. **relations** (depends on episodes + claims)

### RLS Setup Order

For each table, follow this sequence:
1. Create table structure
2. Enable RLS: `ALTER TABLE public.[table_name] ENABLE ROW LEVEL SECURITY;`
3. Create SELECT policy (public read access)
4. Create INSERT policy (authenticated users only)
5. Create performance indexes
6. Test with sample data

### Required Database Triggers

```sql
-- Auto-update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to tables with updated_at columns
CREATE TRIGGER update_episodes_updated_at 
    BEFORE UPDATE ON public.episodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_claims_updated_at 
    BEFORE UPDATE ON public.claims
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### Handling Existing Tables

If any tables already exist:
```sql
-- Check existing structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'claims' AND table_schema = 'public';

-- Add missing columns (example for claims)
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS temporality_score INTEGER CHECK (temporality_score IN (1,2,3,4,5)) DEFAULT 3;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1) DEFAULT 0.5;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS temporality_rationale TEXT;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS structured_categories_json TEXT;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS category_relevance_scores_json TEXT;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id);

-- Enable RLS if not already enabled
ALTER TABLE public.claims ENABLE ROW LEVEL SECURITY;
```

### Authentication Settings
```javascript
// Supabase Auth Configuration
{
  "jwt_expiry": 3600,
  "refresh_token_rotation": true,
  "confirm_email": false,  // Optional - Knowledge_Chipper can handle unconfirmed users
  "site_url": "https://getreceipts.org",
  "redirect_urls": [
    "http://localhost:8080/auth/callback",
    "http://127.0.0.1:8080/auth/callback"
  ]
}
```

### Temporality Analysis Documentation

#### Temporality Score Scale (1-5)
- **1 = Immediate**: Claims relevant only for a very short time (hours/days)
- **2 = Short-term**: Claims relevant for weeks to months  
- **3 = Medium-term**: Claims relevant for months to years (default)
- **4 = Long-term**: Claims relevant for years to decades
- **5 = Timeless**: Claims that remain relevant indefinitely

#### Structured Categories Format
- **structured_categories_json**: JSON array of category names, e.g., `["science", "climate", "temperature"]`
- **category_relevance_scores_json**: JSON object mapping categories to relevance scores, e.g., `{"science": 0.95, "climate": 0.90, "temperature": 0.85}`

### Required Indexes for Performance
```sql
-- Performance indexes for common queries
CREATE INDEX idx_episodes_episode_id ON public.episodes(episode_id);
CREATE INDEX idx_claims_episode_claim ON public.claims(episode_id, claim_id);
CREATE INDEX idx_evidence_episode_claim ON public.evidence_spans(episode_id, claim_id);
CREATE INDEX idx_people_episode ON public.people(episode_id);
CREATE INDEX idx_concepts_episode ON public.concepts(episode_id);
CREATE INDEX idx_jargon_episode ON public.jargon(episode_id);
CREATE INDEX idx_relations_episode ON public.relations(episode_id);
CREATE INDEX idx_milestones_episode ON public.milestones(episode_id);

-- Temporality and categories indexes
CREATE INDEX idx_claims_temporality_score ON public.claims(temporality_score);
CREATE INDEX idx_claims_structured_categories ON public.claims USING gin(structured_categories_json);

-- User ownership indexes
CREATE INDEX idx_episodes_created_by ON public.episodes(created_by);
CREATE INDEX idx_claims_created_by ON public.claims(created_by);
```

## 🚀 **Upload Process from Knowledge_Chipper**

### Direct SQLite to Supabase Transfer
```python
def upload_to_getreceipts(sqlite_db_path, supabase_url, supabase_key, user_tokens):
    # Initialize connections
    sqlite_conn = sqlite3.connect(sqlite_db_path)
    sqlite_conn.row_factory = sqlite3.Row
    
    supabase = create_client(supabase_url, supabase_key)
    supabase.auth.set_session(user_tokens['access_token'], user_tokens['refresh_token'])
    
    user_id = user_tokens['user_id']
    
    # 1. Upload Episodes
    episodes = sqlite_conn.execute("SELECT * FROM episodes").fetchall()
    for episode in episodes:
        episode_data = dict(episode)
        episode_data['created_by'] = user_id
        supabase.table("episodes").insert(episode_data).execute()
    
    # 2. Upload Milestones (if any)
    milestones = sqlite_conn.execute("SELECT * FROM milestones").fetchall()
    for milestone in milestones:
        milestone_data = dict(milestone)
        milestone_data['created_by'] = user_id
        supabase.table("milestones").insert(milestone_data).execute()
    
    # 3. Upload Claims
    claims = sqlite_conn.execute("SELECT * FROM claims").fetchall()
    for claim in claims:
        claim_data = dict(claim)
        claim_data['created_by'] = user_id
        supabase.table("claims").insert(claim_data).execute()
    
    # 4. Upload Evidence Spans
    evidence = sqlite_conn.execute("SELECT * FROM evidence_spans").fetchall()
    for span in evidence:
        span_data = dict(span)
        span_data['created_by'] = user_id
        supabase.table("evidence_spans").insert(span_data).execute()
    
    # 5. Upload People
    people = sqlite_conn.execute("SELECT * FROM people").fetchall()
    for person in people:
        person_data = dict(person)
        person_data['created_by'] = user_id
        supabase.table("people").insert(person_data).execute()
    
    # 6. Upload Concepts
    concepts = sqlite_conn.execute("SELECT * FROM concepts").fetchall()
    for concept in concepts:
        concept_data = dict(concept)
        concept_data['created_by'] = user_id
        supabase.table("concepts").insert(concept_data).execute()
    
    # 7. Upload Jargon
    jargon = sqlite_conn.execute("SELECT * FROM jargon").fetchall()
    for term in jargon:
        term_data = dict(term)
        term_data['created_by'] = user_id
        supabase.table("jargon").insert(term_data).execute()
    
    # 8. Upload Relations
    relations = sqlite_conn.execute("SELECT * FROM relations").fetchall()
    for relation in relations:
        relation_data = dict(relation)
        relation_data['created_by'] = user_id
        supabase.table("relations").insert(relation_data).execute()
```

## 📋 **Testing Requirements**

### Authentication Flow Test
1. Knowledge_Chipper opens browser to GetReceipts auth URL
2. User completes authentication on GetReceipts.org
3. GetReceipts redirects with valid tokens
4. Knowledge_Chipper successfully authenticates with Supabase
5. RLS policies allow data insertion

### Database Structure Test
1. Verify tables created in correct dependency order
2. Test foreign key constraints work properly
3. Confirm all required columns exist with correct types
4. Verify RLS policies are enabled on all tables
5. Test database triggers fire correctly

### Data Upload Test
1. Upload complete episode with all data types
2. Verify all tables receive data correctly
3. Confirm RLS policies filter by user ownership
4. Test batch uploads (50+ claims)
5. Verify foreign key relationships work across tables
6. Test upload dependency order (episodes → claims → evidence)

### Error Handling Test
1. Network interruption during upload
2. Invalid authentication tokens
3. Duplicate data handling
4. Database constraint violations

## 🎯 **Success Criteria**

✅ **GetReceipts can receive all Knowledge_Chipper data types**  
✅ **Zero data transformation required**  
✅ **Authentication handoff works seamlessly**  
✅ **RLS policies enforce user data ownership**  
✅ **Batch uploads perform efficiently**  
✅ **All SQLite relationships preserved in Supabase**

## 📋 **Implementation Checklist for GetReceipts**

### Phase 1: Preparation
- [ ] Configure Supabase authentication settings
- [ ] Set up redirect URLs for Knowledge_Chipper callbacks
- [ ] Create auto-update timestamp function

### Phase 2: Table Creation (In Order)
- [ ] Create episodes table + RLS policies + indexes
- [ ] Create milestones table + RLS policies + indexes
- [ ] Create claims table + RLS policies + indexes  
- [ ] Create evidence_spans table + RLS policies + indexes
- [ ] Create people table + RLS policies + indexes
- [ ] Create concepts table + RLS policies + indexes
- [ ] Create jargon table + RLS policies + indexes
- [ ] Create relations table + RLS policies + indexes

### Phase 3: Verification
- [ ] Test authentication flow with Knowledge_Chipper
- [ ] Verify foreign key constraints work
- [ ] Test RLS policies with sample data
- [ ] Performance test with indexes

This specification ensures GetReceipts is ready for direct, high-fidelity data transfer from Knowledge_Chipper with secure user authentication.
