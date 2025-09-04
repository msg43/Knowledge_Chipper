# GUI Comprehensive Testing Framework

This framework provides automated comprehensive testing for the Knowledge Chipper GUI application, covering all permutations of input types, GUI tabs, and processing operations.

## Quick Start

### 1. Setup Test Data

First, generate the required test files:

```bash
cd tests/gui_comprehensive
python3 main_test_runner.py setup
```

This creates audio, video, and document files in `tests/fixtures/sample_files/`.

### 2. Run Tests

**Option A: Interactive Script (Recommended)**
```bash
./run_gui_tests.sh
```

**Option B: Direct Commands**
```bash
# From project root, using venv Python directly (recommended)
cd /path/to/Knowledge_Chipper
/path/to/Knowledge_Chipper/venv/bin/python3 tests/gui_comprehensive/main_test_runner.py smoke

# Or from tests/gui_comprehensive directory
cd tests/gui_comprehensive
../../venv/bin/python3 main_test_runner.py smoke

# Comprehensive tests (1-2 hours) 
../../venv/bin/python3 main_test_runner.py comprehensive

# All test suites
../../venv/bin/python3 main_test_runner.py all
```

**Note**: If you have pyenv or other Python version managers installed, they may interfere with virtual environment activation. In such cases, use the venv Python directly as shown above.

## Test Modes

| Mode | Duration | Description |
|------|----------|-------------|
| `setup` | 2-5 min | Generate test data files |
| `smoke` | 5-10 min | Quick validation tests |
| `basic` | 30 min | Basic functionality tests |
| `comprehensive` | 1-2 hours | Full permutation testing |
| `stress` | 2+ hours | Large file stress testing |
| `all` | 3+ hours | All test suites sequentially |

## GUI Management

The framework can automatically launch and manage the GUI application:

### Auto-Launch (Default)
```bash
python3 main_test_runner.py smoke
```
- Automatically starts Knowledge Chipper GUI
- Waits for GUI initialization
- Runs tests against the GUI
- Cleans up GUI process when done

### Use Existing GUI
```bash
python3 main_test_runner.py smoke --no-gui-launch
```
- Assumes GUI is already running
- Connects to existing GUI instance
- Doesn't manage GUI lifecycle

### Startup Timeout
```bash
python3 main_test_runner.py smoke --gui-startup-timeout 60
```
- Controls how long to wait for GUI startup (default: 30 seconds)

## Command Line Options

```bash
python3 main_test_runner.py [MODE] [OPTIONS]

Options:
  --test-data-dir DIR          Test data directory (default: tests/fixtures)
  --output-dir DIR             Output directory (default: tests/reports)
  --config CONFIG              Test configuration file
  --timeout SECONDS           Override timeout per test
  --verbose, -v                Enable verbose logging
  --dry-run                    Show what would be tested
  --no-gui-launch              Don't launch GUI automatically
  --gui-startup-timeout SECS   GUI startup timeout (default: 30)
```

## Test Coverage

The framework tests all combinations of:

### File Types
- **Audio**: `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.aac`
- **Video**: `.mp4`, `.webm`, `.mov`, `.avi`, `.mkv`
- **Documents**: `.txt`, `.md`, `.html`, `.pdf`

### GUI Tabs
- Process Pipeline
- Local Transcription
- Summarization
- YouTube
- File Watcher

### Operations
- Transcribe only
- Summarize only  
- Full pipeline
- MOC generation
- Batch processing

## Test Data

### Generated Files
The setup creates comprehensive test files:

**Audio Files:**
- `short_speech_30s.mp3` - 30-second speech sample
- `conversation_2min.wav` - Multi-speaker conversation
- `music_with_speech.m4a` - Speech with background music
- `interview_10min.flac` - Long-form interview
- `conference_talk_30min.wav` - Full presentation
- Plus additional formats and quality variants

**Video Files:**
- `tutorial_3min.mp4` - Educational content
- `interview_5min.webm` - Interview video
- `webinar_10min.mp4` - Presentation format
- `conference_talk_15min.mov` - Professional recording
- `full_lecture_45min.mp4` - Extended content

**Document Files:**
- `meeting_notes.txt` - Plain text meeting notes
- `blog_post.md` - Markdown formatted content
- `research_paper.txt` - Academic paper
- `technical_spec.txt` - Technical documentation
- `news_article.html` - HTML formatted content
- `large_manual_100pages.txt` - Stress testing document

### File Characteristics
- **Size variety**: Small (KB), medium (MB), large (GB)
- **Content variety**: Clean/noisy audio, single/multi-speaker
- **Format variety**: All supported input formats
- **Duration variety**: 30 seconds to 60+ minutes

## Output and Reports

### Test Results
Results are saved to `tests/reports/` with timestamps:
```
tests/reports/
├── test_report_20240115_143022.json
├── validation_reports/
├── screenshots/
└── logs/
```

### Report Contents
- **Test Summary**: Pass/fail counts, success rates
- **Detailed Results**: Per-test outcomes, timings, errors
- **Validation Reports**: Output quality assessments
- **Performance Metrics**: Processing times, resource usage
- **Screenshots**: GUI state during testing (if available)

## Validation

The framework validates:

### File Output
- Expected files are created
- File formats are correct
- File sizes are reasonable
- Content quality meets standards

### Content Quality
- **Transcripts**: Minimum length, no error markers
- **Summaries**: Required sections, appropriate length
- **MOCs**: Structured content, key sections present

### Performance
- Processing times within expected ranges
- Memory usage reasonable
- No crashes or hangs

## Troubleshooting

### Common Issues

**"GUI process terminated unexpectedly"**
- Check if Knowledge Chipper dependencies are installed
- Verify PyQt6 is available: `python -c "import PyQt6"`
- Check logs for specific error messages

**"Test data directory not found"**
- Run `python3 main_test_runner.py setup` first
- Verify files exist in `tests/fixtures/sample_files/`

**"Tab not found" errors**
- GUI may not have loaded completely
- Try increasing `--gui-startup-timeout`
- Verify GUI is running correctly manually

**Tests timeout**
- Large files may need longer processing times
- Use `--timeout` to increase per-test timeout
- Check system resources (CPU, memory, disk)

### Debug Mode
```bash
python3 main_test_runner.py smoke --verbose --dry-run
```
- Shows what would be tested without execution
- Displays detailed configuration
- Helps identify setup issues

### Manual Verification
Before running automated tests:
1. Launch GUI manually: `python -m knowledge_system.gui`
2. Verify basic functionality works
3. Check all expected tabs are present
4. Test file loading manually

## Development

### Framework Structure
```
gui_comprehensive/
├── main_test_runner.py      # Entry point, CLI handling
├── test_orchestrator.py     # Test coordination, GUI management
├── test_framework.py        # Core testing infrastructure
├── gui_automation.py        # GUI interaction utilities
├── validation.py            # Output validation
├── setup_test_data.sh       # Test data generation
├── validate_setup.py        # Setup verification
└── run_gui_tests.sh         # User-friendly runner
```

### Adding New Tests
1. Add test cases to `test_orchestrator.py`
2. Update validation rules in `validation.py`
3. Add file types to configuration
4. Update documentation

### Configuration
Test behavior is controlled by:
- `tests/fixtures/test_configs/comprehensive_config.yaml`
- Command line arguments
- Environment variables

## Integration

### CI/CD Integration
```bash
# In CI pipeline
python3 main_test_runner.py setup
python3 main_test_runner.py smoke --no-gui-launch
```

### Custom Workflows
The framework can be integrated into custom testing workflows by:
- Using individual test orchestrator methods
- Implementing custom validation rules
- Extending automation capabilities

---

For more information, see the individual module documentation or run:
```bash
python3 main_test_runner.py --help
```
