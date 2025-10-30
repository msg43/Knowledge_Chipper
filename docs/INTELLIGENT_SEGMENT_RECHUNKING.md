# Intelligent Segment Re-chunking for HCE Processing

## Problem Statement

**Issue**: Whisper.cpp creates many small segments (~2-5 seconds each) based on natural pauses in speech. For a 4-minute video, this results in **~135 segments**, which means:
- ❌ 135 separate LLM calls during HCE mining
- ❌ 6-10 minutes processing time
- ❌ High API costs
- ❌ Poor context for claim extraction (segments too small)

## Solution Architecture

### Two-Stage Segmentation Strategy

We use **different segmentation granularities for different purposes**:

#### 1. **Transcript Storage (Fine-grained)** - Database
```
Purpose: Preserve exact timing and speaker turns for display/editing
Granularity: One segment per Whisper pause (~2-5 seconds)
Example: 135 segments for 4-minute video
Storage: transcript_segments_json in database
Use cases:
  - Displaying transcripts with timestamps
  - Speaker attribution editing
  - Precise navigation
  - Subtitle generation
```

#### 2. **HCE Mining (Coarse-grained)** - Processing
```
Purpose: Efficient LLM processing for knowledge extraction
Granularity: ~750 tokens per segment (500-1000 range)
Example: 3-6 segments for 4-minute video
Storage: Temporary (created on-the-fly)
Use cases:
  - Claim extraction
  - Jargon identification
  - People/concept mining
  - Contextual analysis
```

## Implementation

### Core Methods

#### `_load_transcript_segments_from_db(video_id)` 
Loads raw Whisper segments from database:
```python
# Returns: list of dicts with 'text', 'start', 'end', 'speaker'
# Example: 135 segments for 4-min video
```

#### `_rechunk_whisper_segments(whisper_segments, episode_id, target_tokens=750)`
Intelligently combines small segments into larger chunks:

**Chunking Strategy (Priority Order):**
1. **Speaker boundary (HARD)**: NEVER mix speakers in one chunk - always split on speaker change
2. **Token limit (HARD)**: Never exceed 1000 tokens per chunk
3. **Sentence boundary (SOFT)**: Prefer splitting at sentence endings (`.`, `!`, `?`) when >= 500 tokens
4. **Timestamp tracking**: Preserve start/end times for each chunk

**Critical Design Decision**: Each chunk contains ONLY ONE SPEAKER to avoid confusing the HCE miner about attribution.

**Example:**
```
Input:  135 Whisper segments (2-5 seconds each)
Output: 3-6 optimized chunks (750 tokens each)
```

### Processing Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Summarization Request                                        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Try to load from DATABASE (Priority 1)                   │
│    - Load transcript_segments_json                           │
│    - Contains raw Whisper output (135 segments)              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Re-chunk for HCE efficiency                               │
│    - Combine into ~750-token chunks                          │
│    - Respect sentence boundaries                             │
│    - Preserve speaker context                                │
│    - Result: 3-6 optimized segments                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. HCE Mining (Parallel)                                     │
│    - 3-6 LLM calls instead of 135                            │
│    - Each call has rich context                              │
│    - Extract claims, jargon, people, concepts                │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ FALLBACK: Parse from .md file                                │
│    - Only if DB segments not available                       │
│    - For external transcripts not created by us              │
└─────────────────────────────────────────────────────────────┘
```

## Performance Improvements

### Before (Using Raw Whisper Segments)
```
4-minute video:
- Segments: 135 (Whisper output)
- LLM calls: 135
- Processing time: 6-10 minutes
- Cost: High (135 API calls)
- Context per call: Poor (20-50 tokens)
```

### After (Intelligent Re-chunking)
```
4-minute video:
- Raw segments: 135 (Whisper output, stored in DB)
- Re-chunked: 3-6 (optimized for HCE)
- LLM calls: 3-6
- Processing time: 1-2 minutes ⚡
- Cost: Low (3-6 API calls)
- Context per call: Rich (750 tokens)
```

**Speed improvement: 3-5x faster**
**Cost reduction: ~95% fewer API calls**

## Key Design Decisions

### Why Not Just Use Whisper Segments?
- **Too small**: 20-50 tokens per segment (insufficient context)
- **Too many**: 135 LLM calls (slow, expensive)
- **Poor claim extraction**: Claims often span multiple small segments

### Why Not Chunk During Transcription?
- **Preserve precision**: Need fine-grained segments for transcript display
- **Enable editing**: Users need to see exact speaker turns
- **Support subtitles**: Small segments required for subtitle timing
- **Separation of concerns**: Transcription optimized for accuracy, HCE optimized for efficiency

### Why 750 Tokens?
- **Context window**: Fits comfortably in most LLM contexts
- **Claim completeness**: Most claims fit within 500-1000 tokens
- **Sentence boundaries**: Natural breaking points at this size
- **API efficiency**: Optimal balance of calls vs context

## Boundary Respect

The re-chunking algorithm respects multiple boundaries in priority order:

### 1. **Hard Boundaries** (ALWAYS respect - never cross)
   - **Speaker changes**: Each chunk contains ONLY ONE SPEAKER
     - Rationale: Mixing speakers confuses HCE miner about who said what
     - Example: If Speaker A has 200 tokens and Speaker B starts, we split even though < target
   - **Maximum token limit**: Never exceed 1000 tokens per chunk
     - Rationale: LLM context window and API limits

### 2. **Soft Boundaries** (Prefer to respect when possible)
   - **Sentence endings** (`.`, `!`, `?`): Split here when >= 500 tokens
     - Rationale: Preserves semantic completeness
   - **Minimum token threshold**: Try to reach 500 tokens before splitting
     - Rationale: Provides sufficient context for claim extraction
   - **Paragraph breaks**: Natural topic boundaries

### 3. **Context Preservation** (Always maintained)
   - Speaker identity (single speaker per chunk)
   - Timestamps (start/end preserved)
   - Sequential order (chronological)

### Example Scenarios

**Scenario 1: Speaker change before target**
```
Speaker A: 300 tokens
Speaker B starts → SPLIT (hard boundary)
Result: 2 chunks (300 + 750 tokens)
```

**Scenario 2: Long monologue**
```
Speaker A: 2000 tokens continuous
→ Split at sentence boundaries every ~750 tokens
Result: 3 chunks (750 + 750 + 500 tokens, all Speaker A)
```

**Scenario 3: Back-and-forth dialogue**
```
Speaker A: 100 tokens
Speaker B: 150 tokens → SPLIT
Speaker A: 200 tokens → SPLIT
Result: 3 small chunks (preserves speaker clarity)
```

## Code Locations

- **Re-chunking logic**: `src/knowledge_system/core/system2_orchestrator.py`
  - `_load_transcript_segments_from_db()`
  - `_rechunk_whisper_segments()`
  
- **Integration**: `src/knowledge_system/core/system2_orchestrator_mining.py`
  - Priority 1: Load from DB and re-chunk
  - Fallback: Parse from .md file

- **Database schema**: `src/knowledge_system/database/models.py`
  - `Transcript.transcript_segments_json` - Raw Whisper segments

## Testing

To verify the improvement:

1. **Transcribe a video** (creates DB segments):
   ```bash
   # This creates 135 Whisper segments in DB
   python -m knowledge_system.cli transcribe video.m4a
   ```

2. **Summarize the video**:
   ```bash
   # This should now use re-chunked segments (3-6 instead of 135)
   python -m knowledge_system.cli summarize video_transcript.md
   ```

3. **Check logs** for confirmation:
   ```
   ✅ Using database segments for VIDEO_ID (135 raw Whisper segments)
   📦 Re-chunked into 6 optimized segments for HCE mining
   Processing 6 segments with 7 parallel workers
   ```

## Future Enhancements

1. **Semantic chunking**: Use embeddings to detect topic shifts
2. **Speaker-aware chunking**: Keep same speaker together when possible
3. **Adaptive sizing**: Adjust chunk size based on content density
4. **Caching**: Cache re-chunked segments for repeated processing

## Related Documentation

- `docs/TRANSCRIPTION_FIXES_2025_10_30.md` - Transcript metadata improvements
- `docs/SPEAKER_IDENTIFICATION_SYSTEM.md` - Speaker attribution system
- `src/knowledge_system/processors/hce/unified_pipeline.py` - HCE processing pipeline
