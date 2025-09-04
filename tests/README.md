# Knowledge Chipper GUI Comprehensive Testing

This directory contains a comprehensive automated testing framework for the Knowledge Chipper GUI that validates every permutation of input types, GUI tabs, and processing operations.

## Quick Start

### 1. Install Dependencies

Ensure you have the testing dependencies installed:

```bash
pip install pytest PyQt6 pyyaml
```

### 2. Prepare Sample Files

You need to provide sample test files as outlined in the plan. See `tests/fixtures/sample_files/README.md` for detailed requirements.

**Required Sample Files:**
- Audio files: MP3, WAV, M4A, FLAC, OGG, AAC (various sizes)
- Video files: MP4, WEBM, AVI, MOV, MKV (various sizes)  
- Document files: PDF, TXT, MD, DOCX, DOC, RTF, HTML (various complexities)
- URL test cases: YouTube URLs, RSS feeds, web pages (in text files)

### 3. Run Tests

```bash
# Quick smoke tests (5-10 minutes)
python -m tests.gui_comprehensive.main_test_runner smoke

# Basic functionality tests (30 minutes)  
python -m tests.gui_comprehensive.main_test_runner basic

# Comprehensive testing (1-2 hours)
python -m tests.gui_comprehensive.main_test_runner comprehensive

# Stress testing (2+ hours)
python -m tests.gui_comprehensive.main_test_runner stress

# Run all test suites
python -m tests.gui_comprehensive.main_test_runner all
```

## Framework Components

### Core Framework (`gui_comprehensive/`)

- **`test_framework.py`** - Base testing infrastructure and test result management
- **`gui_automation.py`** - PyQt6 GUI interaction automation
- **`validation.py`** - Output validation and quality assessment
- **`test_orchestrator.py`** - Test coordination and execution management
- **`main_test_runner.py`** - Command-line interface for running tests

### Test Data (`fixtures/`)

- **`sample_files/`** - Test input files organized by type
- **`test_configs/`** - YAML configuration files for different test scenarios
- **`expected_outputs/`** - Known good results for validation

### Test Reports (`reports/`)

- **`test_results/`** - Detailed test execution results
- **`performance/`** - Performance benchmarking data
- **`coverage/`** - Test coverage reports

## Test Coverage

### Input Types Tested
- **Audio**: MP3, WAV, M4A, FLAC, OGG, AAC
- **Video**: MP4, WEBM, AVI, MOV, MKV
- **Documents**: PDF, TXT, MD, DOCX, DOC, RTF, HTML, HTM
- **URLs**: YouTube videos/playlists, RSS feeds, web pages

### GUI Tabs Tested
- Introduction Tab
- Process Pipeline Tab
- File Watcher Tab  
- YouTube Tab
- Transcription Tab
- Summarization Tab
- Claim Search Tab
- Speaker Attribution Tab
- Summary Cleanup Tab
- API Keys Tab
- Sync Status Tab

### Operations Tested
- Transcription only
- Summarization only
- Full pipeline (transcribe → summarize → MOC)
- MOC generation
- Batch processing
- Speaker diarization
- Error recovery

## Test Modes

### Smoke Tests (5-10 minutes)
Quick validation of core functionality with small files.

### Basic Tests (30 minutes)  
Standard functionality testing with medium files.

### Comprehensive Tests (1-2 hours)
Full permutation testing across all input types, tabs, and operations.

### Stress Tests (2+ hours)
Large files, high-volume processing, and challenging scenarios.

## Configuration

Test behavior is controlled by YAML configuration files:

- **`basic_config.yaml`** - Quick testing with small files
- **`comprehensive_config.yaml`** - Full coverage testing
- **`stress_config.yaml`** - Stress testing configuration

Example configuration:
```yaml
test_suite: comprehensive
timeout: 1800  # 30 minutes per test
file_size_limit_mb: 100
operations:
  - transcribe_only
  - summarize_only
  - full_pipeline
tabs:
  - Process Pipeline
  - Local Transcription  
  - Summarization
```

## Sample File Organization

```
tests/fixtures/sample_files/
├── audio/
│   ├── short_speech_30s.mp3        # Quick tests
│   ├── interview_10min.flac        # Standard tests
│   └── conference_talk_30min.wav   # Stress tests
├── video/
│   ├── tutorial_3min.mp4           # Quick tests
│   ├── webinar_10min.mp4           # Standard tests
│   └── full_lecture_45min.mp4      # Stress tests
├── documents/
│   ├── blog_post.md                # Simple documents
│   ├── research_paper.pdf          # Complex documents
│   └── large_manual_100pages.pdf   # Stress tests
└── urls/
    ├── youtube_test_urls.txt        # YouTube URLs
    ├── rss_test_feeds.txt           # RSS feeds
    └── web_test_urls.txt            # Web pages
```

## Validation Criteria

The framework validates:

### File Processing
- Expected output files are created
- Output files have correct formats and extensions
- Content quality meets minimum standards
- Processing completes within expected time limits

### Content Quality
- Transcripts have minimum length and readability
- Summaries contain required sections
- MOCs include expected categories (People, Jargon, Mental Models)
- No error indicators in output content

### Performance
- Processing times within acceptable ranges
- Memory usage stays within limits
- GUI remains responsive during processing
- No application crashes or hangs

## Reporting

Test results are automatically generated in multiple formats:

### JSON Reports
Detailed machine-readable test results with:
- Individual test outcomes
- Performance metrics
- Validation scores
- Error details

### Summary Reports
Human-readable summaries showing:
- Overall success rates
- Failed test categories  
- Performance benchmarks
- Recommendations

## Troubleshooting

### Common Issues

**Tests fail to start:**
- Ensure Knowledge Chipper GUI dependencies are installed
- Check that sample files are present in correct directories
- Verify PyQt6 is properly configured

**GUI automation fails:**
- Tests require a graphical environment (not SSH without X11)
- Close other applications that might interfere
- Ensure sufficient screen resolution

**File processing timeouts:**
- Large files may need longer timeouts
- Check available system resources
- Consider using smaller test files for development

**Missing sample files:**
- See `tests/fixtures/sample_files/README.md` for file requirements
- Ensure files are in correct subdirectories
- Check file naming conventions

### Debug Mode

Run tests with verbose logging:
```bash
python -m tests.gui_comprehensive.main_test_runner comprehensive --verbose
```

### Dry Run

See what would be tested without running:
```bash
python -m tests.gui_comprehensive.main_test_runner comprehensive --dry-run
```

## Contributing

When adding new test scenarios:

1. Update test configuration files
2. Add appropriate sample files
3. Update validation rules if needed
4. Test locally before committing
5. Update this documentation

## Integration

This testing framework can be integrated into CI/CD pipelines:

```bash
# In your CI script
python -m tests.gui_comprehensive.main_test_runner smoke --output ./ci_results
```

For automated testing, ensure the CI environment supports GUI applications (virtual display may be required).
