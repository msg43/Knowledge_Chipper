# Code Duplication Elimination - Summarization Tab

## Issue

Massive code duplication in `_start_processing()` method with two nearly identical code paths for local vs non-local providers.

## The Redundancy

### Before Refactoring

**Lines 1299-1328** (Local provider path):
```python
# Get content type from combo box
content_type_map = {
    "Transcript (Own)": "transcript_own",
    "Transcript (Third-party)": "transcript_third_party",
    "Document (PDF/eBook)": "document_pdf",
    "Document (White Paper)": "document_whitepaper",
}
content_type = content_type_map.get(
    self.content_type_combo.currentText(), "transcript_own"
)

self._pending_gui_settings = {
    "provider": provider,
    "model": model,
    "max_tokens": 10000,
    # ... 15 more settings
}
```

**Lines 1336-1366** (Non-local provider path):
```python
# Get content type from combo box
content_type_map = {
    "Transcript (Own)": "transcript_own",
    "Transcript (Third-party)": "transcript_third_party",
    "Document (PDF/eBook)": "document_pdf",
    "Document (White Paper)": "document_whitepaper",
}
content_type = content_type_map.get(
    self.content_type_combo.currentText(), "transcript_own"
)

gui_settings = {
    "provider": provider,
    "model": model,
    "max_tokens": 10000,
    # ... 15 more settings (nearly identical!)
}
```

**Lines 1369-1385** (Non-local provider path):
```python
self.summarization_worker = EnhancedSummarizationWorker(...)
self.summarization_worker.progress_updated.connect(...)
self.summarization_worker.file_completed.connect(...)
# ... 6 signal connections
self.active_workers.append(self.summarization_worker)
self.set_processing_state(True)
self.clear_log()
```

**Lines 1675-1692** (After async model check):
```python
self.summarization_worker = EnhancedSummarizationWorker(...)
self.summarization_worker.progress_updated.connect(...)
self.summarization_worker.file_completed.connect(...)
# ... 6 signal connections (IDENTICAL!)
self.active_workers.append(self.summarization_worker)
self.set_processing_state(True)
self.clear_log()
```

### Duplication Summary

1. **Content type mapping**: Duplicated 2x (lines 1299-1307, 1336-1344)
2. **GUI settings dict**: Duplicated 2x (lines 1309-1328, 1346-1366)
3. **Worker creation + signals**: Duplicated 2x (lines 1369-1385, 1675-1692)

**Total**: ~80 lines of duplicated code

## Solution

### Extract Helper Methods

**Lines 1264-1298**: Added two helper methods

```python
def _get_content_type(self) -> str:
    """Get content type from combo box (extracted to avoid duplication)."""
    content_type_map = {
        "Transcript (Own)": "transcript_own",
        "Transcript (Third-party)": "transcript_third_party",
        "Document (PDF/eBook)": "document_pdf",
        "Document (White Paper)": "document_whitepaper",
    }
    return content_type_map.get(
        self.content_type_combo.currentText(), "transcript_own"
    )

def _build_gui_settings(self, provider: str, model: str) -> dict:
    """Build GUI settings dictionary for processing (extracted to avoid duplication)."""
    return {
        "provider": provider,
        "model": model,
        "max_tokens": 10000,
        "output_dir": self.output_edit.text() or None,
        # ... all settings in one place
        "content_type": self._get_content_type(),
        # Unified Pipeline HCE settings
        "use_skim": True,
        "miner_model_override": self._get_model_override(...),
        "flagship_judge_model": self._get_model_override(...),
        "max_workers": 1,
    }
```

### Simplify Code Paths

**Local provider path** (Lines 1332-1338):
```python
# Store processing parameters for async model check
self._pending_files = files
self._pending_gui_settings = self._build_gui_settings(provider, model)

# Start async model availability check
self._start_async_model_check(model)
return  # Exit early, processing will continue after model check
```

**Non-local provider path** (Lines 1340-1342):
```python
# Non-local provider: build settings and start worker immediately
gui_settings = self._build_gui_settings(provider, model)
self._start_summarization_worker(files, gui_settings)
```

**After model check** (already using `_start_summarization_worker`):
```python
# Lines 1671-1674: Reset button text
if hasattr(self, "start_btn"):
    self.start_btn.setText(self._get_start_button_text())

# Lines 1675-1692: Create worker with all signal connections
self.summarization_worker = EnhancedSummarizationWorker(...)
# ... (this was already extracted into _start_summarization_worker)
```

## Results

### Before
- **~150 lines** in `_start_processing()` method
- **80+ lines** of duplicated code
- **3 places** where settings dict is built
- **2 places** where worker is created and connected

### After
- **~80 lines** in `_start_processing()` method
- **0 lines** of duplicated code
- **1 place** where settings dict is built (`_build_gui_settings()`)
- **1 place** where worker is created (`_start_summarization_worker()`)

### Code Reduction
- **70+ lines removed** from `_start_processing()`
- **35 lines added** for helper methods
- **Net reduction**: ~35 lines
- **Maintainability**: Significantly improved

## Benefits

1. **Single Source of Truth**: Settings built in one place
2. **Easier to Modify**: Change settings once, affects all paths
3. **Reduced Bugs**: No risk of paths diverging
4. **Better Readability**: Main method is now clear and concise
5. **Easier Testing**: Helper methods can be tested independently

## Pattern Recognition

This is the same type of redundancy as `populate_initial_models()`:
- Code added incrementally to fix bugs
- Different code paths doing the same work
- Never refactored to extract common logic

### Red Flags for This Pattern
- ❌ Same dict/mapping defined multiple times
- ❌ Nearly identical code blocks in if/else branches
- ❌ Copy-paste with minor modifications
- ❌ Comments like "Prepare settings" repeated

### Detection Strategy
```bash
# Find methods with high line count
grep -n "def " file.py | while read line; do
    # Methods > 100 lines are candidates for extraction
done

# Find duplicated dict definitions
grep -A 10 "content_type_map = {" file.py
```

## Related Refactorings

This refactoring was discovered while fixing the "button stuck" bug. The investigation revealed:

1. **Timer redundancy** (`populate_initial_models()`) - FIXED
2. **Button state bug** (missing text reset) - FIXED  
3. **Code duplication** (settings/worker creation) - **FIXED NOW**

All three issues stem from incremental development without periodic refactoring.

## Files Modified

- `src/knowledge_system/gui/tabs/summarization_tab.py`:
  - Lines 1264-1274: Added `_get_content_type()` helper
  - Lines 1276-1298: Added `_build_gui_settings()` helper
  - Lines 1332-1338: Simplified local provider path
  - Lines 1340-1342: Simplified non-local provider path
  - Removed ~70 lines of duplicated code

## Testing

### Verification Steps

1. **Local provider with installed model**:
   - Should check model availability
   - Should start processing
   - Settings should be correct

2. **Local provider with missing model**:
   - Should show download dialog
   - Should start processing after download
   - Settings should be correct

3. **Non-local provider (OpenAI/Anthropic)**:
   - Should skip model check
   - Should start processing immediately
   - Settings should be correct

4. **All paths should**:
   - Use same settings structure
   - Create worker with same signal connections
   - Handle errors consistently

## Lessons Learned

### How Duplication Accumulates

1. **Initial implementation**: Single code path
2. **Bug fix**: Add async model check for local provider
3. **Copy-paste**: Duplicate settings building for new path
4. **More features**: Add settings to both paths
5. **Result**: Divergent code paths with subtle differences

### Prevention Strategy

1. **Extract early**: As soon as code is duplicated, extract it
2. **Code review**: Flag methods > 100 lines for refactoring
3. **Periodic audits**: Search for duplicated patterns
4. **Test coverage**: Ensure all paths are tested

### Refactoring Checklist

When you see duplicated code:
- [ ] Extract common logic into helper method
- [ ] Ensure all code paths use the helper
- [ ] Test all code paths still work
- [ ] Remove old duplicated code
- [ ] Document the refactoring

## Conclusion

This refactoring eliminates a significant source of technical debt and makes the code much more maintainable. Combined with the timer redundancy fix and button state fix, the summarization tab is now cleaner and more reliable.

**Impact**:
- ✅ 70+ lines of duplication removed
- ✅ Single source of truth for settings
- ✅ Easier to add new settings
- ✅ Reduced risk of bugs from divergent paths
- ✅ Better code organization
