# File Organization Guide

## Overview

The Knowledge Chipper system generates multiple types of output files during processing. This guide explains where files are saved and how to find them.

## Output Directory Structure

When you specify an output directory (e.g., `/Users/matthewgreer/Projects/SAMPLE OUTPUTS/5`), the system creates the following structure:

```
output_directory/
├── transcripts/          # Transcript markdown files (from database regeneration)
├── summaries/            # Summary markdown files with claims analysis
├── moc/                  # Maps of Content (People, Concepts, etc.)
├── exports/              # Export files (SRT, VTT, TXT, JSON)
├── Thumbnails/           # Video thumbnails
├── downloads/            # Downloaded media files
│   ├── youtube/          # YouTube audio/video files
│   └── Thumbnails/       # Downloaded thumbnails
├── *.md                  # Transcript files (from AudioProcessor during transcription)
├── *_transcript.md       # Legacy transcript naming
├── *_color_coded.html    # Color-coded HTML transcripts with speaker highlighting
└── *_enhanced.md         # Enhanced markdown transcripts
```

## File Types and Locations

### 1. Transcription Files

**During Transcription (AudioProcessor):**
- **Location:** Root of output directory
- **Naming:** `{sanitized_title}.md` or `{sanitized_title}_transcript.md`
- **Example:** `Demographics Part 5 The Chinese Collapse.md`
- **When Created:** Immediately after transcription completes
- **Contains:** Full transcript with timestamps and speaker labels (if diarization enabled)

**From Database (FileGenerationService):**
- **Location:** `transcripts/` subdirectory
- **Naming:** `{title}_{source_id}.md`
- **Example:** `Demographics Part 5_ The Chinese Collapse_0MSV2bh48MA.md`
- **When Created:** When regenerating files from database
- **Contains:** Same content as above, but generated from database records

### 2. Summary Files

- **Location:** `summaries/` subdirectory
- **Naming:** `Summary_{title}_{source_id}.md`
- **Example:** `Summary_Demographics Part 5_ The Chinese Collapse_0MSV2bh48MA.md`
- **When Created:** After summarization/mining process completes
- **Contains:** 
  - HCE claim analysis (Tier A/B/C claims)
  - Extracted people, concepts, and relations
  - Executive summary
  - Evidence mappings

### 3. Color-Coded Transcripts

- **Location:** Root of output directory
- **Naming:** `{title}_{source_id}_transcript_color_coded.html`
- **Example:** `Why_Trumps_Stance_on_Canada_Makes_Sense__Peter_Zeihan_kxKk7sBpcYA_transcript_color_coded.html`
- **When Created:** When speaker attribution is applied
- **Contains:** HTML version with color-coded speakers for easy reading

### 4. Enhanced Transcripts

- **Location:** Root of output directory
- **Naming:** `{title}_{source_id}_transcript_enhanced.md`
- **Example:** `Why_Trumps_Stance_on_Canada_Makes_Sense__Peter_Zeihan_kxKk7sBpcYA_transcript_enhanced.md`
- **When Created:** When speaker attribution is applied
- **Contains:** Markdown with enhanced speaker labels

## File Naming Conventions

### Source ID
Every YouTube video has an 11-character source ID (e.g., `0MSV2bh48MA`). This ID is used to:
- Link files to database records
- Prevent naming collisions
- Enable file regeneration

### Sanitized Titles
File names use sanitized versions of video titles:
- Spaces are preserved for readability
- Special characters are removed
- Maximum length limits may apply

## File Relationships

All files for a single video share the same `source_id`. This allows you to:

1. **Find all files for a video:**
   ```bash
   ls -la *0MSV2bh48MA*
   ```

2. **Regenerate files from database:**
   ```python
   from knowledge_system.services.file_generation import regenerate_video_files
   regenerate_video_files("0MSV2bh48MA", output_dir="/path/to/output")
   ```

3. **Match transcripts to summaries:**
   - Transcript: `{title}_{source_id}.md`
   - Summary: `Summary_{title}_{source_id}.md`
   - Both share the same `source_id`

## Database Storage

**Important:** All transcription and summarization data is stored in the SQLite database:
- **Location:** `~/Library/Application Support/Knowledge Chipper/knowledge_system.db` (macOS)
- **Tables:** `media_sources`, `transcripts`, `summaries`, `claims`, `people`, `concepts`

**Markdown files are generated FROM the database** and can be regenerated at any time without re-processing the video.

## File Persistence

### What's Stored in Database (Permanent)
- ✅ Transcription text and segments
- ✅ Speaker labels and timestamps
- ✅ Claims, people, concepts, relations
- ✅ Summary text and metadata
- ✅ Processing costs and token counts

### What's Stored in Files (Regenerable)
- 📄 Markdown transcripts
- 📄 Markdown summaries
- 📄 Color-coded HTML
- 📄 Export files (SRT, VTT, TXT)

**Key Principle:** Files are views of database data. If you delete a file, you can regenerate it from the database. If you re-run processing for the same video, the database record is updated and files can be regenerated.

## Avoiding File Conflicts

The system is designed to prevent file conflicts:

1. **Different directories:** Transcripts and summaries go to different subdirectories
2. **Different prefixes:** Summary files start with "Summary_"
3. **Source ID inclusion:** Files include the source_id to prevent title collisions
4. **Overwrite behavior:** Re-running processing for the same video overwrites the previous database entry and regenerates files

## Finding Your Files

### After Transcription
Look in the **root of your output directory** for:
- `{title}.md` - Main transcript file

### After Summarization
Look in the **summaries/** subdirectory for:
- `Summary_{title}_{source_id}.md` - Summary with claims analysis

### After Speaker Attribution
Look in the **root of your output directory** for:
- `{title}_{source_id}_transcript_color_coded.html` - Color-coded HTML
- `{title}_{source_id}_transcript_enhanced.md` - Enhanced markdown

## Common Issues

### "I don't see my summary file"
- ✅ Check the `summaries/` subdirectory, not the root
- ✅ Look for files starting with "Summary_"
- ✅ Search by source_id: `ls -la summaries/*{source_id}*`

### "My transcript and summary have different names"
- ✅ This is expected - they use different naming conventions
- ✅ Both include the source_id for linking
- ✅ Transcript: `{title}.md` (root) or `{title}_{source_id}.md` (transcripts/)
- ✅ Summary: `Summary_{title}_{source_id}.md` (summaries/)

### "Files are overwriting each other"
- ✅ If you see this, it's likely a bug - files should go to different locations
- ✅ Transcripts → root or transcripts/
- ✅ Summaries → summaries/
- ✅ They should never overwrite each other

## Recommendations

1. **Use consistent output directories** for related videos
2. **Don't manually edit generated files** - edit the database and regenerate
3. **Keep the database backed up** - it's the source of truth
4. **Use source_id to link files** when organizing or searching

## Future Improvements

Planned improvements to file organization:
- [ ] Move all transcripts to `transcripts/` subdirectory (currently split between root and transcripts/)
- [ ] Unified naming convention across all file types
- [ ] Automatic file consolidation and cleanup
- [ ] Better handling of duplicate titles with different source_ids
