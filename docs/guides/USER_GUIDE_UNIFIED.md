# User Guide: Processing with Unified Pipeline

## Quick Start

### Processing a Transcript

1. Open GUI
2. Go to **Summarization** tab
3. Select transcript file(s)
4. Click **Start Processing**

The system will:
- ✅ Parse transcript into segments
- ✅ Mine ALL segments in parallel (3-8x faster!)
- ✅ Extract claims with evidence quotes
- ✅ Rank claims A/B/C by importance
- ✅ Identify people, jargon, mental models
- ✅ Find relations between claims
- ✅ Categorize topics
- ✅ Generate summary markdown

### Understanding Results

**Claims with Evidence:**
```markdown
## Claims (Tier A)

### The transformer architecture revolutionized NLP
**Type:** factual | **Tier:** A

**Evidence:**
- [00:01:15] "The transformer architecture, introduced in the 
'Attention Is All You Need' paper, revolutionized natural language 
processing."
```

**People Mentions:**
```markdown
## People Mentioned

- **Sam Altman** [00:00:00]: "CEO of OpenAI, recently announced GPT-4"
- **Geoffrey Hinton** [00:00:30]: "Godfather of deep learning, pioneered many techniques"
```

**Mental Models:**
```markdown
## Mental Models & Concepts

- **Backpropagation** [00:00:15]: Algorithm that enables neural networks to learn
- **Alignment** [00:01:00]: Ensuring AI pursues human values
```

**Relations:**
```markdown
## Claim Relations

- claim_001 **supports** claim_003
  - Both discuss transformer benefits
- claim_005 **contradicts** claim_007
  - Different views on AI timeline
```

**Categories:**
```markdown
## Categories

- **Artificial Intelligence** [Q11660] (confidence: 0.95)
- **Machine Learning** [Q2539] (confidence: 0.88)
- **Natural Language Processing** [Q30642] (confidence: 0.82)
```

## Performance

### Parallel Processing

The system automatically uses multiple workers based on your hardware:

| Your Mac | Workers | Expected Speed |
|----------|---------|----------------|
| M2 Ultra | 8 | 100 segments in ~2 min |
| M2 Max | 6 | 100 segments in ~2.5 min |
| M2 Pro | 4 | 100 segments in ~4 min |
| M1/M2 | 3 | 100 segments in ~5 min |

### Manual Control

To force sequential (for debugging):
```python
# In settings.yaml or config
mining:
  max_workers: 1
  enable_parallel: false
```

## Database

All data stored in: `~/Library/Application Support/SkipThePodcast/unified_hce.db`

### Querying Claims

**Get all Tier A claims:**
```sql
SELECT canonical, tier, first_mention_ts
FROM claims
WHERE tier = 'A'
ORDER BY json_extract(scores_json, '$.importance') DESC;
```

**Get claims with evidence:**
```sql
SELECT 
  c.canonical,
  c.tier,
  COUNT(e.seq) as evidence_count
FROM claims c
LEFT JOIN evidence_spans e ON c.claim_id = e.claim_id
GROUP BY c.claim_id
HAVING evidence_count > 0
ORDER BY evidence_count DESC;
```

**Get claims by episode:**
```sql
SELECT canonical, tier, first_mention_ts
FROM claims
WHERE episode_id = 'episode_xyz'
ORDER BY tier, first_mention_ts;
```

### Querying Evidence

**Get evidence for a claim:**
```sql
SELECT 
  e.t0,
  e.t1,
  e.quote,
  e.context_text
FROM evidence_spans e
WHERE e.episode_id = 'episode_xyz' 
  AND e.claim_id = 'claim_001'
ORDER BY e.seq;
```

**Get all evidence with timestamps:**
```sql
SELECT 
  c.canonical as claim,
  e.t0,
  e.t1,
  e.quote
FROM claims c
JOIN evidence_spans e ON c.claim_id = e.claim_id
WHERE c.episode_id = 'episode_xyz'
ORDER BY e.t0;
```

### Querying Relations

**Get all claim relations:**
```sql
SELECT 
  sc.canonical as source,
  r.type,
  tc.canonical as target,
  r.strength,
  r.rationale
FROM relations r
JOIN claims sc ON r.source_claim_id = sc.claim_id
JOIN claims tc ON r.target_claim_id = tc.claim_id
WHERE r.episode_id = 'episode_xyz';
```

**Get supporting claims:**
```sql
SELECT 
  sc.canonical as supporting_claim,
  tc.canonical as main_claim
FROM relations r
JOIN claims sc ON r.source_claim_id = sc.claim_id
JOIN claims tc ON r.target_claim_id = tc.claim_id
WHERE r.type = 'supports'
  AND r.episode_id = 'episode_xyz';
```

### Querying People

**Get all people mentioned:**
```sql
SELECT 
  name,
  t0,
  context_quote
FROM people
WHERE episode_id = 'episode_xyz'
ORDER BY t0;
```

**Get people by type:**
```sql
SELECT 
  name,
  entity_type,
  context_quote
FROM people
WHERE episode_id = 'episode_xyz'
  AND entity_type = 'person'
ORDER BY name;
```

### Querying Categories

**Get episode categories:**
```sql
SELECT 
  category_name,
  wikidata_qid,
  coverage_confidence,
  frequency_score
FROM structured_categories
WHERE episode_id = 'episode_xyz'
ORDER BY coverage_confidence DESC;
```

### Cross-Episode Queries

**Find claims across all episodes:**
```sql
SELECT 
  e.title as episode,
  c.canonical,
  c.tier
FROM claims c
JOIN episodes e ON c.episode_id = e.episode_id
WHERE c.canonical LIKE '%artificial intelligence%'
ORDER BY e.recorded_at DESC;
```

**Find most mentioned people:**
```sql
SELECT 
  normalized as person,
  COUNT(*) as mention_count
FROM people
GROUP BY normalized
ORDER BY mention_count DESC
LIMIT 20;
```

**Find most common categories:**
```sql
SELECT 
  category_name,
  COUNT(*) as episode_count,
  AVG(coverage_confidence) as avg_confidence
FROM structured_categories
GROUP BY category_name
ORDER BY episode_count DESC
LIMIT 20;
```

## Troubleshooting

### "Processing seems slow"

Check if parallel processing is enabled:
```bash
# Check unified database
sqlite3 ~/Library/Application\ Support/SkipThePodcast/unified_hce.db "
  SELECT episode_id, COUNT(*) as claims 
  FROM claims 
  GROUP BY episode_id
"
```

Verify in logs:
```
🔧 HCE Config: miner=ollama:qwen2.5:7b-instruct, parallel=auto
```

If you see `parallel=1`, it's running sequentially.

### "Not seeing evidence spans"

Evidence spans are stored separately. Use JOIN:
```sql
SELECT 
  c.canonical,
  COUNT(e.seq) as evidence_count
FROM claims c
LEFT JOIN evidence_spans e ON c.claim_id = e.claim_id
GROUP BY c.claim_id;
```

### "Database file not found"

The unified database should be at:
```
~/Library/Application Support/SkipThePodcast/unified_hce.db
```

If missing, run migration:
```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 scripts/migrate_to_unified_schema.py
```

### "Want to reset everything"

**Backup first!**
```bash
cp ~/Library/Application\ Support/SkipThePodcast/unified_hce.db \
   ~/unified_hce.db.backup
```

**Clear episode:**
```sql
sqlite3 ~/Library/Application\ Support/SkipThePodcast/unified_hce.db "
  DELETE FROM claims WHERE episode_id = 'episode_xyz';
  DELETE FROM people WHERE episode_id = 'episode_xyz';
  DELETE FROM concepts WHERE episode_id = 'episode_xyz';
  DELETE FROM jargon WHERE episode_id = 'episode_xyz';
  DELETE FROM episodes WHERE episode_id = 'episode_xyz';
"
```

Note: Cascading deletes handle related data automatically.

### "Progress bar stuck"

Check logs for errors:
```bash
tail -f logs/knowledge_system.log
```

Common issues:
- LLM service not running (Ollama)
- Out of memory (reduce max_workers)
- Network issues (if using cloud LLM)

### "Claims missing context"

Context quotes are populated during mining. Check:
```sql
SELECT 
  name,
  context_quote
FROM people
WHERE episode_id = 'episode_xyz'
  AND context_quote IS NOT NULL;
```

If empty, the mining may have failed or the LLM didn't extract context.

## Advanced Usage

### Custom Worker Count

```python
from src.knowledge_system.core.system2_orchestrator import System2Orchestrator

orchestrator = System2Orchestrator()
job_id = orchestrator.create_job(
    "mine",
    "episode_custom",
    config={
        "file_path": "transcript.txt",
        "max_workers": 6,  # Custom worker count
        "enable_parallel_processing": True,
    }
)
```

### Progress Callbacks

```python
def my_progress_callback(step, percent, episode_id, current=None, total=None):
    print(f"{step}: {percent}% - {episode_id}")
    if current and total:
        print(f"  Progress: {current}/{total}")

orchestrator = System2Orchestrator(progress_callback=my_progress_callback)
```

### Direct Pipeline Usage

```python
from src.knowledge_system.processors.hce.unified_pipeline import UnifiedHCEPipeline
from src.knowledge_system.processors.hce.config_flex import PipelineConfigFlex, StageModelConfig
from src.knowledge_system.processors.hce.types import EpisodeBundle, Segment

# Create config
config = PipelineConfigFlex(
    models=StageModelConfig(
        miner="ollama:qwen2.5:7b-instruct",
        judge="ollama:qwen2.5:7b-instruct",
        flagship_judge="ollama:qwen2.5:7b-instruct",
    ),
    max_workers=4,
    enable_parallel_processing=True,
)

# Create episode bundle
episode = EpisodeBundle(
    episode_id="my_episode",
    segments=[
        Segment(segment_id="seg_001", text="...", t0="00:00:00", t1="00:00:30"),
        # ... more segments
    ]
)

# Process
pipeline = UnifiedHCEPipeline(config)
outputs = pipeline.process(episode)

# Access results
print(f"Claims: {len(outputs.claims)}")
print(f"Evidence: {sum(len(c.evidence) for c in outputs.claims)}")
print(f"Relations: {len(outputs.relations)}")
```

## Tips & Best Practices

1. **Let it run in parallel** - Don't force sequential unless debugging
2. **Check evidence spans** - They provide crucial context for claims
3. **Use tier filtering** - Focus on Tier A claims for most important insights
4. **Explore relations** - They show how claims connect and support each other
5. **Review categories** - They help organize and discover themes
6. **Query across episodes** - Find patterns and recurring themes
7. **Backup before experiments** - Copy the database before trying risky queries

## Getting Help

- **Architecture:** See `docs/ARCHITECTURE_UNIFIED.md`
- **Implementation:** See `UNIFICATION_MASTER_PLAN.md`
- **Rollback:** See `_deprecated/README.md`
- **Issues:** Check logs in `logs/knowledge_system.log`

## Changelog

### v2.0.0-unified (2025-10-23)
- ✅ Parallel processing (3-8x faster)
- ✅ Evidence spans with timestamps
- ✅ Claim evaluation (A/B/C tiers)
- ✅ Relations between claims
- ✅ Structured categories
- ✅ Context quotes for entities
- ✅ Single unified database
- ✅ Rich markdown export

### v1.x (legacy)
- Sequential processing
- Simple claim extraction
- No evidence spans
- No relations
- No categories
- Dual storage paths
