# Flagship Evaluator Model Default Fix

## Issue
Upon launch, the "Flagship Evaluator Model" dropdown in the Summarization tab was appearing EMPTY, even though there was a default model configured in `settings.yaml`.

## Root Cause Analysis

### The Problem
The issue was caused by **two separate bugs** that compounded each other:

#### Bug 1: Model Name Mismatch (Fixed in earlier iteration)
A mismatch between stored model names and displayed model names for locally installed Ollama models:

1. **Storage Format**: Settings are saved/loaded as `"qwen2.5:7b-instruct"` (clean model name)
2. **Display Format**: GUI dropdowns show installed models as `"qwen2.5:7b-instruct (Installed)"` (with suffix)
3. **Match Failure**: When loading settings, `findText("qwen2.5:7b-instruct")` failed to find `"qwen2.5:7b-instruct (Installed)"` in the dropdown

#### Bug 2: Empty Provider Not Handled (Fixed in this iteration)
When no provider was saved in session state (e.g., first launch), the code failed to populate models:

1. **Empty Provider**: On first launch, `get_combo_selection()` returns `""` (empty string)
2. **Failed Check**: Code checked `if saved_provider:` which is False for empty strings
3. **No Population**: `_update_advanced_model_combo()` was never called, leaving model combo empty
4. **Root Issue**: Code didn't default to "local" provider when no provider was saved

### Why This Happened
The Ollama manager (`src/knowledge_system/utils/ollama_manager.py:370`) appends `" (Installed)"` to locally installed model names to distinguish them from available-but-not-installed models:

```python
installed_model = ModelInfo(
    name=f"{model.name} (Installed)",  # <-- Adds suffix
    ...
)
```

This is useful for the UI to show which models are ready to use vs. which need to be downloaded. However, the settings persistence layer was storing the full display name (with suffix) instead of the canonical model name.

Additionally, there were **three separate code paths** that needed fixing:
1. **`_load_settings()`** - Loading saved model selections from session state
2. **`_update_advanced_model_combo()`** - Setting default model when populating combo
3. **`populate_initial_models()`** - Setting default model on first UI initialization

Each of these code paths was trying to find models by their canonical name (without suffix) but the combo boxes contained display names (with suffix).

## Solution Implemented

### Three-Part Fix (Plus Redundancy Elimination)

#### 1. Default to Local Provider When Empty
When no provider is saved in session state, default to "local" (MVP LLM approach):

**File**: `src/knowledge_system/gui/tabs/summarization_tab.py`

**Lines 3060-3063** (in `_load_settings()` method):
```python
# If no saved provider, default to "local" (MVP LLM approach)
if not saved_provider:
    saved_provider = "local"
    logger.debug(f"  No saved provider, defaulting to 'local'")
```

This ensures that `_update_advanced_model_combo()` is always called with a valid provider, even on first launch.

#### 2. Loading Settings - Fuzzy Match
When loading saved model selections, try both exact match and match with `" (Installed)"` suffix:

**File**: `src/knowledge_system/gui/tabs/summarization_tab.py`

**Lines 3028-3034** (main model combo):
```python
# Try exact match first
index = self.model_combo.findText(saved_model)
# If not found, try with " (Installed)" suffix for local models
if index < 0 and saved_provider == "local":
    index = self.model_combo.findText(f"{saved_model} (Installed)")
if index >= 0:
    self.model_combo.setCurrentIndex(index)
```

**Lines 3128-3134** (advanced model combos):
```python
# Try exact match first
index = model_combo.findText(saved_model)
# If not found, try with " (Installed)" suffix for local models
if index < 0 and saved_provider == "local":
    index = model_combo.findText(f"{saved_model} (Installed)")
if index >= 0:
    model_combo.setCurrentIndex(index)
```

#### 2. Model Combo Population - Fuzzy Default Selection
When populating model combos with available models, use fuzzy matching to set default model:

**Lines 2323-2335** (`_update_advanced_model_combo` method):
```python
# Try to restore previous selection if it's still valid
if current_text and current_text in all_items:
    model_combo.setCurrentText(current_text)
elif provider == "local" and not current_text:
    # For local provider with no selection, default to MVP LLM
    mvp_model = "qwen2.5:7b-instruct"
    # Try exact match first, then with " (Installed)" suffix
    if mvp_model in all_items:
        model_combo.setCurrentText(mvp_model)
    elif f"{mvp_model} (Installed)" in all_items:
        model_combo.setCurrentText(f"{mvp_model} (Installed)")
    elif len(all_items) > 1:  # Has models besides empty option
        model_combo.setCurrentIndex(1)  # Select first real model
```

#### 4. Redundancy Elimination
The `populate_initial_models()` function was completely removed as it was redundant:

**Why it was redundant:**
- Provider combos default to empty string (first item in list)
- `populate_initial_models()` only ran if provider was "local"
- Since provider was never "local" at T+100ms, this function did nothing
- By the time provider is set to "local" (in `_load_settings()` at T+200ms), model population happens there

**Simplified architecture:**
- ✅ `_update_advanced_model_combo()` - Populates models and sets default (handles fuzzy matching)
- ✅ `_load_settings()` - Loads saved provider/model, calls above
- ✅ `on_provider_changed()` - User changes provider, calls above
- ❌ `populate_initial_models()` - **DELETED** (did nothing useful)

#### 5. Saving Settings - Clean Storage
When saving model selections, strip the `" (Installed)"` suffix to keep stored values clean:

**Lines 3210-3216** (main model combo):
```python
model_text = safe_get_text(self.model_combo, "model_combo")
if model_text is not None:
    # Remove " (Installed)" suffix if present to keep stored value clean
    clean_model_text = model_text.replace(" (Installed)", "")
    self.gui_settings.set_combo_selection(
        self.tab_name, "model", clean_model_text
    )
```

**Lines 3285-3292** (advanced model combos):
```python
# Save model selection (strip " (Installed)" suffix to keep stored value clean)
stage_model_text = safe_get_text(model_combo, f"{stage_name}_model")
if stage_model_text is not None:
    # Remove " (Installed)" suffix if present
    clean_model_text = stage_model_text.replace(" (Installed)", "")
    self.gui_settings.set_combo_selection(
        self.tab_name, f"{stage_name}_model", clean_model_text
    )
```

## Benefits

1. **Backward Compatibility**: Existing saved settings (with or without suffix) will load correctly
2. **Forward Compatibility**: New settings are saved in clean format
3. **Consistent Storage**: Model names stored in session state match the canonical format from `settings.yaml`
4. **User-Friendly Display**: Users still see the helpful `" (Installed)"` indicator in dropdowns

## Testing Recommendations

### Test Case 1: Fresh Install
1. Launch app with no prior session state
2. Navigate to Summarization tab
3. Verify "Flagship Evaluator Model" shows `"qwen2.5:7b-instruct (Installed)"` (or appropriate default)

### Test Case 2: Existing Session
1. Launch app with existing session state containing saved model
2. Navigate to Summarization tab  
3. Verify saved model is correctly selected in dropdown

### Test Case 3: Model Selection Persistence
1. Select a different model in "Flagship Evaluator Model" dropdown
2. Restart the application
3. Verify the selected model is restored on launch

### Test Case 4: Cross-Provider Compatibility
1. Select OpenAI or Anthropic provider (no " (Installed)" suffix)
2. Select a model
3. Restart the application
4. Verify model is correctly restored

## Files Modified

- `src/knowledge_system/gui/tabs/summarization_tab.py`:
  - **Lines 1194-1198**: **DELETED** `populate_initial_models()` function (redundant)
  - **Lines 2323-2335**: Added fuzzy match in `_update_advanced_model_combo()` for default model selection
  - **Lines 3028-3034**: Added fuzzy match for main model combo loading in `_load_settings()`
  - **Lines 3060-3063**: **NEW FIX** - Default to "local" provider when no provider is saved
  - **Lines 3128-3134**: Added fuzzy match for advanced model combos loading in `_load_settings()`
  - **Lines 3210-3216**: Added suffix stripping for main model combo saving in `_save_settings()`
  - **Lines 3285-3292**: Added suffix stripping for advanced model combos saving in `_save_settings()`

### Code Reduction
- **Removed**: 40+ lines of redundant code in `populate_initial_models()`
- **Result**: Cleaner, more maintainable architecture with only 2 code paths instead of 3

## Related Components

- `src/knowledge_system/utils/ollama_manager.py`: Adds `" (Installed)"` suffix to model names
- `src/knowledge_system/gui/core/settings_manager.py`: Handles settings persistence
- `config/settings.yaml`: Defines default LLM provider and model

## Architectural Improvement

### Before: Three Redundant Code Paths
```
T+0ms:   _setup_ui() - Initialize combos with empty values
T+100ms: populate_initial_models() - Does nothing (provider is empty)
T+200ms: _load_settings() - Sets provider and populates models
User:    on_provider_changed() - Populates models when user changes provider
```

**Problem**: `populate_initial_models()` was dead code that never executed its logic because:
1. Provider combos default to `""` (empty string)
2. Function only runs if provider is `"local"`
3. Provider is never `"local"` at T+100ms
4. By T+200ms when provider is set, `_load_settings()` handles everything

### After: Two Clean Code Paths
```
T+0ms:   _setup_ui() - Initialize combos with empty values
T+200ms: _load_settings() - Sets provider, populates models, sets default
User:    on_provider_changed() - Populates models when user changes provider
```

**Benefits**:
- ✅ 40+ lines of dead code removed
- ✅ Clearer initialization sequence
- ✅ Easier to debug and maintain
- ✅ No duplicate fuzzy-matching logic
- ✅ Single source of truth for model population

## Notes

- This fix applies to **all advanced model dropdowns** in the Summarization tab:
  - Unified Miner Model
  - Flagship Evaluator Model
  - (Any future per-stage model selectors)

- The Transcription tab does not have this issue because Whisper models don't use the `" (Installed)"` suffix pattern

- The fix is defensive: it handles both old session states (with suffix) and new ones (without suffix)
