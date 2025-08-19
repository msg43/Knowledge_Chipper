# HCE (Hybrid Claim Extractor) Full Replacement Implementation TODO List

## Progress Summary
**Overall Progress: ~45% Complete (35+ completed items)**

### Phase Breakdown:
- ✅ **Pre-Implementation**: 100% (7/7)
- ✅ **Core Replacement**: 100% (26/26)
  - ✅ HCE Package Installation: 100% (4/4)
  - ✅ Database Schema Evolution: 100% (3/3)
  - ✅ Processor Replacement: 100% (2/2)
  - ✅ GUI Integration Layer: 100% (7/7)
  - ✅ Command Updates: 100% (12/12)
  - ✅ File Generation Updates: 100% (5/5)
  - ✅ Configuration: 100% (6/6)
- ⏳ **UI/UX Adaptation**: 20% (3/15)
- ⏳ **Advanced Features**: 0% (0/11)
- ⏳ **Migration & Cleanup**: 17% (2/12)
- ⏳ **Testing & Deployment**: 0% (0/9)

**Last Updated: 2024-01-25 by completing Core Replacement phase**

## Overview
This document outlines the implementation plan for **completely replacing** the existing summarization and MOC system with the Hybrid Claim Extractor (HCE) system. This is a full replacement approach - no legacy system preservation or feature flags needed.

## Key Differences from Integration Approach
- **No feature flags** - HCE becomes the only system
- **Direct replacement** of SummarizerProcessor and MOCProcessor
- **Simplified implementation** - no dual code paths
- **Same UI/UX** - users see the same tabs and functionality
- **Enhanced outputs** - structured claims instead of simple summaries

## Pre-Implementation Tasks

### 1. Environment Setup
- [x] Create feature branch: `feature/hce-replacement` ✅ COMPLETED
- [x] Update requirements.txt with HCE dependencies: ✅ COMPLETED
  - [x] Add pydantic>=2.0
  - [x] Add sentence-transformers for embeddings
  - [x] Add transformers for cross-encoder support
  - [x] Add hdbscan for clustering
  - [x] Add scipy for clustering metrics
  - [x] Update torch/tensorflow requirements
- [x] Create comprehensive backup of existing code ✅ COMPLETED (via git commits)
- [x] Document current API contracts for GUI integration ✅ COMPLETED (in HCE_Integration_Report.md)

### 2. System Architecture Planning
- [x] Map existing GUI touchpoints to new HCE outputs ✅ COMPLETED (see HCE_Integration_Report.md)
- [x] Design unified output format that satisfies current UI needs ✅ COMPLETED
- [x] Plan database schema modifications ✅ COMPLETED (migrations ready)
- [x] Create rollback strategy ✅ COMPLETED (docs/HCE_ROLLBACK_STRATEGY.md)

## Phase 1: Core Replacement

### 3. HCE Package Installation
- [x] Move `hce_kit/claim_extractor/` to `src/knowledge_system/processors/hce/` ✅ COMPLETED
- [x] Update imports to match project structure ✅ COMPLETED
- [x] Remove conflicting legacy processors: ✅ COMPLETED
  - [x] Archive `summarizer.py` to `legacy/` (renamed to summarizer_legacy.py)
  - [x] Archive `moc.py` to `legacy/` (renamed to moc_legacy.py)
- [x] Update `processors/__init__.py` to export HCE components ✅ COMPLETED

### 4. Database Schema Evolution
- [x] Extend existing SQLite schema: ✅ COMPLETED
  ```sql
  -- Modify existing tables to support HCE
  ALTER TABLE summaries ADD COLUMN processing_type TEXT DEFAULT 'legacy';
  ALTER TABLE summaries ADD COLUMN hce_data_json TEXT;
  
  -- Add HCE-specific tables
  CREATE TABLE claims (
    video_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    canonical TEXT NOT NULL,
    claim_type TEXT,
    tier TEXT,
    scores_json TEXT,
    evidence_json TEXT,
    PRIMARY KEY (video_id, claim_id),
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
  );
  
  CREATE TABLE claim_relations (
    video_id TEXT NOT NULL,
    source_claim_id TEXT NOT NULL,
    target_claim_id TEXT NOT NULL,
    relation_type TEXT,
    strength REAL,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
  );
  ```
- [x] Create migration script for existing data ✅ COMPLETED (migrate_legacy_data.py)
- [x] Add FTS5 indexes for claim search ✅ COMPLETED (in HCE schema)

### 5. Processor Replacement
- [x] Create HCE processors: ✅ COMPLETED (created adapters instead)
  ```python
  class HCEProcessor(BaseProcessor):
      """Unified processor that replaces SummarizerProcessor and MOCProcessor"""
      
      def process(self, input_data):
          # Convert input to EpisodeBundle
          # Run HCE pipeline
          # Return structured output compatible with GUI
  ```
- [x] Implement adapters for existing interfaces: ✅ COMPLETED
  - [x] `get_summary()` → Returns claim-based summary
  - [x] `get_people()` → Returns HCE people entities
  - [x] `get_tags()` → Returns concepts as tags
  - [x] `get_jargon()` → Returns HCE jargon terms

### 6. GUI Integration Layer
- [x] Create `src/knowledge_system/gui/adapters/hce_adapter.py`: ✅ COMPLETED
  - [x] Convert HCE outputs to formats expected by GUI
  - [x] Maintain existing field names and structures
  - [x] Add new fields as optional enhancements
- [x] Update worker classes to use HCEProcessor: ✅ COMPLETED
  - [x] `ProcessPipelineWorker`
  - [x] `EnhancedSummarizationWorker` 
  - [x] MOC generation handled in ProcessPipelineWorker
- [x] Add HCE progress tracking dialog ✅ COMPLETED

### 7. Command Updates
- [x] Replace summarization logic in `commands/summarize.py`: ✅ COMPLETED
  - [x] Remove LLM-based summarization
  - [x] Use HCE claim extraction
  - [x] Format claims as readable summary
  - [x] Added HCE-specific CLI options (min-claim-tier, max-claims, etc.)
  - Note: Database saving happens in SummarizerProcessor when video_id is provided
- [x] Replace MOC logic in `commands/moc.py`: ✅ COMPLETED
  - [x] Use HCE entity extractors
  - [x] Maintain same output file structure
  - [x] Added use_database_entities option
- [x] Update `commands/process.py`: ✅ COMPLETED
  - [x] Remove option toggles for summarization styles
  - [x] Updated to show HCE processing in output

### 8. File Generation Updates
- [x] Modify `services/file_generation.py`: ✅ COMPLETED
  - [x] Generate summaries from claims and relations
  - [x] Create MOC files from HCE entities
  - [x] Add new formats: ✅ COMPLETED
    - [x] Claims report (markdown with tiers)
    - [x] Contradiction analysis
    - [x] Evidence mapping
- [x] Ensure backward-compatible file naming ✅ COMPLETED

### 9. Configuration Simplification
- [x] Update `config.py`: ✅ COMPLETED
  - [x] Remove legacy summarization settings (removed focus option)
  - [x] Add HCE model configurations (HCEConfig class)
  - [x] Simplify LLM provider settings (kept as-is)
- [x] Update settings GUI: ✅ COMPLETED
  - [x] Remove summarization style options (none existed)
  - [x] Add claim extraction settings (in HCEConfig)
  - [x] Add tier thresholds (tier_a_threshold, tier_b_threshold)

## Phase 2: UI/UX Adaptation

### 10. Summarization Tab Transformation
- [x] Rename "Summarization" to "Analysis" or keep name: ✅ Updated to "Claim Extraction & Analysis"
- [ ] Update tab functionality:
  - [x] Input: transcript/document (unchanged)
  - [x] Output: structured claims instead of summary (done via processors)
  - [ ] Add claim filtering controls
  - [ ] Show relations and contradictions
- [x] Maintain progress tracking ✅ COMPLETED
- [x] Update help text and tooltips ✅ COMPLETED

### 11. Process Tab Enhancement
- [ ] Update processing options:
  - [ ] Remove "summarization style" dropdown
  - [ ] Add "analysis depth" slider
  - [ ] Add claim tier selection
- [ ] Update results display:
  - [ ] Show claim count
  - [ ] Display top claims
  - [ ] Link to full analysis

### 12. Output Format Compatibility
- [ ] Ensure markdown files contain:
  - [ ] Executive summary (from A-tier claims)
  - [ ] Key claims by category
  - [ ] People, concepts, and jargon sections
  - [ ] Evidence citations
- [ ] Maintain YAML frontmatter compatibility
- [ ] Support existing Obsidian workflows

## Phase 3: Advanced Features

### 13. Search and Discovery
- [ ] Add claim search to GUI:
  - [ ] Full-text search across claims
  - [ ] Filter by type, tier, person
  - [ ] Cross-video claim tracking
- [ ] Create claim explorer view
- [ ] Add relationship visualization

### 14. Batch Processing Updates
- [ ] Modify batch processor for HCE:
  - [ ] Parallel claim extraction
  - [ ] Cross-video entity resolution
  - [ ] Consolidated reports
- [ ] Add progress per stage
- [ ] Implement resume capability

### 15. Performance Optimization
- [ ] Cache embeddings in SQLite
- [ ] Reuse entity extractions
- [ ] Implement claim deduplication
- [ ] Add SQLite query optimization

## Phase 4: Migration and Cleanup

### 16. Data Migration
- [x] Create migration tool: ✅ COMPLETED (migrate_legacy_data.py)
  - [x] Mark existing summaries as processing_type='legacy'
  - [ ] Extract entities from old MOC data
  - [x] Preserve timestamps and metadata ✅ COMPLETED
- [ ] Validate migrated data
- [x] Create rollback capability ✅ COMPLETED (database backup)

### 17. Code Cleanup
- [ ] Remove legacy processors:
  - [ ] Delete archived files
  - [ ] Remove unused imports
  - [ ] Clean up configuration
- [ ] Update documentation
- [ ] Remove legacy tests

### 18. Testing Suite
- [ ] Update existing tests:
  - [ ] Replace summarizer tests with HCE tests
  - [ ] Update MOC tests for new format
  - [ ] Verify GUI integration
- [ ] Add HCE-specific tests:
  - [ ] Claim extraction accuracy
  - [ ] Entity resolution
  - [ ] Relation detection
- [ ] Performance benchmarks

## Additional Completed Tasks (Not in Original List)
These tasks were completed as part of the implementation but weren't explicitly listed:

- [x] Created database persistence method `save_hce_data()` in DatabaseService
- [x] Extended database models with `processing_type` and `hce_data_json` columns
- [x] Created HCE-specific test files (test_summarizer_hce.py, test_moc_hce.py)
- [x] Created migration test (test_hce_migration.py)
- [x] Created comprehensive progress report (HCE_PROGRESS_REPORT.md)
- [x] Implemented database saving in SummarizerProcessor.process()
- [x] Set up HCE models imports in database/__init__.py

## Deployment Strategy

### 19. Staged Rollout
- [ ] Phase 1: Development environment
  - [ ] Full system test
  - [ ] Performance validation
  - [ ] Bug fixes
- [ ] Phase 2: Beta testing
  - [ ] Limited user group
  - [ ] Feedback collection
  - [ ] UI/UX refinement
- [ ] Phase 3: Full deployment
  - [ ] All users migrated
  - [ ] Legacy code removed
  - [ ] Documentation updated

### 20. User Communication
- [ ] Update all documentation
- [ ] Create migration guide
- [ ] Announce changes
