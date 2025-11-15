# CRITICAL GUI Testing Findings
**Date:** 2025-11-15
**Discovery:** Systematic GUI smoke test execution revealed critical segfaults

## Environment Versions

**All bleeding-edge versions may have compatibility issues:**
- **Python:** 3.13.5 (released June 2025 - very recent!)
- **PyQt6:** 6.9.1
- **Qt:** 6.9.0
- **psutil:** 7.0.0
- **Platform:** Darwin 24.6.0 (macOS)

## Test Results Summary

**Out of 13 GUI tab tests:**
- ✅ **10 PASSED** (test_transcription_tab, test_api_keys_tab, test_batch_processing_tab, test_claim_search_tab, test_cloud_uploads_tab, test_introduction_tab, test_monitor_tab, test_process_tab, test_prompts_tab, test_speaker_attribution_tab)
- ❌ **2 CRASHED** (test_summarization_tab, test_summary_cleanup_tab)
- ⚠️ **1 UNTESTED** (test_sync_status_tab - not reached due to crashes)

## Critical Crashes

### 1. SummarizationTab Crash
**Location:** `src/knowledge_system/gui/tabs/summarization_tab.py:1124`
**Operation:** `model_combo.setEditable(True)`
**Error:** Segmentation fault

### 2. SummaryCleanupTab Crash
**Location:** `src/knowledge_system/gui/tabs/summary_cleanup_tab.py:204`
**Function:** `create_text_editor`
**Error:** Segmentation fault

### 3. Background Threading Crashes
**Location:** `src/knowledge_system/core/dynamic_parallelization.py:534`
**Function:** `_monitor_resources` calling `psutil.cpu_percent()`
**Error:** Segmentation fault in multiple threads

## Root Cause Analysis

**Most Likely:** Python 3.13 compatibility issues with:
1. **PyQt6/Qt 6.9.0** - setEditable() and text editor operations
2. **psutil 7.0.0** - cpu_percent() in multi-threaded context

**Evidence:**
- 10 tabs work perfectly (Qt environment functional)
- Crashes only on specific Qt operations (setEditable, text editor)
- psutil crashes in background threads

## Impact Assessment

**Production Impact:** UNKNOWN - CRITICAL TO VERIFY
- If the GUI works in production: Test-specific environment issue
- If the GUI crashes in production: **BLOCKING ISSUE**

**Immediate Action Required:**
1. Test the application manually in production mode
2. Check if SummarizationTab and SummaryCleanupTab work
3. Verify resource monitoring doesn't crash the app

## Recommended Solutions

### Option 1: Python Version Downgrade (SAFEST)
```bash
# Downgrade to Python 3.11 or 3.12
pyenv install 3.11.9
pyenv local 3.11.9
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[gui,hce,diarization]"
```

### Option 2: Pin Older Package Versions
```toml
# pyproject.toml
[tool.poetry.dependencies]
python = "^3.11,<3.13"  # Avoid Python 3.13
PyQt6 = "~6.7.0"  # Use older stable version
psutil = "~5.9.0"  # Use stable version
```

### Option 3: Guard Problematic Operations (WORKAROUND)
```python
# In summarization_tab.py
try:
    model_combo.setEditable(True)
except RuntimeError:
    # Fallback: use non-editable combo
    logger.warning("QComboBox.setEditable() failed, using non-editable")

# In dynamic_parallelization.py
try:
    cpu_percent = psutil.cpu_percent(interval=None)
except:
    cpu_percent = 0.0  # Fallback value
```

## Immediate Next Steps

1. ✅ Document findings (this file)
2. ⏳ Mark failing tests as `@pytest.mark.skip` temporarily
3. ⏳ Test GUI manually in production
4. ⏳ Research Python 3.13 + PyQt6 compatibility
5. ⏳ Consider Python version downgrade

## Test Markers to Add

```python
# tests/gui/test_all_tabs_smoke.py

@pytest.mark.skip(reason="Segfault with Python 3.13.5 + PyQt6 6.9.1 - investigating")
def test_summarization_tab(self, qapp):
    ...

@pytest.mark.skip(reason="Segfault with Python 3.13.5 + PyQt6 6.9.1 - investigating")
def test_summary_cleanup_tab(self, qapp):
    ...
```

## Long-term Solution

**Recommendation:** Stay on Python 3.11 or 3.12 until PyQt6 + Python 3.13 compatibility is confirmed stable.

Python 3.13 was released in October 2024 and many GUI libraries are still catching up with compatibility testing.

## Files Created

- `docs/testing/GUI_TEST_SEGFAULT_REPORT.md` - Detailed crash analysis
- `docs/testing/GUI_CRITICAL_FINDINGS.md` - This summary

---

**Status:** CRITICAL - Requires immediate attention
**Owner:** Development team
**Priority:** P0 if production is affected, P1 if test-only issue
