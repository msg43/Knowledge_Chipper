# Voice Fingerprinting Fix - November 2025

## Problem

Voice fingerprinting was not merging speakers in single-speaker monologues. The system would detect 2 speakers when there should only be 1, and the log message "Voice fingerprinting did NOT merge speakers (still have 2 speakers)" would appear.

## Root Cause

The voice fingerprinting system was receiving the **wrong audio file path**. It was being passed the original input file (e.g., `.mp4`, `.m4a`) instead of the converted 16kHz mono WAV file that was used for diarization.

### Technical Details

1. **Audio Processing Flow:**
   - Original file (`path`) → Audio conversion → Temporary WAV file (`output_path`)
   - Diarization runs on `output_path` (16kHz mono WAV)
   - Voice fingerprinting needs to analyze the SAME file used for diarization

2. **The Bug:**
   - In `audio_processor.py` line 2115, the code was passing `str(path)` (original file)
   - Should have been passing `str(output_path)` (converted WAV file)
   - Voice fingerprinting couldn't properly analyze the audio because:
     - Original file might be in different format (MP4, M4A, etc.)
     - Original file might have different sample rate or channels
     - Audio features would not match the diarization segments

3. **Why It Failed:**
   - Voice fingerprinting extracts audio segments based on diarization timestamps
   - If the audio file format/sample rate doesn't match, segment extraction fails
   - Without proper audio analysis, speakers cannot be merged
   - System falls back to keeping all speakers separate

## The Fix

Changed line 2115 in `src/knowledge_system/processors/audio_processor.py`:

```python
# BEFORE (incorrect):
str(path),  # Pass audio path for voice fingerprinting

# AFTER (correct):
str(output_path),  # Pass converted WAV path for voice fingerprinting (same file used for diarization)
```

## Impact

### What This Fixes:
- ✅ Voice fingerprinting now receives the correct audio file
- ✅ Audio segments can be properly extracted based on diarization timestamps
- ✅ Voice similarity analysis works correctly
- ✅ Single-speaker monologues will be correctly merged (2 speakers → 1 speaker)
- ✅ Over-segmented speakers in multi-speaker content will be properly merged

### What Remains Unchanged:
- Manual review queueing still works (happens after automatic assignment)
- Fallback to text-based similarity still works if audio is unavailable
- All other speaker identification features remain intact

## Testing Recommendations

Test with:
1. **Single-speaker monologue** (should detect 1 speaker, not 2+)
2. **Two-speaker interview** (should detect 2 speakers, not 4+)
3. **Multi-speaker podcast** (should detect correct number of speakers)
4. **Various audio formats** (MP4, M4A, WAV, etc.)

Expected behavior:
- Voice fingerprinting should merge similar speakers
- Log should show: "✅ Voice fingerprinting merged speakers: X → Y"
- Final speaker count should match actual number of distinct voices

## Related Files

- `src/knowledge_system/processors/audio_processor.py` - Fixed audio path passing
- `src/knowledge_system/processors/speaker_processor.py` - Voice fingerprinting logic
- `src/knowledge_system/voice/voice_fingerprinting.py` - Core fingerprinting system
- `docs/STAGE_2_VOICE_FINGERPRINTING_COMPLETE.md` - Voice fingerprinting documentation

## Date Fixed

November 10, 2025
