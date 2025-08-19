# HCE (Hybrid Claim Extractor) Full Replacement Implementation TODO List

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
- [ ] Create feature branch: `feature/hce-replacement`
- [ ] Update requirements.txt with HCE dependencies:
  - [ ] Add pydantic>=2.0
  - [ ] Add sentence-transformers for embeddings
  - [ ] Add transformers for cross-encoder support
  - [ ] Add hdbscan for clustering
  - [ ] Add scipy for clustering metrics
  - [ ] Update torch/tensorflow requirements
- [ ] Create comprehensive backup of existing code
- [ ] Document current API contracts for GUI integration

### 2. System Architecture Planning
- [x] Map existing GUI touchpoints to new HCE outputs ✅ COMPLETED (see HCE_Integration_Report.md)
- [x] Design unified output format that satisfies current UI needs ✅ COMPLETED
- [x] Plan database schema modifications ✅ COMPLETED (migrations ready)
- [ ] Create rollback strategy

## Phase 1: Core Replacement

### 3. HCE Package Installation
- [ ] Move `hce_kit/claim_extractor/` to `src/knowledge_system/processors/hce/`
- [ ] Update imports to match project structure
- [ ] Remove conflicting legacy processors:
  - [ ] Archive `summarizer.py` to `legacy/`
  - [ ] Archive `moc.py` to `legacy/`
- [ ] Update `processors/__init__.py` to export HCE components

### 4. Database Schema Evolution
- [ ] Extend existing SQLite schema:
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
- [ ] Create migration script for existing data
- [ ] Add FTS5 indexes for claim search

### 5. Processor Replacement
- [ ] Create `src/knowledge_system/processors/hce_processor.py`:
  ```python
  class HCEProcessor(BaseProcessor):
      """Unified processor that replaces SummarizerProcessor and MOCProcessor"""
      
      def process(self, input_data):
          # Convert input to EpisodeBundle
          # Run HCE pipeline
          # Return structured output compatible with GUI
  ```
- [ ] Implement adapters for existing interfaces:
  - [ ] `get_summary()` → Returns claim-based summary
  - [ ] `get_people()` → Returns HCE people entities
  - [ ] `get_tags()` → Returns concepts as tags
  - [ ] `get_jargon()` → Returns HCE jargon terms

### 6. GUI Integration Layer
- [ ] Create `src/knowledge_system/gui/adapters/hce_adapter.py`:
  - [ ] Convert HCE outputs to formats expected by GUI
  - [ ] Maintain existing field names and structures
  - [ ] Add new fields as optional enhancements
- [ ] Update worker classes to use HCEProcessor:
  - [ ] `ProcessPipelineWorker`
  - [ ] `SummarizationWorker`
  - [ ] `MOCGenerationWorker`

### 7. Command Updates
- [ ] Replace summarization logic in `commands/summarize.py`:
  - [ ] Remove LLM-based summarization
  - [ ] Use HCE claim extraction
  - [ ] Format claims as readable summary
- [ ] Replace MOC logic in `commands/moc.py`:
  - [ ] Use HCE entity extractors
  - [ ] Maintain same output file structure
- [ ] Update `commands/process.py`:
  - [ ] Remove option toggles for summarization styles
  - [ ] Add HCE-specific options (tier filtering, etc.)

### 8. File Generation Updates
- [ ] Modify `services/file_generation.py`:
  - [ ] Generate summaries from claims and relations
  - [ ] Create MOC files from HCE entities
  - [ ] Add new formats:
    - [ ] Claims report (markdown with tiers)
    - [ ] Contradiction analysis
    - [ ] Evidence mapping
- [ ] Ensure backward-compatible file naming

### 9. Configuration Simplification
- [ ] Update `config.py`:
  - [ ] Remove legacy summarization settings
  - [ ] Add HCE model configurations
  - [ ] Simplify LLM provider settings
- [ ] Update settings GUI:
  - [ ] Remove summarization style options
  - [ ] Add claim extraction settings
  - [ ] Add tier thresholds

## Phase 2: UI/UX Adaptation

### 10. Summarization Tab Transformation
- [ ] Rename "Summarization" to "Analysis" or keep name
- [ ] Update tab functionality:
  - [ ] Input: transcript/document
  - [ ] Output: structured claims instead of summary
  - [ ] Add claim filtering controls
  - [ ] Show relations and contradictions
- [ ] Maintain progress tracking
- [ ] Update help text and tooltips

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
- [ ] Create migration tool:
  - [ ] Convert existing summaries to claim format
  - [ ] Extract entities from old MOC data
  - [ ] Preserve timestamps and metadata
- [ ] Validate migrated data
- [ ] Create rollback capability

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
