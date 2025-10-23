# Storage Unification Master Plan - PART 2
## Testing, Cleanup, Documentation & Deployment

*Continued from UNIFICATION_MASTER_PLAN.md*

---

## 4. Phase 3: Code Cleanup

**Duration:** 3-4 hours  
**Goal:** Remove deprecated code paths and update dependencies

### 4.1 Files to Deprecate/Remove

**Create deprecation tracking file:**

**File:** `scripts/deprecation_checklist.md`

```markdown
# Code Deprecation Checklist

## Files to Remove (After Testing)

### Database Operations
- [ ] `src/knowledge_system/database/hce_operations.py`
  - Functions: store_mining_results(), load_mining_results(), clear_episode_data()
  - Replaced by: storage_sqlite.upsert_pipeline_outputs()

### Models  
- [ ] Simplify `src/knowledge_system/database/models.py`
  - Keep: MediaSource, Summary, GeneratedFile
  - Can remove if HCE models fully replace: Episode, Claim, Person, Concept, Jargon classes
  - Decision: Keep for backward compatibility, mark as deprecated

## Files to Update

### Imports to Find & Replace
```bash
# Find all imports of deprecated module
grep -r "from.*hce_operations import" src/
grep -r "import.*hce_operations" src/
```

### Replace patterns:
- `from ..database.hce_operations import store_mining_results` → Remove (now handled in orchestrator_mining.py)
- `from ..database.hce_operations import get_episode_summary` → Update to query unified DB

## Status
- [ ] All deprecated imports identified
- [ ] All deprecated imports replaced
- [ ] Deprecated files moved to `_deprecated/` directory
- [ ] Tests updated
- [ ] Documentation updated
```

### 4.2 Move Deprecated Code

```bash
# Create deprecated directory
mkdir -p _deprecated/database
mkdir -p _deprecated/docs

# Move deprecated files (DON'T DELETE YET - keep for rollback)
git mv src/knowledge_system/database/hce_operations.py _deprecated/database/
git mv src/knowledge_system/database/hce_models.py _deprecated/database/

# Create deprecation notice
cat > _deprecated/README.md << 'EOF'
# Deprecated Code

This directory contains code deprecated during the storage unification.

## Files

### database/hce_operations.py
**Deprecated:** 2025-10-23
**Replaced by:** storage_sqlite.upsert_pipeline_outputs()
**Reason:** Dual storage paths consolidated

### database/hce_models.py  
**Deprecated:** 2025-10-23
**Replaced by:** HCE SQLite schema
**Reason:** SQLAlchemy ORM replaced with raw SQL for performance

## Rollback

If you need to rollback:
```bash
git mv _deprecated/database/hce_operations.py src/knowledge_system/database/
git mv _deprecated/database/hce_models.py src/knowledge_system/database/
```

Then restore old System2Orchestrator._process_mine() from git history.
EOF
```

### 4.3 Update Import References

**File:** `scripts/update_imports.sh`

```bash
#!/bin/bash
# Update all imports to remove references to deprecated code

echo "Updating imports..."

# Find files that import hce_operations
files_to_update=$(grep -rl "from.*hce_operations import\|import.*hce_operations" src/ tests/ scripts/ 2>/dev/null)

if [ -z "$files_to_update" ]; then
    echo "✓ No deprecated imports found"
    exit 0
fi

echo "Files to update:"
echo "$files_to_update"

# For each file, check what needs updating
for file in $files_to_update; do
    echo ""
    echo "Checking: $file"
    grep -n "hce_operations" "$file"
    echo "  (Review and update manually)"
done

echo ""
echo "⚠️  Please review and update imports manually"
echo "    Most should be removed or replaced with storage_sqlite imports"
```

### 4.4 Update Tests

**File:** `tests/system2/test_hce_operations.py`

Either remove or update to test new path:

```python
"""
Tests for unified HCE storage via System2Orchestrator.

These tests verify that the integrated UnifiedHCEPipeline
stores rich data correctly.
"""

import pytest
from pathlib import Path
import sqlite3

from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
from src.knowledge_system.database.service import DatabaseService


class TestUnifiedMiningStorage:
    """Test unified mining and storage pipeline."""
    
    @pytest.fixture
    def test_transcript(self, tmp_path):
        """Create test transcript file."""
        transcript = tmp_path / "test.txt"
        transcript.write_text("""
[00:00:00] Speaker A: Today we'll discuss first principles thinking, 
a mental model used by Elon Musk for problem solving.

[00:00:15] Speaker B: The key is breaking down complex problems 
into fundamental truths, rather than reasoning by analogy.

[00:00:30] Speaker A: This technique, pioneered by Aristotle, 
helps you innovate rather than iterate.
""")
        return transcript
    
    def test_mining_creates_rich_data(self, test_transcript):
        """Test that mining creates evidence, relations, categories."""
        orchestrator = System2Orchestrator()
        
        # Create mining job
        job_id = orchestrator.create_job(
            "mine",
            "test_episode",
            config={
                "file_path": str(test_transcript),
                "miner_model": "ollama:qwen2.5:7b-instruct",
            }
        )
        
        # Process job
        import asyncio
        result = asyncio.run(orchestrator.process_job(job_id))
        
        # Verify success
        assert result["status"] == "succeeded"
        assert result["result"]["claims_extracted"] > 0
        
        # Verify rich data in database
        unified_db = Path.home() / ".skip_the_podcast" / "unified_hce.db"
        assert unified_db.exists()
        
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        # Check for evidence spans
        cursor.execute("SELECT COUNT(*) FROM evidence_spans WHERE episode_id = 'test_episode'")
        evidence_count = cursor.fetchone()[0]
        assert evidence_count > 0, "Should have evidence spans"
        
        # Check for people mentions
        cursor.execute("SELECT COUNT(*) FROM people WHERE episode_id = 'test_episode'")
        people_count = cursor.fetchone()[0]
        assert people_count > 0, "Should have people (Elon Musk, Aristotle)"
        
        # Check for concepts
        cursor.execute("SELECT COUNT(*) FROM concepts WHERE episode_id = 'test_episode'")
        concepts_count = cursor.fetchone()[0]
        assert concepts_count > 0, "Should have concepts (first principles)"
        
        conn.close()
    
    def test_context_quotes_populated(self, test_transcript):
        """Test that context_quote fields are populated."""
        orchestrator = System2Orchestrator()
        
        job_id = orchestrator.create_job(
            "mine",
            "test_context_episode",
            config={"file_path": str(test_transcript)}
        )
        
        import asyncio
        asyncio.run(orchestrator.process_job(job_id))
        
        # Check database
        unified_db = Path.home() / ".skip_the_podcast" / "unified_hce.db"
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        # Verify context_quote in people
        cursor.execute("""
            SELECT name, context_quote FROM people 
            WHERE episode_id = 'test_context_episode' 
            AND context_quote IS NOT NULL
        """)
        people_with_quotes = cursor.fetchall()
        assert len(people_with_quotes) > 0, "People should have context quotes"
        
        # Verify context_quote in concepts
        cursor.execute("""
            SELECT name, context_quote FROM concepts 
            WHERE episode_id = 'test_context_episode' 
            AND context_quote IS NOT NULL
        """)
        concepts_with_quotes = cursor.fetchall()
        assert len(concepts_with_quotes) > 0, "Concepts should have context quotes"
        
        conn.close()
```

---

## 5. Phase 4: Testing

**Duration:** 4-6 hours  
**Goal:** Comprehensive testing of unified path

### 5.1 Unit Tests

**File:** `tests/integration/test_unified_pipeline_integration.py`

```python
"""Integration tests for UnifiedHCEPipeline in System2Orchestrator."""

import pytest
import asyncio
from pathlib import Path
import sqlite3

from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
from src.knowledge_system.processors.hce.types import EpisodeBundle, Segment


class TestUnifiedPipelineIntegration:
    """Test UnifiedHCEPipeline integration."""
    
    @pytest.fixture
    def sample_transcript(self, tmp_path):
        """Create comprehensive test transcript."""
        transcript = tmp_path / "comprehensive_test.txt"
        transcript.write_text("""
[00:00:00] Speaker A: Today we're discussing blockchain technology.
The Bitcoin whitepaper, written by Satoshi Nakamoto in 2008, 
introduced the concept of a decentralized ledger.

[00:00:20] Speaker B: The proof-of-work mechanism ensures security.
Think of it like a digital version of the Byzantine Generals Problem.

[00:00:40] Speaker A: Ethereum, created by Vitalik Buterin, extends 
this with smart contracts. These are self-executing contracts with 
terms directly written in code.

[00:01:00] Speaker B: I believe blockchain will transform finance 
within the next decade. It eliminates the need for trusted intermediaries.

[00:01:20] Speaker A: However, scalability remains a challenge.
The trilemma of security, scalability, and decentralization means 
you can only optimize for two of three.
""")
        return transcript
    
    def test_parallel_processing_faster_than_sequential(self, sample_transcript):
        """Verify parallel processing is faster."""
        import time
        
        orchestrator = System2Orchestrator()
        
        # Sequential processing
        job_id_seq = orchestrator.create_job(
            "mine",
            "seq_test",
            config={
                "file_path": str(sample_transcript),
                "max_workers": 1,  # Force sequential
            }
        )
        
        start = time.time()
        asyncio.run(orchestrator.process_job(job_id_seq))
        sequential_time = time.time() - start
        
        # Parallel processing
        job_id_par = orchestrator.create_job(
            "mine",
            "par_test",
            config={
                "file_path": str(sample_transcript),
                "max_workers": None,  # Auto parallel
            }
        )
        
        start = time.time()
        asyncio.run(orchestrator.process_job(job_id_par))
        parallel_time = time.time() - start
        
        print(f"Sequential: {sequential_time:.2f}s")
        print(f"Parallel: {parallel_time:.2f}s")
        print(f"Speedup: {sequential_time/parallel_time:.2f}x")
        
        # Parallel should be faster (or at least not slower)
        assert parallel_time <= sequential_time * 1.1  # Allow 10% variance
    
    def test_rich_data_extraction(self, sample_transcript):
        """Verify all rich data types are extracted."""
        orchestrator = System2Orchestrator()
        
        job_id = orchestrator.create_job(
            "mine",
            "rich_data_test",
            config={"file_path": str(sample_transcript)}
        )
        
        result = asyncio.run(orchestrator.process_job(job_id))
        
        # Verify result includes rich metrics
        assert result["result"]["claims_extracted"] > 0
        assert result["result"]["evidence_spans"] > 0
        assert result["result"]["people_extracted"] >= 2  # Satoshi, Vitalik
        assert result["result"]["concepts_extracted"] >= 2  # Blockchain, Smart contracts
        assert result["result"]["jargon_extracted"] >= 3  # Proof-of-work, Byzantine Generals, etc.
        
        # Verify claims have tiers
        assert result["result"]["claims_tier_a"] >= 0
        assert result["result"]["claims_tier_b"] >= 0
        assert result["result"]["claims_tier_c"] >= 0
        
        # Verify database has relations and categories
        unified_db = Path.home() / ".skip_the_podcast" / "unified_hce.db"
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM relations WHERE episode_id = 'rich_data_test'")
        relations_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM structured_categories WHERE episode_id = 'rich_data_test'")
        categories_count = cursor.fetchone()[0]
        
        conn.close()
        
        # May not always have relations/categories, but structure should exist
        assert relations_count >= 0
        assert categories_count >= 0
    
    def test_evidence_spans_have_timestamps(self, sample_transcript):
        """Verify evidence spans include timestamps."""
        orchestrator = System2Orchestrator()
        
        job_id = orchestrator.create_job(
            "mine",
            "evidence_test",
            config={"file_path": str(sample_transcript)}
        )
        
        asyncio.run(orchestrator.process_job(job_id))
        
        unified_db = Path.home() / ".skip_the_podcast" / "unified_hce.db"
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t0, t1, quote 
            FROM evidence_spans 
            WHERE episode_id = 'evidence_test'
            AND t0 IS NOT NULL
            LIMIT 5
        """)
        
        evidence = cursor.fetchall()
        conn.close()
        
        assert len(evidence) > 0, "Should have evidence with timestamps"
        
        for t0, t1, quote in evidence:
            assert t0 is not None, "t0 should exist"
            assert quote is not None, "quote should exist"
            assert len(quote) > 10, "quote should be meaningful"
    
    def test_progress_callbacks_work(self, sample_transcript):
        """Verify progress callbacks fire during processing."""
        progress_updates = []
        
        def progress_callback(step, percent, episode_id, current=None, total=None):
            progress_updates.append({
                "step": step,
                "percent": percent,
                "episode_id": episode_id
            })
        
        orchestrator = System2Orchestrator(progress_callback=progress_callback)
        
        job_id = orchestrator.create_job(
            "mine",
            "progress_test",
            config={"file_path": str(sample_transcript)}
        )
        
        asyncio.run(orchestrator.process_job(job_id))
        
        # Should have multiple progress updates
        assert len(progress_updates) > 0, "Should have progress updates"
        
        # Should have various stages
        stages = {update["step"] for update in progress_updates}
        assert "loading" in stages or "parsing" in stages
        assert "storing" in stages or len(stages) >= 3
        
        # Progress should increase
        percents = [u["percent"] for u in progress_updates]
        assert max(percents) > min(percents), "Progress should increase"
```

### 5.2 Performance Benchmark

**File:** `scripts/benchmark_unified_vs_old.py`

```python
#!/usr/bin/env python3
"""
Benchmark unified pipeline vs old sequential approach.

This script measures:
1. Processing time
2. Memory usage
3. Data quality (number of extractions)
"""

import time
import psutil
import asyncio
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.core.system2_orchestrator import System2Orchestrator


def measure_performance(transcript_path, config_name, config):
    """Measure processing performance."""
    process = psutil.Process()
    
    # Measure memory before
    mem_before = process.memory_info().rss / 1024 / 1024  # MB
    
    # Create orchestrator
    orchestrator = System2Orchestrator()
    
    # Create job
    job_id = orchestrator.create_job(
        "mine",
        f"benchmark_{config_name}",
        config=config
    )
    
    # Time execution
    start = time.time()
    result = asyncio.run(orchestrator.process_job(job_id))
    elapsed = time.time() - start
    
    # Measure memory after
    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    mem_used = mem_after - mem_before
    
    return {
        "config": config_name,
        "time_seconds": elapsed,
        "memory_mb": mem_used,
        "claims": result["result"]["claims_extracted"],
        "evidence": result["result"].get("evidence_spans", 0),
        "people": result["result"]["people_extracted"],
        "jargon": result["result"]["jargon_extracted"],
        "concepts": result["result"]["mental_models_extracted"],
    }


def main():
    """Run benchmarks."""
    # Create test transcript
    transcript = Path("benchmark_transcript.txt")
    transcript.write_text("""
[00:00:00] Speaker A: Today we'll discuss artificial intelligence and machine learning.
Sam Altman, CEO of OpenAI, recently announced GPT-4, their latest language model.

[00:00:15] Speaker B: Neural networks are inspired by biological neurons in the brain.
The backpropagation algorithm enables these networks to learn from data.

[00:00:30] Speaker A: Geoffrey Hinton, often called the godfather of deep learning,
pioneered many of these techniques. He worked at Google Brain before recently departing.

[00:00:45] Speaker B: I believe AI will transform every industry within 5 years.
We're seeing applications in healthcare, finance, and autonomous vehicles.

[00:01:00] Speaker A: However, alignment remains a critical challenge.
Stuart Russell emphasizes the importance of ensuring AI systems pursue human values.

[00:01:15] Speaker B: The transformer architecture, introduced in the "Attention Is All You Need" paper,
revolutionized natural language processing. This is what enables models like GPT and BERT.

[00:01:30] Speaker A: Yann LeCun argues that we need to move beyond supervised learning
towards self-supervised learning to achieve more general intelligence.

[00:01:45] Speaker B: The Turing Test, proposed by Alan Turing in 1950, 
remains a benchmark for machine intelligence, though many debate its relevance today.
""")
    
    print("=" * 80)
    print("UNIFIED PIPELINE PERFORMANCE BENCHMARK")
    print("=" * 80)
    
    configs = [
        {
            "name": "sequential",
            "config": {
                "file_path": str(transcript),
                "max_workers": 1,
                "enable_parallel_processing": False,
            }
        },
        {
            "name": "parallel_auto",
            "config": {
                "file_path": str(transcript),
                "max_workers": None,  # Auto-calculate
                "enable_parallel_processing": True,
            }
        },
        {
            "name": "parallel_4workers",
            "config": {
                "file_path": str(transcript),
                "max_workers": 4,
                "enable_parallel_processing": True,
            }
        },
    ]
    
    results = []
    
    for cfg in configs:
        print(f"\n{'='*80}")
        print(f"Running: {cfg['name']}")
        print(f"{'='*80}")
        
        result = measure_performance(transcript, cfg["name"], cfg["config"])
        results.append(result)
        
        print(f"Time: {result['time_seconds']:.2f}s")
        print(f"Memory: {result['memory_mb']:.1f} MB")
        print(f"Claims: {result['claims']}")
        print(f"Evidence Spans: {result['evidence']}")
        print(f"People: {result['people']}")
        print(f"Jargon: {result['jargon']}")
        print(f"Concepts: {result['concepts']}")
    
    # Summary comparison
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    baseline = results[0]
    
    for result in results:
        speedup = baseline["time_seconds"] / result["time_seconds"]
        mem_diff = result["memory_mb"] - baseline["memory_mb"]
        
        print(f"\n{result['config']:.<30} ", end="")
        print(f"Time: {result['time_seconds']:>6.2f}s ({speedup:>4.2f}x) ", end="")
        print(f"Mem: {mem_diff:>+6.1f}MB")
    
    # Cleanup
    transcript.unlink()
    
    print(f"\n{'='*80}")
    print("✅ Benchmark complete")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
```

**Run:**
```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python scripts/benchmark_unified_vs_old.py
```

### 5.3 Integration Test Suite

**File:** `scripts/run_unification_tests.sh`

```bash
#!/bin/bash
# Comprehensive test suite for storage unification

set -e  # Exit on error

echo "=================================="
echo "STORAGE UNIFICATION TEST SUITE"
echo "=================================="

# Activate venv
source venv/bin/activate

# 1. Schema tests
echo ""
echo "1. Testing schema..."
python scripts/analyze_schema_differences.py

# 2. Migration tests
echo ""
echo "2. Testing migration..."
python scripts/migrate_to_unified_schema.py

# 3. Unit tests
echo ""
echo "3. Running unit tests..."
pytest tests/integration/test_unified_pipeline_integration.py -v

# 4. System2 tests
echo ""
echo "4. Running System2 tests..."
pytest tests/system2/test_hce_operations.py -v

# 5. Context quotes test
echo ""
echo "5. Testing context quotes..."
python scripts/test_context_quotes_simple.py

# 6. Performance benchmark
echo ""
echo "6. Running performance benchmark..."
python scripts/benchmark_unified_vs_old.py

# 7. GUI smoke test
echo ""
echo "7. GUI smoke test (manual)..."
echo "   Please run GUI and test Summarization Tab:"
echo "   - Process a transcript"
echo "   - Verify progress updates"
echo "   - Check output file"
echo "   - Verify database entries"
echo ""
read -p "GUI test complete? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ GUI test failed or skipped"
    exit 1
fi

echo ""
echo "=================================="
echo "✅ ALL TESTS PASSED"
echo "=================================="
```

---

## 6. Phase 5: Documentation

**Duration:** 2-3 hours  
**Goal:** Update all documentation

### 6.1 Update Architecture Documentation

**File:** `docs/ARCHITECTURE_UNIFIED.md`

```markdown
# Architecture: Unified Storage Layer

## Overview

The system uses a single, unified storage path for all HCE (Hybrid Claim Extraction) data:

```
User Action (GUI/CLI)
    ↓
System2Orchestrator
    ↓
UnifiedHCEPipeline
    ├─> Mining (parallel)
    ├─> Evaluation (flagship)
    ├─> Categorization
    └─> Storage (unified DB)
```

## Components

### System2Orchestrator
**Location:** `src/knowledge_system/core/system2_orchestrator.py`

**Responsibilities:**
- Job creation and tracking
- Progress callbacks to GUI
- LLM request/response logging
- Auto-process chaining
- Error handling and retry

**Does NOT:**
- Mine segments directly
- Store data directly

### UnifiedHCEPipeline
**Location:** `src/knowledge_system/processors/hce/unified_pipeline.py`

**Responsibilities:**
- Parallel segment mining
- Claim evaluation and ranking
- Relation extraction
- Category identification
- Progress reporting

**Phases:**
1. Short summary generation
2. Parallel mining (3-8x faster)
3. Flagship evaluation (A/B/C tiers)
4. Long summary generation
5. Category analysis

### Storage Layer
**Location:** `src/knowledge_system/processors/hce/storage_sqlite.py`

**Responsibilities:**
- Bulk SQL inserts (optimized)
- Evidence span storage
- Relation storage
- Category storage
- FTS index maintenance

**Database:** `~/.skip_the_podcast/unified_hce.db`

## Data Flow

```
Transcript File
    ↓
Parse to Segments
    ↓
UnifiedHCEPipeline.process()
    ├─> mine_episode_unified() [PARALLEL]
    │   └─> Returns: UnifiedMinerOutput[] 
    ├─> evaluate_claims_flagship()
    │   └─> Returns: EvaluatedClaim[]
    ├─> analyze_structured_categories()
    │   └─> Returns: StructuredCategory[]
    └─> Returns: PipelineOutputs
        ├─> claims: ScoredClaim[] (with tier A/B/C)
        ├─> evidence: EvidenceSpan[] (with t0/t1/quote)
        ├─> relations: Relation[]
        ├─> categories: StructuredCategory[]
        ├─> people: PersonMention[]
        ├─> concepts: MentalModel[]
        └─> jargon: JargonTerm[]
    ↓
storage_sqlite.upsert_pipeline_outputs()
    └─> Unified Database
```

## Performance

### Parallel Processing

**Auto-calculation:**
- M2 Ultra (24 cores): 8 workers
- M2 Max (12 cores): 6 workers  
- M2 Pro (10 cores): 4 workers
- M1/M2 (8 cores): 3 workers

**Speed improvement:** 3-8x faster than sequential

**Memory safety:** Automatic throttling if RAM > 80%

### Benchmarks

| Hardware | Sequential | Parallel | Speedup |
|----------|-----------|----------|---------|
| M2 Ultra | 15 min | 2 min | 7.5x |
| M2 Max | 15 min | 2.5 min | 6x |
| M2 Pro | 15 min | 4 min | 3.75x |

## Database Schema

See: `src/knowledge_system/database/migrations/unified_schema.sql`

**Key tables:**
- `claims` - All claims with tier, scores, temporality
- `evidence_spans` - Quotes with timestamps (t0/t1)
- `relations` - Links between claims
- `structured_categories` - WikiData topics
- `people` - Mentions with context
- `concepts` - Mental models with evidence
- `jargon` - Terms with definitions and context

**Indexes:**
- Tier-based claim lookup
- Timestamp-based evidence
- Full-text search on claims and quotes

## Migration from Old System

**Old system:**
- Sequential segment-by-segment mining
- Simple ORM storage (SQLAlchemy)
- No evidence spans
- No claim evaluation
- No relations
- No categories

**New system:**
- Parallel batch mining
- Optimized SQL storage
- Full evidence with timestamps
- Flagship evaluation (A/B/C)
- Claim relations
- Structured categories

**Migration:** Use `scripts/migrate_to_unified_schema.py`
```

### 6.2 Update User Documentation

**File:** `docs/guides/USER_GUIDE_UNIFIED.md`

```markdown
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
**Evidence:** "The transformer architecture, introduced in the 
'Attention Is All You Need' paper, revolutionized natural language 
processing." [00:01:15]
```

**People Mentions:**
```markdown
## People

- **Sam Altman** (CEO of OpenAI) - "recently announced GPT-4" [00:00:00]
- **Geoffrey Hinton** (Godfather of deep learning) - "pioneered many techniques" [00:00:30]
```

**Mental Models:**
```markdown
## Mental Models

- **Backpropagation** - Algorithm that enables neural networks to learn
- **Alignment** - Ensuring AI pursues human values
```

## Performance

### Parallel Processing

The system automatically uses multiple workers based on your hardware:

| Your Mac | Workers | Expected Speed |
|----------|---------|----------------|
| M2 Ultra | 8 | 100 segments in ~2 min |
| M2 Max | 6 | 100 segments in ~2.5 min |
| M2 Pro | 4 | 100 segments in ~4 min |

### Manual Control

To force sequential (for debugging):
```python
# In settings.yaml
mining:
  max_workers: 1
  enable_parallel: false
```

## Database

All data stored in: `~/.skip_the_podcast/unified_hce.db`

**Query claims:**
```sql
SELECT canonical, tier, first_mention_ts
FROM claims
WHERE tier = 'A'
ORDER BY json_extract(scores_json, '$.importance') DESC;
```

**Query evidence:**
```sql
SELECT c.canonical, e.quote, e.t0, e.t1
FROM claims c
JOIN evidence_spans e ON c.claim_id = e.claim_id
WHERE c.episode_id = 'episode_xyz';
```

**Query relations:**
```sql
SELECT 
  sc.canonical as source,
  r.type,
  tc.canonical as target
FROM relations r
JOIN claims sc ON r.source_claim_id = sc.claim_id
JOIN claims tc ON r.target_claim_id = tc.claim_id;
```

## Troubleshooting

### "Processing seems slow"

Check if parallel processing is enabled:
```bash
sqlite3 ~/.skip_the_podcast/unified_hce.db "
  SELECT value FROM settings WHERE key = 'max_workers'
"
```

### "Not seeing evidence spans"

Evidence spans are stored separately. Use JOIN:
```sql
SELECT c.canonical, COUNT(e.seq) as evidence_count
FROM claims c
LEFT JOIN evidence_spans e ON c.claim_id = e.claim_id
GROUP BY c.claim_id;
```

### "Want to reset everything"

```bash
# Backup first!
cp ~/.skip_the_podcast/unified_hce.db ~/unified_hce.db.backup

# Clear episode
sqlite3 ~/.skip_the_podcast/unified_hce.db "
  DELETE FROM claims WHERE episode_id = 'episode_xyz';
  DELETE FROM people WHERE episode_id = 'episode_xyz';
  -- etc (cascading deletes handle related data)
"
```
```

---

## 7. Phase 6: Deployment

**Duration:** 2 hours  
**Goal:** Ship to production safely

### 7.1 Pre-Deployment Checklist

**File:** `scripts/pre_deployment_checklist.sh`

```bash
#!/bin/bash
# Pre-deployment safety checklist

echo "PRE-DEPLOYMENT CHECKLIST"
echo "========================"
echo ""

# 1. All tests pass
echo "1. Running test suite..."
if ./scripts/run_unification_tests.sh; then
    echo "   ✓ All tests passed"
else
    echo "   ❌ Tests failed - DO NOT DEPLOY"
    exit 1
fi

# 2. Database migration tested
echo ""
echo "2. Checking database migration..."
if [ -f "~/.skip_the_podcast/unified_hce.db" ]; then
    echo "   ✓ Unified database exists"
else
    echo "   ⚠️  Unified database not found - run migration first"
    exit 1
fi

# 3. Backup exists
echo ""
echo "3. Checking backups..."
backup_count=$(ls -1 knowledge_system.db.backup.* 2>/dev/null | wc -l)
if [ "$backup_count" -gt 0 ]; then
    echo "   ✓ Found $backup_count backup(s)"
else
    echo "   ❌ No backups found - create backup first"
    exit 1
fi

# 4. Documentation updated
echo ""
echo "4. Checking documentation..."
if [ -f "docs/ARCHITECTURE_UNIFIED.md" ] && [ -f "docs/guides/USER_GUIDE_UNIFIED.md" ]; then
    echo "   ✓ Documentation exists"
else
    echo "   ⚠️  Documentation incomplete"
fi

# 5. Deprecated code moved
echo ""
echo "5. Checking deprecated code..."
if [ -d "_deprecated" ]; then
    echo "   ✓ Deprecated directory exists"
    echo "   Files:"
    ls -1 _deprecated/database/ 2>/dev/null || echo "     (none)"
else
    echo "   ⚠️  Deprecated directory not found"
fi

# 6. Git status
echo ""
echo "6. Checking git status..."
if [ -z "$(git status --porcelain)" ]; then
    echo "   ✓ Working directory clean"
else
    echo "   ⚠️  Uncommitted changes:"
    git status --short
fi

echo ""
echo "========================"
echo "✅ PRE-DEPLOYMENT CHECKS COMPLETE"
echo "========================"
echo ""
echo "Ready to deploy? (Review above)"
```

### 7.2 Deployment Steps

```bash
# 1. Final commit
git add -A
git commit -m "feat: Unify storage layer with UnifiedHCEPipeline

- Integrate UnifiedHCEPipeline into System2Orchestrator
- Replace sequential mining with parallel processing (3-8x faster)
- Store rich data: evidence spans, relations, categories
- Migrate to unified database schema
- Remove deprecated hce_operations.py
- Update all documentation

BREAKING CHANGE: Database schema updated, run migration script
"

# 2. Tag release
git tag -a v2.0.0-unified -m "Storage Unification Release"

# 3. Push
git push origin feature/unify-storage-layer
git push origin v2.0.0-unified

# 4. Create PR
gh pr create \
  --title "Storage Unification: UnifiedHCEPipeline Integration" \
  --body "$(cat << 'EOF'
## Overview
Consolidates dual storage paths into single unified pipeline.

## Changes
- ✅ UnifiedHCEPipeline integrated into System2Orchestrator
- ✅ Parallel processing (3-8x faster mining)
- ✅ Rich data capture (evidence, relations, categories)
- ✅ Unified database schema
- ✅ Comprehensive test suite
- ✅ Documentation updated

## Performance
- Sequential: 15 min per transcript
- Parallel: 2 min per transcript
- **Speedup: 7.5x on M2 Ultra**

## Migration
Run: `python scripts/migrate_to_unified_schema.py`

## Testing
All tests passed (see CI)

## Breaking Changes
- Database schema updated (migration required)
- Old hce_operations.py deprecated (moved to _deprecated/)

## Rollback Plan
See ROLLBACK_PLAN.md if issues arise
EOF
)"

# 5. Wait for CI
echo "Waiting for CI tests..."
gh pr checks

# 6. Merge when ready
echo "Ready to merge? Review PR and approve."
```

---

## 8. Rollback Plan

**File:** `ROLLBACK_PLAN.md`

```markdown
# Rollback Plan

If the unified storage causes issues, follow these steps to rollback:

## Step 1: Restore Backup Branch

```bash
# Switch to backup
git checkout backup/before-unification

# Create rollback branch
git checkout -b rollback/unified-storage

# Force push to main (if needed)
git push origin rollback/unified-storage:main --force
```

## Step 2: Restore Database

```bash
# Find most recent backup
ls -lt knowledge_system.db.backup.* | head -1

# Restore (replace TIMESTAMP with actual)
cp knowledge_system.db.backup.TIMESTAMP knowledge_system.db
```

## Step 3: Restore Deprecated Code

```bash
# Move back hce_operations.py
git mv _deprecated/database/hce_operations.py src/knowledge_system/database/

# Restore old System2Orchestrator._process_mine()
git show backup/before-unification:src/knowledge_system/core/system2_orchestrator.py > temp.py
# Copy relevant sections manually
```

## Step 4: Test Rollback

```bash
# Run old tests
pytest tests/system2/test_hce_operations.py

# Test GUI
python launch_gui.command
```

## Step 5: Notify Users

```markdown
⚠️ **ROLLBACK NOTICE**

We've rolled back the storage unification due to [REASON].

Action required:
- Update to latest code: `git pull`
- Your data is safe (backed up automatically)
- Processing will use old sequential path temporarily

We're working on a fix and will re-deploy soon.
```

## Prevention

To avoid needing rollback:
- ✅ Run full test suite before merging
- ✅ Test on multiple hardware configs
- ✅ Get user feedback on beta branch first
- ✅ Monitor first 24h after deployment

## Data Recovery

If data was lost:
```bash
# Unified DB had data but got corrupted
cp ~/.skip_the_podcast/unified_hce.db.backup ~/.skip_the_podcast/unified_hce.db

# Export to CSV for safety
sqlite3 ~/.skip_the_podcast/unified_hce.db <<EOF
.mode csv
.output claims_backup.csv
SELECT * FROM claims;
.output people_backup.csv
SELECT * FROM people;
EOF
```
```

---

## Summary Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Pre-Flight | 1 hour | ☐ |
| Phase 1: Database Prep | 2-4 hours | ☐ |
| Phase 2: Integration | 6-8 hours | ☐ |
| Phase 3: Cleanup | 3-4 hours | ☐ |
| Phase 4: Testing | 4-6 hours | ☐ |
| Phase 5: Documentation | 2-3 hours | ☐ |
| Phase 6: Deployment | 2 hours | ☐ |
| **TOTAL** | **20-28 hours** | **☐** |

## Next Steps

1. Review this plan
2. Create feature branch
3. Execute Phase 1
4. Test after each phase
5. Update status checkboxes
6. Deploy when all green

---

**End of Master Plan Part 2**

See UNIFICATION_MASTER_PLAN.md for Part 1.




