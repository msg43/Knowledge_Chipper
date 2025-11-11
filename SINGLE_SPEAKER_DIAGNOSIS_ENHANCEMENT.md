# Single-Speaker Over-Segmentation Diagnosis Enhancement

**Date:** November 9, 2025  
**Context:** User reported SPEAKER_01 appearing in a Sam Harris video that has only ONE speaker

## The Real Problem

The video has **only ONE speaker** (Sam Harris monologue), but:
1. Diarization incorrectly split him into `SPEAKER_00` and `SPEAKER_01`
2. Voice fingerprinting failed to merge them back together
3. Heuristic over-segmentation detection failed to merge them
4. LLM received 2 speaker IDs and either:
   - Only provided name for one (the bug)
   - Provided different names for both (violating the "same person" rule)

## System Architecture for Handling This

The system has **THREE defensive layers** to handle over-segmentation:

### Layer 1: Voice Fingerprinting
**File:** `src/knowledge_system/processors/speaker_processor.py` (lines 532-671)  
**Purpose:** Use ECAPA-TDNN embeddings to detect same voice, merge speaker IDs BEFORE LLM sees them  
**Status:** Should have merged SPEAKER_00 and SPEAKER_01 but didn't

### Layer 2: Heuristic Over-Segmentation Detection  
**File:** `src/knowledge_system/processors/speaker_processor.py` (lines 472-531)  
**Purpose:** Text-based similarity analysis to merge speakers with similar patterns  
**Status:** Should have merged as fallback but didn't

### Layer 3: LLM Smart Assignment
**File:** `src/knowledge_system/utils/llm_speaker_suggester.py` (lines 408-414)  
**Purpose:** LLM analyzes content and assigns SAME name to both IDs if they're the same person  
**Status:** Either didn't provide name for SPEAKER_01, or provided different names

## Diagnostic Enhancements Added

### Enhancement 1: Speaker Merging Diagnostics

**File:** `src/knowledge_system/processors/speaker_processor.py`  
**Lines:** 184-209

Added logging to track speaker count before/after each merging layer:

```python
# Track voice fingerprinting
speaker_count_before_voice = len(speaker_map)
self._voice_fingerprint_merge_speakers(speaker_map, audio_path)
speaker_count_after_voice = len(speaker_map)

if speaker_count_after_voice < speaker_count_before_voice:
    logger.info(f"✅ Voice fingerprinting merged speakers: {speaker_count_before_voice} → {speaker_count_after_voice}")
elif speaker_count_before_voice > 1:
    logger.warning(f"⚠️ Voice fingerprinting did NOT merge speakers (still have {speaker_count_before_voice} speakers)")

# Track heuristic merging  
speaker_count_before_heuristic = len(speaker_map)
self._detect_and_merge_oversegmented_speakers(speaker_map)
speaker_count_after_heuristic = len(speaker_map)

if speaker_count_after_heuristic < speaker_count_before_heuristic:
    logger.info(f"✅ Heuristic merging merged speakers: {speaker_count_before_heuristic} → {speaker_count_after_heuristic}")
elif speaker_count_before_heuristic > 1:
    logger.warning(f"⚠️ Heuristic merging did NOT merge speakers (still have {speaker_count_before_heuristic} speakers)")
```

**What This Reveals:**
- Shows exactly which layer (if any) successfully merged speakers
- Warns when merging should have happened but didn't
- Helps identify if voice fingerprinting is working or falling back

### Enhancement 2: Single-Speaker Detection Logging

**File:** `src/knowledge_system/utils/llm_speaker_suggester.py`  
**Lines:** 198-227

Added intelligent logging for single-speaker scenarios:

```python
# Check if LLM correctly assigned same name to multiple speaker IDs
if len(all_names) != len(unique_names):
    name_counts = {}
    for speaker_id, (name, conf) in suggestions.items():
        if name not in name_counts:
            name_counts[name] = []
        name_counts[name].append(speaker_id)
    
    for name, speaker_ids in name_counts.items():
        if len(speaker_ids) > 1:
            logger.info(f"✅ LLM correctly assigned '{name}' to {len(speaker_ids)} speaker IDs: {speaker_ids}")
            logger.info(f"   This is CORRECT behavior for single-speaker content that was over-segmented by diarization")

# Detect single-speaker over-segmentation
if len(speaker_segments) > 1 and len(unique_names) == 1:
    logger.info(f"🎯 SINGLE-SPEAKER DETECTION: {len(speaker_segments)} speaker IDs but only 1 unique name")
    logger.info(f"   This indicates diarization over-segmented a monologue/solo podcast")
```

**What This Reveals:**
- Confirms when LLM correctly handles single-speaker over-segmentation
- Distinguishes between "duplicate names bug" vs "correct single-speaker handling"
- Makes it obvious when the system is working as designed

## Expected Log Output for Sam Harris Video

### If System Works Correctly:
```
🔍 Preparing speaker data from 2 diarization segments...
⚠️ Voice fingerprinting did NOT merge speakers (still have 2 speakers)
⚠️ Heuristic merging did NOT merge speakers (still have 2 speakers)
LLM suggested names for 2 speakers
  SPEAKER_00 -> 'Sam Harris' (confidence: 0.95)
  SPEAKER_01 -> 'Sam Harris' (confidence: 0.95)
✅ LLM correctly assigned 'Sam Harris' to 2 speaker IDs: ['SPEAKER_00', 'SPEAKER_01']
   This is CORRECT behavior for single-speaker content that was over-segmented by diarization
🎯 SINGLE-SPEAKER DETECTION: 2 speaker IDs but only 1 unique name ('Sam Harris')
   This indicates diarization over-segmented a monologue/solo podcast
```

### If Bug Occurs (what we saw):
```
🔍 Preparing speaker data from 2 diarization segments...
⚠️ Voice fingerprinting did NOT merge speakers (still have 2 speakers)
⚠️ Heuristic merging did NOT merge speakers (still have 2 speakers)
LLM suggested names for 1 speakers  ← ONLY 1!
  SPEAKER_00 -> 'Sam Harris' (confidence: 0.95)
🚨 CRITICAL: LLM did not provide name for SPEAKER_01 - this should NEVER happen!
   All suggestions received: ['SPEAKER_00']
   All speakers in segments: ['SPEAKER_00', 'SPEAKER_01']
Emergency fallback: SPEAKER_01 -> 'Unknown Speaker B'
```

## Root Cause Possibilities

Based on the enhanced logging, we'll be able to identify:

### Possibility 1: Voice Fingerprinting Not Running
- Log shows: "Voice fingerprinting not available" or import error
- **Fix:** Ensure voice fingerprinting dependencies are installed

### Possibility 2: Voice Fingerprinting Too Conservative
- Log shows: "⚠️ Voice fingerprinting did NOT merge speakers"
- Similarity threshold may be too high (currently requires 0.85 cosine similarity)
- **Fix:** Lower threshold for single-speaker detection

### Possibility 3: LLM Response Incomplete
- Log shows: "LLM suggested names for 1 speakers" (should be 2)
- LLM only analyzed first part of transcript where SPEAKER_00 appears
- **Fix:** Ensure LLM sees samples from ALL speakers

### Possibility 4: LLM Key Normalization Issue
- LLM returns `SPEAKER_0` but code expects `SPEAKER_00`
- Normalization code fails to match them
- **Fix:** Already has normalization, but may need debugging

## Testing Instructions

1. **Re-transcribe the Sam Harris video:**
   ```bash
   # Run with verbose logging
   python -m knowledge_system transcribe "https://www.youtube.com/watch?v=y4iShNoJJLc"
   ```

2. **Check the logs for:**
   - "Voice fingerprinting merged speakers" (should happen but probably doesn't)
   - "Heuristic merging merged speakers" (should happen as fallback)
   - "LLM suggested names for X speakers" (X should equal number of speaker IDs)
   - "SINGLE-SPEAKER DETECTION" (should appear if LLM correctly handles it)
   - "CRITICAL: LLM did not provide name" (should NOT appear)

3. **Expected Outcome:**
   - Either Layer 1 or Layer 2 merges speakers → Only 1 speaker ID sent to LLM
   - OR Layer 3 assigns same name to both → All segments show "Sam Harris"
   - NO "SPEAKER_01" labels in final transcript

## Files Modified

1. `src/knowledge_system/processors/speaker_processor.py`
   - Added speaker merging diagnostics (lines 184-209)

2. `src/knowledge_system/utils/llm_speaker_suggester.py`
   - Added single-speaker detection logging (lines 198-227)
   - Improved duplicate name handling to distinguish correct vs incorrect duplicates

## Next Steps

1. Re-transcribe the video with enhanced logging
2. Identify which layer is failing:
   - If voice fingerprinting isn't merging → Check similarity threshold
   - If heuristic merging isn't working → Check text similarity algorithm
   - If LLM isn't providing all names → Check LLM prompt/response parsing
3. Apply targeted fix based on which layer failed
4. Consider making voice fingerprinting more aggressive for single-speaker detection

## Why This Matters

Single-speaker content (monologues, solo podcasts, commentary) is VERY common:
- Sam Harris monologues
- Solo YouTube commentary
- Audiobook narration
- Lecture recordings

Diarization systems frequently over-segment these because:
- Voice changes slightly over time (fatigue, mic position)
- Background noise creates false speaker boundaries
- Pauses/silence trigger new speaker detection

**The system is DESIGNED to handle this, but something in the chain is failing.**

The enhanced logging will pinpoint exactly where.
