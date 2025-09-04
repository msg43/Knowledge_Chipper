# LLM Prompt for GetReceipts Supabase Schema Generation

## Prompt for AI Assistant

Use this prompt with any LLM to generate the complete GetReceipts Supabase database schema with proper RLS policies:

---

**SYSTEM PROMPT:**

You are a PostgreSQL database expert specializing in Supabase Row Level Security (RLS) implementations. Generate a complete database schema for the GetReceipts platform that receives enhanced RF-1 formatted claims data from Knowledge_Chipper.

**TASK:**

Create SQL statements to build a complete Supabase database schema that receives RF-1 JSON from Knowledge_Chipper's `/api/receipts` endpoint and stores it in properly normalized relational tables (NOT as JSON storage).

### CORE REQUIREMENTS

1. **RF-1 JSON Parsing**: Parse incoming JSON transport format into relational tables
2. **Normalized Storage**: Proper foreign key relationships, no data duplication
3. **Row Level Security**: Proper RLS policies for public access with authenticated modifications  
4. **Knowledge Artifacts**: Structured relational storage for people, jargon, and mental models
5. **Community Features**: Voting, commenting, and consensus tracking
6. **Data Provenance**: Full traceability back to Knowledge_Chipper sources
7. **Query Performance**: Proper indexes for efficient searches and analytics

### TABLE SPECIFICATIONS

#### 1. Claims Table (public.claims)
**Purpose**: Store factual claims with metadata and scoring
**Columns**:
- `id`: UUID, Primary Key, Default: gen_random_uuid()
- `slug`: TEXT, Unique, Not Null (for URL-friendly access)
- `claim_text`: TEXT, Not Null (main claim statement)
- `claim_long`: TEXT (detailed description with evidence)
- `claim_type`: TEXT, Check constraint for ('factual','causal','normative','forecast','definition')
- `tier`: TEXT, Check constraint for ('A','B','C')
- `confidence_score`: REAL (0.0-1.0)
- `importance_score`: REAL (0.0-1.0)
- `novelty_score`: REAL (0.0-1.0)
- `controversy_score`: REAL (0.0-1.0)
- `fragility_score`: REAL (0.0-1.0)

**Temporality Analysis (New):**
- `temporality_score`: INTEGER, Check constraint IN (1,2,3,4,5), Default 3
  - 1=Immediate (days), 2=Short-term (weeks-months), 3=Medium-term (1-10 years), 4=Long-term (10+ years), 5=Timeless (universal)
- `temporality_confidence`: REAL, Check constraint BETWEEN 0 AND 1, Default 0.5
- `temporality_rationale`: TEXT (explanation for temporality classification)

**Structured Categories (New):**
- `structured_categories`: TEXT[] (array of Wikidata-style category names this claim belongs to)
- `category_relevance_scores`: JSONB (mapping of category names to relevance scores 0.0-1.0)

**Metadata:**
- `source_episode_id`: TEXT (Knowledge_Chipper episode reference)
- `source_claim_id`: TEXT (Knowledge_Chipper claim reference)
- `source_app`: TEXT, Default 'Knowledge_Chipper'
- `user_id`: UUID, References auth.users(id)
- `created_at`: TIMESTAMP WITH TIME ZONE, Default NOW()
- `updated_at`: TIMESTAMP WITH TIME ZONE, Default NOW()
- `status`: TEXT, Default 'active', Check constraint for ('active', 'under_review', 'disputed', 'verified')
- `consensus_score`: REAL, Default 0.0
- `raw_rf1_json`: JSONB (original RF-1 for reference/debugging only)
- `hce_tier`: TEXT (from Knowledge_Chipper tier)
- `hce_confidence`: REAL (from Knowledge_Chipper confidence)
- `hce_importance`: REAL (from Knowledge_Chipper importance)
- `hce_novelty`: REAL (from Knowledge_Chipper novelty)
- `hce_controversy`: REAL (from Knowledge_Chipper controversy)
- `hce_fragility`: REAL (from Knowledge_Chipper fragility)

**RLS Policies**:
- Public SELECT for active claims only
- Authenticated INSERT with user ownership
- Users can UPDATE their own claims only
- Admins can UPDATE any claim status

#### 2. Sources Table (public.sources)
**Purpose**: Store source information for source pages (episodes/documents)
**Columns**:
- `id`: UUID, Primary Key, Default: gen_random_uuid()
- `source_id`: TEXT, Unique, Not Null (from RF-1 episode_data.episode_id)
- `title`: TEXT (from RF-1 episode_data.title)
- `source_type`: TEXT, Check constraint for ('youtube', 'rss', 'document', 'audio')
- `url`: TEXT (YouTube/RSS/document URL)
- `recorded_at`: TIMESTAMP WITH TIME ZONE (from RF-1 episode_data.recorded_at)
- `duration`: INTEGER (seconds, from RF-1 episode_data.duration)
- `created_at`: TIMESTAMP WITH TIME ZONE, Default NOW()

#### 3. Source Milestones Table (public.source_milestones)
**Purpose**: Store chapters/table of contents (parsed from RF-1 episode_data.milestones)
**Columns**:
- `id`: UUID, Primary Key, Default: gen_random_uuid()
- `source_id`: UUID, References public.sources(id), ON DELETE CASCADE
- `milestone_id`: TEXT (from RF-1 milestone_id)
- `title`: TEXT (chapter title or TOC entry)
- `timestamp_start`: TEXT (for videos) or `page_number`: INTEGER (for documents)
- `timestamp_end`: TEXT (for videos) or `page_end`: INTEGER (for documents)
- `summary`: TEXT (from RF-1 summary)
- `sequence_order`: INTEGER
- `created_at`: TIMESTAMP WITH TIME ZONE, Default NOW()

#### 4. Speakers Table (public.speakers)
**Purpose**: Store speaker information for attribution and expertise tracking
**Columns**:
- `id`: UUID, Primary Key, Default: gen_random_uuid()
- `name`: TEXT, Unique, Not Null
- `role`: TEXT (host, guest, expert, etc.)
- `expertise_areas`: TEXT[] (array of expertise domains)
- `bio`: TEXT
- `credibility_score`: REAL, Default 0.5
- `created_at`: TIMESTAMP WITH TIME ZONE, Default NOW()

#### 5. Evidence Table (public.evidence)
**Purpose**: Store evidence with dual-level context (parsed from RF-1 supporters/opponents arrays)
**Columns**:
- `id`: UUID, Primary Key, Default: gen_random_uuid()
- `claim_id`: UUID, References public.claims(id), ON DELETE CASCADE
- `source_id`: UUID, References public.sources(id)
- `speaker_id`: UUID, References public.speakers(id)
- `evidence_type`: TEXT, Default 'supporting', Check constraint for ('supporting', 'opposing')

**Precise Quote Level:**
- `quote_text`: TEXT, Not Null (precise verbatim quote)
- `timestamp_start`: TEXT (precise quote start)
- `timestamp_end`: TEXT (precise quote end)
- `youtube_link`: TEXT (direct link to precise quote moment)

**Extended Context Level:**
- `context_text`: TEXT (extended conversational context around quote)
- `context_timestamp_start`: TEXT (extended context start)
- `context_timestamp_end`: TEXT (extended context end)
- `context_youtube_link`: TEXT (link to extended context)
- `context_type`: TEXT, Default 'conversational_boundary', Check constraint for ('exact', 'conversational_boundary', 'fixed_window', 'segment')

**Metadata:**
- `segment_id`: TEXT
- `sequence_order`: INTEGER
- `created_at`: TIMESTAMP WITH TIME ZONE, Default NOW()

**RLS Policies**:
- Public SELECT for evidence of active claims
- Evidence inherits access from parent claim

#### 6. People Table (public.people)
**Purpose**: Store person/organization mentions (parsed from RF-1 knowledge_artifacts.people array)
**Columns**:
- `id`: UUID, Primary Key, Default: gen_random_uuid()
- `claim_id`: UUID, References public.claims(id), ON DELETE CASCADE
- `name`: TEXT, Not Null (from RF-1 name field)
- `surface_form`: TEXT (from RF-1 surface_form field)
- `entity_type`: TEXT, Check constraint for ('person', 'organization')
- `confidence`: REAL (from RF-1 confidence field)
- `external_ids`: JSONB (from RF-1 external_ids - minimal JSON for IDs only)
- `timestamps`: TEXT (from RF-1 timestamps field)
- `segment_id`: TEXT (from RF-1 segment_id field)
- `created_at`: TIMESTAMP WITH TIME ZONE, Default NOW()

#### 7. Jargon Table (public.jargon)
**Purpose**: Store technical terms and definitions (parsed from RF-1 knowledge_artifacts.jargon array)
**Columns**:
- `id`: UUID, Primary Key, Default: gen_random_uuid()
- `claim_id`: UUID, References public.claims(id), ON DELETE CASCADE
- `term`: TEXT, Not Null (from RF-1 term field)
- `definition`: TEXT (from RF-1 definition field)
- `category`: TEXT (from RF-1 category field)
- `evidence_timestamps`: TEXT[] (from RF-1 evidence_timestamps array)
- `usage_examples`: TEXT[] (from RF-1 usage_examples array)
- `created_at`: TIMESTAMP WITH TIME ZONE, Default NOW()

#### 8. Mental Models Table (public.mental_models)  
**Purpose**: Store conceptual frameworks and mental models (parsed from RF-1 knowledge_artifacts.mental_models array)
**Columns**:
- `id`: UUID, Primary Key, Default: gen_random_uuid()
- `claim_id`: UUID, References public.claims(id), ON DELETE CASCADE
- `name`: TEXT, Not Null (from RF-1 name field)
- `description`: TEXT (from RF-1 description field)
- `aliases`: TEXT[] (from RF-1 aliases array)
- `evidence_timestamps`: TEXT[] (from RF-1 evidence_timestamps array)
- `key_concepts`: TEXT[] (from RF-1 key_concepts array)
- `first_mention`: TEXT (from RF-1 first_mention field)
- `created_at`: TIMESTAMP WITH TIME ZONE, Default NOW()

**RLS Policies**:
- Public SELECT for knowledge artifacts of active claims

**Note**: The following features are GetReceipts community additions, not captured in Knowledge_Chipper:

#### 9. Claim Relationships Table (public.claim_relationships) - OPTIONAL
**Purpose**: Store relationships between claims (currently disabled in Knowledge_Chipper due to implementation issues)
**Status**: ⚠️ **NOT CURRENTLY POPULATED** - Relations extraction is disabled pending prompt template creation
**Columns**:
- `id`: UUID, Primary Key, Default: gen_random_uuid()
- `source_claim_id`: UUID, References public.claims(id), ON DELETE CASCADE
- `target_claim_id`: UUID, References public.claims(id), ON DELETE CASCADE
- `relationship_type`: TEXT, Check constraint for ('supports', 'contradicts', 'depends_on', 'refines')
- `strength`: REAL, Check constraint BETWEEN 0 AND 1
- `rationale`: TEXT
- `created_at`: TIMESTAMP WITH TIME ZONE, Default NOW()

#### Community Features (GetReceipts-specific)
**Note**: Claim votes and comments are GetReceipts community features, not captured in Knowledge_Chipper. These would be added separately by GetReceipts for user interaction.

### PERFORMANCE REQUIREMENTS

Create these indexes for optimal performance:
- Claims: status, user_id, created_at, consensus_score, source_id, temporality_score, structured_categories
- Sources: source_id, source_type, created_at
- Source Milestones: source_id, sequence_order
- Speakers: name, credibility_score
- Evidence: claim_id, source_id, speaker_id, context_type
- Knowledge tables: claim_id (for people, jargon, mental_models)
- Structured Categories: episode_id, category_name, coverage_confidence
- Relationships: source_claim_id, target_claim_id (if implemented)

### SECURITY REQUIREMENTS

1. **Enable RLS on all tables**
2. **Public read access** for active content
3. **Authenticated write access** with ownership validation
4. **Admin override capabilities** for moderation
5. **Cascade deletes** to maintain referential integrity

### RF-1 JSON PARSING LOGIC

The `/api/receipts` endpoint must parse incoming RF-1 JSON and populate these tables:

1. **Parse source data**: Insert/upsert into `sources` table
2. **Parse source milestones**: Insert each milestone into `source_milestones` table
3. **Parse speakers**: Insert/upsert speakers into `speakers` table
4. **Parse main claim**: Insert into `claims` table with core RF-1 fields, temporality analysis, categories, and source reference
5. **Parse supporters/opponents arrays**: Insert evidence with dual-level context into `evidence` table
6. **Parse knowledge_artifacts.people array**: Insert each into `people` table
7. **Parse knowledge_artifacts.jargon array**: Insert each into `jargon` table
8. **Parse knowledge_artifacts.mental_models array**: Insert each into `mental_models` table
9. **Parse claim relationships**: Insert each into `claim_relationships` table (⚠️ Currently disabled - will be empty)
10. **Store raw RF-1 JSON**: Keep original in `raw_rf1_json` field for debugging

### ADDITIONAL FEATURES

1. **RF-1 parsing endpoint**: `/api/receipts` that accepts Knowledge_Chipper RF-1 JSON with source data
2. **Source pages**: `/sources/[source_id]` showing all claims, milestones, and speakers for a source
3. **Speaker profile pages**: `/speakers/[speaker_name]` showing all claims by a specific speaker
4. **Dual-level evidence**: Both precise quotes and extended conversational context using smart boundary detection
5. **Temporality scoring**: 1-5 scale for knowledge longevity assessment (1=Immediate, 5=Timeless)
6. **Structured categories**: Wikidata-style topic classification at both episode and claim levels
7. **Category-based search**: Find claims by semantic categories with relevance scoring
8. **Updated timestamp triggers** for claims
9. **Full-text search indexes** for claims, evidence, people, jargon, sources, categories
10. **Unique constraint handling**: Prevent duplicate claims from same Knowledge_Chipper source

**Community Features** (to be added separately by GetReceipts):
- User voting system (claim_votes table)
- Comment threads (claim_comments table) 
- Consensus scoring algorithms

### ENHANCED QUERY CAPABILITIES

The new temporality and category fields enable powerful queries:

**Knowledge Longevity Queries:**
- `SELECT * FROM claims WHERE temporality_score = 5 ORDER BY importance_score DESC` (Find timeless insights)
- `SELECT * FROM claims WHERE temporality_score <= 2 AND created_at > NOW() - INTERVAL '30 days'` (Recent short-term claims)

**Category-Based Discovery:**
- `SELECT * FROM claims WHERE 'Artificial Intelligence' = ANY(structured_categories)` (All AI claims)
- `SELECT * FROM claims WHERE array_length(structured_categories, 1) > 2` (Multi-domain claims)
- `SELECT category_relevance_scores->'Economics' as econ_score FROM claims WHERE 'Economics' = ANY(structured_categories)` (Economics relevance)

**Combined Semantic Searches:**
- Find timeless AI claims: `temporality_score = 5 AND 'Artificial Intelligence' = ANY(structured_categories)`
- Find emerging tech trends: `temporality_score = 4 AND 'Technology' = ANY(structured_categories) AND created_at > NOW() - INTERVAL '6 months'`

### OUTPUT FORMAT

Generate the complete SQL schema as a single file that can be executed on a fresh Supabase instance. Include:

1. All CREATE TABLE statements with constraints
2. All RLS policy definitions  
3. All performance indexes
4. Any necessary functions or triggers
5. Comments explaining the purpose of each component

**CRITICAL**: Ensure all foreign key relationships are properly defined and that RLS policies allow the intended access patterns while maintaining security.

---

**Execute this schema generation for the GetReceipts platform supporting enhanced RF-1 data from Knowledge_Chipper.**
