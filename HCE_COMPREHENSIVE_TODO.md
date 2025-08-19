# HCE Full Replacement - Comprehensive TODO List

## Status Overview
- Total Tasks: ~60
- Completed: ~15 (25%)
- In Progress: 0
- Remaining: ~45 (75%)

## Pre-Implementation Tasks (6 tasks)

### Environment Setup
- [ ] Create feature branch: `feature/hce-replacement`
- [ ] Update requirements.txt with HCE dependencies
- [ ] Create comprehensive backup of existing code
- [x] Document current API contracts for GUI integration ✅

### System Architecture Planning  
- [x] Map existing GUI touchpoints to new HCE outputs ✅
- [x] Design unified output format that satisfies current UI needs ✅
- [x] Plan database schema modifications ✅
- [ ] Create rollback strategy document

## Phase 1: Core Replacement (25 tasks)

### HCE Package Installation
- [x] Move `hce_kit/claim_extractor/` to `src/knowledge_system/processors/hce/` ✅
- [x] Update imports to match project structure ✅
- [x] Archive `summarizer.py` to `summarizer_legacy.py` ✅
- [x] Archive `moc.py` to `moc_legacy.py` ✅
- [x] Update `processors/__init__.py` to export HCE components ✅

### Database Schema Evolution
- [x] Create HCE schema migration files ✅
- [x] Create compatibility views for backward compatibility ✅
- [ ] Add processing_type column to summaries table
- [ ] Add hce_data_json column to summaries table
- [ ] Create data migration script for existing records
- [ ] Add FTS5 indexes for claim search
- [ ] Test migration on sample database

### Processor Replacement
- [x] Create HCE-based SummarizerProcessor ✅
- [x] Create HCE-based MOCProcessor ✅
- [x] Implement claim-to-summary formatting ✅
- [x] Implement HCE entity extraction ✅
- [ ] Add database persistence for HCE data
- [ ] Implement caching layer for embeddings

### GUI Integration Layer
- [ ] Create `gui/adapters/hce_adapter.py`
- [ ] Update ProcessPipelineWorker to use HCE
- [ ] Update EnhancedSummarizationWorker
- [ ] Update MOCGenerationWorker
- [ ] Add progress tracking for HCE stages

### Command Updates
- [ ] Update `commands/summarize.py` to save HCE data
- [ ] Update `commands/moc.py` entity extraction
- [ ] Update `commands/process.py` options
- [ ] Remove legacy summarization style options
- [ ] Add HCE-specific CLI options

### File Generation Updates
- [ ] Update FileGenerationService for HCE data
- [ ] Add claims report generation
- [ ] Add contradiction analysis output
- [ ] Add evidence mapping files
- [ ] Ensure backward-compatible file naming

### Configuration Updates
- [ ] Remove legacy summarization settings from config
- [ ] Add HCE model configurations
- [ ] Update settings GUI to remove old options
- [ ] Add claim extraction settings
- [ ] Add tier threshold configuration

## Phase 2: UI/UX Adaptation (12 tasks)

### Summarization Tab Updates
- [ ] Update tab to show claim extraction progress
- [ ] Add claim filtering controls
- [ ] Add tier selection UI
- [ ] Show relations and contradictions
- [ ] Update help text and tooltips
- [ ] Add claim count display

### Process Tab Enhancement
- [ ] Remove "summarization style" dropdown
- [ ] Add "analysis depth" slider
- [ ] Add claim tier selection
- [ ] Update results display format
- [ ] Add claim statistics view

### Output Format Compatibility
- [ ] Verify markdown file structure
- [ ] Ensure YAML frontmatter compatibility
- [ ] Test Obsidian workflow compatibility

## Phase 3: Advanced Features (10 tasks)

### Search and Discovery
- [ ] Add claim search to GUI
- [ ] Implement FTS search functionality
- [ ] Add filtering by type, tier, person
- [ ] Create claim explorer view
- [ ] Add relationship visualization

### Batch Processing
- [ ] Update batch processor for HCE
- [ ] Implement parallel claim extraction
- [ ] Add cross-video entity resolution
- [ ] Add progress tracking per stage
- [ ] Implement resume capability

## Phase 4: Migration and Cleanup (10 tasks)

### Data Migration
- [ ] Create migration tool for existing summaries
- [ ] Extract entities from old MOC data
- [ ] Preserve timestamps and metadata
- [ ] Validate migrated data
- [ ] Create rollback capability

### Code Cleanup
- [ ] Remove legacy processor files
- [ ] Remove unused imports
- [ ] Clean up old configuration
- [ ] Update all documentation
- [ ] Remove legacy tests

## Phase 5: Testing and Deployment (7 tasks)

### Testing
- [x] Create HCE-specific test suites ✅
- [x] Create acceptance tests ✅
- [ ] Add performance benchmarks
- [ ] Run full regression test suite

### Deployment
- [ ] Test in development environment
- [ ] Create beta testing plan
- [ ] Update user documentation
- [ ] Create migration guide

---

## Execution Plan

I will now work through these tasks systematically, starting with the highest priority items that block other work.
