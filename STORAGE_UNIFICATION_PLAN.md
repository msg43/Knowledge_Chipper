# Storage Unification Plan: One Path, Full Features

## Current Problem

Your GUI uses a **simplified mining path** that discards valuable data:

```
❌ CURRENT GUI PATH (Inferior):
System2Orchestrator._process_mine()
  → Mines segments manually with _mine_single_segment()
  → Gets simple UnifiedMinerOutput objects
  → Calls store_mining_results() from hce_operations.py
  → Stores to SQLAlchemy ORM (Person, Concept, Jargon)
  → LOSES: Evidence spans, relations, claim evaluation, categories

✅ BETTER PATH (Already exists!):
UnifiedHCEPipeline.process()
  → Mines with mine_episode_unified() 
  → Evaluates claims with flagship evaluator
  → Builds rich PipelineOutputs with evidence, relations, categories
  → Saves with storage_sqlite.upsert_pipeline_outputs()
  → KEEPS: Everything!
```

## The Fix: Use UnifiedHCEPipeline in System2Orchestrator

The good news: **The full pipeline already exists!** You just need to use it.

## Implementation Plan

### Phase 1: Replace Mining Logic (2-3 hours)

**File:** `src/knowledge_system/core/system2_orchestrator.py`

**Change:** Replace manual segment mining with `UnifiedHCEPipeline.process()`

#### Current Code (Lines 391-496):
```python
async def _process_mine(self, episode_id, config, checkpoint, run_id):
    # Manual mining
    segments = self._parse_transcript_to_segments(transcript_text, episode_id)
    
    miner_outputs = []
    for i in range(start_segment, len(segments)):
        output = await self._mine_single_segment(segments[i], miner_model, run_id)
        miner_outputs.append(output)
    
    # Simple storage (LOSES DATA)
    from ..database.hce_operations import store_mining_results
    store_mining_results(self.db_service, episode_id, miner_outputs)
```

#### New Code:
```python
async def _process_mine(self, episode_id, config, checkpoint, run_id):
    # 1. Load transcript
    file_path = config.get("file_path")
    transcript_text = Path(file_path).read_text()
    
    # 2. Parse to segments
    segments = self._parse_transcript_to_segments(transcript_text, episode_id)
    
    # 3. Create EpisodeBundle
    from ..processors.hce.types import EpisodeBundle
    episode_bundle = EpisodeBundle(
        episode_id=episode_id,
        segments=segments
    )
    
    # 4. Initialize UnifiedHCEPipeline with config
    from ..processors.hce.config_flex import PipelineConfigFlex, StageModelConfig
    from ..processors.hce.unified_pipeline import UnifiedHCEPipeline
    
    miner_model = config.get("miner_model", "ollama:qwen2.5:7b-instruct")
    
    hce_config = PipelineConfigFlex(
        models=StageModelConfig(
            miner=miner_model,
            judge=miner_model,  # Can use same or different model
            flagship_judge=miner_model,
        )
    )
    
    pipeline = UnifiedHCEPipeline(hce_config)
    
    # 5. Process with full pipeline (mining + evaluation + categories)
    def progress_wrapper(step, percent, episode_id, current=None, total=None):
        if self.progress_callback:
            self.progress_callback(step, percent, episode_id, current, total)
    
    pipeline_outputs = pipeline.process(
        episode_bundle,
        progress_callback=progress_wrapper
    )
    
    # 6. Store rich PipelineOutputs to database
    from ..processors.hce.storage_sqlite import upsert_pipeline_outputs, open_db
    
    db_path = self._get_hce_database_path()  # Use HCE-specific DB
    conn = open_db(db_path)
    
    try:
        video_id = episode_id.replace("episode_", "")
        upsert_pipeline_outputs(
            conn,
            pipeline_outputs,
            episode_title=Path(file_path).stem,
            video_id=video_id
        )
        conn.commit()
        logger.info(f"✅ Stored full pipeline outputs: {len(pipeline_outputs.claims)} claims with evidence")
    finally:
        conn.close()
    
    # 7. Return rich results
    return {
        "status": "succeeded",
        "output_id": episode_id,
        "result": {
            "claims_extracted": len(pipeline_outputs.claims),
            "claims_tier_a": len([c for c in pipeline_outputs.claims if c.tier == "A"]),
            "claims_tier_b": len([c for c in pipeline_outputs.claims if c.tier == "B"]),
            "claims_tier_c": len([c for c in pipeline_outputs.claims if c.tier == "C"]),
            "jargon_extracted": len(pipeline_outputs.jargon),
            "people_extracted": len(pipeline_outputs.people),
            "mental_models_extracted": len(pipeline_outputs.concepts),
            "relations": len(pipeline_outputs.relations),
            "categories": len(pipeline_outputs.structured_categories),
        }
    }
```

### Phase 2: Database Consolidation (1 hour)

**Decision Point:** Should we:
- **Option A:** Use HCE SQLite DB exclusively (simpler)
- **Option B:** Keep main DB but sync from HCE DB (compatibility)

**Recommendation:** Option A - Use HCE SQLite DB as single source of truth

#### Update DatabaseService to point to HCE DB:
```python
# src/knowledge_system/database/service.py

def __init__(self, database_url: str | None = None):
    if database_url is None:
        # Use HCE database by default
        hce_db_path = Path.home() / ".skip_the_podcast" / "hce_pipeline.db"
        database_url = f"sqlite:///{hce_db_path}"
```

### Phase 3: Remove Vestigial Code (30 minutes)

**Files to deprecate:**
- `src/knowledge_system/database/hce_operations.py` - No longer needed
- Simple ORM models in `models.py` for HCE data - Use HCE schema instead

**Keep:**
- `storage_sqlite.py` - Primary storage layer
- `unified_pipeline.py` - Primary processing logic

### Phase 4: Update GUI Display (2 hours)

**Enhance results display to show new data:**

```python
# src/knowledge_system/gui/tabs/summarization_tab.py

def _emit_hce_analytics(self, result: dict):
    """Emit rich HCE analytics with new fields."""
    analytics = {
        "claims_total": result.get("claims_extracted", 0),
        "claims_tier_a": result.get("claims_tier_a", 0),
        "claims_tier_b": result.get("claims_tier_b", 0),
        "claims_tier_c": result.get("claims_tier_c", 0),
        "jargon": result.get("jargon_extracted", 0),
        "people": result.get("people_extracted", 0),
        "concepts": result.get("mental_models_extracted", 0),
        "relations": result.get("relations", 0),
        "categories": result.get("categories", 0),
    }
    
    self.hce_analytics_received.emit(analytics)
```

## Benefits of This Approach

### What You Get:
✅ **Evidence Spans** - Every claim has timestamped quotes  
✅ **Claim Evaluation** - Flagship LLM ranks claims A/B/C  
✅ **Relations** - Claims link to supporting/contradicting claims  
✅ **Categories** - WikiData-style topic classification  
✅ **Temporality Scoring** - Timeless vs time-sensitive claims  
✅ **Optimized Storage** - Bulk SQL inserts, not ORM overhead  
✅ **One Code Path** - Maintain one system, not two  

### For Your 5000 Podcast Goal:
- **Rich Claims Database** - Every claim has source quotes and timestamps
- **Knowledge Graph** - Relations between claims across episodes
- **Topic Organization** - Structured categories for discovery
- **Quality Filtering** - Tier A/B/C for focusing on best content
- **Temporal Analysis** - Identify evergreen vs dated content
- **Evidence Tracking** - Jump directly to source quote in transcript

## Migration Steps

### Step 1: Create Feature Branch
```bash
git checkout -b feature/unify-storage-layer
```

### Step 2: Implement Changes
1. Update `system2_orchestrator.py` to use `UnifiedHCEPipeline`
2. Point database to HCE SQLite DB
3. Update GUI analytics display
4. Test with sample transcripts

### Step 3: Validate
```bash
# Run test with full pipeline
python scripts/test_unified_pipeline.py

# Verify database has rich data
sqlite3 ~/.skip_the_podcast/hce_pipeline.db "
  SELECT 
    COUNT(*) as total_claims,
    COUNT(DISTINCT episode_id) as episodes,
    AVG(json_array_length(evidence_json)) as avg_evidence_per_claim
  FROM claims
"
```

### Step 4: Deploy
- Merge to main
- Update documentation
- Celebrate having ONE good system instead of TWO mediocre ones

## Timeline

| Phase | Time | Complexity |
|-------|------|------------|
| Phase 1: Use UnifiedHCEPipeline | 2-3 hours | Medium |
| Phase 2: Database consolidation | 1 hour | Low |
| Phase 3: Remove old code | 30 min | Low |
| Phase 4: GUI enhancements | 2 hours | Medium |
| **Total** | **5-7 hours** | **Worth it!** |

## Risk Mitigation

### Concern: "Will this break my existing data?"
**Answer:** No. We can:
1. Keep old DB as read-only archive
2. Migrate existing data to HCE schema
3. Run both in parallel during transition

### Concern: "Will GUI progress callbacks work?"
**Answer:** Yes! UnifiedHCEPipeline already has `progress_callback` parameter. Just wrap it:
```python
pipeline.process(episode, progress_callback=self.progress_callback)
```

### Concern: "What about checkpointing?"
**Answer:** UnifiedHCEPipeline doesn't have built-in checkpointing, but:
- Most transcripts process in <5 minutes anyway
- Can add checkpoint wrapper if needed
- Storage is atomic (all-or-nothing)

## Conclusion

You don't need two paths. You need **one excellent path**.

`UnifiedHCEPipeline` already does everything you want:
- Mines content
- Evaluates quality
- Captures evidence
- Links relations
- Categorizes topics
- Stores richly

Your GUI just needs to **use it** instead of reimplementing a worse version.

**Next Action:** Start with Phase 1 - update `_process_mine()` to use `UnifiedHCEPipeline`. Test with one transcript. If it works, continue with other phases.

