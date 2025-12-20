# Claims-First Migration Guide

This guide explains how to migrate from the speaker-first pipeline to the claims-first architecture.

## Overview

The claims-first architecture inverts the traditional processing order:

| Speaker-First (Old) | Claims-First (New) |
|---------------------|-------------------|
| 1. Diarization | 1. Transcription |
| 2. Transcription | 2. Claim Extraction |
| 3. Speaker Assignment | 3. Evaluation & Filtering |
| 4. Claim Extraction | 4. Timestamp Matching |
| 5. Evaluation | 5. **Lazy** Speaker Attribution |

## Benefits

- **Faster**: YouTube transcripts in ~5 seconds vs 10-15 min Whisper
- **Cheaper**: Only attribute speakers to important claims
- **Simpler**: No diarization dependency for new pipeline
- **Better**: LLM understands context better than acoustic matching

## Prerequisites

1. **Database Migration**: Run the migration script first
   ```bash
   python scripts/apply_claims_first_migration.py
   ```

2. **Optional Dependencies**: The claims-first pipeline uses:
   - `youtube-transcript-api` for YouTube transcripts
   - Existing Whisper for fallback transcription
   - Existing LLM adapters for claim extraction

## Enabling Claims-First

### Option 1: Configuration File

Edit `config/settings.yaml`:

```yaml
claims_first:
  enabled: true
  transcript_source: auto  # auto, youtube, or whisper
  youtube_quality_threshold: 0.7
  evaluator_model: configurable  # gemini, claude, or configurable
  lazy_attribution_min_importance: 7
```

### Option 2: Python Code

```python
from knowledge_system.processors.audio_processor import AudioProcessor

# Create processor with claims-first enabled
processor = AudioProcessor(
    use_claims_first=True,
    claims_first_config={
        "transcript_source": "auto",
        "youtube_quality_threshold": 0.7,
        "lazy_attribution_min_importance": 7,
    }
)

# Process with claims-first
result = processor.process_claims_first(
    audio_path=Path("/path/to/audio.mp3"),
    source_url="https://youtube.com/watch?v=...",
    metadata={"title": "Episode Title"}
)
```

### Option 3: Direct Pipeline Access

```python
from knowledge_system.processors.claims_first import (
    ClaimsFirstConfig,
    ClaimsFirstPipeline,
)

config = ClaimsFirstConfig(
    enabled=True,
    transcript_source="auto",
)

pipeline = ClaimsFirstPipeline(config=config)

result = pipeline.process(
    source_url="https://youtube.com/watch?v=...",
    audio_path=Path("/path/to/audio.mp3"),
    metadata={"title": "Episode Title"}
)

# Access results
print(f"Total claims: {result.total_claims}")
print(f"A-tier claims: {len(result.a_tier_claims)}")
print(f"Attributed: {len(result.attributed_claims)}")
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `false` | Master enable flag |
| `transcript_source` | `auto` | `auto`, `youtube`, or `whisper` |
| `youtube_quality_threshold` | `0.7` | Min quality for YouTube transcripts |
| `evaluator_model` | `configurable` | `gemini`, `claude`, or `configurable` |
| `lazy_attribution_min_importance` | `7` | Min importance for speaker attribution |
| `context_window_seconds` | `60` | Context for speaker attribution |
| `store_candidates` | `true` | Store candidates for re-evaluation |
| `fuzzy_match_threshold` | `0.7` | Quote-to-timestamp match threshold |

## Transcript Sources

### Auto Mode (Recommended)

1. Try YouTube transcript first (~5 seconds)
2. Assess quality using heuristics
3. Fall back to Whisper if quality < threshold

### YouTube Only

Forces use of YouTube's auto-generated transcripts. Best for:
- High-volume processing
- Cost-sensitive scenarios
- English content with clear audio

### Whisper Only

Forces Whisper transcription. Best for:
- Non-YouTube sources
- Critical accuracy requirements
- Poor quality YouTube transcripts

## Lazy Speaker Attribution

Only claims with importance >= `lazy_attribution_min_importance` get speaker attribution.

### Attribution Signals

The LLM uses these signals:

1. **First-person language**: "my research", "I think"
2. **Expertise matching**: Topic vs guest credentials
3. **Turn-taking patterns**: Question → claim → response
4. **Metadata**: Guest names from description
5. **Self-introductions**: "I'm [name] and..."

### Attribution Result

```python
result.claims[0].speaker  # SpeakerAttribution or None

# If attributed:
speaker = result.claims[0].speaker
print(speaker.speaker_name)  # "Dr. Jane Smith"
print(speaker.confidence)    # 0.85
print(speaker.is_host)       # False
print(speaker.reasoning)     # ["Expert content", "Used 'my research'"]
```

## Rollback

If issues arise, you can roll back:

### Immediate (Config Toggle)

```yaml
claims_first:
  enabled: false
```

### Full Rollback (Git)

```bash
# Checkout the preserved tag
git checkout v3.5.0-speaker-first-final

# Or the archive branch
git checkout speaker-first-archive
```

## A/B Testing

Run both pipelines in parallel to compare:

```python
# Speaker-first
processor_sf = AudioProcessor(use_claims_first=False, enable_diarization=True)
result_sf = processor_sf.process(audio_path)

# Claims-first
processor_cf = AudioProcessor(use_claims_first=True)
result_cf = processor_cf.process_claims_first(audio_path, source_url=url)

# Compare
print(f"Speaker-first claims: {len(result_sf.metadata.get('claims', []))}")
print(f"Claims-first claims: {result_cf.metadata['total_claims']}")
```

## Validation

Run the validation script:

```bash
# Test on 20 podcasts from database
python scripts/validate_claims_first.py --use-db --count 20

# Test on curated test URLs
python scripts/validate_claims_first.py --count 5

# YouTube transcripts only
python scripts/validate_claims_first.py --youtube-only
```

## Database Changes

New columns in `claims`:
- `timestamp_precision`: `word` or `segment`
- `transcript_source`: `youtube`, `whisper`, or `manual`
- `speaker_attribution_confidence`: 0.0-1.0

New columns in `media_sources`:
- `transcript_source`: Which transcript was used
- `transcript_quality_score`: YouTube quality assessment
- `used_claims_first_pipeline`: Boolean flag

New tables:
- `candidate_claims`: Pre-filtering candidates for re-evaluation
- `claims_first_processing_log`: Processing metrics and timing

## Troubleshooting

### "youtube-transcript-api not installed"

```bash
pip install youtube-transcript-api
```

### YouTube transcript quality too low

Lower the threshold or force Whisper:

```yaml
claims_first:
  youtube_quality_threshold: 0.5  # Lower threshold
  # OR
  transcript_source: whisper  # Force Whisper
```

### No speaker attribution

Check that claims have importance >= `lazy_attribution_min_importance`:

```python
# Lower the threshold
config = ClaimsFirstConfig(lazy_attribution_min_importance=5)
```

### Slow processing

Use YouTube-only mode for maximum speed:

```yaml
claims_first:
  transcript_source: youtube
```

## Questions?

See also:
- `CLAIMS_FIRST_ARCHITECTURE_OVERHAUL_PLAN.md` - Original design document
- `EXTRACTION_ARCHITECTURE_ANALYSIS.md` - Analysis of extraction approaches
- `tests/test_claims_first_pipeline.py` - Test suite with examples

