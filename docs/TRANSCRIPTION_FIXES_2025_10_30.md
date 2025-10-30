# Transcription Metadata Fixes - October 30, 2025

## Issues Fixed

### 1. Missing Thumbnail in Markdown Transcripts ✅

**Problem**: Transcripts generated from YouTube URLs were not including thumbnail images in the markdown output.

**Root Cause**: The `_create_markdown()` method in `audio_processor.py` was not checking for or embedding thumbnail paths.

**Fix**: 
- Added thumbnail embedding logic after YAML frontmatter (lines 1072-1082 in `audio_processor.py`)
- Checks for `thumbnail_local_path` in `video_metadata`
- Embeds thumbnail using markdown image syntax: `![Thumbnail](path)`

**Files Modified**:
- `src/knowledge_system/processors/audio_processor.py`

---

### 2. Missing YouTube Categories in YAML Frontmatter ✅

**Problem**: YouTube platform categories (e.g., "News & Politics", "Education") were not being included in the markdown YAML frontmatter.

**Root Cause**: 
1. Categories were stored in normalized database tables (`platform_categories`, `source_platform_categories`) but not retrieved when fetching video metadata
2. The markdown generator wasn't checking for or adding categories to YAML

**Fix**:
- **Database Layer** (`database/service.py`):
  - Added `_get_platform_categories_for_source()` method to retrieve categories from normalized tables
  - Modified `get_video()` to dynamically attach categories as `categories_json` property
  
- **GUI Layer** (`gui/tabs/transcription_tab.py`):
  - Added `categories` field to video metadata dictionary passed to audio processor (line 1268-1270)
  
- **Markdown Generation** (`processors/audio_processor.py`):
  - Added YouTube categories to YAML frontmatter (lines 1010-1018)
  - Handles both list and string category formats
  - Uses `youtube_categories` field name for clarity

**Files Modified**:
- `src/knowledge_system/database/service.py`
- `src/knowledge_system/gui/tabs/transcription_tab.py`
- `src/knowledge_system/processors/audio_processor.py`

---

### 3. Speaker Attribution System Not Running ✅

**Problem**: The multi-layered speaker attribution system was not identifying known hosts, resulting in misspelled or generic speaker names (e.g., "SPEAKER_00" instead of "Jeff Snider").

**Root Cause**: 
1. Video metadata passed to speaker processor was missing critical channel information (`uploader`, `uploader_id`)
2. The metadata was being pulled from `kwargs.get("metadata")` instead of `kwargs.get("video_metadata")` which had the complete information

**Fix**:
- **GUI Layer** (`gui/tabs/transcription_tab.py`):
  - Added `uploader_id` to video metadata dictionary (line 1261)
  - Added `thumbnail_local_path` to video metadata dictionary (line 1273)
  
- **Audio Processor** (`processors/audio_processor.py`):
  - Changed speaker processor to use `video_metadata` first, falling back to `metadata` (line 1724)
  - This ensures channel information reaches the speaker attribution system

**How Speaker Attribution Works**:
1. **Channel Mapping** (`config/speaker_attribution.yaml`): Contains 262+ podcast channels with known hosts
2. **Matching Logic** (`processors/speaker_processor.py`): Uses case-insensitive partial matching for channel names
3. **LLM Integration**: Known hosts are passed as context to LLM for intelligent speaker-to-name matching
4. **Fallback**: If no match found, uses content-based detection or keeps generic labels

**Files Modified**:
- `src/knowledge_system/gui/tabs/transcription_tab.py`
- `src/knowledge_system/processors/audio_processor.py`

---

## Testing Recommendations

To verify these fixes work end-to-end:

1. **Download a YouTube video** with known metadata:
   ```bash
   # Example: Eurodollar University (has known hosts: Jeff Snider, Emil Kalinowski)
   python -m knowledge_system.cli download "https://www.youtube.com/watch?v=EXAMPLE"
   ```

2. **Transcribe the video** with diarization enabled:
   ```bash
   python -m knowledge_system.cli transcribe path/to/audio.m4a --diarization
   ```

3. **Check the output markdown** for:
   - ✅ Thumbnail image embedded after YAML frontmatter
   - ✅ `youtube_categories: ["Category1", "Category2"]` in YAML
   - ✅ Real speaker names (e.g., "Jeff Snider") instead of "SPEAKER_00"

4. **Verify speaker attribution** in logs:
   ```
   📺 Found channel mapping for: Eurodollar University
   📺 Channel 'Eurodollar University' is hosted by: Jeff Snider, Emil Kalinowski
   ✅ Applied automatic speaker assignments: {'SPEAKER_00': 'Jeff Snider', 'SPEAKER_01': 'Emil Kalinowski'}
   ```

---

## Architecture Notes

### Metadata Flow

```
YouTube Download
    ↓
Database (MediaSource + platform_categories tables)
    ↓
GUI Transcription Tab (retrieves video metadata)
    ↓
Audio Processor (receives video_metadata kwarg)
    ↓
├─→ Speaker Processor (uses uploader for channel matching)
└─→ Markdown Generator (embeds thumbnail, categories, speaker names)
```

### Key Design Decisions

1. **Categories Storage**: Categories are normalized in separate tables (`platform_categories`, `source_platform_categories`) to avoid duplication and enable efficient querying across sources.

2. **Dynamic Property**: `categories_json` is added as a dynamic property on `MediaSource` objects rather than a database column, since it's derived from the normalized tables.

3. **Thumbnail Paths**: Thumbnails are stored with absolute paths in the database but can be converted to relative paths in markdown for portability.

4. **Speaker Attribution Priority**:
   - Priority 1: Channel-based mapping (fastest, most accurate for known podcasts)
   - Priority 2: LLM-based analysis (for unknown channels or guests)
   - Priority 3: Content-based detection (keyword matching)
   - Priority 4: Fallback to generic labels

---

## Related Files

- **Speaker Attribution Config**: `config/speaker_attribution.yaml` (262 podcast channels)
- **Database Schema**: `src/knowledge_system/database/models.py`
- **Channel Mappings Documentation**: `docs/CHANNEL_SPEAKER_MAPPINGS.md`
- **Speaker System Documentation**: `docs/SPEAKER_IDENTIFICATION_SYSTEM.md`

---

## Future Improvements

1. **Thumbnail Relative Paths**: Convert absolute thumbnail paths to relative paths based on output directory structure
2. **Category Enrichment**: Add WikiData category mapping for platform categories
3. **Speaker Learning**: Implement feedback loop to learn from user corrections
4. **Multi-language Support**: Extend speaker attribution to non-English podcasts
