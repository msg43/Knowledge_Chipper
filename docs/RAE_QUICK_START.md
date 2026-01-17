# RAE Quick Start Guide

**Retrieval-Augmented Extraction (RAE)** - Enforce jargon consistency and track claim evolution

---

## What is RAE?

RAE injects channel-specific knowledge into extraction prompts to:
1. **Enforce jargon consistency** - Use established definitions across episodes
2. **Prevent duplicate extraction** - Skip claims already extracted (≥95% similar)
3. **Track evolution** - Link claims that changed over time (85-94% similar)
4. **Expose contradictions** - Flag when speakers change positions

---

## How to Use

### Automatic Activation

RAE is **automatically enabled** when processing videos with a `channel_id`.

No configuration needed - it just works!

### Processing a Channel Series

```python
# Example: Process 10 Huberman Lab episodes

from knowledge_system.core.system2_orchestrator import System2Orchestrator

orchestrator = System2Orchestrator()

youtube_urls = [
    "https://youtube.com/watch?v=abc123",  # Episode 1
    "https://youtube.com/watch?v=def456",  # Episode 2
    # ... 8 more episodes
]

for url in youtube_urls:
    result = orchestrator.process_youtube_url(url)
    print(f"✅ Processed: {result.metadata['title']}")
```

**What Happens:**
- Episode 1: All claims are novel, jargon definitions established
- Episode 2-10: RAE context injected, duplicates skipped, contradictions flagged

---

## Viewing Results

### On GetReceipts.org

1. **Browse Claims** - Go to `/dashboard/claims`
2. **Click a Claim** - See claim detail page
3. **View Evolution** - Click "Evolution Timeline" tab
4. **See Timeline** - Visual timeline showing:
   - All versions of the claim
   - Similarity scores
   - Contradiction flags
   - Evidence spans with timestamps

### Example Evolution Timeline

```
📅 Jan 15, 2024 - Episode 42
"Dopamine is primarily a reward molecule"
[00:12:34] Evidence: "When you get a reward, dopamine spikes..."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 Feb 10, 2024 - Episode 47
🔁 Duplicate (98% similar) - Mentioned again, not re-extracted

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 Jun 8, 2024 - Episode 63
⚠️ CONTRADICTION (87% similar)
"Dopamine regulates motivation and anticipation, not reward itself"
[00:45:12] Evidence: "Recent research shows dopamine is about wanting..."
```

---

## Configuration

### RAE Service Settings

**Default:** Production API (`https://getreceipts.org/api`)

To use development API:
```python
from knowledge_system.services.rae_service import RAEService

service = RAEService(use_production=False)  # Uses localhost:3000
```

### Limits

Adjust how much history is fetched:
```python
history = await rae_service.fetch_channel_history(
    channel_id="UC123...",
    claim_limit=100,  # Default: 50
    jargon_limit=200  # Default: 100
)
```

### Disable RAE

To disable RAE for a specific episode:
```python
# Remove channel_id from metadata
metadata.pop('channel_id', None)
```

---

## Troubleshooting

### "No RAE context available"
**Normal:** First episode from channel has no history yet

### "RAE fetch failed"
**Check:** Is GetReceipts.org accessible?  
**Check:** Is the API endpoint deployed?  
**Fix:** System continues without RAE (graceful degradation)

### "Evolution detection failed"
**Check:** Is TasteEngine initialized?  
**Check:** Is sentence-transformers installed?  
**Fix:** System continues without evolution tracking

### "Duplicate claims still being extracted"
**Check:** Is `channel_id` present in metadata?  
**Check:** Are claims actually >95% similar?  
**Note:** Evolution (85-94%) and contradictions ARE extracted (by design)

---

## Performance Tips

### For Large Series (100+ episodes)

1. **Batch Processing** - Process episodes in order (oldest to newest)
2. **Monitor Memory** - Evolution detector uses ~10MB per episode
3. **Check Logs** - Watch for "RAE context injected" messages

### For One-Off Videos

RAE adds minimal overhead (~1-2s) but provides little benefit.

Consider processing one-off videos without channel context.

---

## Advanced Usage

### Manual Evolution Analysis

```python
from knowledge_system.processors.claim_evolution_detector import get_claim_evolution_detector

detector = get_claim_evolution_detector()

# Analyze claims manually
enhanced_claims = await detector.analyze_claims(
    new_claims=[
        {"canonical": "Dopamine is a reward molecule"},
        {"canonical": "Serotonin affects mood"}
    ],
    channel_id="UC123...",
    episode_date="2024-01-15"
)

# Check results
for claim in enhanced_claims:
    print(f"Status: {claim['evolution_status']}")
    if claim.get('is_contradiction'):
        print(f"  ⚠️ Contradicts: {claim['contradicts_claim_id']}")
```

### Custom Similarity Threshold

```python
# In claim_evolution_detector.py, modify thresholds:

# Current:
# - Duplicate: ≥0.95
# - Evolution: 0.85-0.94

# To make more/less strict:
if similarity >= 0.98:  # Stricter duplicate threshold
    claim['evolution_status'] = 'duplicate'
elif similarity >= 0.90:  # Stricter evolution threshold
    claim['evolution_status'] = 'evolution'
```

---

## API Reference

### GET `/api/channels/:channelId/history`

**Query Params:**
- `claim_limit` (default: 50) - Max claims to return
- `jargon_limit` (default: 100) - Max jargon terms to return

**Response:**
```json
{
  "channel_id": "UC123...",
  "jargon_registry": [
    {
      "term": "quantitative easing",
      "definition": "Central bank policy...",
      "domain": "economics",
      "episode_id": "ep_001",
      "created_at": "2024-01-15T..."
    }
  ],
  "top_claims": {
    "economics": [
      {
        "claim_id": "claim_001",
        "canonical": "Inflation is caused by...",
        "tier": "A",
        "importance_score": 8.5,
        "episode_id": "ep_001",
        "created_at": "2024-01-15T..."
      }
    ]
  },
  "metadata": {
    "total_jargon_terms": 45,
    "total_claims": 38,
    "fetched_at": "2024-01-17T..."
  }
}
```

### GET `/api/claims/:claimId/evolution`

**Response:**
```json
{
  "claim_id": "claim_001",
  "evolution_chain": [
    {
      "claim_id": "claim_001",
      "canonical": "Dopamine is a reward molecule",
      "episode_id": "ep_001",
      "episode_title": "Understanding Dopamine",
      "episode_date": "2024-01-15T...",
      "similarity_to_previous": null,
      "is_contradiction": false,
      "evolution_status": "novel",
      "depth": 0,
      "evidence_spans": [...]
    },
    {
      "claim_id": "claim_042",
      "canonical": "Dopamine regulates motivation, not reward",
      "episode_id": "ep_042",
      "episode_title": "Dopamine Revisited",
      "episode_date": "2024-06-08T...",
      "similarity_to_previous": 0.87,
      "is_contradiction": true,
      "evolution_status": "contradiction",
      "depth": 1,
      "evidence_spans": [...]
    }
  ],
  "statistics": {
    "total_versions": 2,
    "contradictions": 1,
    "evolutions": 0,
    "first_mentioned": "2024-01-15T...",
    "last_mentioned": "2024-06-08T..."
  }
}
```

---

## FAQ

**Q: Does RAE slow down processing?**  
A: Yes, by 3-8 seconds per episode. But it prevents duplicate work and tracks valuable evolution patterns.

**Q: What if I don't want jargon consistency?**  
A: Remove `channel_id` from metadata or disable RAE in settings (future feature).

**Q: Can I see contradictions without processing all episodes?**  
A: No - you need to process episodes in order for evolution tracking to work.

**Q: Does RAE work with local files (non-YouTube)?**  
A: Only if you manually add `channel_id` to metadata. YouTube videos get it automatically.

**Q: How accurate is contradiction detection?**  
A: Current heuristic: ~70-80%. Future LLM-based detection will improve to 90%+.

---

## Support

- **Documentation:** See [RAE_IMPLEMENTATION_COMPLETE.md](RAE_IMPLEMENTATION_COMPLETE.md)
- **Architecture:** See [dynamic_learning_with_rae_flowchart.html](dynamic_learning_with_rae_flowchart.html)
- **Tests:** Run `pytest tests/test_rae_integration.py -v`
- **Issues:** Check logs in `logs/` directory for RAE-specific errors

---

**Ready to track claim evolution across your podcast series!** 🚀
