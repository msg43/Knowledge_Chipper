# Smoke Tests - Critical User Workflow Validation

This directory contains **smoke tests** that validate critical user-facing workflows in **production mode** (without `TESTING_MODE` bypass).

## Purpose

After discovering that 99% test pass rate missed two critical production bugs:
1. App wouldn't launch (FFmpeg PATH issue)
2. App wouldn't transcribe (data structure mismatch)

We created this smoke test suite to ensure **the most critical user workflows always work**.

## Philosophy

**These tests validate PRODUCTION behavior, not mocked "testing universe" behavior.**

- ✅ Run without `TESTING_MODE=1` bypass
- ✅ Use real components (minimal mocking)
- ✅ Test end-to-end workflows
- ✅ Validate actual data structures
- ✅ Test environment-specific issues (Homebrew PATH, etc.)
- ✅ Run quickly (< 5 minutes total)

## Smoke Tests

### 1. `test_preflight_homebrew_detection.py`
**What it catches**: FFmpeg PATH issues (would have caught Bug #1)
- Tests FFmpeg detection when only in Homebrew, not PATH
- Verifies automatic PATH modification
- Tests yt-dlp detection
- **Runtime**: ~5 seconds

### 2. `test_download_service_output_structure.py`
**What it catches**: Data structure mismatches (would have caught Bug #2)
- Validates YouTubeDownloadService output structure
- Ensures `downloaded_files` key exists (not `audio_path`)
- Tests AudioProcessor input validation
- **Runtime**: ~10 seconds

### 3. `test_app_launch_production.py`
**What it catches**: App initialization failures
- Launches GUI without TESTING_MODE
- Verifies preflight checks run
- Tests window initialization
- **Runtime**: ~15 seconds

## Running Smoke Tests

```bash
# Run all smoke tests
pytest tests/smoke/ -v

# Run specific smoke test
pytest tests/smoke/test_preflight_homebrew_detection.py -v

# Run smoke tests with detailed output
pytest tests/smoke/ -vv -s
```

## Integration with Development Workflow

### Pre-Push Hook (Recommended)
Add to `.git/hooks/pre-push`:
```bash
#!/bin/bash
echo "Running smoke tests..."
pytest tests/smoke/ -q
if [ $? -ne 0 ]; then
    echo "Smoke tests failed! Push aborted."
    exit 1
fi
```

### CI/CD Integration
```yaml
# .github/workflows/ci.yml
- name: Run Smoke Tests
  run: pytest tests/smoke/ -v
  timeout-minutes: 5
```

## Design Principles

### 1. Fast Feedback
- All smoke tests complete in < 5 minutes
- Failures provide clear, actionable error messages
- Tests are independent (can run in any order)

### 2. Production Reality
- No `TESTING_MODE` bypass (except where unavoidable)
- Tests use real file I/O, real PATH detection, real data structures
- Environment-specific issues are explicitly tested (macOS Homebrew, etc.)

### 3. Critical Path Coverage
- Each test validates a user-facing workflow
- Tests focus on integration points (where components connect)
- Tests catch architecture mismatches (data structure incompatibilities)

## When to Add New Smoke Tests

Add a smoke test when:
1. A production bug is found that existing tests missed
2. A new critical user workflow is added
3. A new integration point is created
4. An environment-specific issue is discovered

## Relationship to Other Test Types

```
Unit Tests (tests/*.py)           - Test individual functions/classes
  ↓
Integration Tests (tests/integration/) - Test component interactions
  ↓
Smoke Tests (tests/smoke/)         - Test critical user workflows ⭐ YOU ARE HERE
  ↓
E2E Tests (tests/e2e/)            - Test complete user journeys
```

**Smoke tests are the MINIMUM required to have confidence in production deployment.**

## Test Markers

```python
@pytest.mark.smoke         # Marks test as smoke test
@pytest.mark.production    # Test runs in production mode (no TESTING_MODE)
```

Run only smoke tests:
```bash
pytest -m smoke -v
```

## History

- **2025-11-15**: Created smoke test suite after discovering 99% test pass rate missed:
  - FFmpeg PATH issue (app wouldn't launch)
  - Transcription data structure mismatch (app wouldn't transcribe)

**Never again.**
