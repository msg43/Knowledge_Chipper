# GetReceipts Supabase Schema Mapping Guide

## Overview
This document provides the complete mapping between Knowledge Chipper's HCE data and the expected GetReceipts Supabase schema with Row Level Security (RLS) policies.

## Data Flow Architecture

```
Knowledge_Chipper HCE Pipeline → RF-1 Enhanced Format → GetReceipts Supabase
```

## Knowledge Chipper → GetReceipts Table Mapping

### 1. Claims and Episodes

**Source (Knowledge Chipper):**
```sql
-- episodes table
CREATE TABLE episodes (
  episode_id TEXT PRIMARY KEY,
  video_id TEXT UNIQUE,
  title TEXT,
  recorded_at TEXT,
  inserted_at TEXT DEFAULT (datetime('now'))
);

-- claims table  
CREATE TABLE claims (
  episode_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  canonical TEXT NOT NULL,
  claim_type TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
  tier TEXT CHECK (tier IN ('A','B','C')),
  first_mention_ts TEXT,
  scores_json TEXT NOT NULL,
  inserted_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (episode_id, claim_id)
);
```

**Target (GetReceipts Supabase):**
```sql
-- Enhanced claims table with RLS
CREATE TABLE public.claims (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  claim_text TEXT NOT NULL,
  claim_long TEXT,
  claim_type TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
  tier TEXT CHECK (tier IN ('A','B','C')),
  confidence_score REAL,
  importance_score REAL,
  novelty_score REAL,
  controversy_score REAL,
  fragility_score REAL,
  
  -- Source tracking
  source_episode_id TEXT,
  source_claim_id TEXT,
  source_app TEXT DEFAULT 'Knowledge_Chipper',
  
  -- User and access control
  user_id UUID REFERENCES auth.users(id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  -- Status and moderation
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'under_review', 'disputed', 'verified')),
  consensus_score REAL DEFAULT 0.0,
  
  -- Enhanced metadata
  knowledge_artifacts JSONB,
  provenance JSONB
);

-- Enable RLS
ALTER TABLE public.claims ENABLE ROW LEVEL SECURITY;

-- RLS Policies for claims
CREATE POLICY "Anyone can view active claims" ON public.claims 
  FOR SELECT USING (status = 'active');
  
CREATE POLICY "Authenticated users can insert claims" ON public.claims 
  FOR INSERT TO authenticated 
  WITH CHECK (auth.uid() = user_id);
  
CREATE POLICY "Users can update their own claims" ON public.claims 
  FOR UPDATE TO authenticated 
  USING (auth.uid() = user_id);
```

### 2. Sources and Milestones

**Source (Knowledge Chipper):**
```sql
-- episodes table
CREATE TABLE episodes (
  episode_id TEXT PRIMARY KEY,
  video_id TEXT UNIQUE,
  title TEXT,
  recorded_at TEXT,
  inserted_at TEXT DEFAULT (datetime('now'))
);

-- milestones table
CREATE TABLE milestones (
  episode_id TEXT NOT NULL,
  milestone_id TEXT NOT NULL,
  t0 TEXT,
  t1 TEXT,
  summary TEXT,
  PRIMARY KEY (episode_id, milestone_id)
);
```

**Target (GetReceipts Supabase):**
```sql
-- Sources for source pages (episodes = sources)
CREATE TABLE public.sources (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  source_id TEXT UNIQUE NOT NULL,
  title TEXT,
  source_type TEXT CHECK (source_type IN ('youtube', 'rss', 'document', 'audio')),
  url TEXT,
  recorded_at TIMESTAMP WITH TIME ZONE,
  duration INTEGER, -- seconds for videos
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Source milestones (chapters for videos, TOC for documents)
CREATE TABLE public.source_milestones (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  source_id UUID REFERENCES public.sources(id) ON DELETE CASCADE,
  milestone_id TEXT,
  title TEXT,
  timestamp_start TEXT, -- for videos
  timestamp_end TEXT,   -- for videos
  page_number INTEGER,  -- for documents
  page_end INTEGER,     -- for documents
  summary TEXT,
  sequence_order INTEGER,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Speakers for attribution
CREATE TABLE public.speakers (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  role TEXT,
  expertise_areas TEXT[],
  bio TEXT,
  credibility_score REAL DEFAULT 0.5,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_milestones ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.speakers ENABLE ROW LEVEL SECURITY;

-- Public access for source browsing
CREATE POLICY "Anyone can view sources" ON public.sources FOR SELECT USING (true);
CREATE POLICY "Anyone can view milestones" ON public.source_milestones FOR SELECT USING (true);
CREATE POLICY "Anyone can view speakers" ON public.speakers FOR SELECT USING (true);
```

### 3. Enhanced Evidence with Conversational Context

**Source (Knowledge Chipper):**
```sql
CREATE TABLE evidence_spans (
  episode_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  segment_id TEXT,
  t0 TEXT,
  t1 TEXT,
  quote TEXT,
  PRIMARY KEY (episode_id, claim_id, seq)
);
```

**Target (GetReceipts Supabase):**
```sql
-- Precise quotes table
CREATE TABLE public.evidence_quotes (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  claim_id UUID REFERENCES public.claims(id) ON DELETE CASCADE,
  source_id UUID REFERENCES public.sources(id),
  speaker_id UUID REFERENCES public.speakers(id),
  
  -- Precise quote content
  quote_text TEXT NOT NULL,               -- Precise verbatim quote
  evidence_type TEXT DEFAULT 'supporting' CHECK (evidence_type IN ('supporting', 'opposing')),
  
  -- Precise timestamps 
  timestamp_start TEXT,                   -- Precise quote start
  timestamp_end TEXT,                     -- Precise quote end
  youtube_link TEXT,                      -- Link to precise moment
  
  -- Metadata
  segment_id TEXT,
  confidence REAL,
  sequence_order INTEGER,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Extended context table
CREATE TABLE public.evidence_context (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  quote_id UUID REFERENCES public.evidence_quotes(id) ON DELETE CASCADE,
  
  -- Extended context content
  context_text TEXT NOT NULL,             -- Extended conversational context
  context_timestamp_start TEXT,           -- Extended context start
  context_timestamp_end TEXT,             -- Extended context end
  context_youtube_link TEXT,              -- Link to extended context
  
  -- Context detection method
  boundary_method TEXT DEFAULT 'conversational_boundary' CHECK (boundary_method IN ('conversational_boundary', 'fixed_window', 'segment_boundary')),
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.evidence_quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_context ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can view quotes for active claims" ON public.evidence_quotes 
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.claims 
      WHERE claims.id = evidence_quotes.claim_id AND claims.status = 'active'
    )
  );

CREATE POLICY "Anyone can view context for active quotes" ON public.evidence_context 
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.evidence_quotes eq 
      JOIN public.claims c ON c.id = eq.claim_id
      WHERE eq.id = evidence_context.quote_id AND c.status = 'active'
    )
  );
```

### 4. Knowledge Artifacts

**Source (Knowledge Chipper):**
```sql
-- people table
CREATE TABLE people (
  episode_id TEXT NOT NULL,
  mention_id TEXT NOT NULL,
  surface TEXT NOT NULL,
  normalized TEXT,
  entity_type TEXT CHECK (entity_type IN ('person','org')),
  external_ids_json TEXT,
  confidence REAL
);

-- concepts table (mental models)
CREATE TABLE concepts (
  episode_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  name TEXT NOT NULL,
  definition TEXT,
  aliases_json TEXT,
  evidence_json TEXT
);

-- jargon table
CREATE TABLE jargon (
  episode_id TEXT NOT NULL,
  term_id TEXT NOT NULL,
  term TEXT NOT NULL,
  category TEXT,
  definition TEXT,
  evidence_json TEXT
);
```

**Target (GetReceipts Supabase):**
```sql
-- People/Organizations (simplified name)
CREATE TABLE public.people (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  claim_id UUID REFERENCES public.claims(id) ON DELETE CASCADE,
  
  name TEXT NOT NULL,
  surface_form TEXT,
  entity_type TEXT CHECK (entity_type IN ('person', 'organization')),
  confidence REAL,
  
  -- External identifiers
  external_ids JSONB, -- {"wikipedia": "...", "wikidata": "Q..."}
  
  -- Context within claim
  timestamps TEXT,
  segment_id TEXT,
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Jargon/Technical Terms (simplified name)
CREATE TABLE public.jargon (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  claim_id UUID REFERENCES public.claims(id) ON DELETE CASCADE,
  
  term TEXT NOT NULL,
  definition TEXT,
  category TEXT,
  
  -- Usage context
  evidence_timestamps TEXT[],
  usage_examples TEXT[],
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Mental Models/Concepts (simplified name)
CREATE TABLE public.mental_models (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  claim_id UUID REFERENCES public.claims(id) ON DELETE CASCADE,
  
  name TEXT NOT NULL,
  description TEXT,
  aliases TEXT[],
  
  -- Evidence and context
  evidence_timestamps TEXT[],
  key_concepts TEXT[],
  first_mention TEXT,
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS on knowledge artifacts
ALTER TABLE public.people ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jargon ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mental_models ENABLE ROW LEVEL SECURITY;

-- RLS Policies for knowledge artifacts (inherit from parent claim)
CREATE POLICY "View people for active claims" ON public.people 
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.claims 
      WHERE claims.id = people.claim_id AND claims.status = 'active'
    )
  );

CREATE POLICY "View jargon for active claims" ON public.jargon 
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.claims 
      WHERE claims.id = jargon.claim_id AND claims.status = 'active'
    )
  );

CREATE POLICY "View mental models for active claims" ON public.mental_models 
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.claims 
      WHERE claims.id = mental_models.claim_id AND claims.status = 'active'
    )
  );
```

### 5. Claim Relationships

**Source (Knowledge Chipper):**
```sql
CREATE TABLE relations (
  episode_id TEXT NOT NULL,
  source_claim_id TEXT NOT NULL,
  target_claim_id TEXT NOT NULL,
  type TEXT CHECK (type IN ('supports','contradicts','depends_on','refines')),
  strength REAL CHECK (strength BETWEEN 0 AND 1),
  rationale TEXT
);
```

**Target (GetReceipts Supabase):**
```sql
CREATE TABLE public.claim_relationships (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  source_claim_id UUID REFERENCES public.claims(id) ON DELETE CASCADE,
  target_claim_id UUID REFERENCES public.claims(id) ON DELETE CASCADE,
  
  relationship_type TEXT CHECK (relationship_type IN ('supports', 'contradicts', 'depends_on', 'refines')),
  
  strength REAL CHECK (strength BETWEEN 0 AND 1),
  rationale TEXT,
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  UNIQUE(source_claim_id, target_claim_id, relationship_type)
);

ALTER TABLE public.claim_relationships ENABLE ROW LEVEL SECURITY;

CREATE POLICY "View claim relationships for active claims" ON public.claim_relationships 
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.claims 
      WHERE (claims.id = claim_relationships.source_claim_id OR 
             claims.id = claim_relationships.target_claim_id) 
      AND claims.status = 'active'
    )
  );

**Note**: This comes directly from Knowledge_Chipper's relations table - these are relationships detected within the same source content.
```

## Community Features (Not in Knowledge_Chipper)

**Note**: The following features would be added by GetReceipts for community interaction, but are not captured in Knowledge_Chipper:

### Claim Votes
- User voting system (credible/disputed/upvote/downvote)
- Consensus scoring algorithms
- Vote aggregation and weighting

### Claim Comments  
- Discussion threads on claims
- Threaded comment system
- User reputation tracking

### User Management
- User profiles and authentication
- Moderation capabilities
- User-generated content policies

**These would be separate GetReceipts-specific tables and features.**

## Enhanced Data Transformation Mapping

### Enhanced RF-1 Format Mapping
Your GetReceipts exporter should be updated to handle the enhanced format:

```json
{
  // ✅ EXISTING CORE FIELDS
  "claim_text": "claim.canonical",
  "claim_long": "detailed_description_with_evidence",
  "topics": ["claim.claim_type", "...extracted_topics"],
  "sources": "formatted_source_info_with_youtube_links",
  "provenance": {
    "producer_app": "Knowledge_Chipper",
    "episode_id": "pipeline_outputs.episode_id",
    "claim_id": "claim.claim_id",
    "tier": "claim.tier",
    "confidence": "claim.scores.confidence_final"
  },
  "knowledge_artifacts": {
    "people": "formatted_people_mentions",
    "jargon": "formatted_jargon_terms", 
    "mental_models": "formatted_concepts",
    "claim_relationships": "related_claims"
  },
  
  // 🆕 ENHANCED EPISODE DATA
  "episode_data": {
    "episode_id": "pipeline_outputs.episode_id",
    "title": "episode_title",
    "recorded_at": "episode_date",
    "duration": "episode_duration_seconds",
    "source_url": "youtube_url",
    "milestones": [
      {
        "milestone_id": "milestone.milestone_id",
        "title": "chapter_title",
        "timestamp_start": "milestone.t0",
        "timestamp_end": "milestone.t1",
        "summary": "milestone.summary"
      }
    ]
  },
  
  // 🆕 ENHANCED EVIDENCE WITH CONTEXT
  "supporters": [
    {
      "quote_exact": "evidence.quote",
      "quote_context": "extended_conversational_context",
      "timestamp_exact": "evidence.t0-evidence.t1",
      "timestamp_context": "extended_timestamp_range",
      "youtube_link_exact": "youtube_url&t=precise_seconds",
      "youtube_link_context": "youtube_url&t=context_start_seconds",
      "speaker": "speaker_name",
      "context_type": "conversational_boundary",
      "evidence_type": "supporting"
    }
  ]
}
```

## Security Considerations

### Row Level Security (RLS) Strategy

1. **Public Read Access**: Active claims and their knowledge artifacts are publicly readable
2. **Authenticated Write**: Only authenticated users can create/modify content
3. **Owner Control**: Users can only modify their own submissions
4. **Moderation Support**: Admin roles can moderate content status

### Database Indexes

```sql
-- Performance indexes for GetReceipts
CREATE INDEX idx_claims_status ON public.claims(status);
CREATE INDEX idx_claims_user_id ON public.claims(user_id);
CREATE INDEX idx_claims_created_at ON public.claims(created_at);
CREATE INDEX idx_claims_consensus_score ON public.claims(consensus_score);
CREATE INDEX idx_claims_episode_id ON public.claims(episode_id);

-- Episode and speaker indexes for source pages
CREATE INDEX idx_episodes_episode_id ON public.episodes(episode_id);
CREATE INDEX idx_episode_milestones_episode_id ON public.episode_milestones(episode_id);
CREATE INDEX idx_episode_milestones_sequence ON public.episode_milestones(sequence_order);
CREATE INDEX idx_speakers_name ON public.speakers(name);
CREATE INDEX idx_speakers_credibility ON public.speakers(credibility_score);

-- Enhanced evidence indexes
CREATE INDEX idx_evidence_claim_id ON public.evidence(claim_id);
CREATE INDEX idx_evidence_episode_id ON public.evidence(episode_id);
CREATE INDEX idx_evidence_speaker_id ON public.evidence(speaker_id);
CREATE INDEX idx_evidence_context_type ON public.evidence(context_type);

-- Knowledge artifact indexes
CREATE INDEX idx_knowledge_people_claim_id ON public.knowledge_people(claim_id);
CREATE INDEX idx_knowledge_jargon_claim_id ON public.knowledge_jargon(claim_id);
CREATE INDEX idx_knowledge_mental_models_claim_id ON public.knowledge_mental_models(claim_id);

-- Relationship indexes
CREATE INDEX idx_claim_relationships_source ON public.claim_relationships(source_claim_id);
CREATE INDEX idx_claim_relationships_target ON public.claim_relationships(target_claim_id);
```

## Migration Strategy

1. **Schema Creation**: Use the LLM prompt below to generate the complete schema
2. **Data Pipeline**: Your existing GetReceipts exporter handles the transformation
3. **Testing**: Validate data mapping with a small test dataset
4. **Deployment**: Apply schema to production Supabase instance

## Enhanced Features Summary

### Episode Source Pages
- **URL Pattern**: `/episodes/[episode_id]`  
- **Features**: Complete episode view with milestones, all claims, speaker attribution, timestamped navigation
- **Data Sources**: `episodes`, `episode_milestones`, `claims`, `evidence`, `speakers` tables

### Speaker Profile Pages  
- **URL Pattern**: `/speakers/[speaker_name]`
- **Features**: All claims by speaker across episodes, expertise tracking, credibility scoring
- **Data Sources**: `speakers`, `evidence`, `claims` tables with speaker attribution

### Conversational Context Evidence
- **Dual-level quotes**: Precise verbatim + extended conversational context
- **Smart boundaries**: Context detection based on topic flow, not fixed time windows
- **YouTube integration**: Both precise and contextual timestamp links

### Enhanced Search & Discovery
- **Episode-centric browsing**: Find claims within specific source conversations
- **Speaker-based filtering**: Filter claims by speaker expertise and credibility
- **Topic-based navigation**: Browse by episode milestones and discussion topics

## Implementation Notes

- Enhanced RF-1 format is **backward compatible** - existing fields preserved
- **Conversational boundary detection** requires implementing smart context extraction in Knowledge_Chipper
- **Episode source pages** transform GetReceipts from claims database to comprehensive knowledge browser
- **Speaker attribution** enables expertise-based claim weighting and credibility tracking
- Schema supports **incremental rollout** - can implement features progressively
