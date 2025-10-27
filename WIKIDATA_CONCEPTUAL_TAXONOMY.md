# WikiData Conceptual Taxonomy for Knowledge Claims

## The Goal

A **stable, widely-recognized taxonomy** for categorizing knowledge claims across all domains.

**Want:**
- Fields of study (Economics, Physics, Psychology)
- Conceptual domains (Monetary policy, Quantum mechanics, Cognitive science)
- ~500-1,000 categories (comprehensive but manageable)
- Stable over time
- Recognized globally

**Don't Want:**
- Biological species taxonomy (thousands of species)
- Chemical compounds (millions of molecules)
- Specific entities (individual people, companies, products)
- Geographic taxonomy (cities, regions)
- Temporal specificity (2024 elections, COVID-19 pandemic)

---

## The Right WikiData Root: Q5891 (Fields of Study)

### Query Strategy

WikiData has **Q5891 (field of study)** as the root for conceptual taxonomy:

```
Q5891 (Field of study)
├── Q8134 (Economics)
│   ├── Q186363 (Monetary policy)
│   ├── Q39680 (Macroeconomics)
│   └── Q39631 (Microeconomics)
├── Q7163 (Politics)
│   ├── Q7188 (Government)
│   └── Q36236 (Ideology)
├── Q336 (Science)
│   ├── Q413 (Physics)
│   │   ├── Q11379 (Quantum mechanics)
│   │   └── Q12483 (Classical mechanics)
│   ├── Q2329 (Chemistry)
│   └── Q420 (Biology)
├── Q11016 (Technology)
│   ├── Q11660 (Artificial intelligence)
│   └── Q21198 (Computer science)
└── ... more
```

**This excludes:**
- ❌ Homo sapiens (Q15978631) - species
- ❌ Water (H2O) (Q283) - chemical
- ❌ Apple Inc. (Q312) - company
- ❌ New York City (Q60) - place

**Perfect for knowledge claims!**

---

## Recommended Approach: Three-Tier Taxonomy

### Tier 1: Top-Level Domains (~30 categories)

Major fields recognized globally:

```
Sciences:
- Q336  Science (general)
- Q413  Physics
- Q2329 Chemistry
- Q420  Biology
- Q395  Mathematics
- Q1069 Geology
- Q11398 Astronomy

Social Sciences:
- Q8134  Economics
- Q7163  Politics
- Q21201 Sociology
- Q9418  Psychology
- Q23404 Anthropology

Humanities:
- Q9129  History
- Q25379 Philosophy
- Q8242  Literature
- Q8386  Law
- Q9158  Linguistics

Applied Sciences:
- Q11016 Technology
- Q11190 Medicine
- Q11378 Ethics
- Q483269 Engineering

Other:
- Q638   Music
- Q735   Art
- Q11024  Communication
- Q49850  Religion
```

### Tier 2: Sub-Fields (~200-300 categories)

Recognized subfields within each domain:

```
Economics → Monetary policy, Fiscal policy, International trade, Finance, etc.
Physics → Quantum mechanics, Thermodynamics, Electromagnetism, etc.
Politics → International relations, Public policy, Geopolitics, etc.
Psychology → Cognitive science, Behavioral economics, Neuroscience, etc.
Technology → AI, Machine learning, Cybersecurity, Software engineering, etc.
```

### Tier 3: Specific Topics (~300-500 categories)

Specific enough to be useful, broad enough to be stable:

```
Monetary policy → Interest rates, Quantitative easing, Central banking
AI → Machine learning, Neural networks, Natural language processing
Medicine → Epidemiology, Oncology, Cardiology
```

**Total: ~500-800 categories**

---

## Perfect Model: Library Classification Systems

### Dewey Decimal Classification (DDC)

**Structure:**
- 10 main classes
- 100 divisions
- 1,000 sections
- ~10,000 subsections

**Mapped to WikiData:** Yes! Many DDC categories have WikiData Q-numbers

**Example:**
```
000 Computer science, information & general works
  004 Computer science (Q21198)
    004.8 Artificial intelligence (Q11660)
100 Philosophy & psychology
  150 Psychology (Q9418)
    153 Cognitive processes (Q153292)
200 Religion
  ...
```

**Coverage:** Comprehensive for all human knowledge  
**Stability:** Unchanged for decades  
**Recognition:** Global standard (used by 200,000+ libraries)

### Library of Congress Classification

**Similar but more granular:**
- 21 main classes
- ~50,000 subdivisions

**Also maps to WikiData**

---

## ✅ RECOMMENDED: Use WikiData's Academic Discipline Hierarchy

### The Query

```sparql
SELECT DISTINCT ?item ?itemLabel ?itemDescription ?parentLabel
WHERE {
  # Get fields of study, academic disciplines, and branches
  {
    ?item wdt:P31 wd:Q2267705.  # Field of study
  } UNION {
    ?item wdt:P31 wd:Q11862829. # Academic discipline  
  } UNION {
    ?item wdt:P31 wd:Q1936384.  # Branch of science
  } UNION {
    ?item wdt:P31 wd:Q28865.    # Domain of discourse
  }
  
  # Get parent category
  OPTIONAL { ?item wdt:P279 ?parent. }
  
  # Get labels
  SERVICE wikibase:label { 
    bd:serviceParam wikibase:language "en". 
  }
  
  # Exclude overly specific
  FILTER NOT EXISTS { ?item wdt:P31 wd:Q7187. }   # Not a species/gene
  FILTER NOT EXISTS { ?item wdt:P31 wd:Q11173. }  # Not a chemical compound
}
ORDER BY ?itemLabel
LIMIT 2000
```

**Expected result:** ~1,000-1,500 conceptual categories

**Coverage:**
- All major academic fields
- Recognized subfields
- Stable (fields of study don't change rapidly)
- Global (WikiData is multilingual, globally curated)

---

## Updated Download Script

Let me update the script to target these specific root categories:

```python
def download_conceptual_taxonomy(self, target_size: int = 800) -> list[dict]:
    """
    Download conceptual taxonomy (fields of study, academic disciplines).
    
    Excludes:
    - Biological species (Q16521)
    - Chemical compounds (Q11173)
    - People (Q5)
    - Places (Q515, Q3024240)
    - Specific events
    - Products/brands
    
    Includes:
    - Fields of study (Q2267705)
    - Academic disciplines (Q11862829)
    - Branches of science (Q1936384)
    - Domains of discourse (Q28865)
    - Recognized subfields
    """
    
    query = """
    SELECT DISTINCT ?item ?itemLabel ?itemDescription ?parentLabel
    WHERE {
      # Root concepts: fields of study and academic disciplines
      {
        ?item wdt:P31/wdt:P279* wd:Q2267705.  # Field of study
      } UNION {
        ?item wdt:P31/wdt:P279* wd:Q11862829. # Academic discipline
      } UNION {
        ?item wdt:P31/wdt:P279* wd:Q1936384.  # Branch of science
      }
      
      # Get parent
      OPTIONAL { ?item wdt:P279 ?parent. }
      
      # Labels
      SERVICE wikibase:label { 
        bd:serviceParam wikibase:language "en". 
      }
      
      # Exclusions (what we DON'T want)
      FILTER NOT EXISTS { ?item wdt:P31 wd:Q16521. }   # Not taxon
      FILTER NOT EXISTS { ?item wdt:P31 wd:Q11173. }   # Not chemical
      FILTER NOT EXISTS { ?item wdt:P31 wd:Q5. }       # Not person
      FILTER NOT EXISTS { ?item wdt:P31 wd:Q515. }     # Not city
      FILTER NOT EXISTS { ?item wdt:P31 wd:Q431289. }  # Not brand
    }
    LIMIT 2000
    """
```

---

## Estimated Coverage

### With ~800 Conceptual Categories

**Domains covered:**

| Domain | Categories | Examples |
|--------|-----------|----------|
| Natural Sciences | ~150 | Physics, Chemistry, Biology subfields |
| Social Sciences | ~120 | Economics, Politics, Sociology subfields |
| Humanities | ~100 | History, Philosophy, Literature subfields |
| Applied Sciences | ~120 | Engineering, Medicine, Technology subfields |
| Formal Sciences | ~50 | Mathematics, Logic, Computer Science |
| Interdisciplinary | ~80 | Cognitive science, Environmental studies |
| Arts & Culture | ~60 | Music theory, Art history, Media studies |
| Professions | ~50 | Law, Business, Education |
| Emerging Fields | ~70 | AI, Blockchain, Climate science |

**Total:** ~800 stable, recognized conceptual categories

---

## Stability Analysis

### Very Stable (won't change):
- Physics, Chemistry, Biology
- Economics, Politics, Sociology
- Mathematics, Logic
- History, Philosophy

### Moderately Stable (slow evolution):
- Subfields of sciences (new discoveries → new subfields every ~10 years)
- Social science methodologies
- Medical specialties

### Less Stable (faster evolution):
- Technology subfields (AI, Blockchain - new every ~2-5 years)
- Emerging interdisciplinary fields
- Business practices

**Solution:** Update vocabulary quarterly or annually to capture emerging fields

---

## Recognition by "Rest of World"

### WikiData Benefits:

1. **Multilingual** - 300+ languages
2. **Globally curated** - Maintained by worldwide community
3. **Linked to:**
   - Wikipedia (everyone recognizes)
   - Library classification systems
   - Academic institution databases
   - National archives

4. **Stable Q-numbers** - Once assigned, never change

### Compared to Alternatives:

| System | Categories | Stability | Global Recognition | WikiData Mapped |
|--------|-----------|-----------|-------------------|-----------------|
| **WikiData Fields** | ~1,000 | High | ✅ Yes | Native |
| Dewey Decimal | ~10,000 | Very High | ✅ Yes | ✅ Partial |
| Library of Congress | ~50,000 | High | ✅ Yes (US/UK) | ✅ Partial |
| Schema.org | ~800 | Medium | ✅ Yes | ✅ Yes |
| DBpedia | ~100,000 | Medium | Medium | ✅ Yes |

**Verdict:** WikiData conceptual categories are **perfect** for your use case:
- Stable (fields of study don't disappear)
- Recognized (linked to major classification systems)
- Right granularity (~1,000 categories, not millions)
- Excludes biological/chemical taxonomy automatically

---

## ✅ Recommended Implementation

### Download WikiData Conceptual Categories

Update the script to query:
- Q2267705 (Field of study) ⭐
- Q11862829 (Academic discipline) ⭐
- Q1936384 (Branch of science) ⭐

With filters to exclude:
- Q16521 (Taxon) - No biological species
- Q11173 (Chemical compound) - No molecules
- Q5 (Human) - No individual people
- Q515 (City) - No geographic entities
- Q431289 (Brand) - No commercial products

**Expected:** ~800-1,200 stable conceptual categories

---

## Updated Script

Would you like me to update the download script with:

1. **Better root categories** (Q2267705, Q11862829, Q1936384)
2. **Stronger exclusion filters** (no species, chemicals, people, places)
3. **Rate limiting fixes** (slower queries, better backoff)
4. **Fallback to curated lists** if SPARQL times out

This would give you a **stable, globally-recognized conceptual taxonomy** at the right granularity level (~800 categories) that won't include thousands of phyla and species!
