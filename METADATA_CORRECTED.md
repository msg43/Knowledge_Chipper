# Metadata Architecture (CORRECTED)

## There Are Only TWO Types of Metadata

### 1. **Platform Metadata** (From the Source)
- **Examples:** YouTube categories ("News & Politics"), YouTube tags, uploader, view count
- **WikiData enforced?** ❌ NO - we accept whatever the platform gives us
- **Tables:** `platform_categories`, `source_platform_categories`, `media_sources`
- **Mutability:** Immutable (it's what the platform said)

### 2. **Our Metadata** (Our Analysis + User Curation)
- **Examples:** Tier ranking, WikiData categories, verification status, user notes
- **WikiData enforced?** ✅ YES - for categories only
- **Tables:** `claims`, `claim_categories`, `source_categories`
- **Mutability:** User-editable

---

## The Confusion I Created

### ❌ WRONG: "Three Types of Metadata"

I incorrectly said:
1. Source Metadata (WHO/WHEN/WHERE)
2. Claim Metadata (YOUR ANALYSIS)
3. **Semantic Metadata** (WHAT IT'S ABOUT) ← This was confusing!

**The problem:** "Semantic metadata" made it sound like a separate layer.

### ✅ CORRECT: "Two Types of Metadata"

**Platform Metadata:**
- Everything FROM the platform (YouTube, PDF metadata, etc.)
- Includes platform's categories ("News & Politics")
- NO WikiData enforcement

**Our Metadata:**
- Everything WE add through analysis or curation
- Includes:
  - **Categorization** (WikiData enforced) at source AND claim level
  - **Curation** (tier, verification, notes)
  - **User tags** (custom tags, not WikiData)
  - **Workflow** (reviewed_by, flagged_for_review)

---

## Categories: Platform vs. WikiData

### Platform Categories (NOT WikiData)

**From:** YouTube, iTunes, Spotify, etc.  
**Storage:** `platform_categories` + `source_platform_categories`  
**Enforcement:** NONE - accept as-is

```sql
-- Platform categories (uncontrolled)
CREATE TABLE platform_categories (
    category_id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,           -- 'youtube', 'itunes'
    category_name TEXT NOT NULL       -- Whatever platform says
);

-- Link to sources
CREATE TABLE source_platform_categories (
    source_id TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id),
    FOREIGN KEY (category_id) REFERENCES platform_categories(category_id)
);
```

**Example:**
```
YouTube video has categories: ["News & Politics", "Education"]
→ Store in platform_categories as-is
→ NO WikiData mapping
→ NO enforcement
```

### Our Categories (WikiData Enforced)

**From:** Our HCE analysis  
**Storage:** `source_categories` + `claim_categories`  
**Enforcement:** WikiData controlled vocabulary

```sql
-- Our categorization (WikiData only)
CREATE TABLE source_categories (
    source_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,        -- MUST be in wikidata_categories
    rank INTEGER CHECK (rank BETWEEN 1 AND 3),
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id),
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)  -- ENFORCED
);

CREATE TABLE claim_categories (
    claim_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,        -- MUST be in wikidata_categories
    is_primary BOOLEAN,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)  -- ENFORCED
);
```

**Example:**
```
Same YouTube video analyzed by our system:
→ Source categories: ["Economics" (Q8134), "Monetary policy" (Q186363)]
→ WikiData enforced
→ Two-stage pipeline (free-form LLM → embedding matching)
```

---

## Complete Picture for a Source

```json
{
  "source": {
    "source_id": "video_abc123",
    "title": "Fed Meeting Coverage",
    "uploader": "CNBC",
    "upload_date": "2024-10-15",
    
    // === PLATFORM CATEGORIES (NOT WikiData) ===
    "platform_categories": [
      "News & Politics",      // YouTube said this
      "Education"             // YouTube said this
    ],
    
    // === OUR CATEGORIES (WikiData enforced) ===
    "our_categories": [
      {
        "wikidata_id": "Q24885",
        "category_name": "Finance",
        "rank": 1,
        "source": "system"    // Our HCE analysis
      },
      {
        "wikidata_id": "Q186363",
        "category_name": "Monetary policy",
        "rank": 2,
        "source": "system"
      }
    ]
  },
  
  "claims": [
    {
      "canonical": "Fed raised rates 25bps",
      
      // === OUR METADATA ===
      "tier": "A",
      "verification_status": "verified",
      "evaluator_notes": "Confirmed",
      
      // === OUR CATEGORY (WikiData enforced) ===
      "category": {
        "wikidata_id": "Q186363",
        "category_name": "Monetary policy",
        "is_primary": true
      }
    }
  ]
}
```

---

## Why NO "Semantic Metadata" Category?

### The Question: "Why do we need a semantic metadata category?"

**Answer: We don't!** There are only two types:

1. **Platform metadata** - What the platform tells us
2. **Our metadata** - What we determine/curate

**Categories are part of "our metadata"** - they're just WikiData-constrained.

### Corrected Categorization

**WRONG:**
```
1. Source Metadata (platform)
2. Claim Metadata (our analysis)
3. Semantic Metadata (categories) ← Unnecessary third category
```

**RIGHT:**
```
1. Platform Metadata
   - uploader, upload_date, view_count
   - Platform categories ("News & Politics")
   - Platform tags
   
2. Our Metadata
   - Curation: tier, verification_status, notes
   - Categories: WikiData-enforced (source + claim level)
   - User tags: custom tags
   - Workflow: reviewed_by, flagged_for_review
```

**Categories are just one PART of "our metadata"** - they're not a separate type.

---

## Corrected Table Organization

### Platform Metadata Tables
```
media_sources              # Platform gave us: uploader, upload_date, etc.
platform_categories        # Platform gave us: "News & Politics"
source_platform_categories # Link: source → platform categories
platform_tags             # Platform gave us: "finance", "fed"
source_platform_tags      # Link: source → platform tags
```

**NO WikiData enforcement** - accept as-is from platform.

### Our Metadata Tables
```
claims                    # Our extraction + curation
  ├─ tier, verification_status, evaluator_notes  (curation)
  ├─ importance_score, specificity_score         (system analysis)
  └─ flagged_for_review, reviewed_by             (workflow)

wikidata_categories      # Our controlled vocabulary
source_categories        # Our categorization of sources (WikiData)
claim_categories         # Our categorization of claims (WikiData)
user_tags                # Our custom tags (NOT WikiData)
claim_tags              # Link: claims → user tags
```

**WikiData enforced ONLY for `source_categories` and `claim_categories`.**

---

## Summary

### Two-Part Answer

**Q1: "Why do we need a semantic metadata category?"**

**A:** We don't! There are only TWO types:
- Platform metadata (from source)
- Our metadata (our analysis)

Categories are PART of "our metadata," not a separate type.

**Q2: "Are you saying source categories are WikiData enforced?"**

**A:** YES - but only **OUR source categories** (`source_categories` table), NOT platform categories:

- `platform_categories` (from YouTube) → ❌ NOT WikiData enforced
- `source_categories` (our analysis) → ✅ WikiData enforced

**Two separate category systems:**
1. Platform's categories (what YouTube said)
2. Our categories (what we analyzed using WikiData)

Both can exist on the same source!

---

## Corrected Schema

```sql
-- Platform's categories (NOT WikiData)
CREATE TABLE platform_categories (
    platform TEXT,
    category_name TEXT  -- "News & Politics", "Education"
);

CREATE TABLE source_platform_categories (
    source_id TEXT,
    category_id INTEGER,  -- FK to platform_categories (NOT WikiData)
);

-- Our categories (WikiData enforced)
CREATE TABLE wikidata_categories (
    wikidata_id TEXT PRIMARY KEY,     -- "Q186363"
    category_name TEXT                 -- "Monetary policy"
);

CREATE TABLE source_categories (
    source_id TEXT,
    wikidata_id TEXT,                  -- FK to wikidata_categories (ENFORCED)
    rank INTEGER,
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);

CREATE TABLE claim_categories (
    claim_id TEXT,
    wikidata_id TEXT,                  -- FK to wikidata_categories (ENFORCED)
    is_primary BOOLEAN,
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);
```

Is this the correct understanding now?

