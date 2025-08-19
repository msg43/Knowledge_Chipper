# HCE (Hybrid Claim Extractor) Implementation TODO List

## Overview
This document outlines the complete implementation plan for integrating the Hybrid Claim Extractor (HCE) system into the Knowledge Chipper codebase. The implementation follows a phased approach with Phase 1 establishing core infrastructure and Phase 2 adding advanced features.

## Updates for Existing Infrastructure (2024-01-18)
The implementation plan has been updated to account for:
1. **SQLite Database**: Comprehensive database schema already implemented with 7 tables for videos, transcripts, summaries, MOC extractions, file tracking, jobs, and Bright Data sessions
2. **Bright Data Proxy System**: Existing proxy integration for YouTube downloads with session management, sticky IPs, and cost tracking
3. **Database Service**: Existing CRUD operations and analytics infrastructure
4. **File Generation Service**: Existing capability to regenerate files from SQLite data

Key integration points:
- HCE will store claims and relations in new SQLite tables
- HCE can optionally use Bright Data proxies for LLM API calls
- HCE will leverage existing DatabaseService for all data operations
- HCE outputs will be tracked in the existing file generation system

## Pre-Implementation Tasks

### 1. Environment Setup
- [ ] Create feature branch: `feature/hce-integration`
- [ ] Set up HCE dependencies in requirements.txt:
  - [ ] Add pydantic>=2.0
  - [ ] Add sentence-transformers for embeddings
  - [ ] Add transformers for cross-encoder support
  - [ ] Add hdbscan for clustering (Phase 2)
  - [ ] Add scipy for clustering metrics
  - [ ] Add torch/tensorflow based on platform
- [ ] Create tests directory structure: `tests/hce/`
- [ ] Set up CI to run with `--use_hce` flag tests

### 2. Legacy Component Mapping Documentation
- [ ] Create `hce_kit/docs/architecture/HCE_Integration_Report.md`
- [ ] Document mapping:
  - [ ] AudioProcessor → EpisodeBundle converter
  - [ ] SummarizerProcessor → HCE Miner/Judge pipeline
  - [ ] MOCProcessor → HCE People/Concepts/Glossary extractors
  - [ ] File outputs → HCE Export module
- [ ] Document data flow diagrams
- [ ] Create migration guide for existing features

## Phase 1: Core Integration

### 3. HCE Package Integration
- [ ] Copy `hce_kit/claim_extractor/` to `src/knowledge_system/hce/`
- [ ] Update imports to use knowledge_system namespace
- [ ] Add `__init__.py` with proper exports
- [ ] Ensure no import side effects
- [ ] Add py.typed marker for type checking

### 4. Configuration Integration
- [ ] Add HCE configuration to `src/knowledge_system/config.py`:
  ```python
  class HCEConfig(BaseSettings):
      enabled: bool = False
      models: StageModelConfig
      rerank_policy: RerankPolicy
      use_skim: bool = True
      cache_dir: Path = Path("~/.cache/knowledge_system/hce")
      use_bright_data_proxy: bool = True  # Enable proxy for LLM calls if needed
      database_integration: bool = True  # Store HCE outputs in SQLite
  ```
- [ ] Add `--use_hce` flag to CLI commands
- [ ] Add HCE settings to GUI settings tab
- [ ] Create default HCE config template
- [ ] Add environment variable support: `USE_HCE=1`
- [ ] Integrate with existing Bright Data configuration for proxy support

### 5. Data Conversion Layer & Database Integration
- [ ] Create `src/knowledge_system/hce/converters.py`:
  - [ ] `transcript_to_episode_bundle()`: Convert SQLite transcript records to EpisodeBundle
  - [ ] `youtube_to_segments()`: Convert YouTube transcripts with timestamps from database
  - [ ] `audio_to_segments()`: Convert Whisper output to segments
  - [ ] `diarization_to_segments()`: Convert diarized output to segments
  - [ ] `database_to_episode_bundle()`: Load existing data from SQLite for reprocessing
  - [ ] `video_to_episode_mapping()`: Map video_id to episode_id for compatibility
- [ ] Handle speaker attribution from diarization
- [ ] Preserve timestamps in all conversions
- [ ] Add validation for segment boundaries
- [ ] Integration with existing `DatabaseService` for data retrieval
- [ ] Support for segment storage in new schema:
  ```python
  def store_segments(conn, episode_id: str, segments: List[Segment]):
      """Store segments in SQLite for future reference"""
  ```

### 6. Model Adapter Implementation
- [ ] Implement `src/knowledge_system/hce/model_adapters.py`:
  - [ ] Create unified model loader for ModelURIs
  - [ ] Support for existing providers:
    - [ ] `ollama://` - Ollama models
    - [ ] `openai://` - OpenAI API (with optional Bright Data proxy)
    - [ ] `anthropic://` - Anthropic API (with optional Bright Data proxy)
    - [ ] `local://` - Local models (Whisper, etc.)
    - [ ] `vllm://` - vLLM server support
  - [ ] Implement model caching and management
  - [ ] Add retry logic and error handling
  - [ ] Bright Data proxy integration for API calls if configured
- [ ] Integration with existing LLM providers in `utils/llm_providers.py`
- [ ] Cost tracking integration with `BrightDataSessionManager`

### 7. Core Pipeline Implementation
- [ ] Create `src/knowledge_system/hce/pipeline.py`:
  - [ ] Main pipeline orchestrator class
  - [ ] Stage execution with progress tracking
  - [ ] Cancellation token support
  - [ ] Memory-efficient batch processing
  - [ ] Result caching between stages
  - [ ] SQLite checkpointing for resume capability
- [ ] Implement core stages:
  - [ ] Skim (optional milestone extraction)
  - [ ] Mine (claim extraction)
  - [ ] Evidence linking
  - [ ] Deduplication/Consolidation
  - [ ] Reranking
  - [ ] Router (uncertainty-based)
  - [ ] Judge (flagship validation)
- [ ] Add pipeline persistence:
  - [ ] Save intermediate results to SQLite
  - [ ] Enable pipeline resume from any stage
  - [ ] Track processing metadata and costs

### 8. Export Module Enhancement & Database Storage
- [ ] Extend `src/knowledge_system/hce/export.py`:
  - [ ] Markdown export with timestamps
  - [ ] JSONL export for downstream processing
  - [ ] YAML export compatible with legacy MOC format
  - [ ] Obsidian-compatible markdown with backlinks
  - [ ] HTML export with interactive elements
- [ ] Implement two-stage persistence:
  - [ ] Stage 1: Call existing `export_all()` for file generation
  - [ ] Stage 2: Call `storage_sqlite.upsert_pipeline_outputs()` for database storage
- [ ] Add common query utilities:
  - [ ] Top-tier claims by importance
  - [ ] Contradiction discovery
  - [ ] Full-text search across claims/quotes
  - [ ] Cross-episode entity tracking
  - [ ] Jargon glossary generation
- [ ] Integration with `GeneratedFile` tracking system
- [ ] File regeneration from HCE SQLite data
- [ ] Preserve backward compatibility with existing outputs

### 9. CLI Integration
- [ ] Update `src/knowledge_system/commands/process.py`:
  - [ ] Add `--use_hce` flag
  - [ ] Route to HCE pipeline when enabled
  - [ ] Maintain legacy behavior when disabled
- [ ] Create new command `hce-extract`:
  - [ ] Direct access to HCE pipeline
  - [ ] Stage-specific options
  - [ ] Model selection per stage
- [ ] Update help text and documentation

### 10. Basic Testing Suite
- [ ] Create `tests/hce/test_converters.py`
- [ ] Create `tests/hce/test_pipeline.py`
- [ ] Create `tests/hce/test_models.py`
- [ ] Add smoke test: `make hce-smoketest`
- [ ] Ensure legacy tests still pass

## Phase 2: Advanced Features

### 11. NLI Integration (Upgrade A)
- [ ] Implement `src/knowledge_system/hce/nli.py`:
  - [ ] Local NLI model support
  - [ ] Truth/entailment checking
  - [ ] Confidence scoring
  - [ ] Integration with router for flagship review
- [ ] Add NLI model to model registry
- [ ] Create prompts for NLI-guided review
- [ ] Add tests for NLI components

### 12. Advanced Clustering (Upgrade B)
- [ ] Upgrade `dedupe.py` with HDBSCAN:
  - [ ] Implement HDBSCAN clustering
  - [ ] Dynamic cluster sizing
  - [ ] Outlier detection
  - [ ] Cluster quality metrics
- [ ] Enhance cross-encoder reranking:
  - [ ] Multi-model ensemble
  - [ ] Score normalization
  - [ ] Adaptive thresholds

### 13. Calibration System (Upgrade C)
- [ ] Implement `src/knowledge_system/hce/calibration.py`:
  - [ ] Self-consistency variance calculation
  - [ ] NLI margin computation
  - [ ] Rerank margin analysis
  - [ ] Uncertainty aggregation
- [ ] Create logistic gate for routing:
  - [ ] Learn from judged examples
  - [ ] Dynamic threshold adjustment
  - [ ] Performance monitoring

### 14. Global Index (Upgrade D - Partial)
- [ ] Implement `src/knowledge_system/hce/global_index.py`:
  - [ ] Cross-episode entity tracking
  - [ ] People disambiguation across episodes
  - [ ] Mental model evolution tracking
  - [ ] Jargon term consolidation
- [ ] Leverage existing SQLite infrastructure:
  - [ ] Use existing database schema for persistence
  - [ ] Create additional tables for HCE-specific data:
    - [ ] `hce_global_entities` for cross-episode tracking
    - [ ] `hce_entity_mentions` for occurrence tracking
    - [ ] `hce_entity_relations` for entity relationships
  - [ ] Vector index for similarity search (SQLite FTS5)
  - [ ] Version control for updates

### 15. Discourse Analysis (Upgrade E)
- [ ] Implement `src/knowledge_system/hce/discourse.py`:
  - [ ] Sentence-level classification
  - [ ] Turn-level analysis
  - [ ] Tag types: claim/evidence/anecdote/hedge/caveat
  - [ ] Confidence scoring per tag
- [ ] Integration with claim extraction
- [ ] Export discourse tags in outputs

### 16. Temporal & Numeric Analysis (Upgrade G)
- [ ] Implement `src/knowledge_system/hce/temporal_numeric.py`:
  - [ ] Date/time normalization
  - [ ] Relative time resolution
  - [ ] Numeric range validation
  - [ ] Conflict detection
  - [ ] Timeline generation
- [ ] Add validation rules
- [ ] Create conflict resolution UI

### 17. Quality Assurance (Upgrade H)
- [ ] Implement comprehensive testing:
  - [ ] Snapshot tests for each stage
  - [ ] Invariant testing (miner→judge)
  - [ ] Performance benchmarks
  - [ ] Memory usage profiling
- [ ] Add telemetry:
  - [ ] Stage timing metrics
  - [ ] Model performance tracking
  - [ ] Error rate monitoring
  - [ ] Usage analytics (opt-in)
- [ ] Create test data generator

### 18. Obsidian UX Features (Upgrade I)
- [ ] Enhanced export features:
  - [ ] Mermaid relationship graphs
  - [ ] Automatic backlinking
  - [ ] Tag hierarchies
  - [ ] Triage lanes (A/B/C tiers)
- [ ] Create Obsidian plugin companion:
  - [ ] Custom CSS for HCE content
  - [ ] Interactive claim navigation
  - [ ] Evidence hover previews
- [ ] Template system for customization

## Integration Tasks

### 19. GUI Integration
- [ ] Create HCE tab in GUI:
  - [ ] Model selection per stage
  - [ ] Pipeline configuration
  - [ ] Progress visualization
  - [ ] Result preview
- [ ] Update existing tabs:
  - [ ] Add HCE option to Process tab
  - [ ] Show HCE in transcription workflow
  - [ ] Enable in batch processing
- [ ] Settings integration:
  - [ ] Model management UI
  - [ ] Cache management
  - [ ] Performance tuning

### 20. Performance Optimization
- [ ] Implement streaming processing:
  - [ ] Process segments as they arrive
  - [ ] Incremental result updates
  - [ ] Memory-efficient buffering
- [ ] Add caching layers:
  - [ ] Model inference cache
  - [ ] Embedding cache
  - [ ] Result cache with TTL
- [ ] GPU acceleration:
  - [ ] CUDA support for embeddings
  - [ ] Metal Performance Shaders on macOS
  - [ ] Batch inference optimization

### 21. Documentation
- [ ] User documentation:
  - [ ] HCE quick start guide
  - [ ] Model selection guide
  - [ ] Output format reference
  - [ ] Troubleshooting guide
- [ ] Developer documentation:
  - [ ] Architecture overview
  - [ ] API reference
  - [ ] Extension guide
  - [ ] Contributing guidelines
- [ ] Migration guides:
  - [ ] From legacy MOC to HCE
  - [ ] From summarizer to claims
  - [ ] Custom prompt migration

### 22. Deployment & Release
- [ ] Update build scripts:
  - [ ] Include HCE dependencies
  - [ ] Bundle required models
  - [ ] Update installer size estimates
- [ ] Release preparation:
  - [ ] Feature flag testing
  - [ ] Performance benchmarks
  - [ ] Compatibility testing
  - [ ] Release notes
- [ ] Post-release:
  - [ ] Monitor error reports
  - [ ] Gather user feedback
  - [ ] Plan improvements

## Validation & Acceptance

### 23. Acceptance Criteria Validation
- [ ] Verify `make hce-smoketest` passes
- [ ] Confirm all pytest tests pass
- [ ] Validate feature flag behavior
- [ ] Check backward compatibility
- [ ] Benchmark performance vs legacy
- [ ] User acceptance testing
- [ ] Documentation review

### 24. Final Integration Report
- [ ] Complete `HCE_Integration_Report.md`:
  - [ ] Implementation summary
  - [ ] Performance metrics
  - [ ] Known limitations
  - [ ] Future improvements
  - [ ] Lessons learned
- [ ] Create demo video
- [ ] Prepare presentation materials

### 32. Advanced SQLite Features
- [ ] Implement performance optimizations:
  - [ ] Enable WAL mode for concurrent reads
  - [ ] Create covering indexes for common queries
  - [ ] Use contentless FTS5 tables for efficiency
- [ ] Add query views for common patterns:
  - [ ] `v_episode_claims` - Claims with all evidence
  - [ ] `v_claim_supporters` - Claims and their supporting relations
  - [ ] `v_cross_episode_entities` - Entities across all episodes
- [ ] Implement versioning strategy:
  - [ ] Schema version tracking
  - [ ] Run history with config hashes
  - [ ] Optional append-only audit tables
- [ ] Add backup and replication:
  - [ ] Litestream integration for off-site backup
  - [ ] Export utilities for data portability

## Integration with Existing Infrastructure

### 27. SQLite Database Integration (Enhanced)
- [ ] Create comprehensive HCE schema with FTS5 support:
  - [ ] Create `src/knowledge_system/hce/sqlite_schema.sql` with:
    ```sql
    -- Episodes table (maps to existing videos table or extends it)
    CREATE TABLE IF NOT EXISTS episodes (
      episode_id TEXT PRIMARY KEY,
      video_id TEXT UNIQUE,  -- FK to existing videos table
      title TEXT,
      recorded_at TEXT,
      inserted_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (video_id) REFERENCES videos(video_id)
    );
    
    -- Claims with proper constraints and scoring
    CREATE TABLE IF NOT EXISTS claims (
      episode_id TEXT NOT NULL,
      claim_id TEXT NOT NULL,
      canonical TEXT NOT NULL,
      claim_type TEXT CHECK (claim_type IN ('factual','causal','normative','forecast','definition')),
      tier TEXT CHECK (tier IN ('A','B','C')),
      first_mention_ts TEXT,
      scores_json TEXT NOT NULL,  -- {"importance":..., "novelty":...}
      inserted_at TEXT DEFAULT (datetime('now')),
      PRIMARY KEY (episode_id, claim_id),
      FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
    );
    
    -- Evidence spans with segment references
    CREATE TABLE IF NOT EXISTS evidence_spans (
      episode_id TEXT NOT NULL,
      claim_id TEXT NOT NULL,
      seq INTEGER NOT NULL,
      segment_id TEXT,
      t0 TEXT, t1 TEXT,
      quote TEXT,
      PRIMARY KEY (episode_id, claim_id, seq),
      FOREIGN KEY (episode_id, claim_id) REFERENCES claims(episode_id, claim_id) ON DELETE CASCADE
    );
    
    -- Full-text search indexes
    CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
      episode_id, claim_id, canonical, claim_type, content=''
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS quotes_fts USING fts5(
      episode_id, claim_id, quote, content=''
    );
    ```
- [ ] Create `src/knowledge_system/hce/storage_sqlite.py`:
  - [ ] Implement idempotent upsert functions
  - [ ] Add FTS5 indexing for search capabilities
  - [ ] Support both video_id and episode_id mappings
  - [ ] Enable WAL mode and proper foreign keys
- [ ] Create migration to map existing data:
  - [ ] Map video_id → episode_id
  - [ ] Convert MOC extractions to HCE entities
  - [ ] Preserve existing relationships

### 28. Bright Data Proxy Integration
- [ ] Enable Bright Data proxy support for HCE LLM calls:
  - [ ] Configure proxy for OpenAI/Anthropic API calls if needed
  - [ ] Use `BrightDataSessionManager` for session management
  - [ ] Track API costs in SQLite database
- [ ] Implement proxy rotation for large batch processing
- [ ] Add proxy health monitoring and fallback logic

### 29. Cost Optimization with Database
- [ ] Implement HCE result caching in SQLite:
  - [ ] Check for existing claims before processing
  - [ ] Reuse entity extractions across episodes
  - [ ] Cache embedding computations
- [ ] Deduplication at claim level using database queries
- [ ] Cost reporting integration with existing analytics

## Post-Implementation

### 30. Monitoring & Maintenance
- [ ] Set up error tracking integrated with existing logging
- [ ] Create performance dashboards using SQLite analytics
- [ ] Plan regular model updates
- [ ] Schedule security reviews
- [ ] Establish support channels


## Notes

- All tasks should maintain backward compatibility with legacy pipeline
- Feature flag `--use_hce` must default to False initially
- Each phase should be independently testable
- Performance should match or exceed legacy system
- User experience should be seamless during migration
