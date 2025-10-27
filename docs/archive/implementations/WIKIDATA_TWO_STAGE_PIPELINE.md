# WikiData Category Enforcement: Two-Stage Pipeline

## The Problem with Prompt-Based Enforcement

### ❌ Approaches That Don't Work

**1. Token Masking / Constrained Decoding**
```python
# Force LLM to only output from allowed tokens
response = llm.generate(prompt, allowed_tokens=['Q8134', 'Q7163', ...])
```
**Problem:** Very slow, not supported by all providers

**2. Massive Category List in Prompt**
```python
prompt = f"""
Choose from these 200 categories:
- Economics (Q8134): The social science...
- Politics (Q7163): Activities associated...
- Finance (Q24885): Management of money...
[... 197 more categories ...]

Now categorize: {content}
"""
```
**Problem:** Dilutes the prompt, wastes tokens, degrades performance

---

## ✅ Better Approach: Two-Stage Pipeline

### Stage 1: LLM Generates Free-Form Categories

**Clean, focused prompt** (no category list):

```python
def generate_freeform_categories(content: str, level: str) -> list[str]:
    """
    Ask LLM to generate category descriptions without constraints.
    
    Args:
        content: The content to categorize
        level: 'source' (general, max 3) or 'claim' (specific, typically 1)
    
    Returns:
        List of category descriptions
    """
    
    if level == 'source':
        prompt = f"""
Analyze this content and identify the 3 most important GENERAL topics it covers.

CONTENT:
{content}

Provide 3 broad, high-level topics (like "Economics", "Politics", "Technology").
Not specific subtopics, but general domains.

OUTPUT (JSON):
{{
  "categories": [
    {{"name": "General topic 1", "rationale": "Why this fits"}},
    {{"name": "General topic 2", "rationale": "Why this fits"}},
    {{"name": "General topic 3", "rationale": "Why this fits"}}
  ]
}}
"""
    else:  # claim
        prompt = f"""
Analyze this claim and identify the single most SPECIFIC topic it's about.

CLAIM:
{content}

Provide ONE specific topic (like "Monetary policy", not just "Economics").

OUTPUT (JSON):
{{
  "category": {{"name": "Specific topic", "rationale": "Why this fits"}}
}}
"""
    
    # Clean prompt, no category list!
    response = llm.generate_structured(prompt, response_format=...)
    
    if level == 'source':
        return [cat['name'] for cat in response['categories']]
    else:
        return [response['category']['name']]
```

**Benefits:**
- ✅ Clean, focused prompt
- ✅ Fast (no token masking)
- ✅ LLM can use its full knowledge
- ✅ Natural language output

**Example output:**
```
["Economics", "Central banking", "Monetary policy"]
```

### Stage 2: Map to WikiData Categories

**Separate service** matches free-form → WikiData:

```python
def map_to_wikidata_categories(
    freeform_categories: list[str],
    wikidata_vocab: list[dict],
    top_k: int = 3
) -> list[dict]:
    """
    Map free-form category descriptions to WikiData categories.
    
    Args:
        freeform_categories: LLM-generated category names
        wikidata_vocab: List of {wikidata_id, category_name, description, embedding}
        top_k: Number of best matches to return per category
    
    Returns:
        List of WikiData matches with confidence scores
    """
    
    matches = []
    
    for freeform_cat in freeform_categories:
        # Find best WikiData matches using embeddings
        candidates = find_closest_wikidata_categories(
            query=freeform_cat,
            wikidata_vocab=wikidata_vocab,
            top_k=top_k
        )
        
        matches.append({
            'freeform': freeform_cat,
            'candidates': candidates  # Top K WikiData matches
        })
    
    return matches
```

---

## Mapping Strategies

### Option 1: Embedding-Based Matching (Recommended)

**Pre-compute embeddings for WikiData vocabulary:**

```python
from sentence_transformers import SentenceTransformer

class WikiDataMatcher:
    def __init__(self, wikidata_vocab_file: Path):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # Fast, lightweight
        
        # Load WikiData vocabulary
        with open(wikidata_vocab_file) as f:
            self.vocab = json.load(f)
        
        # Pre-compute embeddings for all WikiData categories
        self.category_texts = [
            f"{cat['category_name']}: {cat['description']}"
            for cat in self.vocab
        ]
        self.embeddings = self.model.encode(self.category_texts)
    
    def find_matches(self, freeform_category: str, top_k: int = 3) -> list[dict]:
        """
        Find closest WikiData categories using semantic similarity.
        """
        # Embed the free-form category
        query_embedding = self.model.encode([freeform_category])
        
        # Compute cosine similarity
        from sklearn.metrics.pairwise import cosine_similarity
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        
        # Get top-K matches
        top_indices = similarities.argsort()[-top_k:][::-1]
        
        matches = []
        for idx in top_indices:
            matches.append({
                'wikidata_id': self.vocab[idx]['wikidata_id'],
                'category_name': self.vocab[idx]['category_name'],
                'similarity': float(similarities[idx]),
                'confidence': 'high' if similarities[idx] > 0.8 else 'medium' if similarities[idx] > 0.6 else 'low'
            })
        
        return matches
```

**Example:**
```python
matcher = WikiDataMatcher('wikidata_vocab.json')

# LLM said "Central banking"
matches = matcher.find_matches("Central banking", top_k=3)

# Results:
[
  {'wikidata_id': 'Q66344', 'category_name': 'Central banking', 'similarity': 0.98, 'confidence': 'high'},
  {'wikidata_id': 'Q53536', 'category_name': 'Federal Reserve System', 'similarity': 0.76, 'confidence': 'medium'},
  {'wikidata_id': 'Q186363', 'category_name': 'Monetary policy', 'similarity': 0.72, 'confidence': 'medium'}
]
```

**Auto-accept if high confidence:**
- Similarity > 0.85: Auto-accept ✅
- Similarity 0.6-0.85: Show user for approval ⚠️
- Similarity < 0.6: Flag for review ❌

### Option 2: Fuzzy String Matching (Fallback)

```python
from fuzzywuzzy import process

def fuzzy_match_wikidata(freeform_category: str, wikidata_vocab: list[dict], top_k: int = 3) -> list[dict]:
    """
    Fallback: Use fuzzy string matching if embeddings not available.
    """
    category_names = [cat['category_name'] for cat in wikidata_vocab]
    
    # Find closest matches by string similarity
    matches = process.extract(freeform_category, category_names, limit=top_k)
    
    results = []
    for match_name, score in matches:
        wikidata_cat = next(cat for cat in wikidata_vocab if cat['category_name'] == match_name)
        results.append({
            'wikidata_id': wikidata_cat['wikidata_id'],
            'category_name': match_name,
            'similarity': score / 100.0,  # Normalize to 0-1
            'confidence': 'high' if score > 85 else 'medium' if score > 60 else 'low'
        })
    
    return results
```

### Option 3: LLM-Based Refinement (For Edge Cases)

```python
def llm_refine_mapping(freeform_category: str, candidates: list[dict]) -> dict:
    """
    If confidence is low, ask LLM to choose best match from candidates.
    """
    
    candidates_text = "\n".join([
        f"- {cat['category_name']} ({cat['wikidata_id']}): {cat['description']}"
        for cat in candidates
    ])
    
    prompt = f"""
The system generated this category: "{freeform_category}"

Which of these WikiData categories is the best match?

{candidates_text}

Choose the BEST match, or respond "none" if none fit well.

OUTPUT (JSON):
{{
  "best_match": "Q...",  // WikiData ID or "none"
  "rationale": "..."
}}
"""
    
    response = llm.generate_structured(prompt, ...)
    return response
```

---

## Complete Two-Stage Pipeline

```python
async def categorize_source(source_id: str, source_content: str):
    """
    Complete two-stage pipeline for source categorization.
    """
    
    # === STAGE 1: LLM generates free-form categories ===
    freeform_categories = generate_freeform_categories(
        content=source_content,
        level='source'
    )
    # Example: ["Economics", "Central banking", "Monetary policy"]
    
    # === STAGE 2: Map to WikiData ===
    matcher = WikiDataMatcher('wikidata_vocab.json')
    
    final_categories = []
    needs_review = []
    
    for rank, freeform_cat in enumerate(freeform_categories[:3], start=1):
        # Find WikiData matches
        matches = matcher.find_matches(freeform_cat, top_k=3)
        best_match = matches[0]
        
        if best_match['confidence'] == 'high':
            # Auto-accept high confidence matches
            final_categories.append({
                'wikidata_id': best_match['wikidata_id'],
                'category_name': best_match['category_name'],
                'rank': rank,
                'relevance': best_match['similarity'],
                'source': 'system',
                'user_approved': False
            })
        else:
            # Low/medium confidence: flag for user review
            needs_review.append({
                'freeform': freeform_cat,
                'rank': rank,
                'candidates': matches
            })
    
    # === STAGE 3: Store results ===
    with db.get_session() as session:
        for cat in final_categories:
            session.add(SourceCategory(
                source_id=source_id,
                wikidata_id=cat['wikidata_id'],
                rank=cat['rank'],
                relevance_score=cat['relevance'],
                source='system',
                user_approved=False
            ))
        
        # Flag source for review if any mappings uncertain
        if needs_review:
            session.add(CategoryReviewTask(
                source_id=source_id,
                pending_mappings=json.dumps(needs_review),
                status='pending'
            ))
        
        session.commit()
```

---

## User Review Workflow

### When Confidence is Low

```
┌─ CATEGORY REVIEW NEEDED ─────────────────────┐
│                                               │
│ Source: "Fed Policy Discussion"              │
│                                               │
│ The system suggested "Central banking"       │
│ but needs your confirmation.                  │
│                                               │
│ Best matches:                                 │
│   ● Central banking (Q66344)      [98%] ✓    │
│   ○ Federal Reserve System (Q53536) [76%]    │
│   ○ Monetary policy (Q186363)      [72%]    │
│                                               │
│ [Accept Top Match] [Choose Different] [Skip] │
└───────────────────────────────────────────────┘
```

### Review Queue

```
┌─ PENDING CATEGORY REVIEWS (12) ──────────────┐
│                                               │
│ 1. "Fed Policy Discussion"                   │
│    Suggested: Central banking → Q66344 (98%) │
│    [Review] [Auto-approve]                    │
│                                               │
│ 2. "AI Safety Research"                       │
│    Suggested: Artificial intelligence → ?    │
│    Low confidence (45%) - needs manual review │
│    [Review]                                   │
│                                               │
│ [Auto-approve all high confidence (>85%)]    │
│ [Expand WikiData vocabulary]                  │
└───────────────────────────────────────────────┘
```

---

## Dynamic WikiData Vocabulary

### Vocabulary File (`wikidata_vocab.json`)

```json
{
  "version": "2024-10-26",
  "categories": [
    {
      "wikidata_id": "Q8134",
      "category_name": "Economics",
      "description": "Social science studying production, distribution, and consumption",
      "level": "general",
      "parent_id": null,
      "aliases": ["Economic science", "Political economy"]
    },
    {
      "wikidata_id": "Q186363",
      "category_name": "Monetary policy",
      "description": "Process by which monetary authority controls money supply",
      "level": "specific",
      "parent_id": "Q8134",
      "aliases": ["Monetary policies", "Central bank policy"]
    }
  ]
}
```

### Updating Vocabulary

```python
def update_wikidata_vocabulary(new_categories: list[dict]):
    """
    Update the WikiData vocabulary file.
    Automatically recomputes embeddings.
    """
    # Load current vocabulary
    with open('wikidata_vocab.json') as f:
        vocab = json.load(f)
    
    # Add new categories
    vocab['categories'].extend(new_categories)
    vocab['version'] = datetime.now().isoformat()
    
    # Save updated vocabulary
    with open('wikidata_vocab.json', 'w') as f:
        json.dump(vocab, f, indent=2)
    
    # Recompute embeddings
    matcher = WikiDataMatcher('wikidata_vocab.json')
    matcher.save_embeddings('wikidata_embeddings.pkl')
    
    logger.info(f"Updated vocabulary to {len(vocab['categories'])} categories")
```

**Vocabulary updates trigger:**
- Embedding recomputation (one-time, cached)
- No prompt changes (vocabulary not in prompts!)
- Immediate effect on mapping

---

## Benefits of Two-Stage Approach

### ✅ Clean Prompts
- No 200-category lists
- LLM uses natural language
- Focused on content analysis

### ✅ Fast
- No token masking
- Embedding search is instant (<1ms)
- Can process thousands of categories

### ✅ Dynamic
- Update vocabulary anytime
- Recompute embeddings once
- No code changes needed

### ✅ Flexible
- High confidence: auto-accept
- Medium confidence: user review
- Low confidence: suggest vocabulary expansion

### ✅ Scalable
- Works with 100, 1000, or 10,000 WikiData categories
- Embedding search scales to millions of categories
- No prompt size limits

---

## Summary

### Pipeline

```
Content
  ↓
STAGE 1: LLM generates free-form categories
  - Clean prompt (no category list)
  - Fast (no constraints)
  - Natural language output
  ↓
STAGE 2: Map to WikiData via embeddings
  - Semantic similarity search
  - Instant (pre-computed embeddings)
  - Top-K matches with confidence
  ↓
STAGE 3: Auto-accept or flag for review
  - High confidence (>0.85): auto-accept
  - Medium (0.6-0.85): user review
  - Low (<0.6): expand vocabulary
  ↓
Store in database
```

### Comparison

| Approach | Speed | Prompt Size | Dynamic | Accuracy |
|----------|-------|-------------|---------|----------|
| Token masking | ❌ Slow | Small | ❌ No | ✅ High |
| Category list in prompt | ✅ Fast | ❌ Huge | ❌ No | ⚠️ Medium |
| **Two-stage pipeline** | ✅ Fast | ✅ Small | ✅ Yes | ✅ High |

**Winner:** Two-stage pipeline!

Ready to implement this approach?
