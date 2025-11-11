# Voice Fingerprinting Diagnosis - November 10, 2025

## Problem

Voice fingerprinting is not merging speakers in single-speaker monologues. The system detects 2 speakers when there should only be 1, and logs show "Voice fingerprinting did NOT merge speakers (still have 2 speakers)".

## Two-Tier Voice Fingerprinting System

The system has two stages:

### Stage 1: Audio-Based Voice Fingerprinting (Primary)
- **Location**: `src/knowledge_system/processors/speaker_processor.py` → `_voice_fingerprint_merge_speakers()`
- **Method**: Extracts audio segments for each detected speaker and generates multi-modal voice fingerprints
- **Features Used**:
  - MFCC (Mel-frequency cepstral coefficients) - 20% weight
  - Spectral features (centroid, rolloff, zero crossing) - 10% weight
  - Prosodic features (pitch, tempo, rhythm) - 10% weight
  - Wav2Vec2 embeddings (deep learning) - 30% weight
  - ECAPA-TDNN embeddings (speaker verification) - 30% weight
- **Threshold**: 0.7 (70% similarity = same person)
- **Fallback**: If audio is unavailable or errors occur, falls back to text-based heuristics

### Stage 2: Text-Based Heuristics (Fallback)
- **Location**: `src/knowledge_system/processors/speaker_processor.py` → `_voice_fingerprint_merge_speakers_fallback()`
- **Method**: Compares speaker segments based on text patterns
- **Used When**: Audio path is missing, audio file doesn't exist, or audio processing fails

## Diagnostic Enhancements Added

I've added comprehensive logging to identify exactly why the voice fingerprinting is failing:

### 1. Feature Extraction Logging
**File**: `src/knowledge_system/voice/voice_fingerprinting.py` (lines 426-438)

Now logs which features were successfully extracted vs. empty:
```
Voice fingerprint extracted - Success: [mfcc, spectral, prosodic], Empty: [wav2vec2, ecapa]
```

This tells us if the deep learning models (wav2vec2, ecapa) are loading properly.

### 2. Feature Comparison Logging
**File**: `src/knowledge_system/voice/voice_fingerprinting.py` (lines 445-495)

Now logs detailed information about which features are being used for similarity calculation:
```
Voice similarity features - Available: [mfcc=0.850, spectral=0.720], Missing: [prosodic(missing), wav2vec2(missing), ecapa(missing)]
Voice similarity calculated: 0.785 from 2 features (total weight: 0.30)
```

This shows:
- Which features are available for comparison
- Which features are missing or have errors
- The individual similarity scores for each feature
- The final weighted similarity score
- The total weight used (should be 1.0 if all features available, lower if some missing)

### 3. Speaker Comparison Logging
**File**: `src/knowledge_system/processors/speaker_processor.py` (lines 669-673)

Now ALWAYS logs similarity scores between all speaker pairs:
```
🔍 Voice similarity: SPEAKER_00 vs SPEAKER_01 = 0.650 (threshold: 0.7, will_merge: False)
```

This shows:
- Which speakers are being compared
- The actual similarity score
- Whether it meets the threshold for merging
- Why speakers are NOT being merged

## Verification Checklist

Before diagnosing voice fingerprinting issues, verify these prerequisites:

### ✅ Audio Format Check
Look for these log entries:
```
🔍 Loading audio for voice fingerprinting: /tmp/audio_xyz.wav
🔍 File exists: True, Size: X.XX MB
🔍 Audio loaded - Shape: (XXXXXX,), Sample rate: 16000Hz, Duration: XX.XXs
```

**Red flags:**
- ❌ File path shows `.mp4`, `.m4a`, or other non-WAV format
- ❌ Sample rate is not 16000Hz
- ❌ Shape shows 2 dimensions (stereo instead of mono)
- ❌ "Audio file not found" or "using fallback"

### ✅ CSV Database Check
Look for these log entries:
```
🔍 _get_known_hosts_from_channel() called
🔍 Extracted channel info - ID: XXXXX, Name: XXXXX
✅ channel_hosts.csv found, size: 13942 bytes
✅ Loaded 524 channel/podcast mappings from CSV
✅ CSV lookup SUCCESS - Channel 'XXXXX' is hosted by: XXXXX
```

**Red flags:**
- ❌ "_get_known_hosts_from_channel() called" is missing (function not invoked)
- ❌ "No metadata provided for channel host lookup - CSV will not be used"
- ❌ "channel_hosts.csv NOT FOUND"
- ❌ "CSV lookup FAILED - No host mapping found"
- ❌ Loaded count is not ~524 entries

## Possible Root Causes

Based on the diagnostic logging, here are the likely issues:

### 1. Deep Learning Models Not Loading
**Symptoms**:
- `wav2vec2` and `ecapa` features are empty
- Total weight in similarity calculation is only 0.3-0.4 instead of 1.0
- Only traditional features (mfcc, spectral, prosodic) are available

**Impact**:
- Without the deep learning models (60% of the weight), similarity scores will be much lower
- Traditional features alone may not be discriminative enough for single-speaker detection
- A monologue might score 0.65 instead of 0.85, falling below the 0.7 threshold

**Solution**:
- Check if `transformers` and `speechbrain` packages are installed
- Verify models are being downloaded/loaded correctly
- Check device compatibility (CPU/MPS/CUDA)

### 2. Audio Segment Extraction Issues
**Symptoms**:
- "No valid audio segments for SPEAKER_XX" messages
- Fingerprints not being extracted at all

**Impact**:
- If audio segments can't be extracted, no fingerprints are created
- Falls back to text-based heuristics which are less reliable

**Solution**:
- Verify the audio file path is correct (should be the converted 16kHz WAV)
- Check segment timestamps are valid
- Ensure audio file has sufficient duration

### 3. Similarity Threshold Too High
**Symptoms**:
- Similarity scores consistently between 0.6-0.7
- Speakers are clearly the same but just below threshold

**Impact**:
- Legitimate matches are being rejected

**Solution**:
- Consider lowering threshold from 0.7 to 0.65 for single-speaker scenarios
- Or implement adaptive threshold based on number of speakers detected

### 4. Feature Extraction Errors
**Symptoms**:
- Features show as "error" in the logs
- Exception messages in the logs

**Impact**:
- Fewer features available for comparison
- Lower confidence in similarity scores

**Solution**:
- Check for audio format issues
- Verify sample rate is 16kHz
- Check for corrupted audio segments

## Critical Diagnostic Checks Added

### Audio Format Verification
The system now logs the audio file being passed to voice fingerprinting:
```
🔍 Loading audio for voice fingerprinting: /path/to/file.wav
🔍 File exists: True, Size: 2.34 MB
🔍 Audio loaded - Shape: (224000,), Sample rate: 16000Hz, Duration: 14.00s
```

This confirms:
- ✅ The correct converted WAV file is being used (not the original MP4/M4A)
- ✅ Audio is mono (shape shows single dimension)
- ✅ Sample rate is 16kHz as required
- ✅ Audio duration matches expectations

### CSV Database Verification
The system now logs CSV loading and usage:
```
🔍 _get_known_hosts_from_channel() called
🔍 Extracted channel info - ID: UC2D2CMWXMOVWx7giW1n3LIg, Name: Huberman Lab, RSS: None, Source: youtube_abc123
🔍 Looking for channel_hosts.csv at: /path/to/config/channel_hosts.csv
✅ channel_hosts.csv found, size: 13942 bytes
✅ Loaded 524 channel/podcast mappings from CSV
📺 Found host by channel ID: UC2D2CMWXMOVWx7giW1n3LIg → Andrew D. Huberman
✅ CSV lookup SUCCESS - Channel 'Huberman Lab' is hosted by: Andrew D. Huberman
   → LLM will use this context to match speakers to this name
```

This confirms:
- ✅ The CSV lookup function is being called
- ✅ Channel metadata is being extracted correctly
- ✅ CSV file exists and is loaded
- ✅ Correct number of mappings loaded (should be ~524 for 262 podcasts with 2 lookup keys each)
- ✅ Host name is found and passed to LLM

## What to Look For in Logs

When you run a transcription with a single-speaker monologue, look for these log entries:

### 1. Voice Fingerprinting Initialization
```
🎯 Voice fingerprinting available - analyzing speaker segments
```
✅ Good: System is attempting voice fingerprinting
❌ Bad: If missing, voice fingerprinting is not being invoked

### 2. Feature Extraction
```
Voice fingerprint extracted - Success: [mfcc, spectral, prosodic, wav2vec2, ecapa], Empty: []
```
✅ Good: All 5 features extracted
⚠️ Warning: If wav2vec2 or ecapa are empty, deep learning models aren't working
❌ Bad: If only traditional features (mfcc, spectral, prosodic) are available

### 3. Similarity Calculation
```
Voice similarity features - Available: [mfcc=0.850, spectral=0.720, prosodic=0.680, wav2vec2=0.920, ecapa=0.950], Missing: []
Voice similarity calculated: 0.862 from 5 features (total weight: 1.00)
```
✅ Good: All features available, high similarity score (>0.7)
⚠️ Warning: If total weight < 1.0, some features are missing
❌ Bad: If similarity < 0.7 for a single-speaker monologue

### 4. Speaker Comparison
```
🔍 Voice similarity: SPEAKER_00 vs SPEAKER_01 = 0.862 (threshold: 0.7, will_merge: True)
🔗 Voice fingerprinting: SPEAKER_00 and SPEAKER_01 are likely the same speaker (similarity: 0.862)
🎯 Merged SPEAKER_01 into SPEAKER_00 (voice similarity: 0.862)
```
✅ Good: Speakers merged successfully
❌ Bad: `will_merge: False` means similarity is below threshold

### 5. Final Result
```
✅ Voice fingerprinting merged speakers: 2 → 1
```
✅ Good: Speakers were merged
❌ Bad: "Voice fingerprinting did NOT merge speakers (still have 2 speakers)"

## Testing Instructions

1. **Run a single-speaker transcription** with the enhanced logging
2. **Capture the full log output** and search for the patterns above
3. **Share the relevant log sections** showing:
   - Feature extraction results
   - Similarity calculation details
   - Speaker comparison scores
   - Final merge decision

## Expected Behavior

For a single-speaker monologue with a distinctive voice:
- **Similarity score should be**: 0.85-0.95 (very high)
- **All 5 features should extract**: mfcc, spectral, prosodic, wav2vec2, ecapa
- **Total weight should be**: 1.0
- **Result**: Speakers should merge (2 → 1)

## Next Steps

Based on the diagnostic logs, we can:

1. **If deep learning models are missing**: Install/configure transformers and speechbrain
2. **If similarity is just below threshold**: Adjust threshold or implement adaptive logic
3. **If audio extraction fails**: Fix audio file path or format issues
4. **If features have errors**: Debug specific feature extraction code

## Files Modified

1. `src/knowledge_system/processors/speaker_processor.py`
   - Added detailed logging for speaker similarity comparisons (lines 669-673)

2. `src/knowledge_system/voice/voice_fingerprinting.py`
   - Added feature extraction success/failure logging (lines 426-438)
   - Added detailed feature comparison logging (lines 445-495)

## Related Documentation

- `docs/STAGE_2_VOICE_FINGERPRINTING_COMPLETE.md` - Original implementation
- `VOICE_FINGERPRINTING_FIX_NOV_2025.md` - Previous fix for audio path issue
- `docs/SPEAKER_IDENTIFICATION_SYSTEM.md` - Overall system architecture
- `SPEAKER_ATTRIBUTION_UPGRADE_COMPLETE.md` - Pipeline overview
