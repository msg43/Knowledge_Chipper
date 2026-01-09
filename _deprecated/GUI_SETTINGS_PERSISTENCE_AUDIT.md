# GUI Settings Persistence Audit

## Summary
Comprehensive audit of GUI tab settings persistence across the Knowledge System application.

## Persistence Infrastructure

### Core Components
- **`GUISettingsManager`** (`src/knowledge_system/gui/core/settings_manager.py`)
  - Provides methods for persisting all GUI component types
  - Methods: `get_output_directory()`, `set_output_directory()`, `get_checkbox_state()`, `set_checkbox_state()`, `get_combo_selection()`, `set_combo_selection()`, `get_spinbox_value()`, `set_spinbox_value()`, `get_line_edit_text()`, `set_line_edit_text()`, `get_list_setting()`, `set_list_setting()`
  
- **`SessionManager`** (`src/knowledge_system/gui/core/session_manager.py`)
  - Backend storage using JSON file
  - Location: `~/Library/Application Support/SkipThePodcast/gui_session.json`

### Settings Hierarchy
1. Session state (last used value) - highest priority
2. settings.yaml (system defaults)
3. Provided default parameter - fallback

## Tab-by-Tab Analysis

### ✅ TranscriptionTab
**Status:** FULLY PERSISTED

**Persisted Settings:**
- Output directory ✅
- Model combo ✅
- Device combo ✅
- Language combo ✅
- Format combo ✅
- Include timestamps checkbox ✅
- Enable diarization checkbox ✅
- Enable speaker assignment checkbox ✅
- Enable color coding checkbox ✅
- Overwrite existing checkbox ✅
- Use YouTube proxy checkbox ✅
- Enable cookies checkbox ✅
- Cookie files list ✅
- Min delay spinbox ✅
- Max delay spinbox ✅
- Randomization spinbox ✅
- Disable proxies with cookies checkbox ✅

**Implementation:** `_load_settings()` and `_save_settings()` methods at lines 3674 and 3868

---

### ✅ ProcessTab
**Status:** FULLY PERSISTED

**Persisted Settings:**
- Output directory ✅
- Transcribe checkbox ✅
- Summarize checkbox ✅
- Create MOC checkbox ✅
- Write MOC Obsidian pages checkbox ✅

**Implementation:** `_load_settings()` and `_save_settings()` methods at lines 650 and 621

---

### ✅ SummarizationTab
**Status:** FULLY PERSISTED

**Persisted Settings:**
- Output directory ✅
- Provider combo ✅
- Model combo ✅
- Template path ✅
- Claim tier combo ✅
- Max claims spinbox ✅
- Tier A threshold spinbox ✅
- Tier B threshold spinbox ✅
- Advanced models group (miner/flagship judge providers and models) ✅

**Implementation:** `_load_settings()` and `_save_settings()` methods at lines 2570 and 2816

---

### ✅ MonitorTab
**Status:** FULLY PERSISTED

**Persisted Settings:**
- Watch directory line edit ✅
- File patterns line edit ✅
- Recursive checkbox ✅
- Auto process checkbox ✅
- Dry run checkbox ✅
- Debounce delay spinbox ✅

**Implementation:** `_load_settings()` and `_save_settings()` methods at lines 611 and 651

---

### ✅ APIKeysTab
**Status:** FULLY PERSISTED

**Persisted Settings:**
- All API key fields (OpenAI, Anthropic, Google, Groq, etc.) ✅

**Implementation:** `_load_settings()` and `_save_settings()` methods at lines 760 and 781

---

### ✅ PromptsTab
**Status:** FULLY PERSISTED

**Persisted Settings:**
- Selected prompt template ✅

**Implementation:** `_load_settings()` and `_save_settings()` methods at lines 743 and 747

---

### ❌ BatchProcessingTab
**Status:** NOT PERSISTED

**Missing Persistence:**
- Batch name line edit ❌
- Max concurrent downloads spinbox ❌
- Max parallel mining spinbox ❌
- Max parallel evaluation spinbox ❌
- Resume checkbox ❌

**Recommendation:** Add `_load_settings()` and `_save_settings()` methods

---

### ⚠️ ClaimSearchTab
**Status:** MINIMAL PERSISTENCE NEEDED

**Analysis:** Search tab is primarily for querying, not configuration. Search text and filters are typically transient.

**Recommendation:** Consider persisting:
- Last search query (optional)
- Filter preferences (tier, claim type) (optional)

**Priority:** LOW - search state is typically ephemeral

---

### ⚠️ CloudUploadsTab
**Status:** MINIMAL PERSISTENCE NEEDED

**Analysis:** OAuth state and database selection are session-specific and shouldn't persist across app restarts.

**Recommendation:** No persistence needed - authentication state is managed separately

**Priority:** NONE

---

### ℹ️ IntroductionTab
**Status:** NO PERSISTENCE NEEDED

**Analysis:** Static informational tab with no user-configurable settings

---

### ℹ️ SpeakerAttributionTab
**Status:** SPECIAL CASE

**Analysis:** Not a BaseTab subclass, uses QWidget directly. Has its own persistence logic for speaker mappings and channel mappings stored in separate database tables.

**Recommendation:** No changes needed - uses domain-specific persistence

---

### ℹ️ SyncStatusTab
**Status:** NO PERSISTENCE NEEDED

**Analysis:** Display-only tab showing sync status, no user-configurable settings

---

### ℹ️ SummaryCleanupTab
**Status:** NO PERSISTENCE NEEDED

**Analysis:** Utility tab for cleanup operations, no persistent settings required

---

## Action Items

### High Priority
1. **BatchProcessingTab** - Add full settings persistence
   - Batch name
   - Spinbox values (max downloads, mining, evaluation)
   - Resume checkbox

### Low Priority
2. **ClaimSearchTab** - Consider adding optional persistence
   - Last search query
   - Filter preferences

### No Action Needed
- TranscriptionTab ✅
- ProcessTab ✅
- SummarizationTab ✅
- MonitorTab ✅
- APIKeysTab ✅
- PromptsTab ✅
- CloudUploadsTab (OAuth state managed separately)
- IntroductionTab (no settings)
- SpeakerAttributionTab (custom persistence)
- SyncStatusTab (display only)
- SummaryCleanupTab (utility tab)

## Implementation Pattern

All tabs that need persistence should follow this pattern:

```python
def _load_settings(self) -> None:
    """Load settings from session."""
    try:
        # Output directory
        output_dir = self.gui_settings.get_output_directory(self.tab_name, "")
        self.output_dir_line.setText(output_dir)
        
        # Checkboxes
        self.my_checkbox.setChecked(
            self.gui_settings.get_checkbox_state(self.tab_name, "my_checkbox", False)
        )
        
        # Spinboxes
        self.my_spinbox.setValue(
            self.gui_settings.get_spinbox_value(self.tab_name, "my_spinbox", 10)
        )
        
        # Combos
        saved_value = self.gui_settings.get_combo_selection(self.tab_name, "my_combo", "")
        if saved_value:
            index = self.my_combo.findText(saved_value)
            if index >= 0:
                self.my_combo.setCurrentIndex(index)
        
        logger.debug(f"Settings loaded for {self.tab_name} tab")
    except Exception as e:
        logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")

def _save_settings(self) -> None:
    """Save current settings to session."""
    try:
        # Output directory
        self.gui_settings.set_output_directory(self.tab_name, self.output_dir_line.text())
        
        # Checkboxes
        self.gui_settings.set_checkbox_state(
            self.tab_name, "my_checkbox", self.my_checkbox.isChecked()
        )
        
        # Spinboxes
        self.gui_settings.set_spinbox_value(
            self.tab_name, "my_spinbox", self.my_spinbox.value()
        )
        
        # Combos
        self.gui_settings.set_combo_selection(
            self.tab_name, "my_combo", self.my_combo.currentText()
        )
        
        logger.debug(f"Saved settings for {self.tab_name} tab")
    except Exception as e:
        logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")

def _on_setting_changed(self):
    """Called when any setting changes to automatically save."""
    self._save_settings()
```

## Notes

- All tabs inheriting from `BaseTab` have access to `self.gui_settings` (GUISettingsManager instance)
- Settings are automatically saved to `~/Library/Application Support/SkipThePodcast/gui_session.json`
- Window geometry is persisted separately via `MainWindow._save_session()`
- API keys are persisted in `settings.yaml` (not session state)
