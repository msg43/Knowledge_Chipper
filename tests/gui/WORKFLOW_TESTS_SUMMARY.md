# Workflow Tests Summary

Quick reference for all available workflow tests.

## Overview

Workflow tests simulate complete user journeys from start to finish. They test how users actually interact with the application, not just individual components.

## Quick Start

```bash
# Run all workflow tests
pytest tests/gui/test_user_workflows.py -v --timeout=300

# Run specific category
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows -v

# Run specific workflow
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_local_audio_file -v
```

## Available Workflows

### 🎙️ Transcription Workflows (3 tests)

| Test | Description | Duration |
|------|-------------|----------|
| `test_transcribe_local_audio_file` | User transcribes local audio with diarization | ~30s |
| `test_transcribe_youtube_url` | User downloads and transcribes YouTube video | ~30s |
| `test_batch_transcribe_multiple_files` | User batch processes 3+ audio files | ~30s |

**Run all:**
```bash
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows -v
```

### 📝 Summarization Workflows (3 tests)

| Test | Description | Duration |
|------|-------------|----------|
| `test_summarize_single_transcript` | User analyzes single transcript with HCE | ~30s |
| `test_batch_summarize_folder` | User batch analyzes folder of 5+ transcripts | ~30s |
| `test_change_analysis_template` | User changes content type and template | ~10s |

**Run all:**
```bash
pytest tests/gui/test_user_workflows.py::TestSummarizationWorkflows -v
```

### 🔄 Complete User Journeys (2 tests)

| Test | Description | Duration |
|------|-------------|----------|
| `test_complete_transcribe_to_summarize_workflow` | Full pipeline: Audio → Transcript → Analysis | ~60s |
| `test_settings_change_workflow` | User changes API keys and settings | ~20s |

**Run all:**
```bash
pytest tests/gui/test_user_workflows.py::TestCompleteUserJourneys -v
```

### 👁️ Monitor Workflows (1 test)

| Test | Description | Duration |
|------|-------------|----------|
| `test_setup_folder_monitoring` | User sets up auto-processing folder watch | ~20s |

**Run all:**
```bash
pytest tests/gui/test_user_workflows.py::TestMonitorWorkflows -v
```

### ⚠️ Error Handling Workflows (2 tests)

| Test | Description | Duration |
|------|-------------|----------|
| `test_start_without_files_shows_error` | User tries to start without selecting files | ~10s |
| `test_invalid_url_handling` | User enters invalid YouTube URL | ~10s |

**Run all:**
```bash
pytest tests/gui/test_user_workflows.py::TestErrorHandlingWorkflows -v
```

## Total Coverage

- **11 workflow tests** covering major user interactions
- **~5 minutes** to run complete suite
- **15+ user scenarios** tested end-to-end

## Common Commands

### Run by Speed

```bash
# Fast tests only (<30s)
pytest tests/gui/test_user_workflows.py -v -m "not slow"

# All tests including slow ones
pytest tests/gui/test_user_workflows.py -v --timeout=300
```

### Run by Feature

```bash
# Transcription features
pytest tests/gui/test_user_workflows.py -k "transcribe" -v

# Summarization features
pytest tests/gui/test_user_workflows.py -k "summarize" -v

# Error handling
pytest tests/gui/test_user_workflows.py -k "error" -v
```

### Debug Specific Workflow

```bash
# Run with debugger
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_local_audio_file --pdb

# Run with verbose output
pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_local_audio_file -v -s
```

## What Each Workflow Tests

### Transcribe Local Audio File
✅ File selection dialog  
✅ Model selection dropdown  
✅ Diarization checkbox toggle  
✅ Processing initiation  
✅ File list management  

### Transcribe YouTube URL
✅ URL input field  
✅ URL validation  
✅ Proxy mode selection  
✅ Download initiation  
✅ Settings integration  

### Batch Transcribe
✅ Multiple file selection  
✅ Batch processing configuration  
✅ Auto-process checkbox  
✅ Progress tracking  
✅ File queue management  

### Summarize Single Transcript
✅ Transcript file selection  
✅ AI provider selection  
✅ Model selection  
✅ Content type selection  
✅ Max claims configuration  
✅ Analysis initiation  

### Batch Summarize Folder
✅ Folder selection  
✅ Multiple file handling  
✅ Batch configuration  
✅ Progress tracking  
✅ Result aggregation  

### Change Analysis Template
✅ Content type dropdown  
✅ Template path auto-update  
✅ Manual template editing  
✅ Template validation  

### Complete Transcribe → Summarize
✅ Cross-tab workflow  
✅ File handoff between tabs  
✅ State persistence  
✅ Complete pipeline  
✅ Result verification  

### Settings Change
✅ API key entry  
✅ Settings persistence  
✅ Model configuration  
✅ Settings validation  

### Setup Folder Monitoring
✅ Folder selection  
✅ Pattern configuration  
✅ Auto-process setup  
✅ Monitor activation  

### Error Handling
✅ Empty file list validation  
✅ Invalid URL detection  
✅ Error message display  
✅ Graceful failure  

## Adding New Workflows

1. **Identify the workflow**: What does the user want to accomplish?
2. **Break into steps**: What actions do they take?
3. **Write the test**: Simulate each step with qtbot
4. **Add mocking**: Mock expensive operations
5. **Add assertions**: Verify each step works

Example:
```python
@pytest.mark.timeout(60)
def test_my_new_workflow(self, qtbot, tab, tmp_path):
    """Simulate: User does X to accomplish Y."""
    # Step 1: Setup
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    
    # Step 2: User action
    with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileNames') as mock:
        mock.return_value = ([str(test_file)], "")
        qtbot.mouseClick(tab.add_files_btn, Qt.MouseButton.LeftButton)
    
    # Step 3: Verify
    assert tab.file_list.count() == 1
```

See `docs/WORKFLOW_TESTING_GUIDE.md` for complete guide.

## Resources

- **Full Guide**: `docs/WORKFLOW_TESTING_GUIDE.md`
- **Test File**: `tests/gui/test_user_workflows.py`
- **Examples**: `tests/gui/EXAMPLE_TEST.py`
- **Quick Reference**: `tests/gui/README.md`

## Troubleshooting

### Test Hangs
```bash
# Increase timeout
pytest tests/gui/test_user_workflows.py -v --timeout=600
```

### Test Fails
```bash
# Run with debugger
pytest tests/gui/test_user_workflows.py::test_name --pdb

# Run with verbose output
pytest tests/gui/test_user_workflows.py::test_name -v -s
```

### Need to Skip Test
```python
@pytest.mark.skip(reason="Temporarily disabled")
def test_something():
    ...
```

## Success Metrics

After running workflow tests, you should see:

```
tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_local_audio_file PASSED
tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_youtube_url PASSED
tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_batch_transcribe_multiple_files PASSED
tests/gui/test_user_workflows.py::TestSummarizationWorkflows::test_summarize_single_transcript PASSED
tests/gui/test_user_workflows.py::TestSummarizationWorkflows::test_batch_summarize_folder PASSED
tests/gui/test_user_workflows.py::TestSummarizationWorkflows::test_change_analysis_template PASSED
tests/gui/test_user_workflows.py::TestCompleteUserJourneys::test_complete_transcribe_to_summarize_workflow PASSED
tests/gui/test_user_workflows.py::TestCompleteUserJourneys::test_settings_change_workflow PASSED
tests/gui/test_user_workflows.py::TestMonitorWorkflows::test_setup_folder_monitoring PASSED
tests/gui/test_user_workflows.py::TestErrorHandlingWorkflows::test_start_without_files_shows_error PASSED
tests/gui/test_user_workflows.py::TestErrorHandlingWorkflows::test_invalid_url_handling PASSED

====== 11 passed in 3.45s ======
```

## Next Steps

1. ✅ Run workflow tests: `pytest tests/gui/test_user_workflows.py -v`
2. ✅ Review test file to understand patterns
3. ✅ Add workflows for new features as you build them
4. ✅ Keep workflows updated when UI changes

Happy testing! 🚀
