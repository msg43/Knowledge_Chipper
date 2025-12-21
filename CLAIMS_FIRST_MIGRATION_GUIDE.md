# Claims-First Architecture Migration Guide

## Overview

Version 4.0.0 introduces a fundamental architectural change: **Claims-First Processing**. This inverts the traditional speaker-first pipeline where transcripts were fully diarized before any claim extraction could begin.

### What Changed

| **Before (Speaker-First)** | **After (Claims-First)** |
|---------------------------|-------------------------|
| Diarization required (30-45 min) | YouTube transcripts used first (instant) |
| Speaker attribution for ALL text | Speaker attribution only for A/B-tier claims |
| Whisper transcription always | Whisper only as fallback |
| pyannote dependency required | No pyannote dependency |
| Voice fingerprinting used | Lazy contextual attribution |

## Migration Steps

### 1. Update Dependencies

The following dependencies are **no longer required**:
- `pyannote.audio` - Speaker diarization
- `speechbrain` - Voice embeddings
- `torch-audio` - Audio processing for fingerprinting

You can remove them from your environment:
```bash
pip uninstall pyannote.audio speechbrain
```

### 2. Apply Database Migration

The database migration adds new columns and tables for claims-first processing:

```bash
cd /path/to/Knowledge_Chipper
source venv/bin/activate
python -c "
from knowledge_system.database.apply_hce_migrations import apply_migration
from pathlib import Path
apply_migration(
    'knowledge_system.db', 
    Path('src/knowledge_system/database/migrations/2025_12_20_claims_first_support.sql')
)
"
```

### 3. Update Configuration

Claims-first mode is now enabled by default. To verify or modify settings:

**config/settings.yaml:**
```yaml
claims_first:
  enabled: true
  transcript_source: "auto"  # auto, youtube, whisper
  youtube_quality_threshold: 0.7
  lazy_attribution_min_importance: 7  # Only attribute speakers for importance >= 7
```

### 4. GUI Changes

The Transcription tab now has a "Claims-First Mode" checkbox instead of the deprecated speaker assignment options:

- ✅ **Claims-First Mode** (new): Use the new pipeline
- ❌ ~~Enable speaker diarization~~ (removed)
- ❌ ~~Enable speaker assignment~~ (removed)

## New Pipeline Stages

### Claims-First Pipeline Flow

```
1. TRANSCRIPT ACQUISITION
   ├── Try YouTube transcript (instant, free)
   │   └── Quality check: word count, error markers
   └── Fallback to Whisper (10-20 min)
       └── Local transcription with timestamps

2. CLAIM EXTRACTION (UnifiedMiner)
   ├── Chunk transcript (~15k chars per chunk)
   ├── Extract claims with GPT-4o-mini (fast, cheap)
   └── Output: Raw candidate claims

3. CLAIM EVALUATION (FlagshipEvaluator)
   ├── Score claims on multiple dimensions
   │   ├── Epistemic value (0-10)
   │   ├── Actionability (0-10)
   │   └── Uniqueness (0-10)
   ├── Assign tiers: A (≥8), B (6-7), C (<6)
   └── Filter: Only keep A/B tier

4. TIMESTAMP MATCHING
   ├── Match claim quotes to transcript segments
   └── Precision: word-level (Whisper) or segment (YouTube)

5. SPEAKER ATTRIBUTION (Lazy, A/B only)
   ├── Use contextual clues from transcript
   ├── Match against known speakers in metadata
   └── Skip C-tier claims entirely
```

## Rollback

The speaker-first codebase is preserved for rollback if needed:

- **Git tag:** `v3.5.0-speaker-first-final`
- **Git branch:** `speaker-first-archive`
- **Config toggle:** Set `claims_first.enabled: false`

To rollback:
```bash
git checkout speaker-first-archive
# Or restore from tag:
git checkout v3.5.0-speaker-first-final
```

## Benefits

### Speed Improvements
- **10-20x faster** for podcasts with good YouTube transcripts
- Skip 30-45 minute diarization entirely
- Parallel claim extraction across chunks

### Cost Savings
- No expensive voice processing
- Cheaper LLM calls (GPT-4o-mini for extraction)
- Only evaluate high-value claims

### Quality Focus
- Focus processing on claims that matter
- Higher signal-to-noise ratio
- Reduced "claim spam" from low-value extractions

## Troubleshooting

### YouTube transcript not available
Some videos don't have auto-generated transcripts. The pipeline will automatically fall back to Whisper.

### Low quality transcripts
If YouTube transcript quality is below threshold (default 0.7), the pipeline upgrades to Whisper automatically.

### Speaker attribution not working
Speaker attribution only applies to A/B-tier claims (importance ≥ 7). C-tier claims are intentionally not attributed.

### Missing Google AI package
If you see "Google AI package not installed", the pipeline falls back to OpenAI (GPT-4o-mini). This is fine - OpenAI is reliable and works well.

## API Changes

### Removed APIs
```python
# These no longer exist:
from knowledge_system.processors.diarization import SpeakerDiarizationProcessor
from knowledge_system.voice import VoiceFingerprintProcessor, SpeakerVerificationService
from knowledge_system.gui.dialogs import SpeakerAssignmentDialog
```

### New APIs
```python
# Use these instead:
from knowledge_system.processors.claims_first import (
    ClaimsFirstPipeline,
    ClaimsFirstConfig,
    TranscriptFetcher,
)

# Process a podcast:
config = ClaimsFirstConfig(enabled=True)
pipeline = ClaimsFirstPipeline(config)
result = pipeline.process("https://youtube.com/watch?v=...", metadata={...})

# Access results:
print(f"Extracted {result.total_claims} claims")
for claim in result.a_tier_claims:
    print(f"  {claim.canonical}")
```

## Questions?

Open an issue at: https://github.com/msg43/Knowledge_Chipper/issues
