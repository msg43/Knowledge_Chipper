# GUI Comprehensive Testing Plan for Knowledge Chipper

## Overview

This document outlines an exhaustive testing strategy for the Knowledge Chipper GUI that validates every permutation of input types, GUI tabs, and processing operations. The testing framework will use PyQt6's testing capabilities combined with automated file processing validation.

## 1. Test Scope & Coverage

### 1.1 Input Types to Test

#### Audio Files
- **MP3**: Standard compressed audio format
- **WAV**: Uncompressed audio format  
- **M4A**: Apple audio format
- **FLAC**: Lossless compressed audio
- **OGG**: Open-source audio format
- **AAC**: Advanced Audio Coding format

#### Video Files  
- **MP4**: Standard video format
- **WEBM**: Web-optimized video format
- **AVI**: Audio Video Interleave format
- **MOV**: QuickTime video format
- **MKV**: Matroska video format

#### Document Files
- **PDF**: Portable Document Format
- **TXT**: Plain text files
- **MD**: Markdown files
- **DOCX**: Microsoft Word documents
- **DOC**: Legacy Microsoft Word documents
- **RTF**: Rich Text Format
- **HTML**: Web markup files
- **HTM**: HTML variant

#### URL-Based Inputs
- **YouTube Single Videos**: Individual video URLs
- **YouTube Playlists**: Playlist URLs with multiple videos
- **RSS Feeds**: RSS/Atom feed URLs
- **Web URLs**: General web page URLs for content extraction

### 1.2 GUI Tabs to Test

1. **Introduction Tab**: Static content display and navigation
2. **Process Tab**: Main file processing pipeline with batch operations
3. **Watcher Tab**: Folder monitoring and automated processing
4. **YouTube Tab**: YouTube content extraction with proxy support
5. **Transcription Tab**: Audio/video transcription using Whisper
6. **Summarization Tab**: AI-powered content summarization
7. **Claim Search Tab**: HCE claim extraction and search functionality
8. **Speaker Attribution Tab**: Speaker diarization management
9. **Summary Cleanup Tab**: Post-processing content cleanup
10. **API Keys Tab**: Credential management and validation
11. **Sync Status Tab**: Cloud synchronization status (optional)

### 1.3 Processing Operations Matrix

#### Core Operations
- **Transcribe Only**: Audio/video → text conversion
- **Summarize Only**: Text → AI summary
- **Full Pipeline**: Transcribe → Summarize → MOC generation
- **MOC Generation**: Create Maps of Content from processed files
- **Batch Processing**: Multiple files with various operations
- **Error Recovery**: Handling failed processing attempts

#### Advanced Operations
- **Speaker Diarization**: Multi-speaker identification and attribution
- **Custom Prompts**: User-defined summarization prompts
- **Quality Retry**: Automatic retry with higher-quality models
- **Cloud Export**: Export to external platforms (GetReceipts, etc.)

## 2. Test Framework Architecture

### 2.1 Directory Structure
```
tests/
├── gui_comprehensive/
│   ├── __init__.py
│   ├── test_framework.py          # Core testing framework
│   ├── test_orchestrator.py       # Main test coordinator
│   ├── gui_automation.py          # PyQt6 GUI interaction helpers
│   ├── validation.py              # Output validation utilities
│   └── reporting.py               # Test result reporting
├── fixtures/
│   ├── sample_files/              # Test input files
│   │   ├── audio/                 # Audio test samples
│   │   ├── video/                 # Video test samples
│   │   ├── documents/             # Document test samples
│   │   └── urls/                  # URL test cases
│   ├── expected_outputs/          # Known good results
│   └── test_configs/              # Test configuration files
├── reports/
│   ├── test_results/              # Detailed test outputs
│   ├── performance/               # Performance benchmarks
│   └── coverage/                  # Coverage reports
└── utils/
    ├── file_generators.py         # Generate test files
    ├── cleanup.py                 # Test environment cleanup
    └── helpers.py                 # Common utilities
```

### 2.2 Core Components

#### Test Framework (test_framework.py)
- Base classes for GUI interaction
- File loading and processing coordination
- Progress monitoring and timeout handling
- Error capture and logging

#### Test Orchestrator (test_orchestrator.py)
- Manages test execution order and dependencies
- Coordinates permutation testing across all combinations
- Handles parallel test execution where possible
- Aggregates results and generates reports

#### GUI Automation (gui_automation.py)
- PyQt6 QTest integration for simulated user interactions
- Tab navigation and control manipulation
- File selection and drag-drop simulation
- Button clicks and form filling

#### Validation (validation.py)
- Output file existence and format validation
- Content quality assessment
- Performance metrics collection
- Error condition verification

## 3. Test Case Categories

### 3.1 Smoke Tests (5 minutes)
Quick validation of core functionality:
- Load small sample of each file type
- Verify basic processing pipeline works
- Confirm GUI responsiveness
- Check for critical errors

### 3.2 Comprehensive Tests (30-60 minutes)
Full permutation testing:
- Every file type × every applicable tab × every operation
- Batch processing with mixed file types
- Error condition handling
- Performance benchmarking

### 3.3 Stress Tests (2+ hours)
Extended testing with challenging scenarios:
- Large files (>100MB videos, >50MB documents)
- High-volume batch processing
- Memory pressure testing
- Long-running operations

### 3.4 Edge Case Tests
Specific challenging scenarios:
- Corrupted or invalid files
- Network interruptions for URL processing
- Insufficient disk space conditions
- API key authentication failures

## 4. Required Sample Files

### 4.1 Audio Samples (Place in `tests/fixtures/sample_files/audio/`)

**Small Files (< 5MB each):**
- `short_speech_30s.mp3` - 30-second clear speech sample
- `conversation_2min.wav` - 2-minute two-speaker conversation
- `music_with_speech.m4a` - Background music with speech overlay
- `poor_quality_recording.mp3` - Low-quality audio for robustness testing

**Medium Files (5-20MB each):**
- `interview_10min.flac` - 10-minute interview for diarization testing
- `podcast_excerpt.ogg` - Podcast segment with multiple speakers
- `webinar_audio.aac` - Presentation audio with Q&A

**Large Files (20-50MB each):**
- `conference_talk_30min.wav` - Full conference presentation
- `audiobook_chapter.mp3` - Audiobook chapter for long-form testing

### 4.2 Video Samples (Place in `tests/fixtures/sample_files/video/`)

**Small Files (< 25MB each):**
- `tutorial_3min.mp4` - Educational tutorial video
- `interview_5min.webm` - Interview with clear speech
- `presentation_short.avi` - Slideshow presentation

**Medium Files (25-100MB each):**
- `conference_talk_15min.mov` - Conference presentation
- `documentary_excerpt.mkv` - Documentary segment
- `webinar_10min.mp4` - Webinar with slides and speech

**Large Files (100-500MB each):**
- `full_lecture_45min.mp4` - Complete lecture for stress testing
- `panel_discussion_60min.webm` - Multi-speaker panel

### 4.3 Document Samples (Place in `tests/fixtures/sample_files/documents/`)

**Text Documents:**
- `research_paper.pdf` - Academic paper with citations and references
- `blog_post.md` - Markdown blog post with formatting
- `meeting_notes.txt` - Plain text meeting notes
- `technical_spec.docx` - Technical specification document
- `legacy_report.doc` - Legacy Word document
- `formatted_article.rtf` - RTF with complex formatting

**Web Documents:**
- `news_article.html` - HTML news article with embedded media
- `blog_page.htm` - Blog page with comments and navigation
- `wikipedia_page.html` - Complex Wikipedia page export

**Challenging Documents:**
- `large_manual_100pages.pdf` - Large PDF for performance testing
- `scanned_document.pdf` - Scanned PDF requiring OCR
- `multilingual_document.pdf` - Document with multiple languages

### 4.4 URL Test Cases (Place in `tests/fixtures/sample_files/urls/`)

**YouTube URLs (`youtube_test_urls.txt`):**
```
# Single Videos
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/dQw4w9WgXcQ

# Educational Content
https://www.youtube.com/watch?v=VIDEO_ID_EDUCATIONAL

# Playlists
https://www.youtube.com/playlist?list=PLAYLIST_ID

# Channels
https://www.youtube.com/channel/CHANNEL_ID
```

**RSS Feed URLs (`rss_test_feeds.txt`):**
```
# News Feeds
https://feeds.bbci.co.uk/news/rss.xml
https://rss.cnn.com/rss/edition.rss

# Podcast Feeds
https://feeds.megaphone.fm/PODCAST_FEED

# Blog Feeds  
https://blog.example.com/feed.xml
```

**Web Page URLs (`web_test_urls.txt`):**
```
# Articles
https://example.com/article-page
https://medium.com/@author/article-title

# Documentation
https://docs.python.org/3/tutorial/
https://github.com/project/wiki/page
```

## 5. Test Execution Strategy

### 5.1 Automated Test Suites

#### Suite 1: Quick Validation (5 minutes)
- 1 file per format type with basic processing
- Core tab functionality verification
- Critical error detection

#### Suite 2: Core Permutations (30 minutes)
- All file types × primary tabs
- Standard operation combinations
- Basic error handling

#### Suite 3: Full Coverage (60 minutes)
- Complete permutation matrix
- Advanced operations testing
- Performance benchmarking

#### Suite 4: Stress Testing (120+ minutes)
- Large file processing
- Memory pressure scenarios
- Extended operation testing

### 5.2 Test Configuration Files

**Basic Test Config (`tests/fixtures/test_configs/basic_config.yaml`):**
```yaml
test_suite: basic
timeout: 300  # 5 minutes per test
file_size_limit: 10MB
operations:
  - transcribe_only
  - summarize_only
  - basic_pipeline
tabs:
  - Process Pipeline
  - Local Transcription
  - Summarization
```

**Comprehensive Test Config (`tests/fixtures/test_configs/comprehensive_config.yaml`):**
```yaml
test_suite: comprehensive
timeout: 1800  # 30 minutes per test
file_size_limit: 100MB
operations:
  - transcribe_only
  - summarize_only
  - full_pipeline
  - moc_generation
  - batch_processing
tabs:
  - Process Pipeline
  - Local Transcription
  - Summarization
  - YouTube
  - File Watcher
error_scenarios: true
performance_monitoring: true
```

## 6. Implementation Phases

### Phase 1: Foundation Setup (Week 1)
- [ ] Create test directory structure
- [ ] Implement base test framework classes
- [ ] Set up PyQt6 testing infrastructure
- [ ] Create sample file organization system
- [ ] Implement basic GUI automation helpers

### Phase 2: Core Test Implementation (Week 2)
- [ ] Implement file processing permutation tests
- [ ] Add tab navigation and interaction automation
- [ ] Create output validation mechanisms
- [ ] Add basic error condition testing
- [ ] Implement test result reporting

### Phase 3: Advanced Testing (Week 3)
- [ ] Add YouTube URL and playlist testing
- [ ] Implement RSS feed processing tests
- [ ] Create batch processing validation
- [ ] Add file watcher automation tests
- [ ] Implement performance benchmarking

### Phase 4: Polish & Integration (Week 4)
- [ ] Add comprehensive error scenario testing
- [ ] Implement stress testing capabilities
- [ ] Create detailed test documentation
- [ ] Add maintenance and debugging guides
- [ ] Finalize reporting and metrics

## 7. Success Metrics

### 7.1 Coverage Targets
- **File Format Coverage**: 100% (18+ formats)
- **GUI Tab Coverage**: 100% (11 tabs)
- **Operation Coverage**: 100% (8+ operation types)
- **Error Scenario Coverage**: 90% (common failure modes)

### 7.2 Performance Targets
- **Test Execution Time**: < 2 hours for full suite
- **Memory Usage**: < 8GB peak during testing
- **Success Rate**: > 95% for standard test cases
- **Error Recovery**: 100% graceful handling of expected errors

### 7.3 Quality Targets
- **Zero GUI Crashes**: No application crashes during testing
- **Output Validation**: 100% of successful processes produce valid outputs
- **Performance Consistency**: < 20% variance in processing times for similar files
- **Resource Cleanup**: 100% cleanup of temporary files and processes

## 8. Maintenance & Updates

### 8.1 Regular Maintenance Tasks
- Update sample files when new formats are supported
- Refresh URL test cases (YouTube links, RSS feeds)
- Update expected outputs when processing algorithms change
- Monitor and update performance benchmarks

### 8.2 Integration with Development Workflow
- Run smoke tests on every build
- Run comprehensive tests on release candidates
- Update tests when new features are added
- Maintain test documentation alongside code changes

## 9. Risk Mitigation

### 9.1 Test Environment Isolation
- Use separate test output directories
- Implement comprehensive cleanup procedures
- Isolate API calls with test-specific keys
- Prevent interference with production data

### 9.2 Failure Recovery
- Implement robust timeout mechanisms
- Add automatic test recovery procedures
- Create detailed failure logging
- Provide manual intervention points for debugging

## 10. Getting Started

To begin implementation, please provide the sample files as outlined in Section 4, organized according to the directory structure in Section 2.1. The test framework will be built incrementally, starting with basic file processing validation and expanding to cover all permutations and advanced scenarios.
