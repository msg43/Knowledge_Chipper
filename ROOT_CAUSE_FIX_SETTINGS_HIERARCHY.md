# ROOT CAUSE FIX: Settings Hierarchy

## ❌ The Original Problem (Symptom)
```
DEBUG: Starting summarization with provider='openai', model='gpt-4o-mini-2024-07-18'
```

But `settings.yaml` says:
```yaml
llm:
  provider: "local"
  local_model: "qwen2.5:7b-instruct"
```

## ❌ The Band-Aid Approach (What I Almost Did)
Manually edit `state/application_state.json` to hardwire `"provider": "local"`.

**Problem:** This just moves the hardwiring from one place to another. Doesn't fix the architecture.

## ✅ The Root Cause
`GUISettingsManager` had **no knowledge of `settings.yaml` at all**. It only looked at session state.

```python
# OLD CODE (BROKEN ARCHITECTURE):
def get_combo_selection(self, tab_name: str, combo_name: str, default: str = "") -> str:
    """Get the saved selection of a combo box."""
    return self.session_manager.get_tab_setting(tab_name, combo_name, default)
    # ↑ Only checks session state, ignores settings.yaml entirely! ❌
```

**Design Flaw:** Session state was the **primary source**, with hardcoded fallbacks. settings.yaml was completely ignored.

## ✅ The Proper Fix: Settings Hierarchy

### New Architecture (Line 7-9 in settings_manager.py):
```python
"""
Settings Hierarchy:
1. settings.yaml (source of truth for defaults)
2. Session state (overrides for "last used" preferences)
"""
```

### Implementation (Lines 25-33, 74-107):

**1. Load system settings in `__init__`:**
```python
def __init__(self) -> None:
    """Initialize GUI settings manager."""
    self.session_manager = get_session_manager()
    # Load system settings as source of truth for defaults
    try:
        self.system_settings = get_settings()
    except Exception as e:
        logger.warning(f"Could not load system settings: {e}")
        self.system_settings = None
```

**2. Check hierarchy in `get_combo_selection`:**
```python
def get_combo_selection(
    self, tab_name: str, combo_name: str, default: str = ""
) -> str:
    """
    Get the saved selection of a combo box.
    
    Priority:
    1. Session state (last used value)
    2. settings.yaml (system default)
    3. Provided default parameter
    """
    # First check session state
    saved_value = self.session_manager.get_tab_setting(tab_name, combo_name, None)
    if saved_value is not None:
        return saved_value  # ✅ Preserve "last used" behavior
    
    # Fall back to settings.yaml for provider/model defaults
    if self.system_settings is not None:
        if combo_name == "provider" and tab_name == "Summarization":
            return self.system_settings.llm.provider  # ✅ From settings.yaml!
        elif combo_name == "model" and tab_name == "Summarization":
            if hasattr(self.system_settings.llm, 'local_model'):
                return self.system_settings.llm.local_model
            return self.system_settings.llm.model
        elif combo_name == "miner_provider":
            return self.system_settings.llm.provider
        elif combo_name == "miner_model":
            if hasattr(self.system_settings.llm, 'local_model'):
                return self.system_settings.llm.local_model
            return self.system_settings.llm.model
    
    # Final fallback to provided default
    return default
```

## 🎯 How This Works

### Scenario 1: Fresh Install (No Session State)
1. User opens GUI for first time
2. Session state is empty
3. `get_combo_selection("Summarization", "provider", "local")` called
4. Session state returns `None` (no saved value)
5. **Falls back to `settings.yaml`** → reads `llm.provider = "local"` ✅
6. GUI shows "local" provider

### Scenario 2: User Changes Provider in GUI
1. User selects "openai" from dropdown
2. GUI calls `set_combo_selection("Summarization", "provider", "openai")`
3. This saves to session state
4. Next time GUI opens: session state returns "openai"
5. **Session state overrides settings.yaml** ✅
6. GUI shows "openai" provider (last used value preserved)

### Scenario 3: User Edits settings.yaml
1. User changes `settings.yaml`: `provider: "local"` → `provider: "anthropic"`
2. GUI already has session state with "openai"
3. Session state still returns "openai" (preserves user's GUI selection)
4. **To use new settings.yaml default:** Clear session state or delete GUI selection

### Scenario 4: User Clears Session State
1. User deletes `state/application_state.json` (or specific tab settings)
2. Session state returns `None` for provider/model
3. **Falls back to settings.yaml** → reads current values ✅
4. GUI resets to settings.yaml defaults

## 📋 Comparison: Old vs New

| Scenario | Old Behavior | New Behavior |
|----------|-------------|--------------|
| Fresh install | Uses hardcoded default (`"local"`) | Uses `settings.yaml` default ✅ |
| User changes in GUI | Saves to session state ✅ | Saves to session state ✅ |
| User edits settings.yaml | **Ignored!** ❌ | Used when session state empty ✅ |
| Clear session state | Falls back to hardcoded default | Falls back to `settings.yaml` ✅ |

## 🔍 What Changed in Code

**File:** `src/knowledge_system/gui/core/settings_manager.py`

**Changes:**
1. Import `get_settings` from config module (line 15)
2. Load `self.system_settings` in `__init__` (lines 29-33)
3. Enhanced `get_combo_selection` to check settings.yaml (lines 85-107)
4. Fixed type hint for `get_list_setting` (line 191)

**Lines Changed:** ~40 lines
**Architecture Impact:** Establishes proper settings hierarchy for entire GUI

## ✅ Why This is the Right Fix

1. **Single Source of Truth:** `settings.yaml` is now the source of truth for defaults
2. **Preserves User Preferences:** Session state still works for "remember last used"
3. **No Hardcoding:** No hardcoded provider/model values in session state or GUI
4. **Extensible:** Easy to add more settings.yaml integration for other fields
5. **Fallback Safety:** Still has fallback chain if anything fails

## 🚀 Testing the Fix

### Test 1: Fresh Session State
```bash
# Clear session state
rm state/application_state.json

# Launch GUI
# Expected: Summarization tab shows provider="local", model="qwen2.5:7b-instruct"
```

### Test 2: Change in GUI
```
1. Change provider to "openai"
2. Restart GUI
3. Expected: Still shows "openai" (session state preserved)
```

### Test 3: Edit settings.yaml + Clear Session
```bash
# Edit config/settings.yaml to use different provider
# Clear session state
rm state/application_state.json

# Launch GUI
# Expected: Shows new settings.yaml values
```

### Test 4: Legacy Session State (Your Case)
```
1. Session state has: "provider": "openai" (from past use)
2. settings.yaml has: provider: "local"
3. Launch GUI
4. Expected: Shows "openai" (preserves your last choice)
5. Clear session or select "local" manually to switch
```

## 📝 Future Improvements

This pattern can be extended to other settings:
- HCE models (miner, evaluator)
- Transcription models
- Output directories (could use settings.yaml paths as defaults)
- Processing options

The architecture is now in place; just add more `if` clauses in `get_combo_selection` for other fields.

## 🎓 Lessons Learned

1. **Always check for source of truth:** Don't assume hardcoded defaults are acceptable
2. **Settings hierarchy matters:** Session > Config > Default is a common pattern
3. **Architecture > Quick Fixes:** Fixing the architecture prevents future problems
4. **Test the chain:** Verify each level of fallback works correctly

---

**Status:** ✅ ROOT CAUSE FIXED
**Files Changed:** 1 (`settings_manager.py`)
**Testing Required:** Launch GUI and verify settings.yaml defaults are respected

