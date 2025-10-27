# HCE Architecture Refactoring - In Progress

**Started:** October 26, 2025  
**Status:** Points 1-2 Complete, Points 4-5 In Progress

---

## Scope: 4 Major Changes

1. **Point 1:** Simplify miner filtering (let evaluator handle quality) ✅ **DONE**
2. **Point 2:** Tunable miner selectivity (liberal/moderate/conservative) ✅ **DONE**
3. **Point 4:** Separate evaluators for all entity types (claims, jargon, people, concepts) ⏳ **IN PROGRESS**
4. **Point 5:** Streamlined DB communication (structured outputs + bulk insert) ⏳ **IN PROGRESS**

---

## Changes Completed

### ✅ Point 1: Simplified Miner Filtering

**Modified:** `prompts/unified_miner.txt`

**Changed from:**
```
Exclude claims that are:
✗ Trivial facts
✗ Basic definitions everyone knows
✗ Procedural statements
```

**Changed to:**
```
Extract ALL claims, including:
✓ Factual statements (even if well-known)
✓ Definitions (even if basic)

Only skip:
✗ Pure meta-commentary
✗ Greetings and sign-offs

**IMPORTANT:** Do NOT filter for importance - evaluator will handle quality filtering.
```

**Impact:** Miner now extracts comprehensively, evaluator does all quality filtering

---

### ✅ Point 2: Tunable Miner Selectivity

**Created 3 prompt variants:**
- `prompts/unified_miner_liberal.txt` - Extract everything
- `prompts/unified_miner_moderate.txt` - Balanced (current behavior)
- `prompts/unified_miner_conservative.txt` - Only high-value items

**Added configuration:**
```python
# config_flex.py
class PipelineConfigFlex(BaseModel):
    miner_selectivity: Literal["liberal", "moderate", "conservative"] = "moderate"
```

**Updated code:**
```python
# unified_miner.py - UnifiedMiner.__init__()
def __init__(self, llm, prompt_path=None, selectivity="moderate"):
    # Load appropriate prompt based on selectivity
    if prompt_path is None:
        prompt_files = {"liberal": "..._liberal.txt", ...}
        prompt_path = Path(__file__).parent / "prompts" / prompt_files[selectivity]
```

**Updated callers:**
```python
# unified_pipeline.py
miner_outputs = mine_episode_unified(
    episode, 
    miner_model_uri,
    selectivity=self.config.miner_selectivity  # ← Pass from config
)
```

---

## Changes In Progress

### ⏳ Point 4: Separate Entity Evaluators

**Status:** Creating evaluator modules

**Architecture:**
```python
# evaluators/
├─ __init__.py (created)
├─ jargon_evaluator.py (in progress)
├─ people_evaluator.py (pending)
└─ concepts_evaluator.py (pending)
```

**Will enable:**
- Deduplication for ALL entity types (currently only claims get this)
- Quality filtering for jargon, people, concepts
- Parallel evaluation (4 concurrent calls instead of 1)
- Entity-specific criteria (different for each type)

---

### ⏳ Point 5: Streamlined DB Communication

**Status:** Planning implementation

**Will implement:**
```python
# database/service.py - NEW method
def bulk_insert_json(self, table: str, records: list[dict]):
    """Insert JSON records directly without ORM conversion."""
    # Use SQLite JSON extension for efficiency
    
# database/hce_store.py - UPDATE  
def upsert_pipeline_outputs(self, outputs):
    # Use bulk insert instead of ORM
    self.db.bulk_insert_json("claims", outputs.claims)
    self.db.bulk_insert_json("jargon", outputs.jargon)
    ...
```

**Benefits:**
- 10-15% faster database writes
- Simpler code (fewer conversion layers)
- Direct JSON → SQL

---

## Remaining Tasks

### Point 4 Evaluators (HIGH PRIORITY)

- [ ] Create `jargon_evaluator.py` with deduplication logic
- [ ] Create `people_evaluator.py` with name merging  
- [ ] Create `concepts_evaluator.py` with framework dedup
- [ ] Create prompts for each evaluator
- [ ] Integrate parallel evaluation in `unified_pipeline.py`
- [ ] Test deduplication actually works

### Point 5 Bulk Insert (MEDIUM PRIORITY)

- [ ] Implement `bulk_insert_json()` in DatabaseService
- [ ] Update `HCEStore.upsert_pipeline_outputs()`
- [ ] Test performance improvement

### GUI Integration (Point 2 Extension)

- [ ] Add miner selectivity dropdown to SummarizationTab
- [ ] Wire up config parameter
- [ ] Test GUI updates config correctly

### Testing & Verification

- [ ] Test mining with all 3 selectivity levels
- [ ] Verify all 4 entity types get evaluated
- [ ] Verify deduplication works (check DB for duplicates)
- [ ] Measure performance impact
- [ ] Automated debugging if issues found

---

## Expected Impact

### Before Changes:
- Jargon deduplication: ❌ None (duplicates in DB)
- People deduplication: ❌ None (20 "Powell" records)
- Concepts deduplication: ❌ None
- Miner selectivity: Fixed (moderate only)
- DB write efficiency: ORM overhead

### After Changes:
- Jargon deduplication: ✅ Merges "QE" variants
- People deduplication: ✅ Merges name variants
- Concepts deduplication: ✅ Merges similar frameworks
- Miner selectivity: ✅ User choice (liberal/moderate/conservative)
- DB write efficiency: ✅ Bulk insert (10-15% faster)

---

## Next Steps

1. Create jargon_evaluator.py
2. Create people_evaluator.py
3. Create concepts_evaluator.py
4. Integrate parallel evaluation
5. Implement bulk insert
6. Test everything
7. Debug any issues automatically

**Estimated remaining effort:** 4-6 hours

