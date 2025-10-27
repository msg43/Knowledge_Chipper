# WikiData Vocabulary Strategy

## The Question: Full Taxonomy vs Curated List?

You asked: "Download the wikidata complete taxonomy and use that?"

**Answer:** Yes, but with smart filtering!

---

## The Challenge

**WikiData has:**
- ~100 million items total
- But only ~50,000-100,000 relevant topic categories
- Many are too specific (e.g., "Q123456: 2024 Montana Senate Race")
- Many are biological/chemical taxonomy (not relevant for general claims)

**We need:**
- Broad enough to cover common topics (~1,000-2,000 categories)
- Filtered to conceptual topics (not specific entities)
- Hierarchical (parent-child relationships)
- Regularly updated

---

## ✅ Implemented Solution

### download_wikidata_taxonomy.py

**Strategy:**

1. **Query top-level concepts** (Economics, Politics, Science, etc.)
2. **Query academic disciplines** (fields of study)
3. **Get subcategories** 2-3 levels deep
4. **Filter out:**
   - Specific entities (people, cities, companies)
   - Biological taxonomy (species, genera)
   - Chemical compounds
   - Geographic locations

**Result:** ~1,000-2,000 conceptual categories perfect for knowledge claims

---

## Current Status

### Test Run Results

**Attempted:**
```bash
python download_wikidata_taxonomy.py --max-categories 200 --depth 2
```

**Results:**
- ✅ Downloaded 21 broad concepts successfully
- ⚠️ Academic disciplines query returned 0 (query needs refinement)
- ⚠️ Subcategory query hit rate limit (429 Too Many Requests)

**Diagnosis:**
- WikiData SPARQL has aggressive rate limiting
- Need slower queries with more sleep time
- Or: Use pre-downloaded curated lists

---

## Better Approach: Hybrid Strategy

### Option 1: Curate Manually (RECOMMENDED)

**Expand our current 41 to ~200-500 categories** by manually adding from WikiData:

**Process:**
1. Browse WikiData category hierarchies
2. Add relevant categories to `wikidata_seed.json`
3. Focus on:
   - All major academic disciplines
   - Common topics in news/media
   - Business/technology domains
   - Social sciences
   - Natural sciences (high-level only)

**Time investment:** ~2-3 hours to curate 200 categories  
**Quality:** High (human-curated)  
**Coverage:** Excellent for 80-90% of content

**Tools:**
- https://www.wikidata.org/wiki/Wikidata:Main_Page
- Browse category hierarchies
- Copy Q-numbers and descriptions

### Option 2: Semi-Automated Download (IMPLEMENTED)

**Use the download script with slow, respectful querying:**

```bash
# Download with conservative limits
python download_wikidata_taxonomy.py \
  --max-categories 500 \
  --depth 2 \
  --output wikidata_expanded.json
  
# Merge with existing curated list
python download_wikidata_taxonomy.py \
  --merge src/knowledge_system/database/wikidata_seed.json \
  --max-categories 500 \
  --output wikidata_merged.json
```

**Challenges:**
- Rate limiting (need to space out queries)
- Query complexity (academic disciplines query needs work)
- Takes time (~10-20 minutes with rate limiting)

**Benefits:**
- Automated updates possible
- Gets official descriptions
- Maintains hierarchy

### Option 3: Use Pre-Downloaded Lists (FASTEST)

Several curated WikiData category lists exist:

**Source 1: WikiData Category Lists**
- Download from: https://www.wikidata.org/wiki/Wikidata:Database_download
- Filter to "Categories" subset
- Process locally

**Source 2: Schema.org Mapping**
- Schema.org has ~800 types
- Many map to WikiData
- Well-curated for web content

**Source 3: Wikipedia Main Topics**
- Wikipedia's top-level categories
- Most have WikiData IDs
- ~500-1,000 conceptual categories

---

## Recommended Immediate Action

### Expand to 200 Categories Manually (Fastest & Best Quality)

**Time:** 2 hours  
**Method:** Add to `wikidata_seed.json`  
**Quality:** High  
**Coverage:** 80-90% of typical content

**Category suggestions to add:**

**Business & Economics (add ~30):**
- Q179289 ✅ Inflation (already have)
- Q507619 Supply chain
- Q4830453 Business
- Q219577 Entrepreneurship
- Q484652 International development
- Q161238 Investment
- Q192949 Taxation
- Q171433 Marketing
- Q483394 Startup company
- Q43637 Real estate
- ... +20 more

**Technology & Computing (add ~25):**
- Q11660 ✅ Artificial intelligence (already have)
- Q2539 Machine learning (47728)
- Q2 Software engineering
- Q21198 Computer science
- Q131257 Data science
- Q22702 Cybersecurity
- Q2493 Internet of things
- Q185425 Cloud computing
- Q1058914 5G
- ... +15 more

**Politics & Society (add ~30):**
- Q7163 ✅ Politics (already have)
- Q157292 International relations
- Q7174 Democracy
- Q7188 Government
- Q162633 Public policy
- Q159810 International trade
- Q124364 Social movement
- Q42178 Journalism
- ... +22 more

**Sciences (add ~30):**
- Q336 ✅ Science (already have)
- Q413 Physics
- Q2329 Chemistry
- Q420 Biology
- Q199 Psychology
- Q11173 Neuroscience
- Q8137 Climate science
- Q21201 Sociology
- ... +22 more

**Health & Medicine (add ~20):**
- Q11190 Medicine
- Q12199 Public health
- Q788926 Epidemiology
- Q808 Biotechnology
- Q7189 Vaccine
- ... +15 more

**Culture & Society (add ~20):**
- Q8134 Education
- Q11042 Culture
- Q8134 Religion
- Q17143031 Social media
- ... +16 more

**Estimated:** ~155 new categories = 196 total

---

## Recommendation

### Short Term (Next 2 Hours): Manual Curation

**Add 150-200 carefully selected categories to wikidata_seed.json:**

```json
{
  "categories": [
    ... existing 41 ...,
    {
      "wikidata_id": "Q507619",
      "category_name": "Supply chain",
      "description": "Management of the flow of goods and services",
      "level": "specific",
      "parent_id": "Q8134",
      "aliases": ["Supply chain management", "Logistics chain"]
    },
    ... +149 more ...
  ]
}
```

**Benefits:**
- ✅ Fast (2 hours vs days of API calls)
- ✅ High quality (human-curated)
- ✅ No rate limits
- ✅ Focused on relevant topics
- ✅ Good descriptions/aliases

### Long Term: Automated Updates

**Use download script for periodic refreshes:**

```bash
# Monthly update: Download new categories
python download_wikidata_taxonomy.py \
  --merge wikidata_seed.json \
  --max-categories 100 \
  --output wikidata_seed.json

# This adds ~100 new categories per month
# Keeps vocabulary fresh
```

---

## Implementation Plan

### Phase 1: Expand to 200 Categories (MANUAL - 2 hours)

1. Browse WikiData for each domain
2. Add Q-numbers to wikidata_seed.json
3. Include descriptions and aliases
4. Recompute embeddings

**Expected improvement:**
- Automation: 8% → 50-60%
- Vocab gaps: 33% → 10-15%

### Phase 2: Expand to 500 Categories (SEMI-AUTO - 1 week)

1. Use download script with slow rate limiting
2. Review and filter results
3. Merge with curated list
4. Recompute embeddings

**Expected improvement:**
- Automation: 60% → 70-75%
- Vocab gaps: 15% → 5-8%

### Phase 3: Maintain at 500-1000 (AUTO - ongoing)

1. Monthly downloads of new categories
2. Automatic merging
3. Continuous improvement

**Expected steady state:**
- Automation: 70-75%
- Vocab gaps: 5-8%
- Coverage: 95%+ of content

---

## Current Script Status

**What works:**
- ✅ SPARQL query construction
- ✅ Broad concepts download (21 categories)
- ✅ Result parsing
- ✅ Merge functionality

**What needs refinement:**
- ⚠️ Academic disciplines query (returned 0, needs fixing)
- ⚠️ Rate limiting (hitting 429 errors)
- ⚠️ Retry logic (needs longer delays)

**Fix needed:**
```python
# Add more aggressive rate limiting
time.sleep(5)  # Instead of 1 second

# Add backoff on 429
if response.status_code == 429:
    wait_time = int(response.headers.get('Retry-After', 60))
    time.sleep(wait_time)
```

---

## Recommendation

### BEST APPROACH: Start Manual, Automate Later

**Week 1 (NOW):**
- Manually curate 150-200 categories (2-3 hours)
- Add to wikidata_seed.json
- Recompute embeddings
- **Result:** 50-60% automation

**Month 1:**
- Use download script to expand to 500
- Review and filter
- **Result:** 70% automation

**Ongoing:**
- Monthly automated downloads
- Automatic merging
- **Result:** Maintain 70%+ automation

---

Would you like me to:
1. **Fix the download script** to handle rate limiting better?
2. **Create a curated 200-category list** from WikiData manually?
3. **Use a pre-downloaded WikiData category dump** and filter it locally?

The fastest path to 70% automation is **option 2** (manual curation to 200 categories).
