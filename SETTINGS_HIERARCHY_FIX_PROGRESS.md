# Settings Hierarchy Fix - Progress Report

**Date:** October 31, 2025  
**Status:** IN PROGRESS

---

## Completed Tasks ✅

### 1. Removed Obsolete Tier Threshold Spinboxes
- **File:** `summarization_tab.py`
- **Lines removed:** UI creation (929-960), loading (3063-3073), saving (3255-3269)
- **Reason:** Tiers are assigned by LLM, not numeric thresholds
- **Evidence:** `schemas/flagship_output.v1.json` - tier is enum field in LLM output

### 2. Removed Obsolete Token Budget Spinboxes  
- **File:** `summarization_tab.py`
- **Lines removed:** Entire budgets section (1224-1263)
- **Reason:** Feature never implemented in backend - no code enforces token limits
- **Evidence:** grep found ZERO references in processing code

### 3. Removed Tier Thresholds from Config
- **File:** `config.py`
- **Lines removed:** 586-591 (tier_a_threshold, tier_b_threshold fields)
- **Reason:** Not used anywhere in HCE processing pipeline

---

## In Progress 🔄

### 4. Fix Summarization Tab Provider/Model Settings Hierarchy

**Current Issue:**
```python
# Line 3022 - Hardcoded fallback
saved_provider = self.gui_settings.get_combo_selection(
    self.tab_name, "provider", "local"  # Bypasses settings.yaml
)

# Line 3032 - Hardcoded fallback  
saved_model = self.gui_settings.get_combo_selection(
    self.tab_name, "model", "qwen2.5-coder:7b-instruct"  # Bypasses settings.yaml
)
```

**Required Fix:**
1. Change fallback to empty string `""`
2. Add Summarization tab support to settings_manager.py
3. Ensure settings.yaml llm.provider and llm.model are used

---

## Remaining Tasks 📋

### 5. Fix Summarization Advanced Model Providers
- Remove hardcoded "local" from line 1068
- Remove hardcoded defaults from lines 3105-3108

### 6. Fix Process Tab Checkboxes
- Remove `setChecked(True/False)` from lines 349, 353, 357, 363
- Change fallbacks in _load_settings from True/False to None
- Add Process tab support to settings_manager.py

### 7. Fix Monitor Tab File Patterns
- Remove `setText()` from line 99
- Change fallback in _load_settings line 624
- Add Monitor tab support to settings_manager.py

### 8. Fix Monitor Tab Checkboxes
- Remove `setChecked()` from lines 112, 181, 206
- Add Monitor tab support to settings_manager.py

### 9. Add Settings.yaml Support
- Add `processing` section with checkbox defaults
- Add `file_watcher` section with monitor defaults
- Document all new settings

### 10. Update Settings Manager
- Add Summarization tab recognition
- Add Process tab recognition  
- Add Monitor tab recognition
- Map settings to config fields

### 11. Test Everything
- Fresh session file test
- Settings.yaml override test
- Session persistence test

### 12. Update Documentation
- Update MANIFEST.md
- Create comprehensive fix summary

---

## Files Modified So Far

1. ✅ `src/knowledge_system/gui/tabs/summarization_tab.py` - Removed obsolete code
2. ✅ `src/knowledge_system/config.py` - Removed tier thresholds
3. ⏳ `src/knowledge_system/gui/core/settings_manager.py` - Pending updates
4. ⏳ `src/knowledge_system/gui/tabs/process_tab.py` - Pending fixes
5. ⏳ `src/knowledge_system/gui/tabs/monitor_tab.py` - Pending fixes
6. ⏳ `config/settings.example.yaml` - Pending additions

---

## Next Steps

Continue with task 4: Fix summarization tab provider/model to properly use settings hierarchy by:
1. Removing hardcoded fallbacks
2. Adding settings_manager support
3. Testing with fresh session

**Estimated Time Remaining:** ~60 minutes

