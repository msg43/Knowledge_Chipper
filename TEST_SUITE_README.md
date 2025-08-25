# Knowledge Chipper Comprehensive Test Suite

This test suite systematically tests all combinations of extraction, transcription, and summarization available in the Knowledge Chipper CLI using the files in `data/test_files/Test Inputs/`.

## 🎯 Test Coverage

### Input Files Tested
- **Audio/Video:** `harvard.wav`, `Yuval Noah Harari...mp3`, `Member Video #21...webm`, `wolf.MP4`
- **Documents:** `dario-amodei-transcript.html`, `Terence Tao...pdf`, `Dwarkesh_arthur-kroeber.md`, `Dwarkesh_arthur-kroeber.txt`, `Biamp and Biwiring! We NEED to TALK!.md`
- **YouTube:** URLs from `Youtube_Playlists_1.csv`, `Youtube_Playlists_1.txt`, `Youtube_Playlists_1.rtf`
- **Template:** `Summary Prompt.txt` for custom summarization

### Test Categories

#### 1. 🎵 Audio/Video Transcription
- **Files:** All audio formats (WAV, MP3) and video formats (WebM, MP4) 
- **Models:** base, small
- **Formats:** md, txt
- **Diarization:** With/without speaker labels
- **Devices:** auto

#### 2. 📺 YouTube Extraction
- **File Sources:** CSV, TXT, and RTF files containing YouTube URLs
- **Features:** URL processing, thumbnail download
- **Diarization:** With/without speaker labels
- **Timeout:** Extended for network operations

#### 3. 📝 Document Summarization
- **File Types:** HTML, PDF, Markdown, Text
- **Models:** gpt-4o-mini-2024-07-18, gpt-3.5-turbo
- **Templates:** Default and custom (`Summary Prompt.txt`)

#### 4. 📄 Markdown In-Place Summarization
- **Target:** Markdown files with "# Full Transcript" sections
- **Process:** Extracts text below transcript header, adds summary above it in same file
- **Files:** `Biamp and Biwiring! We NEED to TALK!.md`, `Dwarkesh_arthur-kroeber.md`
- **Models:** gpt-4o-mini-2024-07-18
- **Template:** Custom (`Summary Prompt.txt`)

#### 5. 🔄 Combined Processing Pipeline
- **Flow:** Transcription → Summarization → MOC generation
- **Models:** base (transcription) + gpt-4o-mini-2024-07-18 (summarization)

## 🚀 Running the Tests

### Prerequisites
1. Ensure Knowledge Chipper is properly installed and configured
2. Verify all test input files are present in `data/test_files/Test Inputs/`
3. Configure API keys for LLM providers (OpenAI, Anthropic)

### Execute Test Suite
```bash
# From the Knowledge Chipper project root:
python comprehensive_test_suite.py

# Or make it executable and run directly:
chmod +x comprehensive_test_suite.py
./comprehensive_test_suite.py
```

### Expected Runtime
- **Audio/Video Tests:** 2-5 minutes per file (depending on length and model)
- **Document Tests:** 30-60 seconds per file
- **YouTube Tests:** 3-10 minutes (depending on video length)
- **Total Suite:** 30-60 minutes (varies by content and system performance)

## 📊 Output Structure

```
data/test_files/Test Outputs/
├── transcription/                    # Basic transcription outputs (all audio/video)
├── transcription_with_diarization/   # Speaker-labeled transcriptions  
├── summarization/                    # Document summaries + in-place MD updates
├── html_processing/                  # HTML document processing
├── pdf_processing/                   # PDF document processing
├── youtube_extraction/               # YouTube processing (from CSV/TXT/RTF)
├── combined_processing/              # Full pipeline outputs
└── logs/                            # Test reports and logs
    ├── test_report_YYYYMMDD_HHMMSS.json  # Machine-readable results
    └── test_report_YYYYMMDD_HHMMSS.md    # Human-readable report
```

## 📈 Test Reports

The suite generates comprehensive reports in two formats:

### JSON Report (`test_report_YYYYMMDD_HHMMSS.json`)
- Machine-readable test results
- Individual test outcomes
- Performance metrics
- Error details

### Markdown Report (`test_report_YYYYMMDD_HHMMSS.md`)
- Human-readable summary
- Test statistics
- Grouped results by test type
- Failed test details with commands and errors

### Report Contents
- **Total Tests Run**
- **Success/Failure Counts**
- **Success Rate Percentage**
- **Total Processing Time**
- **Individual Test Results**
- **Output File Counts**
- **Error Messages for Failed Tests**

## 🛠 Customization

### Modifying Test Parameters

Edit `comprehensive_test_suite.py` to customize:

```python
# Change transcription models
models = ["base", "small", "medium"]  # Add more models

# Change summarization models  
models = ["gpt-4o-mini-2024-07-18", "claude-3-haiku-20240307"]

# Change output formats
formats = ["md", "txt", "srt", "vtt"]

# Adjust timeouts
timeout=600  # 10 minutes for transcription
timeout=1200 # 20 minutes for YouTube
```

### Adding New Test Files
1. Place files in `data/test_files/Test Inputs/`
2. Update the respective test method in the script
3. Ensure file formats are supported by Knowledge Chipper

## 🔧 Troubleshooting

### Common Issues

**Missing Dependencies:**
```bash
pip install -r requirements.txt
```

**API Key Errors:**
- Configure OpenAI API key in `config/settings.yaml`
- Configure Anthropic API key if using Claude models

**File Not Found Errors:**
- Verify all test input files are present
- Check file permissions and paths

**Timeout Errors:**
- Increase timeout values for large files
- Check system resources and processing capability

### Test Failure Analysis

1. **Check the generated report** in `logs/` for detailed error messages
2. **Review individual command outputs** in the JSON report
3. **Verify API keys and model availability**
4. **Check file format compatibility**

## 🎯 Expected Test Results

### Successful Tests Should Produce:
- **Transcription Tests:** `.md` or `.txt` files with transcribed content
- **Diarization Tests:** Speaker labels in transcriptions  
- **Summarization Tests:** Summary files using specified templates
- **YouTube Tests:** Downloaded video content + thumbnails
- **Combined Tests:** Multiple output files from full pipeline

### Performance Benchmarks:
- **Audio Transcription:** ~1-3x real-time (5min audio = 5-15min processing)
- **Document Summarization:** ~30-60 seconds per document
- **YouTube Processing:** ~2-5x video length for transcription

### Quality Checks:
- Transcriptions should be readable and accurate
- Summaries should follow the template structure
- Speaker diarization should show multiple speakers (when applicable)
- Output files should be properly formatted

## 📋 Test Checklist

Before running the test suite:

- [ ] Knowledge Chipper is installed and working
- [ ] API keys are configured
- [ ] Test input files are present
- [ ] Sufficient disk space for outputs (~1-2GB)
- [ ] Network connectivity for YouTube tests
- [ ] FFMPEG installed (for video processing)

After running the test suite:

- [ ] Review test report for success rate
- [ ] Spot-check output files for quality
- [ ] Verify expected file counts in each output directory
- [ ] Check for any error patterns in failed tests

## 🤝 Contributing

To extend the test suite:

1. **Add new test methods** following the existing pattern
2. **Update output directory structure** if needed
3. **Add new file types** to the respective test categories
4. **Update this README** with new test descriptions

## 📞 Support

If you encounter issues:

1. Check the generated test reports for detailed error information
2. Verify your Knowledge Chipper installation and configuration
3. Review the troubleshooting section above
4. Check the main Knowledge Chipper documentation
