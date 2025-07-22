# Knowledge System Architecture & Implementation Plan

## 1. High-Level Architecture Diagram (Text Form)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              KNOWLEDGE SYSTEM APP                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   GUI Layer     │    │   CLI Layer     │    │   API Layer     │         │
│  │  (PyQt6/Tkinter)│    │   (Click)       │    │  (FastAPI)      │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│           │                       │                       │                 │
│           └───────────────────────┼───────────────────────┘                 │
│                                   │                                         │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐   │
│  │                    CORE APPLICATION LAYER                            │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │   │
│  │  │Transcription│ │Summarization│ │   MOC Gen   │ │File Watchers│     │   │
│  │  │  Manager    │ │  Manager    │ │  Manager    │ │  Manager    │     │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐   │
│  │                    PROCESSOR LAYER                                   │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │   │
│  │  │YouTube Proc │ │  PDF Proc   │ │  Video Proc │ │   MD Proc   │     │   │
│  │  │(yt-dlp API) │ │(PyPDF2/PDF) │ │(WhisperX)   │ │(File I/O)   │     │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐   │
│  │                    SERVICE LAYER                                     │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │   │
│  │  │LLM Service  │ │WhisperX Svc │ │YouTube API  │ │File Monitor │     │   │
│  │  │(OpenAI/Claude│ │(GPU/CPU)   │ │(yt-dlp)     │ │(watchdog)   │     │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐   │
│  │                    DATA LAYER                                        │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │   │
│  │  │SQLite State │ │Config Files │ │Log Files    │ │Cache Dir    │     │   │
│  │  │(Progress)   │ │(YAML/JSON)  │ │(Rotating)   │ │(Temp Files) │     │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

GPU UTILIZATION STRATEGY:
- Primary: WhisperX with CUDA/MPS acceleration
- Fallback 1: WhisperX CPU-only mode
- Fallback 2: OpenAI Whisper API (cloud)
- Fallback 3: Local Whisper (CPU)

FILE SYSTEM LAYOUT:
/Users/{user}/Documents/KnowledgeSystem/
├── config/
│   ├── settings.yaml
│   ├── prompts/
│   └── models/
├── data/
│   ├── vaults/
│   ├── cache/
│   └── temp/
├── logs/
├── state/
└── output/
    ├── transcripts/
    ├── summaries/
    └── mocs/
```

## 2. Component Inventory Table

| Component | Language/Tech | Key Libraries | Main Responsibilities | Build Targets |
|-----------|---------------|---------------|----------------------|---------------|
| GUI Application | Python 3.11+ | PyQt6, tkinter | Main user interface, progress tracking | macOS .app bundle |
| CLI Interface | Python 3.11+ | Click, rich | Command-line operations, scripting | CLI executable |
| Core Engine | Python 3.11+ | asyncio, threading | Orchestration, state management | Python package |
| YouTube Processor | Python 3.11+ | yt-dlp, requests | Video metadata & download | Python module |
| PDF Processor | Python 3.11+ | PyPDF2, pdfplumber | Text extraction | Python module |
| WhisperX Service | Python 3.11+ | whisperx, torch | Audio transcription | Python module |
| LLM Service | Python 3.11+ | openai, anthropic | Summarization, MOC generation | Python module |
| File Watcher | Python 3.11+ | watchdog, inotify | Directory monitoring | Python module |
| State Manager | Python 3.11+ | sqlite3, sqlalchemy | Progress tracking, resume | Python module |
| Config Manager | Python 3.11+ | pydantic, yaml | Settings management | Python module |
| Logger | Python 3.11+ | logging, loguru | Error tracking, debugging | Python module |
| Error Handler | Python 3.11+ | custom exceptions | Graceful failure handling | Python module |

**Plugin Layer (LLM Providers):**
- OpenAI GPT-4/Claude-3 (API-based)
- Local LM (Ollama, llama.cpp)
- Anthropic Claude (API-based)
- Custom model endpoints

**Secrets Management:**
- Environment variables (.env files)
- macOS Keychain integration
- Encrypted config files

## 3. User-Facing Apps Wireframe Outline

### Main GUI Application
**Window 1: Transcription Manager**
- Left Panel: Source Selection
  - YouTube playlist URL input
  - Local folder selection (video, PDF, MD)
  - Source type tabs
- Right Panel: Processing Options
  - WhisperX settings (diarization, model size)
  - Filter options (min word count)
  - Dry run toggle
  - Progress bar with detailed status
- Bottom Panel: Log viewer with error details

**Window 2: Summarization Manager**
- Source folder selection
- LLM model selection dropdown
- Prompt template selector
- Summary length slider
- Batch processing queue
- Progress tracking with individual file status

**Window 3: MOC Generator**
- Vault selection
- MOC type checkboxes (People, Tags, Mental Models, Jargon)
- Visualization options (Mermaid, Canvas, JSONL)
- Belief YAML generation settings
- Real-time preview panel

**Common Elements:**
- Dark theme (Obsidian aesthetic)
- Settings persistence
- Error notification system
- Help/About dialogs

### CLI Interface
- `knowledge-system transcribe --source <url/folder> --options`
- `knowledge-system summarize --folder <path> --model <name>`
- `knowledge-system moc --vault <path> --types <people,tags,models>`
- `knowledge-system watch --folder <path> --mode <continuous>`

## 4. Detailed Planning Timeline

### Phase 1: Foundation (Weeks 1-2)
**Week 1:**
- Project scaffolding and configuration system
- Logging and error handling framework
- Basic CLI structure with Click
- Unit testing framework setup

**Week 2:**
- File I/O utilities and safety functions
- Base processor class architecture
- Configuration management with YAML
- Basic GUI skeleton with PyQt6

### Phase 2: Core Processing (Weeks 3-6)
**Week 3:**
- YouTube API integration (metadata only)
- YouTube processor with dry-run capability
- Audio download functionality

**Week 4:**
- WhisperX integration with GPU support
- PDF text extraction processor
- File watcher implementation

**Week 5:**
- Transcription pipeline end-to-end
- Error handling and resume functionality
- Progress tracking system

**Week 6:**
- Integration testing and bug fixes
- Performance optimization
- Documentation updates

### Phase 3: Intelligence Layer (Weeks 7-10)
**Week 7:**
- LLM service abstraction layer
- OpenAI/Claude API integration
- Summarization processor

**Week 8:**
- MOC generation algorithms
- People/Tags/Mental Models extractors
- Belief YAML structure

**Week 9:**
- Visualization components (Mermaid, Canvas)
- Topic clustering implementation
- Advanced MOC features

**Week 10:**
- Intelligence layer integration
- End-to-end testing
- Performance tuning

### Phase 4: Polish & Distribution (Weeks 11-12)
**Week 11:**
- GUI refinement and UX improvements
- Code signing and notarization
- Auto-update system

**Week 12:**
- Final testing and bug fixes
- Documentation and help system
- Distribution packaging

## 5. Risk Register & Mitigations

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|------------|--------|------------|-------|
| macOS Code Signing Issues | Medium | High | Use Developer ID, test notarization early | DevOps Lead |
| Large File Memory Usage | High | Medium | Implement chunking, streaming, memory monitoring | Backend Dev |
| YouTube API Changes | High | Medium | Abstract API layer, multiple fallback strategies | Backend Dev |
| GPU Memory Exhaustion | Medium | High | Dynamic batch sizing, CPU fallback, memory monitoring | ML Engineer |
| LLM API Rate Limits | High | Medium | Implement retry logic, queue management, local fallbacks | Backend Dev |
| File System Permissions | Medium | High | Proper error handling, user-friendly permission requests | Frontend Dev |
| Dependency Conflicts | Medium | Medium | Pin versions, virtual environments, dependency audit | DevOps Lead |

## 6. Testing & QA Strategy

### Unit Testing
- **Framework:** pytest 7.4+
- **Coverage Target:** 85%+
- **Test Data:** Mock YouTube responses, sample PDFs, fake audio files
- **File Locations:** `tests/unit/` for each module

### Integration Testing
- **Framework:** pytest with fixtures
- **End-to-End:** Complete transcription pipeline
- **Test Data:** 10-20 sample videos, 5-10 PDFs
- **File Locations:** `tests/integration/`

### UI/UX Testing
- **Framework:** pytest-qt for GUI testing
- **Manual Testing:** User acceptance testing with non-technical users
- **Accessibility:** macOS VoiceOver compatibility

### Performance Testing
- **Large File Handling:** 2GB+ video files
- **Memory Usage:** Monitor during batch processing
- **GPU Utilization:** Stress testing with multiple concurrent jobs

### Notarization Testing
- **Automated:** CI/CD pipeline for code signing
- **Manual:** Test on clean macOS installations
- **Distribution:** Test auto-update mechanism

## 7. Deployment & Distribution Steps

### Code Signing Process
1. **Developer ID Certificate:** Obtain from Apple Developer Program
2. **Hardened Runtime:** Enable in build configuration
3. **Entitlements:** Configure minimal required permissions
4. **Notarization:** Submit to Apple for notarization
5. **Stapling:** Attach notarization ticket to app

### Build Pipeline
1. **Environment Setup:** Python virtual environment with pinned dependencies
2. **PyInstaller:** Create standalone executable
3. **Code Signing:** Sign with Developer ID
4. **Notarization:** Submit to Apple
5. **Packaging:** Create .dmg installer

### Auto-Update System
- **Update Server:** Simple HTTP server with version JSON
- **Client Check:** Daily background check for updates
- **Download:** Secure download with checksum verification
- **Installation:** Automatic update with user confirmation

### Documentation
- **README.md:** Installation and basic usage
- **User Guide:** Comprehensive feature documentation
- **Developer Guide:** Contributing guidelines
- **API Documentation:** For CLI and programmatic use

## 8. Bill of Materials (BoM)

### External Libraries
- **Core:** Python 3.11+, PyQt6 6.5+, Click 8.1+
- **YouTube:** yt-dlp 2023.12+, requests 2.31+
- **PDF:** PyPDF2 3.0+, pdfplumber 0.10+
- **ML:** torch 2.1+, whisperx 3.1+, transformers 4.35+
- **LLM:** openai 1.3+, anthropic 0.7+
- **Utilities:** pydantic 2.5+, loguru 0.7+, watchdog 3.0+

### Licenses
- **MIT:** Most Python packages
- **Apache 2.0:** PyTorch, Transformers
- **GPL v3:** Some audio processing libraries
- **Commercial:** OpenAI API usage

### Apple Entitlements
- **com.apple.security.app-sandbox:** Basic sandboxing
- **com.apple.security.network.client:** Network access
- **com.apple.security.files.user-selected.read-write:** File access
- **com.apple.security.device.audio-input:** Audio processing

### Hardware Requirements
- **Minimum:** 16GB RAM, Intel/Apple Silicon, 50GB storage
- **Recommended:** 32GB+ RAM, Apple Silicon, 100GB+ storage
- **GPU:** Metal-compatible GPU for WhisperX acceleration

## 9. Next-Action Checklist

### High Priority
- [ ] Set up development environment with Python 3.11+
- [ ] Create project repository with proper structure
- [ ] Implement configuration system with YAML
- [ ] Set up logging framework with rotation
- [ ] Create base processor class architecture
- [ ] Implement YouTube metadata fetching
- [ ] Set up unit testing framework with pytest
- [ ] Create basic CLI interface with Click
- [ ] Implement file I/O utilities with safety checks
- [ ] Set up error handling and exception hierarchy

### Medium Priority
- [ ] Implement WhisperX integration with GPU support
- [ ] Create PDF text extraction processor
- [ ] Build file watcher with watchdog
- [ ] Implement LLM service abstraction layer
- [ ] Create summarization processor
- [ ] Build MOC generation algorithms
- [ ] Implement GUI with PyQt6
- [ ] Set up state management with SQLite
- [ ] Create progress tracking system
- [ ] Implement resume functionality

### Low Priority
- [ ] Add advanced visualization features
- [ ] Implement auto-update system
- [ ] Create comprehensive documentation
- [ ] Set up CI/CD pipeline
- [ ] Implement performance monitoring
- [ ] Add accessibility features
- [ ] Create user acceptance testing plan
- [ ] Set up distribution packaging
- [ ] Implement advanced error reporting
- [ ] Create backup and recovery features

---

## Right-Sized LLM Ticket Breakdown

### Phase 0: Foundation (Tickets 0-A to 0-D)
**Ticket 0-A: Project Scaffolding**
- Goal: Create basic project structure and configuration
- Deliverables: `pyproject.toml`, `requirements.txt`, `src/` structure
- Test: `pytest -q` runs successfully
- Acceptance: `python -m knowledge_system --version` exits 0

**Ticket 0-B: Configuration System**
- Goal: Implement settings management with YAML
- Deliverables: `config.py`, `settings.yaml`, `tests/test_config.py`
- Test: Load config, validate defaults, handle missing files
- Acceptance: `python -c "from config import Settings; s = Settings()"` works

**Ticket 0-C: Logging Framework**
- Goal: Set up structured logging with rotation
- Deliverables: `logger.py`, `tests/test_logger.py`
- Test: Log messages, file rotation, error levels
- Acceptance: Log file created with proper format

**Ticket 0-D: Error Handling**
- Goal: Create custom exception hierarchy
- Deliverables: `errors.py`, `tests/test_errors.py`
- Test: Exception types, error messages, context preservation
- Acceptance: Exceptions provide meaningful error information

### Phase 1: Core Infrastructure (Tickets 1-A to 1-D)
**Ticket 1-A: File Utilities**
- Goal: Safe file operations and naming
- Deliverables: `utils/file_io.py`, `tests/test_file_io.py`
- Test: Safe filename creation, file operations, error handling
- Acceptance: `safe_filename("test:file.mp4")` returns valid filename

**Ticket 1-B: Base Processor**
- Goal: Abstract processor class for all input types
- Deliverables: `processors/base.py`, `tests/test_base.py`
- Test: Processor lifecycle, error handling, progress tracking
- Acceptance: Dummy processor can process test files

**Ticket 1-C: CLI Framework**
- Goal: Command-line interface with Click
- Deliverables: `cli.py`, `tests/test_cli.py`
- Test: Help commands, argument parsing, exit codes
- Acceptance: `knowledge-system --help` shows all commands

**Ticket 1-D: State Management**
- Goal: SQLite-based progress tracking
- Deliverables: `state.py`, `tests/test_state.py`
- Test: Progress tracking, resume functionality, state persistence
- Acceptance: Can track and resume interrupted operations

### Phase 2: Input Processing (Tickets 2-A to 2-D)
**Ticket 2-A: YouTube Metadata**
- Goal: Fetch video metadata without download
- Deliverables: `processors/youtube_metadata.py`, `tests/test_youtube_metadata.py`
- Test: Metadata extraction, error handling, rate limiting
- Acceptance: `fetch_metadata("video_url")` returns structured data

**Ticket 2-B: YouTube Download**
- Goal: Download video audio for transcription
- Deliverables: `processors/youtube_download.py`, `tests/test_youtube_download.py`
- Test: Audio download, format conversion, error handling
- Acceptance: Downloads audio file from YouTube URL

**Ticket 2-C: PDF Processing**
- Goal: Extract text from PDF files
- Deliverables: `processors/pdf.py`, `tests/test_pdf.py`
- Test: Text extraction, page handling, error recovery
- Acceptance: Extracts text from sample PDF

**Ticket 2-D: File Watcher**
- Goal: Monitor directories for new files
- Deliverables: `watchers.py`, `tests/test_watchers.py`
- Test: File detection, callback execution, error handling
- Acceptance: Detects new files in monitored directory

### Phase 3: Transcription (Tickets 3-A to 3-C)
**Ticket 3-A: WhisperX Integration**
- Goal: Audio transcription with GPU support
- Deliverables: `services/whisperx.py`, `tests/test_whisperx.py`
- Test: Transcription accuracy, GPU/CPU fallback, error handling
- Acceptance: Transcribes audio file to text

**Ticket 3-B: Transcription Pipeline**
- Goal: End-to-end transcription workflow
- Deliverables: `transcription_manager.py`, `tests/test_transcription.py`
- Test: Complete pipeline, progress tracking, error recovery
- Acceptance: Processes YouTube playlist end-to-end

**Ticket 3-C: MD File Generation**
- Goal: Create structured markdown files
- Deliverables: `processors/md_generator.py`, `tests/test_md_generator.py`
- Test: MD structure, metadata sections, transcript formatting
- Acceptance: Creates properly formatted MD files

### Phase 4: Intelligence Layer (Tickets 4-A to 4-D)
**Ticket 4-A: LLM Service**
- Goal: Abstract LLM provider interface
- Deliverables: `services/llm.py`, `tests/test_llm.py`
- Test: API calls, error handling, response parsing
- Acceptance: Can call OpenAI/Claude APIs

**Ticket 4-B: Summarization**
- Goal: Generate summaries from transcripts
- Deliverables: `summarizer.py`, `tests/test_summarizer.py`
- Test: Summary generation, prompt handling, output formatting
- Acceptance: Creates summaries with proper structure

**Ticket 4-C: MOC Generation**
- Goal: Extract people, tags, mental models
- Deliverables: `moc_builder.py`, `tests/test_moc.py`
- Test: Entity extraction, link generation, file creation
- Acceptance: Generates People.md, Tags.md, etc.

**Ticket 4-D: Belief YAML**
- Goal: Create belief structures with sources
- Deliverables: `belief_generator.py`, `tests/test_belief.py`
- Test: YAML generation, source tracking, epistemic weights
- Acceptance: Creates structured belief YAML files

### Phase 5: GUI & Polish (Tickets 5-A to 5-C)
**Ticket 5-A: GUI Framework**
- Goal: Basic PyQt6 interface
- Deliverables: `gui/main_window.py`, `tests/test_gui.py`
- Test: Window creation, basic interactions, error display
- Acceptance: GUI launches and shows main interface

**Ticket 5-B: Progress UI**
- Goal: Real-time progress tracking
- Deliverables: `gui/progress.py`, `tests/test_progress.py`
- Test: Progress bars, status updates, error display
- Acceptance: Shows real-time processing progress

**Ticket 5-C: Settings UI**
- Goal: Configuration management interface
- Deliverables: `gui/settings.py`, `tests/test_settings.py`
- Test: Settings persistence, validation, UI updates
- Acceptance: Can modify and save settings through GUI

### Dependencies Between Tickets
- **0-B depends on 0-A:** Configuration needs project structure
- **1-B depends on 0-C:** Base processor needs logging
- **2-A depends on 1-B:** YouTube processor extends base processor
- **2-B depends on 2-A:** Download needs metadata first
- **3-A depends on 2-B:** WhisperX needs audio files
- **3-B depends on 3-A:** Pipeline needs transcription service
- **4-A depends on 3-C:** LLM service needs MD files
- **4-B depends on 4-A:** Summarization needs LLM service
- **4-C depends on 4-B:** MOC needs summaries
- **5-A depends on 1-C:** GUI needs CLI framework

Each ticket should be completed with `pytest -q` passing before moving to the next dependent ticket. 