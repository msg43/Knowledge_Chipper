# Question Mapper Usage Guide

Complete guide for using the Question Mapper system in Knowledge Chipper.

## Overview

The Question Mapper transforms Knowledge Chipper from a flat claim database into a discourse exploration tool by automatically discovering the questions that claims answer, creating an inquiry-driven knowledge navigation layer.

**Key Concept:** Instead of browsing claims by tags or categories, users navigate by questions like "How effective are carbon taxes?" with claims organized as answers, supporting evidence, contradictions, and prerequisite knowledge.

## Quick Start

### 1. Apply Database Migrations

First-time setup requires running the database migrations:

```bash
# From project root
cd src/knowledge_system/database/migrations

# Apply migrations (assuming you have a migration runner)
# Or manually run the SQL files in order:
sqlite3 path/to/knowledge_system.db < 2025_11_16_fix_verification_status.sql
sqlite3 path/to/knowledge_system.db < 2025_11_16_add_user_notes_to_claims.sql
sqlite3 path/to/knowledge_system.db < 2025_11_16_add_questions_system.sql
```

### 2. Process Existing Claims (CLI)

Run question mapping on sources that already have claims:

```bash
# Process a single source (e.g., YouTube video)
python scripts/run_question_mapper.py --source dQw4w9WgXcQ

# Process all unmapped sources (requires manual review via GUI)
python scripts/run_question_mapper.py --all

# Auto-approve all discovered questions (no manual review)
python scripts/run_question_mapper.py --all --auto-approve

# Process first 10 unmapped sources
python scripts/run_question_mapper.py --all --limit 10 --auto-approve
```

### 3. Review Questions (GUI)

Open the Knowledge Chipper GUI and navigate to the **Questions** tab:

1. View unreviewed questions in the table (yellow highlighting)
2. Double-click a question to see details
3. Click **✓ Approve** to keep the question
4. Click **✗ Reject** to delete the question
5. Use **📋 View Claims** to see all assigned claims

## Usage Scenarios

### Scenario 1: Processing New Content

**After running HCE on a new video/document:**

```python
from knowledge_system.processors.question_mapper import process_source_questions

# Process questions for newly analyzed source
result = process_source_questions(
    source_id="new_video_123",
    auto_approve=False  # Requires manual review
)

print(f"Discovered {result['questions_discovered']} questions")
print(f"Assigned {result['claims_assigned']} claims")
```

**Then review in GUI:**
- Open Questions tab
- Filter by domain if desired
- Approve/reject discovered questions

### Scenario 2: Batch Processing Existing Data

**For catching up on historical data:**

```bash
# Process all sources without questions
python scripts/run_question_mapper.py --all --limit 50

# Then review in GUI Questions tab
```

### Scenario 3: Programmatic Integration

**Integrate into custom workflow:**

```python
from knowledge_system.core.llm_adapter import LLMAdapter
from knowledge_system.database.service import DatabaseService
from knowledge_system.processors.question_mapper import QuestionMapperOrchestrator

# Initialize
llm = LLMAdapter(provider="ollama", model="qwen2.5:14b")
db = DatabaseService()
mapper = QuestionMapperOrchestrator(llm, db)

# Load claims from database
claims = db.get_claims_for_source("source_123")

# Convert to dict format
claim_dicts = [
    {"claim_id": c.claim_id, "claim_text": c.claim_text}
    for c in claims
]

# Run pipeline
result = mapper.process_claims(
    claims=claim_dicts,
    batch_size=50,
    auto_approve=False
)

# Access results
for question in result.discovered_questions:
    print(f"Q: {question.question_text}")
    print(f"   Type: {question.question_type}")
    print(f"   Confidence: {question.confidence}")
    print(f"   Claims: {len(question.claim_ids)}")
```

### Scenario 4: HCE Post-Processing Hook

**Automatically run after HCE completes (future integration):**

```python
# In system2_orchestrator or similar
from knowledge_system.processors.question_mapper import post_hce_hook

# After HCE stores claims
result = post_hce_hook(
    source_id=source_id,
    enable_question_mapping=True,
    auto_approve=False  # Requires manual review
)

if result and result['success']:
    logger.info(f"Question mapping: {result['questions_discovered']} questions discovered")
```

## Configuration Options

### Question Discovery

```python
min_discovery_confidence: float = 0.6  # Threshold for accepting discovered questions
batch_size: int = 50                   # Claims per LLM call
```

**Tuning Tips:**
- Raise `min_discovery_confidence` (e.g., 0.7) for higher quality, fewer questions
- Lower it (e.g., 0.5) for more questions that may need manual filtering
- Increase `batch_size` for faster processing but higher LLM token usage

### Question Merging

```python
min_merge_confidence: float = 0.7  # Threshold for merge recommendations
```

**Merge Actions:**
- `MERGE_INTO_EXISTING` - New question is duplicate/subset (discarded)
- `MERGE_EXISTING_INTO_NEW` - New question is broader/better (existing archived)
- `LINK_AS_RELATED` - Related but distinct (both kept, linked)
- `KEEP_DISTINCT` - No significant relationship

**Tuning Tips:**
- Higher confidence = more conservative merging
- Lower confidence = more aggressive deduplication

### Claim Assignment

```python
min_relevance: float = 0.5  # Threshold for claim-question assignments
```

**Relation Types:**
- `answers` - Direct answer
- `partial_answer` - Addresses one aspect
- `supports_answer` - Provides evidence
- `contradicts` - Alternative view (important for discourse!)
- `prerequisite` - Background knowledge needed
- `follow_up` - Raises related question
- `context` - Provides framing/scope

**Tuning Tips:**
- Higher relevance = fewer but stronger assignments
- Lower relevance = more comprehensive coverage

## GUI Features

### Questions Tab

**Table Columns:**
- **Question** - Question text (truncated)
- **Type** - factual, causal, normative, comparative, procedural, forecasting
- **Domain** - Topic area (economics, climate policy, etc.)
- **Importance** - Score from 0-1
- **Status** - ⏳ Pending or ✓ Reviewed

**Color Coding:**
- **Yellow** - Pending review (bold text)
- **Green** - Reviewed and approved

**Actions:**
- **✓ Approve Selected** - Bulk approve (marks as reviewed)
- **✗ Reject Selected** - Bulk delete
- **📋 View Claims** - See all assigned claims with relation types
- **Domain Filter** - Filter by topic area
- **🔄 Refresh** - Reload from database

### Question Details Dialog

**Displays:**
- Full question text
- Question type and domain
- Importance score
- Notes/rationale field (editable)

**Actions:**
- **✓ Approve** - Mark as reviewed, keep question
- **✗ Reject** - Delete question and all assignments
- **Close** - Return to table without changes

## Database Schema

### Core Tables

**`questions`** - Main question storage
- `question_id` (PK) - Unique identifier
- `question_text` - The question (unique)
- `question_type` - Type enum
- `domain` - Topic area
- `status` - open, answered, contested, abandoned, merged
- `reviewed` - Boolean flag for GUI workflow
- `importance_score` - 0-1 score

**`question_claims`** - Many-to-many assignments
- `claim_id` (FK) - Reference to claim
- `question_id` (FK) - Reference to question
- `relation_type` - How claim relates
- `relevance_score` - 0-1 relevance
- `rationale` - Explanation of relationship

**Views:**
- `v_questions_with_answers` - Questions with claim counts
- `v_question_hierarchy` - Question relationships
- `v_claims_multi_question` - Claims assigned to multiple questions
- `v_pending_question_assignments` - Unreviewed questions

## Best Practices

### 1. Review Before Approving

**Don't blindly auto-approve.** The LLM may discover:
- Overly specific questions
- Duplicate questions phrased differently
- Low-quality questions

**Review workflow:**
1. Run with `auto_approve=False`
2. Review in GUI Questions tab
3. Approve high-quality questions
4. Reject low-quality or duplicate questions
5. Merge related questions as needed

### 2. Start Small

**Process a few sources first** to:
- Tune confidence thresholds
- Understand question quality
- Develop review criteria

```bash
# Process just 5 sources initially
python scripts/run_question_mapper.py --all --limit 5
```

### 3. Monitor LLM Costs

**Question mapping uses 2-3 LLM calls per batch:**
- Discovery: ~1 call per 50 claims
- Merging: 1 call (all new questions vs existing)
- Assignment: ~1 call per 30 claims

**Cost optimization:**
- Use local models (Ollama) for prototyping
- Batch processing is more efficient than per-source
- Higher batch_size = fewer calls but larger prompts

### 4. Leverage Contradictions

**The `contradicts` relation type is powerful** for capturing discourse:
- Competing theories
- Conflicting evidence
- Alternative interpretations

**Don't filter these out** - they're valuable for critical thinking!

### 5. Use Domain Filtering

**In the GUI, filter by domain** to focus review:
- Review all economics questions together
- Develop domain-specific quality standards
- Ensure consistency within topics

## Troubleshooting

### No Questions Discovered

**Possible causes:**
- Claims too generic or unspecific
- Confidence threshold too high
- Insufficient claims (need ~3+ per question)

**Solutions:**
- Lower `min_discovery_confidence` to 0.5
- Check claim quality from HCE
- Ensure claims have good content

### Too Many Low-Quality Questions

**Symptoms:**
- Overly specific questions
- Questions for single claims
- Trivial or obvious questions

**Solutions:**
- Raise `min_discovery_confidence` to 0.7+
- Review and reject in GUI
- Improve claim extraction quality

### Duplicate Questions

**Despite merging, some duplicates slip through:**

**Manual fix:**
- Use GUI to identify duplicates
- Reject the inferior version
- Or use `merge_questions()` in DatabaseService

```python
db.merge_questions(
    source_question_id="q_duplicate",
    target_question_id="q_canonical"
)
```

### LLM Timeout/Errors

**Large batches may timeout:**

**Solutions:**
- Reduce `batch_size` (try 30 instead of 50)
- Use faster LLM model
- Process in smaller chunks with `--limit`

## Advanced Features

### Custom Relation Types

**Modify `models.py` to add new relation types:**

```python
class RelationType(str, Enum):
    # ... existing types
    CHALLENGE = "challenge"  # Challenges assumption in question
    REFRAME = "reframe"      # Reframes the question itself
```

Then update `assignment.txt` prompt with new types.

### Question Hierarchies

**Use `question_relations` table** for hierarchies:
- Prerequisite questions
- Follow-up questions
- Sub-questions
- Alternative framings

Currently not auto-populated, but schema supports it.

### Integration with Search

**Combine with Claim Search tab:**

```python
# Search for claims related to a question
question = db.get_question("q_123")
claims = db.get_claims_for_question("q_123")

# Search claims by question-related keywords
keywords = question["question_text"].split()
results = search_claims(keywords)
```

## Performance

### Benchmarks

**Typical processing times (50 claims, Ollama Qwen2.5:14b):**
- Discovery: ~30-45 seconds
- Merging: ~15-20 seconds
- Assignment: ~40-60 seconds
- **Total: ~90-125 seconds**

**With OpenAI GPT-4:**
- Discovery: ~10-15 seconds
- Merging: ~5-10 seconds
- Assignment: ~15-25 seconds
- **Total: ~30-50 seconds**

### Optimization

**For large-scale processing:**
- Use batch mode with `--limit`
- Run overnight for bulk processing
- Use faster models for discovery/assignment
- Reserve flagship models for critical merging decisions

## FAQ

**Q: Can I run question mapping without HCE?**
A: Yes! Question Mapper works on any claims in the database, regardless of how they were created.

**Q: What if I don't want to review every question?**
A: Use `--auto-approve` flag or `auto_approve=True` in code. But review a sample first to ensure quality.

**Q: Can I delete a question after approving?**
A: Yes, select it in the GUI and click Reject. This deletes the question and all claim assignments.

**Q: What happens to claims when I reject a question?**
A: Claims are unaffected. Only the question and its assignments are deleted.

**Q: Can I edit question text?**
A: Not currently. Questions are read-only after creation. You can merge questions or create new ones.

**Q: How do I see which claims answer a question?**
A: Select the question in GUI and click "📋 View Claims" button.

**Q: Can I run this on a subset of claims?**
A: Yes, pass a filtered list to `process_claims()` in code. CLI processes all claims for a source.

**Q: What LLM models work best?**
A: Qwen2.5:14b (local), GPT-4, Claude 3.5 Sonnet all work well. Smaller models (7B) may struggle with nuanced merging.

## Conclusion

The Question Mapper adds a powerful sense-making layer to Knowledge Chipper by organizing claims around the questions they answer. This transforms passive claim browsing into active inquiry-driven exploration.

**Next Steps:**
1. Run migrations to set up database
2. Process a few sources to test
3. Review questions in GUI
4. Tune thresholds for your content
5. Enable auto-processing for new sources

**For Support:**
- Check implementation summary: `QUESTION_MAPPER_IMPLEMENTATION_SUMMARY.md`
- Review unit tests: `tests/test_question_mapper.py`
- Examine prompts: `src/knowledge_system/processors/question_mapper/prompts/`
