# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Skipthepodcast.com** (formerly Knowledge_Chipper) is a macOS desktop application that transforms videos, audio, and documents into structured, searchable knowledge using AI-powered analysis. The system extracts claims, identifies speakers, and organizes content into a claim-centric database.

**Current Version:** 3.5.0
**Python:** 3.11+
**Primary Interface:** PyQt6 GUI (CLI removed)

## Essential Development Commands

### Setup
```bash
make install              # Install deps + pre-commit hooks
make dependencies-check   # Verify critical dependencies
```

### Testing
```bash
make test                 # Full test suite (recommended before push)
make test-quick           # Fast unit tests (~30s)
make test-unit            # All unit tests
make test-integration     # Integration tests (requires Ollama)
make test-gui             # GUI tests
make smoke-test           # Basic functionality verification
```

**Important:** Run `make test-quick` before pushing. Full `make test` before releases.

### Single Test Execution
```bash
# Run specific test file
pytest tests/test_basic.py -v

# Run specific test function
pytest tests/test_basic.py::test_function_name -v

# Run with keyword filter
pytest tests/ -k "youtube" -v
```

### Code Quality
```bash
make lint                 # Linting (flake8)
make format              # Auto-format (black + isort)
make security-check      # Security scan (bandit)
make pre-commit-all      # Run all pre-commit hooks
```

### Building
```bash
make build               # Build distribution packages
make clean               # Remove build artifacts
```

### yt-dlp Management
```bash
make check-ytdlp-releases  # Check for updates with risk assessment
make update-ytdlp          # Quick version check/update
make test-ytdlp-update     # Full test + validate workflow
```

**Note:** yt-dlp version is production-pinned in pyproject.toml (currently `2025.10.14`). See `docs/YT_DLP_UPGRADE_PROCEDURE.md` for upgrade process.

## Architecture Overview

### Core Processing Pipeline

```
User Input (GUI)
    ↓
System2Orchestrator (core/system2_orchestrator.py)
    ↓
UnifiedHCEPipeline (processors/hce/unified_pipeline.py)
    ├─> Mining (parallel segment processing)
    ├─> Evaluation (flagship model scoring)
    ├─> Categorization (domain classification)
    └─> Storage (unified SQLite DB)
```

### Key Architectural Principles

**1. Claim-Centric, Not Source-Centric**
- Claims are the fundamental atomic unit of knowledge
- Sources (videos, documents) provide attribution context
- Database queries start with `claims` table, JOIN to `media_sources` for context
- Architecture: `claims` → references → `sources`, NOT `sources` → contains → `claims`

**2. Database-Centric Design**
- Database is single source of truth (not files)
- Files are regenerated from DB on demand
- Metadata lookups use database, not filename parsing
- Location: `~/Library/Application Support/SkipThePodcast/`

**3. Hybrid Claim Extraction (HCE)**
- Parallel mining across transcript segments (3-8x faster)
- Flagship evaluation model ranks claims (A/B/C tiers)
- Structured outputs via JSON mode (not grammar-enforced, 5-6x faster)
- Post-validation repairs common LLM omissions (e.g., domain field)

**4. Multi-Account YouTube Downloads**
- Session-based anti-bot protection
- Parallel downloads across accounts (not sequential rotation)
- Cookie-based authentication for bulk processing (100+ videos)

### Directory Structure

```
src/knowledge_system/
├── core/                    # Orchestration & pipeline coordination
│   ├── system2_orchestrator.py       # Main job orchestrator
│   ├── system2_orchestrator_mining.py # Mining integration
│   ├── llm_adapter.py                # LLM provider abstraction
│   └── enhanced_hce_pipeline.py      # HCE pipeline implementation
├── processors/              # Content processing
│   ├── hce/                # Hybrid Claim Extraction system
│   │   ├── unified_pipeline.py       # Main HCE pipeline
│   │   ├── storage_sqlite.py         # Unified DB storage
│   │   └── miners/                   # Claim mining modules
│   ├── youtube_download.py          # yt-dlp wrapper
│   ├── audio_processor.py           # Transcription (whisper.cpp)
│   ├── diarization.py              # Speaker identification
│   └── document_processor.py        # PDF/DOCX processing
├── services/                # Business logic services
│   ├── file_generation.py          # Regenerate files from DB
│   ├── download_scheduler.py       # Download queue management
│   ├── multi_account_downloader.py # Parallel account downloads
│   └── speaker_learning_service.py # Voice fingerprinting
├── database/                # Database layer
│   ├── models.py           # SQLAlchemy ORM models
│   ├── service.py          # Database access layer
│   ├── claim_store.py      # Claim-specific operations
│   └── migrations/         # Schema migrations
├── gui/                     # PyQt6 GUI (8 tabs)
│   ├── main_window_pyqt6.py        # Main application window
│   ├── tabs/               # Tab implementations
│   ├── components/         # Reusable UI components
│   └── workers/            # Background worker threads
├── voice/                   # Voice fingerprinting system
└── utils/                   # Shared utilities
```

### Database Schema Highlights

**Core Tables:**
- `media_sources` - Videos, podcasts, documents (organizational)
- `claims` - Extracted knowledge claims (primary data)
- `transcripts` - Transcription data with timestamps
- `summaries` - Analysis results with metrics
- `people`, `concepts`, `relations` - Knowledge graph entities
- `speaker_fingerprints` - Voice identification data

**Content Types:** Transcripts distinguish between "Transcript (Own)", "Transcript (Third-party)", "Document (PDF/eBook)", "Document (White Paper)" to adapt processing.

### File Organization

Output files are organized by type in subdirectories:

```
output_directory/
├── transcripts/          # From database regeneration
├── summaries/            # Claims analysis results
├── moc/                  # Maps of Content
├── exports/              # SRT, VTT, JSON exports
├── downloads/youtube/    # Downloaded media
└── *.md                  # Transcripts from AudioProcessor
```

Files are linked via `source_id` (11-char YouTube ID or generated hash). See `docs/FILE_ORGANIZATION.md` for details.

## Common Workflows

### Processing a YouTube Video

1. **Download**: `processors/youtube_download.py` via yt-dlp
   - Saves metadata to `media_sources` table
   - Records `audio_file_path` in database
2. **Transcribe**: `processors/audio_processor.py` via whisper.cpp
   - Stores transcript in `transcripts` table
   - Generates markdown file
3. **Diarize** (optional): `processors/diarization.py` via pyannote.audio
   - Identifies speaker segments
   - Creates `speaker_fingerprints`
4. **Analyze**: `core/system2_orchestrator.py` → `processors/hce/unified_pipeline.py`
   - Mines claims in parallel
   - Evaluates with flagship model
   - Stores to unified HCE database
5. **Review**: GUI Review tab displays ranked claims

### Running Tests

**Critical:** Tests may fail if optional dependencies are missing:
- `pyannote.audio` for diarization tests
- Ollama running locally for integration tests
- `soundfile` library for voice fingerprinting tests

Use markers to filter:
```bash
pytest -m "not integration"  # Skip integration tests
pytest -k "not voice"         # Skip voice fingerprinting
```

See `.pre-commit-config.yaml` for test collection exclusions.

### Version Management

**IMPORTANT:** `pyproject.toml` is the single source of truth for version numbers.

```bash
python3 scripts/bump_version.py --part patch|minor|major
bash scripts/update_build_date.sh  # Sync README.md
```

Always bump version BEFORE making significant changes. Use semantic versioning.

## Important Implementation Rules

### From `.cursor/rules/`

**1. No Graceful Fallbacks** (`.cursor/rules/no-graceful-fallback.mdc`)
- Before creating fallbacks or suppressing warnings, ask the user
- Prefer fixing root causes over masking symptoms

**2. Claim-Centric Architecture** (`.cursor/rules/claim-centric-architecture.mdc`)
- Use "claims attributed to source", NOT "source contains claims"
- Queries start with claims table, JOIN sources for context
- Claims are queryable independently of source

**3. HCE Workflow** (`.cursor/rules/hce-workflow.mdc`)
- Cut-over workflow for swapping legacy → HCE
- Maintain external API compatibility
- Use database compatibility views for gradual migration

## Critical Files and Configurations

### Settings Hierarchy
- **GUI State**: Persisted via QSettings (platform-specific)
- **Application Config**: `config.py` with Pydantic settings
- **Database**: Single source of truth for processing state

### Pre-commit Hooks
Run automatically on commit (see `.pre-commit-config.yaml`):
- Auto-fix: `black`, `isort`, `trailing-whitespace`
- Pre-push: `flake8`, `bandit`, `pytest --collect-only`

Voice fingerprinting tests excluded from pre-push collection (soundfile dependency issues).

### Lazy-Loaded Dependencies
To reduce initial install size:
- `diarization` extras (~377MB): torch, transformers, pyannote.audio
- `hce` extras (~500MB): sentence-transformers
- `gui` extras: PyQt6

Install with: `pip install -e ".[diarization,hce,gui]"`

## Testing Notes

### GUI Testing
- Uses pytest-qt for PyQt6 component testing
- See `tests/gui_comprehensive/` for examples
- Separate pytest config: `pytest.ini.gui_testing`

### Integration Tests
Require external services:
- Ollama for local LLM tests
- Mark with `@pytest.mark.integration`

### Test Data
- Sample transcripts: `tests/sample_data/`
- Fixtures: `tests/fixtures/`
- Real audio: `tests/real_speech_pack/` (if available)

## Troubleshooting

### Common Issues

**Import Errors:**
- Check `tests/test_database_imports.py` for database export validation
- Verify `__init__.py` exports in modified modules

**yt-dlp Failures:**
- Version pinned in pyproject.toml for stability
- Check `docs/YT-DLP_MONITORING_GUIDE.md` for update procedures
- Use `make check-ytdlp-releases` for changelog analysis

**Missing Models:**
- Whisper models: `~/.cache/whisper/`
- Diarization models: `~/.cache/torch/pyannote/`
- Qwen models: `ollama list` to verify installation

**Database Migrations:**
- Manual migrations in `database/migrations/`
- Apply with `DatabaseService().run_migrations()`

### Logging
- Main logs: `logs/` directory
- GUI logs integrated via `gui/utils/log_integration.py`
- Verbosity controlled in `logger.py` and `logger_system2.py`

## Resources

- **User Guide**: `README.md`
- **Architecture**: `docs/ARCHITECTURE_UNIFIED.md`, `docs/DATABASE_CENTRIC_ARCHITECTURE.md`
- **File Organization**: `docs/FILE_ORGANIZATION.md`
- **Testing Guide**: `docs/AUTOMATED_TESTING_GUIDE.md`
- **yt-dlp Updates**: `docs/YT_DLP_UPGRADE_PROCEDURE.md`
- **Queue System**: `docs/QUEUE_TAB_USER_GUIDE.md`
- **Change History**: `CHANGELOG.md`
