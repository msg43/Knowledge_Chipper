# GUI Testing Suite

Comprehensive testing for PyQt6 GUI components using `pytest-qt`, `pytest-timeout`, and `ipdb`.

## Quick Start

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all GUI tests
pytest tests/gui/ -v

# Run with GUI-specific configuration
pytest -c pytest.ini.gui_testing tests/gui/ -v

# Run only smoke tests (fast)
pytest tests/gui/ -k "smoke" -v

# Run only interaction tests
pytest tests/gui/test_user_interactions.py -v

# Run with custom timeout
pytest tests/gui/ -v --timeout=60
```

## Test Files

### `test_all_tabs_smoke.py`
**Purpose**: Verify all GUI tabs can be instantiated without errors.

**What it tests**:
- Tab initialization
- Widget existence
- Basic widget methods (`.text()`, `.value()`, `.currentText()`)

**Run time**: ~5-10 seconds

```bash
pytest tests/gui/test_all_tabs_smoke.py -v
```

### `test_summarization_tab_smoke.py`
**Purpose**: Detailed smoke tests for SummarizationTab.

**What it tests**:
- Widget attribute existence
- Method availability
- Source code analysis for missing widgets

**Run time**: ~2-3 seconds

```bash
pytest tests/gui/test_summarization_tab_smoke.py -v
```

### `test_widget_initialization.py`
**Purpose**: Static analysis of widget initialization patterns.

**What it tests**:
- All referenced widgets are initialized in `__init__`
- Widget naming conventions
- Method calls match widget types (`.value()` on spinboxes, etc.)

**Run time**: ~3-5 seconds

```bash
pytest tests/gui/test_widget_initialization.py -v
```

### `test_user_interactions.py` ⭐ NEW
**Purpose**: Simulate real user interactions with the GUI.

**What it tests**:
- Button clicks
- Text input
- Dropdown selections
- Checkbox toggles
- Signal/slot connections
- Async operations
- Conditional UI behavior

**Run time**: ~10-30 seconds

```bash
pytest tests/gui/test_user_interactions.py -v
```

### `test_user_workflows.py` ⭐ NEW
**Purpose**: Simulate complete end-to-end user workflows.

**What it tests**:
- **Transcription workflows**: Local audio files, YouTube URLs, batch transcription
- **Summarization workflows**: Single transcripts, folder batches, template changes
- **Complete journeys**: Transcribe → Summarize → Review
- **Settings workflows**: Changing API keys, models, preferences
- **Monitor workflows**: Setting up folder watching, auto-processing
- **Error handling**: Invalid inputs, missing files, edge cases

**Run time**: ~2-5 minutes (full suite)

```bash
# Run all workflow tests
pytest tests/gui/test_user_workflows.py -v --timeout=300

# Run specific workflow category
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows -v
pytest tests/gui/test_user_workflows.py::TestSummarizationWorkflows -v

# Run specific workflow
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_local_audio_file -v
```

## Test Fixtures (conftest.py)

Shared fixtures available to all tests:

### Basic Fixtures
- `qapp` - QApplication instance (session-scoped)
- `mock_settings` - Mock settings manager
- `mock_gui_settings` - Mock GUI settings manager

### Sample Data
- `sample_transcript_file` - Single test transcript
- `sample_transcript_files` - Multiple test transcripts
- `sample_yaml_template` - Test YAML template

### Helper Fixtures
- `wait_for_signal(signal, timeout)` - Wait for Qt signal
- `click_button(button)` - Click button with event processing
- `type_text(widget, text)` - Type text into widget
- `mock_file_dialog(files)` - Mock file selection dialogs
- `mock_message_box()` - Mock message boxes
- `disable_network()` - Prevent network access
- `capture_signals(signal)` - Capture emitted signals

## Common Test Patterns

### Testing Button Clicks

```python
def test_button_click(qtbot, tab):
    """Test button click interaction."""
    qtbot.mouseClick(tab.start_btn, Qt.MouseButton.LeftButton)
    qtbot.wait(100)  # Wait for UI update
    assert tab.some_state_changed
```

### Testing Text Input

```python
def test_text_input(qtbot, tab):
    """Test text input."""
    qtbot.keyClicks(tab.url_input, "https://example.com")
    assert "example.com" in tab.url_input.text()
```

### Testing Signals

```python
def test_signal_emission(qtbot, tab):
    """Test signal is emitted."""
    with qtbot.waitSignal(tab.my_signal, timeout=1000):
        tab.trigger_action()
```

### Testing Async Operations

```python
@pytest.mark.timeout(30)
def test_async_operation(qtbot, tab):
    """Test async operation with timeout."""
    with qtbot.waitSignal(tab.worker.finished, timeout=30000):
        tab.start_worker()
```

## Debugging Failed Tests

### Using ipdb

```python
def test_something(qtbot, tab):
    """Test with debugging."""
    breakpoint()  # Execution stops here
    
    # Now you can:
    # - Inspect: p tab.file_list.count()
    # - Try actions: qtbot.mouseClick(tab.button, Qt.MouseButton.LeftButton)
    # - Check state: p tab.is_processing
```

### Running with ipdb

```bash
# Run test and drop into debugger on failure
pytest tests/gui/test_user_interactions.py --pdb

# Or use ipdb specifically
pytest tests/gui/test_user_interactions.py --pdbcls=IPython.terminal.debugger:TerminalPdb
```

### Common ipdb Commands

```
n       - Next line
s       - Step into function
c       - Continue execution
l       - List code
p var   - Print variable
pp var  - Pretty-print variable
w       - Show stack trace
q       - Quit debugger
```

## Test Organization

### Markers

Tests can be marked for selective running:

```python
@pytest.mark.slow
def test_long_operation():
    """Marked as slow."""
    ...

@pytest.mark.requires_ollama
def test_with_ollama():
    """Requires Ollama running."""
    ...

@pytest.mark.integration
def test_full_pipeline():
    """Integration test."""
    ...
```

Run specific markers:

```bash
# Skip slow tests
pytest tests/gui/ -m "not slow"

# Run only integration tests
pytest tests/gui/ -m "integration"

# Run only tests that don't require Ollama
pytest tests/gui/ -m "not requires_ollama"
```

## Timeout Protection

All tests have automatic timeout protection to prevent hanging:

```bash
# Global timeout (30 minutes)
pytest tests/gui/ --timeout=1800

# Per-test timeout
@pytest.mark.timeout(60)  # 60 seconds
def test_something():
    ...
```

## Best Practices

1. ✅ **Use fixtures** - Reuse common setup code
2. ✅ **Mock external services** - Don't hit real APIs
3. ✅ **Test one thing** - Each test should verify one behavior
4. ✅ **Use descriptive names** - `test_button_disabled_without_files` not `test_button`
5. ✅ **Add timeouts** - Prevent tests from hanging forever
6. ✅ **Clean up** - Use `tmp_path` and `qtbot.addWidget()` for automatic cleanup
7. ✅ **Debug with ipdb** - Use `breakpoint()` to inspect failures

## Continuous Integration

Tests run automatically on CI with:

```yaml
- name: Run GUI tests
  run: |
    pip install -r requirements-dev.txt
    pytest tests/gui/ -v --timeout=1800 --tb=short
```

## Troubleshooting

### Test Hangs
- Add `@pytest.mark.timeout(N)` to specific tests
- Use `--timeout=N` flag when running pytest

### QApplication Error
- Use session-scoped `qapp` fixture (already configured)
- Don't create multiple QApplication instances

### Widget Not Found
- Use `breakpoint()` and inspect with `dir(tab)`
- Check widget naming with `tab.findChildren(QWidget)`

### Signal Not Emitted
- Increase timeout: `qtbot.waitSignal(signal, timeout=10000)`
- Verify signal exists: `assert hasattr(widget, 'my_signal')`

## Resources

- [Full Testing Guide](../../docs/GUI_TESTING_GUIDE.md)
- [pytest-qt Documentation](https://pytest-qt.readthedocs.io/)
- [pytest-timeout Documentation](https://pypi.org/project/pytest-timeout/)
- [ipdb Documentation](https://github.com/gotcha/ipdb)

## Summary

Our GUI testing suite provides:

1. 🔍 **Smoke Tests** - Catch initialization bugs
2. 🔬 **Static Analysis** - Validate widget references
3. 🎮 **Interaction Tests** - Simulate real users
4. ⏱️ **Timeout Protection** - Prevent hanging
5. 🐛 **Interactive Debugging** - Use ipdb to investigate failures

Run `pytest tests/gui/ -v` to verify everything works! 🚀
