# Knowledge System Codebase Structure & Database Schema

## Overview

Skip the Podcast Desktop (Knowledge System) is a comprehensive macOS application that transforms audio, video, and documents into structured knowledge using AI-powered analysis. The system uses a SQLite-first architecture with optional cloud sync and features advanced speaker diarization, voice fingerprinting, and structured claim extraction.

**Version**: 3.2.82  
**Architecture**: SQLite-first with modular processing pipelines  
**Main Language**: Python 3.13+  
**GUI Framework**: PyQt6  

## Core Architecture

### Design Principles
- **SQLite-First**: All processing results stored in local database before optional file exports
- **Unified Processing**: Single LLM call extracts all entity types (70% reduction in API calls)
- **Modular Components**: Clean separation of processors, services, and UI layers
- **Performance Optimized**: Intelligent chunking, caching, and batch operations
- **Offline-First**: Full functionality without internet, optional cloud sync

## File Structure

### Root Directory
```
/Users/matthewgreer/Projects/Knowledge_Chipper/
├── src/knowledge_system/          # Main source code
├── config/                        # Configuration files and prompts
├── scripts/                       # Build and utility scripts
├── docs/                          # Documentation
├── tests/                         # Test suite
├── output/                        # Generated output files
├── pyproject.toml                 # Project configuration
├── requirements.txt               # Dependencies
└── README.md                      # Main documentation
```

### Source Code Structure (`src/knowledge_system/`)

#### Core Modules
- **`cli.py`** - Command-line interface entry point
- **`config.py`** - Configuration management
- **`logger.py`** - Centralized logging system
- **`errors.py`** - Custom exception classes
- **`watchers.py`** - File system monitoring

#### Main Packages

##### `/commands/` - CLI Command Handlers
- **`process.py`** - Main processing pipeline commands
- **`transcribe.py`** - Audio/video transcription commands
- **`summarize.py`** - Content summarization commands
- **`database.py`** - Database management commands
- **`moc.py`** - Maps of Content extraction
- **`voice_test.py`** - Voice fingerprinting testing
- **`upload.py`** - Cloud upload functionality
- **`common.py`** - Shared CLI utilities

##### `/core/` - Processing Orchestration
- **`intelligent_processing_coordinator.py`** - Main pipeline coordinator
- **`connected_processing_coordinator.py`** - Connected processing with staging
- **`dynamic_parallelization.py`** - Resource-aware parallelization
- **`batch_processor.py`** - Batch processing operations
- **`parallel_processor.py`** - Parallel execution management
- **`enhanced_hce_pipeline.py`** - HCE pipeline orchestration

##### `/database/` - Data Persistence
- **`models.py`** - Main SQLAlchemy models (media_sources, transcripts, summaries)
- **`hce_models.py`** - HCE-specific models (episodes, claims, evidence)
- **`service.py`** - Database service layer
- **`speaker_models.py`** - Speaker-related models
- **`migrations/`** - Database migration scripts
  - `001_rename_videos_to_media_sources.py`
  - `003_add_enhanced_youtube_fields.py`
  - `2025_01_15_claim_tier_validation.sql`
  - `2025_08_18_hce_columns.sql`

##### `/processors/` - Content Processing
- **`whisper_cpp_transcribe.py`** - Audio transcription using Whisper.cpp
- **`diarization.py`** - Speaker diarization with pyannote.audio
- **`speaker_processor.py`** - Speaker identification and voice fingerprinting
- **`document_processor.py`** - PDF and document processing
- **`youtube_download.py`** - YouTube video downloading
- **`youtube_metadata.py`** - YouTube metadata extraction
- **`audio_processor.py`** - Audio file processing utilities

##### `/processors/hce/` - Hybrid Claim Extractor
- **`unified_pipeline.py`** - Main HCE processing pipeline
- **`miner.py`** - Stage-A: Claim extraction and mining
- **`evaluator.py`** - Stage-B: Claim evaluation and ranking
- **`schema_validator.py`** - JSON schema validation
- **`prompts/`** - HCE prompt templates
- **`sqlite_schema.sql`** - HCE-specific database schema

##### `/gui/` - User Interface (PyQt6)
- **`main_window_pyqt6.py`** - Main application window
- **`startup_integration.py`** - Application startup logic

###### `/gui/tabs/` - Main UI Tabs
- **`introduction_tab.py`** - Welcome and guidance for new users
- **`youtube_tab.py`** - YouTube video processing interface
- **`transcription_tab.py`** - Local audio/video transcription
- **`summarization_tab.py`** - Content analysis and HCE processing
- **`claim_search_tab.py`** - Search extracted claims and knowledge
- **`speaker_attribution_tab.py`** - Speaker identification management
- **`process_tab.py`** - Complete processing pipeline interface
- **`watcher_tab.py`** - File system monitoring and auto-processing
- **`api_keys_tab.py`** - LLM provider configuration
- **`sync_status_tab.py`** - Cloud sync management (optional)
- **`cloud_uploads_tab.py`** - Cloud upload interface (optional)
- **`summary_cleanup_tab.py`** - Summary editing and cleanup

###### `/gui/components/` - Reusable UI Components
- **`base_tab.py`** - Base class for all tabs
- **`progress_tracking.py`** - Progress display components
- **`file_operations.py`** - File selection and management
- **`enhanced_error_dialog.py`** - Error handling dialogs

###### `/gui/workers/` - Background Processing
- **`transcription_worker.py`** - Background transcription processing
- **`summarization_worker.py`** - Background summarization processing
- **`batch_processing_worker.py`** - Batch processing operations

##### `/services/` - Business Logic Services
- **`transcription_service.py`** - Transcription orchestration
- **`speaker_learning_service.py`** - Speaker profile learning
- **`supabase_sync.py`** - Cloud synchronization (optional)
- **`supabase_storage.py`** - Cloud storage management (optional)
- **`claims_upload_service.py`** - Claims upload to cloud
- **`file_generation.py`** - Output file generation
- **`oauth_callback_server.py`** - OAuth authentication

##### `/voice/` - Voice Processing
- **`voice_fingerprinting.py`** - Voice fingerprinting with ECAPA-TDNN + Wav2Vec2
- **`speaker_verification_service.py`** - Speaker verification logic
- **`accuracy_testing.py`** - Voice accuracy testing utilities

##### `/superchunk/` - Advanced Processing (Expert Mode)
- **`runner.py`** - SuperChunk processing runner
- **`extractors.py`** - Advanced claim extraction
- **`canonicalization.py`** - Claim canonicalization
- **`embeddings.py`** - Vector embeddings for similarity
- **`ledger.py`** - Processing ledger and tracking
- **`vector_store.py`** - Vector storage and retrieval

##### `/utils/` - Utility Functions
- **`hardware_detection.py`** - Hardware specification detection
- **`file_utils.py`** - File operations utilities
- **`yaml_utils.py`** - YAML processing utilities
- **`text_processing.py`** - Text manipulation utilities
- **`process_analytics.py`** - Processing analytics and metrics

##### `/integrations/` - External Integrations
- **`getreceipts_integration.py`** - Receipt processing integration

## Database Schema

### Core Tables (SQLAlchemy Models)

#### `media_sources` (Primary Media Table)
```sql
CREATE TABLE media_sources (
    media_id TEXT PRIMARY KEY,           -- Unique identifier (backward compatible as video_id)
    source_type TEXT NOT NULL,           -- 'youtube', 'upload', 'rss'
    title TEXT NOT NULL,                 -- Media title
    url TEXT NOT NULL,                   -- Source URL
    
    -- YouTube-specific metadata
    description TEXT,                    -- Video description
    uploader TEXT,                       -- Channel name
    uploader_id TEXT,                    -- Channel ID
    upload_date TEXT,                    -- YYYYMMDD format
    duration_seconds INTEGER,            -- Video length
    view_count INTEGER,                  -- View statistics
    like_count INTEGER,
    comment_count INTEGER,
    categories_json TEXT,                -- JSON array of categories
    privacy_status TEXT,                 -- YouTube privacy status
    caption_availability BOOLEAN,        -- Caption availability
    
    -- Thumbnails
    thumbnail_url TEXT,                  -- Original YouTube thumbnail
    thumbnail_local_path TEXT,           -- Local downloaded thumbnail
    
    -- Tags and keywords
    tags_json TEXT,                      -- JSON array of video tags
    extracted_keywords_json TEXT,        -- AI-extracted keywords
    
    -- Related content
    related_videos_json TEXT,            -- Related video data
    channel_stats_json TEXT,             -- Channel statistics
    video_chapters_json TEXT,            -- Video chapters/timestamps
    
    -- Processing metadata
    extraction_method TEXT,              -- 'bright_data_api', 'yt_dlp', etc.
    processed_at DATETIME,               -- Processing timestamp
    bright_data_session_id TEXT,         -- Bright Data session ID
    processing_cost REAL,                -- Processing cost
    status TEXT DEFAULT 'pending'        -- 'pending', 'processing', 'completed', 'failed'
);
```

#### `transcripts` (Transcript Storage)
```sql
CREATE TABLE transcripts (
    transcript_id TEXT PRIMARY KEY,
    video_id TEXT REFERENCES media_sources(media_id),
    language TEXT NOT NULL,              -- Language code (e.g., 'en')
    is_manual BOOLEAN NOT NULL,          -- Manual vs auto-generated
    transcript_type TEXT,                -- 'youtube_api', 'diarized', 'whisper', etc.
    
    -- Transcript content
    transcript_text TEXT NOT NULL,       -- Clean full text
    transcript_text_with_speakers TEXT,  -- Text with speaker labels
    
    -- Timestamped segments
    transcript_segments_json TEXT NOT NULL,  -- JSON array of segments
    diarization_segments_json TEXT,          -- Speaker-diarized segments
    
    -- Processing details
    whisper_model TEXT,                  -- Whisper model used
    device_used TEXT,                    -- 'cpu', 'cuda', 'mps'
    diarization_enabled BOOLEAN,         -- Speaker diarization flag
    diarization_model TEXT,              -- Diarization model used
    
    -- Quality metrics
    confidence_score REAL,               -- Overall confidence
    segment_count INTEGER,               -- Number of segments
    total_duration REAL,                 -- Total duration in seconds
    
    -- Speaker assignments
    speaker_assignments TEXT,            -- JSON: {speaker_id: assigned_name}
    speaker_assignment_completed BOOLEAN,
    speaker_assignment_completed_at DATETIME,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processing_time_seconds REAL
);
```

#### `summaries` (Summary Storage)
```sql
CREATE TABLE summaries (
    summary_id TEXT PRIMARY KEY,
    video_id TEXT REFERENCES media_sources(media_id),
    transcript_id TEXT REFERENCES transcripts(transcript_id),
    
    -- Summary content
    summary_text TEXT NOT NULL,          -- Summary text
    summary_metadata_json TEXT,          -- YAML frontmatter as JSON
    
    -- Processing type
    processing_type TEXT DEFAULT 'legacy',  -- 'legacy' or 'hce'
    hce_data_json TEXT,                  -- HCE structured output
    
    -- LLM processing details
    llm_provider TEXT NOT NULL,          -- 'openai', 'anthropic', 'local'
    llm_model TEXT NOT NULL,             -- Model name
    prompt_template_path TEXT,           -- Template used
    focus_area TEXT,                     -- Optional focus parameter
    
    -- Token consumption
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    processing_cost REAL,
    
    -- Performance metrics
    input_length INTEGER,                -- Input character count
    summary_length INTEGER,              -- Summary character count
    compression_ratio REAL,              -- Compression ratio
    processing_time_seconds REAL,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    template_used TEXT
);
```

#### `moc_extractions` (Maps of Content)
```sql
CREATE TABLE moc_extractions (
    moc_id TEXT PRIMARY KEY,
    video_id TEXT REFERENCES media_sources(media_id),
    summary_id TEXT REFERENCES summaries(summary_id),
    
    -- Extracted entities (JSON arrays)
    people_json TEXT,                    -- People mentions
    tags_json TEXT,                      -- Content tags
    mental_models_json TEXT,             -- Mental models
    jargon_json TEXT,                    -- Technical terms
    beliefs_json TEXT,                   -- Claims and beliefs
    
    -- MOC metadata
    theme TEXT,                          -- 'topical', 'chronological', 'hierarchical'
    depth INTEGER,                       -- Extraction depth
    include_beliefs BOOLEAN,             -- Include beliefs flag
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    extraction_method TEXT
);
```

### HCE (Hybrid Claim Extractor) Tables

#### `episodes` (HCE Episode Mapping)
```sql
CREATE TABLE episodes (
    episode_id TEXT PRIMARY KEY,
    video_id TEXT REFERENCES media_sources(media_id),
    title TEXT,
    recorded_at TEXT,                    -- ISO8601 timestamp
    inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### `claims` (Structured Claims)
```sql
CREATE TABLE claims (
    episode_id TEXT REFERENCES episodes(episode_id),
    claim_id TEXT NOT NULL,
    canonical TEXT NOT NULL,             -- Consolidated claim text
    claim_type TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
    tier TEXT CHECK (tier IN ('A','B','C')),
    first_mention_ts TEXT,               -- First occurrence timestamp
    scores_json TEXT NOT NULL,           -- JSON: {"importance":0.8, "novelty":0.7, "confidence":0.9}
    
    -- Temporality analysis
    temporality_score INTEGER CHECK (temporality_score IN (1,2,3,4,5)),
    temporality_confidence REAL CHECK (temporality_confidence BETWEEN 0 AND 1),
    temporality_rationale TEXT,
    
    -- Structured categories
    structured_categories_json TEXT,     -- JSON array of categories
    category_relevance_scores_json TEXT, -- JSON mapping categories to scores
    
    -- Upload tracking
    last_uploaded_at TEXT,
    upload_status TEXT DEFAULT 'pending',
    
    inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (episode_id, claim_id)
);
```

#### `evidence_spans` (Claim Evidence)
```sql
CREATE TABLE evidence_spans (
    episode_id TEXT REFERENCES episodes(episode_id),
    claim_id TEXT REFERENCES claims(claim_id),
    span_id TEXT NOT NULL,
    
    -- Evidence details
    quote TEXT NOT NULL,                 -- Supporting quote
    t0 TEXT,                             -- Start timestamp
    t1 TEXT,                             -- End timestamp
    segment_id TEXT,                     -- Segment reference
    
    -- Context levels
    immediate_context TEXT,              -- Immediate surrounding context
    broader_context TEXT,                -- Broader context
    
    -- Evidence quality
    relevance_score REAL,                -- Relevance to claim
    confidence REAL,                     -- Evidence confidence
    
    PRIMARY KEY (episode_id, claim_id, span_id),
    FOREIGN KEY (episode_id, claim_id) REFERENCES claims(episode_id, claim_id)
);
```

#### `people` (Person/Organization Mentions)
```sql
CREATE TABLE people (
    episode_id TEXT REFERENCES episodes(episode_id),
    mention_id TEXT NOT NULL,
    span_segment_id TEXT,
    t0 TEXT,                             -- Start timestamp
    t1 TEXT,                             -- End timestamp
    surface TEXT NOT NULL,               -- As mentioned in text
    normalized TEXT,                     -- Canonical form
    entity_type TEXT CHECK (entity_type IN ('person','org')) DEFAULT 'person',
    external_ids_json TEXT,              -- JSON: {"wikipedia":"...", "wikidata":"Q..."}
    confidence REAL,
    PRIMARY KEY (episode_id, mention_id)
);
```

#### `concepts` (Mental Models and Concepts)
```sql
CREATE TABLE concepts (
    episode_id TEXT REFERENCES episodes(episode_id),
    model_id TEXT NOT NULL,
    name TEXT NOT NULL,
    definition TEXT,
    first_mention_ts TEXT,
    aliases_json TEXT,                   -- JSON array of aliases
    evidence_json TEXT,                  -- JSON array of evidence spans
    PRIMARY KEY (episode_id, model_id)
);
```

#### `jargon` (Technical Terms)
```sql
CREATE TABLE jargon (
    episode_id TEXT REFERENCES episodes(episode_id),
    term_id TEXT NOT NULL,
    term TEXT NOT NULL,
    category TEXT,                       -- 'technical', 'industry', 'acronym'
    definition TEXT,
    evidence_json TEXT,                  -- JSON array of evidence spans
    PRIMARY KEY (episode_id, term_id)
);
```

### Supporting Tables

#### `generated_files` (File Generation Tracking)
```sql
CREATE TABLE generated_files (
    file_id TEXT PRIMARY KEY,
    video_id TEXT REFERENCES media_sources(media_id),
    transcript_id TEXT REFERENCES transcripts(transcript_id),
    summary_id TEXT REFERENCES summaries(summary_id),
    moc_extraction_id TEXT REFERENCES moc_extractions(moc_id),
    
    file_type TEXT NOT NULL,             -- 'transcript', 'summary', 'moc', 'thumbnail'
    file_path TEXT NOT NULL,             -- Local file path
    file_format TEXT,                    -- 'md', 'txt', 'yaml', 'json', 'png'
    file_size_bytes INTEGER,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### `bright_data_sessions` (Bright Data Integration)
```sql
CREATE TABLE bright_data_sessions (
    session_id TEXT PRIMARY KEY,
    video_id TEXT REFERENCES media_sources(media_id),
    
    -- Session details
    session_type TEXT,                   -- 'metadata', 'transcript', 'download'
    status TEXT,                         -- 'active', 'completed', 'failed'
    started_at DATETIME,
    completed_at DATETIME,
    
    -- Cost tracking
    cost_usd REAL,
    data_transferred_mb REAL,
    
    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);
```

## Key Processing Pipelines

### 1. Unified HCE (Hybrid Claim Extractor) Pipeline
- **Stage-A (Miner)**: Single-pass extraction of claims, people, concepts, jargon
- **Stage-B (Flagship Evaluator)**: LLM-powered ranking and validation
- **Scoring System**: Importance (1-10), Novelty (1-10), Confidence (1-10)
- **Claim Types**: Factual, causal, normative, forecast, definitional

### 2. Voice Fingerprinting System
- **Models**: ECAPA-TDNN + Wav2Vec2 for 97% accuracy
- **Features**: Multi-modal analysis (MFCC, spectral, prosodic)
- **Integration**: Conservative diarization with AI-powered speaker merging
- **Hardware**: Automatic MPS (Apple Silicon) and CUDA support

### 3. Intelligent Processing Coordination
- **Dynamic Parallelization**: Resource-aware worker scaling
- **Queue Management**: Optimal distribution for minimum processing time
- **Hardware Optimization**: Automatic model selection based on Mac specs
- **Audio Preservation**: Intelligent staging and cleanup

## Configuration System

### Configuration Files (`config/`)
- **`settings.yaml`** - Main application settings
- **`credentials.yaml`** - API keys and authentication
- **`speaker_attribution.yaml`** - Speaker identification settings
- **`obsidian_linking.yaml`** - Obsidian integration settings
- **`prompts/`** - LLM prompt templates

### Hardware-Aware Model Selection
- **M2/M3 Ultra (64GB+)**: `qwen2.5:14b-instruct` (8.2GB)
- **M2/M3 Max (32GB+)**: `qwen2.5:14b-instruct` (8.2GB)
- **M2/M3 Pro (16GB+)**: `qwen2.5:7b-instruct` (4GB)
- **Base Systems**: `qwen2.5:3b-instruct` (2GB)

## Dependencies

### Core Dependencies
- **PyQt6** - GUI framework
- **SQLAlchemy** - Database ORM
- **Click** - CLI framework
- **Pydantic** - Data validation
- **Loguru** - Logging system

### ML/AI Dependencies
- **OpenAI** - GPT models
- **Anthropic** - Claude models
- **Transformers** - Hugging Face models
- **PyAnnote.audio** - Speaker diarization
- **Whisper.cpp** - Audio transcription
- **Sentence-transformers** - Embeddings

### Optional Dependencies
- **Supabase** - Cloud sync (optional)
- **CUDA** - GPU acceleration (optional)
- **Bright Data** - YouTube data proxy (optional)

## Entry Points

### Command Line Interface
```bash
knowledge-system transcribe --input "video.mp4" --enable-diarization
knowledge-system summarize "transcript.md"
knowledge-system process ./content/ --recursive
knowledge-system voice enroll --speaker-name "John Doe" --audio-file "sample.wav"
```

### GUI Application
```bash
knowledge-system gui
# or
ks-gui
```

## Build System

### Package Structure
- **DMG Installation**: Pre-bundled with all dependencies (~600MB)
- **Intelligent Updates**: Daily patches (~940KB) with component caching
- **Apple Code Signing**: Complete notarization workflow
- **Hardware Optimization**: Automatic model selection and caching

### Build Artifacts
- **`build/`** - Build output directory
- **`dist/`** - Distribution packages
- **`build_packages/`** - macOS package creation
- **`build_framework/`** - Python framework bundling

This codebase represents a sophisticated knowledge management system with advanced AI capabilities, designed for processing large volumes of multimedia content into structured, searchable knowledge.
