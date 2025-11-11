# Summarization Tab Redundancy and Crash Fix

## Issue

Two problems were identified in the summarization tab:

1. **Missing Widget Crash**: `AttributeError: 'SummarizationTab' object has no attribute 'flagship_file_tokens_spin'`
2. **Redundant File List Calls**: `_get_file_list()` was being called 3 times during startup

## Root Causes

### 1. Missing Widgets
The code referenced two spin box widgets that were never created:
- `self.flagship_file_tokens_spin`
- `self.flagship_session_tokens_spin`

These were being accessed in `_start_processing()` at lines 1290-1291 and 3462-3463.

### 2. Redundant Calls
The file list was being retrieved multiple times:
1. `validate_inputs()` - line 1390 (necessary for validation)
2. `_start_processing()` - line 1233 (stored in `_pending_files`)
3. `_continue_processing_after_model_check()` - line 1354 (redundant!)

## Fixes Applied

### 1. Missing Widget Fix
Replaced widget references with sensible default values:

```python
# Before (crashed):
"flagship_file_tokens": self.flagship_file_tokens_spin.value(),
"flagship_session_tokens": self.flagship_session_tokens_spin.value(),

# After (works):
"flagship_file_tokens": 8000,  # Default token limit per file
"flagship_session_tokens": 128000,  # Default session token limit
```

**Rationale**: These are advanced token limit settings that:
- Are not exposed in the UI
- Have sensible defaults (8K per file, 128K session limit)
- Don't need user configuration for normal operation

### 2. Redundancy Fix
Modified `_continue_processing_after_model_check()` to use cached file list:

```python
# Before (redundant call):
file_list = self._get_file_list()

# After (uses cache):
file_list = self._pending_files if hasattr(self, '_pending_files') and self._pending_files else self._get_file_list()
```

**Impact**: Reduces file list retrieval from 3 calls to 2 calls:
- 1st call: `validate_inputs()` - validates files exist
- 2nd call: `_start_processing()` - stores in `_pending_files`
- ~~3rd call~~: Uses cached `_pending_files` instead

## Files Modified

- `src/knowledge_system/gui/tabs/summarization_tab.py`
  - Lines 1290-1291: Replaced widget references with defaults
  - Line 1355: Use cached file list
  - Lines 3462-3463: Replaced widget references with defaults

## Testing

The fix resolves:
- ✅ AttributeError crash on summarization start
- ✅ Redundant file list calls (3 → 2)
- ✅ Cleaner startup logs

## Related Issues

This fix is part of the larger summarization stability improvements:
- Event loop fixes (PARALLEL_PROCESSING_FIX.md)
- Schema alignment (SUMMARIZATION_CRASH_FIX.md)
- Sequential processing for Ollama reliability
