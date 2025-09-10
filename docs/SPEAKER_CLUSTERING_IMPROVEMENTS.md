# Speaker Clustering Improvements for Interview Scenarios

## Problem Description

The original issue was with speaker diarization clustering where multiple distinct speakers (like an interviewer and interviewee) were being grouped under the same speaker ID. This happened because the "conservative" diarization sensitivity settings were too aggressive in merging different speakers together.

## Root Cause Analysis

The problem was in the diarization clustering parameters, not the LLM speaker assignment:

### Original Conservative Settings (Problematic)
- **Clustering threshold**: 0.85 (too high - voices needed to be very different to be separate)
- **Min cluster size**: 25 (too large - forced small segments to merge)
- **Min duration**: 1.5s (too long - merged quick exchanges)
- **Silence detection**: 0.5s (missed rapid turn-taking)

These settings were designed to prevent false speaker splits in single-speaker content, but were too restrictive for interviews with distinct speakers.

## Solution Implemented

### 1. Configuration Update (`config/settings.yaml`)
```yaml
# Speaker identification and diarization settings
speaker_identification:
  # Change from "conservative" to "balanced" for better interview separation
  diarization_sensitivity: "balanced"  # Options: aggressive, balanced, conservative
  
  # Additional clustering improvements for interviews
  min_speaker_duration: 0.5  # Shorter minimum duration for quick exchanges
  speaker_separation_threshold: 0.7  # Lower threshold = easier to separate speakers
```

### 2. Enhanced Clustering Parameters

#### Balanced Sensitivity (Optimized for Interviews)
- **Clustering threshold**: 0.65 ↓ (reduced from 0.7)
- **Min cluster size**: 12 ↓ (reduced from 15) 
- **Min duration**: 0.4s ↓ (reduced from 0.5s)
- **Silence detection**: 0.3s ↓ (reduced from 0.5s)

#### Aggressive Sensitivity (Maximum Speaker Detection)
- **Clustering threshold**: 0.55 ↓ (reduced from 0.6)
- **Min cluster size**: 8 ↓ (reduced from 10)
- **Min duration**: 0.25s ↓ (reduced from 0.3s)
- **Silence detection**: 0.2s ↓ (very short silence detection)

#### Conservative Sensitivity (Unchanged - Single Speaker Bias)
- **Clustering threshold**: 0.85 (high threshold for fewer speakers)
- **Min cluster size**: 25 (large cluster size)
- **Min duration**: 1.5s (long minimum segments)
- **Silence detection**: 0.5s (longer silence required)

## Usage Guidelines

### For Different Content Types

**Interviews & Conversations** → Use **"balanced"** sensitivity
- Perfect for Q&A sessions, podcast interviews, debates
- Better separation of distinct speakers
- Handles quick back-and-forth exchanges

**Panel Discussions & Group Meetings** → Use **"aggressive"** sensitivity  
- Maximum speaker detection for multiple participants
- Catches even brief interjections
- May create more speaker splits (which can be merged later)

**Single Speaker Content** → Use **"conservative"** sensitivity
- Lectures, monologues, presentations
- Prevents false speaker splits from background noise
- Biased toward fewer speakers

### Changing Sensitivity Settings

Currently, diarization sensitivity is configured in `config/settings.yaml`. To change it:

1. Edit `/Users/matthewgreer/Projects/Knowledge_Chipper/config/settings.yaml`
2. Change the `diarization_sensitivity` value:
   ```yaml
   speaker_identification:
     diarization_sensitivity: "balanced"  # or "aggressive" or "conservative"
   ```
3. Restart the application for changes to take effect

## Expected Improvements

With the "balanced" sensitivity settings, you should see:

1. **Better Speaker Separation**: Distinct speakers (interviewer/interviewee) should get separate speaker IDs
2. **Faster Turn-Taking Detection**: Quick exchanges will be captured as separate segments
3. **Reduced False Merging**: Different voices won't be incorrectly grouped together
4. **Maintained Quality**: Still prevents excessive over-segmentation

## Testing Your Changes

To test the improvements:

1. Use the same interview content that previously had clustering issues
2. Ensure `diarization_sensitivity: "balanced"` is set in your config
3. Run diarization again and check if distinct speakers get separate IDs
4. If still not separated enough, try `"aggressive"` sensitivity
5. If too many speakers created, use `"conservative"`

## Future Enhancements

Potential improvements for the GUI:
- Add diarization sensitivity dropdown in transcription settings
- Real-time preview of clustering parameters
- Content-type detection for automatic sensitivity selection

## Technical Details

The clustering improvements work by:
- **Lower thresholds** make it easier to consider voices as different speakers
- **Smaller cluster sizes** prevent forced merging of distinct speaker segments  
- **Shorter durations** capture rapid speaker changes
- **Better silence detection** identifies turn-taking in conversations

This balances the trade-off between speaker separation accuracy and computational efficiency while maintaining compatibility with MPS acceleration on Apple Silicon.
