# Workflow Testing Guide

Complete guide to testing end-to-end user workflows in the Knowledge Chipper GUI.

## Overview

Workflow tests simulate complete user journeys from start to finish, testing how multiple components work together. Unlike unit tests that test individual functions, workflow tests verify that entire features work as users expect.

## Table of Contents

1. [What Are Workflow Tests?](#what-are-workflow-tests)
2. [Available Workflows](#available-workflows)
3. [Running Workflow Tests](#running-workflow-tests)
4. [Writing New Workflows](#writing-new-workflows)
5. [Best Practices](#best-practices)
6. [Examples](#examples)

## What Are Workflow Tests?

**Workflow tests** simulate complete user interactions across multiple steps:

```python
# Example: Complete transcription workflow
def test_transcribe_audio_workflow(qtbot, tab):
    """Simulate user transcribing an audio file."""
    # Step 1: User adds file
    add_file(tab, "audio.mp3")
    
    # Step 2: User selects model
    select_model(tab, "base")
    
    # Step 3: User enables diarization
    enable_diarization(tab)
    
    # Step 4: User starts transcription
    click_start(tab)
    
    # Step 5: Verify completion
    wait_for_completion(tab)
    assert transcript_created()
```

### Workflow vs Unit Tests

| Aspect | Unit Tests | Workflow Tests |
|--------|-----------|----------------|
| **Scope** | Single function/method | Complete user journey |
| **Duration** | Milliseconds | Seconds to minutes |
| **Dependencies** | Mocked | Partially real |
| **Purpose** | Verify logic | Verify user experience |
| **Example** | `test_parse_url()` | `test_transcribe_youtube_video()` |

## Available Workflows

### Transcription Workflows

Located in `test_user_workflows.py::TestTranscriptionWorkflows`

#### 1. Transcribe Local Audio File
```bash
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_local_audio_file -v
```

**Simulates:**
1. User clicks "Add Files"
2. Selects an audio file
3. Chooses transcription model
4. Enables speaker diarization
5. Clicks "Start Transcription"

**Tests:**
- File selection works
- Model selection persists
- Diarization checkbox toggles
- Processing starts correctly

#### 2. Transcribe YouTube URL
```bash
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_youtube_url -v
```

**Simulates:**
1. User enters YouTube URL
2. Selects model and options
3. Configures proxy settings
4. Starts download and transcription

**Tests:**
- URL input validation
- Proxy mode selection
- YouTube download initiation

#### 3. Batch Transcribe Multiple Files
```bash
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_batch_transcribe_multiple_files -v
```

**Simulates:**
1. User selects multiple audio files
2. Enables auto-process checkbox
3. Starts batch transcription

**Tests:**
- Multiple file selection
- Batch processing configuration
- Auto-process pipeline

### Summarization Workflows

Located in `test_user_workflows.py::TestSummarizationWorkflows`

#### 1. Summarize Single Transcript
```bash
pytest tests/gui/test_user_workflows.py::TestSummarizationWorkflows::test_summarize_single_transcript -v
```

**Simulates:**
1. User adds transcript file
2. Selects AI provider (OpenAI, Anthropic, Ollama)
3. Chooses model
4. Selects content type (Unified HCE, etc.)
5. Adjusts max claims
6. Starts analysis

**Tests:**
- File selection
- Provider/model selection
- Content type configuration
- Analysis initiation

#### 2. Batch Summarize Folder
```bash
pytest tests/gui/test_user_workflows.py::TestSummarizationWorkflows::test_batch_summarize_folder -v
```

**Simulates:**
1. User selects folder with multiple transcripts
2. Configures batch settings
3. Starts batch analysis

**Tests:**
- Folder selection
- Multiple file handling
- Batch analysis

#### 3. Change Analysis Template
```bash
pytest tests/gui/test_user_workflows.py::TestSummarizationWorkflows::test_change_analysis_template -v
```

**Simulates:**
1. User changes content type
2. Template path updates automatically
3. User manually edits template path

**Tests:**
- Content type selection
- Template auto-update
- Manual template editing

### Complete User Journeys

Located in `test_user_workflows.py::TestCompleteUserJourneys`

#### 1. Transcribe → Summarize Workflow
```bash
pytest tests/gui/test_user_workflows.py::TestCompleteUserJourneys::test_complete_transcribe_to_summarize_workflow -v
```

**Simulates:**
1. User transcribes audio file
2. Waits for completion
3. Switches to Summarize tab
4. Selects the transcript
5. Runs analysis
6. Reviews results

**Tests:**
- Cross-tab workflow
- File handoff between tabs
- Complete pipeline

#### 2. Settings Change Workflow
```bash
pytest tests/gui/test_user_workflows.py::TestCompleteUserJourneys::test_settings_change_workflow -v
```

**Simulates:**
1. User opens Settings tab
2. Enters API key
3. Changes default model
4. Saves settings

**Tests:**
- Settings persistence
- API key entry
- Model configuration

### Monitor Workflows

Located in `test_user_workflows.py::TestMonitorWorkflows`

#### 1. Setup Folder Monitoring
```bash
pytest tests/gui/test_user_workflows.py::TestMonitorWorkflows::test_setup_folder_monitoring -v
```

**Simulates:**
1. User selects folder to watch
2. Configures file patterns (*.mp3, *.mp4)
3. Enables auto-processing
4. Starts monitoring

**Tests:**
- Folder selection
- Pattern configuration
- Monitor activation

### Error Handling Workflows

Located in `test_user_workflows.py::TestErrorHandlingWorkflows`

#### 1. Start Without Files
```bash
pytest tests/gui/test_user_workflows.py::TestErrorHandlingWorkflows::test_start_without_files_shows_error -v
```

**Simulates:**
- User tries to start processing without selecting files

**Tests:**
- Error message displayed
- Graceful failure

#### 2. Invalid URL Handling
```bash
pytest tests/gui/test_user_workflows.py::TestErrorHandlingWorkflows::test_invalid_url_handling -v
```

**Simulates:**
- User enters invalid YouTube URL

**Tests:**
- URL validation
- Error handling

## Running Workflow Tests

### Run All Workflows

```bash
# Run complete workflow test suite
pytest tests/gui/test_user_workflows.py -v --timeout=300

# Run with detailed output
pytest tests/gui/test_user_workflows.py -v --timeout=300 -s

# Run and stop on first failure
pytest tests/gui/test_user_workflows.py -v --timeout=300 -x
```

### Run Specific Category

```bash
# Run only transcription workflows
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows -v

# Run only summarization workflows
pytest tests/gui/test_user_workflows.py::TestSummarizationWorkflows -v

# Run only complete journeys
pytest tests/gui/test_user_workflows.py::TestCompleteUserJourneys -v
```

### Run Specific Workflow

```bash
# Run single workflow test
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_local_audio_file -v

# With debugging
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_local_audio_file -v --pdb
```

### Run with Custom Timeout

```bash
# Increase timeout for slow machines
pytest tests/gui/test_user_workflows.py -v --timeout=600

# Decrease for fast feedback
pytest tests/gui/test_user_workflows.py -v --timeout=120
```

## Writing New Workflows

### Template

```python
@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
@pytest.mark.integration
class TestMyWorkflows:
    """Test my custom workflows."""
    
    @pytest.fixture
    def my_tab(self, qtbot):
        """Create tab for testing."""
        from knowledge_system.gui.tabs.my_tab import MyTab
        
        tab = MyTab()
        qtbot.addWidget(tab)
        return tab
    
    @pytest.mark.timeout(60)
    def test_my_workflow(self, qtbot, my_tab, tmp_path):
        """
        Simulate: User does X, Y, and Z
        
        Workflow:
        1. User action 1
        2. User action 2
        3. User action 3
        4. Verify result
        """
        # Step 1: Setup
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        # Step 2: User action
        qtbot.mouseClick(my_tab.button, Qt.MouseButton.LeftButton)
        qtbot.wait(100)
        
        # Step 3: Verify
        assert my_tab.state_changed
```

### Step-by-Step Guide

#### 1. Identify the Workflow

Ask yourself:
- What is the user trying to accomplish?
- What steps do they take?
- What should happen at each step?

Example: "User wants to transcribe a YouTube video"

#### 2. Break Down into Steps

```python
"""
Workflow: Transcribe YouTube Video

1. User opens Transcribe tab
2. User enters YouTube URL
3. User selects model (e.g., "base")
4. User clicks "Start Transcription"
5. System downloads video
6. System transcribes audio
7. User sees completion message
"""
```

#### 3. Write the Test

```python
@pytest.mark.timeout(60)
def test_transcribe_youtube_video(self, qtbot, transcription_tab):
    """Simulate: User transcribes YouTube video."""
    
    # Step 1: User enters URL
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    qtbot.keyClicks(transcription_tab.url_input, test_url)
    
    # Step 2: User selects model
    transcription_tab.model_combo.setCurrentText("base")
    
    # Step 3: Mock the actual processing
    with patch.object(transcription_tab, '_start_processing') as mock:
        # User clicks start
        qtbot.mouseClick(transcription_tab.start_btn, Qt.MouseButton.LeftButton)
        
        # Verify processing started
        assert mock.called
```

#### 4. Add Mocking

Mock expensive operations:

```python
# Mock file dialog
with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileNames') as mock_dialog:
    mock_dialog.return_value = (["/path/to/file.txt"], "")
    qtbot.mouseClick(tab.add_files_btn, Qt.MouseButton.LeftButton)

# Mock message boxes
with patch('PyQt6.QtWidgets.QMessageBox.information') as mock_msg:
    qtbot.mouseClick(tab.button, Qt.MouseButton.LeftButton)
    assert mock_msg.called

# Mock processing
with patch.object(tab, '_start_processing') as mock_process:
    qtbot.mouseClick(tab.start_btn, Qt.MouseButton.LeftButton)
    assert mock_process.called
```

#### 5. Add Assertions

Verify each step:

```python
# Verify file was added
assert tab.file_list.count() == 1

# Verify selection changed
assert tab.provider_combo.currentText() == "openai"

# Verify processing started
assert mock_process.called

# Verify state changed
assert tab.is_processing == True
```

## Best Practices

### 1. Test Real User Paths

✅ **Good** - Tests what users actually do:
```python
def test_user_transcribes_podcast(qtbot, tab):
    """User downloads and transcribes a podcast episode."""
    # 1. Enter podcast URL
    # 2. Select model
    # 3. Enable diarization (for multiple speakers)
    # 4. Start transcription
```

❌ **Bad** - Tests implementation details:
```python
def test_internal_method(qtbot, tab):
    """Test _internal_helper_method()."""
    tab._internal_helper_method()  # Users don't call this
```

### 2. Use Descriptive Names

✅ **Good**:
```python
def test_user_can_batch_transcribe_folder_of_audio_files(qtbot, tab):
    ...
```

❌ **Bad**:
```python
def test_batch(qtbot, tab):
    ...
```

### 3. Document the Workflow

```python
def test_my_workflow(qtbot, tab):
    """
    Simulate: User does X to accomplish Y
    
    Workflow:
    1. User action 1
    2. User action 2
    3. Expected result
    
    Tests:
    - Feature A works
    - Feature B integrates with A
    - Error handling for edge case C
    """
```

### 4. Mock External Dependencies

```python
# Mock network calls
with patch('requests.get'):
    ...

# Mock file system
with patch('pathlib.Path.exists', return_value=True):
    ...

# Mock expensive operations
with patch.object(tab, '_run_whisper'):
    ...
```

### 5. Use Appropriate Timeouts

```python
# Fast UI interactions
@pytest.mark.timeout(10)
def test_button_click_workflow(qtbot, tab):
    ...

# File processing
@pytest.mark.timeout(60)
def test_transcribe_workflow(qtbot, tab):
    ...

# Complete pipelines
@pytest.mark.timeout(300)
def test_end_to_end_workflow(qtbot, tab):
    ...
```

### 6. Clean Up Properly

```python
def test_workflow(qtbot, tab, tmp_path):
    """Test using temporary files."""
    # Use tmp_path - automatically cleaned up
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    
    # Use qtbot.addWidget - automatically cleaned up
    qtbot.addWidget(tab)
    
    # No manual cleanup needed!
```

## Examples

### Example 1: Simple Workflow

```python
@pytest.mark.timeout(30)
def test_user_adds_and_removes_file(self, qtbot, tab, tmp_path):
    """User adds a file then removes it."""
    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    
    # User adds file
    with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileNames') as mock:
        mock.return_value = ([str(test_file)], "")
        qtbot.mouseClick(tab.add_files_btn, Qt.MouseButton.LeftButton)
    
    # Verify file added
    assert tab.file_list.count() == 1
    
    # User removes file
    tab.file_list.setCurrentRow(0)
    qtbot.mouseClick(tab.remove_file_btn, Qt.MouseButton.LeftButton)
    
    # Verify file removed
    assert tab.file_list.count() == 0
```

### Example 2: Multi-Step Workflow

```python
@pytest.mark.timeout(60)
def test_complete_analysis_workflow(self, qtbot, tab, tmp_path):
    """User performs complete analysis workflow."""
    # Step 1: Add transcript
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("Speaker 1: Important claim here.")
    
    with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileNames') as mock:
        mock.return_value = ([str(transcript)], "")
        qtbot.mouseClick(tab.add_files_btn, Qt.MouseButton.LeftButton)
    
    # Step 2: Select provider
    tab.provider_combo.setCurrentText("ollama")
    qtbot.wait(100)  # Wait for model list to update
    
    # Step 3: Select model
    if tab.model_combo.count() > 0:
        tab.model_combo.setCurrentIndex(0)
    
    # Step 4: Configure options
    tab.max_claims_spin.setValue(50)
    
    # Step 5: Start analysis (mocked)
    with patch.object(tab, '_start_processing') as mock_process:
        qtbot.mouseClick(tab.start_btn, Qt.MouseButton.LeftButton)
        assert mock_process.called
```

### Example 3: Cross-Tab Workflow

```python
@pytest.mark.timeout(120)
def test_transcribe_then_summarize(self, qtbot, tmp_path):
    """User transcribes then summarizes in one session."""
    from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab
    from knowledge_system.gui.tabs.summarization_tab import SummarizationTab
    
    # Part 1: Transcription
    trans_tab = TranscriptionTab()
    qtbot.addWidget(trans_tab)
    
    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake audio")
    
    with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileNames') as mock:
        mock.return_value = ([str(audio_file)], "")
        qtbot.mouseClick(trans_tab.add_files_btn, Qt.MouseButton.LeftButton)
    
    with patch.object(trans_tab, '_start_processing'):
        qtbot.mouseClick(trans_tab.start_btn, Qt.MouseButton.LeftButton)
    
    # Part 2: Summarization (using transcript from part 1)
    summ_tab = SummarizationTab()
    qtbot.addWidget(summ_tab)
    
    transcript = tmp_path / "audio_transcript.txt"
    transcript.write_text("Transcribed content")
    
    with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileNames') as mock:
        mock.return_value = ([str(transcript)], "")
        qtbot.mouseClick(summ_tab.add_files_btn, Qt.MouseButton.LeftButton)
    
    with patch.object(summ_tab, '_start_processing'):
        qtbot.mouseClick(summ_tab.start_btn, Qt.MouseButton.LeftButton)
```

## Troubleshooting

### Workflow Test Hangs

```bash
# Increase timeout
pytest tests/gui/test_user_workflows.py -v --timeout=600

# Or add to specific test
@pytest.mark.timeout(600)
def test_slow_workflow():
    ...
```

### Mock Not Working

```python
# Make sure to patch the right location
# Bad: Patches wrong module
with patch('module_a.function'):
    ...

# Good: Patches where it's used
with patch('module_b.function'):  # module_b imports from module_a
    ...
```

### Signal Not Emitted

```python
# Increase wait time
with qtbot.waitSignal(signal, timeout=10000):  # 10 seconds
    trigger_action()

# Or check if signal exists
assert hasattr(widget, 'my_signal')
```

## Summary

Workflow tests provide:

1. ✅ **User perspective** - Tests match real usage
2. ✅ **Integration testing** - Verifies components work together
3. ✅ **Regression prevention** - Catches breaking changes
4. ✅ **Documentation** - Shows how features should work
5. ✅ **Confidence** - Proves the app works end-to-end

**Next Steps:**
1. Run existing workflows: `pytest tests/gui/test_user_workflows.py -v`
2. Review examples in the test file
3. Write workflows for your new features
4. Keep workflows updated as features change

Happy testing! 🎉
