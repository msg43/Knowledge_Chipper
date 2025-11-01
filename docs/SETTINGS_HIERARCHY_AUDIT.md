# Settings Hierarchy Audit - Multiple Sources of Truth Analysis

**Date:** October 31, 2025  
**Auditor:** AI Assistant  
**Purpose:** Identify all locations where hardcoded defaults bypass the settings hierarchy

---

## Executive Summary

### Issues Found
- ✅ **FIXED:** Transcription Tab - Model default ("large" instead of "medium")
- ⚠️ **ISSUE:** Summarization Tab - Model default hardcoded as "qwen2.5-coder:7b-instruct"
- ⚠️ **ISSUE:** Summarization Tab - Provider default hardcoded as "local"
- ⚠️ **ISSUE:** Process Tab - Checkbox defaults hardcoded (transcribe=True, summarize=True, moc=False)
- ⚠️ **ISSUE:** Monitor Tab - File patterns hardcoded as "*.mp4,*.mp3,*.wav,*.m4a,*.pdf,*.txt,*.md"
- ⚠️ **ISSUE:** Monitor Tab - Debounce delay hardcoded as 5 seconds
- ⚠️ **ISSUE:** Monitor Tab - Checkboxes hardcoded (recursive=True, auto_process=True, system2_pipeline=False)
- ⚠️ **ISSUE:** Summarization Tab - Multiple spinbox values hardcoded (thresholds, budget limits)
- ⚠️ **ISSUE:** Summarization Tab - Claim tier default hardcoded as "All"

### Recommended Priority

**HIGH PRIORITY** (User-facing defaults that should respect settings.yaml):
1. Summarization Tab - Provider/Model defaults
2. Process Tab - Checkbox defaults
3. Monitor Tab - File patterns and auto-process settings

**MEDIUM PRIORITY** (Reasonable defaults, but should still use hierarchy):
4. Monitor Tab - Debounce delay
5. Summarization Tab - Tier thresholds

**LOW PRIORITY** (UI state, not configuration):
6. Summarization Tab - Budget limits (advanced feature, collapsed by default)
7. Summarization Tab - Claim tier filter (UI filter, not processing config)

---

## Detailed Analysis

### 1. Transcription Tab ✅ FIXED

**Status:** RESOLVED (October 31, 2025)

**Before:**
```python
# Line 2136
self.model_combo.setCurrentText("base")  # Hardcoded

# Line 3950
saved_model = self.gui_settings.get_combo_selection(
    self.tab_name, "model", "medium"  # Hardcoded fallback
)
```

**After:**
```python
# Line 2136
# Don't set a hardcoded default - let _load_settings() handle it

# Line 3953
saved_model = self.gui_settings.get_combo_selection(
    self.tab_name, "model", ""  # Let settings manager handle hierarchy
)
```

**Settings Manager Fixed:**
```python
# Line 132
if tab_name in ("Transcription", "Local Transcription", "Audio Transcription"):
    if combo_name == "model":
        return self.system_settings.transcription.whisper_model
```

---

### 2. Summarization Tab ⚠️ NEEDS FIX

#### Issue 2A: Provider Default
**Location:** `summarization_tab.py:3022`

```python
# CURRENT (WRONG):
saved_provider = self.gui_settings.get_combo_selection(
    self.tab_name, "provider", "local"  # Hardcoded fallback
)
```

**Problem:** Bypasses `settings.yaml` → `llm.provider`

**Recommended Fix:**
```python
# CORRECT:
saved_provider = self.gui_settings.get_combo_selection(
    self.tab_name, "provider", ""  # Let settings manager handle it
)
```

**Settings Manager Addition Needed:**
```python
# In settings_manager.py get_combo_selection():
if tab_name == "Summarization":
    if combo_name == "provider":
        return self.system_settings.llm.provider
    elif combo_name == "model":
        if hasattr(self.system_settings.llm, "local_model"):
            return self.system_settings.llm.local_model
        return self.system_settings.llm.model
```

#### Issue 2B: Model Default
**Location:** `summarization_tab.py:3032`

```python
# CURRENT (WRONG):
saved_model = self.gui_settings.get_combo_selection(
    self.tab_name, "model", "qwen2.5-coder:7b-instruct"  # Hardcoded fallback
)
```

**Problem:** 
- Bypasses `settings.yaml` → `llm.model` or `llm.local_model`
- Hardcoded model may not even be installed

**Recommended Fix:**
```python
# CORRECT:
saved_model = self.gui_settings.get_combo_selection(
    self.tab_name, "model", ""  # Let settings manager handle it
)
```

#### Issue 2C: Advanced Model Providers
**Location:** `summarization_tab.py:1068`

```python
# CURRENT (WRONG):
provider_combo.setCurrentText("local")  # Default to local (MVP LLM)
```

**Problem:** Should not set in UI initialization

**Recommended Fix:**
```python
# CORRECT:
# Don't set default - let _load_settings() handle it
provider_combo.addItems(["", "openai", "anthropic", "local"])
```

#### Issue 2D: Threshold Spinboxes
**Locations:**
- `summarization_tab.py:942` - Tier A threshold: `setValue(85)`
- `summarization_tab.py:958` - Tier B threshold: `setValue(65)`

**Problem:** Hardcoded in UI initialization, should load from settings or session

**Recommended Fix:**
Add to settings.yaml:
```yaml
summarization:
  tier_a_threshold: 85
  tier_b_threshold: 65
```

Add to settings_manager.py:
```python
if tab_name == "Summarization":
    if spinbox_name == "tier_a_threshold":
        return self.system_settings.summarization.tier_a_threshold
    elif spinbox_name == "tier_b_threshold":
        return self.system_settings.summarization.tier_b_threshold
```

#### Issue 2E: Claim Tier Filter
**Location:** `summarization_tab.py:909`

```python
# CURRENT:
self.claim_tier_combo.setCurrentText("All")
```

**Analysis:** This is a UI filter, not a configuration setting. Less critical, but should still load from session for user convenience.

**Recommended Fix:**
```python
# Don't set default - let _load_settings() handle it
self.claim_tier_combo.addItems(["All", "Tier A", "Tier B", "Tier C"])
```

---

### 3. Process Tab ⚠️ NEEDS FIX

#### Issue 3A: Checkbox Defaults
**Locations:**
- `process_tab.py:349` - Transcribe: `setChecked(True)`
- `process_tab.py:353` - Summarize: `setChecked(True)`
- `process_tab.py:357` - MOC: `setChecked(False)`
- `process_tab.py:363` - MOC Pages: `setChecked(False)`

**Current _load_settings:**
```python
# Line 659 - Still uses hardcoded fallbacks
self.transcribe_checkbox.setChecked(
    self.gui_settings.get_checkbox_state(self.tab_name, "transcribe", True)  # Hardcoded
)
self.summarize_checkbox.setChecked(
    self.gui_settings.get_checkbox_state(self.tab_name, "summarize", True)  # Hardcoded
)
```

**Problem:**
- Sets defaults in both UI initialization AND _load_settings
- Bypasses potential settings.yaml configuration

**Recommended Fix:**

1. Remove UI initialization defaults:
```python
# CORRECT:
self.transcribe_checkbox = QCheckBox("Transcribe Audio/Video")
# Don't call setChecked() - let _load_settings() handle it
```

2. Add to settings.yaml:
```yaml
processing:
  default_transcribe: true
  default_summarize: true
  default_generate_moc: false
  default_write_moc_pages: false
```

3. Update settings_manager.py:
```python
if tab_name == "Process":
    if checkbox_name == "transcribe":
        return self.system_settings.processing.default_transcribe
    elif checkbox_name == "summarize":
        return self.system_settings.processing.default_summarize
    # etc.
```

4. Update _load_settings to use empty defaults:
```python
self.transcribe_checkbox.setChecked(
    self.gui_settings.get_checkbox_state(self.tab_name, "transcribe", None)
)
```

---

### 4. Monitor Tab ⚠️ NEEDS FIX

#### Issue 4A: File Patterns
**Location:** `monitor_tab.py:99`

```python
# CURRENT (WRONG):
self.file_patterns.setText("*.mp4,*.mp3,*.wav,*.m4a,*.pdf,*.txt,*.md")
```

**Current _load_settings:**
```python
# Line 624 - Hardcoded fallback
saved_patterns = self.gui_settings.get_line_edit_text(
    self.tab_name,
    "file_patterns",
    "*.mp4,*.mp3,*.wav,*.m4a,*.pdf,*.txt,*.md",  # Hardcoded
)
```

**Problem:** Sets in both places, bypasses settings.yaml

**Recommended Fix:**

1. Remove UI initialization:
```python
# CORRECT:
self.file_patterns = QLineEdit()
# Don't call setText() - let _load_settings() handle it
```

2. Add to settings.yaml:
```yaml
file_watcher:
  default_file_patterns: "*.mp4,*.mp3,*.wav,*.m4a,*.pdf,*.txt,*.md"
  default_debounce_delay: 5
  default_recursive: true
  default_auto_process: true
  default_system2_pipeline: false
```

3. Update settings_manager.py:
```python
if tab_name == "Monitor":
    if line_edit_name == "file_patterns":
        return self.system_settings.file_watcher.default_file_patterns
```

#### Issue 4B: Debounce Delay
**Location:** `monitor_tab.py:127`

```python
# CURRENT (WRONG):
self.debounce_delay.setValue(5)
```

**Problem:** Should load from settings/session

**Recommended Fix:** Same pattern as file_patterns - remove UI init, add to settings.yaml

#### Issue 4C: Checkbox Defaults
**Locations:**
- `monitor_tab.py:112` - Recursive: `setChecked(True)`
- `monitor_tab.py:181` - Auto-process: `setChecked(True)`
- `monitor_tab.py:206` - System2 pipeline: `setChecked(False)`

**Problem:** Should load from settings/session

**Recommended Fix:** Same pattern as Process Tab checkboxes

---

## Implementation Plan

### Phase 1: Critical Fixes (User-Facing Defaults)

1. **Summarization Tab Provider/Model**
   - Files: `summarization_tab.py`, `settings_manager.py`
   - Add settings.yaml support for summarization defaults
   - Remove hardcoded "local" and "qwen2.5-coder:7b-instruct"
   - Estimated effort: 30 minutes

2. **Process Tab Checkboxes**
   - Files: `process_tab.py`, `settings_manager.py`, `settings.example.yaml`
   - Add `processing` section to settings.yaml
   - Remove UI initialization defaults
   - Estimated effort: 20 minutes

3. **Monitor Tab Settings**
   - Files: `monitor_tab.py`, `settings_manager.py`, `settings.example.yaml`
   - Add `file_watcher` section to settings.yaml
   - Remove UI initialization defaults
   - Estimated effort: 25 minutes

### Phase 2: Configuration Improvements

4. **Summarization Tier Thresholds**
   - Add to settings.yaml
   - Update settings_manager.py
   - Estimated effort: 15 minutes

### Phase 3: Nice-to-Have

5. **UI State Persistence**
   - Claim tier filter (session only, not config)
   - Budget limits (session only, not config)
   - Estimated effort: 10 minutes

### Total Estimated Effort
**~100 minutes (1.5-2 hours)** for complete consistency across all tabs

---

## Testing Checklist

For each tab after fixes:

### Test 1: Fresh Install
```bash
# Remove session file
rm ~/.knowledge_system/gui_session.json

# Launch app
python -m knowledge_system.gui.main

# Expected: All defaults come from settings.yaml
```

### Test 2: Settings.yaml Override
```yaml
# Edit settings
summarization:
  provider: "openai"
  
processing:
  default_transcribe: false
```
```bash
rm ~/.knowledge_system/gui_session.json
python -m knowledge_system.gui.main
# Expected: Summarization shows "openai", Process tab transcribe unchecked
```

### Test 3: Session Persistence
```bash
# 1. Launch app
# 2. Change settings in each tab
# 3. Close app
# 4. Launch app again
# Expected: All tabs restore last-used values
```

---

## Benefits of Full Implementation

1. **Consistency** - All tabs follow same settings hierarchy
2. **Predictability** - Users know where to change defaults
3. **Configurability** - Settings.yaml controls all defaults
4. **User Preference** - Session state always respected
5. **Maintainability** - One place to change defaults
6. **Documentation** - settings.example.yaml documents all options
7. **Testing** - Easy to test different configurations
8. **Enterprise** - Organizations can ship pre-configured settings.yaml

---

## Current State vs. Ideal State

### Current State
```
settings.yaml → (sometimes respected)
    ↓
Python code hardcoded defaults → (always wins)
    ↓
Session state → (restored on top)
```

### Ideal State (After Fixes)
```
settings.yaml (system defaults)
    ↓
Session state (user preferences)
    ↓
UI widgets (no defaults set)
```

---

## Related Documentation

- `docs/SETTINGS_SINGLE_SOURCE_OF_TRUTH.md` - Architecture guide
- `SETTINGS_SINGLE_SOURCE_OF_TRUTH_FIX.md` - Transcription tab fix summary
- `src/knowledge_system/config.py` - Configuration schema
- `src/knowledge_system/gui/core/settings_manager.py` - Settings hierarchy implementation

---

## Status

- ✅ **Transcription Tab** - Fixed (October 31, 2025)
- ⏳ **Other Tabs** - Documented, awaiting implementation
- 📋 **Implementation Plan** - Ready for execution

---

## Recommendations

1. **Immediate Action:** Fix Summarization Tab provider/model (highest user impact)
2. **Short Term:** Fix all Phase 1 items (critical user-facing defaults)
3. **Medium Term:** Complete Phase 2 (configuration improvements)
4. **Long Term:** Establish coding standard requiring all defaults go through settings manager
5. **Process:** Add linter or pre-commit hook to detect hardcoded `setCurrentText()`, `setChecked()`, `setValue()` in `__init__()` methods
