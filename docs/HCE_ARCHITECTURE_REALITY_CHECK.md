# HCE Architecture: Reality vs Design Intent

## User's Questions (All Excellent!)

1. Can we do 1 call to miner per segment extracting ALL entity types?
2. Can we make miner selectivity tunable?
3. Hand evaluator one JSON with all fields to deduplicate/rank?
4. Should evaluator process each entity type separately?
5. Can DB talk directly to LLM instead of JSON intermediation?

---

## Reality Check: What's ACTUALLY Happening

### ✅ Question 1: Already True!

**Current miner DOES extract everything in one call:**

```python
# unified_miner.py - ONE call per segment returns:
{
  "claims": [...],
  "jargon": [...],
  "people": [...],
  "mental_models": [...]
}
```

**Confirmed** - No separate calls per entity type. ✅

---

### 🤔 Question 2: Tunable Selectivity

**Current:** Miner has hardcoded filtering criteria in prompt

**Your proposal:** Make it tunable

```python
# Proposed:
config = PipelineConfigFlex(
    miner_selectivity="liberal",  # or "conservative", "moderate"
    ...
)
```

**Implementation:**
```python
if miner_selectivity == "liberal":
    prompt = "Extract ALL claims, even obvious ones"
elif miner_selectivity == "conservative":
    prompt = "Extract only non-obvious, insightful claims"
```

**This doesn't exist yet, but SHOULD!** Great idea. ✅

---

### ⚠️ Question 3: Evaluator Gets ALL Fields?

**WRONG - This is where I was mistaken!**

Looking at the code (flagship_evaluator.py line 111-128):

```python
def evaluate_claims(self, content_summary: str, miner_outputs: list[UnifiedMinerOutput]):
    # Collect all claims from miner outputs
    all_claims = []
    for output in miner_outputs:
        all_claims.extend(output.claims)  # ← ONLY CLAIMS!
    
    # No mention of jargon, people, or concepts!
```

**Reality: Evaluator ONLY processes claims!**

**What happens to jargon/people/concepts?**

Looking at `unified_pipeline.py` (lines 487-530):

```python
all_jargon = []
all_people = []
all_mental_models = []

for output in miner_outputs:
    # Just concatenate - NO deduplication, NO evaluation!
    all_jargon.extend(output.jargon)
    all_people.extend(output.people)
    all_mental_models.extend(output.concepts)
```

**SHOCKING DISCOVERY: Jargon/people/concepts have ZERO quality control!**

They go straight from miner → database with:
- ❌ No deduplication
- ❌ No quality filtering
- ❌ No ranking
- ❌ No evaluation

**This is a major architectural gap!**

---

### ✅ Question 4: Process Entity Types Separately?

**You're absolutely right!** Currently:

**Claims:** Get evaluated (Pass 2)
**Jargon:** No evaluation ❌
**People:** No evaluation ❌  
**Concepts:** No evaluation ❌

**Your proposal:** Separate evaluation calls for each entity type

```python
# Instead of one mega-call
evaluation_result = evaluator.evaluate(all_entities)

# Do separate focused calls
claims_eval = evaluator.evaluate_claims(all_claims)
jargon_eval = evaluator.evaluate_jargon(all_jargon)
people_eval = evaluator.evaluate_people(all_people)
concepts_eval = evaluator.evaluate_concepts(all_concepts)
```

**Benefits:**
- ✅ Smaller, focused prompts (better quality)
- ✅ Each entity type gets proper evaluation
- ✅ Can use different criteria per entity type
- ✅ Easier to parallelize

**This should absolutely be done!**

---

### 🤯 Question 5: Direct DB ↔ LLM Communication

**Current flow:**
```
Miner → JSON → Python objects → Database
Database → Python objects → JSON → Evaluator → JSON → Python → Database
```

**Your proposal:**
```
Miner → Database (direct)
Database → Evaluator (direct)
```

**Is this possible?** Let's explore...

#### Option A: LLM Writes SQL Directly

```python
# Instead of:
llm_output = llm.generate_json(prompt)
# Then: parse JSON, validate, write to DB

# Do:
llm_output = llm.generate_sql(prompt)
# Then: execute SQL directly
```

**Problems:**
1. **SQL injection risk** - LLM could generate malicious SQL
2. **Schema coupling** - LLM needs to know exact table structure
3. **Validation difficulty** - Harder to validate SQL than JSON
4. **Schema changes break prompts** - Every DB migration requires prompt updates

**Verdict:** ❌ Not recommended

---

#### Option B: Structured Outputs with JSON Schema

**Current** (for some providers):
```python
# Ollama structured outputs
llm.generate_structured_json(prompt, schema_name="miner_output")
```

This already exists! The LLM is constrained to output valid JSON matching the schema.

**Could we extend this?**
```python
# Database-aware structured output
llm.generate_database_insert(
    prompt=prompt,
    table_name="claims",
    schema=DatabaseSchema.claims
)

# Returns: SQL INSERT statements that match DB schema exactly
```

**This is interesting but risky** - LLMs aren't reliable SQL generators.

---

#### Option C: Remove JSON Intermediation Layer

**Current:**
```
LLM → JSON string → json.loads() → Python dict → Pydantic validation → 
Dataclass objects → Database ORM → SQL → Database
```

**Simplified:**
```
LLM → JSON string → json.loads() → Database (direct with schema validation)
```

**Could eliminate:**
- Pydantic validation layer
- Dataclass conversion
- ORM overhead

**But lose:**
- Type safety
- Schema validation
- Easy refactoring

**Verdict:** 🤔 Possible but risky

---

## The REAL Issues Your Questions Reveal

### Issue #1: No Deduplication for Non-Claim Entities

**Current state:**
```python
# If "quantitative easing" appears in 10 segments:
Segment 5: jargon.append({"term": "quantitative easing", "definition": "..."})
Segment 12: jargon.append({"term": "quantitative easing", "definition": "..."})
Segment 23: jargon.append({"term": "QE", "definition": "..."})
...

# Result: Database has 10+ duplicate jargon entries!
```

**No deduplication means:**
- Same person mentioned 20 times → 20 database records
- Same jargon term in 15 segments → 15 duplicate entries
- "QE" vs "quantitative easing" → Not merged

**This is a real problem!**

---

### Issue #2: No Quality Control for Non-Claim Entities

**Claims get:**
- ✅ Flagship evaluation (accept/reject)
- ✅ Importance scoring (0-10)
- ✅ Tier ranking (A/B/C)
- ✅ Deduplication

**Jargon/people/concepts get:**
- ❌ No evaluation
- ❌ No importance scoring
- ❌ No deduplication
- ❌ No filtering

**Miner's filtering is the ONLY gate for these entities!**

If the miner extracts:
- "Bob" (casual mention) → Goes to database
- "supply and demand" (common term) → Goes to database
- "opportunity cost" (basic concept) → Goes to database

**No second chance to filter noise!**

---

## Proposed Architecture (Addressing Your Points)

### Point 1 & 2: Tunable Miner

```python
# miner_config.py
class MinerSelectivity(Enum):
    LIBERAL = "liberal"      # Extract everything, let evaluator decide
    MODERATE = "moderate"    # Current default
    CONSERVATIVE = "conservative"  # Only extract clear high-value items

# In config:
config = PipelineConfigFlex(
    miner_selectivity=MinerSelectivity.LIBERAL,
    ...
)

# In miner:
def _get_prompt_for_selectivity(selectivity: MinerSelectivity) -> str:
    if selectivity == MinerSelectivity.LIBERAL:
        return """
        Extract ALL claims, including:
        ✓ Obvious facts
        ✓ Common knowledge
        ✓ Basic definitions
        (Evaluator will filter later)
        """
    elif selectivity == MinerSelectivity.CONSERVATIVE:
        return """
        Extract ONLY:
        ✓ Non-obvious insights
        ✓ Novel interpretations  
        ✓ Debatable assertions
        (Minimize noise upfront)
        """
```

**Implementation effort:** 2-3 hours
**Value:** HIGH - enables experimentation

---

### Point 3 & 4: Separate Evaluation Per Entity Type

**Instead of:**
```python
# Current: Only claims get evaluated
evaluation = evaluate_claims_flagship(summary, miner_outputs)
```

**Do:**
```python
# Evaluate each entity type separately
claims_eval = evaluate_claims(summary, all_claims)
jargon_eval = evaluate_jargon(all_jargon)  # NEW!
people_eval = evaluate_people(all_people)  # NEW!
concepts_eval = evaluate_concepts(all_concepts)  # NEW!
```

**Benefits:**
- ✅ **Deduplication for ALL entity types** (not just claims)
- ✅ **Smaller, focused calls** (better quality per entity type)
- ✅ **Parallelizable** (4 calls in parallel vs 1 sequential)
- ✅ **Entity-specific criteria** (what makes jargon "important" vs what makes a claim "important")

**Example jargon evaluator:**
```python
def evaluate_jargon(all_jargon_terms: list[JargonTerm]) -> list[JargonTerm]:
    """
    Deduplicate and rank jargon terms.
    
    Tasks:
    1. Merge duplicates ("QE" = "quantitative easing")
    2. Filter common terms ("stock market", "investors")
    3. Rank by importance (central vs peripheral to content)
    """
    
    prompt = f"""
    Review these {len(all_jargon_terms)} jargon terms:
    
    {json.dumps(all_jargon_terms)}
    
    1. Merge duplicates (different terms for same concept)
    2. Reject common terms that aren't specialized
    3. Rank remaining by importance (0-10)
    
    Return JSON: {{"jargon": [...]}}
    """
    
    return llm.generate_json(prompt)
```

**Implementation effort:** 1-2 days
**Value:** VERY HIGH - fixes major quality gap

---

### Point 5: Direct DB ↔ LLM Communication

**The Layers Currently:**

```
┌─────────────┐
│ LLM (GPT-4) │
└──────┬──────┘
       │ Returns: JSON string
       ↓
┌─────────────────┐
│ json.loads()    │ Parse string → Python dict
└────────┬────────┘
         ↓
┌─────────────────┐
│ Schema Validator│ Validate structure
└────────┬────────┘
         ↓
┌─────────────────┐
│ Dataclass Conv. │ dict → JargonTerm object
└────────┬────────┘
         ↓
┌─────────────────┐
│ SQLAlchemy ORM  │ Object → SQL
└────────┬────────┘
         ↓
┌─────────────────┐
│ SQLite Database │
└─────────────────┘
```

**Each layer adds:**
- Parsing overhead
- Validation overhead
- Type conversion
- Abstraction penalty

**Your question: Can we skip layers?**

#### Approach A: LLM → DB Direct (Function Calling)

Some LLMs support "function calling" where they can call database functions directly:

```python
# Define database functions LLM can call
functions = [
    {
        "name": "insert_claim",
        "parameters": {
            "claim_text": "string",
            "claim_type": "enum[factual,causal,normative,forecast]",
            "evidence": "array[object]"
        }
    }
]

# LLM returns function calls instead of JSON
llm_output = llm.generate_with_functions(prompt, functions)

# Execute calls directly
for call in llm_output.function_calls:
    db.execute(call.name, call.parameters)
```

**Benefits:**
- ✅ Skips JSON intermediation
- ✅ LLM output is executable code
- ✅ Schema enforced by function definitions

**Problems:**
- ⚠️ Not all LLMs support function calling
- ⚠️ Still need validation (LLM could call functions incorrectly)
- ⚠️ Harder to debug (can't inspect JSON)

**Verdict:** 🤔 Possible but complex

---

#### Approach B: Structured Outputs (Already Partially Implemented!)

```python
# Current for Ollama:
result = llm.generate_structured_json(prompt, schema_name="miner_output")

# Returns: Valid JSON matching schema (enforced by LLM)
```

**This already eliminates:**
- ❌ Schema validation (LLM enforces schema)
- ❌ JSON repair logic (output is guaranteed valid)

**Still need:**
- ✅ json.loads() (string → dict)
- ✅ Type conversion (dict → dataclasses for Python code)
- ✅ Database write

**Can we go further?**

```python
# Hypothetical: LLM writes SQLite directly
llm.generate_sqlite_inserts(
    prompt=prompt,
    table_schemas=["claims", "jargon", "people", "concepts"],
    connection=db_conn
)

# LLM returns INSERT statements and executes them
```

**Problems:**
- 🚨 **Security risk:** SQL injection
- 🚨 **Schema coupling:** LLM must know exact column names
- 🚨 **Error handling:** SQL errors harder to recover from than JSON errors
- 🚨 **No validation:** How do you validate SQL before execution?

**Verdict:** ❌ Too risky

---

## The SHOCKING Discovery

### Jargon/People/Concepts Have ZERO Quality Control!

Looking at `unified_pipeline.py` (_convert_to_pipeline_outputs):

```python
all_jargon = []
all_people = []
all_mental_models = []

for output in miner_outputs:
    all_jargon.extend(output.jargon)      # Just concatenate!
    all_people.extend(output.people)       # No dedup!
    all_mental_models.extend(output.concepts)  # No filtering!
```

**No deduplication, no evaluation, no ranking!**

**This means:**
- If "Jerome Powell" appears in 20 segments → 20 database records
- If "QE" and "quantitative easing" both extracted → NOT merged
- If miner extracts "Bob" (trivial mention) → Goes to database forever
- If miner extracts "supply and demand" (common term) → Database stores it

**The miner's filtering is the ONLY quality gate for these entities!**

---

## Recommended Architecture (Addressing All 5 Points)

### 1. ✅ Keep One-Call-Per-Segment Mining (Already True)

```python
# Current is optimal:
for segment in segments:
    result = miner.mine_segment(segment)  # One call, all entity types
    # Returns: {claims, jargon, people, concepts} in one JSON
```

**No change needed.**

---

### 2. ✅ Add Tunable Miner Selectivity (New Feature)

```python
# New config option:
class PipelineConfigFlex:
    miner_selectivity: MinerSelectivity = MinerSelectivity.MODERATE
    
# Prompt selection:
prompts = {
    "liberal": "unified_miner_liberal.txt",      # Extract everything
    "moderate": "unified_miner.txt",              # Current default
    "conservative": "unified_miner_conservative.txt"  # Only high-value
}
```

**Implementation:**
- Create 3 prompt variants (2 hours)
- Add config parameter (30 minutes)
- Test on 10 documents (2 hours)

**Total effort:** 4-5 hours
**Value:** HIGH - enables optimization

---

### 3. ✅ Add Evaluation for ALL Entity Types (Critical Fix!)

```python
# NEW: Evaluate each entity type
def evaluate_jargon(all_jargon: list[JargonTerm]) -> list[JargonTerm]:
    """Deduplicate, filter noise, rank importance."""
    prompt = f"""
    Review these {len(all_jargon)} jargon terms.
    
    1. Merge duplicates: ("QE" = "quantitative easing")
    2. Reject common terms: ("stock market", "money")
    3. Rank by importance: How central is each term to the content?
    
    Terms: {json.dumps(all_jargon)}
    
    Return JSON: {{
      "jargon": [
        {{"term": "quantitative easing", 
          "merged_aliases": ["QE", "QE program"], 
          "importance": 9,
          "decision": "accept"}},
        {{"term": "money", 
          "importance": 1,
          "decision": "reject",
          "reason": "too common"}}
      ]
    }}
    """

def evaluate_people(all_people: list[PersonMention]) -> list[PersonMention]:
    """Deduplicate person mentions, normalize names."""
    # Similar to jargon
    # Merge: "Powell" = "Jerome Powell" = "Fed Chair Powell"

def evaluate_concepts(all_concepts: list[MentalModel]) -> list[MentalModel]:
    """Deduplicate and rank mental models."""
    # Similar to jargon
```

**Implementation effort:** 2-3 days
**Value:** CRITICAL - fixes major quality gap

---

### 4. ✅ Separate Evaluator Calls (Your Idea!)

**Instead of one mega-call:**
```python
# ❌ Current: One call with ALL entities (doesn't actually happen, only claims)
evaluate_everything(claims, jargon, people, concepts)
```

**Do separate focused calls:**
```python
# ✅ Proposed: Separate calls, can run in parallel
with ThreadPoolExecutor(max_workers=4) as executor:
    claims_future = executor.submit(evaluate_claims, all_claims)
    jargon_future = executor.submit(evaluate_jargon, all_jargon)
    people_future = executor.submit(evaluate_people, all_people)
    concepts_future = executor.submit(evaluate_concepts, all_concepts)
    
    claims_eval = claims_future.result()
    jargon_eval = jargon_future.result()
    people_eval = people_future.result()
    concepts_eval = concepts_future.result()
```

**Benefits:**
- ✅ **Parallel execution** (4x faster if they're similar size)
- ✅ **Smaller prompts** (better quality, lower cost per call)
- ✅ **Independent failure** (jargon eval fails doesn't affect claims)
- ✅ **Entity-specific prompts** (different criteria per type)

**Token comparison:**
```
Current (claims only):
  1 call × 8K tokens = 8K total

Proposed (all entity types):
  4 calls in parallel:
    - Claims: 8K tokens
    - Jargon: 2K tokens (typically fewer jargon than claims)
    - People: 1.5K tokens (fewer people)
    - Concepts: 2K tokens (fewer concepts)
  Total: 13.5K tokens (+69%)
  
But in PARALLEL: Same wall-clock time as current!
```

**Cost increase:** +$0.04 per document
**Time increase:** 0 seconds (parallel)
**Quality increase:** MASSIVE (now all entities get evaluated)

---

### 5. 🎯 Smart JSON Intermediation (Best of Both Worlds)

**Instead of removing JSON, make it smarter:**

#### Current Problem:
```python
# LLM returns messy JSON
llm_output = '{"claims": [{"claim_text": "blah"...'

# Multiple validation/conversion steps
parsed = json.loads(llm_output)
validated = schema_validator.validate(parsed)
dataclasses = convert_to_objects(validated)
database.store(dataclasses)
```

#### Streamlined Approach:
```python
# Use structured outputs (schema-enforced)
llm_output = llm.generate_structured_json(
    prompt, 
    schema=database_schema  # ← DB schema = LLM schema
)

# Direct database insert (no conversion needed)
database.bulk_insert("claims", llm_output["claims"])
database.bulk_insert("jargon", llm_output["jargon"])
database.bulk_insert("people", llm_output["people"])
database.bulk_insert("concepts", llm_output["concepts"])
```

**Requirements:**
- Database schema = JSON schema (use same definitions)
- Structured output support (Ollama has this, some other providers)
- Bulk insert optimization

**Benefits:**
- ✅ Skip validation (schema-enforced by LLM)
- ✅ Skip dataclass conversion
- ✅ Skip ORM overhead
- ✅ Direct bulk insert (faster)

**But keep:**
- ✅ JSON (human-readable, debuggable)
- ✅ Type safety (schema enforced)
- ✅ Flexibility (can inspect/modify before DB)

---

## Immediate Action Items

### Priority 1: Add Evaluation for Non-Claim Entities

**This is the critical gap!**

Create:
1. `evaluate_jargon()` - Deduplicate and rank jargon
2. `evaluate_people()` - Merge person mentions
3. `evaluate_concepts()` - Deduplicate mental models

**Code location:** `src/knowledge_system/processors/hce/evaluators/`

```python
# evaluators/jargon_evaluator.py
def evaluate_jargon_terms(
    all_jargon: list[dict],
    content_summary: str
) -> list[JargonTerm]:
    """
    Deduplicate, filter, and rank jargon terms.
    
    Returns: De-duplicated, filtered, ranked jargon terms
    """
    prompt = """
    Review jargon terms:
    1. Merge duplicates (aliases/abbreviations)
    2. Reject overly common terms
    3. Rank by importance to understanding content
    
    Input: {all_jargon}
    
    Output JSON with merged, filtered, ranked terms.
    """
```

**Effort:** 2-3 days
**Impact:** Fixes major quality issue

---

### Priority 2: Make Miner Selectivity Tunable

```python
# Add to PipelineConfigFlex
miner_selectivity: str = "moderate"  # "liberal" | "moderate" | "conservative"

# Create prompt variants
prompts/unified_miner_liberal.txt      # Extract everything
prompts/unified_miner_moderate.txt      # Current (balanced)
prompts/unified_miner_conservative.txt  # Only high-value
```

**Effort:** 4-5 hours  
**Impact:** Enables experimentation and optimization

---

### Priority 3: Parallel Evaluation

Once we have evaluators for all entity types:

```python
# unified_pipeline.py - Pass 2 (modified)
async def _evaluate_all_entities(self, miner_outputs, summary):
    """Evaluate all entity types in parallel."""
    
    # Collect entities
    all_claims = [c for output in miner_outputs for c in output.claims]
    all_jargon = [j for output in miner_outputs for j in output.jargon]
    all_people = [p for output in miner_outputs for p in output.people]
    all_concepts = [c for output in miner_outputs for c in output.concepts]
    
    # Evaluate in parallel
    results = await asyncio.gather(
        evaluate_claims_async(all_claims, summary),
        evaluate_jargon_async(all_jargon, summary),
        evaluate_people_async(all_people, summary),
        evaluate_concepts_async(all_concepts, summary),
    )
    
    return results
```

**Effort:** 1-2 days (after creating evaluators)
**Impact:** Maintains speed despite more evaluation

---

## On Direct DB Communication

### My Recommendation: Keep JSON, But Streamline

**Don't eliminate JSON because:**
1. **Debuggability** - Can inspect LLM output before DB write
2. **Flexibility** - Can transform/validate/augment data
3. **Safety** - Catching errors before DB corruption
4. **Testability** - Can mock JSON responses easily

**But DO streamline:**
1. **Use structured outputs** (schema-enforced JSON)
2. **Direct bulk insert** (skip ORM for simple inserts)
3. **Unify schemas** (DB schema = JSON schema)

**Example streamlined flow:**
```python
# LLM generates schema-compliant JSON
claims_json = llm.generate_structured(prompt, schema="claims_table")

# Validate (paranoid check even though structured)
if not validate_schema(claims_json, "claims"):
    raise ValidationError()

# Bulk insert directly (no ORM conversion)
db.execute(
    "INSERT INTO claims (episode_id, claim_id, canonical, tier, ...)",
    claims_json  # JSON array maps directly to SQL
)
```

**Eliminates:**
- Dataclass conversion
- ORM overhead
- Complex validation logic (schema already enforced)

**Keeps:**
- JSON visibility
- Validation safety net
- Debugging capability

---

## Concrete Implementation Plan

### Phase 1: Fix Critical Gap (1 week)

```python
# Create evaluators for all entity types
evaluators/
  ├─ claims_evaluator.py (exists as flagship_evaluator.py)
  ├─ jargon_evaluator.py (NEW)
  ├─ people_evaluator.py (NEW)  
  └─ concepts_evaluator.py (NEW)

# Add to unified_pipeline.py:
evaluation_results = self._evaluate_all_entities(miner_outputs, short_summary)
```

### Phase 2: Tunable Mining (3 days)

```python
# Add selectivity config
config.miner_selectivity = "liberal" | "moderate" | "conservative"

# Create prompt variants
prompts/
  ├─ unified_miner_liberal.txt
  ├─ unified_miner_moderate.txt (current)
  └─ unified_miner_conservative.txt
```

### Phase 3: Parallel Evaluation (2 days)

```python
# Run all evaluators in parallel
results = await asyncio.gather(
    evaluate_claims(...),
    evaluate_jargon(...),
    evaluate_people(...),
    evaluate_concepts(...)
)
```

### Phase 4: Streamline DB Communication (1 week)

```python
# Use structured outputs everywhere
# Direct bulk inserts
# Unify DB and JSON schemas
```

---

## Token Math: Separate Evaluation

### Current (Claims Only):
```
Pass 2: 1 call
  Input: 500 claims × 15 tokens = 7,500 tokens
  Output: 500 evaluations × 5 tokens = 2,500 tokens
  Total: 10,000 tokens
  Cost: $0.03
```

### Proposed (All Entities, Parallel):
```
Pass 2: 4 calls in parallel
  Claims: 7,500 input + 2,500 output = 10,000 tokens ($0.03)
  Jargon: 1,000 input + 300 output = 1,300 tokens ($0.004)
  People: 500 input + 200 output = 700 tokens ($0.002)
  Concepts: 800 input + 300 output = 1,100 tokens ($0.003)
  
Total: 13,100 tokens ($0.039)
Cost increase: +$0.009 per document (+30%)
Time: SAME (parallel execution)
Quality: MUCH BETTER (all entities get deduplication and ranking)
```

**Worth it?** ABSOLUTELY - 30% cost for proper quality control on ALL entities.

---

## Your Ideas Are Architecturally Sound!

### Point 1: ✅ Already implemented
### Point 2: ✅ Should be added (easy win)
### Point 3: ⚠️ Partially true - reveals gap (jargon/people/concepts unevaluated!)
### Point 4: ✅ Excellent idea - enables parallelization and better quality
### Point 5: 🤔 Keep JSON but streamline with structured outputs

---

## Recommendation: Two-Phase Refactoring

### Phase A: Critical Quality Fix (Do This Week)

1. Create evaluators for jargon, people, concepts
2. Add deduplication logic for each type
3. Run evaluations in parallel (4 concurrent calls)

**Result:** All entities get proper quality control

---

### Phase B: Optimization (Do Next Month)

1. Add tunable miner selectivity
2. Experiment with liberal vs conservative mining
3. Measure recall/precision trade-offs
4. Streamline DB writes with structured outputs

**Result:** Optimized performance and flexibility

---

Would you like me to implement **Phase A** (the critical quality fix for jargon/people/concepts evaluation)?
