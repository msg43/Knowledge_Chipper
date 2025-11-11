# Transcription Model Default Fixed

**Date:** November 4, 2025  
**Status:** ✅ Fixed

## Problem

**User Report:** "Why did transcription model switch to tiny???"

The transcription model was unexpectedly defaulting to **"tiny"** instead of the expected **"medium"** model.

## Root Cause

The bug was in the settings loading logic in `transcription_tab.py`:

```python
# OLD CODE (Line 4046)
saved_model = self.gui_settings.get_combo_selection(
    self.tab_name, "model", ""  # ← Empty string default!
)
if saved_model:  # ← This is False when saved_model = ""
    index = self.model_combo.findText(saved_model)
    if index >= 0:
        self.model_combo.setCurrentIndex(index)
# If saved_model is "", the combo box is never set!
# It stays at index 0, which is "tiny" (first item)
```

**The Problem:**
1. When no saved model exists, `get_combo_selection()` returns `""`
2. The condition `if saved_model:` evaluates to `False` for empty string
3. The model combo box is never set explicitly
4. It defaults to **index 0 = "tiny"** (first item from `get_valid_whisper_models()`)

**Why "tiny" is index 0:**
```python
# From config.py line 17-22
def get_valid_whisper_models() -> list[str]:
    return ["tiny", "base", "small", "medium", "large"]
    #       ^^^^^^ Index 0 - the default when nothing is set!
```

## The Fix

Changed the default from empty string `""` to **`"medium"`**, which matches the config default:

```python
# NEW CODE (Lines 4045-4060)
saved_model = self.gui_settings.get_combo_selection(
    self.tab_name, "model", "medium"  # ✅ Default to medium
)
if saved_model:
    index = self.model_combo.findText(saved_model)
    if index >= 0:
        self.model_combo.setCurrentIndex(index)
    else:
        # If saved model not found, fall back to medium
        logger.warning(
            f"Saved model '{saved_model}' not found in available models. "
            f"Falling back to 'medium'."
        )
        index = self.model_combo.findText("medium")
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
```

**Why "medium" is the correct default:**
```python
# From config.py line 217-219
class TranscriptionConfig(BaseModel):
    whisper_model: str = Field(
        default="medium", pattern="^(tiny|base|small|medium|large)$"
    )
```

## Technical Details

### Settings Hierarchy
The GUI settings manager follows this hierarchy:
1. **Session state** (last model used in current session)
2. **settings.yaml** (`transcription.whisper_model`)
3. **Fallback default** (now correctly set to `"medium"`)

### Model Selection Flow
```
App Launch
    ↓
_load_settings() called
    ↓
get_combo_selection("model", "medium")
    ↓
    ├─ Has session state? → Use it
    ├─ Has settings.yaml value? → Use it  
    └─ Neither? → Use "medium" ✅
    ↓
setCurrentIndex() to selected model
```

### Why This Bug Was Introduced
The empty string default `""` was likely intended to be "unset", but:
- Empty string is **falsy** in Python: `if "":` → `False`
- This caused the setting code to be skipped entirely
- The combo box remained at its default position (index 0)
- Index 0 = "tiny" (first item in the list)

### Added Defensive Logic
The fix also includes a **fallback** if the saved model isn't found:
```python
else:
    # If saved model not found, fall back to medium
    logger.warning(f"Saved model '{saved_model}' not found...")
    index = self.model_combo.findText("medium")
    if index >= 0:
        self.model_combo.setCurrentIndex(index)
```

This handles edge cases like:
- Corrupted settings file
- Model names changed in config
- Invalid model names from older versions

## Files Modified

### `src/knowledge_system/gui/tabs/transcription_tab.py`
**Purpose:** Transcription tab GUI logic

**Changes:**
- Line 4046: Changed default from `""` to `"medium"`
- Lines 4052-4060: Added fallback logic if saved model not found
- Line 4044: Updated comment to reflect "medium" default

## Testing

### Test 1: Fresh Install
1. Delete session state file (or use fresh install)
2. Launch app
3. Go to Transcription tab
4. **Expected:** Model shows "medium" ✅
5. **Before Fix:** Model showed "tiny" ❌

### Test 2: Saved Model Persists
1. Select "large" model
2. Restart app
3. **Expected:** Model shows "large" (saved state)
4. **Result:** Works correctly ✅

### Test 3: Invalid Saved Model
1. Manually edit settings to use invalid model name
2. Launch app
3. **Expected:** Warning logged, falls back to "medium"
4. **Result:** Works correctly ✅

## User Impact

### Before Fix
- ❌ Model defaulted to "tiny" on fresh launch
- ❌ "tiny" gives poor transcription quality
- ❌ Users had to manually change to "medium" every time
- ❌ Confusing user experience

### After Fix
- ✅ Model correctly defaults to "medium"
- ✅ Matches config.py default
- ✅ Better transcription quality by default
- ✅ Consistent with documentation

## Why "Medium" Is the Right Default

### Model Comparison
| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| tiny | 39M | Very Fast | Poor | Testing only |
| base | 74M | Fast | Fair | Quick previews |
| small | 244M | Medium | Good | Casual use |
| **medium** | **769M** | **Balanced** | **Very Good** | **🌟 Recommended** |
| large | 1550M | Slow | Best | Maximum quality |

**"Medium" is the sweet spot:**
- ✅ Good accuracy (better than small)
- ✅ Reasonable speed (faster than large)
- ✅ Works on most hardware
- ✅ Matches config default
- ✅ Consistent with user expectations

**"Tiny" is problematic:**
- ❌ Very poor accuracy
- ❌ Frequent hallucinations
- ❌ Should only be used for testing
- ❌ Not suitable for production use

## Related Issues

- **UI Layout Fix** (November 4, 2025): Moved Proxy selector above YT→RSS
- **Validation Warnings** (November 4, 2025): Filtered out old/test file warnings
- **Color-Coded & Thumbnail Fix** (November 4, 2025): Disabled color-coded transcripts, fixed thumbnails

## Conclusion

The model was defaulting to "tiny" because the fallback was an empty string, which left the combo box at index 0 ("tiny"). 

**Fix:** Changed fallback from `""` to `"medium"`, matching the config default.

**Result:** Users now get the expected "medium" model by default, providing much better transcription quality! ✅
