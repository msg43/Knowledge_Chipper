# GUI Testing Guide

This guide explains how to write comprehensive GUI tests using `pytest-qt`, `pytest-timeout`, and `ipdb` for the Knowledge Chipper application.

## Table of Contents

1. [Overview](#overview)
2. [Test Structure](#test-structure)
3. [Using pytest-qt](#using-pytest-qt)
4. [Simulating User Interactions](#simulating-user-interactions)
5. [Testing Async Operations](#testing-async-operations)
6. [Debugging GUI Tests](#debugging-gui-tests)
7. [Best Practices](#best-practices)
8. [Examples](#examples)

## Overview

Our GUI testing suite consists of three layers:

1. **Smoke Tests** (`test_*_smoke.py`) - Verify widgets exist and can be instantiated
2. **Widget Validation** (`test_widget_initialization.py`) - Static analysis of widget references
3. **Integration Tests** (`test_user_interactions.py`) - Simulate real user interactions

## Test Structure

### Directory Layout

```
tests/gui/
├── conftest.py                          # Shared fixtures and configuration
├── test_all_tabs_smoke.py              # Smoke tests for all tabs
├── test_summarization_tab_smoke.py     # Detailed smoke tests
├── test_widget_initialization.py       # Static widget validation
└── test_user_interactions.py           # User interaction tests (NEW)
```

### Running Tests

```bash
# Run all GUI tests
pytest tests/gui/ -v

# Run only smoke tests
pytest tests/gui/ -k "smoke" -v

# Run only interaction tests
pytest tests/gui/test_user_interactions.py -v

# Run with timeout protection (30 minute max per test)
pytest tests/gui/ -v --timeout=1800

# Run with specific timeout
pytest tests/gui/ -v --timeout=60

# Skip slow tests
pytest tests/gui/ -v -m "not slow"
```

## Using pytest-qt

### The `qtbot` Fixture

`qtbot` is the main fixture provided by `pytest-qt` for interacting with Qt widgets.

```python
def test_button_click(qtbot, summarization_tab):
    """Example of using qtbot to click a button."""
    # Click a button
    qtbot.mouseClick(summarization_tab.start_btn, Qt.MouseButton.LeftButton)
    
    # Wait for UI to update
    qtbot.wait(100)  # Wait 100ms
```

### Available qtbot Methods

#### Mouse Interactions

```python
# Click
qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)
qtbot.mouseClick(widget, Qt.MouseButton.RightButton)

# Double click
qtbot.mouseDClick(widget, Qt.MouseButton.LeftButton)

# Mouse move
qtbot.mouseMove(widget, pos=QPoint(10, 10))

# Mouse press and release
qtbot.mousePress(widget, Qt.MouseButton.LeftButton)
qtbot.mouseRelease(widget, Qt.MouseButton.LeftButton)
```

#### Keyboard Interactions

```python
# Type text
qtbot.keyClicks(line_edit, "Hello World")

# Press specific keys
qtbot.keyPress(widget, Qt.Key.Key_Return)
qtbot.keyPress(widget, Qt.Key.Key_Escape)

# Key combinations
qtbot.keyPress(widget, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)  # Ctrl+C
```

#### Waiting and Timing

```python
# Wait for specific duration
qtbot.wait(1000)  # Wait 1 second

# Wait for signal
with qtbot.waitSignal(widget.my_signal, timeout=5000):
    widget.trigger_action()

# Wait for multiple signals
with qtbot.waitSignals([signal1, signal2], timeout=5000):
    widget.trigger_action()

# Wait for callback
qtbot.waitUntil(lambda: widget.isVisible(), timeout=5000)
```

## Simulating User Interactions

### Example 1: File Selection

```python
def test_file_selection(qtbot, summarization_tab, tmp_path, mock_file_dialog):
    """Test that user can select files."""
    # Create test files
    test_file = tmp_path / "transcript.txt"
    test_file.write_text("Test content")
    
    # Mock file dialog to return our test file
    mock_file_dialog([str(test_file)])
    
    # Simulate user clicking "Add Files" button
    qtbot.mouseClick(summarization_tab.add_files_btn, Qt.MouseButton.LeftButton)
    
    # Verify file was added to list
    assert summarization_tab.file_list.count() == 1
    assert str(test_file) in summarization_tab.file_list.item(0).text()
```

### Example 2: Dropdown Selection

```python
def test_provider_selection(qtbot, summarization_tab):
    """Test that user can select AI provider."""
    # Get current selection
    initial_provider = summarization_tab.provider_combo.currentText()
    
    # Change selection
    if summarization_tab.provider_combo.count() > 1:
        # Wait for the signal that indicates selection changed
        with qtbot.waitSignal(summarization_tab.provider_combo.currentTextChanged):
            summarization_tab.provider_combo.setCurrentIndex(1)
        
        # Verify selection changed
        assert summarization_tab.provider_combo.currentText() != initial_provider
```

### Example 3: Checkbox Toggle

```python
def test_checkbox_toggle(qtbot, transcription_tab):
    """Test that user can toggle diarization checkbox."""
    initial_state = transcription_tab.diarization_checkbox.isChecked()
    
    # Simulate user clicking checkbox
    qtbot.mouseClick(transcription_tab.diarization_checkbox, Qt.MouseButton.LeftButton)
    
    # Verify state changed
    assert transcription_tab.diarization_checkbox.isChecked() != initial_state
```

### Example 4: Text Input

```python
def test_text_input(qtbot, transcription_tab):
    """Test that user can enter YouTube URL."""
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    # Click to focus
    qtbot.mouseClick(transcription_tab.url_input, Qt.MouseButton.LeftButton)
    
    # Type URL
    qtbot.keyClicks(transcription_tab.url_input, test_url)
    
    # Verify text was entered
    assert transcription_tab.url_input.text() == test_url
```

## Testing Async Operations

### Using pytest-timeout

Protect tests from hanging indefinitely:

```python
@pytest.mark.timeout(30)  # Test will fail if it takes more than 30 seconds
def test_long_running_operation(qtbot, summarization_tab):
    """Test that doesn't hang forever."""
    # ... test code ...
```

### Testing Worker Threads

```python
def test_worker_thread(qtbot, summarization_tab, tmp_path):
    """Test that worker thread is created and signals properly."""
    from knowledge_system.gui.tabs.summarization_tab import EnhancedSummarizationWorker
    
    test_file = tmp_path / "test.txt"
    test_file.write_text("Content")
    
    # Create worker
    worker = EnhancedSummarizationWorker(
        files=[str(test_file)],
        settings={},
        gui_settings=Mock()
    )
    
    # Connect to signals
    progress_updates = []
    worker.progress_updated.connect(lambda p: progress_updates.append(p))
    
    # Wait for completion signal
    with qtbot.waitSignal(worker.processing_finished, timeout=30000):
        worker.start()
    
    # Verify progress updates were received
    assert len(progress_updates) > 0
```

### Testing Signal Emissions

```python
def test_signal_emission(qtbot, introduction_tab):
    """Test that navigation signal is emitted correctly."""
    # Capture signal
    signals_received = []
    introduction_tab.navigate_to_tab.connect(
        lambda tab: signals_received.append(tab)
    )
    
    # Trigger signal
    introduction_tab.navigate_to_tab.emit("Transcribe")
    
    # Verify signal was received
    assert len(signals_received) == 1
    assert signals_received[0] == "Transcribe"
```

## Debugging GUI Tests

### Using ipdb

When a test fails, you can use `ipdb` for interactive debugging:

```python
def test_something(qtbot, summarization_tab):
    """Test with debugging."""
    import ipdb; ipdb.set_trace()  # Debugger will stop here
    
    # Or use the modern way:
    breakpoint()  # Python 3.7+ (set PYTHONBREAKPOINT=ipdb.set_trace)
    
    # Now you can:
    # - Inspect widget states: summarization_tab.file_list.count()
    # - Try interactions: qtbot.mouseClick(summarization_tab.start_btn, Qt.MouseButton.LeftButton)
    # - Check attributes: dir(summarization_tab)
```

### ipdb Commands

```
n (next)      - Execute next line
s (step)      - Step into function
c (continue)  - Continue execution
l (list)      - Show code context
p variable    - Print variable value
pp variable   - Pretty-print variable
w (where)     - Show stack trace
u (up)        - Move up stack frame
d (down)      - Move down stack frame
q (quit)      - Quit debugger
```

### Debugging Tips

1. **Inspect Widget State**:
   ```python
   breakpoint()
   # In debugger:
   p summarization_tab.file_list.count()
   p summarization_tab.provider_combo.currentText()
   ```

2. **Check Widget Visibility**:
   ```python
   p widget.isVisible()
   p widget.isEnabled()
   p widget.geometry()
   ```

3. **Examine Signals**:
   ```python
   # Check if signal is connected
   p widget.my_signal.receivers(widget.my_signal)
   ```

4. **Test Interactions Live**:
   ```python
   breakpoint()
   # In debugger:
   qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
   p widget.state_after_click
   ```

## Best Practices

### 1. Use Fixtures for Common Setup

```python
@pytest.fixture
def configured_tab(qtbot, mock_settings):
    """Create a fully configured tab for testing."""
    from knowledge_system.gui.tabs.summarization_tab import SummarizationTab
    
    tab = SummarizationTab()
    qtbot.addWidget(tab)
    
    # Pre-configure common settings
    tab.provider_combo.setCurrentText("openai")
    tab.model_combo.setCurrentText("gpt-4")
    
    return tab
```

### 2. Test One Thing at a Time

```python
# Good - tests one specific behavior
def test_file_selection_updates_count(qtbot, tab):
    initial_count = tab.file_list.count()
    add_file(tab, "test.txt")
    assert tab.file_list.count() == initial_count + 1

# Bad - tests multiple unrelated things
def test_everything(qtbot, tab):
    add_file(tab, "test.txt")
    assert tab.file_list.count() == 1
    change_provider(tab, "openai")
    assert tab.provider_combo.currentText() == "openai"
    # ... too much in one test
```

### 3. Use Descriptive Test Names

```python
# Good
def test_start_button_disabled_when_no_files_selected(qtbot, tab):
    ...

# Bad
def test_button(qtbot, tab):
    ...
```

### 4. Mock External Dependencies

```python
def test_file_processing(qtbot, tab, mock_ollama_manager, disable_network):
    """Test file processing without hitting external services."""
    # Network is disabled, Ollama is mocked
    # Test can run fast and reliably
    ...
```

### 5. Use Timeouts Appropriately

```python
# For fast UI tests
@pytest.mark.timeout(5)
def test_button_click(qtbot, tab):
    ...

# For tests that process files
@pytest.mark.timeout(30)
def test_file_processing(qtbot, tab):
    ...

# For integration tests
@pytest.mark.timeout(300)  # 5 minutes
def test_full_pipeline(qtbot, tab):
    ...
```

### 6. Clean Up After Tests

```python
def test_something(qtbot, tab, tmp_path):
    """Test that cleans up properly."""
    # Use tmp_path for temporary files - automatically cleaned up
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    
    # qtbot.addWidget() ensures widget is cleaned up
    qtbot.addWidget(tab)
    
    # No manual cleanup needed!
```

## Examples

### Complete Test Example

```python
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

@pytest.mark.timeout(10)
class TestSummarizationWorkflow:
    """Test complete summarization workflow."""
    
    @pytest.fixture
    def tab(self, qtbot, mock_settings):
        """Create configured tab."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab
        
        tab = SummarizationTab()
        qtbot.addWidget(tab)
        return tab
    
    def test_user_can_analyze_transcript(self, qtbot, tab, tmp_path, mock_file_dialog):
        """Test that user can select and analyze a transcript."""
        # 1. Create test file
        transcript = tmp_path / "test_transcript.txt"
        transcript.write_text("Speaker 1: Test content for analysis.")
        
        # 2. Mock file dialog
        mock_file_dialog([str(transcript)])
        
        # 3. User clicks "Add Files"
        qtbot.mouseClick(tab.add_files_btn, Qt.MouseButton.LeftButton)
        
        # 4. Verify file was added
        assert tab.file_list.count() == 1
        
        # 5. User selects provider
        if "openai" in [tab.provider_combo.itemText(i) for i in range(tab.provider_combo.count())]:
            idx = [tab.provider_combo.itemText(i) for i in range(tab.provider_combo.count())].index("openai")
            tab.provider_combo.setCurrentIndex(idx)
        
        # 6. User selects model
        if tab.model_combo.count() > 0:
            tab.model_combo.setCurrentIndex(0)
        
        # 7. Mock the actual processing
        with patch.object(tab, '_start_processing') as mock_process:
            # User clicks "Start"
            qtbot.mouseClick(tab.start_btn, Qt.MouseButton.LeftButton)
            
            # Verify processing was triggered
            assert mock_process.called
```

### Testing Conditional UI

```python
def test_proxy_mode_affects_ui(qtbot, transcription_tab):
    """Test that proxy mode selection affects cookie UI visibility."""
    # Find cookie authentication widgets
    cookie_widgets = []
    for child in transcription_tab.findChildren(QWidget):
        if 'cookie' in child.objectName().lower():
            cookie_widgets.append(child)
    
    # Change proxy mode
    for i in range(transcription_tab.proxy_mode_combo.count()):
        transcription_tab.proxy_mode_combo.setCurrentIndex(i)
        qtbot.wait(100)  # Wait for UI update
        
        # Check that UI updated (visibility, enabled state, etc.)
        # Specific checks depend on your implementation
```

### Testing Error Handling

```python
def test_error_message_shown_for_invalid_input(qtbot, tab, mock_message_box):
    """Test that error message is shown for invalid input."""
    # Try to start without files
    tab.file_list.clear()
    
    # Click start button
    qtbot.mouseClick(tab.start_btn, Qt.MouseButton.LeftButton)
    
    # Verify error message was shown
    assert mock_message_box.warning.called or mock_message_box.critical.called
```

## Continuous Integration

Add to your CI pipeline:

```yaml
# .github/workflows/gui-tests.yml
name: GUI Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
          pip install pytest-xvfb  # For headless GUI testing
      
      - name: Run GUI tests
        run: |
          pytest tests/gui/ -v --timeout=1800 --tb=short
```

## Troubleshooting

### Test Hangs

```bash
# Use timeout to prevent hanging
pytest tests/gui/ --timeout=60 -v

# Or mark specific tests
@pytest.mark.timeout(30)
def test_something():
    ...
```

### QApplication Already Exists Error

```python
# Use session-scoped fixture (already in conftest.py)
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
```

### Widget Not Found

```python
# Use ipdb to inspect
def test_something(qtbot, tab):
    breakpoint()
    # In debugger:
    p dir(tab)  # See all attributes
    p tab.findChildren(QPushButton)  # Find all buttons
```

### Signal Not Emitted

```python
# Increase timeout
with qtbot.waitSignal(signal, timeout=10000):  # 10 seconds
    trigger_action()

# Or check if signal exists
assert hasattr(widget, 'my_signal')
```

## Resources

- [pytest-qt Documentation](https://pytest-qt.readthedocs.io/)
- [pytest-timeout Documentation](https://pypi.org/project/pytest-timeout/)
- [ipdb Documentation](https://github.com/gotcha/ipdb)
- [Qt6 Documentation](https://doc.qt.io/qt-6/)

## Summary

With `pytest-qt`, `pytest-timeout`, and `ipdb`, you have a comprehensive toolkit for:

1. ✅ **Simulating user interactions** - clicks, typing, selections
2. ✅ **Testing async operations** - worker threads, signals, progress
3. ✅ **Preventing hangs** - automatic timeouts
4. ✅ **Debugging failures** - interactive debugging with ipdb
5. ✅ **Ensuring reliability** - comprehensive test coverage

Happy testing! 🎉
