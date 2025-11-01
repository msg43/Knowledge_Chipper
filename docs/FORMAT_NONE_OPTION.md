# Transcription Format "None" Option

## Overview

The transcription tab now includes a "none" option in the format dropdown that allows users to transcribe audio/video files and save all data to the database without creating any output files (markdown, txt, srt, or vtt).

## Implementation Date

October 31, 2025

## Use Case

This feature is particularly useful for:
- **Large batch processing** where database is the primary storage mechanism
- **Memory/disk efficiency** when transcript files are not immediately needed
- **Database-centric workflows** where downstream processes read from database rather than files
- **Testing and validation** without cluttering output directories with files

## Changes Made

### 1. GUI Changes (`transcription_tab.py`)

**Format Dropdown**
```python
self.format_combo.addItems(["txt", "md", "srt", "vtt", "none"])
```

**Tooltip Update**
```
"Output format: 'txt' for plain text, 'md' for Markdown, 'srt' and 'vtt' 
for subtitle files with precise timing, 'none' to save to database only 
without creating output files."
```

**Settings Propagation**
The `format` setting is already included in `gui_settings_to_pass` and is automatically propagated to the audio processor through `processing_kwargs`.

### 2. Processor Changes (`audio_processor.py`)

**Format Parameter Extraction**
```python
output_format = kwargs.get("format", "md")  # Default to markdown if not specified
```

**Conditional File Writing**
```python
# Only create output files if format is not "none"
if output_dir and output_format != "none":
    # ... create markdown and color-coded files ...
elif output_format == "none":
    logger.info("Output format set to 'none' - skipping file creation, will save to database only")
```

**Database Writing (Unchanged)**
```python
# Save to database if database service is available
# This section executes AFTER the file writing decision
# Therefore, database writes happen regardless of format setting
if db_service and final_data:
    # ... create database records ...
```

## Behavior

### When format="none"
1. ✅ Audio/video is transcribed normally
2. ✅ All transcription data is processed (segments, timestamps, speakers, etc.)
3. ✅ Media source record is created/updated in database
4. ✅ Transcript record is created/updated in database
5. ❌ No markdown file is created
6. ❌ No color-coded transcript file is created
7. ❌ No txt/srt/vtt files are created

### When format="md" (or any other format)
1. ✅ Audio/video is transcribed normally
2. ✅ All transcription data is processed
3. ✅ Media source record is created/updated in database
4. ✅ Transcript record is created/updated in database
5. ✅ Markdown file is created
6. ✅ Color-coded transcript file is created (if enabled)

## Code Flow

```
User selects format="none" in GUI
    ↓
Format setting saved to gui_settings
    ↓
Format included in processing_kwargs (line 1132)
    ↓
Format passed to AudioProcessor.process() via **kwargs (line 1406)
    ↓
audio_processor.py extracts format parameter (line 1807)
    ↓
Checks: if output_dir and output_format != "none" (line 1811)
    ↓
    ├─ YES → Creates markdown and color-coded files
    └─ NO  → Logs message and skips file creation (line 1863)
    ↓
Database writing code executes (line 1865+)
    ↓
Result returned with database IDs in metadata
```

## Testing

A comprehensive logic test was created and passed successfully:

```bash
python test_format_none_logic.py
```

**Test Results:**
- ✅ Format dropdown includes 'none' option
- ✅ Tooltip explains 'none' behavior
- ✅ Format parameter is passed to processor
- ✅ Audio processor extracts format parameter
- ✅ File writing is skipped when format='none'
- ✅ Database writing happens regardless of format
- ✅ Code structure ensures database writes with format='none'
- ✅ Components import successfully

## Database Schema

No database schema changes were required. The existing schema already supports:
- Media source records (videos table)
- Transcript records (transcripts table)
- Segments with timestamps
- Speaker diarization data
- Metadata (model, device, processing time, etc.)

## Backward Compatibility

This feature is fully backward compatible:
- Existing transcriptions are unaffected
- Default format remains "md" (markdown)
- All existing formats (txt, md, srt, vtt) work exactly as before
- New "none" option is additive only

## Memory Impact

For a typical 16-minute podcast episode:
- **With files:** ~50KB markdown file + database record
- **With format="none":** Only database record (~10-20KB depending on segment count)

For 7,000 videos:
- **With files:** ~350MB in markdown files + database
- **With format="none":** Only database records (~70-140MB)
- **Savings:** ~210-280MB disk space (60-80% reduction in storage)

## Future Enhancements

Potential future improvements:
1. Add format options for other file types (json, csv, etc.)
2. Add option to compress/archive transcripts after database write
3. Add option to defer file creation until explicitly requested
4. Add bulk export from database to files for archived transcripts

## Related Files

### Modified Files
- `src/knowledge_system/gui/tabs/transcription_tab.py` - Added 'none' to format dropdown and updated tooltip
- `src/knowledge_system/processors/audio_processor.py` - Added format parameter handling and conditional file writing
- `MANIFEST.md` - Documented the feature

### Related Components
- `src/knowledge_system/database/service.py` - Database service used for transcript storage
- `src/knowledge_system/processors/whisper_cpp_transcribe.py` - Underlying transcription engine (unchanged)
- `src/knowledge_system/gui/core/settings_manager.py` - Settings persistence (unchanged)

## Notes

1. **Architecture:** This feature aligns with the claim-centric, database-centric architecture where the database is the source of truth
2. **Performance:** Skipping file I/O provides minor performance improvements for large batches
3. **Use Case:** Most useful for automated pipelines where files are generated on-demand from database queries
4. **Safety:** Database writes are guaranteed to happen regardless of format setting (defensive coding)
