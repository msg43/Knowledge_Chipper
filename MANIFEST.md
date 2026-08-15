# Knowledge_Chipper MANIFEST

**Complete inventory of all files in the Knowledge_Chipper daemon codebase**

**Last Updated:** January 18, 2026  
**Version:** 4.1.0 (Daemon-Only Architecture + Shared Taste Model)  
**Architecture:** Web-first with local daemon processing

---

## PROJECT OVERVIEW

Knowledge_Chipper is a **macOS daemon** that transforms videos, audio, and documents into structured, searchable knowledge using AI-powered analysis. It extracts claims, identifies speakers, and organizes content into a claim-centric database, then uploads to GetReceipts.org for web-based collaboration and visualization.

**Key Architecture Principle**: This is a **daemon-only** codebase. All user interaction happens through the GetReceipts.org web interface at `/contribute`. The daemon runs as a background service providing REST API endpoints for processing operations.

**Current Version:** 4.1.0  
**Daemon Version:** 1.1.x  
**Python:** 3.11+  
**Platform:** macOS only

---

## ARCHITECTURE: DAEMON + WEB

```
┌─────────────────────────────────────────┐
│   GetReceipts.org/contribute (Web UI)   │
│   - Job submission & monitoring          │
│   - Settings & configuration             │
│   - Results viewing                      │
└──────────────┬──────────────────────────┘
               │ HTTP REST API
               │ (localhost:8765)
┌──────────────▼──────────────────────────┐
│   Knowledge_Chipper Daemon (macOS)      │
│   - Video/audio processing               │
│   - AI extraction (claims, entities)     │
│   - Local SQLite database                │
│   - Auto-upload to GetReceipts           │
└─────────────────────────────────────────┘
```

**What Runs Where:**
- **Local Daemon**: Processing, extraction, transcription, local storage
- **Web Interface**: UI, job management, settings, results viewing
- **Cloud (Supabase)**: Canonical storage, deduplication, collaboration

---

## ROOT DIRECTORY

### Configuration Files

- `.bandit` - Security linter configuration
- `.gitignore` - Git ignore patterns
- `.pre-commit-config.yaml` - Pre-commit hooks (black, flake8, mypy, bandit)
- `.python-version` - Python 3.11.x specification for pyenv
- `.secrets.baseline` - Baseline for detect-secrets tool
- `pyproject.toml` - **Python project metadata and dependencies** (single source of truth for version)
- `pyrightconfig.json` - Pyright type checker configuration
- `pytest.ini` - Pytest configuration for test suite
- `requirements.txt` - **Production dependencies** (updated Jan 2026: chromadb, httpx for Dynamic Learning/RAE)
- `requirements-dev.txt` - Development dependencies

### Build and Deployment

- `Makefile` - Build automation (test, lint, format, install, test-daemon)
- `SkipThePodcast.pkgproj` - Packages.app project for building macOS PKG installer

### GitHub Actions Workflows

- `.github/workflows/daemon-release.yml` - **Automated daemon releases** (triggers on version tags)
- `.github/workflows/smoke-test.yml` - Lightweight smoke tests on every push
- `.github/workflows/watch-deno-releases.yml` - Monitors Deno releases (required for yt-dlp)

### Documentation - Cleanup & Status

- `TODO_MARKERS_MEMORIAL.md` - **NEW (Jan 17, 2026):** Historical record of 23 TODO markers addressed during cleanup
- `CLEANUP_ANALYSIS_REPORT.md` - **NEW (Jan 17, 2026):** Analysis report from vulture and depcheck scans
- `SHARED_TASTE_MODEL_IMPLEMENTATION.md` - **NEW (Jan 18, 2026):** Shared taste model distribution implementation details
- `CHANGELOG.md` - Chronological record of all changes
- `CLAUDE.md` - Guidance for Claude Code AI assistant
- `LICENSE` - MIT License
- `README.md` - Main project documentation

### Documentation - Current Features

- `RAE_IMPLEMENTATION_COMPLETE.md` - **NEW (Jan 17, 2026):** RAE (Retrieval-Augmented Extraction) system
- `RAE_QUICK_START.md` - **NEW (Jan 17, 2026):** RAE quick start guide
- `DESKTOP_APP_DEPRECATION.md` - **NEW (Jan 11, 2026):** GUI deprecation documentation
- `DAEMON_DEPENDENCIES_SLIM.md` - **NEW (Jan 11, 2026):** Dependency optimization (206→34 packages)
- `DAEMON_AUTOMATION_COMPLETE.md` - **NEW (Jan 11, 2026):** Automated release workflow
- `ARCHITECTURE_WEB_CANONICAL.md` - Web-canonical architecture documentation
- `CURRENT_ACTIVE_PROMPTS.md` - Two-pass prompt system documentation

### Documentation - Historical (Pre-Cleanup)

Over 100 documentation files covering historical features, bug fixes, and architecture evolution. Key categories:
- Multi-account YouTube download system
- Batch processing optimizations
- Claims-first architecture migration
- Speaker attribution fixes
- Transcription improvements
- Web-canonical migration

---

## DAEMON/

**FastAPI REST API daemon for web-first integration**

### Core Files

- `__init__.py` - Package init with version
- `main.py` - **Entry point** for PyInstaller (imports app from app_factory)
- `app_factory.py` - **FastAPI application factory** (CORS, lifespan, routes, FeedbackProcessor integration, FeedbackSyncScheduler integration)

### config/

- `__init__.py` - Config module init
- `settings.py` - **Pydantic settings** with environment variables (KC_ prefix), device linking, Dynamic Learning config

### api/

- `__init__.py` - API module init
- `routes.py` - **REST endpoints** (/health, /process, /jobs, /config, /monitor, /admin, /updates, /feedback, /feedback/sync, /feedback/sync-status)
- `database_viewer.py` - Read-only SQLite database viewer for admin page

### models/

- `__init__.py` - Models module init
- `schemas.py` - **Pydantic schemas** for all API operations (ProcessRequest, JobStatus, DaemonConfig, MonitorConfig, etc.)

### services/

- `__init__.py` - Services module init
- `processing_service.py` - Wraps processors for REST API (batch processing, job retry/cancel/delete)
- `monitor_service.py` - Folder monitoring service wrapping FileWatcher
- `update_checker.py` - Auto-update system (checks GitHub releases, downloads/installs updates)
- `author_service.py` - Author/channel management
- `link_token_handler.py` - Auto-linking device using token from download URL
- `rss_service.py` - RSS/podcast feed processing
- `youtube_matcher.py` - YouTube search and video matching
- `simple_llm_wrapper.py` - Synchronous LLM wrapper for TwoPassPipeline
- `api_key_store.py` - **NEW (Jan 12, 2026):** Module-level API key storage for daemon
- `feedback_sync_service.py` - **NEW (Jan 18, 2026):** Shared taste model distribution service
  - `FeedbackSyncService` class downloads Matt's curated feedback from GetReceipts.org
  - Incremental sync with `since` parameter (only fetches new feedback)
  - Duplicate detection prevents re-adding existing examples
  - Persistent last sync timestamp tracking
  - `FeedbackSyncScheduler` class for periodic background syncs (every 24 hours)
  - Global singleton instances for service and scheduler

---

## INSTALLER/

**macOS installer components**

- `daemon.spec` - PyInstaller spec file for building standalone executable
- `org.getreceipts.daemon.plist` - LaunchAgent for auto-starting daemon on login
- `create_desktop_shortcut.sh` - **Creates macOS .app bundle** on desktop for daemon control
- `install.sh` - Post-install script (copies daemon, installs LaunchAgent, creates shortcut)
- `build_dmg.sh` - Build script to create .dmg installer + tar.gz for auto-update
- `build_pkg.sh` - **Build signed & notarized PKG installer**

### installer/scripts/

- `postinstall` - PKG postinstall script (creates desktop app, sets up LaunchAgent, starts daemon)

---

## KNOWLEDGE_CHIPPER_OAUTH/

**Device authentication and upload integration for GetReceipts**

- `README.md` - OAuth authentication system documentation
- `requirements_oauth.txt` - Python dependencies for OAuth
- `getreceipts_auth.py` - Happy-style device authentication (UUID + secret key)
- `getreceipts_config.py` - GetReceipts OAuth configuration
- `getreceipts_uploader.py` - **HTTP API-based uploader** (uses /api/knowledge-chipper/upload)
- `integration_example.py` - Integration example code
- `manual_callback_test.py` - Manual OAuth callback testing

---

## SRC/KNOWLEDGE_SYSTEM/

**Main application package**

### Root Module Files

- `__init__.py` - Package initialization, version info, public API exports
- `__main__.py` - Entry point for running as module
- `config.py` - **Configuration management** (APIKeysConfig with OpenAI, Anthropic, Google Gemini, etc.)
- `errors.py` - Custom exception hierarchy
- `logger.py` - Application-wide logging configuration
- `logger_system2.py` - Structured logging for System 2 processing
- `watchers.py` - File system watchers using watchdog
- `py.typed` - Type checking marker file

### CORE/

**Processing orchestration and coordination**

- `__init__.py` - Core module initialization
- `batch_processor.py` - Intelligent batch processing with smart resume and dynamic parallelization
- `checkpoint_manager.py` - Checkpoint management for resumable processing
- `connected_processing_coordinator.py` - Coordinates connected processing stages
- `dynamic_parallelization.py` - Dynamic parallelization based on hardware specs
- `intelligent_processing_coordinator.py` - Intelligent coordinator with adaptive strategies
- `llm_adapter.py` - **LLM provider abstraction** (OpenAI, Anthropic, Google Gemini, Ollama)
- `parallel_processor.py` - Parallel processing for multi-core systems
- `processing_config.py` - Processing configuration management
- `system2_logger.py` - Structured logging for System 2
- `system2_orchestrator_two_pass.py` - **Main orchestrator** for two-pass processing with job management
- `usage_example.py` - Usage examples

**DELETED (Jan 17, 2026):**
- ~~`enhanced_hce_pipeline.py`~~ - Legacy extraction pipeline (deprecated)
- ~~`segment_processor.py`~~ - Segment-level processing (replaced by two-pass)
- ~~`system2_orchestrator.py`~~ - Old orchestrator (replaced by two-pass version)
- ~~`system2_orchestrator_mining.py`~~ - Legacy mining integration (deprecated)

### DATABASE/

**Database models, migrations, and service layer**

- `__init__.py` - Database module initialization
- `models.py` - **SQLAlchemy models** for all tables (includes FeedbackExample, PendingFeedback, Prediction models)
- `service.py` - **Database service layer** with high-level operations
- `review_queue_service.py` - Review queue management for bulk review workflow
- `claim_store.py` - Claim-centric storage operations
- `speaker_models.py` - Speaker and voice fingerprint models (re-exported from models.py)
- `system2_models.py` - System 2 processing job and checkpoint models
- `alembic_migrations.py` - Alembic migration management
- `apply_hce_migrations.py` - Apply database migrations
- `migrate_legacy_data.py` - Migrate legacy data to new schema
- `migrate_to_claim_centric.py` - Migrate to claim-centric architecture
- `load_wikidata_vocab.py` - Load WikiData vocabulary
- `download_podcast_categories.py` - Download podcast category taxonomy
- `download_wikidata_taxonomy.py` - Download WikiData taxonomy
- `wikidata_*.json` - WikiData taxonomy files

#### DATABASE/MIGRATIONS/

**SQL migration files for schema changes**

- `unified_schema.sql` - Current production schema
- `claim_centric_schema.sql` - Claim-centric schema definition
- `add_predictions_system.sql` - Prediction system schema
- `2026_01_feedback_system.sql` - **NEW (Jan 2026):** Dynamic Learning feedback system
- `2025_12_22_add_speaker_to_entities.sql` - Speaker attribution to entities
- `2025_12_21_add_youtube_ai_summary.sql` - YouTube AI summary integration
- `2025_12_20_claims_first_support.sql` - Claims-first pipeline schema
- Plus 20+ additional migration files

#### DATABASE/DATA/

**Configuration and seed data for Dynamic Learning**

- `feedback_reasons.yaml` - **NEW (Jan 2026):** Configurable feedback reasons hierarchy
- `golden_feedback.json` - **NEW (Jan 2026):** Versioned golden set of starter feedback examples

### PROCESSORS/

**Content processing and transformation**

- `__init__.py` - Processors module initialization
- `base.py` - Base processor class
- `audio_processor.py` - **Audio transcription** (whisper.cpp with DTW timestamps)
- `document_processor.py` - PDF/DOCX processing
- `claim_evolution_detector.py` - **NEW (Jan 17, 2026):** RAE claim evolution/contradiction detection
- `html.py` - HTML document processing
- `pdf.py` - PDF document processing
- `pdf_transcript_processor.py` - PDF transcript processing with speaker parsing
- `registry.py` - Processor registry for dynamic selection
- `rss_processor.py` - RSS feed processing
- `unified_batch_processor.py` - Unified batch processor
- `whisper_cpp_transcribe.py` - Transcription using pywhispercpp
- `youtube_download.py` - **YouTube download** (yt-dlp wrapper)
- `youtube_download_with_ai_summary.py` - Enhanced downloader with YouTube AI summary scraping

**DELETED (Jan 17, 2026):**
- ~~`dual_summary_processor.py`~~ - Experimental comparison tool (never completed)
- ~~`diarization.py`~~ - Replaced by claims-first pipeline (v4.0.0)
- ~~`speaker_processor.py`~~ - Replaced by claims-first pipeline (v4.0.0)

#### PROCESSORS/TWO_PASS/

**Active two-pass whole-document processing system**

- `__init__.py` - Two-pass module initialization
- `pipeline.py` - **TwoPassPipeline orchestrator** (extraction → taste filter → truth critic → synthesis)
- `extraction_pass.py` - **Pass 1:** Extract and score all entities from complete document
- `synthesis_pass.py` - **Pass 2:** Generate world-class long summary
- `taste_filter.py` - **Pass 1.5a:** Vector-based style validation
- `truth_critic.py` - **Pass 1.5b:** LLM-based logic validation

##### PROCESSORS/TWO_PASS/PROMPTS/

**Active prompts (3 prompts)**

- `extraction_pass.txt` - Pass 1 extraction prompt (whole-document, 6-dimension scoring)
- `synthesis_pass.txt` - Pass 2 synthesis prompt (dynamic length, thematic organization)
- `truth_critic.txt` - Pass 1.5b prompt (reasoning-first validation)

#### PROCESSORS/CLAIMS_FIRST/

**Claims-first pipeline module (December 2025)**

- `__init__.py` - Module initialization
- `config.py` - ClaimsFirstConfig dataclass
- `transcript_fetcher.py` - YouTube/Whisper transcript abstraction
- `timestamp_matcher.py` - Fuzzy matching evidence quotes to timestamps
- `lazy_speaker_attribution.py` - Targeted LLM-based speaker attribution
- `pipeline.py` - ClaimsFirstPipeline orchestrator

**DELETED (Jan 17, 2026):**
- ~~`processors/hce/`~~ - **Entire legacy HCE system deleted** (33 files, segment-based extraction)
- ~~`processors/question_mapper/`~~ - **Entire question mapper deleted** (10 files, GUI-only feature)

### SERVICES/

**Business logic services**

- `__init__.py` - Services module initialization
- `browser_cookie_manager.py` - Loads YouTube cookies from system browsers
- `claims_upload_service.py` - Upload claims to cloud storage
- `device_auth.py` - Device authentication for GetReceipts.org (Happy-style)
- `prediction_service.py` - Personal forecasting system business logic
- `download_base.py` - Base download service class
- `download_scheduler.py` - Download queue management
- `file_generation.py` - Generate output files from database
- `multi_account_downloader.py` - Multi-account YouTube downloader
- `oauth_callback_server.py` - OAuth callback server
- `playwright_youtube_scraper.py` - YouTube AI summary scraper (Playwright-based)
- `podcast_episode_searcher.py` - Search for podcast episodes
- `podcast_rss_downloader.py` - Download podcast episodes from RSS
- `prompt_sync.py` - Syncs approved prompt refinements from GetReceipts.org
- `entity_sync.py` - **UNIFIED sync service** for all entity types (claims, jargon, people, concepts, predictions, health)
- `feedback_config.py` - **NEW (Jan 2026):** Singleton config loader for feedback reasons
- `taste_engine.py` - **NEW (Jan 2026):** ChromaDB-based semantic feedback storage for Dynamic Learning
- `rae_service.py` - **NEW (Jan 17, 2026):** RAE service for channel-specific knowledge injection
- `queue_snapshot_service.py` - Queue snapshot service
- `session_based_scheduler.py` - Session-based download scheduler (anti-bot)
- `speaker_learning_service.py` - Speaker learning and adaptation
- `supabase_auth.py` - Supabase authentication
- `supabase_storage.py` - Supabase cloud storage operations
- `supabase_sync.py` - Supabase synchronization service
- `transcript_acquisition_orchestrator.py` - Two-phase transcript acquisition
- `transcript_manager.py` - Multi-transcript management
- `two_stage_download_coordinator.py` - Separates metadata fetching from audio downloads
- `unified_download_orchestrator.py` - Unified download orchestrator (YouTube, RSS, local)
- `wikidata_categorizer.py` - WikiData-based categorization
- `youtube_data_api.py` - Official YouTube Data API v3 wrapper
- `youtube_download_service.py` - YouTube download service
- `youtube_video_matcher.py` - YouTube video matcher for PDF transcripts
- `youtube_to_podcast_mapper.py` - Map YouTube URLs to podcast RSS feeds

### SUPERCHUNK/

**SuperChunk system for advanced document processing (experimental)**

20+ modules for advanced document processing pipeline (experimental feature, not used by daemon).

### UTILS/

**Utility functions and helpers (94+ files)**

- `__init__.py` - Utils module initialization
- `ad_detector.py` - Advertisement detection in transcripts
- `deduplication.py` - URL and source deduplication
- `llm_speaker_suggester.py` - LLM-based speaker name suggestion
- `llm_speaker_validator.py` - LLM-based speaker name validation
- `model_metadata.py` - Model access metadata database (status badges for 50+ models)
- `model_registry.py` - Dynamic LLM model registry with multi-tier fetching
- `model_registry_api.py` - Model registry API with OpenRouter, Google Gemini, Anthropic
- `rss_feed_extractor.py` - Extract RSS feeds from Apple Podcasts/RSS.com URLs
- `warning_suppressions.py` - Centralized warning suppression
- `youtube_metadata_validator.py` - Universal metadata validator for YouTube Data API and yt-dlp
- `video_id_extractor.py` - YouTube video ID extraction
- Plus 80+ additional utility modules

#### UTILS/PROXY/

**Proxy management utilities**

- `base_provider.py` - Base proxy provider class
- `direct_provider.py` - Direct connection (no proxy)
- `packetstream_provider.py` - PacketStream proxy implementation

**DELETED (Jan 17, 2026):**
- ~~`anyip_provider.py`~~ - Stub implementation (never completed)
- ~~`brightdata_provider.py`~~ - Stub implementation (never completed)
- ~~`gonzoproxy_provider.py`~~ - Stub implementation (never completed)
- ~~`oxylabs_provider.py`~~ - Stub implementation (never completed)

### SCHEMAS/

**Pydantic models for standardized data structures**

- `__init__.py` - Schemas module initialization
- `transcription_output.py` - Standardized JSON output schema for transcription pipeline

### WORKERS/

**Background worker processes**

- `__init__.py` - Workers module initialization
- `feedback_processor.py` - **NEW (Jan 2026):** Async feedback processing worker (polls pending queue, updates ChromaDB)

**DELETED (Jan 17, 2026):**
- ~~`voice/`~~ - **Entire voice fingerprinting system deleted** (deprecated in v4.0.0)

---

## TESTS/

**Comprehensive test suite (70+ test files)**

- `test_multi_profile_scorer.py` - Multi-profile scoring tests
- `test_flagship_evaluator_v2.py` - Flagship evaluator V2 tests
- `test_health_tracking.py` - Health tracking system tests
- `test_taste_engine.py` - TasteEngine unit tests
- `test_taste_filter.py` - TasteFilter integration tests
- `test_truth_critic.py` - TruthCritic unit tests
- `test_feedback_processor.py` - FeedbackProcessor integration tests
- `test_rae_integration.py` - **NEW (Jan 17, 2026):** RAE system end-to-end tests
- `test_question_mapper.py` - Question mapper tests (14 tests)
- `test_database_imports.py` - Database export validation
- `test_basic.py` - Basic functionality tests
- Plus 60+ additional test modules

---

## CONFIG/

**Application configuration files**

### Prompt Templates

- `prompts/create_moc_prompt.txt` - Maps of Content generation
- `prompts/document_summary_prompt.txt` - Document summarization
- `prompts/episode_summary_prompt.txt` - Episode summarization

### Configuration Files

- `settings.yaml` - Main application settings (user-specific, not in git)
- `settings.example.yaml` - Example settings file
- `credentials.yaml` - API credentials (user-specific, not in git)
- `credentials.example.yaml` - Example credentials template
- `speaker_attribution.yaml` - 262+ podcast-to-host mappings
- `youtube_scraper.yaml` - YouTube AI summary scraper configuration
- `channel_hosts.csv` - YouTube channels to host names mapping

### OAuth and Authentication

- `client_secret_*.json` - Google OAuth client secret
- `youtube_oauth2_credentials.json` - YouTube OAuth2 credentials

---

## DATA/

**Data storage directory**

- `knowledge_system.db` - **Main SQLite database** (media sources, transcripts, claims, summaries, questions)
- `README.md` - Data directory documentation
- `wikidata_categories.txt` - WikiData category list

---

## DOCS/

**Comprehensive project documentation (128+ files)**

### Feature Flowcharts

- `feature-flowchart.md` - Mermaid source for feature availability
- `feature-flowchart.html` - Interactive HTML with rendered diagrams
- `web-ui-wireframes.html` - Interactive wireframes for GetReceipts UI

### Architecture Documentation

- `ARCHITECTURE_UNIFIED.md` - High-level system architecture
- `CLAIM_CENTRIC_ARCHITECTURE.md` - Claim-centric database architecture
- `DATABASE_ARCHITECTURE.md` - Database schema and design
- `DATABASE_CENTRIC_ARCHITECTURE.md` - Database-first design principles
- `PIPELINE_ARCHITECTURE.md` - Processing pipeline architecture
- `DATABASE_PATTERNS.md` - Common database access patterns

### Feature Documentation

- `AUTOMATIC_COOKIE_DETECTION.md` - Automatic cookie detection
- `DEDUPLICATION_SYSTEM.md` - URL and source deduplication
- `MODEL_ACCESS_UX.md` - Model access validation system
- `SPEAKER_ATTRIBUTION.md` - Speaker attribution system
- `YOUTUBE_DOWNLOAD.md` - YouTube download system
- Plus 100+ additional documentation files

### Testing Documentation

- `TESTING_STRATEGY.md` - Overall testing strategy
- `AUTOMATED_TESTING_GUIDE.md` - Automated testing guide
- `GUI_TESTING.md` - GUI testing methodology (historical)
- `INTEGRATION_TESTING.md` - Integration test documentation

### System Maintenance

- `YT_DLP_UPGRADE_PROCEDURE.md` - yt-dlp upgrade procedure
- `YT_DLP_MONITORING_GUIDE.md` - yt-dlp release monitoring
- `TROUBLESHOOTING_DAEMON_VERSION.md` - Daemon version mismatch troubleshooting
- `DAEMON_RELEASE_PROCESS.md` - Complete daemon release workflow

---

## SCRIPTS/

**Utility scripts (237 files)**

Key scripts:
- `release_daemon.sh` - **Generic daemon release script** (auto-detects version)
- `complete_release.sh` - Complete release for daemon + website
- `bundle_deno.sh` - Downloads and packages Deno runtime
- `silent_deno_installer.py` - Installs Deno into app bundle
- `import_pdf_transcripts_batch.py` - Batch import PDF transcripts
- `bump_version.py` - Version bumping utility
- `update_build_date.sh` - Update build date in documentation
- Plus 230+ additional scripts for migrations, fixes, testing, and utilities

---

## OUTPUT/

**Generated output files from processing**

Organized by type in subdirectories:
- `transcripts/` - Transcript markdown files
- `summaries/` - Claims analysis results
- `moc/` - Maps of Content
- `exports/` - SRT, VTT, JSON exports
- `downloads/youtube/` - Downloaded media files

---

## SCHEMAS/

**JSON schemas for data validation**

- `claim_schema.json` - Claim objects
- `episode_schema.json` - Episode metadata
- `flagship_input.v1.json` - Flagship evaluator input
- `flagship_output.v2.json` - Flagship evaluator output (6-dimension multi-profile scoring)
- `miner_input.v1.json` - Unified miner input
- `miner_output.v1.json` - Unified miner output
- `segment_schema.json` - Transcript segments
- `source_schema.json` - Media source metadata
- `summary_schema.json` - Summary objects

---

## ASSETS/

**Application assets**

- `STP_Icon_1.ico` - Application icon (ICO format)
- `STP_Icon_1.jpeg` - Application icon (JPEG format)
- `STP_Icon_1.jpg` - Application icon (JPG format)
- `STP_Icon_1.png` - Application icon (PNG format)
- `STP_Icon_1.psd` - Adobe Photoshop source file

---

## DEPRECATED & REMOVED

### Deleted in January 2026 Cleanup

**Total Removed:** 177 files, 66,563 lines of code, 2.2MB

#### _deprecated/ Directory (131 files)
- All PyQt6 GUI components, tabs, dialogs, workers
- Layer cake GUI implementation
- Old extractors and prompts
- GUI-related documentation

#### Deprecated Processing Systems (46 files)
- `processors/hce/` - Legacy HCE extraction system (33 files)
- `processors/question_mapper/` - Question mapper system (10 files, GUI-only)
- `voice/` - Voice fingerprinting system (1 file)
- `core/segment_processor.py` - Segment processor
- `core/system2_orchestrator.py` - Old orchestrator

#### Experimental/Unused Code
- `dual_summary_processor.py` - Never completed
- `compare_youtube_summaries.py` - Test script
- Stub proxy providers (anyip, brightdata, gonzoproxy, oxylabs)

### Deprecated Dependencies
- **Streamlit** - Web UI (replaced by GetReceipts.org)
- **PyQt6** - Desktop GUI (replaced by web interface)
- **Diarization extras** - torch, transformers, pyannote.audio (replaced by claims-first)
- **HCE extras** - sentence-transformers (replaced by two-pass)

---

## ACTIVE DEPENDENCIES

### Core Framework
- click, pydantic, pydantic-settings, pyyaml, loguru, rich

### File Processing
- watchdog, pypdf2, pdfplumber, beautifulsoup4, playwright

### YouTube & Video
- yt-dlp==2025.11.12 (requires Deno, bundled in DMG)
- requests, youtube-transcript-api

### ML & Transcription
- pywhispercpp (whisper.cpp Python binding)
- pydub (audio processing)

### LLM APIs
- openai, anthropic, google-genai

### Data & Storage
- sqlalchemy, pandas, chromadb (Dynamic Learning)

### Utilities
- python-dotenv, psutil, httpx (RAE)

### Optional
- **cuda**: nvidia-ml-py (GPU info)

---

## KEY WORKFLOWS

### 1. Video Processing (via Web UI)

```
User visits GetReceipts.org/contribute
  ↓
Submits YouTube URL to daemon
  ↓
Daemon downloads, transcribes, extracts
  ↓
Auto-uploads to GetReceipts.org
  ↓
User reviews results in web interface
```

### 2. Daemon Installation

```
Download PKG from GitHub releases
  ↓
Run installer (creates LaunchAgent)
  ↓
Desktop app created: ~/Desktop/GetReceipts Daemon.app
  ↓
Daemon auto-starts on login
  ↓
Web UI detects daemon at localhost:8765
```

### 3. Two-Pass Extraction Pipeline

```
Pass 1: Extraction (extraction_pass.py)
  ↓ Extracts claims, jargon, people, concepts
  ↓ Scores with 6-dimension system
  ↓
Pass 1.5a: Taste Filter (taste_filter.py)
  ↓ Vector similarity to accepted/rejected examples
  ↓ Auto-discard or boost based on style
  ↓
Pass 1.5b: Truth Critic (truth_critic.py)
  ↓ LLM validation of high-importance entities
  ↓ Factual accuracy and categorization check
  ↓
Pass 1.5c: Evolution Detector (claim_evolution_detector.py)
  ↓ RAE-based duplicate/contradiction detection
  ↓ Links evolutions, flags contradictions
  ↓
Pass 2: Synthesis (synthesis_pass.py)
  ↓ Generates world-class long summary
  ↓ Dynamic length based on content complexity
```

---

## VERSION HISTORY

**Current:** 4.1.0 (Daemon-Only Architecture)  
**Daemon:** 1.1.x (Active development)  
**Previous:** 4.0.0 (Claims-first migration), 3.5.0 (Two-pass system)

---

## TESTING

### Test Commands

```bash
make test          # Full test suite
make test-quick    # Fast unit tests (~30s)
make test-daemon   # Daemon-specific tests
make smoke-test    # Basic functionality
```

### Test Coverage
- Unit tests for all major components
- Integration tests for end-to-end workflows
- Daemon API tests
- Performance tests
- Database migration tests

---

## DEVELOPMENT COMMANDS

```bash
make install              # Install deps + pre-commit hooks
make dependencies-check   # Verify critical dependencies
make test                 # Full test suite
make test-quick          # Fast unit tests
make lint                # Linting (flake8)
make format              # Auto-format (black + isort)
make security-check      # Security scan (bandit)
make build               # Build distribution packages
make clean               # Remove build artifacts
```

---

## DEPLOYMENT

### Daemon Releases
1. Bump version: `python3 scripts/bump_version.py --part patch|minor|major`
2. Run release script: `~/Desktop/Release_Daemon.command`
3. Script handles: build, sign, notarize, GitHub release, commit, push

### Distribution
- **Platform:** macOS only
- **Format:** Signed & notarized PKG installer
- **Auto-update:** Built-in update checker (checks GitHub releases every 24 hours)
- **Installation:** ~/Library/Application Support/SkipThePodcast/

---

## CONTACT & LINKS

- **Production:** https://getreceipts.org
- **GitHub:** https://github.com/msg43/Knowledge_Chipper
- **Issues:** GitHub Issues
- **License:** MIT

---

*This manifest is a living document. Last comprehensive update: January 17, 2026 (post-cleanup)*
