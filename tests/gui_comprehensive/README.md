# Comprehensive GUI Test Suite

This directory contains a comprehensive, deterministic test suite for the Knowledge Chipper GUI that validates all major workflows end-to-end.

## Overview

The test suite exercises:
- **Transcription workflows**: All input types (YouTube, RSS, local files, batch)
- **Summarization workflows**: All supported document formats
- **Database persistence**: Validates data written to SQLite
- **File generation**: Validates .md files with YAML frontmatter
- **Auto-process chains**: Tests connected workflows
- **Error handling**: Invalid inputs, cancellation, edge cases

## Quick Start

### Run All Tests (Fake Mode - Fast)
```bash
./run_comprehensive_gui_tests.sh fake
```

### Run Smoke Tests (Real Processing)
```bash
./run_comprehensive_gui_tests.sh smoke
```

### Run Full Real Processing Tests
```bash
# Requires Ollama installed and model downloaded
./run_comprehensive_gui_tests.sh real
```

## Test Modes

### Fake Mode (Recommended for CI)
- **Speed**: ~10 minutes for full suite
- **Requirements**: None (no external services needed)
- **Behavior**: Monkeypatches workers to emit completion signals and write canonical test data
- **Use case**: Fast validation of UI flows, DB persistence, file generation

```bash
export KNOWLEDGE_CHIPPER_FAKE_PROCESSING=1
pytest tests/gui_comprehensive/ -v
```

### Real Mode
- **Speed**: ~60+ minutes (model-dependent)
- **Requirements**: Ollama running with qwen2.5:7b-instruct model
- **Behavior**: Actual transcription and summarization
- **Use case**: Integration testing, manual validation

```bash
export KNOWLEDGE_CHIPPER_FAKE_PROCESSING=0
pytest tests/gui_comprehensive/ -v --timeout=300
```

### Smoke Mode
- **Speed**: ~5-10 minutes
- **Requirements**: Ollama running
- **Behavior**: Runs 1-2 real tests to validate core functionality
- **Use case**: Pre-commit checks, quick sanity testing

```bash
./run_comprehensive_gui_tests.sh smoke
```

## Test Structure

```
tests/gui_comprehensive/
├── README.md                      # This file
├── fake_processing.py             # Fake mode implementation
├── test_transcribe_inputs.py      # Parametrized transcription tests (12 cases)
├── test_transcribe_workflows.py   # Workflow tests (complete, cancel, errors)
├── test_summarize_inputs.py       # Parametrized summarization tests (7 cases)
├── test_outputs_validation.py     # DB and .md validation tests
└── utils/
    ├── __init__.py
    ├── test_utils.py              # UI helpers (switch tabs, find widgets)
    ├── db_validator.py            # SQLite validation
    └── fs_validator.py            # Markdown/YAML validation
```

## Test Matrix

### Transcription (12 tests)
| Input Type        | Auto-Process: Off | Auto-Process: On |
|-------------------|-------------------|------------------|
| YouTube URL       | ✓                 | ✓                |
| YouTube Playlist  | ✓                 | ✓                |
| RSS Feed          | ✓                 | ✓                |
| Local Audio       | ✓                 | ✓                |
| Local Video       | ✓                 | ✓                |
| Batch Files       | ✓                 | ✓                |

**Fixed settings**: whisper.cpp, medium model, diarization=on (conservative), language=English, cookies=yes, proxy=off

### Summarization (7 tests)
| Input Type | Provider | Model               |
|------------|----------|---------------------|
| .md        | Ollama   | qwen2.5:7b-instruct |
| .pdf       | Ollama   | qwen2.5:7b-instruct |
| .txt       | Ollama   | qwen2.5:7b-instruct |
| .docx      | Ollama   | qwen2.5:7b-instruct |
| .html      | Ollama   | qwen2.5:7b-instruct |
| .json      | Ollama   | qwen2.5:7b-instruct |
| .rtf       | Ollama   | qwen2.5:7b-instruct |

## Validation Rules

### Database Validation
Tests verify that after processing:

**For Transcriptions**:
- `media_sources` table has video record with correct metadata
- `transcripts` table has transcript with:
  - transcript_id, video_id
  - transcript_text (full text)
  - transcript_segments_json (timestamped segments)
  - language, whisper_model
  - diarization_enabled flag
  - created_at timestamp

**For Summarizations**:
- `summaries` table has summary with:
  - summary_id, video_id
  - summary_text
  - llm_provider='ollama', llm_model='qwen2.5:7b-instruct'
  - total_tokens, processing_cost
  - template_used ('flagship' or 'mining')
  - created_at timestamp

**For Jobs**:
- `processing_jobs` table has job record with:
  - job_type, status='completed'
  - input_file, output_file paths
  - created_at, completed_at timestamps

### File Validation
Tests verify markdown output files:

**Transcript .md files**:
- Location: `output/transcripts/`
- YAML frontmatter with: title, video_id, language, duration, processed_at
- Body contains transcript text with proper formatting
- If diarization enabled: speaker labels present

**Summary .md files**:
- Location: `output/summaries/`
- YAML frontmatter with: title, video_id, model_name, provider, timestamp
- Body contains summary content
- For flagship: "Summary" section present
- For mining: "Jargon", "People", "Mental Models" sections present

## Environment Variables

### Required (Always Set)
```bash
KNOWLEDGE_CHIPPER_TESTING_MODE=1    # Suppresses GUI dialogs
QT_QPA_PLATFORM=offscreen           # Runs GUI without display
```

### Test Sandboxing
```bash
KNOWLEDGE_CHIPPER_TEST_DB=/path/to/test.sqlite      # Override DB location
KNOWLEDGE_CHIPPER_TEST_OUTPUT_DIR=/path/to/output/  # Override output dir
```

### Processing Mode
```bash
KNOWLEDGE_CHIPPER_FAKE_PROCESSING=1   # Enable fake mode (fast)
KNOWLEDGE_CHIPPER_FAKE_PROCESSING=0   # Use real processing
```

## Writing New Tests

### 1. Use Test Fixtures
```python
@pytest.fixture
def test_sandbox(tmp_path):
    """Create isolated test sandbox."""
    from .utils import create_sandbox
    return create_sandbox(tmp_path / "sandbox")

@pytest.fixture
def gui_app(qapp, test_sandbox):
    """Launch GUI with test sandbox."""
    from knowledge_system.gui.main_window_pyqt6 import MainWindow
    window = MainWindow()
    window.show()
    process_events_for(500)
    yield window
    window.close()
```

### 2. Switch Tabs and Find Widgets
```python
from .utils import switch_to_tab, find_button_by_text

assert switch_to_tab(gui_app, "Transcribe")
start_btn = find_button_by_text(gui_app, "Start")
assert start_btn is not None
```

### 3. Validate Results
```python
from .utils import DBValidator, read_markdown_with_frontmatter

# Check database
db = DBValidator(test_sandbox.db_path)
assert db.has_transcript_for_video("test_video_001")

# Check markdown file
md_path = test_sandbox.output_dir / "transcripts" / "test.md"
frontmatter, body = read_markdown_with_frontmatter(md_path)
assert frontmatter["video_id"] == "test_video_001"
assert len(body) > 0
```

### 4. Use Wait Helpers
```python
from .utils import wait_until, process_events_for

# Wait for condition
success = wait_until(lambda: db.job_completed("transcription"), timeout_ms=5000)
assert success

# Process events
process_events_for(200)  # Allow UI to update
```

## Troubleshooting

### Tests Hang
- Check timeout settings (`--timeout=60` for fake, `--timeout=300` for real)
- Verify `QT_QPA_PLATFORM=offscreen` is set
- Look for blocking dialogs (should be suppressed by `KNOWLEDGE_CHIPPER_TESTING_MODE=1`)

### Database Errors
- Ensure `KNOWLEDGE_CHIPPER_TEST_DB` points to writable location
- Check that test sandbox is properly created
- Verify database migrations ran (tables exist)

### Import Errors
- Activate virtual environment: `source venv/bin/activate`
- Install requirements: `pip install -r requirements.txt -r requirements-dev.txt`
- Check Python version (3.11+ required)

### Fake Mode Not Working
- Verify `KNOWLEDGE_CHIPPER_FAKE_PROCESSING=1` is set
- Check that `fake_processing.py` monkeypatches are installed
- Look for "Fake processing mode enabled" message in logs

### Real Mode Failures
- Ensure Ollama is running: `curl http://localhost:11434/api/version`
- Pull model: `ollama pull qwen2.5:7b-instruct`
- Check model name matches exactly (case-sensitive)
- Increase timeout for slow hardware

## CI Integration

Tests run automatically on:
- Push to `main` or `develop`
- Pull requests
- Manual workflow dispatch

See `.github/workflows/comprehensive-gui-tests.yml` for CI configuration.

### CI Test Matrix
- **Fake mode**: Ubuntu + macOS, Python 3.11 + 3.12
- **Real smoke**: macOS only (manual trigger)

## Performance

| Mode  | Duration | CPU    | Memory | Disk  |
|-------|----------|--------|--------|-------|
| Fake  | ~10 min  | Low    | ~500MB | ~50MB |
| Smoke | ~10 min  | Medium | ~2GB   | ~1GB  |
| Real  | ~60 min  | High   | ~4GB   | ~10GB |

## Maintenance

### Adding New Input Types
1. Add test case to `test_transcribe_inputs.py` or `test_summarize_inputs.py`
2. Update test matrix in this README
3. Add sample file to `tests/fixtures/sample_files/` if needed
4. Update fake mode to generate appropriate results

### Updating Validation Rules
1. Modify `utils/db_validator.py` for database checks
2. Modify `utils/fs_validator.py` for file checks
3. Update validation documentation in this README

### Changing Models
- Update `test_summarize_inputs.py` with new model identifier
- Update fake mode results to match new model output format
- Update documentation

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review test logs in `tests/tmp/` and `test-results/`
3. Run with verbose mode: `VERBOSE=1 ./run_comprehensive_gui_tests.sh fake`
4. Check CI logs for similar failures
