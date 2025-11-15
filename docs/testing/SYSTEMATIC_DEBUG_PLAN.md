# Systematic Debug Plan - Test Suite Completion
**Generated:** 2025-11-15
**Current Status:** 99% unit/integration passing (202/204)

This document provides a prioritized, systematic plan to achieve 100% test coverage and ensure GUI functionality is fully tested.

---

## Priority 1: Critical GUI Testing (IMMEDIATE)

### Task 1.1: Run GUI Smoke Tests
**Estimated Time:** 10 minutes
**Files:** `tests/gui/test_all_tabs_smoke.py`, `tests/gui/test_widget_initialization.py`

**Command:**
```bash
PATH="/opt/homebrew/bin:$PATH" KNOWLEDGE_CHIPPER_TESTING_MODE=1 .venv/bin/python -m pytest tests/gui/ -v --tb=short
```

**Expected Results:**
- All tabs initialize without errors
- Basic widget creation succeeds
- No runtime errors during GUI startup

**If Failures Occur:**
- [ ] Document each failure with screenshot/error message
- [ ] Categorize by tab (Download, Transcribe, Review, Queue, etc.)
- [ ] Create focused todo items for each failing tab

---

### Task 1.2: Test Queue Tab Specifically
**Estimated Time:** 5 minutes
**File:** `tests/gui/test_queue_tab.py`
**Priority:** CRITICAL (primary user-facing feature)

**Command:**
```bash
PATH="/opt/homebrew/bin:$PATH" KNOWLEDGE_CHIPPER_TESTING_MODE=1 .venv/bin/python -m pytest tests/gui/test_queue_tab.py -v
```

**Why Critical:**
- Queue Tab displays real-time pipeline progress
- Just fixed `test_get_source_timeline` (unit test for this feature)
- Need to verify GUI integration works

**Success Criteria:**
- [ ] Queue Tab initializes
- [ ] Source timeline displays correctly
- [ ] Stage status updates work
- [ ] Filters function properly

---

### Task 1.3: Test User Workflows
**Estimated Time:** 15 minutes
**Files:** `tests/gui/test_user_workflows.py`, `tests/gui/test_simple_workflows.py`

**Command:**
```bash
PATH="/opt/homebrew/bin:$PATH" KNOWLEDGE_CHIPPER_TESTING_MODE=1 .venv/bin/python -m pytest tests/gui/test_simple_workflows.py tests/gui/test_user_workflows.py -v
```

**Coverage:**
- Download → Transcribe workflow
- Review Tab interactions
- Settings persistence
- Tab switching

**Success Criteria:**
- [ ] Download tab accepts YouTube URLs
- [ ] Transcribe tab processes audio files
- [ ] Review tab displays results
- [ ] Settings save/load correctly

---

## Priority 2: Fix Non-Critical Test Issues (HIGH)

### Task 2.1: Mark Interactive Test as Manual
**Estimated Time:** 2 minutes
**File:** `tests/test_model_notifications.py`

**Changes Needed:**
```python
import pytest

@pytest.mark.manual
@pytest.mark.skip(reason="Interactive script - requires manual execution")
def test_missing_models():
    """Manual test for model availability notifications."""
    # existing code...
```

**Update pytest.ini:**
```ini
[pytest]
markers =
    integration: marks tests as integration tests (requiring external services)
    manual: marks tests requiring manual/interactive execution
    slow: marks tests as slow (>1 second)
```

---

### Task 2.2: Mark Ollama Test as Integration
**Estimated Time:** 2 minutes
**File:** `tests/test_ollama_structured.py`

**Changes Needed:**
```python
import pytest

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv('OLLAMA_HOST'),
    reason="Requires Ollama server running (set OLLAMA_HOST env var)"
)
def test_schema():
    # existing code...
```

**Documentation:**
Add to test file docstring:
```python
"""
Integration tests for Ollama structured outputs.

Requirements:
- Ollama server running locally (default: http://localhost:11434)
- Qwen2.5 model installed: `ollama pull qwen2.5`

To run:
    export OLLAMA_HOST=http://localhost:11434
    pytest tests/test_ollama_structured.py -v
"""
```

---

## Priority 3: Comprehensive Test Improvements (MEDIUM)

### Task 3.1: Fix YouTube Download Timeout
**Estimated Time:** 30 minutes
**File:** `tests/comprehensive/test_real_gui_complete.py`
**Issue:** Test hangs for >30 minutes on YouTube download

**Investigation Steps:**
1. [ ] Review test timeout settings (currently 600s)
2. [ ] Check if yt-dlp is rate-limited
3. [ ] Verify YouTube URL is still valid
4. [ ] Consider mocking YouTube downloads for speed

**Options:**
- **Option A:** Increase timeout to 900s (15 min)
- **Option B:** Mock YouTube downloads with local test files
- **Option C:** Skip YouTube tests in automated runs, manual only

**Recommended Approach:** Option B (mock downloads)

---

### Task 3.2: Create GUI Test README
**Estimated Time:** 15 minutes
**File:** `tests/gui/README.md`

**Content Needed:**
```markdown
# GUI Tests

## Test Categories

### Smoke Tests (`test_all_tabs_smoke.py`)
Fast initialization tests for all tabs. Run these first.

### Widget Tests (`test_widget_initialization.py`)
Tests individual widget creation and configuration.

### Workflow Tests (`test_simple_workflows.py`, `test_user_workflows.py`)
End-to-end user workflows. May be slower due to actual processing.

### Extended Tests (`test_extended_workflows.py`)
Advanced workflows with multiple steps. Optional for regular runs.

## Running Tests

### Quick smoke test:
```bash
make test-gui  # If target exists
# OR
pytest tests/gui/test_all_tabs_smoke.py -v
```

### Full GUI suite:
```bash
pytest tests/gui/ -v
```

### Specific tab:
```bash
pytest tests/gui/test_queue_tab.py -v
```

## Troubleshooting

- **Qt platform plugin errors:** Make sure DISPLAY is set (Linux) or run in GUI environment
- **Timeout errors:** Increase timeout in pytest.ini or individual tests
- **Import errors:** Ensure PyQt6 extras installed: `pip install -e ".[gui]"`
```

---

## Priority 4: Test Architecture Documentation (LOW)

### Task 4.1: Create Comprehensive Test README
**Estimated Time:** 30 minutes
**File:** `tests/README.md`

**Sections Needed:**
1. Test organization (unit, integration, GUI, comprehensive)
2. Running different test suites
3. Test markers and their meanings
4. External dependencies (Ollama, FFmpeg, etc.)
5. Troubleshooting common issues
6. Contributing guidelines for new tests

---

### Task 4.2: Update pytest.ini with All Markers
**Estimated Time:** 10 minutes
**File:** `pytest.ini`

**Current markers to add:**
```ini
markers =
    integration: Tests requiring external services (Ollama, network)
    manual: Tests requiring manual/interactive execution
    slow: Tests taking >1 second
    skip_youtube: Skip YouTube download tests
    skip_network: Skip all network-dependent tests
    gui: GUI tests requiring display
```

---

## Priority 5: Code Quality Improvements (OPTIONAL)

### Task 5.1: Fix datetime.utcnow() Deprecation Warnings
**Estimated Time:** 2 hours
**Files:** Multiple files across codebase (400+ warnings)
**Impact:** Future Python compatibility

**Migration Pattern:**
```python
# OLD (deprecated)
from datetime import datetime
timestamp = datetime.utcnow()

# NEW (recommended)
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc)
```

**Files to Update:**
- `src/knowledge_system/core/system2_orchestrator.py`
- `src/knowledge_system/database/service.py`
- `src/knowledge_system/gui/queue_event_bus.py`
- `src/knowledge_system/services/queue_snapshot_service.py`
- `tests/fixtures/system2_fixtures.py`
- `tests/test_queue_snapshot_service.py`

**Recommendation:** Create separate PR for this cleanup.

---

### Task 5.2: Migrate to SQLAlchemy 2.0 Imports
**Estimated Time:** 30 minutes
**File:** `src/knowledge_system/database/models.py`

**Change:**
```python
# OLD
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

# NEW
from sqlalchemy.orm import declarative_base
Base = declarative_base()
```

---

## Execution Checklist

Use this checklist to track progress:

### Phase 1: Critical GUI Testing
- [ ] Task 1.1: Run GUI smoke tests
- [ ] Task 1.2: Test Queue Tab specifically
- [ ] Task 1.3: Test user workflows
- [ ] Document all GUI test results
- [ ] Create focused fixes for any GUI failures

### Phase 2: Non-Critical Fixes
- [ ] Task 2.1: Mark interactive test as manual
- [ ] Task 2.2: Mark Ollama test as integration
- [ ] Update pytest.ini with markers
- [ ] Verify test suite runs without non-critical failures

### Phase 3: Comprehensive Tests
- [ ] Task 3.1: Fix YouTube download timeout
- [ ] Task 3.2: Create GUI test README
- [ ] Run comprehensive tests successfully

### Phase 4: Documentation
- [ ] Task 4.1: Create comprehensive test README
- [ ] Task 4.2: Update pytest.ini with all markers
- [ ] Document test organization in CLAUDE.md

### Phase 5: Code Quality (Optional)
- [ ] Task 5.1: Fix datetime.utcnow() deprecations
- [ ] Task 5.2: Migrate SQLAlchemy imports
- [ ] Run test suite to verify no regressions

---

## Success Metrics

**Phase 1 Complete When:**
- ✅ All GUI smoke tests pass
- ✅ Queue Tab tests pass
- ✅ Basic user workflows complete without errors

**Phase 2 Complete When:**
- ✅ Test suite shows 0 failures (only skipped tests)
- ✅ All markers properly documented
- ✅ Interactive/integration tests appropriately marked

**Phase 3 Complete When:**
- ✅ Comprehensive tests run without timeout
- ✅ All test categories documented
- ✅ 100% test pass rate (excluding manual/integration)

**Final Goal:**
**100% automated test pass rate** with GUI tests confirming all user workflows function correctly.

---

## Quick Reference Commands

### Run specific test priority:
```bash
# Priority 1: GUI tests
pytest tests/gui/ -v

# Priority 2: Mark and skip non-automated
pytest -m "not manual and not integration" -v

# Priority 3: Comprehensive (use with caution)
pytest tests/comprehensive/ -v --timeout=900

# Full suite excluding manual/slow
pytest -m "not manual" --ignore=tests/comprehensive --ignore=tests/beta -v
```

### Check current status:
```bash
# Quick unit tests
make test-quick

# Full automated suite
make test

# Show only failures
pytest --tb=short --maxfail=1 -v
```

---

## Notes

- Each task has estimated time to help prioritize
- Tasks within priority levels can be done in parallel
- Document ALL failures/issues discovered
- Update this plan as new issues are found
- Commit fixes incrementally (don't batch everything)

---

**Last Updated:** 2025-11-15
**Current Branch:** main
**Current Commit:** ed393c2
