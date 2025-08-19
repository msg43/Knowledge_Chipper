# HCE Integration Report

**Author**: Cursor Integration Engineer  
**Date**: 2024-01-18  
**Status**: Planning Phase (Updated)

## Executive Summary

This report documents the COMPLETE REPLACEMENT of the legacy summarizer with the Hybrid Claim Extractor (HCE) system in the Knowledge Chipper codebase. The HCE system will replace all existing summarization and MOC functionality while maintaining identical external behavior (UI tabs, filenames, API response shapes).

**Important Note**: This is a FULL REPLACEMENT with NO feature flags. HCE becomes the sole path for summarization and content analysis. The existing SQLite database infrastructure (7 tables) and Bright Data proxy system are preserved and extended with HCE-specific tables.

**Repo Scan Date**: 2024-01-20
**Status**: Replacement Implementation (No Legacy Preservation)

## BEFORE/AFTER Replacement Mapping

### Complete Entrypoint Mapping

Based on comprehensive repo scan, here are ALL entrypoints and their HCE replacement strategy:

#### CLI Entrypoints

| BEFORE (Legacy) | AFTER (HCE) | File Location |
|-----------------|-------------|---------------|
| `chipper summarize` | HCE adapter in `summarize` command | `src/knowledge_system/commands/summarize.py` |
| `chipper process --summarize` | HCE adapter in `process` command | `src/knowledge_system/commands/process.py` |
| `chipper moc` | HCE entity extractors in `moc` command | `src/knowledge_system/commands/moc.py` |
| `chipper watch` (auto-summarize) | HCE adapter in watcher callbacks | `src/knowledge_system/watchers.py` |

#### Service Layer

| BEFORE (Legacy) | AFTER (HCE) | File Location |
|-----------------|-------------|---------------|
| `SummarizerProcessor` | `HCEProcessor` via adapter | `src/knowledge_system/processors/summarizer.py` → `hce_adapter.py` |
| `MOCProcessor` | `HCEProcessor` entity extraction | `src/knowledge_system/processors/moc.py` → `hce_adapter.py` |
| `FileGenerationService` | Extended for HCE outputs | `src/knowledge_system/services/file_generation.py` |
| `DatabaseService` | Extended with HCE tables + views | `src/knowledge_system/database/service.py` |

#### GUI Integration Points

| BEFORE (Legacy) | AFTER (HCE) | File Location |
|-----------------|-------------|---------------|
| `EnhancedSummarizationWorker` | Uses `HCEProcessor` via adapter | `src/knowledge_system/gui/workers/processing_workers.py` |
| `ProcessPipelineWorker` | Uses `HCEProcessor` for both steps | `src/knowledge_system/gui/tabs/process_tab.py` |
| `SummarizationTab` | Unchanged UI, HCE backend | `src/knowledge_system/gui/tabs/summarization_tab.py` |
| Tab names | UNCHANGED - same UI tabs | `src/knowledge_system/gui/main_window_pyqt6.py` |

#### Database Integration

| BEFORE (Legacy Tables) | AFTER (Compatibility Views) | Purpose |
|------------------------|------------------------------|---------|
| Direct `summaries` table access | `summaries` + HCE data in JSON | Backward compatible reads |
| Direct `moc_extractions` table | Views over `people`, `concepts`, `jargon` | Entity compatibility |
| N/A | `claims`, `evidence_spans`, `relations` | New HCE tables |
| N/A | `claims_fts`, `quotes_fts` | Full-text search |

### File Output Compatibility

| Output Type | BEFORE Filename | AFTER Filename | Location |
|-------------|-----------------|----------------|----------|
| Transcript | `{video_id}_transcript.md` | UNCHANGED | `output/transcripts/` |
| Summary | `{video_id}_summary.md` | UNCHANGED | `output/summaries/` |
| MOC People | `People.md` | UNCHANGED | `output/moc/` |
| MOC Tags | `Tags.md` | UNCHANGED | `output/moc/` |
| MOC Jargon | `Jargon.md` | UNCHANGED | `output/moc/` |
| Beliefs | `beliefs.yaml` | UNCHANGED | `output/moc/` |

## Legacy Component Mapping

### Current Architecture Overview

The Knowledge Chipper system currently consists of:

1. **Input Processing**
   - `AudioProcessor`: Handles audio/video transcription via Whisper
   - `YouTubeTranscriptProcessor`: Extracts existing YouTube transcripts
   - `PDFProcessor`: Extracts text from PDFs
   - `SpeakerDiarizationProcessor`: Identifies speakers in audio
   - **Bright Data Integration**: Proxy system for YouTube downloads with session management

2. **Content Processing**
   - `SummarizerProcessor`: Creates summaries using LLMs
   - `MOCProcessor`: Generates Maps of Content (people, tags, mental models, jargon)
   
3. **Data Storage**
   - **SQLite Database**: Comprehensive schema with 7 tables:
     - `videos`: Core video records with metadata
     - `transcripts`: Multiple transcript versions per video
     - `summaries`: LLM-generated summaries with cost tracking
     - `moc_extractions`: Extracted entities (people, tags, models, jargon)
     - `generated_files`: Track all output files
     - `processing_jobs`: Batch job tracking
     - `bright_data_sessions`: Proxy session and cost management
   - **DatabaseService**: CRUD operations and analytics
   
4. **Output Generation**
   - `FileGenerationService`: Regenerates files from SQLite data
   - Markdown files with summaries
   - YAML files with structured data
   - MOC pages for Obsidian

### HCE Module Mapping

| Legacy Component | HCE Module | Integration Strategy |
|-----------------|------------|---------------------|
| `AudioProcessor` + `SpeakerDiarizationProcessor` | Input to `EpisodeBundle` | Create converter to transform diarized transcripts into HCE segments |
| `SummarizerProcessor` | `Miner` + `Judge` + `Consolidator` | Replace summarization with claim extraction pipeline |
| `MOCProcessor` (people extraction) | `PeopleExtractor` | Enhanced with disambiguation and cross-episode tracking |
| `MOCProcessor` (tags) | `ConceptExtractor` | Mental models with definitions and evidence |
| `MOCProcessor` (jargon) | `GlossaryExtractor` | Technical terms with context and definitions |
| Markdown output | `ExportModule` | Enhanced with timestamps, backlinks, and relations |
| YAML beliefs | `ScoredClaim` + `Relations` | Structured claims with evidence and relationships |

## Implementation Strategy

### Adapter Pattern Implementation

The key to seamless replacement is the `summarizer_adapter.py` that maintains exact API compatibility:

```python
# src/knowledge_system/processors/summarizer_adapter.py
class SummarizerProcessor(BaseProcessor):
    """Drop-in replacement for legacy SummarizerProcessor using HCE."""
    
    def __init__(self, provider: str = "openai", model: str = None, max_tokens: int = 500):
        # Store legacy params for compatibility
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        
        # Initialize HCE pipeline
        self.hce_pipeline = HCEPipeline(
            miner_model=f"{provider}://{model}",
            judge_model=f"{provider}://{model}",
            rerank_policy="adaptive"
        )
    
    def process(self, input_data, dry_run=False, **kwargs):
        # Convert to HCE format
        episode = self._convert_to_episode(input_data)
        
        # Run HCE pipeline
        pipeline_output = self.hce_pipeline.process(episode)
        
        # Convert back to legacy format
        return self._convert_to_legacy_result(pipeline_output)
```

### Phase 1: Database Migration and Views

**Goal**: Apply HCE schema while maintaining backward compatibility through views.

**Key Deliverables**:
1. HCE package integrated into codebase
2. Data conversion layer functional
3. Basic claim extraction working end-to-end
4. Feature flag implementation (`--use_hce`)

**Architecture Decisions**:
- HCE will be placed in `src/knowledge_system/hce/` to maintain namespace consistency
- All HCE functionality will be behind a feature flag initially
- Existing processors will remain unchanged
- New `HCEPipeline` class will orchestrate the claim extraction flow

### Phase 2: Advanced Features (Weeks 4-6)

**Goal**: Implement upgrades A, B, C, D (partial), E, G, H, and I.

**Key Deliverables**:
1. NLI-based truth checking (Upgrade A)
2. HDBSCAN clustering for better deduplication (Upgrade B)
3. Calibration and uncertainty routing (Upgrade C)
4. Cross-episode global index (Upgrade D - partial)
5. Discourse tagging (Upgrade E)
6. Temporal/numeric validation (Upgrade G)
7. Quality assurance suite (Upgrade H)
8. Obsidian UX enhancements (Upgrade I)

**Technical Approach**:
- Gradual feature enablement through configuration
- Each upgrade independently testable
- Performance monitoring at each stage

## Data Flow Architecture

### Legacy Flow
```
Input File → Processor → SQLite Database → Output Files
                ↓              ↓
         Bright Data Proxy   Cost Tracking
```

### HCE Flow
```
Input File → SQLite Check → Converter → EpisodeBundle → HCE Pipeline → PipelineOutputs
                ↓                                             ↓                ↓
         Bright Data Proxy                          [Skim → Mine → Link →   SQLite Storage
         (if needed)                                 Dedupe → Rerank →          ↓
                                                    Route → Judge →        Export/Regenerate
                                                    Relations]                Files
                                                         ↓
                                              [People + Concepts + Glossary]
```

## Integration Points

### 1. CLI Integration
```python
# In commands/process.py
@click.option('--use-hce', is_flag=True, help='Use HCE pipeline instead of legacy')
def process(ctx, input_path, output, use_hce, ...):
    if use_hce:
        # Route to HCE pipeline
        from ..hce.pipeline import HCEPipeline
        pipeline = HCEPipeline(config)
        results = pipeline.process(input_path)
    else:
        # Use legacy processors
        ...
```

### 2. GUI Integration
- New "HCE Settings" section in API Keys tab
- Toggle in Process tab for HCE mode
- Progress tracking for multi-stage pipeline
- Result preview with claim visualization

### 3. Configuration Integration
```yaml
# In settings.yaml
hce:
  enabled: false
  models:
    miner: "ollama://qwen2.5:14b-instruct"
    judge: "openai://gpt-4"
    embedder: "local://bge-small-en-v1.5"
  rerank_policy:
    mode: "adaptive"
    min_keep: 25
    max_keep: 400
  database_integration: true
  use_bright_data_proxy: false  # Enable if API calls need proxy

# Existing Bright Data config
bright_data:
  customer_id: ${BD_CUST}
  zone_id: ${BD_ZONE}
  password: ${BD_PASS}
  api_key: ${BRIGHT_DATA_API_KEY}
```

## Model Strategy

### Flexible Model Assignment

Each HCE stage can use different models based on requirements:

| Stage | Default Model | Purpose | Alternative Options |
|-------|--------------|---------|-------------------|
| Miner | `ollama://qwen2.5:14b` | High-recall claim extraction | Any instruction model |
| Judge | `openai://gpt-4` | High-precision validation | `anthropic://claude-3` |
| Embedder | `local://bge-small` | Semantic similarity | `openai://text-embedding-3-small` |
| Reranker | `local://bge-reranker` | Relevance scoring | Cloud rerankers |
| NLI | `local://nli-mini` | Entailment checking | Larger NLI models |

### Model URI System

The `ModelURI` format allows flexible backend selection:
- `ollama://model-name` - Local Ollama models
- `openai://model-name` - OpenAI API
- `anthropic://model-name` - Anthropic API
- `local://model-name` - Local models (Transformers, etc.)
- `vllm://server/model` - vLLM server deployment

## Performance Considerations

### Memory Management
- Streaming processing for large transcripts
- Segment-based processing to avoid loading entire documents
- Embedding cache to avoid recomputation
- Result streaming to GUI/CLI

### Computational Efficiency
- Batch inference for embeddings
- Parallel processing of independent stages
- GPU acceleration where available
- Caching of intermediate results

### Expected Performance
- **Processing Time**: 2-5x legacy (due to multi-stage pipeline)
- **Accuracy**: Higher precision in information extraction
- **Memory Usage**: Comparable to legacy when streaming enabled
- **Output Quality**: Significantly richer structured data

## Integration with Existing Infrastructure

### SQLite Database Integration (Enhanced Design)
The HCE system will leverage and extend the existing SQLite infrastructure with a comprehensive schema:

**Core HCE Tables**:
- `episodes` - Maps to existing videos table with episode abstraction
- `claims` - Scored and tiered claims with JSON scoring data
- `evidence_spans` - Timestamped quotes linked to claims and segments
- `relations` - Typed relationships between claims (supports/contradicts/refines)
- `people`, `concepts`, `jargon` - Entity tables with evidence tracking

**Advanced Features**:
- **FTS5 Full-Text Search**: `claims_fts` and `quotes_fts` for fast semantic search
- **WAL Mode**: Concurrent read access with single writer
- **Idempotent Upserts**: Safe for reprocessing and updates
- **Foreign Key Constraints**: Data integrity across all relationships
- **Covering Indexes**: Optimized for common query patterns

**Integration Approach**:
1. Create `storage_sqlite.py` module for persistence operations
2. Call after existing `export_all()` to maintain file outputs
3. Use existing `DatabaseService` patterns for consistency
4. Track all costs in existing `bright_data_sessions` table

### Bright Data Proxy Support
HCE can optionally use Bright Data proxies for:
- API calls to OpenAI/Anthropic when needed
- Session management for sticky IPs
- Cost tracking and optimization
- Proxy health monitoring

## Risk Mitigation

### Technical Risks
1. **Model Availability**: Fallback models configured for each stage
2. **Performance Regression**: Comprehensive benchmarking suite
3. **Memory Issues**: Streaming and batch size controls
4. **API Failures**: Retry logic and offline fallbacks
5. **Database Growth**: Efficient indexing and cleanup strategies
6. **Proxy Failures**: Fallback to direct connections when safe

### User Experience Risks
1. **Complexity**: Progressive disclosure of features
2. **Migration**: Clear documentation and migration tools
3. **Performance**: User-configurable quality/speed tradeoffs
4. **Compatibility**: Full backward compatibility maintained
5. **Cost Visibility**: Clear cost tracking and reporting

## Testing Strategy

### Unit Tests
- Each HCE module independently tested
- Mock model responses for deterministic tests
- Converter validation tests
- Export format verification

### Integration Tests
- End-to-end pipeline tests
- Legacy compatibility tests
- Performance benchmarks
- Memory usage monitoring

### User Acceptance Tests
- A/B testing with willing users
- Feedback collection system
- Iterative improvements based on usage

## Rollout Plan

### Phase 1: Alpha (Internal Testing)
- Feature flag disabled by default
- Internal team testing
- Performance profiling
- Bug fixes and optimizations

### Phase 2: Beta (Opt-in Users)
- Feature flag available in settings
- Documentation published
- Community feedback gathered
- Model recommendations refined

### Phase 3: General Availability
- Feature flag enabled by default
- Legacy mode still available
- Migration tools provided
- Full documentation and tutorials

## Implementation Benefits

### SQLite Schema Advantages
The proposed SQLite integration provides:

1. **Powerful Querying**:
   - Find top-tier claims by importance scores
   - Discover contradictions within and across episodes
   - Full-text search across all claims and evidence
   - Track entity mentions across episodes

2. **Performance**:
   - WAL mode enables concurrent reads
   - FTS5 provides sub-second search
   - Covering indexes optimize common queries
   - Contentless FTS tables reduce storage

3. **Data Integrity**:
   - Foreign keys ensure referential integrity
   - Check constraints validate data types
   - Idempotent operations prevent duplicates
   - Transaction support for atomic updates

4. **Extensibility**:
   - Schema versioning for upgrades
   - JSON fields for flexible metadata
   - Views for common query patterns
   - Easy backup and replication options

## Success Metrics

### Quantitative Metrics
- Claims extracted per document
- Processing time per stage
- Memory usage patterns
- Model inference costs
- User adoption rate
- Query performance benchmarks
- Storage efficiency ratios

### Qualitative Metrics
- Claim quality assessment
- User satisfaction surveys
- Feature usage patterns
- Community feedback
- Support ticket volume
- Search relevance scores

## Future Enhancements

### Near Term (3-6 months)
- Model distillation for efficiency
- Real-time processing mode
- Collaborative claim validation
- Advanced visualization tools

### Long Term (6-12 months)
- Multi-language support
- Domain-specific models
- Active learning integration
- Knowledge graph generation
- API for third-party integration

## Conclusion

The HCE integration represents a significant enhancement to the Knowledge Chipper's analytical capabilities. By maintaining backward compatibility while introducing advanced claim extraction features, we can provide users with a smooth migration path to more sophisticated content analysis tools. The phased implementation approach ensures stability while allowing for iterative improvements based on user feedback.

The flexible model architecture and comprehensive pipeline design position the system for future enhancements while meeting immediate user needs for better information extraction and knowledge management.

## Acknowledgments

Special thanks to the community member who provided the detailed SQLite schema design with FTS5 integration, idempotent operations, and performance optimizations. This contribution significantly enhanced the robustness and scalability of the HCE integration plan.
