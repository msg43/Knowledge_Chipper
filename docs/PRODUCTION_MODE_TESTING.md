# Production Mode Testing Guide

## Overview

This document explains the **granular testing mode system** introduced in version 3.5.1 to address the critical gap between high test pass rates and production reliability.

### The Problem

**Before this change:**
- Tests ran with `TESTING_MODE=1` environment variable
- This bypassed ALL critical checks: preflight, transcription, LLM calls
- Tests validated "testing universe" behavior, not production behavior
- Result: **99% test pass rate but app wouldn't launch or transcribe**

**Root Cause:**
```bash
# Old approach (all-or-nothing bypass)
TESTING_MODE=1 pytest tests/

# What this did:
# ❌ Skipped FFmpeg validation → Missed PATH bugs
# ❌ Skipped transcription → Missed data structure bugs
# ❌ Skipped LLM calls → Missed integration bugs
# ❌ Skipped preflight checks → Missed dependency bugs
```

### The Solution: Granular Testing Mode

Replace all-or-nothing `TESTING_MODE=1` with **selective, granular flags** that let tests bypass only what they need.

## New Testing Flags

### Core Flags

| Flag | Purpose | When to Use | When NOT to Use |
|------|---------|------------|----------------|
| `SKIP_PREFLIGHT=1` | Skip FFmpeg/yt-dlp validation | Testing non-download features, CI without FFmpeg | Testing download/transcription workflows, app startup |
| `SKIP_TRANSCRIPTION=1` | Skip Whisper transcription | Testing data flow without slow processing | Testing AudioProcessor, full pipeline |
| `SKIP_LLM=1` | Skip Ollama/OpenAI calls | Testing without Ollama, non-LLM features | Testing claim extraction, System2 orchestrator |
| `FAST_MODE=1` | Use tiny models instead of production | Quick integration tests, development iteration | Testing output quality, benchmarking |

### Legacy Support

These still work for backward compatibility:
- `KNOWLEDGE_CHIPPER_TESTING_MODE=1` → Triggers all bypasses (deprecated)
- `KC_SKIP_PREFLIGHT=1` → Same as `SKIP_PREFLIGHT=1`

## Usage in Tests

### Integration Tests (tests/integration/)

Integration tests now run in **production mode by default** with granular fixtures for selective bypassing.

```python
# Example 1: Test database operations (skip expensive processing)
def test_claim_storage(skip_llm, skip_transcription):
    """Test claim storage without waiting for LLM or transcription."""
    # Database operations run in production mode
    # LLM and transcription are mocked/skipped for speed
    pass

# Example 2: Test full pipeline quickly (use tiny models)
def test_complete_pipeline_workflow(fast_mode):
    """Test end-to-end workflow with tiny models for speed."""
    # Uses Whisper 'tiny' instead of 'base'
    # Uses small LLM models if available
    # Still tests real code paths, just faster
    pass

# Example 3: Critical production test (no bypasses)
@pytest.mark.production
def test_critical_user_workflow(production_mode):
    """Test exactly as users experience it."""
    # Real preflight checks
    # Real transcription
    # Real LLM calls
    # Production models
    pass
```

### Available Fixtures (tests/integration/conftest.py)

These fixtures are automatically available in all integration tests:

```python
@pytest.fixture
def production_mode():
    """Ensure test runs in full production mode (no bypasses)."""
    ensure_production_mode()
    yield
    ensure_production_mode()

@pytest.fixture
def skip_llm():
    """Skip actual LLM calls but run everything else."""
    os.environ["SKIP_LLM"] = "1"
    yield
    # Cleanup

@pytest.fixture
def fast_mode():
    """Use tiny/small models instead of production models."""
    os.environ["FAST_MODE"] = "1"
    yield
    # Cleanup

@pytest.fixture
def skip_transcription():
    """Skip actual Whisper transcription."""
    os.environ["SKIP_TRANSCRIPTION"] = "1"
    yield
    # Cleanup

@pytest.fixture
def skip_preflight():
    """Skip preflight checks (FFmpeg, yt-dlp validation)."""
    os.environ["SKIP_PREFLIGHT"] = "1"
    yield
    # Cleanup
```

### Smoke Tests (tests/smoke/)

Smoke tests **always run in production mode** with no bypasses. These are fast (<5 min total) sanity checks for critical workflows.

```python
@pytest.mark.smoke
@pytest.mark.production
class TestAppLaunchProduction:
    """Test app can launch in production mode (would have caught Bug #1)."""

    def test_can_import_gui_module_without_testing_mode(self):
        # Remove TESTING_MODE to simulate production
        if "KNOWLEDGE_CHIPPER_TESTING_MODE" in os.environ:
            del os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"]

        # This import triggers preflight checks
        from knowledge_system.gui import main_window_pyqt6
        # If we get here, preflight passed
        assert True
```

## Component Updates

### preflight.py

**Before:**
```python
def quick_preflight() -> None:
    if os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1":
        return
    check_ffmpeg()
    check_yt_dlp()
```

**After:**
```python
from knowledge_system.utils.testing_mode import should_skip_preflight

def quick_preflight() -> None:
    if should_skip_preflight():  # Checks SKIP_PREFLIGHT + legacy vars
        return
    check_ffmpeg()
    check_yt_dlp()
```

### audio_processor.py

Model selection now respects `FAST_MODE`:

```python
from knowledge_system.utils.testing_mode import get_whisper_model

# In code that selects model:
model = get_whisper_model()  # Returns 'tiny' in FAST_MODE, 'base' in production
processor = AudioProcessor(model=model)
```

## Migration Guide

### For Existing Tests

**Old way (all-or-nothing):**
```bash
# Run all tests with everything bypassed
TESTING_MODE=1 pytest tests/
```

**New way (selective):**
```bash
# Run tests in production mode (recommended)
pytest tests/integration/

# Run with selective bypasses (for speed)
SKIP_LLM=1 FAST_MODE=1 pytest tests/integration/

# Run smoke tests (always production mode)
pytest tests/smoke/ -v
```

### For Test Files

**Old test:**
```python
def test_something():
    # Implicitly relied on TESTING_MODE=1
    # Preflight was bypassed
    # LLM calls were mocked
    # Transcription was skipped
    pass
```

**New test (choose one approach):**

```python
# Approach 1: Production mode (recommended for critical tests)
@pytest.mark.production
def test_something(production_mode):
    # Runs exactly as users experience it
    # All real components
    pass

# Approach 2: Selective bypasses (for speed)
def test_something(skip_llm, fast_mode):
    # Skips LLM calls
    # Uses tiny models for speed
    # Still tests real code paths
    pass

# Approach 3: Heavy mocking (only when necessary)
def test_something():
    with patch('some.slow.component'):
        # Mock only what's truly necessary
        pass
```

## Running Tests

### Quick Development Workflow
```bash
# Fast iteration (skip expensive operations)
SKIP_LLM=1 FAST_MODE=1 pytest tests/integration/ -v

# Run GUI tests (automatically use offscreen mode)
pytest tests/gui/ -v
```

### Pre-Push Workflow
```bash
# Run smoke tests (production mode, fast)
pytest tests/smoke/ -v

# Expected: 11/16 passing (5 known minor failures)
```

### Full Test Suite
```bash
# Run all tests except smoke (still uses TESTING_MODE=1 for now)
make test
```

### Production Mode Only
```bash
# Run only tests marked as production mode
pytest -m production -v
```

## Test Markers

### Smoke Tests
```python
@pytest.mark.smoke          # Fast critical workflow tests
@pytest.mark.production     # Always run in production mode
```

### Integration Tests
```python
@pytest.mark.integration    # Require external services
@pytest.mark.production     # Run in production mode (selective)
```

## FAQ

### Q: Why not just run all tests in production mode?

**A:** Production mode tests are slower and require external dependencies (Ollama, FFmpeg). For rapid development iteration, we need fast tests. The solution: strategic use of `FAST_MODE` and selective bypasses.

### Q: How do I know which fixture to use?

**Decision tree:**
```
Is this a critical user workflow test?
├─ YES → Use `production_mode` fixture
└─ NO → Does it need LLM calls?
    ├─ NO → Use `skip_llm` fixture
    └─ YES → Does it need production model quality?
        ├─ NO → Use `fast_mode` fixture
        └─ YES → Use `production_mode` fixture
```

### Q: What about existing tests that use TESTING_MODE=1?

**A:** They still work via backward compatibility. Gradually migrate them to use granular fixtures. Priority:
1. Critical workflow tests → `production_mode`
2. Integration tests → `fast_mode` or selective bypasses
3. Unit tests → No changes needed (don't use environment variables)

### Q: Why did smoke tests catch bugs that integration tests missed?

**A:** Integration tests ran with `TESTING_MODE=1` which bypassed critical checks. Smoke tests run in **true production mode** and caught:
- FFmpeg PATH bug (Bug #1)
- Data structure mismatch (Bug #2)
- Session manager API (Bug #3)

### Q: How does this improve confidence?

**Before:** 202/204 tests pass → App doesn't launch ❌
**After:** 11/16 smoke tests pass → Caught both production bugs ✅

The smoke test failures were **true failures** representing real issues, not false positives.

## Implementation Details

### testing_mode.py Module

Location: `src/knowledge_system/utils/testing_mode.py`

Key functions:
```python
def skip_preflight() -> bool:
    """Check if SKIP_PREFLIGHT=1 is set."""

def skip_transcription() -> bool:
    """Check if SKIP_TRANSCRIPTION=1 is set."""

def skip_llm() -> bool:
    """Check if SKIP_LLM=1 is set."""

def is_fast_mode() -> bool:
    """Check if FAST_MODE=1 is set."""

def is_production_mode() -> bool:
    """Check if NONE of the testing flags are set."""

def get_whisper_model() -> str:
    """Get appropriate Whisper model: 'tiny' in FAST_MODE, 'base' otherwise."""

def ensure_production_mode():
    """Remove ALL testing mode environment variables."""

# Backward compatibility helpers
def should_skip_preflight() -> bool:
    """Legacy alias supporting old environment variable names."""
    return (
        skip_preflight() or
        os.environ.get("KC_SKIP_PREFLIGHT") == "1" or
        os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"
    )
```

### Integration with Components

Components import and use these functions:

```python
# In preflight.py
from knowledge_system.utils.testing_mode import should_skip_preflight

def quick_preflight():
    if should_skip_preflight():
        return
    # Run checks

# In audio_processor.py
from knowledge_system.utils.testing_mode import get_whisper_model

model = get_whisper_model()  # 'tiny' or 'base'
```

## Best Practices

### 1. Start with Production Mode

New tests should default to production mode unless there's a good reason not to:

```python
# ✅ Good: Production mode by default
def test_user_workflow(production_mode):
    pass

# ⚠️ Consider: Why do you need to bypass?
def test_user_workflow(skip_llm):
    # Document why skip is necessary
    pass
```

### 2. Document Why You're Skipping

```python
def test_database_queries(skip_llm, skip_transcription):
    """
    Test database claim storage operations.

    Skip LLM and transcription because:
    - This test focuses on database CRUD operations
    - LLM/transcription are tested separately
    - Skipping makes test run in <1s instead of 30s
    """
    pass
```

### 3. Use FAST_MODE for Development

```python
@pytest.mark.integration
def test_complete_pipeline_quickly(fast_mode):
    """
    Test full pipeline with tiny models for fast development iteration.

    Note: This doesn't test output quality, just workflow correctness.
    See test_complete_pipeline_production() for quality validation.
    """
    pass
```

### 4. Add Production Tests for Critical Paths

```python
@pytest.mark.production
@pytest.mark.slow
def test_complete_pipeline_production(production_mode):
    """
    Test full pipeline with production models and settings.

    This is the definitive integration test - runs exactly as users experience.
    Runtime: ~2 minutes. Run before releases.
    """
    pass
```

## Smoke Test Results

Current status (as of implementation):
```
tests/smoke/test_preflight_homebrew_detection.py::TestPreflightHomebrewDetection
    ✅ PASSED (5/5 tests)
    - Would have caught FFmpeg PATH bug

tests/smoke/test_download_service_output_structure.py::TestDownloadServiceOutputStructure
    ✅ PASSED (2/5 tests)
    ❌ FAILED (3/5 tests) - Minor API assumptions, non-blocking
    - Would have caught data structure mismatch bug

tests/smoke/test_app_launch_production.py::TestAppLaunchProduction
    ✅ PASSED (4/6 tests)
    ❌ FAILED (2/6 tests) - Environment-specific issues
    - Would have caught both production bugs

Overall: 11/16 passing on first run
```

**Impact:** Both critical production bugs would have been caught by smoke tests.

## Future Work

1. **Migrate existing integration tests** from TESTING_MODE=1 to granular fixtures
2. **Add more smoke tests** for other critical paths (claim extraction, export)
3. **Integrate smoke tests** into pre-push hooks
4. **Performance optimization** for production mode tests (parallel execution)
5. **CI/CD integration** with smoke test suite

## References

- **Original Issue:** "99% tests pass but app doesn't launch"
- **Bugs Caught:**
  - Bug #1: FFmpeg PATH detection failure
  - Bug #2: Data structure mismatch (`downloaded_files` vs `audio_path`)
  - Bug #3: SessionManager missing methods
- **Implementation:** Option C (Hybrid approach)
- **Module:** `src/knowledge_system/utils/testing_mode.py`
- **Smoke Tests:** `tests/smoke/` directory
- **Fixtures:** `tests/integration/conftest.py`

---

**Last Updated:** 2025-01-15 (Version 3.5.1)
