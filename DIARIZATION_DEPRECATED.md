# Diarization System Deprecated

**Date:** December 22, 2025  
**Status:** 🚫 DEPRECATED - Do Not Use

---

## Summary

The entire diarization and voice fingerprinting system has been **deprecated** in favor of a simpler, more accurate approach: **LLM-based speaker inference from content**.

---

## What Was Removed

### Core Principle Change

**OLD APPROACH (Complex):**
```
Audio → Whisper → Diarization → Voice Fingerprinting → User Assignment → segments.speaker → claims
```

**NEW APPROACH (Simple):**
```
Audio/YouTube → Transcript → Pass 1 LLM → Speaker Inference → claims.speaker
```

### Deprecated Files

The following files are **no longer used** and can be removed:

```
src/knowledge_system/processors/diarization.py
src/knowledge_system/voice/voice_fingerprinting.py
src/knowledge_system/processors/speaker_processor.py
src/knowledge_system/utils/speaker_attribution.py
src/knowledge_system/services/speaker_learning_service.py
```

### Deprecated Database Tables

```sql
DROP TABLE speaker_voices;
DROP TABLE speaker_assignments;
DROP TABLE speaker_learning_history;
DROP TABLE speaker_sessions;
DROP TABLE channel_host_mappings;
DROP TABLE speaker_processing_sessions;
DROP TABLE persistent_speaker_profiles;
```

### Deprecated Dependencies

```toml
# Remove from pyproject.toml [diarization] extras
pyannote.audio
speechbrain
transformers[torch]
torchaudio
# Total: ~377MB of dependencies removed
```

### Deprecated Database Column

```sql
-- segments.speaker column removed
ALTER TABLE segments DROP COLUMN speaker;
```

---

## Why This Change?

### Problems with Diarization Approach

1. **Complexity** - 6-stage pipeline with multiple failure points
2. **Slow** - Added 40-80 seconds per video
3. **Inaccurate** - Over-segmentation, false merges, voice drift
4. **Edge Case** - Only needed for audio files without transcripts (~10% of content)
5. **Maintenance Burden** - 377MB of dependencies, complex audio processing
6. **Two Workflows** - Different paths for YouTube vs audio files

### Benefits of LLM Inference

1. **Simpler** - One unified workflow for all content
2. **Faster** - No audio processing overhead
3. **More Accurate** - Content-based attribution beats audio analysis
4. **Works Everywhere** - YouTube, audio, video, documents
5. **Already Implemented** - Pass 1 LLM already extracts speaker info
6. **Smaller Install** - No torch/transformers dependencies

---

## Migration Path

### Phase 1: ✅ COMPLETE - Add Speaker to Entities

```sql
-- Migration: 2025_12_22_add_speaker_to_entities.sql
ALTER TABLE claims ADD COLUMN speaker TEXT;
ALTER TABLE jargon_terms ADD COLUMN introduced_by TEXT;
ALTER TABLE concepts ADD COLUMN advocated_by TEXT;
```

### Phase 2: ✅ COMPLETE - Update Storage Logic

```python
# claim_store.py now extracts speaker from Pass 1 LLM
claim.speaker = self._extract_speaker_from_claim_data(claim_data, session, source_id)
```

### Phase 3: ✅ COMPLETE - Remove segments.speaker

```python
# Segment model updated - speaker column removed
class Segment(Base):
    # speaker = Column(String)  # REMOVED
    start_time = Column(String)
    end_time = Column(String)
    text = Column(Text, nullable=False)
```

### Phase 4: 🔜 PENDING - Remove Diarization Files

```bash
# To be done when ready
rm -rf src/knowledge_system/processors/diarization.py
rm -rf src/knowledge_system/voice/
rm -rf src/knowledge_system/processors/speaker_processor.py
rm -rf src/knowledge_system/utils/speaker_attribution.py
rm -rf src/knowledge_system/services/speaker_learning_service.py
```

### Phase 5: 🔜 PENDING - Remove Dependencies

```bash
# Edit pyproject.toml
# Remove [diarization] extras section
# Remove pyannote.audio, speechbrain, transformers, torchaudio
```

### Phase 6: 🔜 PENDING - Drop Database Tables

```sql
-- Run when ready to clean up
DROP TABLE IF EXISTS speaker_voices;
DROP TABLE IF EXISTS speaker_assignments;
DROP TABLE IF EXISTS speaker_learning_history;
DROP TABLE IF EXISTS speaker_sessions;
DROP TABLE IF EXISTS channel_host_mappings;
DROP TABLE IF EXISTS speaker_processing_sessions;
DROP TABLE IF EXISTS persistent_speaker_profiles;
```

---

## New Architecture

### Unified Workflow (All Content)

```
┌─────────────────────────────────────────────────────────────┐
│ INPUT: Any Content Source                                   │
├─────────────────────────────────────────────────────────────┤
│ YouTube URL → YouTube API transcript                        │
│ Audio file → Whisper transcript (no diarization)           │
│ Video file → Extract audio → Whisper transcript            │
│                                                              │
│ Result: Plain text transcript with timestamps               │
│         (no speaker labels at segment level)                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ STORAGE: Segments (simplified)                              │
├─────────────────────────────────────────────────────────────┤
│ segment_id, source_id, start_time, end_time, text          │
│ (NO speaker field)                                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ PASS 1: EXTRACTION                                           │
├─────────────────────────────────────────────────────────────┤
│ LLM infers speakers from content for all entities:          │
│ - claims.speaker                                            │
│ - jargon.introduced_by                                      │
│ - people.mentioned_by                                       │
│ - concepts.advocated_by                                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ STORAGE: Entities (with speaker attribution)                │
├─────────────────────────────────────────────────────────────┤
│ claims: speaker field populated                             │
│ jargon: introduced_by field populated                       │
│ people: mentioned_by field populated                        │
│ concepts: advocated_by field populated                      │
└─────────────────────────────────────────────────────────────┘
```

### Speaker Inference Example

**Transcript:**
```
"Jeff Snider: The Fed's QE causes dollar weakness.
Emil Kalinowski: I agree, but what about the repo market?
Jeff Snider: The repo market is the key to understanding this."
```

**Pass 1 Output:**
```json
{
  "claims": [
    {
      "claim_text": "Fed QE causes dollar weakness",
      "speaker": "Jeff Snider",
      "evidence_spans": [...]
    },
    {
      "claim_text": "The repo market is key to understanding dollar weakness",
      "speaker": "Jeff Snider",
      "evidence_spans": [...]
    }
  ]
}
```

The LLM infers speakers from:
- Explicit labels in transcript ("Jeff Snider:")
- Context clues ("he argues", "she responds")
- Conversational flow
- Content patterns

**This works better than diarization** because it's content-aware!

---

## For Developers

### If You See Diarization Code

- **Don't use it** - It's deprecated
- **Don't fix bugs in it** - It will be removed
- **Don't add features to it** - Use LLM inference instead

### If You Need Speaker Attribution

- **Use claims.speaker** - Populated by Pass 1 LLM
- **Use jargon.introduced_by** - Who first used the term
- **Use concepts.advocated_by** - Who advocates for the model
- **Query by speaker** - `SELECT * FROM claims WHERE speaker = 'Jeff Snider'`

### If You're Processing Audio

- **Use Whisper without diarization** - Faster, simpler
- **Let Pass 1 LLM infer speakers** - More accurate
- **Don't enable diarization** - It's deprecated

---

## Related Documents

- `src/knowledge_system/database/migrations/2025_12_22_add_speaker_to_entities.sql` - Migration script
- `TWO_PASS_SYSTEM_FLOWCHARTS.md` - Current architecture
- `CLAUDE.md` - Development guide (updated)

---

## Questions?

**Q: What about podcasts with multiple speakers?**  
A: Pass 1 LLM handles this perfectly by inferring from content.

**Q: What about voice fingerprinting?**  
A: Deprecated. LLM content-based attribution is more accurate.

**Q: What if I have audio files?**  
A: Use Whisper without diarization, let Pass 1 LLM infer speakers.

**Q: Can I still use diarization?**  
A: No, it's deprecated and will be removed. Use LLM inference.

**Q: What about existing diarized content?**  
A: Migration script populates claims.speaker from segments.speaker (best effort).

