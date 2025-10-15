# Hardcoded Checkbox Default Values

This document lists all locations in `summarization_tab.py` where checkbox references were replaced with hardcoded default values during the checkbox removal process.

## Summary of Hardcoded Values

| Setting | Hardcoded Value | Original Widget |
|---------|----------------|-----------------|
| `max_tokens` | `10000` | `self.max_tokens_spin.value()` |
| `update_in_place` | `False` | `self.update_md_checkbox.isChecked()` |
| `create_separate_file` | `False` | `self.separate_file_checkbox.isChecked()` |
| `force_regenerate` | `False` | `self.force_regenerate_checkbox.isChecked()` |
| `export_getreceipts` | `False` | `self.export_getreceipts_checkbox.isChecked()` |
| `prompt_driven_mode` | `False` | `self.prompt_driven_mode_checkbox.isChecked()` |
| `use_skim` | `True` | `self.use_skim_checkbox.isChecked()` |
| `enable_routing` | `True` | `self.enable_routing_checkbox.isChecked()` ⚠️ NEVER CREATED |
| `routing_threshold` | `0.35` (35%) | `self.routing_threshold_spin.value()` ⚠️ NEVER CREATED |

---

## Location 1: `_start_processing()` - Local Provider Settings (Line ~1174)

**Purpose:** Store processing parameters for async model check when using local provider

```python
self._pending_gui_settings = {
    "provider": provider,
    "model": model,
    "max_tokens": 10000,  # ⚠️ HARDCODED (was: self.max_tokens_spin.value())
    "template_path": self.template_path_edit.text(),
    "output_dir": self.output_edit.text() or None,
    "update_in_place": False,  # ⚠️ HARDCODED (was: self.update_md_checkbox.isChecked())
    "create_separate_file": False,  # ⚠️ HARDCODED (was: self.separate_file_checkbox.isChecked())
    "force_regenerate": False,  # ⚠️ HARDCODED (was: self.force_regenerate_checkbox.isChecked())
    "analysis_type": "Document Summary",
    "export_getreceipts": False,  # ⚠️ HARDCODED (was: self.export_getreceipts_checkbox.isChecked())
    "profile": self.profile_combo.currentText(),
    "use_skim": True,  # ⚠️ HARDCODED (was: self.use_skim_checkbox.isChecked())
    "enable_routing": self.enable_routing_checkbox.isChecked(),
    "routing_threshold": self.routing_threshold_spin.value() / 100.0,
    "prompt_driven_mode": False,  # ⚠️ HARDCODED (was: self.prompt_driven_mode_checkbox.isChecked())
    "flagship_file_tokens": self.flagship_file_tokens_spin.value(),
    "flagship_session_tokens": self.flagship_session_tokens_spin.value(),
}
```

---

## Location 2: `_start_processing()` - Main Settings (Line ~1201)

**Purpose:** Prepare settings for summarization worker

```python
gui_settings = {
    "provider": provider,
    "model": model,
    "max_tokens": 10000,  # ⚠️ HARDCODED (was: self.max_tokens_spin.value())
    "template_path": self.template_path_edit.text(),
    "output_dir": self.output_edit.text() or None,
    "update_in_place": False,  # ⚠️ HARDCODED (was: self.update_md_checkbox.isChecked())
    "create_separate_file": False,  # ⚠️ HARDCODED (was: self.separate_file_checkbox.isChecked())
    "force_regenerate": False,  # ⚠️ HARDCODED (was: self.force_regenerate_checkbox.isChecked())
    "analysis_type": "Document Summary",
    "export_getreceipts": False,  # ⚠️ HARDCODED (was: self.export_getreceipts_checkbox.isChecked())
    "profile": self.profile_combo.currentText(),
    "use_skim": True,  # ⚠️ HARDCODED (was: self.use_skim_checkbox.isChecked())
    "miner_model_override": self._get_model_override(
        self.miner_provider, self.miner_model
    ),
    "flagship_judge_model": self._get_model_override(
        self.flagship_judge_provider, self.flagship_judge_model
    ),
}
```

---

## Location 3: `_generate_session_report()` - Configuration Section (Line ~2811)

**Purpose:** Generate session report with configuration details

```python
"configuration": {
    "profile": self.profile_combo.currentText(),
    "provider": self.provider_combo.currentText(),
    "model": self.model_combo.currentText(),
    "max_tokens": 10000,  # ⚠️ HARDCODED (was: self.max_tokens_spin.value())
    "analysis_type": "Document Summary",
    "use_skim": True,  # ⚠️ HARDCODED (was: self.use_skim_checkbox.isChecked())
    "enable_routing": self.enable_routing_checkbox.isChecked(),
    "routing_threshold": self.routing_threshold_spin.value(),
    "prompt_driven_mode": False,  # ⚠️ HARDCODED (was: self.prompt_driven_mode_checkbox.isChecked())
    "flagship_file_tokens": self.flagship_file_tokens_spin.value(),
    "flagship_session_tokens": self.flagship_session_tokens_spin.value(),
},
```

---

## Location 4: `_generate_session_report()` - Output Settings Section (Line ~2824)

**Purpose:** Generate session report with output settings

```python
"output_settings": {
    "update_in_place": False,  # ⚠️ HARDCODED (was: self.update_md_checkbox.isChecked())
    "create_separate_file": False,  # ⚠️ HARDCODED (was: self.separate_file_checkbox.isChecked())
    "output_directory": self.output_edit.text(),
    "force_regenerate": False,  # ⚠️ HARDCODED (was: self.force_regenerate_checkbox.isChecked())
},
```

---

## Related Code Sections (Not Hardcoded, But Related)

### Output Directory Logic (Line ~2833)
Simplified from conditional to simple fallback:
```python
# Before: self.output_edit.text() if self.separate_file_checkbox.isChecked() else "output/summaries"
# After:
output_dir = self.output_edit.text() or "output/summaries"
```

### Output Location Message (Line ~2319)
Simplified from conditional to simple check:
```python
# Before: Checked self.update_md_checkbox.isChecked()
# After: Just checks if output_dir has text
output_dir = self.output_edit.text()
if output_dir:
    self.append_log(f"📁 Summary files saved to: {output_dir}")
else:
    self.append_log("📁 Summary files saved next to original files")
```

---

## Implications & Recommendations

### Current Behavior
With these hardcoded values:
- ✅ Max tokens is always 10,000
- ✅ Files are never updated in-place
- ✅ No separate summary files created (unless output_dir specified)
- ✅ No force regeneration
- ✅ No GetReceipts export
- ✅ No prompt-driven mode
- ✅ Skim is always enabled

### Potential Issues
1. **max_tokens**: Should this be configurable elsewhere or is 10,000 always correct?
2. **update_in_place/create_separate_file**: With both False, where do summaries go?
3. **force_regenerate**: Users can't force regeneration of existing summaries
4. **use_skim**: Always True might not be desired for all use cases

### Next Steps
- Review if these defaults match your intended behavior
- Consider if any of these should be exposed via different UI controls
- Determine if any should be configuration file settings instead
- Check if the summarization pipeline needs updates to handle these fixed values

---

## Bug Fix: Missing Routing Widgets

### Issue Found
The application was crashing with error:
```
ERROR | Failed to save settings for Summarization tab: wrapped C/C++ object of type QComboBox has been deleted
```

### Root Cause
The code was trying to access `self.enable_routing_checkbox` and `self.routing_threshold_spin` widgets that were **never created** in the UI initialization. These widgets were referenced in:
- Line ~1187-1188: `_start_processing()` settings dictionary
- Line ~2411: Routing analytics check
- Line ~2769-2780: Profile change handler
- Line ~2813-2814: Session report configuration

### Fix Applied
- Removed all references to these non-existent widgets
- Hardcoded `enable_routing` to `True` (always enabled)
- Hardcoded `routing_threshold` to `0.35` (35%, the "Balanced" default)
- Simplified profile handler to remove routing configuration
- Added UI initialization guard in `_save_settings()` to prevent premature saves
