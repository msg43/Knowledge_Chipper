# Button Stuck at "Checking Model Availability" Fix

## Issue

The "Start Summarization" button gets stuck showing "🔍 Checking model availability..." and never changes back, even though processing starts successfully.

## Root Cause

**File**: `src/knowledge_system/gui/tabs/summarization_tab.py`

### The Problem

When using local models (Ollama), the summarization flow is:

1. **T+0**: User clicks "Start Summarization"
2. **T+1**: Button disabled, text set to "🔍 Checking model availability..."
3. **T+2**: Async model check runs (detects model has "(Installed)" suffix)
4. **T+3**: Model check succeeds, calls `_continue_processing_after_model_check()`
5. **T+4**: Calls `_start_summarization_worker()` which calls `set_processing_state(True)`
6. **BUG**: `set_processing_state(True)` disables the button but **does NOT update the text**!

### Why It Happens

The `set_processing_state()` method in `BaseTab` only enables/disables buttons:

```python
def set_processing_state(self, processing: bool) -> None:
    if hasattr(self, "start_btn"):
        self.start_btn.setEnabled(not processing)  # ✅ Disables button
    if hasattr(self, "stop_btn"):
        self.stop_btn.setEnabled(processing)  # ✅ Enables stop button
    # ❌ Does NOT update button text!
```

So the button stays disabled with the old text "🔍 Checking model availability..." instead of showing "Start Summarization" (which would then be disabled during processing).

## Solution

**Lines 1671-1674**: Reset button text before starting worker

```python
def _start_summarization_worker(self, files: list, gui_settings: dict) -> None:
    """Start the summarization worker with the provided settings."""
    # Reset button text before starting processing
    if hasattr(self, "start_btn"):
        self.start_btn.setText(self._get_start_button_text())
    
    # Start worker...
```

This ensures the button text is reset to "Start Summarization" before `set_processing_state(True)` disables it.

## Why This Wasn't Caught Earlier

The issue only affects the **local provider path** with async model checking:

- ✅ **OpenAI/Anthropic**: No model check, button works fine
- ✅ **Local (first time)**: Model not installed, shows download dialog, button resets
- ❌ **Local (model installed)**: Quick model check succeeds, button text never resets

The bug is in the success path for already-installed local models.

## Related Code Paths

### Paths That Correctly Reset Button

1. **Model check fails** (Line 1591):
   ```python
   self.start_btn.setEnabled(True)
   self.start_btn.setText(self._get_start_button_text())
   ```

2. **Service not running** (Line 1539):
   ```python
   self.start_btn.setEnabled(True)
   self.start_btn.setText(self._get_start_button_text())
   ```

3. **Download dialog closes** (Line 1628):
   ```python
   self.start_btn.setEnabled(True)
   self.start_btn.setText(self._get_start_button_text())
   ```

### Path That Was Missing Reset

4. **Model check succeeds** (Line 1582):
   ```python
   # ❌ Missing button text reset!
   self._continue_processing_after_model_check()
   ```

## Testing

### Before Fix
1. Select local provider with installed model (e.g., "qwen2.5:7b-instruct (Installed)")
2. Click "Start Summarization"
3. Button shows "🔍 Checking model availability..."
4. Processing starts but button stays stuck with that text

### After Fix
1. Select local provider with installed model
2. Click "Start Summarization"
3. Button shows "🔍 Checking model availability..." briefly
4. Button text resets to "Start Summarization" and becomes disabled
5. Processing proceeds normally

## Files Modified

- `src/knowledge_system/gui/tabs/summarization_tab.py`:
  - Lines 1671-1674: Added button text reset before starting worker

## Related Issues

This is separate from the "Flagship Evaluator Model dropdown empty" issue, which was about model selection not loading. This issue is about the button state after model selection works correctly.

Both issues were discovered during the same testing session but have different root causes:
- **Dropdown empty**: Model name mismatch with "(Installed)" suffix
- **Button stuck**: Missing button text reset in success path
