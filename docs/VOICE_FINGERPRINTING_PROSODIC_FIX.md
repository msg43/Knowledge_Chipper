# Voice Fingerprinting Prosodic Features Fix

**Date:** October 31, 2025  
**Component:** Voice Fingerprinting / Speaker Verification  
**Severity:** Medium  
**Status:** ✅ Fixed

## Problem

Error encountered during voice fingerprinting feature extraction:

```
ERROR | knowledge_system.voice.voice_fingerprinting:extract_prosodic_features:149 | 
Error extracting prosodic features: all the input arrays must have same number of 
dimensions, but the array at index 0 has 1 dimension(s) and the array at index 1 
has 2 dimension(s)
```

## Root Cause

The `extract_prosodic_features()` method in `VoiceFeatureExtractor` was attempting to concatenate prosodic features, but the `librosa.beat.beat_track()` function has inconsistent return types across different versions:

- **Some versions:** Return `tempo` as a scalar float
- **Other versions:** Return `tempo` as a numpy array

When `tempo` was returned as an array and wrapped in `np.array([tempo])`, it created a nested array with unexpected dimensions (2D instead of 1D), causing a dimension mismatch error during concatenation with the 1D `pitch_features` array.

### Code Location

File: `src/knowledge_system/voice/voice_fingerprinting.py`  
Method: `VoiceFeatureExtractor.extract_prosodic_features()`  
Lines: 139-151

## Solution

Added defensive type checking and conversion to ensure `tempo` is always converted to a scalar float before creating the feature array:

```python
# Tempo estimation
try:
    tempo, _ = librosa.beat.beat_track(y=audio, sr=self.sample_rate)
    # Ensure tempo is a scalar (librosa may return array or scalar)
    if isinstance(tempo, np.ndarray):
        tempo_value = float(tempo.item()) if tempo.size == 1 else float(tempo[0])
    else:
        tempo_value = float(tempo)
    tempo_features = np.array([tempo_value])
except Exception:
    tempo_features = np.array([0.0])
```

### Key Changes

1. **Type Detection:** Check if `tempo` is a numpy array
2. **Array Handling:** Extract scalar value using `.item()` for single-element arrays or `[0]` for multi-element arrays
3. **Scalar Handling:** Direct float conversion for scalar values
4. **Consistent Output:** Always produce a 1D array with shape `(1,)` for `tempo_features`

## Expected Behavior

The `extract_prosodic_features()` method now:

1. ✅ Returns a consistent 1D array with shape `(5,)` containing:
   - Mean pitch (F0)
   - Standard deviation of pitch
   - Minimum pitch
   - Maximum pitch
   - Tempo (BPM)

2. ✅ Handles both scalar and array returns from `librosa.beat.beat_track()`
3. ✅ Properly concatenates pitch and tempo features without dimension errors
4. ✅ Falls back to zeros on extraction failure (graceful degradation)

## Testing

Created automated test script: `scripts/test_prosodic_features_fix.sh`

### Test Results

```bash
$ ./scripts/test_prosodic_features_fix.sh
Testing prosodic features extraction fix...
Extracting prosodic features...
✓ Prosodic features extracted successfully
  Shape: (5,)
  Expected shape: (5,)
✓ Shape is correct (5 features: mean, std, min, max pitch + tempo)
✓ All features are properly formatted as 1D array

✓ All tests passed!
```

### Manual Verification

```python
from knowledge_system.voice.voice_fingerprinting import VoiceFeatureExtractor
import numpy as np

extractor = VoiceFeatureExtractor(sample_rate=16000)
audio = np.random.randn(16000).astype(np.float32)  # 1 second of test audio

features = extractor.extract_prosodic_features(audio)
print(f"Features shape: {features.shape}")  # Should print: (5,)
print(f"Features: {features}")  # Should print 5 scalar values
```

## Impact

- **Severity:** Medium
- **Affected Components:**
  - Voice fingerprinting feature extraction
  - Speaker enrollment (when extracting prosodic features)
  - Speaker verification (when comparing prosodic features)
  - Voice similarity calculations

- **User Impact:**
  - Previously: Voice fingerprinting could fail during feature extraction
  - Now: Robust handling across different librosa versions

## Related Files

- `src/knowledge_system/voice/voice_fingerprinting.py` - Fixed implementation
- `scripts/test_prosodic_features_fix.sh` - Automated test
- `MANIFEST.md` - Updated with fix documentation

## Dependencies

- `librosa` - Audio analysis library (multiple versions supported)
- `numpy` - Array operations

## Future Improvements

Consider pinning `librosa` to a specific version range in `requirements.txt` to ensure consistent API behavior, or add version detection to handle API changes more explicitly.

## Related Issues

This fix ensures compatibility with various versions of librosa that may be installed in different environments or virtual environments, improving the robustness of the voice fingerprinting system.

