# GUI Test Segfault Report
**Generated:** 2025-11-15
**Python Version:** 3.13.5
**PyQt6 Version:** (from .venv)
**Platform:** Darwin 24.6.0 (macOS)

## Executive Summary

Running GUI smoke tests revealed **critical segmentation faults** in 2 tabs and background threading issues. Out of 13 tab tests:
- **10 PASSED** ✅
- **2 CRASHED** ❌ (segfault)
- **1 NOT TESTED** (summarization, crashed first)

## Crash Details

### Crash 1: SummarizationTab (Priority: CRITICAL)

**File:** `src/knowledge_system/gui/tabs/summarization_tab.py:1124`
**Function:** `create_model_selector`
**Line:** `model_combo.setEditable(True)`
**Test:** `tests/gui/test_all_tabs_smoke.py::TestAllTabsSmoke::test_summarization_tab`

**Stack Trace:**
```
Fatal Python error: Segmentation fault

Current thread 0x00000001f012a140 (most recent call first):
  File ".../summarization_tab.py", line 1124 in create_model_selector
  File ".../summarization_tab.py", line 1158 in _setup_ui
  File ".../components/base_tab.py", line 43 in __init__
  File ".../summarization_tab.py", line 670 in __init__
  File ".../test_all_tabs_smoke.py", line 41 in test_summarization_tab
```

**Analysis:**
- Crash occurs during QComboBox initialization
- Specifically at `.setEditable(True)` call
- May be PyQt6/Python 3.13 compatibility issue
- Or Qt platform plugin issue

**Code Context:**
```python
model_combo = QComboBox()
model_combo.setEditable(True)  # ← SEGFAULT HERE
model_combo.setMinimumWidth(400)
```

---

### Crash 2: SummaryCleanupTab (Priority: HIGH)

**File:** `src/knowledge_system/gui/tabs/summary_cleanup_tab.py:204`
**Function:** `create_text_editor`
**Test:** `tests/gui/test_all_tabs_smoke.py::TestAllTabsSmoke::test_summary_cleanup_tab`

**Stack Trace:**
```
Fatal Python error: Segmentation fault

Current thread 0x00000001f012a140 (most recent call first):
  File ".../summary_cleanup_tab.py", line 204 in create_text_editor
  File ".../summary_cleanup_tab.py", line 148 in setup_ui
  File ".../summary_cleanup_tab.py", line 76 in __init__
  File ".../test_all_tabs_smoke.py", line 197 in test_summary_cleanup_tab
```

**Analysis:**
- Crash during text editor widget creation
- 10 other tabs passed before this crash
- May be similar Qt widget initialization issue

---

### Background Thread Crashes (Priority: MEDIUM)

**File:** `src/knowledge_system/core/dynamic_parallelization.py:534`
**Function:** `_monitor_resources`
**Issue:** `psutil.cpu_percent()` causing segfaults in background threads

**Stack Trace:**
```
Thread 0x0000000315dbf000 (most recent call first):
  File ".../psutil/__init__.py", line 1814 in cpu_percent
  File ".../dynamic_parallelization.py", line 534 in _monitor_resources
  File ".../threading.py", line 994 in run

Thread 0x0000000314db3000 (most recent call first):
  File ".../psutil/__init__.py", line 1814 in cpu_percent
  File ".../dynamic_parallelization.py", line 534 in _monitor_resources
  File ".../threading.py", line 994 in run
```

**Analysis:**
- Multiple threads crashing simultaneously
- psutil.cpu_percent() not thread-safe or Python 3.13 incompatible
- This may be exacerbating GUI crashes

---

## Passing Tests (10/13)

✅ **test_transcription_tab** - PASSED
✅ **test_api_keys_tab** - PASSED
✅ **test_batch_processing_tab** - PASSED
✅ **test_claim_search_tab** - PASSED
✅ **test_cloud_uploads_tab** - PASSED
✅ **test_introduction_tab** - PASSED
✅ **test_monitor_tab** - PASSED
✅ **test_process_tab** - PASSED
✅ **test_prompts_tab** - PASSED
✅ **test_speaker_attribution_tab** - PASSED

---

## Investigation Plan

### 1. Check Python 3.13 Compatibility

**PyQt6 Compatibility:**
- Verify PyQt6 version supports Python 3.13
- Check for known PyQt6 segfault issues on macOS + Python 3.13
- Consider downgrading to Python 3.11 if needed

**psutil Compatibility:**
- Check psutil version and Python 3.13 support
- Investigate thread-safety of cpu_percent() on macOS

### 2. Isolate Qt Widget Issues

**Test each operation separately:**
```python
# Test 1: Basic QComboBox creation
combo = QComboBox()

# Test 2: setEditable
combo.setEditable(True)

# Test 3: Advanced operations
combo.setMinimumWidth(400)
combo.currentTextChanged.connect(lambda: None)
```

### 3. Check Qt Platform Plugin

**Environment variables to test:**
```bash
export QT_DEBUG_PLUGINS=1
export QT_LOGGING_RULES="*.debug=true"
```

### 4. Disable Background Threading

**Test with resource monitoring disabled:**
```python
# In dynamic_parallelization.py
# Temporarily disable _monitor_resources thread
```

---

## Workarounds

### Short-term: Skip Failing Tests

```python
@pytest.mark.skip(reason="Segfault on Python 3.13 - investigating")
def test_summarization_tab(self, qapp):
    ...

@pytest.mark.skip(reason="Segfault on Python 3.13 - investigating")
def test_summary_cleanup_tab(self, qapp):
    ...
```

### Medium-term: Guard Qt Operations

```python
def create_model_selector(...):
    try:
        model_combo = QComboBox()
        if not os.getenv('KNOWLEDGE_CHIPPER_TESTING_MODE'):
            model_combo.setEditable(True)  # Skip in testing
    except Exception as e:
        logger.error(f"QComboBox initialization failed: {e}")
        # Create simpler fallback widget
```

### Long-term: Python Version Downgrade

If PyQt6/psutil are incompatible with Python 3.13:
- Downgrade to Python 3.11 or 3.12
- Update pyproject.toml: `python = "^3.11"`
- Rebuild venv

---

## Critical Questions

1. **Does the GUI work in production?**
   - If yes: This is a test-specific issue
   - If no: These are production crashes!

2. **When did Python 3.13 migration happen?**
   - Check git history for Python version bumps
   - Were GUI tests passing before?

3. **Are there CI/CD tests running?**
   - Check if GUI tests run in CI
   - What Python version does CI use?

---

## Next Steps (Prioritized)

1. **IMMEDIATE:** Check if GUI works in production (run app manually)
2. **HIGH:** Check Python/PyQt6/psutil version compatibility
3. **HIGH:** Try running tests with Python 3.11
4. **MEDIUM:** Isolate Qt widget operations
5. **MEDIUM:** Disable resource monitoring threads
6. **LOW:** Add debug logging to Qt operations

---

## Additional Context

### Environment
- Platform: Darwin 24.6.0 (macOS)
- Python: 3.13.5
- PyQt6: (version from .venv)
- psutil: (version from .venv)

### Test Command
```bash
PATH="/opt/homebrew/bin:$PATH" KNOWLEDGE_CHIPPER_TESTING_MODE=1 .venv/bin/python -m pytest tests/gui/ -v --tb=short
```

### Test Results
- 10 tabs initialized successfully
- 2 tabs crashed with segfault
- 1 tab not tested (crashed first in sequence)

This confirms **the Qt environment is functional** (10 tabs work), but **specific widget operations crash** (setEditable, text editor creation).

---

## Related Files

- `src/knowledge_system/gui/tabs/summarization_tab.py:1124`
- `src/knowledge_system/gui/tabs/summary_cleanup_tab.py:204`
- `src/knowledge_system/core/dynamic_parallelization.py:534`
- `tests/gui/test_all_tabs_smoke.py`
- `tests/gui/conftest.py`

---

**Report Generated:** 2025-11-15
**Status:** CRITICAL - Production impact unknown
**Assignee:** Immediate investigation required
