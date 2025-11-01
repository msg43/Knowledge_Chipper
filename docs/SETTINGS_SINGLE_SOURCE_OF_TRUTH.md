# Settings Single Source of Truth Architecture

## Problem Statement

Previously, the Whisper model default was scattered across multiple locations:
1. `transcription_tab.py` line 2136: Hardcoded `"base"` in UI initialization
2. `transcription_tab.py` line 3950: Hardcoded `"medium"` in `_load_settings()`
3. `settings.example.yaml` line 69: `whisper_model: "medium"`
4. `config.py` line 218: `whisper_model: str = Field(default="medium")`
5. Session file `~/.knowledge_system/gui_session.json`: Cached "large" or "base"

This led to:
- Inconsistent defaults across fresh installs vs. existing users
- Difficult maintenance (changes needed in 4-6 places)
- Confusion about which setting takes precedence
- The exact bug reported: default was "large" instead of "medium"

## Solution: Settings Hierarchy

The `GUISettingsManager` class implements a proper settings hierarchy:

### Priority Order
1. **Session State** (last used value) - Highest priority
   - Stored in `~/.knowledge_system/gui_session.json`
   - Persists user's last choice across app restarts
   
2. **settings.yaml** (system configuration)
   - Source: `config/settings.yaml` → `self.system_settings.transcription.whisper_model`
   - Provides system-wide defaults
   
3. **Fallback Default** (empty string) - Lowest priority
   - Only used if both above fail

### Implementation

```python
# In GUISettingsManager.get_combo_selection():
def get_combo_selection(self, tab_name: str, combo_name: str, default: str = "") -> str:
    # 1. Check session state first
    saved_value = self.session_manager.get_tab_setting(tab_name, combo_name, None)
    if saved_value is not None:
        return saved_value
    
    # 2. Fall back to settings.yaml
    if self.system_settings is not None:
        if tab_name in ("Transcription", "Local Transcription", "Audio Transcription"):
            if combo_name == "model":
                return self.system_settings.transcription.whisper_model
    
    # 3. Final fallback
    return default
```

## Changes Made (2025-10-31)

### 1. Fixed Tab Name Recognition
**File:** `src/knowledge_system/gui/core/settings_manager.py`

**Before:**
```python
if tab_name == "Transcription":  # Only matched exact string
```

**After:**
```python
if tab_name in ("Transcription", "Local Transcription", "Audio Transcription"):
```

**Impact:** Settings manager now properly recognizes all transcription tab variants and correctly falls back to `settings.yaml` defaults.

### 2. Removed Hardcoded Defaults in UI
**File:** `src/knowledge_system/gui/tabs/transcription_tab.py`

**Before:**
```python
self.model_combo.setCurrentText("base")  # Hardcoded default
```

**After:**
```python
# Don't set a hardcoded default - let _load_settings() handle it via settings manager
self.model_combo.addItems(get_valid_whisper_models())
```

**Impact:** UI no longer overrides the settings hierarchy with hardcoded values.

### 3. Simplified Settings Load
**File:** `src/knowledge_system/gui/tabs/transcription_tab.py` - `_load_settings()`

**Before:**
```python
saved_model = self.gui_settings.get_combo_selection(
    self.tab_name, "model", "medium"  # Hardcoded fallback
)
```

**After:**
```python
saved_model = self.gui_settings.get_combo_selection(
    self.tab_name, "model", ""  # Let settings manager handle hierarchy
)
```

**Impact:** Properly delegates to settings manager instead of bypassing it with hardcoded defaults.

### 4. Updated Session File
**File:** `~/.knowledge_system/gui_session.json`

**Changes:**
- "Audio Transcription" tab: `model: "base"` → `"medium"`
- "Local Transcription" tab: `model: "large"` → `"medium"`

**Impact:** Existing users now have correct default.

## Single Source of Truth Flow

```
User launches app
    ↓
TranscriptionTab.__init__()
    ↓
model_combo created (no default set)
    ↓
QTimer.singleShot(200ms, _load_settings)
    ↓
_load_settings() calls:
    gui_settings.get_combo_selection(tab_name="Local Transcription", combo_name="model", default="")
    ↓
GUISettingsManager.get_combo_selection():
    1. Check session_manager.get_tab_setting("Local Transcription", "model")
       → If user changed it before: return saved value ✓
       → If not: continue to step 2
    
    2. Check self.system_settings.transcription.whisper_model
       → Loaded from settings.yaml: "medium" ✓
       → Return "medium"
    
    3. Only if both above fail: return "" (empty string)
    ↓
model_combo.setCurrentText("medium")
    ↓
User sees "medium" as default ✓
```

## Verification

To verify the single source of truth is working:

### Test 1: Fresh Install
```bash
# Remove session file
rm ~/.knowledge_system/gui_session.json

# Launch app
python -m knowledge_system.gui.main

# Expected: model_combo shows "medium" (from settings.yaml)
```

### Test 2: Settings.yaml Override
```yaml
# Edit config/settings.yaml
transcription:
  whisper_model: "small"
```
```bash
# Remove session file
rm ~/.knowledge_system/gui_session.json

# Launch app
# Expected: model_combo shows "small"
```

### Test 3: Session Persistence
```bash
# Launch app, change model to "large", close app
# Launch app again
# Expected: model_combo shows "large" (session state takes precedence)
```

## Benefits

1. **Single Configuration Point:** Change `settings.yaml` to affect all fresh installs
2. **User Preferences Respected:** Session state takes priority over system defaults
3. **No Code Changes for Defaults:** Update `settings.yaml`, not Python code
4. **Consistent Behavior:** All tabs follow the same hierarchy
5. **Easy Debugging:** Clear priority order makes troubleshooting simple

## Maintenance Guidelines

### To Change System Default
1. Edit `config/settings.example.yaml` line 69: `whisper_model: "medium"`
2. Update user's `config/settings.yaml` (if it exists)
3. **DO NOT** add hardcoded defaults to Python code

### To Add New Setting
1. Add to `config.py` `TranscriptionConfig` class with proper default
2. Add to `settings.example.yaml` with documentation
3. Add handling in `GUISettingsManager.get_combo_selection()` (or appropriate method)
4. Use in tab via `self.gui_settings.get_combo_selection(tab_name, setting_name, "")`

### Common Pitfalls to Avoid
- ❌ Setting widget values in `__init__()` - bypasses settings manager
- ❌ Passing non-empty defaults to `get_combo_selection()` - bypasses settings.yaml
- ❌ Hardcoding defaults in `_load_settings()` - defeats the hierarchy
- ✅ Let `_load_settings()` + `GUISettingsManager` handle everything

## Related Files

- `src/knowledge_system/config.py` - System configuration schema
- `src/knowledge_system/gui/core/settings_manager.py` - Settings hierarchy implementation
- `src/knowledge_system/gui/core/session_manager.py` - Session state persistence
- `config/settings.example.yaml` - Template with documented defaults
- `config/settings.yaml` - User's active configuration

## Status

✅ **COMPLETE** (2025-10-31)

All Whisper model settings now follow the single source of truth architecture. No hardcoded defaults remain in the UI code.

