# GUI Testing Findings - CRITICAL UPDATE
**Date:** 2025-11-15
**Environment:** Claude Code CLI (headless, no display)

## Root Cause Identified

The segfaults are **NOT** caused by Python 3.13 + PyQt6 incompatibility.

**Actual Cause:** Running Qt GUI applications in a **headless CLI environment**

### Evidence

```
PasteBoard: Error creating pasteboard: com.apple.pasteboard.clipboard [-4960]
Connection Invalid error for service com.apple.hiservices-xpcservice
no screens available, assuming 24-bit color
Exit code 139 (SIGSEGV - Segmentation Fault)
```

Qt applications **require a display** to function. Running them via Claude Code's CLI without `DISPLAY` set or Xvfb causes crashes.

## What This Means

✅ **The app is likely FINE in production** (when run with a display)
❌ **GUI tests cannot run in this environment** without special setup

## Solutions

### Option 1: Test with Virtual Display (Xvfb)
```bash
# Install Xvfb (X Virtual Framebuffer)
brew install xquartz

# Run tests with virtual display
xvfb-run -a pytest tests/gui/ -v
```

### Option 2: Use pytest-qt with offscreen rendering
```python
# In conftest.py
@pytest.fixture(scope="session")
def qapp(qapp):
    """Configure Qt for headless testing."""
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    return qapp
```

### Option 3: Mark GUI tests as manual
```python
# tests/gui/test_all_tabs_smoke.py
@pytest.mark.manual
@pytest.mark.skip(reason="Requires display - run manually with `python tests/gui/test_all_tabs_smoke.py`")
class TestAllTabsSmoke:
    ...
```

### Option 4: Verify app works manually (RECOMMENDED FIRST STEP)
```bash
# Just run the app normally (with your display)
.venv/bin/python -m knowledge_system.gui.main_window_pyqt6
```

**If it launches successfully, there is NO bug - only a test environment issue.**

## Recommended Action Plan

1. **USER ACTION NEEDED:** Run the app manually to verify it works
   ```bash
   .venv/bin/python -m knowledge_system.gui.main_window_pyqt6
   ```

2. **If app works:** Implement Option 2 or 3 (offscreen testing or mark as manual)

3. **If app still crashes:** Then investigate Python 3.13/PyQt6 compatibility

## Updated Assessment

### Previous Incorrect Analysis ❌
- ~~Blamed Python 3.13.5 + PyQt6 6.9.1 incompatibility~~
- ~~Suggested downgrading Python~~
- ~~Created extensive PyQt6 bug investigation~~

### Correct Analysis ✅
- **Issue:** Running GUI in headless CLI environment
- **Solution:** Either setup virtual display OR verify app works in normal (display) environment
- **Impact:** Test infrastructure issue, not production bug

## Files Fixed

1. ✅ `src/knowledge_system/utils/preflight.py` - Now finds FFmpeg in Homebrew locations
2. ✅ `tests/test_preflight_checks.py` - Tests preflight without bypassing

## Next Steps

**IMMEDIATE:** User needs to manually test the app with a display to confirm it works

**IF APP WORKS:** Choose one of these approaches:
- Setup `QT_QPA_PLATFORM=offscreen` for headless testing
- Mark GUI tests as `@pytest.mark.manual`
- Setup CI with Xvfb for GUI testing

**IF APP CRASHES:** Then investigate actual GUI bugs

---

**Status:** BLOCKED - Waiting for user to verify app works with display
