# Knowledge Chipper Refactor TODO List

**Created**: 2024-12-19
**Status**: Active
**Purpose**: Track implementation of revised Knowledge Chipper architecture

---

## Priority 1: Critical Database Schema Changes

### 1.1 Rename 'videos' table to 'media_sources'
- **Complexity**: Medium
- **Files to modify**:
  - `src/knowledge_system/database/models.py` - Update Video class to MediaSource
  - `src/knowledge_system/database/service.py` - Update all video-related methods
  - `src/knowledge_system/database/migrations/` - Create migration script
  - All processors that reference Video model (~15 files)
  - GUI components referencing videos (~8 files)
- **Dependencies**: None
- **Notes**: This is foundational - must be done first

### 1.2 Split evidence table into 'claim_sources' and 'supporting_evidence'
- **Complexity**: Complex
- **Files to modify**:
  - `src/knowledge_system/database/hce_models.py` - Split EvidenceSpan model
  - `src/knowledge_system/processors/hce/evidence.py` - Update evidence extraction
  - `src/knowledge_system/database/migrations/` - Migration for table split
- **Dependencies**: 1.1 must be complete
- **Notes**: Disambiguates where claim was made vs cited support

### 1.3 Add configurable tables
- **Complexity**: Medium
- **New tables needed**:
  - `claim_types` - Move hardcoded types from code
  - `quality_criteria` - Extensible quality assessment rules
  - `quality_weights` - Configurable tier thresholds
  - `claim_clusters` - Semantic grouping
  - `metadata_groups` - Non-semantic grouping
- **Files to modify**:
  - `src/knowledge_system/database/models.py` - Add new model classes
  - `src/knowledge_system/database/hce_models.py` - Update relationships
- **Dependencies**: 1.1 complete

### 1.4 Add sync_status column for Supabase
- **Complexity**: Simple
- **Files to modify**:
  - All model classes in `models.py` and `hce_models.py`
  - Add: `sync_status = Column(String(20), default='pending')`
  - Add: `last_synced = Column(DateTime)`
- **Dependencies**: 1.1, 1.3 complete

---

## Priority 2: Terminology Standardization

### 2.1 Replace "belief statements" with "claims"
- **Complexity**: Simple
- **Files to modify**:
  - `src/knowledge_system/processors/moc.py` - Rename Belief class to ClaimBelief
  - `data/test_files/beliefs.yaml` → `claims.yaml`
  - All prompt files in `config/prompts/`
  - Documentation files
- **Dependencies**: None
- **Notes**: Global find/replace with careful review

### 2.2 Update "video" to "media_source" references
- **Complexity**: Medium
- **Files to modify**:
  - All processors (~20 files)
  - All GUI components (~10 files)
  - CLI commands (~5 files)
- **Dependencies**: 1.1 complete
- **Notes**: Not all "video" references change - only those referring to audio tracks

### 2.3 Disambiguate "evidence" terminology
- **Complexity**: Simple
- **Files to modify**:
  - Update variable names and docstrings
  - Clarify in prompts what constitutes evidence vs source
- **Dependencies**: 1.2 complete

---

## Priority 3: Core Feature Refactoring

### 3.1 Consolidate Entity Extraction
- **Complexity**: Complex
- **Files to modify**:
  - Create `src/knowledge_system/processors/hce/unified_extractor.py`
  - Remove or deprecate: `people.py`, `concepts.py`, `jargon.py`, `glossary.py`
  - Update `src/knowledge_system/processors/hce/miner.py` to use unified extraction
- **Dependencies**: None
- **New functionality**:
  - Single LLM call per chunk returning JSON with all entities
  - Structured prompt template for unified extraction

### 3.2 Configuration System Implementation
- **Complexity**: Medium
- **Files to create**:
  - `src/knowledge_system/admin/config_manager.py`
  - `src/knowledge_system/gui/tabs/admin_config_tab.py`
- **Dependencies**: 1.3 complete
- **Features**:
  - UI for editing claim types
  - UI for quality criteria management
  - Database-driven configuration loading

### 3.3 Document Type Detection
- **Complexity**: Medium
- **Files to modify**:
  - `src/knowledge_system/processors/base.py` - Add document type detection
  - Create `src/knowledge_system/processors/document_classifier.py`
- **Dependencies**: None
- **Features**:
  - Detect transcript vs article/paper
  - Extract author/publication metadata
  - Route to appropriate pipeline

### 3.4 SQLite-First Output Control
- **Complexity**: Medium
- **Files to modify**:
  - All processors that write .md files (~10 files)
  - Add `export_to_markdown=False` default parameter
  - Create `src/knowledge_system/services/markdown_exporter.py`
- **Dependencies**: Database schema changes complete
- **Notes**: Critical architectural change - no file writes unless requested

---

## Priority 4: New UI Components

### 4.1 Speaker Attribution Confirmation UI
- **Complexity**: Medium
- **Files to create**:
  - `src/knowledge_system/gui/dialogs/speaker_attribution_dialog.py`
  - `src/knowledge_system/gui/widgets/speaker_editor.py`
- **Dependencies**: None
- **Features**:
  - Show diarization results
  - Allow user to correct speaker labels
  - Save corrections to database

### 4.2 Post-Summary Cleanup UI
- **Complexity**: Complex
- **Files to create**:
  - `src/knowledge_system/gui/tabs/cleanup_tab.py`
  - `src/knowledge_system/gui/widgets/entity_reviewer.py`
- **Dependencies**: 3.1 complete
- **Features**:
  - Review extracted entities
  - Correct misidentified items
  - Capture gold training data

### 4.3 Claim Tier Review Interface
- **Complexity**: Medium
- **Files to create**:
  - `src/knowledge_system/gui/dialogs/claim_review_dialog.py`
- **Dependencies**: 1.3 complete
- **Features**:
  - Display claims by tier
  - Allow tier reassignment
  - Show quality criteria reasoning

---

## Priority 5: Cloud Integration

### 5.1 Supabase Sync Mechanism
- **Complexity**: Complex
- **Files to create**:
  - `src/knowledge_system/sync/supabase_sync.py`
  - `src/knowledge_system/sync/conflict_resolver.py`
  - `src/knowledge_system/database/sync_manager.py`
- **Dependencies**: 1.4 complete
- **Features**:
  - Bidirectional sync SQLite ↔ Supabase
  - Conflict resolution strategy
  - Sync status tracking

### 5.2 Cloud Deployment Strategy
- **Complexity**: Complex
- **Files to create**:
  - `deployment/cloud/requirements.txt`
  - `deployment/cloud/aws_deploy.py`
  - `deployment/cloud/docker/Dockerfile`
- **Dependencies**: 5.1 complete
- **Notes**: Define what stays local vs cloud

---

## Priority 6: Code Cleanup & Documentation

### 6.1 Remove/Justify HCE EpisodeBundle
- **Complexity**: Medium
- **Files to modify**:
  - Evaluate if `EpisodeBundle` adds value
  - If removing, refactor ~10 files
- **Dependencies**: Core refactoring complete
- **Decision needed**: Keep or remove abstraction

### 6.2 Consolidate Deduplication Logic
- **Complexity**: Simple
- **Files to modify**:
  - `src/knowledge_system/processors/hce/dedupe.py`
  - `src/knowledge_system/utils/deduplication.py`
- **Dependencies**: None
- **Notes**: Merge duplicate implementations

### 6.3 Documentation Updates
- **Complexity**: Medium
- **Files to create/update**:
  - `docs/CLAIM_EXTRACTION_METHODOLOGY.md`
  - `docs/KNOWLEDGE_HIERARCHY.md`
  - `docs/EPISTEMIC_WEIGHTS.md`
- **Dependencies**: Implementation complete
- **Required definitions**:
  - 3 levels of hierarchical knowledge structure
  - Concept prerequisites system
  - Learning pathways methodology
  - Epistemic weight calculation

---

## Implementation Order

### Phase 1: Foundation (Weeks 1-2)
1. Database schema changes (1.1-1.4)
2. Terminology standardization (2.1-2.3)
3. Document claim extraction methodology

### Phase 2: Core Refactoring (Weeks 3-4)
1. Consolidate entity extraction (3.1)
2. Implement configuration system (3.2)
3. SQLite-first output control (3.4)

### Phase 3: UI Enhancements (Weeks 5-6)
1. Speaker attribution UI (4.1)
2. Post-summary cleanup UI (4.2)
3. Document type handling (3.3)

### Phase 4: Cloud & Polish (Weeks 7-8)
1. Supabase integration (5.1)
2. Code cleanup (6.1-6.2)
3. Complete documentation (6.3)

---

## Progress Tracking

- [ ] Phase 1: Foundation
  - [ ] 1.1 Rename videos → media_sources
  - [ ] 1.2 Split evidence tables
  - [ ] 1.3 Add configurable tables
  - [ ] 1.4 Add sync_status columns
  - [ ] 2.1 Replace "belief" → "claims"
  - [ ] 2.2 Update video → media_source
  - [ ] 2.3 Disambiguate evidence

- [ ] Phase 2: Core Refactoring
  - [ ] 3.1 Unified entity extraction
  - [ ] 3.2 Configuration system
  - [ ] 3.4 SQLite-first outputs

- [ ] Phase 3: UI Enhancements
  - [ ] 4.1 Speaker attribution UI
  - [ ] 4.2 Cleanup UI
  - [ ] 3.3 Document type detection

- [ ] Phase 4: Cloud & Polish
  - [ ] 5.1 Supabase sync
  - [ ] 6.1 Remove/justify EpisodeBundle
  - [ ] 6.2 Consolidate deduplication
  - [ ] 6.3 Complete documentation

---

## Important Clarifications & Technical Details

### Database Migration Strategy
1. **Migration Order**: 
   - Create new tables first (claim_types, quality_criteria, etc.)
   - Populate configuration tables with current hardcoded values
   - Then rename videos → media_sources with foreign key updates
   - Finally split evidence tables

2. **Backward Compatibility**:
   - Create database views with old table names during transition
   - Version the database schema (add schema_version table)
   - Support reading from both old and new schemas for 1 release cycle

### Unified Entity Extraction Details
1. **Chunk Size**: Define optimal chunk size (current: ~1000 tokens?)
2. **Prompt Structure**: 
   ```json
   {
     "claims": [{"text": "", "type": "", "confidence": 0.0}],
     "people": [{"name": "", "role": "", "context": ""}],
     "concepts": [{"term": "", "definition": "", "domain": ""}],
     "jargon": [{"term": "", "meaning": "", "acronym_of": ""}],
     "mental_models": [{"name": "", "description": "", "application": ""}]
   }
   ```
3. **Error Handling**: Graceful fallback if LLM returns malformed JSON

### Quality Assessment Criteria
1. **Default Tiers**:
   - **A**: High confidence, specific, verifiable, well-supported
   - **B**: Moderate confidence, somewhat specific, partially supported
   - **C**: Low confidence, vague, unsupported or speculative
   
2. **Configurable Weights**:
   - Specificity: 0.3
   - Supporting evidence: 0.3
   - Logical coherence: 0.2
   - Source credibility: 0.2

### Supabase Sync Architecture
1. **Sync Direction**:
   - SQLite → Supabase: All data except temp/cache tables
   - Supabase → SQLite: Only shared/collaborative data
   
2. **Conflict Resolution**:
   - Last-write-wins for metadata
   - Merge strategy for claims/entities (union, not overwrite)
   - User prompt for actual conflicts

3. **Performance Considerations**:
   - Batch sync operations (100 records at a time)
   - Delta sync only (track last_modified timestamps)
   - Async background sync with progress indication

### File Export Behavior Changes
1. **Current**: Files written immediately during processing
2. **New**: All data to SQLite, export only when:
   - User clicks "Export to Markdown" 
   - CLI flag `--export-markdown` is set
   - Scheduled export job runs
   
3. **Export Formats**:
   - Markdown (current)
   - JSON (for API consumption)
   - CSV (for analysis tools)

### Testing Requirements
1. **Unit Tests**: Each new module needs 80%+ coverage
2. **Integration Tests**: Full pipeline tests with sample data
3. **Migration Tests**: Ensure data integrity during schema changes
4. **Performance Tests**: Ensure no regression in processing speed

## Notes

1. **Bright Data Integration**: WebShare references should be updated to Bright Data throughout
2. **Thumbnail Storage**: Change to SQLite-first, file export only on demand
3. **Claim Types**: Current hardcoded types need database migration
4. **Quality Tiers**: A/B/C system needs configurable criteria
5. **Gold Training Set**: User corrections should be captured for future model training
6. **LLM Model Selection**: Consider using lighter models for initial extraction, heavier for final summary
7. **Batch Processing**: Implement proper batch processing for multiple files to optimize LLM calls

## Risk Mitigation

1. **Database Migrations**: Create comprehensive backup strategy before schema changes
2. **Backward Compatibility**: Maintain read compatibility with old schema during transition
3. **Testing**: Each phase needs comprehensive test coverage before moving forward
4. **User Communication**: Document breaking changes for existing users
5. **Rollback Plan**: Each migration must have a tested rollback script
6. **Feature Flags**: Use feature flags to gradually roll out changes

---

## Open Questions Requiring Decisions

1. **HCE EpisodeBundle**: Is this abstraction necessary or can we work directly with transcripts/documents?
   - Current: Adds conversion overhead
   - Alternative: Direct processing from source data
   - Decision needed by: Phase 2

2. **Claim Type Extensibility**: How flexible should claim types be?
   - Option A: Fixed set in database (factual, causal, normative, forecast, definition)
   - Option B: Fully user-definable with validation rules
   - Decision needed by: Phase 1

3. **Knowledge Hierarchy Definition**: What are the "3 levels" mentioned?
   - Proposal: Topics → Concepts → Details
   - Alternative: Domains → Theories → Applications
   - Decision needed by: Phase 3

4. **Learning Pathways**: How to implement prerequisite tracking?
   - Graph-based (concepts as nodes, prerequisites as edges)
   - Linear sequences with branching
   - Decision needed by: Phase 4

5. **Bright Data API Limitations**: 
   - Can it handle RSS feeds or only YouTube?
   - What's the fallback if API fails?
   - Cost implications for heavy usage?

6. **Export Timing**: When should .md files be generated?
   - Option A: Never automatically, always manual
   - Option B: Configurable auto-export rules
   - Option C: Export on completion with flag to disable

---

## Performance Optimization Targets

1. **LLM Call Reduction**:
   - Current: Multiple calls per chunk (people, concepts, claims separately)
   - Target: 1 call per chunk for all entities
   - Expected improvement: 70% reduction in API calls

2. **Database Write Optimization**:
   - Current: Individual inserts during processing
   - Target: Batch inserts with transaction management
   - Expected improvement: 10x faster database writes

3. **Memory Usage**:
   - Current: Full document in memory
   - Target: Streaming processing for large documents
   - Expected improvement: Handle 10x larger documents

4. **Sync Performance**:
   - Target: < 2 seconds for 1000 record delta sync
   - Background sync should not block UI
   - Implement progressive sync for large datasets

---

## Success Metrics

1. **Code Quality**:
   - Test coverage > 80%
   - Type hints on all new code
   - Zero mypy errors in refactored modules

2. **Performance**:
   - Processing speed within 10% of current
   - Memory usage reduced by 30%
   - Database size reduced by 20% (better normalization)

3. **User Experience**:
   - Zero data loss during migration
   - Clear migration documentation
   - Backward compatibility for 1 release cycle

4. **Maintainability**:
   - Reduced code duplication by 50%
   - Clear separation of concerns
   - Comprehensive documentation
