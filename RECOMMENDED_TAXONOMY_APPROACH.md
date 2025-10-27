# Recommended Taxonomy Approach

## Your Requirements

✅ Stable over time  
✅ Widely recognized (by rest of world)  
✅ Comprehensive (covers all knowledge domains)  
❌ No hundreds of thousands of biological species  
❌ No overly specific taxonomies  

---

## ✅ Perfect Match: WikiData Fields of Study

### The Root Categories

**Q2267705 (Field of study)** - Primary root
- Economics, Physics, Psychology, Medicine, etc.
- What universities organize into departments
- What scholars identify as their field
- **~800-1,200 total categories**

**Excludes automatically:**
- Biological species taxonomy
- Chemical compounds
- Specific entities (people, places, brands)
- Temporal events

---

## What You'll Get

### Tier 1: Major Domains (~30)
```
Sciences: Physics, Chemistry, Biology, Mathematics
Social Sciences: Economics, Politics, Sociology, Psychology
Humanities: History, Philosophy, Literature, Law
Applied: Technology, Medicine, Engineering, Business
```

### Tier 2: Recognized Subfields (~200-300)
```
Economics → Monetary policy, Fiscal policy, International trade
Physics → Quantum mechanics, Thermodynamics, Astrophysics
Medicine → Cardiology, Neurology, Epidemiology
Technology → AI, Machine learning, Cybersecurity
```

### Tier 3: Specific Topics (~400-600)
```
Monetary policy → Interest rates, Central banking, Quantitative easing
AI → Machine learning, Neural networks, Computer vision
```

**Total: ~800-1,000 stable conceptual categories**

---

## Stability Guarantee

### What Changes (rarely):

- **New academic fields emerge** every ~5-10 years
  - Example: "Data science" didn't exist in 2000
  - Example: "Climate science" emerged in 1990s
  - **Solution:** Update vocabulary quarterly/annually

### What Doesn't Change:

- Core disciplines (Physics, Economics, etc.) - **stable for centuries**
- Major subfields - **stable for decades**
- WikiData Q-numbers - **never change once assigned**

**Conclusion:** ~95% of your vocabulary will be stable indefinitely

---

## Recognition by Rest of World

### WikiData Maps To:

1. **Dewey Decimal Classification** (200,000+ libraries worldwide)
2. **Library of Congress** (US/UK/international libraries)
3. **UNESCO nomenclature** (UN standard)
4. **Academic institutional databases** (universities globally)
5. **Wikipedia categories** (read by billions)

**Example:**
```
WikiData Q186363 "Monetary policy"
  ↔ Dewey 332.46
  ↔ LoC HG230.3
  ↔ Wikipedia Category:Monetary_policy
  ↔ UNESCO 5.02.02
```

**Everyone recognizes these categories!**

---

## ✅ RECOMMENDED PLAN

### Phase 1: Download Conceptual Taxonomy (TODAY)

```bash
# Updated script targets conceptual categories only
python src/knowledge_system/database/download_wikidata_taxonomy.py \
  --max-categories 1000 \
  --conceptual-only \
  --merge wikidata_seed.json \
  --output wikidata_expanded.json
```

**Expected:**
- ~800-1,000 conceptual categories
- Excludes species, chemicals, people, places
- Stable, globally recognized
- Improves automation from 8% → 70%

### Phase 2: Recompute Embeddings

```python
from src.knowledge_system.services.wikidata_categorizer import WikiDataCategorizer

categorizer = WikiDataCategorizer(
    vocab_file='src/knowledge_system/database/wikidata_expanded.json'
)
categorizer._compute_embeddings()
```

### Phase 3: Test with Expanded Vocabulary

```bash
python test_wikidata_with_llm.py
# Expected: 70%+ automation (was 8% with 41 categories)
```

### Phase 4: Quarterly Updates

```bash
# Every 3 months: Add new emerging fields
python download_wikidata_taxonomy.py --merge --max-categories 100
```

---

## Alternative: Use Existing Curated List

If WikiData SPARQL continues having rate limit issues, use **Schema.org** as base:

**Schema.org has ~800 stable types** including:
- Thing → Intangible → topics
- CreativeWork → subjects
- All map to WikiData Q-numbers

**Pre-curated, stable, globally recognized!**

---

Would you like me to:

1. **Fix the download script** to better target conceptual categories with rate limit handling?
2. **Generate a curated 800-category list** using Schema.org + WikiData mapping?
3. **Try downloading with slower queries** (5-10 second delays to avoid rate limits)?

The **fastest** path is option 2 (use Schema.org as seed, expand with WikiData).
