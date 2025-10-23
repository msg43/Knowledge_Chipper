# Comprehensive GUI Test Plan

## Overview
This plan defines a comprehensive automated test suite that exercises every major workflow in the Knowledge Chipper GUI with real data and verifies actual outputs.

**Scope**: Full end-to-end testing of transcription and summarization workflows with real file processing.

**Timeline**: Phased implementation over multiple sessions

---

## Phase 1: Test Infrastructure Setup

### 1.1 Test Data Preparation
**Location**: `tests/fixtures/sample_files/`

Required test files:
- [ ] `sample_video.webm` - Local video file for transcription (30-60 seconds)
- [ ] `sample_audio.mp3` - Local audio file for transcription (30-60 seconds)
- [ ] `sample_transcript.md` - Markdown file with transcript for summarization
- [ ] `sample_document.pdf` - PDF document for summarization (optional)
- [ ] `youtube_urls.txt` - List of test YouTube URLs
- [ ] `rss_feeds.txt` - List of test RSS feed URLs

**Action Items**:
- Create `tests/fixtures/sample_files/` directory
- Generate or obtain short test media files
- Create sample transcript markdown
- Document test file specifications

### 1.2 Test Utilities
**Location**: `tests/gui_comprehensive/test_utils.py`

Required utilities:
- [ ] `DatabaseValidator` - Verify data written to SQLite
- [ ] `FileValidator` - Verify output files created
- [ ] `UIElementFinder` - Robust widget finding with retries
- [ ] `WorkflowExecutor` - Run complete workflows with timeouts
- [ ] `TestDataManager` - Manage test files and cleanup

**Action Items**:
- Create test utilities module
- Add database inspection methods
- Add file system validation methods
- Add UI interaction helpers

### 1.3 Mock/Test Mode Enhancements
**Location**: `src/knowledge_system/` (various files)

Required enhancements:
- [ ] Fast transcription mode (uses cached/mock results)
- [ ] Fast LLM mode (uses cached/mock results)
- [ ] Skip actual downloads (use pre-downloaded files)
- [ ] Accelerated processing timeouts

**Action Items**:
- Review existing testing mode flags
- Add fast-execution paths for tests
- Document testing mode behavior
- Ensure no actual API calls in test mode

---

## Phase 2: Transcription Workflow Tests

### 2.1 Input Type Tests
**Test File**: `tests/gui_comprehensive/test_transcribe_inputs.py`

#### Test: YouTube Video URL
```python
def test_transcribe_youtube_url():
    """Test transcribing a YouTube video URL."""
    # Given: A valid YouTube URL
    # When: Enter URL, select whisper.cpp/medium, enable diarization, start
    # Then: Download completes, transcription runs, output saved to DB and .md
```
- [ ] Valid single video URL
- [ ] Invalid/malformed URL (error handling)
- [ ] Private/unavailable video (error handling)
- [ ] Verify downloaded audio file exists
- [ ] Verify transcription in database
- [ ] Verify .md file created in output/

#### Test: YouTube Playlist URL
```python
def test_transcribe_youtube_playlist():
    """Test transcribing a YouTube playlist."""
    # Given: A playlist URL with 2-3 videos
    # When: Enter URL, select settings, start
    # Then: All videos downloaded and transcribed
```
- [ ] Valid playlist URL (2-3 videos)
- [ ] Verify each video processed
- [ ] Verify batch progress tracking
- [ ] Verify all results in database

#### Test: RSS Feed URL
```python
def test_transcribe_rss_feed():
    """Test transcribing videos from RSS feed."""
    # Given: An RSS feed URL with 2-3 videos
    # When: Enter RSS URL, start processing
    # Then: Videos extracted, downloaded, transcribed
```
- [ ] Valid RSS feed URL
- [ ] Verify feed parsing
- [ ] Verify video extraction
- [ ] Verify batch processing

#### Test: Local Audio File
```python
def test_transcribe_local_audio():
    """Test transcribing a local audio file."""
    # Given: A local .mp3 file
    # When: Select file via file picker, start transcription
    # Then: Transcription runs, output saved
```
- [ ] Local .mp3 file
- [ ] File picker simulation
- [ ] Direct file path entry
- [ ] Verify transcription output

#### Test: Local Video File
```python
def test_transcribe_local_video():
    """Test transcribing a local video file."""
    # Given: A local .webm file
    # When: Select file, start transcription
    # Then: Audio extracted, transcribed, output saved
```
- [ ] Local .webm file
- [ ] Verify audio extraction
- [ ] Verify transcription
- [ ] Verify output files

#### Test: Batch Multiple Files
```python
def test_transcribe_batch_files():
    """Test transcribing multiple files at once."""
    # Given: 2-3 local audio/video files
    # When: Add multiple files, start batch
    # Then: All files processed in sequence
```
- [ ] Add multiple files to queue
- [ ] Verify batch processing
- [ ] Verify progress tracking
- [ ] Verify all results saved

### 2.2 Provider/Model Tests
**Test File**: `tests/gui_comprehensive/test_transcribe_provider.py`

#### Test: Whisper.cpp with Medium Model
```python
def test_whisper_cpp_medium_model():
    """Test transcription with whisper.cpp and medium model."""
    # Given: A test audio file
    # When: Select whisper.cpp provider, medium model
    # Then: Transcription uses correct provider/model
```
- [ ] Verify provider selection persists
- [ ] Verify model selection persists
- [ ] Verify correct transcription engine called
- [ ] Verify model appears in metadata

### 2.3 Options Tests
**Test File**: `tests/gui_comprehensive/test_transcribe_options.py`

#### Test: Diarization Enabled
```python
def test_diarization_enabled():
    """Test transcription with speaker diarization enabled."""
    # Given: A test file with multiple speakers
    # When: Enable diarization with conservative sensitivity
    # Then: Output includes speaker labels (SPEAKER_00, SPEAKER_01)
```
- [ ] Enable diarization checkbox
- [ ] Select conservative sensitivity
- [ ] Verify speaker labels in output
- [ ] Verify diarization data in database

#### Test: English Language
```python
def test_english_language_selection():
    """Test transcription with English language specified."""
    # Given: English language audio
    # When: Select English language
    # Then: Transcription uses English model
```
- [ ] Language dropdown selection
- [ ] Verify language in settings
- [ ] Verify language in metadata

#### Test: Cookie Authentication
```python
def test_youtube_cookie_authentication():
    """Test YouTube download with cookie authentication."""
    # Given: A YouTube URL that might need cookies
    # When: Enable cookie authentication
    # Then: Download succeeds with cookies
```
- [ ] Enable cookie checkbox
- [ ] Verify cookie file used (if configured)
- [ ] Verify successful download

#### Test: Auto-Process Chain
```python
def test_auto_process_enabled():
    """Test auto-process chain (transcribe → mine → flagship)."""
    # Given: A YouTube URL
    # When: Enable auto-process, start transcription
    # Then: Transcription → mining → summarization runs automatically
```
- [ ] Enable auto-process checkbox
- [ ] Verify transcription completes
- [ ] Verify mining starts automatically
- [ ] Verify flagship summary generated
- [ ] Verify all steps saved to database

```python
def test_auto_process_disabled():
    """Test with auto-process disabled."""
    # Given: A YouTube URL
    # When: Disable auto-process, start transcription
    # Then: Only transcription runs, no automatic mining
```
- [ ] Disable auto-process checkbox
- [ ] Verify only transcription runs
- [ ] Verify no automatic follow-up processing

### 2.4 Workflow Tests
**Test File**: `tests/gui_comprehensive/test_transcribe_workflows.py`

#### Test: Complete Workflow
```python
def test_complete_transcription_workflow():
    """Test complete transcription workflow from start to finish."""
    # Given: YouTube URL
    # When: Enter URL → Select settings → Start → Wait for completion
    # Then: All steps complete, output files exist, database updated
```
- [ ] Enter YouTube URL
- [ ] Configure all settings
- [ ] Click start button
- [ ] Monitor progress
- [ ] Verify completion status
- [ ] Verify output files
- [ ] Verify database entries

#### Test: Cancel Mid-Transcription
```python
def test_cancel_transcription():
    """Test canceling transcription mid-process."""
    # Given: Transcription in progress
    # When: Click cancel button
    # Then: Process stops, partial results saved
```
- [ ] Start transcription
- [ ] Click cancel during processing
- [ ] Verify cancellation
- [ ] Verify cleanup
- [ ] Verify status updated

#### Test: Error Handling - Invalid URL
```python
def test_invalid_url_error():
    """Test error handling with invalid YouTube URL."""
    # Given: Invalid/malformed URL
    # When: Try to process
    # Then: Error message shown, process doesn't crash
```
- [ ] Enter invalid URL
- [ ] Verify validation error
- [ ] Verify error message displayed
- [ ] Verify UI remains responsive

#### Test: Error Handling - Missing File
```python
def test_missing_file_error():
    """Test error handling with non-existent file."""
    # Given: Path to non-existent file
    # When: Try to transcribe
    # Then: Error message shown, graceful failure
```
- [ ] Select non-existent file path
- [ ] Verify error handling
- [ ] Verify error message
- [ ] Verify UI remains responsive

---

## Phase 3: Summarization Workflow Tests

### 3.1 Input Type Tests
**Test File**: `tests/gui_comprehensive/test_summarize_inputs.py`

#### Test: Markdown File
```python
def test_summarize_markdown():
    """Test summarizing a markdown transcript."""
    # Given: A .md transcript file
    # When: Add file, select Ollama/Qwen2.5, start
    # Then: Summary generated, saved to DB and output/
```
- [ ] Load .md file
- [ ] Verify file appears in list
- [ ] Start summarization
- [ ] Verify output

#### Test: PDF File
```python
def test_summarize_pdf():
    """Test summarizing a PDF document."""
    # Given: A .pdf file
    # When: Add PDF, start summarization
    # Then: PDF parsed, summarized, output saved
```
- [ ] Load .pdf file
- [ ] Verify PDF parsing
- [ ] Verify summarization
- [ ] Verify output

#### Test: Text File
```python
def test_summarize_text():
    """Test summarizing a plain text file."""
    # Given: A .txt file
    # When: Add file, start
    # Then: Text processed and summarized
```
- [ ] Load .txt file
- [ ] Process and verify output

#### Test: Word Document
```python
def test_summarize_word():
    """Test summarizing a Word document."""
    # Given: A .docx file
    # When: Add file, start
    # Then: Document parsed and summarized
```
- [ ] Load .docx file
- [ ] Verify parsing
- [ ] Verify output

#### Test: Multiple Files Batch
```python
def test_summarize_batch_files():
    """Test summarizing multiple files at once."""
    # Given: 2-3 files of different types
    # When: Add all files, start batch
    # Then: All files processed
```
- [ ] Add multiple files
- [ ] Verify batch processing
- [ ] Verify all outputs

### 3.2 Provider/Model Tests
**Test File**: `tests/gui_comprehensive/test_summarize_provider.py`

#### Test: Local Ollama with Qwen2.5-7B-Instruct
```python
def test_ollama_qwen_model():
    """Test summarization with local Ollama and Qwen model."""
    # Given: Ollama service running with Qwen2.5-7B-Instruct
    # When: Select Ollama provider, Qwen model, start
    # Then: Summarization uses local Ollama
```
- [ ] Select Ollama from provider dropdown
- [ ] Select Qwen2.5-7B-Instruct from model dropdown
- [ ] Verify model selection persists
- [ ] Verify correct model used in processing
- [ ] Verify model name in output metadata

### 3.3 Prompts Tests
**Test File**: `tests/gui_comprehensive/test_summarize_prompts.py`

#### Test: Default Flagship Prompt
```python
def test_flagship_default_prompt():
    """Test flagship summarization with default prompt."""
    # Given: A transcript file
    # When: Use default flagship prompt
    # Then: Summary generated with expected sections
```
- [ ] Select flagship analysis type
- [ ] Use default prompt
- [ ] Verify output structure
- [ ] Verify expected YAML fields

#### Test: Default Mining Prompt
```python
def test_mining_default_prompt():
    """Test knowledge mining with default prompt."""
    # Given: A transcript file
    # When: Use default mining prompts
    # Then: YAML generated with Jargon, People, Mental Models
```
- [ ] Select mining analysis
- [ ] Use default prompts
- [ ] Verify YAML output
- [ ] Verify required fields present

#### Test: Custom Prompt Selection
```python
def test_custom_prompt_selection():
    """Test using a specific prompt from Prompts tab."""
    # Given: Available prompts in system
    # When: Select specific prompt, run summarization
    # Then: Selected prompt used in processing
```
- [ ] Navigate to Prompts tab
- [ ] Select specific prompt
- [ ] Return to Summarize tab
- [ ] Verify prompt selection persists
- [ ] Verify correct prompt used

### 3.4 Output Validation Tests
**Test File**: `tests/gui_comprehensive/test_summarize_outputs.py`

#### Test: SQLite Database Output
```python
def test_database_output_validation():
    """Test that summarization results are saved to database."""
    # Given: A completed summarization
    # When: Query database for results
    # Then: Data exists with correct schema
```
**Validations**:
- [ ] Job record exists in `jobs` table
- [ ] Job status is "completed"
- [ ] LLM requests recorded in `llm_requests` table
- [ ] LLM responses recorded in `llm_responses` table
- [ ] Content stored correctly
- [ ] Timestamps present and valid
- [ ] Metadata populated (model, provider, etc.)
- [ ] File paths correct
- [ ] Video/transcript IDs linked correctly

**Database Tables to Verify**:
```sql
-- Jobs table
SELECT * FROM jobs WHERE video_id = ?
  - Verify: job_type, status, input_file, output_file, created_at, completed_at

-- LLM Requests table
SELECT * FROM llm_requests WHERE job_id = ?
  - Verify: model_name, provider, prompt_text, created_at

-- LLM Responses table  
SELECT * FROM llm_responses WHERE request_id = ?
  - Verify: response_text, tokens_used, created_at

-- Check data integrity
SELECT COUNT(*) FROM jobs WHERE status = 'completed'
```

#### Test: Markdown File Output
```python
def test_markdown_file_output():
    """Test that .md output file is created with correct content."""
    # Given: A completed summarization
    # When: Check output directory
    # Then: .md file exists with expected content
```
**Validations**:
- [ ] File exists in `output/` directory
- [ ] File naming follows convention
- [ ] File contains YAML frontmatter
- [ ] YAML has required fields:
  - [ ] `title`
  - [ ] `original_file` or `video_id`
  - [ ] `model_name`
  - [ ] `provider`
  - [ ] `timestamp`
  - [ ] `processing_time`
- [ ] Content sections present:
  - [ ] Main summary
  - [ ] Jargon (if mining)
  - [ ] People (if mining)
  - [ ] Mental Models (if mining)
- [ ] Markdown formatting valid
- [ ] No malformed YAML
- [ ] File size > 0 bytes

**File Structure to Verify**:
```markdown
---
title: "Video Title"
video_id: "abc123"
model_name: "qwen2.5:7b-instruct"
provider: "ollama"
timestamp: "2025-10-21T12:00:00"
---

# Summary

[Content here]

## Jargon
[Terms here]

## People
[Names here]
```

#### Test: YAML Schema Validation
```python
def test_yaml_schema_validation():
    """Test that output YAML conforms to expected schema."""
    # Given: A completed mining run
    # When: Parse YAML from output
    # Then: Schema validation passes
```
- [ ] Load YAML from output file
- [ ] Validate against JSON schema (if applicable)
- [ ] Verify required fields present
- [ ] Verify data types correct
- [ ] Verify no extra unexpected fields

---

## Phase 4: Integration & End-to-End Tests

### 4.1 Cross-Tab Integration
**Test File**: `tests/gui_comprehensive/test_integration.py`

#### Test: Transcribe → Summarize Pipeline
```python
def test_transcribe_to_summarize_pipeline():
    """Test complete pipeline from video to summary."""
    # Given: YouTube URL
    # When: Transcribe → Navigate to Summarize → Load transcript → Summarize
    # Then: Both transcription and summary in database
```
- [ ] Transcribe video in Transcribe tab
- [ ] Switch to Summarize tab
- [ ] Load generated transcript
- [ ] Run summarization
- [ ] Verify both steps in database
- [ ] Verify both output files exist

#### Test: Auto-Process Full Chain
```python
def test_auto_process_full_chain():
    """Test complete auto-process chain."""
    # Given: YouTube URL with auto-process enabled
    # When: Start transcription
    # Then: Transcribe → Mine → Flagship all run automatically
```
- [ ] Enable auto-process
- [ ] Start with YouTube URL
- [ ] Monitor entire chain
- [ ] Verify all steps complete
- [ ] Verify all outputs exist
- [ ] Verify database has all steps

### 4.2 Monitor Tab Integration
**Test File**: `tests/gui_comprehensive/test_monitor_integration.py`

#### Test: Job Tracking
```python
def test_monitor_job_tracking():
    """Test that Monitor tab shows active jobs."""
    # Given: A processing job running
    # When: Switch to Monitor tab
    # Then: Job appears in list with progress
```
- [ ] Start a job
- [ ] Switch to Monitor tab
- [ ] Verify job appears in list
- [ ] Verify job status updates
- [ ] Verify progress indication

#### Test: Job Control
```python
def test_monitor_job_controls():
    """Test pausing/resuming/canceling from Monitor tab."""
    # Given: A job running
    # When: Use Monitor controls
    # Then: Job responds to controls
```
- [ ] Pause job from Monitor
- [ ] Verify job pauses
- [ ] Resume job
- [ ] Verify job resumes
- [ ] Cancel job
- [ ] Verify cancellation

### 4.3 Review Tab Integration
**Test File**: `tests/gui_comprehensive/test_review_integration.py`

#### Test: View Completed Results
```python
def test_review_completed_results():
    """Test viewing completed results in Review tab."""
    # Given: Completed summarization jobs
    # When: Open Review tab
    # Then: Results appear in table
```
- [ ] Complete several jobs
- [ ] Switch to Review tab
- [ ] Verify jobs appear
- [ ] Verify data columns populated
- [ ] Test filtering/sorting

#### Test: Export from Review
```python
def test_export_from_review():
    """Test exporting results from Review tab."""
    # Given: Selected results in Review
    # When: Click export
    # Then: Export file created
```
- [ ] Select results
- [ ] Click export button
- [ ] Verify export file created
- [ ] Verify export content correct

---

## Phase 5: Error Handling & Edge Cases

### 5.1 Error Handling Tests
**Test File**: `tests/gui_comprehensive/test_error_handling.py`

#### Test: Network Errors
```python
def test_network_error_handling():
    """Test handling of network failures."""
    # Given: Network unavailable
    # When: Try to download YouTube video
    # Then: Error handled gracefully
```
- [ ] Simulate network failure
- [ ] Verify error message
- [ ] Verify retry logic
- [ ] Verify UI remains responsive

#### Test: Invalid File Formats
```python
def test_invalid_file_format():
    """Test handling of unsupported file types."""
    # Given: .exe or .zip file
    # When: Try to add to processing
    # Then: Validation error shown
```
- [ ] Try invalid file types
- [ ] Verify rejection
- [ ] Verify error message

#### Test: Ollama Service Unavailable
```python
def test_ollama_unavailable():
    """Test handling when Ollama service is down."""
    # Given: Ollama not running
    # When: Try to summarize
    # Then: Clear error message shown
```
- [ ] Stop Ollama service
- [ ] Try to summarize
- [ ] Verify error detection
- [ ] Verify error message

### 5.2 Edge Case Tests
**Test File**: `tests/gui_comprehensive/test_edge_cases.py`

#### Test: Very Long File
```python
def test_very_long_transcript():
    """Test processing very long transcript (>50k tokens)."""
    # Given: Long transcript file
    # When: Summarize
    # Then: Chunking handled correctly
```
- [ ] Create/use long transcript
- [ ] Verify chunking
- [ ] Verify all chunks processed
- [ ] Verify output complete

#### Test: Special Characters
```python
def test_special_characters_in_filenames():
    """Test files with special characters in names."""
    # Given: File with unicode/special chars
    # When: Process file
    # Then: Handled correctly
```
- [ ] Files with unicode
- [ ] Files with spaces
- [ ] Files with special chars
- [ ] Verify proper handling

#### Test: Concurrent Operations
```python
def test_concurrent_processing():
    """Test running multiple jobs simultaneously."""
    # Given: Multiple files queued
    # When: Process concurrently
    # Then: All complete without conflicts
```
- [ ] Queue multiple jobs
- [ ] Verify concurrent execution
- [ ] Verify no resource conflicts
- [ ] Verify all outputs correct

---

## Phase 6: Performance & Stability

### 6.1 Performance Tests
**Test File**: `tests/gui_comprehensive/test_performance.py`

#### Test: UI Responsiveness
```python
def test_ui_remains_responsive():
    """Test that UI doesn't freeze during processing."""
    # Given: Heavy processing running
    # When: Interact with UI
    # Then: UI responds within 100ms
```
- [ ] Start heavy processing
- [ ] Test button clicks
- [ ] Test tab switching
- [ ] Verify responsiveness

#### Test: Memory Usage
```python
def test_memory_usage_reasonable():
    """Test that memory usage stays within bounds."""
    # Given: Multiple files processing
    # When: Monitor memory
    # Then: Usage < 2GB
```
- [ ] Monitor memory during tests
- [ ] Verify no memory leaks
- [ ] Verify cleanup after jobs

### 6.2 Stability Tests
**Test File**: `tests/gui_comprehensive/test_stability.py`

#### Test: Repeated Operations
```python
def test_repeated_transcriptions():
    """Test stability with repeated operations."""
    # Given: Same workflow repeated 10 times
    # When: Run repeatedly
    # Then: No degradation or crashes
```
- [ ] Repeat workflow 10 times
- [ ] Verify stability
- [ ] Verify consistent results

#### Test: Long Running Session
```python
def test_long_running_session():
    """Test GUI stability over extended session."""
    # Given: GUI running for extended time
    # When: Process many jobs
    # Then: No crashes or slowdowns
```
- [ ] Run session for 30+ minutes
- [ ] Process many files
- [ ] Verify stability

---

## Test Execution Strategy

### Test Organization
```
tests/
├── gui_comprehensive/
│   ├── test_transcribe_inputs.py      (Phase 2.1)
│   ├── test_transcribe_provider.py    (Phase 2.2)
│   ├── test_transcribe_options.py     (Phase 2.3)
│   ├── test_transcribe_workflows.py   (Phase 2.4)
│   ├── test_summarize_inputs.py       (Phase 3.1)
│   ├── test_summarize_provider.py     (Phase 3.2)
│   ├── test_summarize_prompts.py      (Phase 3.3)
│   ├── test_summarize_outputs.py      (Phase 3.4)
│   ├── test_integration.py            (Phase 4)
│   ├── test_error_handling.py         (Phase 5.1)
│   ├── test_edge_cases.py             (Phase 5.2)
│   ├── test_performance.py            (Phase 6.1)
│   └── test_stability.py              (Phase 6.2)
├── fixtures/
│   └── sample_files/
│       ├── sample_video.webm
│       ├── sample_audio.mp3
│       ├── sample_transcript.md
│       ├── youtube_urls.txt
│       └── rss_feeds.txt
└── tools/
    ├── test_utils.py
    ├── database_validator.py
    ├── file_validator.py
    └── workflow_executor.py
```

### Running Tests

#### Quick Smoke Test (5 minutes)
```bash
pytest tests/gui_comprehensive/test_transcribe_workflows.py::test_complete_transcription_workflow
pytest tests/gui_comprehensive/test_summarize_outputs.py::test_database_output_validation
```

#### Full Transcription Suite (30 minutes)
```bash
pytest tests/gui_comprehensive/test_transcribe_*.py -v
```

#### Full Summarization Suite (30 minutes)
```bash
pytest tests/gui_comprehensive/test_summarize_*.py -v
```

#### Complete Test Suite (2-3 hours)
```bash
pytest tests/gui_comprehensive/ -v --timeout=300
```

#### Nightly Regression (run overnight)
```bash
pytest tests/gui_comprehensive/ -v --timeout=600 --count=3
```

---

## Success Criteria

### Per-Test Success
- [ ] Test passes without errors
- [ ] UI interactions work as expected
- [ ] Output files created in correct locations
- [ ] Database entries validated
- [ ] No UI freezes or crashes
- [ ] Cleanup successful (no temp files left)

### Phase Completion
- [ ] All tests in phase passing
- [ ] Code coverage > 80% for tested features
- [ ] No critical bugs found
- [ ] Performance within acceptable bounds
- [ ] Documentation updated

### Overall Success
- [ ] 95%+ test pass rate
- [ ] All input types tested
- [ ] All workflows tested
- [ ] Database validation working
- [ ] File validation working
- [ ] Error handling verified
- [ ] CI/CD integration complete

---

## Implementation Timeline

### Week 1: Infrastructure
- Day 1-2: Test data preparation
- Day 3-4: Test utilities creation
- Day 5: Fast-execution mode setup

### Week 2: Transcription Tests
- Day 1-2: Input type tests
- Day 3: Provider/model tests
- Day 4: Options tests
- Day 5: Workflow tests

### Week 3: Summarization Tests
- Day 1-2: Input type tests
- Day 3: Provider/model tests
- Day 4: Prompts tests
- Day 5: Output validation tests

### Week 4: Integration & Stability
- Day 1-2: Integration tests
- Day 3: Error handling tests
- Day 4: Edge case tests
- Day 5: Performance & stability tests

### Week 5: Refinement
- Day 1-3: Bug fixes from test results
- Day 4: Documentation
- Day 5: CI/CD setup and verification

---

## Test Data Requirements

### Provide for Testing

1. **YouTube URL** (public, short video, 1-2 minutes):
   - Example: Educational or public domain content
   - Should have multiple speakers for diarization testing

2. **RSS Feed URL** (with 2-3 videos):
   - Example: Podcast or video channel RSS

3. **Local Video File** (.webm, 30-60 seconds):
   - Path: `tests/fixtures/sample_files/sample_video.webm`
   - Requirements: Clear audio, 1-2 speakers

4. **Local Audio File** (.mp3, 30-60 seconds):
   - Path: `tests/fixtures/sample_files/sample_audio.mp3`

5. **Sample Transcript** (.md file):
   - Path: `tests/fixtures/sample_files/sample_transcript.md`
   - Requirements: ~1000-2000 words, realistic content

6. **Sample PDF** (optional):
   - Path: `tests/fixtures/sample_files/sample_document.pdf`

---

## Maintenance Plan

### Regular Test Runs
- **Before each commit**: Smoke tests (5 min)
- **Before each PR**: Full suite (2-3 hours)
- **Nightly**: Complete suite with repeats
- **Weekly**: Performance benchmarks

### Test Updates
- Update tests when features change
- Add tests for bug fixes
- Expand tests for new features
- Review and refactor monthly

### Metrics Tracking
- Test pass rate over time
- Code coverage trends
- Performance benchmarks
- Bug detection rate

---

## Notes

### Testing Mode Behavior
When `KNOWLEDGE_CHIPPER_TESTING_MODE=1`:
- API calls should be mocked or use cached responses
- File downloads use pre-downloaded test files
- Processing times accelerated
- No actual Ollama API calls (use mock responses)
- Database uses test database or isolated schema

### Known Limitations
- Cannot test actual Ollama responses (would require running service)
- YouTube downloads limited by rate limiting
- Some tests may be flaky due to timing
- GUI tests require stable environment

### Future Enhancements
- Add visual regression testing (screenshot comparison)
- Add accessibility testing
- Add localization testing
- Add cross-platform testing (Windows, Linux)
- Add load testing with many concurrent users

