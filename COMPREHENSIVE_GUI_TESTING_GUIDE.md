# Comprehensive GUI Testing Guide

## Overview

You have a **comprehensive GUI testing framework** at `tests/gui_comprehensive/` that can test the GUI end-to-end, but it may not have been configured to catch certain types of errors like the model URI format bug.

## Quick Start

### 1. Setup Test Data (First Time Only)

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
./tests/gui_comprehensive/run_gui_tests.sh
# Choose option: "1. Smoke tests"
```

**Or run directly:**

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 -m tests.gui_comprehensive.main_test_runner setup
```

This creates test files in `tests/fixtures/sample_files/`:
- Audio files (MP3, WAV, M4A, FLAC, etc.)
- Video files (MP4, WEBM, MOV, etc.)
- Document files (MD, TXT, PDF, etc.)

### 2. Run GUI Tests

**Option A: Interactive Script (Recommended)**
```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
./tests/gui_comprehensive/run_gui_tests.sh
```

**Option B: Direct Command**
```bash
# Smoke tests (5-10 minutes) - Quick validation
python3 -m tests.gui_comprehensive.main_test_runner smoke

# Comprehensive tests (1-2 hours) - Full coverage
python3 -m tests.gui_comprehensive.main_test_runner comprehensive

# All tests (3+ hours)
python3 -m tests.gui_comprehensive.main_test_runner all
```

### 3. Use Existing GUI (For Debugging)

If you want to run tests against an already-open GUI (to watch what happens):

```bash
# 1. Open Knowledge Chipper GUI manually
# 2. Run tests with --no-gui-launch flag
python3 -m tests.gui_comprehensive.main_test_runner smoke --no-gui-launch
```

## Test Coverage

The framework tests:

### GUI Tabs Tested
- ✅ **Process Pipeline Tab** - Full pipeline workflows
- ✅ **Local Transcription Tab** - Audio/video transcription
- ✅ **Summarization Tab** - Document summarization (HCE pipeline)
- ✅ **YouTube Tab** - YouTube extraction
- ✅ **Monitor Tab** - System 2 job tracking
- ✅ **Review Tab** - Database queries
- ✅ **Claim Search Tab** - Claim searching
- ✅ **Speaker Attribution Tab** - Speaker assignment

### File Types Tested
- **Audio**: MP3, WAV, M4A, FLAC, OGG, AAC
- **Video**: MP4, WEBM, MOV, AVI, MKV
- **Documents**: MD, TXT, HTML, PDF

### Operations Tested
- Transcription (local Whisper)
- Summarization (HCE unified pipeline)
- MOC generation
- Batch processing
- System 2 job orchestration

## Why Tests May Not Have Caught the Model URI Bug

### Possible Reasons

1. **Tests may use default models**: The test framework might not be testing provider/model selection in the GUI dropdowns

2. **Tests may use Ollama exclusively**: If tests only use local Ollama models, the bug wouldn't surface (since `local/qwen2.5:7b` just gets misparsed but still tries Ollama)

3. **Tests may not validate model URIs**: Tests might check output quality but not the intermediate model configuration

4. **Provider selection not automated**: GUI automation might select files and click buttons but not test provider/model combos

### Verification

Let's check what the tests actually do:

```bash
# See what tests are defined
grep -r "def test_" tests/gui_comprehensive/

# Check if tests change providers
grep -r "provider.*combo\|model.*combo" tests/gui_comprehensive/
```

## Enhancing Tests to Catch This Bug

### Create a New Test: `test_model_configuration.py`

Create a test that specifically validates model URI construction from GUI selections:

```python
"""Test GUI model configuration and URI construction."""

def test_summarization_tab_model_uris(automation, main_window):
    """Test that GUI correctly constructs model URIs for HCE pipeline."""
    
    # Navigate to summarization tab
    automation.navigate_to_tab("Summarization")
    
    # Test OpenAI provider selection
    test_cases = [
        ("openai", "gpt-4o-mini", "openai:gpt-4o-mini"),
        ("anthropic", "claude-3-5-sonnet", "anthropic:claude-3-5-sonnet"),
        ("local", "qwen2.5:7b-instruct", "local://qwen2.5:7b-instruct"),
    ]
    
    for provider, model, expected_uri in test_cases:
        # Select provider and model in GUI
        automation.select_provider("miner_provider", provider)
        automation.select_model("miner_model", model)
        
        # Get the constructed model override
        tab = main_window.get_current_tab()
        actual_uri = tab._get_model_override(
            tab.miner_provider, 
            tab.miner_model
        )
        
        # Validate URI format
        assert actual_uri == expected_uri, (
            f"Model URI mismatch: GUI constructed '{actual_uri}' "
            f"but expected '{expected_uri}' for {provider}/{model}"
        )
```

## Test Modes Explained

| Mode | Duration | Tests | Best For |
|------|----------|-------|----------|
| **smoke** | 5-10 min | Quick validation, 1-2 files per type | Regression testing after fixes |
| **basic** | 30 min | Basic functionality, common scenarios | Daily development testing |
| **comprehensive** | 1-2 hours | Full permutation matrix | Pre-release validation |
| **stress** | 2+ hours | Large files, edge cases | Performance testing |
| **all** | 3+ hours | Every test suite sequentially | Complete system validation |

## Recommended Testing Workflow

### After Code Changes

1. **Smoke Tests** (5-10 min) - Quick sanity check
   ```bash
   python3 -m tests.gui_comprehensive.main_test_runner smoke
   ```

2. If smoke tests pass → **Unit Tests** (5 min)
   ```bash
   pytest tests/unit/
   ```

3. If unit tests pass → **Integration Tests** (15 min)
   ```bash
   pytest tests/integration/
   ```

### Before Committing

```bash
# Run comprehensive tests (1-2 hours)
python3 -m tests.gui_comprehensive.main_test_runner comprehensive
```

### Before Release

```bash
# Run ALL tests (3+ hours)
python3 -m tests.gui_comprehensive.main_test_runner all
```

## Test Outputs

Results are saved to `tests/reports/`:

```
tests/reports/
├── test_results/
│   ├── smoke_test_2025-10-16_14-30-00.json
│   └── comprehensive_test_2025-10-16_10-00-00.json
├── performance/
│   └── performance_metrics.json
└── coverage/
    └── gui_coverage_report.html
```

### Reading Test Results

```bash
# View latest test results
cat tests/reports/test_results/smoke_test_*.json | jq '.summary'

# Check for failures
cat tests/reports/test_results/smoke_test_*.json | jq '.failures'
```

## Common Issues

### Issue: "Virtual environment not found"
**Solution**: 
```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Issue: "Test data not found"
**Solution**:
```bash
python3 -m tests.gui_comprehensive.main_test_runner setup
```

### Issue: "GUI fails to launch"
**Solution**: Launch GUI manually first, then run:
```bash
python3 -m tests.gui_comprehensive.main_test_runner smoke --no-gui-launch
```

### Issue: Tests timeout
**Solution**: Increase timeout:
```bash
python3 -m tests.gui_comprehensive.main_test_runner smoke --timeout 600
```

## Integration with CI/CD

You can run GUI tests in CI/CD with headless mode:

```bash
# Set environment variable for headless testing
export QT_QPA_PLATFORM=offscreen
export KNOWLEDGE_CHIPPER_TESTING_MODE=1

# Run smoke tests
python3 -m tests.gui_comprehensive.main_test_runner smoke --no-gui-launch
```

## Next Steps: Catching More GUI Bugs

To ensure tests catch issues like the model URI bug:

1. **Add Provider/Model Selection Tests**
   - Test all provider combos (OpenAI, Anthropic, Local, Google, etc.)
   - Verify model URIs are constructed correctly
   - Check that actual API calls go to the right provider

2. **Add Configuration Validation Tests**
   - Verify GUI settings are correctly passed to backend
   - Test config serialization/deserialization
   - Validate environment variable injection

3. **Add Integration Tests with Mock APIs**
   - Mock OpenAI, Anthropic APIs
   - Verify correct provider is called
   - Check request format and authentication

4. **Add Error Scenario Tests**
   - Test what happens when wrong provider is called
   - Verify error messages are helpful
   - Check graceful degradation

## Example: Adding a New GUI Test

```python
# tests/gui_comprehensive/test_model_uris.py

import pytest
from tests.gui_comprehensive.gui_automation import GUIAutomation
from tests.gui_comprehensive.test_framework import GUITestFramework

def test_openai_model_uri_construction():
    """Test that selecting OpenAI in GUI creates correct URI."""
    # This test would:
    # 1. Launch GUI or connect to running instance
    # 2. Navigate to Summarization tab
    # 3. Select OpenAI provider
    # 4. Select gpt-4o-mini model
    # 5. Start processing (or inspect config before processing)
    # 6. Verify model URI is "openai:gpt-4o-mini" not "openai/gpt-4o-mini"
    # 7. Verify actual API call goes to OpenAI (using mock/spy)
    pass
```

## Summary

You **DO** have comprehensive GUI testing infrastructure. The model URI bug likely slipped through because:

1. Tests may not cover all provider/model selection permutations
2. Tests may not validate intermediate configuration (only final output)
3. Tests may primarily use Ollama (where the bug is less obvious)

**Solution**: Enhance existing tests to:
- Test provider/model selection
- Validate model URI construction
- Mock API calls to verify correct provider is used
- Add assertions on intermediate config, not just final output

