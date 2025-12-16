# Rollback Instructions - Claims-First Architecture Overhaul

**Created:** December 15, 2025
**Backup Commit:** `254e1be`
**Backup Tag:** `v1.x-pre-overhaul`
**Backup Branch:** `backup/pre-claims-first-overhaul-2025-12-15`

---

## Quick Rollback (Emergency)

If the claims-first overhaul causes critical issues, restore the old system immediately:

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper

# Option 1: Reset to tag (simplest)
git checkout v1.x-pre-overhaul

# Option 2: Reset main branch to backup state
git reset --hard v1.x-pre-overhaul

# Option 3: Checkout backup branch
git checkout backup/pre-claims-first-overhaul-2025-12-15
```

**After rollback:**
1. Restart any running processes
2. Verify diarization pipeline works: `python -m pytest tests/test_diarization.py`
3. Process a test podcast to confirm functionality
4. Notify users that old system has been restored

---

## What's in the Backup

This backup preserves the **full diarization pipeline** system as of December 15, 2025:

### Code Components (preserved)
- ✅ `src/knowledge_system/processors/diarization.py` (pyannote diarization)
- ✅ `src/knowledge_system/voice/voice_fingerprinting.py` (acoustic analysis)
- ✅ `src/knowledge_system/processors/speaker_processor.py` (6-layer pipeline)
- ✅ `src/knowledge_system/utils/llm_speaker_suggester.py` (LLM attribution)
- ✅ All speaker attribution GUI components
- ✅ All configuration for diarization settings

### Dependencies (preserved in requirements.txt)
- pyannote.audio
- speechbrain
- transformers
- torch
- wav2vec2 models
- ECAPA-TDNN models

### Documentation (preserved)
- All SPEAKER_* documentation files
- VOICE_FINGERPRINTING_* guides
- Diarization configuration guides
- Testing documentation

---

## Backup Locations

### Git Remote (GitHub)
- **Branch:** https://github.com/msg43/Knowledge_Chipper/tree/backup/pre-claims-first-overhaul-2025-12-15
- **Tag:** https://github.com/msg43/Knowledge_Chipper/releases/tag/v1.x-pre-overhaul
- **Commit:** https://github.com/msg43/Knowledge_Chipper/commit/254e1be

### Local Git
```bash
# List all backups
git branch | grep backup
git tag | grep overhaul

# View backup commit
git show v1.x-pre-overhaul

# Compare current state to backup
git diff v1.x-pre-overhaul..HEAD
```

---

## Partial Rollback (Selective)

If only specific components need to be restored:

### Restore diarization module only
```bash
git checkout v1.x-pre-overhaul -- src/knowledge_system/processors/diarization.py
git checkout v1.x-pre-overhaul -- src/knowledge_system/voice/
```

### Restore speaker processing pipeline
```bash
git checkout v1.x-pre-overhaul -- src/knowledge_system/processors/speaker_processor.py
git checkout v1.x-pre-overhaul -- src/knowledge_system/utils/llm_speaker_suggester.py
```

### Restore GUI components
```bash
git checkout v1.x-pre-overhaul -- src/knowledge_system/gui/tabs/speaker_attribution_tab.py
git checkout v1.x-pre-overhaul -- src/knowledge_system/gui/dialogs/speaker_assignment_dialog.py
```

### Restore dependencies
```bash
git checkout v1.x-pre-overhaul -- requirements.txt
pip install -r requirements.txt
```

---

## Verification After Rollback

Run these checks to ensure the old system is working:

### 1. Check Dependencies
```bash
pip list | grep -E "pyannote|speechbrain|transformers"
# Should show: pyannote-audio, speechbrain, transformers installed
```

### 2. Test Diarization
```bash
python -c "from knowledge_system.processors.diarization import DiarizationProcessor; print('✅ Diarization available')"
```

### 3. Test Voice Fingerprinting
```bash
python -c "from knowledge_system.voice.voice_fingerprinting import VoiceFingerprinting; print('✅ Voice fingerprinting available')"
```

### 4. Process Test Audio
```bash
# Use a short test file
python -m knowledge_system.processors.audio_processor --diarization test_audio.wav
```

### 5. Check GUI
```bash
# Launch GUI and verify Speaker Attribution tab exists
python -m knowledge_system.gui
```

---

## What Changed in Overhaul (for reference)

When rolling back, you're reverting these changes:

### Removed in Overhaul
- Claims-first pipeline (`processors/claims_first_pipeline.py`)
- YouTube transcript fetcher (`processors/transcript_fetcher.py`)
- Lazy speaker attribution (`processors/lazy_speaker_attribution.py`)
- Timestamp matcher (`processors/timestamp_matcher.py`)

### Restored by Rollback
- Full 6-layer diarization pipeline
- Voice fingerprinting with ECAPA-TDNN
- Full-transcript speaker attribution
- CSV channel mapping integration
- All speaker-related GUI tabs

### Configuration Changes
```yaml
# Old config (restored)
enable_diarization: true
voice_fingerprinting_enabled: true
diarization_sensitivity: conservative

# New config (removed)
transcript_source: auto
lazy_attribution_min_importance: 7
youtube_quality_threshold: 0.7
```

---

## Timeline for Keeping Backup

**Recommendation:** Keep this backup for at least 6 months (until June 2026)

- **Weeks 1-4:** High risk period, backup critical
- **Months 2-3:** Monitor production, backup still important
- **Months 4-6:** If no issues, backup becomes safety net only
- **After 6 months:** If claims-first is stable, can delete backup branch/tag

**Do NOT delete before:**
- Running claims-first in production for 3+ months
- Processing 500+ podcasts successfully
- Receiving positive user feedback
- Confirming no critical regressions

---

## Support

If you need help with rollback:

1. **Check logs:** Review `logs/` directory for error messages
2. **Consult docs:** See `CLAIMS_FIRST_ARCHITECTURE_OVERHAUL_PLAN.md` Section 8 (Rollback Plan)
3. **Test incrementally:** Don't rollback everything at once, try partial rollback first
4. **Document issues:** Note what failed so it can be fixed in claims-first v2

---

## Success Indicators (When Backup Can Be Deleted)

Safe to delete backup when ALL of these are true:

- [ ] Claims-first in production for 6+ months
- [ ] No rollbacks needed in last 3 months
- [ ] User satisfaction ≥8/10
- [ ] Speaker attribution accuracy ≥85%
- [ ] <5% bug reports related to new system
- [ ] Processing 1,000+ podcasts/month successfully
- [ ] Team confident in new architecture

**Until then: KEEP THIS BACKUP SAFE**

---

*Last Updated: December 15, 2025*
