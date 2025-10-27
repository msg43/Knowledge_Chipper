# Metadata Architecture: Source vs. Claim

## The Two Types of Metadata

### 1. **Source Metadata** (Immutable - From Origin)
Lives in: `media_sources` table

**Where it comes from:**
- YouTube API (uploader, upload_date, view_count, categories)
- PDF extraction (author, publication date, journal)
- Article scraping (author, site, published date)
- RSS feeds (podcast info, episode date)

**Who owns it:** The content creator/platform (READ-ONLY for us)

**Examples:**
```sql
media_sources:
  - uploader: "Paul Krugman"
  - upload_date: "20241015"
  - view_count: 45000
  - duration_seconds: 3600
  - categories: ["News & Politics", "Economics"]
  - source_type: "youtube"
```

### 2. **Claim Metadata** (Mutable - Added by User/System)
Lives in: `hce_claims` table

**Where it comes from:**
- HCE extraction (tier, claim_type, scores)
- User annotations (evaluator_notes, custom tags)
- System analysis (temporality_score, upload_status)
- User edits (corrections, refinements)

**Who owns it:** Us (the knowledge system user)

**Examples:**
```sql
hce_claims:
  - tier: "A"                          # System-assigned, user-editable
  - evaluator_notes: "Needs verification"  # User-added
  - temporality_score: 4               # System-analyzed
  - custom_tags: ["monetary-policy", "urgent"]  # User-added
  - confidence_override: 0.9           # User-adjusted
```

---

## How They Work Together

### Architecture
```
CLAIM
  ├─ Claim Metadata (mutable, user-editable)
  │    ├─ tier: "A"
  │    ├─ evaluator_notes: "Check this"
  │    └─ custom_tags: ["important"]
  │
  └─ source_id → SOURCE
                   └─ Source Metadata (immutable, from platform)
                        ├─ uploader: "Paul Krugman"
                        ├─ upload_date: "20241015"
                        └─ view_count: 45000
```

**Claims don't duplicate source metadata** - they access it via JOIN.

---

## Querying: Access Both via JOIN

### Example: Find claims with both types of metadata

```sql
SELECT 
    -- Claim data (our metadata)
    c.canonical AS claim_text,
    c.tier AS our_ranking,
    c.evaluator_notes AS our_notes,
    c.temporality_score AS our_analysis,
    
    -- Source data (platform metadata)
    m.uploader AS original_author,
    m.upload_date AS original_date,
    m.view_count AS platform_popularity,
    m.title AS source_title,
    m.source_type AS where_from
    
FROM hce_claims c
JOIN media_sources m ON c.source_id = m.media_id

WHERE c.tier = 'A'  -- Filter by our metadata
  AND m.uploader = 'Paul Krugman'  -- Filter by source metadata
ORDER BY m.upload_date DESC;
```

**No duplication** - clean separation of concerns.

---

## User-Added Metadata on Claims

### Current Schema (User-Editable Fields)

```sql
CREATE TABLE hce_claims (
    claim_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    
    -- === SYSTEM-EXTRACTED (but user can edit) ===
    canonical TEXT NOT NULL,
    claim_type TEXT,  -- factual, causal, normative, etc.
    tier TEXT,  -- A, B, C (importance ranking)
    scores_json TEXT,  -- {importance, specificity, verifiability}
    
    -- === USER-ADDED METADATA ===
    evaluator_notes TEXT,  -- User comments/annotations
    temporality_score INTEGER,  -- User-adjusted if needed
    temporality_confidence REAL,
    temporality_rationale TEXT,
    
    structured_categories_json TEXT,  -- User can add/edit
    category_relevance_scores_json TEXT,
    
    -- === USER WORKFLOW TRACKING ===
    upload_status TEXT,  -- pending, uploaded, rejected
    upload_timestamp DATETIME,
    upload_error TEXT,
    
    -- === TIMESTAMPS ===
    created_at DATETIME,  -- When claim was extracted
    updated_at DATETIME,  -- When user last edited
    
    FOREIGN KEY (source_id) REFERENCES media_sources(media_id)
);
```

### Recommended: Add More User Metadata Fields

```sql
-- Add to hce_claims schema
ALTER TABLE hce_claims ADD COLUMN user_tags_json TEXT;  -- ["urgent", "controversial", "fact-check"]
ALTER TABLE hce_claims ADD COLUMN user_confidence_override REAL;  -- User can override system confidence
ALTER TABLE hce_claims ADD COLUMN user_tier_override TEXT;  -- User can override A/B/C ranking
ALTER TABLE hce_claims ADD COLUMN user_notes TEXT;  -- Separate from evaluator_notes
ALTER TABLE hce_claims ADD COLUMN flagged_for_review BOOLEAN DEFAULT 0;
ALTER TABLE hce_claims ADD COLUMN reviewed_by TEXT;  -- User who reviewed this claim
ALTER TABLE hce_claims ADD COLUMN reviewed_at DATETIME;
ALTER TABLE hce_claims ADD COLUMN verification_status TEXT;  -- unverified, verified, disputed, false
ALTER TABLE hce_claims ADD COLUMN verification_source TEXT;  -- URL/citation for verification
```

---

## Clear Distinction Table

| **Metadata Type** | **Table** | **Mutability** | **Source** | **Example Fields** |
|-------------------|-----------|----------------|------------|-------------------|
| **Source Metadata** | `media_sources` | Immutable | Platform API | `uploader`, `upload_date`, `view_count`, `duration` |
| **System Metadata** | `hce_claims` | System-set, user-viewable | HCE Pipeline | `tier`, `claim_type`, `scores_json`, `evidence` |
| **User Metadata** | `hce_claims` | User-editable | Manual input | `evaluator_notes`, `user_tags`, `verification_status` |

---

## Example Scenarios

### Scenario 1: User Reviews a Claim

**Initial state (system-extracted):**
```python
claim = {
    'claim_id': 'claim_abc123',
    'source_id': 'video_xyz',
    'canonical': 'The Fed raised rates by 25 basis points',
    'tier': 'B',  # System assigned
    'claim_type': 'factual',
    'evaluator_notes': None,  # Empty
    'user_confidence_override': None,
}

# Source metadata (from YouTube)
source = {
    'media_id': 'video_xyz',
    'uploader': 'CNBC',
    'upload_date': '20241015',
    'view_count': 120000,
}
```

**User reviews and adds metadata:**
```python
# User updates claim
claim.update({
    'tier': 'A',  # User upgrades importance
    'evaluator_notes': 'Confirmed by Fed press release',
    'user_tags_json': ['monetary-policy', 'verified'],
    'verification_status': 'verified',
    'verification_source': 'https://federalreserve.gov/press-release/2024-10-15',
    'reviewed_by': 'matthew',
    'reviewed_at': '2024-10-16T10:30:00',
})

# Source metadata NEVER changes (it's from YouTube)
# source.view_count might update if we re-fetch, but that's automatic
```

### Scenario 2: Comparing Claims Across Sources

**Query: Find all claims about "inflation" with author credibility context**

```sql
SELECT 
    c.canonical,
    c.tier AS our_importance_rating,
    c.verification_status AS our_verification,
    c.user_tags_json AS our_tags,
    
    -- Author credibility from source
    m.uploader AS author,
    m.view_count AS reach,
    m.upload_date AS published_when,
    m.source_type AS medium
    
FROM hce_claims c
JOIN media_sources m ON c.source_id = m.media_id

WHERE c.canonical LIKE '%inflation%'
  AND c.tier IN ('A', 'B')
  AND c.verification_status = 'verified'
  
ORDER BY m.upload_date DESC;
```

**Result:**
```
canonical                        | our_importance | our_verification | author           | reach  | published  | medium
-------------------------------- | -------------- | ---------------- | ---------------- | ------ | ---------- | -------
"CPI rose 3.2% year-over-year"  | A              | verified         | Paul Krugman     | 85000  | 2024-10-15 | youtube
"Inflation expectations rising" | B              | disputed         | Random Podcast   | 1200   | 2024-10-14 | youtube
"Fed targets 2% inflation"      | A              | verified         | Jerome Powell    | 250000 | 2024-10-10 | youtube
```

**Distinction is clear:**
- `tier`, `verification_status` = **OUR metadata** (user/system)
- `author`, `reach`, `published` = **SOURCE metadata** (platform)

---

## Proposed Enhanced Schema

### Add User Metadata Columns to Claims

```sql
CREATE TABLE hce_claims (
    -- === IDENTIFIERS ===
    claim_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    
    -- === EXTRACTED CONTENT (system, but user can edit) ===
    canonical TEXT NOT NULL,
    original_text TEXT,
    claim_type TEXT,
    tier TEXT,
    scores_json TEXT,
    
    -- === EVIDENCE (system-extracted) ===
    evidence_spans JSON,  -- Links to hce_evidence_spans table
    first_mention_ts TEXT,
    
    -- === SYSTEM ANALYSIS (auto-generated) ===
    temporality_score INTEGER,
    temporality_confidence REAL,
    temporality_rationale TEXT,
    structured_categories_json TEXT,
    
    -- === USER METADATA (manually added/edited) ===
    evaluator_notes TEXT,                    -- User comments
    user_tags_json TEXT,                     -- ["urgent", "fact-check"]
    user_tier_override TEXT,                 -- Override system tier
    user_confidence_override REAL,           -- Override system confidence
    
    -- === VERIFICATION WORKFLOW ===
    verification_status TEXT,                -- unverified, verified, disputed, false
    verification_source TEXT,                -- URL or citation
    verification_notes TEXT,                 -- Why verified/disputed
    flagged_for_review BOOLEAN DEFAULT 0,
    reviewed_by TEXT,                        -- User who reviewed
    reviewed_at DATETIME,
    
    -- === UPLOAD/EXPORT TRACKING ===
    upload_status TEXT DEFAULT 'pending',
    upload_timestamp DATETIME,
    upload_error TEXT,
    exported_to_json TEXT,                   -- ["getreceipts", "obsidian"]
    
    -- === TIMESTAMPS ===
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),
    
    FOREIGN KEY (source_id) REFERENCES media_sources(media_id) ON DELETE CASCADE
);
```

### Keep Source Metadata Clean

```sql
CREATE TABLE media_sources (
    -- === IDENTIFIERS ===
    media_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,  -- youtube, pdf, article, rss
    
    -- === BASIC METADATA (from source) ===
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    
    -- === AUTHOR INFO (from source) ===
    uploader TEXT,              -- YouTube/podcast creator
    uploader_id TEXT,           -- YouTube channel ID
    author TEXT,                -- For PDFs/articles
    organization TEXT,          -- Publishing organization
    
    -- === TEMPORAL INFO (from source) ===
    upload_date TEXT,           -- YYYYMMDD
    recorded_at TEXT,           -- For podcasts/videos
    published_at TEXT,          -- For articles/papers
    
    -- === PLATFORM METRICS (from source) ===
    duration_seconds INTEGER,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER,
    
    -- === CATEGORIZATION (from source) ===
    categories_json TEXT,       -- Platform categories
    tags_json TEXT,             -- Platform tags
    
    -- === TECHNICAL (from source) ===
    privacy_status TEXT,
    caption_availability BOOLEAN,
    language TEXT,
    
    -- === LOCAL STORAGE ===
    thumbnail_url TEXT,
    thumbnail_local_path TEXT,
    audio_file_path TEXT,
    
    -- === TIMESTAMPS ===
    created_at DATETIME DEFAULT (datetime('now')),
    fetched_at DATETIME,        -- Last time we pulled from platform
    
    -- NO user-editable metadata here - it's all from the source
);
```

---

## User Interface Implications

### Claim Detail View

```
┌─────────────────────────────────────────────┐
│ CLAIM DETAIL                                │
├─────────────────────────────────────────────┤
│                                             │
│ "The Fed raised rates by 25 basis points"  │
│                                             │
│ ┌─ CLAIM METADATA (Editable) ─────────────┐│
│ │ Tier: [A] ▼          Type: [Factual] ▼ ││
│ │ Your Tags: monetary-policy, verified    ││
│ │ Verification: [✓ Verified]              ││
│ │ Verified By: Fed Press Release →        ││
│ │ Notes: [Confirmed by official source]   ││
│ │ Reviewed By: matthew (2024-10-16)       ││
│ └─────────────────────────────────────────┘│
│                                             │
│ ┌─ SOURCE METADATA (Read-Only) ───────────┐│
│ │ 📺 From: CNBC                           ││
│ │ 📅 Published: Oct 15, 2024              ││
│ │ 👁 Views: 120,000                       ││
│ │ ⏱ Duration: 12:34                       ││
│ │ 🔗 https://youtube.com/watch?v=...      ││
│ └─────────────────────────────────────────┘│
│                                             │
│ [Save Changes] [Flag for Review] [Export]  │
└─────────────────────────────────────────────┘
```

---

## API/Code Examples

### Fetching Claim with Full Context

```python
def get_claim_with_context(claim_id: str) -> dict:
    """Get claim with both claim metadata and source metadata."""
    with db.get_session() as session:
        result = session.execute("""
            SELECT 
                -- Claim data (mutable)
                c.claim_id,
                c.canonical,
                c.tier,
                c.claim_type,
                c.evaluator_notes,
                c.user_tags_json,
                c.verification_status,
                c.verification_source,
                
                -- Source data (immutable)
                m.media_id AS source_id,
                m.title AS source_title,
                m.uploader AS author,
                m.upload_date,
                m.view_count,
                m.duration_seconds,
                m.source_type,
                m.url AS source_url
                
            FROM hce_claims c
            JOIN media_sources m ON c.source_id = m.media_id
            WHERE c.claim_id = :claim_id
        """, {"claim_id": claim_id}).first()
        
        return {
            'claim': {
                'id': result.claim_id,
                'text': result.canonical,
                'tier': result.tier,
                'type': result.claim_type,
                'notes': result.evaluator_notes,
                'tags': json.loads(result.user_tags_json or '[]'),
                'verification': result.verification_status,
            },
            'source': {
                'id': result.source_id,
                'title': result.source_title,
                'author': result.author,
                'date': result.upload_date,
                'views': result.view_count,
                'duration': result.duration_seconds,
                'type': result.source_type,
                'url': result.source_url,
            }
        }
```

### Updating Claim Metadata (User Edits)

```python
def update_claim_metadata(claim_id: str, updates: dict) -> None:
    """Update user-editable claim metadata only."""
    allowed_fields = {
        'tier', 'evaluator_notes', 'user_tags_json', 
        'verification_status', 'verification_source',
        'verification_notes', 'user_tier_override',
    }
    
    # Filter to only allowed fields
    safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
    safe_updates['updated_at'] = datetime.utcnow()
    
    with db.get_session() as session:
        session.execute(
            update(HCEClaim)
            .where(HCEClaim.claim_id == claim_id)
            .values(**safe_updates)
        )
        session.commit()
    
    # Source metadata NEVER updated through this function
```

---

## Summary

### Clear Separation

| Aspect | Source Metadata | Claim Metadata |
|--------|----------------|----------------|
| **Lives in** | `media_sources` | `hce_claims` |
| **Set by** | Platform API | User + System |
| **Mutability** | Immutable (from source) | Mutable (user edits) |
| **Examples** | uploader, view_count, upload_date | tier, notes, verification_status |
| **Access** | Via JOIN on `source_id` | Direct query |
| **Purpose** | Attribution & context | Knowledge management |

### No Duplication

Claims **reference** source metadata via `source_id`, they don't **copy** it.

### User Can Add

- Tags
- Notes
- Verification status
- Tier overrides
- Review flags
- Custom confidence scores

### User CANNOT Change

- Uploader name
- Upload date
- View count
- Source URL

---

This architecture gives you:
✅ **Clean separation** - source vs. claim metadata  
✅ **No duplication** - claims reference, don't copy  
✅ **User control** - full editing of claim metadata  
✅ **Platform integrity** - source metadata stays true to origin  
✅ **Rich context** - JOIN gives you both in one query  

Ready to implement this structure!


