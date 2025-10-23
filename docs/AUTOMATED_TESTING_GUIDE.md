# Automated GUI Testing Guide

## Overview

Knowledge Chipper has a comprehensive automated testing system that tests ALL GUI workflows, tabs, and processes without requiring human intervention. This catches bugs before they reach production.

## Quick Start

### Run All Automated Tests

```bash
# From project root
./tests/run_comprehensive_automated_tests.sh
```

This will:
- ✅ Test all GUI tabs and workflows
- ✅ Test all input types (audio, video, PDF, YouTube, text)
- ✅ Test error handling and edge cases
- ✅ Test database integration
- ✅ Test System 2 orchestration
- ✅ Generate detailed bug reports

**Time required**: ~15-30 minutes for complete test suite

### Run Quick Smoke Tests

```bash
# Fast validation (5-10 minutes)
cd tests/gui_comprehensive
../../venv/bin/python3 main_test_runner.py smoke
```

### Run Specific Test Categories

```bash
# GUI workflow tests only
venv/bin/pytest tests/gui_comprehensive/test_all_workflows_automated.py -v

# System 2 integration tests
venv/bin/pytest tests/gui_comprehensive/test_system2_integration.py -v

# Database tests
venv/bin/pytest tests/integration/test_system2_database.py -v
```

## What Gets Tested

### 1. GUI Tabs and Navigation
- ✅ All tabs load without errors
- ✅ Tab switching works correctly
- ✅ UI elements are accessible and responsive

### 2. YouTube Download Workflow
- ✅ URL input validation
- ✅ Quality selection
- ✅ Download button functionality
- ✅ Cookie authentication (when enabled)
- ✅ Error handling for invalid URLs

### 3. Transcription Workflow
- ✅ Provider selection (OpenAI, Deepgram, etc.)
- ✅ Model selection
- ✅ File selection
- ✅ Transcription submission
- ✅ Speaker diarization options

### 4. Summarization Workflow
- ✅ LLM provider selection
- ✅ Model selection
- ✅ Prompt customization
- ✅ Output format options

### 5. Knowledge Mining Workflow
- ✅ Mining configuration
- ✅ Sequential vs. parallel processing
- ✅ YAML output generation
- ✅ Jargon, People, Mental Models extraction

### 6. Speaker Attribution Workflow
- ✅ Speaker configuration
- ✅ Attribution processing
- ✅ Voice fingerprinting (when enabled)

### 7. Monitor Tab (System 2)
- ✅ Job list display
- ✅ Job status tracking
- ✅ Job controls (pause, resume, cancel)
- ✅ Real-time updates

### 8. Review Tab
- ✅ Database integration
- ✅ Result display
- ✅ Filtering and search
- ✅ Export functionality

### 9. Settings and Configuration
- ✅ API key management
- ✅ Settings persistence
- ✅ Provider/model defaults
- ✅ Output directory configuration

### 10. Error Handling
- ✅ Invalid input handling
- ✅ Network error handling
- ✅ Missing dependencies detection
- ✅ Graceful degradation

## Test Modes

### Smoke Tests (5-10 minutes)
Quick validation that core functionality works:
```bash
./tests/gui_comprehensive/main_test_runner.py smoke
```

### Comprehensive Tests (30-60 minutes)
Full workflow testing across all tabs and processes:
```bash
./tests/run_comprehensive_automated_tests.sh
```

### Stress Tests (2+ hours)
Large file processing and concurrent operation tests:
```bash
./tests/gui_comprehensive/main_test_runner.py stress
```

## Automated Bug Detection

After running tests, automatically detect and report bugs:

```bash
# Analyze test results and generate bug report
python tests/tools/bug_detector.py tests/reports/

# Output: tests/reports/bug_reports/bug_report_YYYYMMDD_HHMMSS.md
```

The bug detector automatically identifies:
- 🔴 **Critical**: Crashes, segfaults, fatal errors
- 🟠 **High**: Assertion failures, UI errors, database corruption
- 🟡 **Medium**: Timeouts, performance issues
- 🟢 **Low**: Minor UI glitches, warnings

Each bug report includes:
- Severity and category
- Affected components
- Reproduction steps
- Error messages and stack traces
- Related test cases

## CI/CD Integration

### GitHub Actions (Automated on Every Push/PR)

The automated tests run automatically on:
- Every push to `main` or `develop`
- Every pull request
- Manual workflow dispatch

Configuration: `.github/workflows/automated-gui-tests.yml`

Tests run on:
- macOS (latest)
- Ubuntu (latest)
- Python 3.11 and 3.12

### View Results

1. Go to your repository on GitHub
2. Click "Actions" tab
3. Select "Automated GUI Tests" workflow
4. View test results, download artifacts

### PR Comments

Test results are automatically posted as comments on pull requests, showing:
- Total tests run
- Pass/fail counts
- Success rate
- Failed test details

## Understanding Test Results

### Test Reports Structure

```
tests/reports/automated_YYYYMMDD_HHMMSS/
├── SUMMARY.txt                    # Overall summary
├── phase_1_core_unit_tests.txt    # Unit test results
├── phase_2_gui_smoke_tests.txt    # Smoke test results
├── phase_3_all_gui_workflows.txt  # Workflow test results
├── phase_4_system_2_integration.txt
├── phase_5_database_integration.txt
└── phase_6_review_tab_monitoring.txt
```

### Reading Test Output

```
================================================================
Phase 3/6: All GUI Workflows
================================================================

test_youtube_download_workflow ✅ PASSED
test_transcription_workflow ✅ PASSED
test_summarization_workflow ✅ PASSED
test_speaker_attribution_workflow ✅ PASSED
test_monitor_tab_system2 ✅ PASSED
test_review_tab_database ❌ FAILED
  Details: Database connection timeout

================================================================
FINAL TEST REPORT
================================================================

Total test phases: 6
Passed: 5
Failed: 1
Success rate: 83%
```

## Writing New Tests

### Adding a New Workflow Test

Edit `tests/gui_comprehensive/test_all_workflows_automated.py`:

```python
def test_my_new_workflow(self, gui_tester):
    """Test my new workflow."""
    # Switch to relevant tab
    assert gui_tester.switch_to_tab("My Tab"), "Failed to switch to tab"
    
    # Interact with UI
    gui_tester.set_text_field("my_input", "test value")
    gui_tester.select_combo_item("my_combo", "Option 1")
    
    # Click button
    result = gui_tester.click_button("my_button")
    
    # Record result
    gui_tester.record_result(
        "my_new_workflow",
        result,
        "Description of what was tested"
    )
    
    assert result, "Workflow failed"
```

### Testing Best Practices

1. **Use Testing Mode**: Always set `KNOWLEDGE_CHIPPER_TESTING_MODE=1`
   - Suppresses interactive dialogs
   - Enables headless testing
   - Prevents network calls (when appropriate)

2. **Set Reasonable Timeouts**: 
   - Smoke tests: 60 seconds per test
   - Workflow tests: 300 seconds per test
   - Stress tests: 600+ seconds per test

3. **Check for Prerequisites**:
   - Verify widgets exist before interacting
   - Handle missing components gracefully
   - Provide clear error messages

4. **Clean Up Resources**:
   - Close windows properly
   - Stop background threads
   - Clear temporary files

## Troubleshooting

### Tests Fail to Start

```bash
# Check Python environment
which python3
python3 --version

# Reinstall dependencies
./venv/bin/pip install -e .
./venv/bin/pip install pytest pytest-asyncio pytest-timeout
```

### GUI Doesn't Launch in Tests

```bash
# Check environment variables
echo $KNOWLEDGE_CHIPPER_TESTING_MODE  # Should be "1"
echo $QT_QPA_PLATFORM                  # Should be "offscreen"

# On Linux, may need Xvfb
xvfb-run -a ./tests/run_comprehensive_automated_tests.sh
```

### Tests Timeout

```bash
# Run with longer timeout
pytest tests/gui_comprehensive/test_all_workflows_automated.py --timeout=600

# Or run specific slow tests individually
pytest tests/gui_comprehensive/test_all_workflows_automated.py::TestAllGUIWorkflows::test_youtube_download_workflow
```

### Database Errors

```bash
# Reset test database
rm -f tests/fixtures/test_knowledge_system.db

# Or use in-memory database for testing
export KNOWLEDGE_CHIPPER_TEST_DB=":memory:"
```

## Performance Optimization

### Parallel Test Execution

Run tests in parallel for faster results:

```bash
# Run with 4 parallel workers
pytest tests/ -n 4 --dist=loadgroup
```

### Skip Slow Tests

```bash
# Skip tests marked as slow
pytest tests/ -m "not slow"

# Run only fast smoke tests
pytest tests/gui_comprehensive/test_smoke_automated.py
```

### Cached Test Data

Generate test data once and reuse:

```bash
# Generate test files
cd tests/gui_comprehensive
./setup_test_data.sh

# Files are cached in tests/fixtures/sample_files/
```

## Continuous Improvement

### Add Tests for New Features

When adding a new feature:
1. Write automated tests FIRST (TDD)
2. Test happy path and error cases
3. Test edge cases and boundary conditions
4. Update this documentation

### Monitor Test Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src/knowledge_system --cov-report=html

# Open htmlcov/index.html to view coverage
open htmlcov/index.html
```

### Review Bug Reports Regularly

```bash
# After each test run
ls -lt tests/reports/*/bug_reports/

# Review the most recent report
cat tests/reports/*/bug_reports/bug_report_*.md | less
```

## Integration with Development Workflow

### Before Committing

```bash
# Run smoke tests (5 minutes)
./tests/gui_comprehensive/main_test_runner.py smoke

# If all pass, commit
git add .
git commit -m "Feature: Added XYZ"
```

### Before Merging PR

```bash
# Run comprehensive tests (30 minutes)
./tests/run_comprehensive_automated_tests.sh

# Review bug report
python tests/tools/bug_detector.py tests/reports/

# If success rate > 95%, merge
```

### After Release

```bash
# Run full test suite including stress tests
./tests/gui_comprehensive/main_test_runner.py all

# Archive results for comparison
cp -r tests/reports/automated_* tests/reports/release_$(date +%Y%m%d)/
```

## Summary

✅ **Automated testing catches bugs before production**
✅ **All GUI workflows are tested**
✅ **CI/CD integration on every commit**
✅ **Automatic bug detection and reporting**
✅ **Comprehensive test coverage**

**Run tests frequently. Catch bugs early. Ship with confidence.**

For questions or issues, see:
- `tests/README.md` - Testing framework overview
- `tests/gui_comprehensive/README.md` - GUI testing details
- `.github/workflows/automated-gui-tests.yml` - CI/CD configuration

