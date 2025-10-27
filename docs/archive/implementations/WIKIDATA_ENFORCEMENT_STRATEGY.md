# WikiData Category Enforcement Strategy

## The Challenge

We want LLMs to categorize content using **standardized WikiData categories**, NOT hallucinated/invented categories.

**Problem:** LLMs will invent categories like:
- "Monetary policies" (should be "Monetary policy")
- "Fed stuff" (should be "Federal Reserve System")
- "Economics and finance" (should be separate: "Economics" OR "Finance")

**Solution:** Constrain LLM to choose from a **curated WikiData vocabulary**.

---

## Two Types of Categories (Different Enforcement)

### 1. **Platform Categories** (NO WikiData Enforcement)

**Source:** YouTube, PDF metadata, RSS feeds, etc.  
**Storage:** Separate tables (`youtube_categories`, `youtube_tags`, etc.)  
**Enforcement:** NONE - we accept whatever the platform gives us

```sql
-- Platform categories (as-is from YouTube/etc.)
CREATE TABLE platform_categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,           -- 'youtube', 'itunes', 'spotify'
    category_name TEXT NOT NULL,
    UNIQUE(platform, category_name)
);

CREATE TABLE source_platform_categories (
    source_id TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (source_id, category_id),
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id),
    FOREIGN KEY (category_id) REFERENCES platform_categories(category_id)
);
```

**Example:**
```
YouTube video has categories: ["News & Politics", "Education"]
  → Store as-is in platform_categories
  → Link to source in source_platform_categories
  → NO WikiData mapping required
```

### 2. **Semantic Categories** (WikiData ENFORCED)

**Source:** Our HCE pipeline (LLM analysis)  
**Storage:** `source_categories`, `claim_categories`  
**Enforcement:** LLM MUST choose from curated WikiData list

```sql
-- Our curated WikiData vocabulary
CREATE TABLE wikidata_categories (
    wikidata_id TEXT PRIMARY KEY,          -- "Q186363"
    category_name TEXT NOT NULL UNIQUE,    -- "Monetary policy"
    category_description TEXT,
    parent_wikidata_id TEXT,
    level TEXT,                            -- 'general' or 'specific'
    FOREIGN KEY (parent_wikidata_id) REFERENCES wikidata_categories(wikidata_id)
);

-- Source categories (WikiData ONLY)
CREATE TABLE source_categories (
    source_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,             -- MUST be in wikidata_categories
    rank INTEGER CHECK (rank BETWEEN 1 AND 3),
    relevance_score REAL,
    PRIMARY KEY (source_id, wikidata_id),
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id),
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)  -- ENFORCED
);

-- Claim categories (WikiData ONLY)
CREATE TABLE claim_categories (
    claim_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,             -- MUST be in wikidata_categories
    is_primary BOOLEAN DEFAULT 0,
    relevance_score REAL,
    PRIMARY KEY (claim_id, wikidata_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)  -- ENFORCED
);
```

---

## WikiData Enforcement Mechanisms

### Step 1: Curate the Vocabulary

**Manually select ~100-200 WikiData categories** across common domains:

```sql
-- Pre-populate with curated categories
INSERT INTO wikidata_categories (wikidata_id, category_name, level, category_description) VALUES
-- General categories
('Q8134', 'Economics', 'general', 'Social science studying production, distribution, and consumption'),
('Q7163', 'Politics', 'general', 'Activities associated with governance and power relations'),
('Q11016', 'Technology', 'general', 'Application of scientific knowledge for practical purposes'),
('Q336', 'Science', 'general', 'Systematic study of the natural and social world'),
('Q24885', 'Finance', 'general', 'Management of money and investments'),

-- Specific economics categories
('Q186363', 'Monetary policy', 'specific', 'Process by which monetary authority controls money supply'),
('Q53536', 'Federal Reserve System', 'specific', 'Central banking system of the United States'),
('Q82580', 'Interest rate', 'specific', 'Rate at which interest is paid by borrowers'),
('Q179289', 'Inflation', 'specific', 'General increase in prices and fall in purchasing value of money'),
('Q185038', 'Quantitative easing', 'specific', 'Monetary policy of purchasing securities'),

-- Specific politics categories
('Q159810', 'International trade', 'specific', 'Exchange of goods and services across borders'),
('Q7188', 'Geopolitics', 'specific', 'Politics influenced by geographical factors'),
('Q36236', 'Ideology', 'specific', 'Set of beliefs or philosophies'),

-- Add more as needed...
;
```

**Criteria for inclusion:**
- High-level general categories (Economics, Politics, Science, etc.)
- Specific categories relevant to your content
- Balance breadth (many domains) with depth (specific subcategories)
- Can expand over time as you encounter new topics

### Step 2: LLM Prompt Engineering (Constrained Selection)

**For Source Categorization:**

```python
def categorize_source_with_wikidata(source_text: str, available_categories: list[dict]) -> list[dict]:
    """
    Categorize a source using ONLY the provided WikiData categories.
    
    Args:
        source_text: The source content (title, description, transcript)
        available_categories: List of dicts with {wikidata_id, category_name, description}
    
    Returns:
        List of exactly 3 categories with relevance scores
    """
    
    # Build the category list for the prompt
    category_list = "\n".join([
        f"- {cat['category_name']} ({cat['wikidata_id']}): {cat['description']}"
        for cat in available_categories
    ])
    
    prompt = f"""
You are a content categorization expert. Analyze the following source and select EXACTLY 3 categories from the provided WikiData category list.

SOURCE CONTENT:
{source_text}

AVAILABLE CATEGORIES (you MUST choose from this list):
{category_list}

INSTRUCTIONS:
1. Select EXACTLY 3 categories that best describe this source
2. Rank them 1-3 by relevance (1 = most relevant)
3. You MUST use the exact WikiData IDs provided
4. If the perfect category isn't available, choose the closest one
5. Provide a relevance score (0.0-1.0) for each

OUTPUT FORMAT (JSON):
{{
  "categories": [
    {{"wikidata_id": "Q...", "category_name": "...", "rank": 1, "relevance": 0.95, "rationale": "..."}},
    {{"wikidata_id": "Q...", "category_name": "...", "rank": 2, "relevance": 0.87, "rationale": "..."}},
    {{"wikidata_id": "Q...", "category_name": "...", "rank": 3, "relevance": 0.73, "rationale": "..."}}
  ]
}}
"""
    
    # Use structured output (OpenAI function calling, Anthropic tools, etc.)
    response = llm.generate_structured(
        prompt=prompt,
        response_format={
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "wikidata_id": {"type": "string", "pattern": "^Q[0-9]+$"},
                            "category_name": {"type": "string"},
                            "rank": {"type": "integer", "minimum": 1, "maximum": 3},
                            "relevance": {"type": "number", "minimum": 0, "maximum": 1},
                            "rationale": {"type": "string"}
                        },
                        "required": ["wikidata_id", "category_name", "rank", "relevance"]
                    },
                    "minItems": 3,
                    "maxItems": 3
                }
            },
            "required": ["categories"]
        }
    )
    
    return response['categories']
```

**For Claim Categorization:**

```python
def categorize_claim_with_wikidata(claim_text: str, available_categories: list[dict]) -> dict:
    """
    Categorize a claim using ONLY the provided WikiData categories.
    
    Returns:
        Single primary category
    """
    
    category_list = "\n".join([
        f"- {cat['category_name']} ({cat['wikidata_id']}): {cat['description']}"
        for cat in available_categories
    ])
    
    prompt = f"""
You are a claim categorization expert. Analyze the following claim and select the SINGLE most specific category from the provided WikiData category list.

CLAIM:
{claim_text}

AVAILABLE CATEGORIES (you MUST choose from this list):
{category_list}

INSTRUCTIONS:
1. Select the ONE most specific category that describes this claim
2. You MUST use the exact WikiData ID provided
3. If the perfect category isn't available, choose the closest one
4. Provide a relevance score (0.0-1.0)

OUTPUT FORMAT (JSON):
{{
  "category": {{
    "wikidata_id": "Q...",
    "category_name": "...",
    "relevance": 0.92,
    "rationale": "..."
  }}
}}
"""
    
    response = llm.generate_structured(
        prompt=prompt,
        response_format={
            "type": "object",
            "properties": {
                "category": {
                    "type": "object",
                    "properties": {
                        "wikidata_id": {"type": "string", "pattern": "^Q[0-9]+$"},
                        "category_name": {"type": "string"},
                        "relevance": {"type": "number", "minimum": 0, "maximum": 1},
                        "rationale": {"type": "string"}
                    },
                    "required": ["wikidata_id", "category_name", "relevance"]
                }
            },
            "required": ["category"]
        }
    )
    
    return response['category']
```

### Step 3: Validation and Fallback

```python
def validate_and_store_categories(source_id: str, llm_categories: list[dict], db: DatabaseService):
    """
    Validate that LLM returned valid WikiData IDs and store them.
    """
    with db.get_session() as session:
        # Get valid WikiData IDs from our vocabulary
        valid_ids = {row.wikidata_id for row in session.query(WikiDataCategory.wikidata_id).all()}
        
        for cat in llm_categories:
            wikidata_id = cat['wikidata_id']
            
            # Validate WikiData ID exists in our vocabulary
            if wikidata_id not in valid_ids:
                logger.error(f"LLM returned invalid WikiData ID: {wikidata_id}")
                # Fallback: try to find by name
                fallback = session.query(WikiDataCategory).filter_by(
                    category_name=cat['category_name']
                ).first()
                
                if fallback:
                    logger.warning(f"Using fallback WikiData ID: {fallback.wikidata_id}")
                    wikidata_id = fallback.wikidata_id
                else:
                    # Skip this category if we can't validate it
                    logger.error(f"Skipping invalid category: {cat}")
                    continue
            
            # Store the validated category
            source_category = SourceCategory(
                source_id=source_id,
                wikidata_id=wikidata_id,
                rank=cat['rank'],
                relevance_score=cat['relevance'],
                confidence=0.85,  # Based on LLM reliability
                source='system'
            )
            session.add(source_category)
        
        session.commit()
```

---

## Three Enforcement Layers

### Layer 1: Database FK Constraint (Hard Enforcement)

```sql
CREATE TABLE source_categories (
    source_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,
    ...
    FOREIGN KEY (wikidata_id) REFERENCES wikidata_categories(wikidata_id)  -- ENFORCED
);
```

**Effect:** Database will reject any `wikidata_id` not in the vocabulary table.

### Layer 2: Structured Output (LLM Constraint)

```python
response_format={
    "wikidata_id": {"type": "string", "pattern": "^Q[0-9]+$"}  # Must be Q-number
}
```

**Effect:** LLM is forced to return WikiData ID format.

### Layer 3: Prompt Engineering (Explicit List)

```
You MUST choose from this list:
- Economics (Q8134)
- Politics (Q7163)
...
```

**Effect:** LLM is given explicit choices, reducing hallucination.

---

## Handling Category Gaps

**What if the perfect category doesn't exist in our vocabulary?**

### Option 1: Expand Vocabulary (Preferred)

```python
def suggest_new_wikidata_category(content: str, existing_categories: list[str]) -> dict:
    """
    Ask LLM to suggest a WikiData category that's missing from our vocabulary.
    """
    prompt = f"""
The existing categories don't fit well for this content:
{content}

Existing categories: {existing_categories}

Suggest a specific WikiData category that should be added to our vocabulary.
Provide the WikiData ID (Q-number), name, and description.
"""
    
    # This goes to a review queue for manual approval
    suggestion = llm.generate(prompt)
    
    # Store as pending suggestion
    db.store_category_suggestion(
        wikidata_id=suggestion['wikidata_id'],
        category_name=suggestion['category_name'],
        status='pending_review',
        suggested_by='system',
        suggestion_context=content[:500]
    )
```

### Option 2: Use Closest Match + Flag

```python
def categorize_with_confidence_flag(content: str, categories: list[dict]) -> dict:
    """
    If no great match exists, use closest and flag for review.
    """
    result = categorize_source_with_wikidata(content, categories)
    
    # If all relevance scores are low, flag it
    if all(cat['relevance'] < 0.6 for cat in result['categories']):
        logger.warning(f"Low relevance scores for source categorization")
        db.flag_for_category_review(
            source_id=source_id,
            reason='low_relevance_scores',
            suggested_action='expand_vocabulary'
        )
    
    return result
```

---

## Vocabulary Management UI

```
┌─ WIKIDATA VOCABULARY MANAGER ────────────────┐
│                                               │
│ Current Vocabulary: 187 categories            │
│                                               │
│ General Categories (45):                      │
│   ✓ Economics (Q8134)                         │
│   ✓ Politics (Q7163)                          │
│   ✓ Technology (Q11016)                       │
│   ...                                         │
│                                               │
│ Pending Suggestions (3):                      │
│   ⏳ Climate policy (Q7942)     [Approve]     │
│   ⏳ Artificial intelligence (Q11660) [Approve]│
│   ⏳ Blockchain (Q20514253)     [Approve]     │
│                                               │
│ [+ Add Category Manually]                     │
│ [Import from WikiData Search]                 │
│ [View Category Hierarchy]                     │
└───────────────────────────────────────────────┘
```

---

## Pipeline Integration

```python
async def process_source_categorization(source_id: str, source_content: str):
    """
    Categorize a source using WikiData vocabulary.
    """
    # 1. Load curated WikiData categories
    categories = db.get_wikidata_categories(level='general')  # ~50-100 categories
    
    # 2. Ask LLM to categorize (constrained to vocabulary)
    llm_result = categorize_source_with_wikidata(source_content, categories)
    
    # 3. Validate and store
    validate_and_store_categories(source_id, llm_result, db)
    
    # 4. Flag if low confidence
    if any(cat['relevance'] < 0.6 for cat in llm_result):
        db.flag_for_review(source_id, reason='low_category_relevance')

async def process_claim_categorization(claim_id: str, claim_text: str, source_categories: list[str]):
    """
    Categorize a claim using WikiData vocabulary.
    
    Note: Provide source_categories as context to help LLM.
    """
    # 1. Load specific WikiData categories (narrower than source categories)
    categories = db.get_wikidata_categories(level='specific')  # ~100-200 categories
    
    # 2. Add source categories as context
    prompt_context = f"This claim is from a source about: {', '.join(source_categories)}"
    
    # 3. Ask LLM to categorize (constrained to vocabulary)
    llm_result = categorize_claim_with_wikidata(
        claim_text=f"{prompt_context}\n\nClaim: {claim_text}",
        available_categories=categories
    )
    
    # 4. Validate and store
    validate_and_store_claim_category(claim_id, llm_result, db)
```

---

## Summary

### Platform Categories (Uncontrolled)
- ❌ NO WikiData enforcement
- ✅ Accept as-is from YouTube, iTunes, etc.
- Storage: `platform_categories` table
- Purpose: Attribution/metadata from source

### Semantic Categories (WikiData Controlled)
- ✅ WikiData enforcement via:
  1. **Curated vocabulary** (~100-200 categories)
  2. **Structured LLM output** (forced format)
  3. **Database FK constraint** (hard validation)
  4. **Explicit prompt list** (reduce hallucination)
- Storage: `source_categories`, `claim_categories` tables
- Purpose: Our structured categorization

### Vocabulary Evolution
- Start with ~100 curated WikiData categories
- Expand as needed via:
  - Manual additions
  - LLM suggestions → review queue
  - User requests
- Goal: Balance coverage vs. constraint

### Enforcement Stack
```
LLM Prompt (explicit list)
    ↓
Structured Output (Q-number format)
    ↓
Python Validation (check against vocabulary)
    ↓
Database FK Constraint (hard enforcement)
```

**Result:** LLM can ONLY return categories from our curated WikiData vocabulary!

