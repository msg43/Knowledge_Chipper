# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Feature - PDF Transcript Import System (December 25, 2025)

**Import podcaster-provided transcripts with automatic YouTube matching**

#### New Features

- **PDF Transcript Import**: Import high-quality PDF transcripts from podcasters
  - Automatic speaker label detection (multiple formats supported)
  - Timestamp parsing (multiple formats)
  - Quality scoring based on speaker labels, timestamps, formatting
  - Metadata extraction (title, date, speakers)
- **Multi-Transcript Management**: Store multiple transcript versions per episode
  - PDF (podcaster-provided), YouTube API, Whisper transcripts coexist
  - Configurable priority order (pdf_provided > youtube_api > whisper)
  - Automatic quality-based selection
  - Per-source preferred transcript tracking
- **YouTube Video Matching**: Automatic matching of PDFs to YouTube videos
  - 4 matching strategies: database fuzzy match, title search, metadata search, LLM query
  - Confidence scoring (0-100%)
  - Manual review for low-confidence matches
  - Playwright-based YouTube search with fallback
- **Import Transcripts Tab**: New GUI tab for PDF import
  - Single PDF import with optional YouTube URL
  - Batch folder scanning
  - Auto-match toggle with confidence threshold
  - Results table with match status
  - Real-time progress tracking
- **Batch Import Script**: CLI tool for bulk PDF import
  - Folder scanning support
  - CSV mapping file support (pdf_path, youtube_url)
  - Configurable confidence threshold
  - Progress reporting and statistics

#### Architecture Improvements

- **Two-Pass Integration**: PDF transcripts work seamlessly with two-pass workflow
- **Quality-Based Selection**: System automatically uses highest-quality transcript
- **Database Schema**: Added quality_score, has_speaker_labels, has_timestamps, preferred_transcript_id fields
- **Transcript Priority**: Configurable in config.yaml

#### Files Added

- `src/knowledge_system/database/migrations/add_pdf_transcript_support.sql`
- `src/knowledge_system/processors/pdf_transcript_processor.py`
- `src/knowledge_system/services/youtube_video_matcher.py`
- `src/knowledge_system/services/transcript_manager.py`
- `src/knowledge_system/gui/tabs/import_transcripts_tab.py`
- `scripts/import_pdf_transcripts_batch.py`
- `tests/test_pdf_transcript_import.py`
- `PDF_TRANSCRIPT_IMPORT_IMPLEMENTATION_COMPLETE.md`
- `GUI_INTEGRATION_COMPLETE.md`

#### Files Modified

- `src/knowledge_system/database/models.py` - Extended Transcript and MediaSource models
- `src/knowledge_system/database/service.py` - Added transcript management methods
- `src/knowledge_system/processors/two_pass/pipeline.py` - Integrated TranscriptManager
- `src/knowledge_system/config.py` - Added TranscriptProcessingConfig
- `src/knowledge_system/gui/main_window_pyqt6.py` - Added Import Transcripts tab
- `src/knowledge_system/gui/tabs/__init__.py` - Exported new tab

### Feature - YouTube Data API v3 Integration (December 25, 2025)

**Official YouTube API for reliable metadata, yt-dlp for audio only**

#### New Features

- **YouTube Data API Service**: Official API wrapper for metadata fetching
  - Single video metadata fetch (1 quota unit)
  - Batch metadata fetch (50 videos per request, 1 quota unit)
  - Video search functionality (100 quota units)
  - Automatic quota tracking (10,000 free units/day)
  - Quota reset handling
  - API key validation
- **Metadata Validator**: Universal validator for both API and yt-dlp
  - Format conversion (ISO 8601 duration → seconds, dates → YYYYMMDD)
  - Type validation and coercion
  - String sanitization
  - Default values for missing fields
  - Handles both API and yt-dlp response formats
- **Audio Linking Methods**: Robust audio-to-metadata linking
  - `link_audio_to_source()` - Link downloaded audio to existing metadata
  - `verify_audio_metadata_link()` - Comprehensive verification
  - File existence validation
  - File size validation (minimum 200KB)
  - Diagnostic reporting
- **Two-Stage Download Coordinator**: Metadata-first workflow
  - Stage 1: Fetch all metadata via API (fast, batch-optimized)
  - Stage 2: Download audio via yt-dlp (only for new videos)
  - Deduplication before download
  - Automatic fallback to yt-dlp for metadata if API unavailable

#### Architecture Improvements

- **Separation of Concerns**: Metadata (API) separate from audio (yt-dlp)
- **Reliability**: API guarantees JSON structure, no parsing errors
- **Speed**: API is faster than web scraping, batch requests are 50x more efficient
- **Robustness**: Audio failures don't lose metadata
- **Quota Efficiency**: Batch optimization maximizes free tier

#### Files Added

- `src/knowledge_system/services/youtube_data_api.py` - API wrapper
- `src/knowledge_system/utils/youtube_metadata_validator.py` - Validation layer
- `src/knowledge_system/services/two_stage_download_coordinator.py` - Orchestrator
- `tests/test_youtube_data_api.py` - API tests
- `tests/test_metadata_validator.py` - Validator tests
- `YOUTUBE_DATA_API_INTEGRATION_COMPLETE.md`

#### Files Modified

- `src/knowledge_system/config.py` - Added YouTubeAPIConfig
- `src/knowledge_system/database/service.py` - Added audio linking methods
- `src/knowledge_system/services/youtube_video_matcher.py` - Integrated API with Playwright fallback

#### Configuration

```yaml
youtube_api:
  enabled: true
  api_key: "YOUR_API_KEY"  # From Google Cloud Console
  quota_limit: 10000
  fallback_to_ytdlp: true
  batch_size: 50
```

### Feature - Two-Phase Transcript Acquisition (December 25, 2025)

**10-100x faster transcript acquisition for YouTube playlists**

#### New Features

- **TranscriptAcquisitionOrchestrator**: New unified orchestrator with two-phase workflow
  - Phase 1: Rapid metadata + transcript fetch (1-3 second delays, burst pattern)
  - Phase 2: Selective Whisper fallback (3-5 minute delays, only for videos without transcripts)
- **Force Whisper checkbox**: User control to skip YouTube API and force Whisper transcription
  - Added to Transcription Tab and Batch Processing Tab
  - Warning indicator shows when slow mode is enabled
- **Database tracking**: New `transcript_source` field tracks origin (youtube_api, whisper_fallback, whisper_forced)
- **Settings persistence**: Force Whisper preference saved across sessions

#### Architecture Improvements

- **Clean orchestration**: Single clear path for transcript acquisition
- **Intelligent pacing**: Fast for metadata (mimics human browsing), slow only when downloading audio
- **Database-centric**: All metadata stored immediately in Phase 1
- **No redundant code**: Deleted unused `unified_download_orchestrator_v2.py`

#### Files Added

- `src/knowledge_system/services/transcript_acquisition_orchestrator.py` - New two-phase orchestrator
- `src/knowledge_system/database/migrations/add_transcript_source.sql` - Database migration

#### Files Modified

- `src/knowledge_system/database/models.py` - Added `transcript_source` field to Transcript model
- `src/knowledge_system/gui/tabs/transcription_tab.py` - Added Force Whisper checkbox and settings
- `src/knowledge_system/gui/tabs/batch_processing_tab.py` - Added Force Whisper checkbox
- `src/knowledge_system/gui/core/settings_manager.py` - Added force_whisper settings support

#### Files Removed

- `src/knowledge_system/services/unified_download_orchestrator_v2.py` - Unused V2 orchestrator (replaced)

#### Benefits

- 10-100x faster for playlists with available YouTube transcripts
- User control via Force Whisper checkbox for quality preference
- Clean codebase with no orphaned orchestrator code
- Intelligent pacing mimics human behavior patterns

---

### Feature - Auto-Sync with Close Protection (December 22, 2025)

**Prevents data loss with automatic syncing and close warnings**

#### New Features

- **Auto-sync on accept**: Items automatically sync to GetReceipts in background immediately after acceptance
- **Close warning**: Prevents closing app with unsynced accepted items (Save/Discard/Cancel options)
- **Sync status indicator**: Real-time feedback in dashboard (Syncing.../Synced ✓/Queued for sync)
- **Offline support**: Can review items offline, queues for sync when online
- **Manual sync button**: Retained for batch sync and retry of failed items

#### User Experience

- Accept item → Auto-syncs in 2-3 seconds → Appears on web immediately
- Work offline → Items queue → Manual sync uploads all when online
- Try to close with unsynced items → Warning dialog → Choose to save/discard/cancel
- Visual feedback → Dashboard shows sync status in real-time

#### Files Modified

- **NEW:** `src/knowledge_system/gui/workers/auto_sync_worker.py` - Background sync worker
- `src/knowledge_system/gui/tabs/extract_tab.py` - Auto-sync triggers, unsynced tracking
- `src/knowledge_system/gui/components/review_dashboard.py` - Sync status indicator
- `src/knowledge_system/gui/components/review_queue.py` - Remove item by ID method
- `src/knowledge_system/gui/main_window_pyqt6.py` - Close warning dialog
- `src/knowledge_system/database/review_queue_service.py` - is_item_synced() method

#### Benefits

- No data loss - items sync immediately
- Offline capable - queue for sync when online
- Standard UX - follows Gmail/Slack patterns
- Fail-safe - close warning catches missed syncs
- Non-blocking - background sync doesn't interrupt workflow

---

### UI - Extract Tab Improvements (December 22, 2025)

**Cleaner, more compact UI with better dark theme consistency**

#### Changes

- **Consistent dark theme**: All white backgrounds changed to dark gray (#2d2d2d, #3c3c3c)
- **Removed Tier filter**: Simplified filter bar (Type, Source, Status, Search only)
- **Renamed "Video" to "Source"**: More accurate terminology, properly references all sources
- **Compact review status**: Inline text instead of large stat cards (60% space reduction)
- **Dual progress bars**: Current file progress (blue) + batch progress (green)

#### Files Modified

- `gui/components/review_dashboard.py` - Redesigned with inline status and dual progress bars
- `gui/components/filter_bar.py` - Removed tier filter, renamed Video→Source
- `gui/components/review_queue.py` - Dark theme backgrounds
- `gui/components/enhanced_progress_display.py` - Dark theme backgrounds
- `gui/tabs/extract_tab.py` - Dark theme dialog, update sources on item add

#### New Dashboard Layout

```
📊 Processing: 0/0 videos  0 items extracted  Pending: 80 | Accepted: 0 | Rejected: 0
Current: [████████░░░░░░░░░░░░] Extracting...
Batch:   [███░░░░░░░░░░░░░░░░░] 15%
```

---

### Major - Speaker Attribution Simplification (December 22, 2025)

**Removed complex diarization system in favor of LLM-based speaker inference**

#### Breaking Changes

- **Deprecated diarization system**: pyannote.audio, voice fingerprinting, and speaker learning system no longer used
- **Removed `segments.speaker` column**: Speaker attribution now at entity level (claims, jargon, concepts)
- **Unified workflow**: All content (YouTube + audio) processed identically through Pass 1 LLM

#### New Features

- **Entity-level speaker attribution**: Added `claims.speaker`, `jargon_terms.introduced_by`, `concepts.advocated_by` fields
- **Web-based claim merging**: Added `claims.cluster_id` and `claims.is_canonical_instance` for manual deduplication in web interface
- **LLM speaker inference**: Pass 1 extraction now infers speakers from content (more accurate than audio analysis)
- **Simplified workflow**: One unified path for all content types

#### Database Changes

- Added `claims.speaker TEXT` - Who made this claim (from Pass 1 LLM)
- Added `claims.cluster_id TEXT` - For grouping duplicate claims in web interface
- Added `claims.is_canonical_instance BOOLEAN` - Primary version in merged cluster
- Added `jargon_terms.introduced_by TEXT` - Who first used/explained the term
- Added `concepts.advocated_by TEXT` - Who advocates for this mental model
- Migration script: `2025_12_22_add_speaker_to_entities.sql`

#### Performance Improvements

- **40-80 seconds faster** per video (no diarization overhead)
- **377MB smaller install** (removed torch/transformers dependencies)
- **Simpler codebase** (removed 5+ files, 7+ database tables)

#### Benefits

- **More accurate**: Content-based speaker inference beats audio diarization
- **Unified workflow**: YouTube and audio files processed identically
- **Better UX**: Web-based manual merging with full context (~100 claims per speaker)
- **Easier maintenance**: No complex audio processing stack

#### Files Modified

- `src/knowledge_system/database/models.py` - Added speaker fields to entities
- `src/knowledge_system/database/claim_store.py` - Extract speaker from Pass 1 LLM
- `src/knowledge_system/database/migrations/claim_centric_schema.sql` - Removed segments.speaker
- `DIARIZATION_DEPRECATED.md` - NEW: Deprecation notice and migration guide
- `SPEAKER_ATTRIBUTION_SIMPLIFICATION_COMPLETE.md` - NEW: Complete implementation summary

#### Migration Notes

- Existing claims migrated from `segments.speaker` (best effort)
- Diarization files marked deprecated but not yet removed
- Future phases will remove diarization code and dependencies

---

### Major - Bulk Review Workflow for Extract Tab (December 22, 2025)

**Complete redesign of Extract Tab with industry-standard bulk review patterns**

#### New Features

- **Review Dashboard**: Collapsible stats panel showing real-time processing progress (videos processed, items extracted) and review status (pending/accepted/rejected counts)
- **Unified Review Queue**: Single QTableView replacing the 5 separate tab-based lists, with columns for Type, Content, Source, Tier, Importance, and Status
- **Filter Bar**: Horizontal filter controls for Type (Claim/Jargon/Person/Concept), Video/Source, Status (Pending/Accepted/Rejected), Tier (A/B/C/D), and text search
- **Bulk Action Toolbar**: Gmail-style toolbar that appears when items are selected, with Accept All, Reject All, Set Tier, Select All Visible, Select All Pending actions
- **Enhanced Detail Panel**: Accept/Reject/Skip buttons with Previous/Next navigation for rapid single-item review
- **Confirm & Sync Dialog**: Summary dialog showing counts of accepted/rejected/pending items before pushing to GetReceipts

#### Keyboard Shortcuts

- `A` - Accept current item and move to next
- `R` - Reject current item and move to next
- `J/K` - Navigate to next/previous item
- `Space` - Toggle selection of current item
- `Escape` - Deselect all
- `/` - Focus search box
- `Ctrl+Enter` - Open Confirm & Sync dialog

#### New Components

- `gui/components/review_dashboard.py` - Progress and stats dashboard
- `gui/components/review_queue.py` - Unified queue model, filter model, and view
- `gui/components/filter_bar.py` - Horizontal filter controls
- `gui/components/bulk_action_toolbar.py` - Selection-aware bulk actions
- `database/review_queue_service.py` - Database persistence service for review items
- `database/migrations/2025_12_22_review_queue.sql` - Review queue table schema

#### Database Persistence

- Review items persist across sessions until explicitly synced to GetReceipts
- On tab open, loads all pending and unsynced items from previous sessions
- Status changes (accept/reject) are saved immediately to database
- Synced items marked with `synced_at` timestamp and removed from queue

#### UI/UX Patterns Adopted

Based on research of content moderation tools (Admation, Moxo, Filestage), data labeling platforms (Label Studio, Prodigy), and bulk action UIs (Gmail, Notion, Airtable):
- Tri-state checkbox selection
- Sticky bulk action bar
- Color-coded status pills
- Virtual scrolling for 10K+ items
- Confirmation gates for destructive bulk actions

### Major - Two-Pass Architecture Migration (December 22, 2025)

**BREAKING CHANGE: Complete architectural overhaul from two-step to two-pass system**

#### What Changed

Migrated from the legacy two-step (mining + evaluator) system to a modern two-pass (extraction + synthesis) architecture. This is a fundamental change in how the system processes content.

**Old System (Two-Step):**
- Transcript → Split into segments → Mine each segment → Evaluate all claims → Store
- Multiple LLM calls per video
- Fragmented claims across segment boundaries
- Lost context

**New System (Two-Pass):**
- Transcript (complete) → Pass 1: Extract & Score → Pass 2: Synthesize Summary → Store
- Only 2 LLM calls per video
- Whole-document processing
- Preserves complete argument structures

#### Files Removed (18 files, ~6,452 lines)

**Segment-Based Two-Step:**
- `src/knowledge_system/core/system2_orchestrator_mining.py`
- `src/knowledge_system/core/batch_pipeline.py`
- `src/knowledge_system/processors/hce/unified_pipeline.py`
- `src/knowledge_system/processors/hce/unified_miner.py`
- `src/knowledge_system/processors/hce/flagship_evaluator.py`
- `src/knowledge_system/processors/hce/evaluators/jargon_evaluator.py`
- `src/knowledge_system/processors/hce/evaluators/people_evaluator.py`
- `src/knowledge_system/processors/hce/evaluators/concepts_evaluator.py`

**Whole-Document Two-Step:**
- `src/knowledge_system/processors/claims_first/` (entire directory)

#### Files Created (9 files, ~2,325 lines)

**Two-Pass System:**
- `src/knowledge_system/processors/two_pass/__init__.py`
- `src/knowledge_system/processors/two_pass/extraction_pass.py` - Pass 1 implementation
- `src/knowledge_system/processors/two_pass/synthesis_pass.py` - Pass 2 implementation
- `src/knowledge_system/processors/two_pass/pipeline.py` - Orchestrator
- `src/knowledge_system/processors/two_pass/prompts/extraction_pass.txt`
- `src/knowledge_system/processors/two_pass/prompts/synthesis_pass.txt`
- `src/knowledge_system/core/system2_orchestrator_two_pass.py` - Integration

#### Benefits

1. **Simpler Codebase**: Net -4,127 lines of code
2. **Faster Processing**: Only 2 API calls vs. many
3. **Better Quality**: Whole-document context preserved
4. **Lower Cost**: Fewer API calls, fewer tokens
5. **Absolute Scoring**: Importance scores (0-10) globally comparable
6. **Speaker Inference**: Built-in without diarization
7. **World-Class Summaries**: Thematic narrative synthesis

#### Breaking Changes

- `ClaimsFirstWorker` renamed to `TwoPassWorker` (backward compatibility alias maintained)
- Configuration changed: `miner_model` + `evaluator_model` → single `llm_model`
- No more tier-based ranking (A/B/C) - use importance scores instead
- GUI stages reduced from 6 to 4

#### Migration

See `TWO_PASS_MIGRATION_COMPLETE.md` for full details.

Rollback checkpoint: `checkpoint-before-two-step-removal` (commit 66371a3)

### Performance - Cloud API Mining Optimization (December 21, 2025)

**MASSIVE SPEEDUP: 7.5x faster claim mining for cloud APIs (Anthropic, OpenAI, Google)**

#### Problem
- Mining 80 segments with Claude Sonnet 4.5 took **30 minutes** (should be 2-3 minutes)
- Root causes:
  1. **Artificial concurrency limits**: Cloud APIs limited to 8 concurrent requests (designed for local Ollama, not cloud)
  2. **No segment batching**: Each segment = separate API call (80 calls × 22s latency = 30 min)
  3. **Conservative rate limits**: Set to 50 RPM when Anthropic allows 4,000 RPM

#### Solution
1. **Removed hardware tier limits for cloud APIs** (`llm_adapter.py`)
   - Before: 2-8 concurrent requests based on CPU (M1/M2/Ultra)
   - After: 100 concurrent requests (hardware-independent, limited by rate limiter)
   - Rationale: Cloud APIs are just HTTP requests - your CPU doesn't matter

2. **Implemented segment batching** (`unified_miner.py`)
   - Cloud APIs: 20 segments per API call (auto-detected)
   - Local Ollama: 1 segment per call (unchanged, optimized for GPU parallelization)
   - Reduces 80 API calls → 4 API calls (20x fewer roundtrips)

3. **Updated rate limiters to match provider limits**
   - Anthropic: 50 RPM → 1,000 RPM (actual limit: 4,000 RPM for paid tier)
   - OpenAI: 60 RPM → 500 RPM (actual limit: 3,500+ RPM for tier 2)
   - Google: 60 RPM → 1,000 RPM (actual limit: 1,500+ RPM for paid tier)

#### Performance Impact
- **Before**: 80 segments × 22s = 30 minutes
- **After**: 4 batches × 22s = **~90 seconds** (20x faster)
- **API calls per minute**: As many as hardware allows, up to provider's rate limit (1,000 RPM)

#### Files Modified
- `src/knowledge_system/core/llm_adapter.py`: Cloud concurrency limits and rate limiters
- `src/knowledge_system/processors/hce/unified_miner.py`: Batch mining logic with auto-detection

### Fixed

- **GitHub Actions Smoke Test** - Fixed failing smoke test workflow by adding missing lightweight dependencies
  - Added `pydantic-settings>=2.0.0` (required by `config.py`)
  - Added `rich>=13.0.0` (required by progress display utilities)
  - Added `sqlalchemy>=2.0.0` (required by database models)
  - Smoke test now successfully validates Python syntax and basic imports across Python 3.11, 3.12, and 3.13
  - Provides fast feedback (~2-3 minutes) on code quality without requiring heavy ML dependencies

### Added (Major Feature: YouTube AI Summary Integration)

- **YouTube AI Summary Scraping** - Automatically scrape YouTube's AI-generated summaries alongside local LLM processing
  - `PlaywrightYouTubeScraper` service for browser automation with cookie-based authentication
  - `BrowserCookieManager` loads YouTube cookies from Chrome/Safari/Firefox (reuses yt-dlp infrastructure)
  - `YouTubeDownloadWithAISummary` processor wraps existing download pipeline
  - Waits 12-60 seconds for complete summary generation (handles long videos)
  - Supports fuzzy timestamp matching with 6 regex patterns
  
- **Database Schema** (`database/migrations/add_youtube_ai_summary.sql`)
  - Added `youtube_ai_summary` TEXT column to `media_sources` table
  - Added `youtube_ai_summary_fetched_at` DATETIME column
  - Added `youtube_ai_summary_method` TEXT column ('playwright_scraper' or 'api')
  - Clear separation: `description` (source-provided), `youtube_ai_summary` (YouTube AI), `short_summary`/`long_summary` (Knowledge_Chipper LLM)
  
- **Markdown Output Enhancements** (`processors/audio_processor.py`)
  - Added "YouTube AI Summary" section to generated markdown files
  - Hyperlinked ALL timestamps throughout document (description, AI summary, transcript)
  - Supports timestamp formats: `(1:16-1:28)`, `[7:12]`, `**00:06**`, `00:00 //`, standalone chapters
  - Added note: "Click any timestamp to jump to that point in the video"
  
- **Standalone Scraper Tool** (`scrape_youtube_complete.py`)
  - Complete video data extraction: metadata + transcript + AI summary
  - Uses yt-dlp for rich metadata (23 tags, view count, duration, etc.)
  - Downloads thumbnail to Thumbnails/ directory
  - Title-based filenames (e.g., "China's Economic Prospects on the Cusp - George Magnus.md")
  - Outputs in Knowledge_Chipper standard format
  
- **Comparison Tools**
  - `compare_youtube_summaries.py` - Compare YouTube AI vs local LLM summaries
  - `test_youtube_ai_integration.py` - End-to-end pipeline integration test
  
- **Dependencies**
  - Added `playwright>=1.40.0` to requirements.txt and pyproject.toml
  - Installation script: `scripts/install_playwright.py`
  - Auto-installs Chromium browser (~50 MB) on first use

### Changed

- **AudioProcessor Markdown Generation**
  - Changed "YouTube Description" to "Description" (clearer for all source types)
  - Added YouTube AI Summary section (conditional on availability)
  - Hyperlinked timestamps in description and AI summary
  - Hyperlinked transcript timestamps for YouTube videos
  
- **Database Architecture Documentation**
  - Clarified purpose of each summary field:
    - `description`: Source-provided (YouTube desc, RSS notes, PDF abstract)
    - `youtube_ai_summary`: YouTube AI-generated (scraped)
    - `short_summary`: Knowledge_Chipper short (local LLM)
    - `long_summary`: Knowledge_Chipper long (local LLM)
  - Allows comparison testing between YouTube AI and Knowledge_Chipper summaries

### Technical Details

- **Browser Cookie Loading**: Reuses existing yt-dlp cookie infrastructure
- **Chrome Timestamp Bug Fix**: Converts Chrome's microsecond timestamps to seconds for Playwright
- **Fuzzy Timestamp Matching**: Context-aware regex patterns avoid false positives
- **Performance**: YouTube AI summary: ~15-20 seconds vs local LLM: ~2-5 minutes (10-20x faster)
- **Fallback**: Graceful degradation if YouTube AI unavailable (Premium required, region-locked)

### Added (Major Feature: 6-Dimension Multi-Profile Scoring)

- **Multi-Profile Scoring System** - Expanded from 5 to 6 dimensions with user archetype-based importance calculation
  - Added **Temporal Stability** dimension (1=ephemeral to 10=timeless)
  - Added **Scope** dimension (1=narrow to 10=universal)
  - Updated all 12 user profiles with 6-dimension weights
  - Profiles: Scientist, Philosopher, Educator, Student, Skeptic, Investor, Policy Maker, Tech Professional, Health Professional, Journalist, Generalist, Pragmatist
  
- **Flagship Evaluator V2** (`src/knowledge_system/processors/hce/flagship_evaluator.py`)
  - Integrated multi-profile scorer into evaluation pipeline
  - LLM evaluates 6 dimensions once, then arithmetic calculates 12 profile scores (zero marginal cost)
  - Max-scoring aggregation: final importance = max(all profile scores)
  - Rescues niche-but-valuable claims (high for at least one profile)
  - New `_process_multi_profile_scoring()` method
  
- **Updated Prompt** (`prompts/flagship_evaluator.txt`)
  - Requests 6 independent dimension scores instead of single importance
  - Detailed rubrics and examples for each dimension
  - Emphasizes scoring independence (don't conflate dimensions)
  
- **Schema V2** (`schemas/flagship_output.v2.json`)
  - Added `dimensions` object with 6 required fields
  - Added `profile_scores` object with 12 profile scores
  - Added `best_profile` field (which profile gave highest score)
  - Added `tier` field (A/B/C/D classification)
  - Backward compatible with V1 output
  
- **Database Migration** (`database/migrations/2025_12_22_multi_profile_scoring.sql`)
  - Added `dimensions` JSON column
  - Added `profile_scores` JSON column
  - Added `best_profile` TEXT column
  - Added `temporal_stability` REAL column (extracted for filtering)
  - Added `scope` REAL column (extracted for filtering)
  - Created indexes on `best_profile`, `temporal_stability`, `scope`, `tier`
  
- **Unit Tests** (`tests/test_multi_profile_scorer.py`)
  - Dimension validation (6 dimensions required)
  - Profile weight validation (all sum to 1.0)
  - Profile scoring arithmetic
  - Max-scoring rescues niche claims
  - Trivial claims still rejected
  - Temporal stability effects
  - Tier assignment
  
- **Integration Tests** (`tests/test_flagship_evaluator_v2.py`)
  - V2 output with dimensions and profile scores
  - Backward compatibility with V1 output
  - Tier distribution tracking
  - Profile distribution tracking

### Changed

- **Profile Weights** (`src/knowledge_system/scoring/profiles.py`)
  - Redistributed weights across 6 dimensions for all 12 profiles
  - All weights still sum to 1.0
  - Scientist now: 45% epistemic, 28% verifiability, 13% novelty, 8% temporal, 4% scope, 2% actionability
  - Investor now: 48% actionability, 23% verifiability, 13% epistemic, 8% novelty, 5% temporal, 3% scope
  
- **EvaluatedClaim Class** (`flagship_evaluator.py`)
  - Added `dimensions`, `profile_scores`, `best_profile`, `tier` properties
  - Maintains backward compatibility with V1 fields

### Technical Details

- **Cost Impact**: +50% LLM cost per claim (longer output), but zero marginal cost for adding profiles
- **Performance**: Profile scoring is pure arithmetic (<1ms for 12 profiles)
- **Scalability**: Adding 100 profiles costs the same as 1 profile (same LLM call)

## [4.0.0] - 2025-12-21

### Added (Major Architecture: Claims-First Pipeline)

This release introduces the **Claims-First Architecture**, a fundamental shift in how we process podcast content. Instead of the speaker-first approach (diarization → transcription → extraction), we now extract claims first from undiarized transcripts and only attribute speakers to high-value claims.

#### New Pipeline Components

- **Claims-First Pipeline** (`src/knowledge_system/processors/claims_first/`)
  - `TranscriptFetcher`: Unified interface for YouTube and Whisper transcripts
  - `TimestampMatcher`: Fuzzy matching of evidence quotes to timestamps
  - `LazySpeakerAttributor`: Targeted speaker attribution for A/B-tier claims only
  - `ClaimsFirstPipeline`: Main orchestrator for the new workflow
  - `ClaimsFirstConfig`: Configuration dataclass with validation

- **Database Schema Updates** (`database/migrations/2025_12_20_claims_first_support.sql`)
  - New columns: `timestamp_precision`, `transcript_source`, `speaker_attribution_confidence`
  - New table: `candidate_claims` for re-evaluation support
  - New table: `claims_first_processing_log` for tracking
  - New table: `extraction_checkpoints` for auth failure recovery

- **ClaimsFirstResult Enhancements** (`pipeline.py`)
  - `rejected_claims`: List of claims rejected by evaluator (visible for review)
  - `candidates_count`: Total candidates before evaluation
  - `acceptance_rate`: Ratio of accepted to total candidates
  - `quality_assessment`: Passive quality opinion with status, suggestion, thresholds
  - `promote_claim()`: Move rejected claims back through post-processing
  - `generate_summaries()`: Generate KC short/long summaries from all inputs

- **Authentication Failure Recovery** (`session_based_scheduler.py`)
  - `save_auth_failure_checkpoint()`: Save progress on 401/403/bot detection
  - `get_pending_checkpoint()`: Check for pending checkpoints
  - `resume_from_checkpoint()`: Resume from saved state
  - `is_auth_error()`: Detect auth-related errors

- **Configuration** 
  - New `claims_first` section in `config/settings.yaml`
  - New `ClaimsFirstConfig` in `config.py`
  - Configurable evaluator model selection (Gemini/Claude)

#### Updated Components

- **UnifiedMiner**: Now accepts plain text input (no speaker labels required)
  - New `mine()` method for claims-first mode
  - Text chunking with overlap for long transcripts
  - Output merging and deduplication

- **FlagshipEvaluator**: Added configurable model selection
  - New `evaluate_claims_simple()` convenience function
  - New `ConfigurableFlagshipEvaluator` with auto-upgrade

- **AudioProcessor**: Added claims-first flag
  - New `use_claims_first` parameter
  - New `process_claims_first()` method
  - Automatic diarization skip in claims-first mode

#### New Scripts

- `scripts/apply_claims_first_migration.py`: Database migration script
- `scripts/validate_claims_first.py`: Validation on test podcasts

#### Benefits

- **Faster Processing**: Skip diarization for YouTube content with good transcripts
- **Lower Cost**: Only attribute speakers to important claims (A/B tier)
- **Simpler Code**: Reduced dependency on pyannote/torch for new pipeline
- **Better Quality**: LLM-based speaker attribution using context

### Removed (Speaker-First Pipeline)

The following files have been **deleted** as part of the claims-first migration. 
The speaker-first code can be restored from Git if needed:
- **Git tag**: `v3.5.0-speaker-first-final`
- **Git branch**: `speaker-first-archive`

#### Deleted Processor Files
- `src/knowledge_system/processors/diarization.py` - Speaker diarization processor
- `src/knowledge_system/processors/speaker_processor.py` - Speaker assignment processor

#### Deleted Voice Processing Files  
- `src/knowledge_system/voice/voice_fingerprinting.py` - Acoustic voice fingerprinting
- `src/knowledge_system/voice/speaker_verification_service.py` - Speaker verification
- `src/knowledge_system/voice/accuracy_testing.py` - Voice accuracy testing

#### Deleted GUI Components
- `src/knowledge_system/gui/tabs/speaker_attribution_tab.py` - Speaker Attribution tab
- `src/knowledge_system/gui/dialogs/speaker_assignment_dialog.py` - Speaker assignment dialog
- `src/knowledge_system/gui/dialogs/batch_speaker_dialog.py` - Batch speaker dialog
- `src/knowledge_system/gui/dialogs/hce_update_dialog.py` - HCE update dialog

#### Deleted Utility Files
- `src/knowledge_system/utils/speaker_assignment_queue.py` - Speaker assignment queue

#### Modified Files (Speaker Features Disabled)
- `audio_processor.py` - Diarization calls return no-op with warning
- `transcription_tab.py` - Speaker assignment checkbox replaced with Claims-First toggle
- `model_preloader.py` - Diarization preloading is a no-op
- `queue_tab.py` - Stage names updated for claims-first pipeline

#### GUI Changes
- **NEW Extract Tab**: Dedicated tab for claims-first extraction with:
  - Two-pane editor layout (results list on left, detail editor on right)
  - LLM selection per stage (Miner provider/model, Evaluator provider/model)
  - 6-stage progress display with visual indicators
  - Quality assessment panel with acceptance rate and transcript quality
  - Rejected claims tab with "Promote" button
  - Re-run with Whisper fallback button
- **Queue Tab**: Updated stage names (Extract Claims, Evaluate Claims, Attribution)
- Removed deprecated diarization and speaker assignment UI elements

#### New GUI Components
- **PipelineProgressDisplay**: 6-stage progress widget for claims-first pipeline
- **ClaimsFirstWorker**: Background worker with pause/resume/cancel support
- **ClaimItem/EntityItem**: Custom list items for results display

#### Documentation
- New `CLAIMS_FIRST_MIGRATION_GUIDE.md` with step-by-step migration instructions

### Added (Web Episode Page Enhancements - GetReceipts.org)

The Episode page on GetReceipts.org now displays comprehensive claims-first data:

- **KC Short Summary**: Prominent 1-2 paragraph summary above the fold
- **KC Long Summary**: Expandable executive-level comprehensive analysis
- **YouTube AI Summary**: Collapsible section labeled as AI-generated
- **Chapter Timestamps**: Clickable navigation to video positions
- **Tags**: Badge display of episode categorization
- **Full Transcript**: Expandable with quality indicator and source type
- **Transcript Quality Score**: Visual indicator of transcript reliability

#### Supabase Migration (`026_claims_first_support.sql`)
- `short_summary`, `long_summary`, `yt_ai_summary` columns on media_sources
- `transcript_source`, `transcript_quality_score` columns
- `tags` JSONB array for categorization
- `episode_chapters` table for video navigation
- `extraction_checkpoints` table for auth failure recovery

### Added (Google Gemini LLM Support)

Comprehensive support for Google Gemini LLMs, matching existing support for OpenAI, Anthropic, and Ollama.

#### New Provider Support
- **GoogleProvider** in `src/knowledge_system/utils/llm_providers.py`
  - Full async support using `google-genai` package
  - Structured JSON output via response schema
  - Token estimation and rate limiting

- **LLM Adapter Integration** in `src/knowledge_system/core/llm_adapter.py`
  - `_call_google()` method for Gemini API calls
  - Default model: `gemini-2.0-flash`
  - Environment variable support: `GOOGLE_API_KEY` or `GEMINI_API_KEY`

#### Configuration
- New `google_api_key` field in `APIKeysConfig` (`src/knowledge_system/config.py`)
- Updated `pyproject.toml` and `requirements.txt` with `google-genai` dependency
- Model selection via `provider: "google"` and `model: "gemini-2.0-flash"` in config

#### Available Models
- `gemini-2.0-flash` (default) - Fast, efficient model
- `gemini-2.0-flash-exp` - Experimental features
- `gemini-1.5-pro` - Higher capability model
- `gemini-1.5-flash` - Balanced speed/quality

---

## [3.5.0] - Previous Release

### Changed (Major Refactor: Word-Driven Speaker Alignment)
- **Transcription Backend**: Replaced whisper.cpp subprocess calls with `pywhispercpp` Python binding
  - Uses DTW (Dynamic Time Warping) for accurate word-level timestamps
  - Cleaner Python integration with same performance as subprocess
  - Removed all subprocess command building and `_run_whisper_with_progress()` code

- **Speaker Alignment**: Now using pyannote-whisper's battle-tested word-driven alignment pattern
  - Assigns speaker labels at word midpoints (not segment boundaries)
  - Median filter smoothing eliminates single-word speaker flips
  - Words merged into segments by consecutive speaker labels
  - Reference: https://github.com/yinruiqing/pyannote-whisper

- **Diarization Tuning**: Applied Hervé Bredin's optimized hyperparameters for podcast content
  - New "bredin" sensitivity mode with challenge-winning configuration
  - `num_speakers` oracle mode for known 2-speaker podcasts
  - Tunable parameters: `clustering_threshold`, `min_cluster_size`, `min_duration_off`
  - Reference: https://herve.niderb.fr/posts/2022-12-02-how-I-won-2022-diarization-challenges.html

- **Persistent Profiles**: Fixed to use DTW timestamps + stable regions only
  - Fingerprints extracted only from stable speaker regions (2+ seconds continuous)
  - Prevents profile pollution from transition zones
  - New functions: `find_stable_regions()`, `extract_fingerprints_from_stable_regions()`

### Added
- `pywhispercpp>=1.2.0` and `pyannote-whisper` as dependencies
- `scripts/tune_diarization.py` - Grid search hyperparameter tuning based on Bredin's recipe
- Median filter smoothing for speaker label stability
- New settings: `num_speakers`, `clustering_threshold`, `min_cluster_size`, `median_filter_window`
- Stable region extraction functions in `voice_fingerprinting.py`

- **Deno Runtime Integration for YouTube Downloads**: yt-dlp 2025.11.12+ requires Deno JavaScript runtime
  - **DMG Bundling**: Deno is now bundled in DMG builds for offline YouTube downloads
  - **New Scripts**:
    - `scripts/bundle_deno.sh` - Creates Deno package for DMG installer
    - `scripts/silent_deno_installer.py` - Installs Deno into app bundle
  - **Preflight Check**: `check_deno()` added to verify Deno availability at startup
  - **GitHub Action**: `.github/workflows/watch-deno-releases.yml` monitors for Deno updates
  - **Why Deno?**: YouTube now uses complex JavaScript challenges that require a full JS runtime for signature extraction. Deno is recommended by yt-dlp for security and ease of use.
  - **For Local Dev**: Install with `brew install deno` or `curl -fsSL https://deno.land/install.sh | sh`

### Changed
- **yt-dlp upgraded to 2025.11.12**: First version requiring Deno runtime for YouTube downloads. Deno is bundled in DMG and checked at startup via preflight.

### Removed
- `_split_mixed_speaker_segments()` - replaced by word-driven alignment
- `_reassign_segments_by_voice_verification()` - replaced by word-driven alignment  
- `_verify_word_level_speakers()` - replaced by pyannote-whisper pattern
- Subprocess-based whisper.cpp calls - replaced by pywhispercpp
- Old word verification config settings (replaced by median filter + stable regions)

---

## Previous Changelog Entries

### Added (Legacy - Before Word-Driven Refactor)
- **Word-Level Speaker Attribution** (SUPERSEDED): Previous implementation used whisper.cpp `--output-words` flag with custom verification. Now replaced by pywhispercpp + pyannote-whisper pattern.

- **Persistent Speaker Profiles**: Speaker voice profiles now persist across episodes for recurring hosts.
  - New `speaker_profiles` database table stores averaged embeddings
  - `PersistentSpeakerProfile` SQLAlchemy model with fingerprint accumulation
  - Profiles accumulate across episodes (more data = better accuracy)
  - Channel-aware profile lookup for instant host recognition
  - New methods: `accumulate_speaker_profile()`, `get_or_create_channel_profile()`
  - New migration: `database/migrations/024_persistent_speaker_profiles.sql`
  - Confidence scoring based on sample count and feature availability

- **Batch Processing Pipeline with Prompt Caching**: Complete implementation of batch API support for OpenAI and Anthropic with automatic prompt caching optimization.
  - **50% cost savings** via batch API discounts (24-48 hour processing)
  - **Additional 25% input savings** from OpenAI prompt caching for static prompt prefixes
  - **3-stage pipeline**: Mining → Flagship Evaluation → Re-mining of flagged segments
  - **Processing modes**: `realtime`, `batch`, and `auto` (switches based on segment count)
  - **GUI integration**: Mode selector, cost estimates, and cache metrics display
  - **Database tracking**: New tables for batch jobs and requests with cache hit metrics
  - **Re-mining**: Low-confidence and empty segments automatically re-processed with stronger model
  
  **New Files:**
  - `src/knowledge_system/core/batch_client.py` - Base class and data models
  - `src/knowledge_system/core/batch_openai.py` - OpenAI Batch API client
  - `src/knowledge_system/core/batch_anthropic.py` - Anthropic Batch API client
  - `src/knowledge_system/core/batch_pipeline.py` - 3-stage pipeline orchestrator
  - `database/migrations/023_batch_processing.sql` - Batch tracking tables
  - `tests/test_batch_pipeline.py` - 19 unit tests for batch processing
  
  **Cost Estimate for 5,000 Hours:**
  - Real-time: ~$438
  - Batch only: ~$219
  - Batch + caching: ~$170-195

### Changed
- **yt-dlp upgraded to 2025.10.22**: Updated from 2025.10.14 with YouTube support fixes. **Important:** This is the last version before Deno/JavaScript runtime becomes required (2025.11.12+). pyannote.audio minimum bumped to 4.0.1 for the new community-1 speaker diarization model.

- **Specialized Miner Prompts Aligned to V2/V3 Architecture**: Rewrote `unified_miner_transcript_third_party.txt` and `unified_miner_document.txt` to match the V2/V3 structure and extraction standards:
  - **Refinement patterns section** for blocking known-bad entities via synced feedback
  - **Mental model calibration list** with 25+ exemplars and "named AND used" extraction rule
  - **Worked examples** demonstrating proper handling of source-specific scenarios
  - **Schema harmonization**: Third-party transcripts use `"Unknown"` speaker and `"00:00"` timestamps when unavailable; documents use `location` and `source_attribution` instead of timestamps/speaker
  - **Tighter extraction bar**: Removed "be lenient" language—tolerance is for metadata limitations, not content quality
  - **Document-specific fields**: `formally_defined` boolean for jargon, `is_document_author` for people, `citation_info` for evidence spans
  - **Third-party transcript fields**: Optional `quality_note` for flagging transcription issues

### Added
- **Unified Miner Prompt V3** (`unified_miner_transcript_own_V3.txt`): Complete rewrite of the own-transcript mining prompt for Qwen instruct models. Key improvements:
  - **66% smaller** than V1 (347 lines vs 916 lines) while improving extraction consistency
  - **Worked example** with full input→output JSON demonstrating proper speaker entity handling, multi-claim extraction, jargon with multiple evidence spans, and mental model extraction
  - **Mental model calibration list** with 25+ exemplars across 4 categories (Decision & Reasoning, Economic & Strategic, Systems & Dynamics, Frameworks) plus anti-hallucination warning
  - **Anti-copying guard** to prevent Qwen from regurgitating example timestamps/quotes
  - **Refinement patterns section** for iterative improvement via known-bad entity lists
  - **Speaker entities in people array** with `is_speaker=true` per architectural spec
  - **Clearer skip criteria** for claims (meta-commentary, empty reactions, tautologies), jargon (generic terms), and mental models (bare name-drops without application)

- **Entity Refinement Sync**: Desktop app automatically syncs prompt improvements from GetReceipts.org

  **How It Works:**
  1. Review and reject incorrect entities on the web at `getreceipts.org/dashboard/entities`
  2. The web generates AI-powered prompt improvements from your rejections
  3. Desktop app automatically fetches and applies these improvements
  4. Future extractions benefit from learned patterns
  
  **User Benefit:** When you reject "US President" as a person on the web, the desktop app learns to skip similar titles like "CEO", "Secretary of State", etc. in future extractions.
  
  **Technical Details:**
  - New service: `src/knowledge_system/services/prompt_sync.py`
  - Refinements stored in: `~/Library/Application Support/Knowledge Chipper/refinements/`
  - Files: `person_refinements.txt`, `jargon_refinements.txt`, `concept_refinements.txt`
  - Modified `unified_miner.py` to inject synced refinements as `<bad_example>` entries
  - Sync happens automatically when device authentication is enabled
- **Web-Canonical Architecture with Ephemeral Local Database**: Implemented complete web-canonical architecture where GetReceipts web database (Supabase) is the single source of truth and the desktop Knowledge_Chipper acts as an ephemeral processor. Desktop claims are marked `hidden=1` after successful upload and no longer appear in local views, forcing users to the web for editing and viewing canonical data.
- **Happy-Style Device Authentication**: Auto-generated device authentication using UUID + cryptographically secure secret key (no user interaction required). Device credentials stored in `~/.getreceipts/device_auth.json` and bcrypt-hashed on backend for security.
- **HTTP API-Based Uploader**: Completely rewrote `knowledge_chipper_oauth/getreceipts_uploader.py` (500+ lines → ~200 lines, net -213 lines) to use HTTP requests to `/api/knowledge-chipper/upload` instead of Supabase Python SDK, bypassing RLS policies and simplifying code.
- **Device Provenance Tracking**: All uploaded data tagged with `device_id` for attribution. Database tracks which Knowledge_Chipper device created each claim, person, concept, jargon entry, episode, milestone, evidence span, and relation.
- **Claim Version Tracking**: Reprocessed claims auto-increment `version` field and link to previous version via `replaces_claim_id`, enabling full reprocessing history tracking.
- **Device Authentication API Endpoint**: Created `/api/knowledge-chipper/device-auth` endpoint that registers new devices or verifies existing devices using bcrypt key verification.
- **Database Migrations for Device Tracking**: Created comprehensive migrations adding `device_id`, `source_id`, `uploaded_at`, `version`, and `replaces_claim_id` columns to all relevant tables in GetReceipts Supabase schema.
- **Safe Rollback Strategy**: Created two git branches for easy rollback: `feature/desktop-canonical` (commit a582767, safe rollback point) and `feature/web-canonical-ephemeral` (commit 738ef9f, experimental implementation).
- **Comprehensive Testing Scripts**: Added `test_web_canonical_upload.py` for automated upload testing and `check_schema.py` for verifying Supabase schema state.
- **Complete Documentation Suite**: Created comprehensive documentation including `ARCHITECTURE_WEB_CANONICAL.md` (complete architecture guide), `VERCEL_ENV_SETUP.md` (environment variable setup), `MIGRATION_CHECK.md` (schema diagnosis), `READY_TO_TEST.md`, `QUICK_START.md`, and `DEPLOYMENT_STATUS.md`.

### Changed
- **Diarization Sensitivity Default**: Default changed from "conservative" to "dialogue" for better quick-exchange capture in podcasts and interviews
- **Speaker Processor Architecture**: Refactored to use word-level verification as primary method, with segment-level as fallback when word timestamps unavailable
- **Claims Upload Service - Ephemeral Behavior**: Modified `src/knowledge_system/services/claims_upload_service.py` to add `hidden` column support and `hide_uploaded_claims()` method. Claims marked uploaded are now hidden from local views, implementing ephemeral-local architecture.
- **Cloud Uploads Tab - Auto-Hide After Upload**: Modified `src/knowledge_system/gui/tabs/cloud_uploads_tab.py` to automatically hide uploaded claims after successful upload, moving them to web-canonical storage.
- **Upload Mechanism - SDK to HTTP API**: Switched from Supabase Python SDK (subject to RLS policies) to direct HTTP API requests using service role key internally. Cleaner code, better error handling, bypasses RLS.
- **Backend Upload Endpoint**: Enhanced `/api/knowledge-chipper/upload` with canonical deduplication, fuzzy matching, entity codes, and extraction tracking (discovered during testing - was rewritten independently).

### Fixed
- **Linting Error on Git Push**: Fixed unescaped apostrophe in `src/app/claim/page.tsx` line 185 (`Don't` → `Don&apos;t`).
- **Missing bcryptjs Dependency**: Added bcryptjs and @types/bcryptjs to GetReceipts package.json for device key hashing.
- **RLS Policy Blocking Uploads**: Resolved Row Level Security errors by switching from direct Supabase SDK calls to HTTP API endpoints that use service role key internally.
- **Missing SUPABASE_SERVICE_ROLE_KEY**: Added environment variable to Vercel deployment for upload endpoint authentication.
- **Device Not Registered Error**: Implemented device-auth endpoint call before first upload to register device credentials.
- **Missing device_id Columns**: Created focused re-run migration `001b_add_device_columns_RERUN.sql` to fix incomplete initial migration where CREATE TABLE succeeded but ALTER TABLE statements didn't persist.

### Technical Details
- **Architecture Pattern**: One-way upload flow (no sync complexity), web is always current
- **Offline Capability**: Desktop can still view local claims until uploaded, then hidden
- **Reprocessing Workflow**: Users can reprocess transcripts with upgraded LLM models, creating versioned claims that replace previous versions
- **Git Strategy**: `feature/desktop-canonical` preserves original architecture, `feature/web-canonical-ephemeral` contains experimental implementation
- **Code Reduction**: Net -213 lines in uploader rewrite (500+ → ~200 lines)
- **Security**: Device keys never transmitted in plain text after initial registration, bcrypt-hashed (10 rounds) on backend
- **Database Schema**: Uses `IF NOT EXISTS` for safe re-run migrations, devices table tracks last_seen_at and optional user_id for claiming devices

### Deprecated
- **`_split_mixed_speaker_segments()`**: Replaced by word-level verification (`_verify_word_level_speakers`). Kept as fallback when word timestamps unavailable
- **`_reassign_segments_by_voice_verification()`**: Replaced by word-level verification with better accuracy (4-7% vs 10-15% DER)

### Fixed
- **Database Schema: Missing user_notes Column**: Fixed `sqlite3.OperationalError` where Review tab failed to load claims due to missing `user_notes` column in the claims table. Applied the `2025_11_16_add_user_notes_to_claims.sql` migration to add the column and index. Updated `DatabaseService` to automatically apply incremental migrations on startup, preventing this issue from occurring on fresh installations or after database resets.

## [3.5.3] - 2025-11-11

### Fixed
- **Summarize Tab Database Row Selection UX**: Fixed unintuitive checkbox selection behavior in the Summarize tab's database browser. Previously, users had to click directly on the tiny checkbox widget to select a transcript for summarization. Now clicking anywhere on a row (title, duration, etc.) toggles the checkbox, making selection much more intuitive. Added debug logging to track checkbox state changes and source selection for easier troubleshooting.

### Enhanced
- **Seamless Transcription-to-Summarization Workflow**: When clicking "Summarize Transcript" after transcription, the Summarization tab now automatically: (1) switches to Database mode (not Files), (2) refreshes and checks the boxes for all transcribed sources, and (3) immediately starts summarization without further user input. This provides a streamlined workflow consistent with the database-first architecture, where the rich database segments (with timestamps, speakers, metadata) are used as input instead of parsing markdown files. The system extracts `source_id` from transcription metadata and uses it to locate and select the corresponding database records.
- **Cookie File Persistence Diagnostics**: Added comprehensive logging throughout the cookie file loading and saving pipeline to diagnose persistence issues. System now logs: (1) full paths of cookie files being loaded from session, (2) verification that cookie_manager widget is initialized before loading, (3) signal disconnect/reconnect operations, (4) verification that files were actually set in the UI after loading, (5) detection of mismatches between expected and loaded file counts. Also logs all save operations with confirmation of successful writes to session. This enables rapid diagnosis of any cookie persistence failures by showing exactly where in the chain the issue occurs. See `COOKIE_PERSISTENCE_DIAGNOSIS_2025_11_10.md` for complete diagnostic guide.

### Changed
- **Summary Data Now Appended to Transcript Files**: Major architectural change - summary data (claims, people, concepts) is now appended to the existing transcript markdown file instead of creating a separate summary file. After summarization completes, the system finds the transcript file and appends: (1) Summary section with generated summary text, (2) Claims section organized by tier (A/B/C) with importance scores, (3) People section with descriptions, (4) Concepts section with definitions. This creates a single comprehensive markdown file per video with transcript + analysis, eliminating confusion about where files are located. The transcript file already contains thumbnail, YouTube description, and full transcript, making it the complete reference document.

### Fixed
- **Summary Markdown Template Bug**: Fixed critical bug in `FileGenerationService.generate_summary_markdown()` where non-HCE summaries were generated with literal template code instead of actual values. The template string was missing the `f` prefix, causing output like `{video.title}` instead of the actual video title. This affected legacy (non-HCE) summaries that fall back to the simple format when `hce_data_json` is not available. Now properly formats all summary markdown files with actual video metadata, model information, and summary text.
- **Claims Not Appearing in Summary Files**: Fixed issue where claims were stored in the database but not appearing in generated summary files. Root cause: The summary record's `hce_data_json` field was None, causing the file generator to fall back to legacy format. New `append_summary_to_transcript()` method reads claims directly from the database tables (claims, people, concepts) via proper joins, ensuring all extracted data appears in the output regardless of how it was stored.
- **CRITICAL: Transcribed YouTube Videos Not Appearing in Summarize Tab**: Fixed critical bug where transcribed YouTube videos didn't appear in the Summarize tab's database browser. Root cause: AudioProcessor was generating a NEW source_id (e.g., `audio_filename_hash123`) for every transcription instead of using the existing source_id from the YouTube download. This created orphaned Transcript records that weren't linked to any MediaSource record. The Summarize tab's query requires BOTH a MediaSource AND a Transcript with matching source_ids. Solution: AudioProcessor now checks for `source_metadata` in kwargs and uses the existing `source_id` before generating a new one. This ensures YouTube transcripts are properly linked to their MediaSource records and appear in the Summarize tab.
- **Transcription Format Parameter Not Respected**: Fixed critical bug where the audio processor ignored the `format` parameter from the GUI, causing markdown files to not be created even when format was set to "md". The code was checking `if output_dir:` but not checking `if output_dir and format != "none":` as documented in `FORMAT_NONE_OPTION.md`. Added proper format parameter extraction and conditional file writing logic. When format is "none", the system now logs "Output format set to 'none' - skipping file creation, will save to database only" and correctly skips file creation while still saving to the database.
- **Voice Fingerprinting Not Merging Single-Speaker Monologues**: Fixed critical bug where voice fingerprinting received the wrong audio file path (original input file instead of converted 16kHz mono WAV), preventing proper speaker merging. The system was passing `path` (original MP4/M4A) instead of `output_path` (converted WAV used for diarization) to `prepare_speaker_data()`. This caused voice fingerprinting to fail audio segment extraction, resulting in single-speaker content being incorrectly split into 2+ speakers. Now correctly passes the converted WAV file path, enabling proper voice similarity analysis and speaker merging.

### Enhanced
- **Voice Fingerprinting Diagnostic Logging**: Added comprehensive diagnostic logging to identify why voice fingerprinting fails to merge speakers. System now logs: (1) which features were successfully extracted vs. empty (mfcc, spectral, prosodic, wav2vec2, ecapa), (2) per-feature similarity scores and which features are available/missing during comparison, (3) total weight used in similarity calculation (should be 1.0 if all features available), (4) actual similarity scores between all speaker pairs with merge decision reasoning, (5) audio file format verification (confirms 16kHz mono WAV is being used, not original MP4/M4A), (6) CSV database loading and lookup (confirms channel_hosts.csv is found, loaded with ~524 entries, and host names are successfully matched). This enables rapid diagnosis of issues like missing deep learning models (wav2vec2/ecapa not loading), audio extraction failures, wrong audio format being passed, CSV not being invoked, or threshold problems. See `VOICE_FINGERPRINTING_DIAGNOSIS_NOV_2025.md` for complete diagnostic guide.
- **Summarize Tab Database List Not Refreshing**: Fixed issue where newly transcribed YouTube URLs didn't appear in the Summarize tab's database browser. Added automatic refresh when the Summarize tab becomes visible and the database view is active. Also added diagnostic logging to detect transcripts without corresponding MediaSource records (orphaned transcripts).
- **Missing Summary Markdown Files & Schema Migration Completion**: Fixed critical issue where summarization reported success but no `.md` file was generated. Root cause: The unified pipeline was storing data to the `episodes` table but never creating the required `Summary` record in the `summaries` table. Added call to `_create_summary_from_pipeline_outputs()` to create the Summary record before attempting markdown generation. Also completed the incomplete migration to claim-centric schema by fixing all remaining references to old schema: (1) Changed `video_id` to `source_id` in 3 Summary instantiations in `system2_orchestrator.py`, (2) Changed `get_video()` to `get_source()` in 6 locations across `file_generation.py` and `speaker_processor.py`. This completes the architectural migration from episode-centric to claim-centric schema and ensures `generate_summary_markdown()` can find the data it needs to create properly formatted summary files.

### Removed
- **Duplicate Summary Generation Code Path**: Removed `generate_summary_markdown_from_pipeline()` method which was creating inconsistent markdown formats. The unified pipeline now uses the standard `generate_summary_markdown()` method that reads from database and uses `_generate_hce_markdown()` for consistent formatting. This eliminates code duplication and ensures ONE format for all HCE summaries, following the painstakingly laid out format specifications.

### Changed
- **Robust LLM Fallback System**: Enhanced MVP LLM detection to use ANY available Ollama model if preferred models aren't found. Priority order: (1) Preferred models (qwen2.5:7b, etc.), (2) Any Qwen model, (3) Any Llama model, (4) Any instruct model, (5) Any available model. This ensures speaker attribution never fails when Ollama has models installed, even if they're not the bundled defaults. System logs which fallback tier is used and warns if quality may be reduced.
- **Transcript Markdown Formatting Optimization**: Improved paragraph breaking for better readability. Reduced max paragraph length from 900 to 500 characters and pause threshold from 7s to 3s for more natural breaks. Paragraphs now break more aggressively on sentence boundaries and pauses, making transcripts easier to scan and read. Force break threshold reduced from 1200 to 700 characters.
- **YouTube Description Header**: Changed "Description" header to "YouTube Description" specifically for YouTube videos, making the source of the description clearer in markdown files.
- **Transcript Markdown Filename**: Removed "_transcript" suffix from markdown filenames for cleaner file naming (e.g., "Trump exploits antisemitism.md" instead of "Trump exploits antisemitism_transcript.md").
- **Transcript Markdown Formatting**: Completely redesigned human-readable transcript formatting with intelligent paragraph grouping. Segments are now grouped into logical paragraphs based on speaker changes, long pauses, sentence boundaries, and character limits. Speaker names and timestamps appear on a header line (`**Speaker** [00:00]`) followed by paragraph text, with blank lines between paragraphs for improved readability. The system automatically adapts to monologues (showing speaker label once at start, then only timestamps) vs dialogues (showing speaker label on every speaker change), eliminating redundant labels while maintaining clarity. This applies to both database-generated markdown files and direct transcription output.
- **Summarization Debugging Enhancements**: Added comprehensive diagnostic logging throughout the unified mining pipeline to track progress and identify hangs. Mining phase now reports progress at INFO level when 3% change OR 10 seconds elapsed (whichever comes first), with all segments logged at DEBUG level. Parallel processor logs initial batch submission, task completions, and active task counts. All errors now include full tracebacks at debug level. This addresses cases where summarization hung at 35% without clear error reporting.

### Removed
- **Deprecated Old HCE Extractors**: Moved pre-unified-pipeline extraction modules to `_deprecated/hce_old_extractors/`: `people.py`, `glossary.py`, `concepts.py`, `skim.py`. These standalone extractors were replaced by the unified pipeline in October 2025, which extracts all entity types in a single pass (70% fewer LLM calls, 3-8x faster). Also moved 12 unused prompt files from the old two-tier evaluation system and standalone detection architecture. See `VESTIGIAL_CODE_ANALYSIS.md` for full details.

### Fixed
- **Flagship Evaluator Model Dropdown Empty on Launch**: Fixed critical bug where the "Flagship Evaluator Model" dropdown appeared empty on first launch despite default models being configured. Root cause: When no provider was saved in session state (e.g., first launch), `_load_settings()` would get an empty string from `get_combo_selection()`, fail the `if saved_provider:` check, and never call `_update_advanced_model_combo()` to populate models. Solution: Default to "local" provider when no provider is saved, ensuring model combo is always populated. This fix applies to all advanced model dropdowns (Unified Miner Model, Flagship Evaluator Model) in the Summarization tab. See `FLAGSHIP_EVALUATOR_MODEL_DEFAULT_FIX.md` for complete analysis of the two-bug compound issue (empty provider handling + model name suffix mismatch).
- **Speaker Attribution Model Name Mismatch**: Fixed critical issue where speaker attribution failed even when Qwen model was bundled and installed. Root cause: installation scripts pulled `"qwen2.5:7b"` but code expected `"qwen2.5:7b-instruct"` (Ollama strips the `-instruct` suffix when storing models). Updated MVP_MODEL_ALTERNATIVES to match actual Ollama model names: `["qwen2.5:7b", "qwen2.5:14b", "qwen2.5:3b", ...]`. This ensures the bundled LLM is properly detected and used for speaker attribution with the 262-podcast CSV mapping database, providing real speaker names instead of generic SPEAKER_01 labels.
- **CRITICAL: Flagship Evaluator Scoring Scale Inconsistency**: Fixed a critical bug in the flagship evaluator prompt that caused all claims to be scored as low-quality (tier C). The prompt had conflicting instructions: sections 25-47 instructed scoring on a 0.0-1.0 scale, while sections 66-88 specified a 1-10 scale. This caused the LLM to return scores like 0.8 (meaning 80% on a 0-1 scale) which were interpreted as 0.8/10 (8% on a 1-10 scale), resulting in importance scores below 5 and tier C assignment. All three scoring dimensions (importance, novelty, confidence) now consistently use the 1-10 scale throughout the prompt. This fix restores proper claim quality assessment where high-quality claims (importance >= 8) are correctly identified as tier A.
- **Vestigial Relations and Contradictions Statistics**: Removed misleading "Relations mapped" and "Contradictions detected" statistics from the summarization output. These features were never implemented in the unified pipeline (which explicitly returns empty arrays for relations and contradictions), but the GUI was still displaying them as if they were functional. This created confusion when they suddenly appeared showing "0" values. The RelationMiner class exists but is disabled, and the unified pipeline comments indicate "Relations not implemented in unified pipeline yet". Cleaned up all UI code that referenced these unimplemented features to avoid false expectations.
- **Logger Variable Shadowing in Unified Miner**: Fixed `cannot access local variable 'logger'` error caused by redundant logger re-assignments within exception handlers that shadowed the module-level logger. Removed all `import logging; logger = logging.getLogger(__name__)` statements within functions and consistently use the module-level logger throughout.
- **QueueTab AttributeError**: Fixed `AttributeError: 'QueueTab' object has no attribute 'log_error'` by replacing all `self.log_error()` calls with the correct `self.append_log()` method from BaseTab. Added error emoji (❌) prefix to error messages for consistency with other tabs.
- **Summarization Progress Reporting Frequency**: Fixed progress reporting throttling to match specification of every 5% or 10 seconds (whichever comes first). Previously was reporting every 10% or 30 seconds, resulting in less frequent status updates during long summarization operations. Now provides more responsive feedback in both the console log and chunk processing displays.
- **Transcript Markdown Display**: Removed redundant H1 heading from transcript markdown files since Obsidian and similar markdown viewers automatically display the YAML frontmatter `title` field as the document heading. This eliminates duplicate titles in the UI.
- **Transcript Markdown Filename Spaces**: Changed transcript filenames to preserve spaces instead of converting to underscores (e.g., `Will Japan and South Korea Gang Up on China Peter Zeihan_transcript.md` instead of `Will_Japan_and_South_Korea_Gang_Up_on_China_Peter_Zeihan_transcript.md`). This provides more natural display in file browsers and Obsidian's file tree.
- **Transcript Markdown Filename Generation**: Fixed transcript filenames to use clean video titles instead of including video IDs. Filenames are now human-readable (e.g., `Why_Im_Bullish_on_Southeast_Asia_Peter_Zeihan_transcript.md` instead of `Why_Im_Bullish_on_Southeast_Asia__Peter_Zeihan_gYnAgWRcZPM_transcript.md`).
- **Description Preview Truncation**: Fixed a bug where the first character of video descriptions was being removed in the YAML frontmatter `description_preview` field. The `.rstrip()` operation after slicing was incorrectly stripping leading characters.
- **Mining Fallback Warning Context**: Improved logging to distinguish between DB-centric processing (where missing segments is unexpected) and file-centric processing (where parsing markdown is expected). The warning "⚠️ No DB segments found" now only appears when processing from database, not when explicitly processing standalone markdown files.
- **Speaker Attribution Incomplete Assignment**: Enhanced error logging in LLM speaker suggester to diagnose cases where diarization detects multiple speakers but LLM only provides names for some. Added critical error messages showing which speakers were missed and emergency fallback names. This addresses cases where transcripts showed "SPEAKER_01" instead of real names despite the multi-layered speaker attribution system.
- **Thumbnail Absolute Paths**: Changed thumbnail image references in markdown transcripts from absolute paths to relative paths (e.g., `downloads/youtube/Thumbnails/filename.jpg`). This ensures thumbnails display correctly when files are moved, shared, or viewed in different markdown editors like Obsidian.
- **Single-Speaker Over-Segmentation Diagnostics**: Added comprehensive logging to track speaker merging through all three defensive layers (voice fingerprinting, heuristic detection, LLM analysis). System now logs when diarization over-segments single-speaker content (monologues, solo podcasts) and whether each layer successfully merges or correctly assigns the same name to all speaker IDs. Makes it immediately obvious which layer is failing when single-speaker videos incorrectly show multiple speaker labels.
- **Speaker Assignment System Not Invoked**: Added critical diagnostic logging to detect when the entire speaker attribution system is bypassed. Logs now show whether the speaker assignment block is reached, and if not, displays the exact condition flags (`diarization_successful`, `diarization_segments`) that prevented it from running. This diagnoses cases where speaker attribution fails not because of a bug in the system, but because the system never runs at all.
- **Markdown Transcript Segment Parsing**: Fixed `_parse_transcript_to_segments()` to correctly parse speaker-attributed markdown transcripts with `[MM:SS] (Speaker Name): text` format. The system now preserves all speaker segments instead of re-chunking by tokens, fixing the issue where 6 speaker segments were incorrectly reported as 3 segments.
- **Short Summary Generation Type Error**: Fixed `'dict' object has no attribute 'strip'` error in `_generate_short_summary()` by adding robust type checking for nested dictionary responses from LLM. The code now handles cases where `response.get("summary")` returns another dict instead of a string.
- **Archive Skip Logging Clarity**: Improved logging when yt-dlp skips videos already in the download archive. Changed misleading WARNING message to DEBUG level and clarified that returning None is expected behavior when videos are already downloaded. The system now clearly indicates when it's reusing existing files from the archive vs encountering actual download errors.

## [3.5.2] - 2025-11-08

### Added
- **Claim Domain Classification**: Added `domain` field to claims table and schema for broad field classification (e.g., "physics", "economics", "politics"). Claims can now be filtered and searched by domain alongside jargon terms.
- **Domain Column Migration Script**: Created `scripts/add_domain_column_to_claims.py` to add the missing `domain` column to existing databases.

### Changed
- **Domain Guidance in Miner Prompts**: Updated all 7 miner prompts to guide LLMs toward broad, searchable domain categories. Prompts now explicitly instruct to use general fields like "physics" not "quantum mechanics", "economics" not "monetary policy", ensuring consistent categorization for filtering.
- **Open-Ended Domain Classification**: Both claims and jargon use free-form domain strings (no enum restrictions), allowing natural categorization while prompt guidance ensures broad, searchable categories.
- **Transcription Progress Reporting Frequency**: Reduced the progress update threshold from 5% to 2% increments in whisper_cpp_transcribe.py, providing more frequent visual feedback during long transcription operations.

### Fixed
- **Queue Tab Initialization Error**: Fixed `AttributeError` where `_last_refresh_interval` was accessed before initialization, causing crashes when filters changed during startup.
- **Review Tab Database Error**: Fixed `OperationalError` caused by missing `domain` column in claims table. Added migration to system2_migration.py and standalone migration script for existing databases.
- **Summarization Tab Model Selection**: Improved model combo default selection logic to automatically select the first available model when no previous selection exists, and made warning messages more informative to distinguish between "no models available" vs "models available but none selected".
- **Schema Validation for Missing Claim Domains**: Added repair logic to automatically set `domain = "general"` for claims when LLMs fail to include the required domain field, preventing validation failures and fallback to non-structured JSON generation.
- **Stage Status Race Condition**: Fixed `IntegrityError` in `upsert_stage_status()` caused by concurrent transactions attempting to insert the same stage status record. The method now catches the integrity error and retries with an update operation, properly handling the race condition.

## [3.5.1] - 2025-11-05

### Added
- **Queue Tab**: New tab to visualize real-time pipeline status for all processing stages (download, transcription, summarization). Users can monitor progress, filter by stage/status, and view throughput metrics.
- **Advanced GUI Testing Suite**: Comprehensive GUI testing with pytest-qt and pytest-timeout to simulate real user interactions, test async operations, and debug UI failures interactively.

### Changed
- **Schema Consolidation**: Deleted `miner_output.v2.json` as it was redundant. The v1 file now contains the v2 structure (nested `evidence_spans`, `definition` field) and is what the validator actually uses. This eliminates confusion between file naming and content structure.
- **Queue Tab Default Filter**: The Queue tab now defaults to "Active Only" filter, automatically hiding completed and failed items for a cleaner view.
- **Removed Jargon Domain Enum Constraint**: Changed jargon `domain` field from restricted enum to free-form string, allowing LLM to naturally describe specialized fields (e.g., "quantum mechanics", "constitutional law") rather than forcing into predefined categories.

### Fixed
- **Schema Validation Errors**: Fixed `context_type` enum mismatch in `miner_output.v1.json` (was `["exact", "sentence", "paragraph"]`, now correctly `["exact", "extended", "segment"]` to match database schema). Removed restrictive `domain` enum constraint to allow LLM to freely describe jargon domains without artificial categorization limits.
- **Queue Tab View Details Dialog**: Fixed JSON parsing error that caused empty popup when viewing queue item details. The `metadata_json` field is now correctly handled as a pre-deserialized dictionary.
- **Queue Tab File Links**: Added clickable hyperlinks to completed markdown files in the Actions column. Double-clicking a completed item now opens the summary file directly in the default markdown editor.
- **Queue Tab Failed Items**: Added "Active Only" filter option to automatically hide completed and failed items, keeping the queue view focused on in-progress work.
- **Queue Tab Failure Tracking**: Fixed summarization failures not updating queue status in real-time. The queue now immediately reflects failed status when summarization encounters errors, preventing items from appearing stuck "in progress".
- **YouTube Archive Reuse**: Retranscription runs can now reuse previously downloaded audio when yt-dlp skips via its archive, preventing overwrite workflow failures. A user confirmation dialog has been added.
- **Thumbnail Embedding**: Thumbnails are now correctly embedded in markdown files by ensuring the database is updated *after* the thumbnail is downloaded.
- **Transcription Model Default**: The transcription model now correctly defaults to "medium" instead of "tiny", ensuring better quality out-of-the-box.
- **Vestigial UI Elements**: Removed a non-functional "Prompt File" picker from the Summarization tab to reduce user confusion.
- **UI Layout**: Improved the layout of the Transcription tab by repositioning the Proxy selector for a better visual flow.
- **Startup Validation Noise**: Reduced false-positive warnings during startup validation by intelligently filtering out test files and old entries.
- **YAML Corruption with Color-Coded Transcripts**: Disabled the color-coded transcript feature that was breaking YAML frontmatter parsing. Speaker assignments now work correctly without this feature.
- **Archive Validation Edge Case**: Added validation to remove invalid yt-dlp archive entries (e.g., from failed downloads) to prevent videos from being permanently skipped.
- **Transcription Pipeline Errors**: Fixed a blocking `NameError` on `Segment` import and 10 other issues related to database operations, error handling, and performance in the transcription pipeline.
- **Speaker Diarization Accuracy**: Improved speaker attribution by modifying the LLM prompt to skeptically evaluate diarization splits, allowing it to correctly merge speakers that were incorrectly split.
- **Transcript Formatting**: Fixed a parameter name mismatch to ensure YouTube metadata is correctly included in transcripts. Also improved readability by grouping consecutive segments by the same speaker into paragraphs.
- **Database Parameter Names**: Corrected database parameter names (e.g., `video_id` to `source_id`) in the audio processor to ensure transcripts are saved correctly. Improved logging to reflect the claim-centric architecture.

## [3.5.0] - 2025-10-17

### Breaking Changes
- Removed CLI interface - application is now GUI-only. All functionality is available through the enhanced GUI with the System2 architecture.

### Added
- Comprehensive System2Orchestrator tests for asynchronous job processing.
- LLM adapter async behavior tests, including event loop cleanup validation.
- GUI integration tests using automated workflows.
- Direct logic tests for complete code coverage.
- An automated test suite with zero human intervention required.

### Changed
- The Monitor tab now uses System2Orchestrator, consistent with the Summarization tab.
- Unified code path: all operations now use the System2Orchestrator architecture, eliminating divergence between CLI and GUI implementations.

### Removed
- All CLI commands (`transcribe`, `summarize`, `moc`, `process`, `database`, `upload`, `voice_test`).
- CLI-specific processors and legacy summarizer modules.
- The `commands/` directory and `cli.py` entry point.

### Fixed
- Transcript files now load correctly in the summarization tab after transcription.
- Event loop closure errors during async HTTP client cleanup have been resolved.
- The Monitor tab now uses the same tested code path as the rest of the GUI.

---

## [3.2.22] - 2025-09-17

### Added
- **System 2 HCE Migration**: All HCE processors now use a centralized LLM adapter with System 2 architecture for improved tracking, rate limiting, and cost management.
- **Complete Bundle Approach**: The application is now distributed as a ~600MB DMG with all models and dependencies included, enabling full offline functionality from the first launch.
- **Advanced Voice Fingerprinting**: A new system with 97% accuracy using ECAPA-TDNN and Wav2Vec2 models, bundled for immediate offline use. It automatically merges speakers incorrectly split by diarization.
- **Smart Podcast-Focused Speaker Detection**: A purely LLM-based approach for speaker suggestions that analyzes clean, deduplicated segments and full metadata for higher accuracy.
- **Diarization Excellence & Over-Segmentation Solution**: A conservative diarization strategy combined with voice fingerprinting and text overlap detection to ensure high-quality speaker segmentation.
- **Accuracy Achievement Pipeline**: A multi-step process (Conservative Diarization → Voice Fingerprinting → LLM Validation → Contextual Analysis → User Review) that achieves 99% final accuracy.

### Changed
- **Major Architecture Refactor**: The application has been refactored to support multiple formats (PDFs, Word docs), cloud sync with Supabase, and a unified processing pipeline that reduces API calls by 70%.

---

## Older Releases

Details for older releases can be found in the git history.

## [3.5.1] - 2025-11-13

### Refactoring - Major Code Quality Improvements

#### Removed (-3,692 lines)
- Removed obsolete `gui/adapters/hce_adapter.py` (240 lines) - raises NotImplementedError
- Removed `database/speaker_models_old.py` (1,001 lines) - superseded by unified models
- Removed `database/speaker_models_new.py` (759 lines) - backward compatibility layer
- Removed deprecated `utils/state.py` (544 lines) - replaced by DatabaseService
- Removed deprecated `utils/tracking.py` (865 lines) - replaced by ProgressTracker
- Removed `_apply_recommended_settings()` method from api_keys_tab.py (142 lines)
- Removed deprecated `config.use_gpu` field

#### Added
- Created `core/processing_config.py` with centralized configuration classes
- Replaced `gui/core/session_manager.py` with QSettings-based implementation

#### Changed
- Renamed `gui/legacy_dialogs.py` → `gui/ollama_dialogs.py` (clarity improvement)
- Migrated LLM provider preference handling (removed state.py dependency)
- Updated `system2_orchestrator.py` to use configuration constants

#### Performance
- Optimized download URL validation with batch queries (10-50x faster for 100+ URLs)
- Added optimization roadmap for HCE bulk inserts and Supabase batching

#### Breaking Changes
- JSON-based session management removed (migrated to Qt QSettings)
- Deprecated modules removed: `state.py`, `tracking.py`
- LLM preference persistence now GUI-only (CLI users must specify explicitly)

### Documentation
- Created `REFACTORING_NOVEMBER_2025.md` with complete refactoring summary
- Updated CHANGELOG.md with all changes
- Documented deferred refactorings (6 sections remaining, 50-60 hours estimated)

**See REFACTORING_NOVEMBER_2025.md for complete details and remaining work.**


## [3.5.2] - 2025-11-13 (Continued)

### Refactoring - Additional Architectural Improvements

#### Added
- Created `core/checkpoint_manager.py` - Checkpoint save/load/restore operations extracted from System2Orchestrator
- Created `core/segment_processor.py` - Transcript parsing and chunking operations
- Created `services/download_base.py` - Base class for download orchestrators
- Created `processors/hce/entity_converters.py` - Focused converters for claims, jargon, people, concepts

#### Performance
- Implemented parallel table syncing with dependency groups (3-5x faster Supabase sync)
- Syncs independent tables concurrently using ThreadPoolExecutor
- 4-tier dependency groups respect foreign key constraints

#### Refactoring
- Broke down 217-line `_convert_to_pipeline_outputs()` into 4 focused converter classes
- Extracted CheckpointManager from System2Orchestrator (~210 lines)
- Extracted SegmentProcessor from System2Orchestrator (~190 lines)
- Created DownloadCoordinator base class (~150 lines of common functionality)

#### Type Safety
- Added 100% type coverage to all new modules
- ~150+ type annotations added across core modules
- Full mypy compatibility for new code

### Total Refactoring Summary (Sections 1-11)
- **12 commits** with comprehensive refactoring
- **3,692 lines removed** (obsolete/duplicate code)
- **1,200+ lines added** (focused, well-typed classes)
- **Net: -2,500 lines** while improving architecture
- **Performance: 3-50x** improvements in batch operations
- **Type coverage: +30%** improvement

**See REFACTORING_NOVEMBER_2025.md for complete details.**
