# Format Dropdown Implementation Status

## Summary

The transcription tab format dropdown currently has **partial implementation**. Only "md" and "none" formats are fully functional.

## Format Options Status

| Format | Status | Behavior | Notes |
|--------|--------|----------|-------|
| **md** | ✅ Fully Implemented | Creates markdown file with YAML frontmatter, timestamps, and metadata | Default format, fully functional |
| **none** | ✅ Fully Implemented | Saves to database only, no files created | Added October 31, 2025 |
| **txt** | ❌ Not Implemented | Currently creates .md file (ignores format setting) | Needs implementation |
| **srt** | ❌ Not Implemented | Currently creates .md file (ignores format setting) | Needs implementation |
| **vtt** | ❌ Not Implemented | Currently creates .md file (ignores format setting) | Needs implementation |

## Current Code Flow

```python
# audio_processor.py line 2003
saved_file = self.save_transcript_to_markdown(
    temp_result,
    path,
    output_dir,
    include_timestamps=include_timestamps,
    video_metadata=video_metadata,
)
```

The `save_transcript_to_markdown()` method **always** creates markdown files with `.md` extension, regardless of the format parameter passed in kwargs.

## What Needs to Be Done

To fully implement all format options, we need to:

### 1. Add Format Parameter to save_transcript Method

Modify the signature to accept and use format:

```python
def save_transcript(
    self,
    transcription_result: ProcessorResult,
    audio_path: Path,
    output_dir: str | Path | None = None,
    include_timestamps: bool = True,
    video_metadata: dict | None = None,
    output_format: str = "md",  # ADD THIS
) -> Path | None:
```

### 2. Implement Format-Specific Savers

Create methods for each format:

```python
def _save_as_txt(self, data, path) -> Path:
    """Plain text without timestamps or formatting"""
    
def _save_as_srt(self, data, path) -> Path:
    """SubRip subtitle format with timing"""
    
def _save_as_vtt(self, data, path) -> Path:
    """WebVTT subtitle format with timing"""
```

### 3. Add Format Routing Logic

```python
def save_transcript(self, ...):
    if output_format == "md":
        return self._save_as_markdown(...)
    elif output_format == "txt":
        return self._save_as_txt(...)
    elif output_format == "srt":
        return self._save_as_srt(...)
    elif output_format == "vtt":
        return self._save_as_vtt(...)
    elif output_format == "none":
        return None  # No file output
```

### 4. Update File Extensions

Ensure correct extensions are used:
- `.md` for markdown
- `.txt` for plain text
- `.srt` for SubRip
- `.vtt` for WebVTT
- None for "none"

## Example Format Outputs

### Markdown (.md) - IMPLEMENTED
```markdown
---
title: Example Video
video_id: abc123
tags: [ai, technology]
---

# Example Video

**00:10**: This is the transcript text
**00:25**: More transcript text
```

### Plain Text (.txt) - TODO
```
This is the transcript text
More transcript text
```

### SRT (.srt) - TODO
```
1
00:00:10,000 --> 00:00:15,000
This is the transcript text

2
00:00:25,000 --> 00:00:30,000
More transcript text
```

### WebVTT (.vtt) - TODO
```
WEBVTT

00:00:10.000 --> 00:00:15.000
This is the transcript text

00:00:25.000 --> 00:00:30.000
More transcript text
```

## Priority Database Architecture Fix (October 31, 2025)

✅ **COMPLETED**: Moved database writes BEFORE file writes

The code now prioritizes database writes over file writes:

1. ✅ **Database writes happen FIRST** (lines 1810-1912)
2. ✅ **File writes happen SECOND** (lines 1914-2027)
3. ✅ **Success depends on database write**, not file write

This ensures:
- Critical data is persisted to database even if file writing fails
- Database is the source of truth (claim-centric architecture)
- Files are optional artifacts
- format="none" works correctly (database write completes, file write skipped)

## Recommendation

**Option 1: Remove Non-Functional Formats (Quick Fix)**
- Remove "txt", "srt", "vtt" from dropdown
- Keep only "md" and "none" which are fully functional
- Update tooltip to reflect available options

**Option 2: Implement Missing Formats (Complete Solution)**
- Follow implementation plan above
- Add format-specific savers for txt, srt, vtt
- Test each format thoroughly
- Update documentation

## Related Files

- `src/knowledge_system/gui/tabs/transcription_tab.py` - Format dropdown definition
- `src/knowledge_system/processors/audio_processor.py` - Transcript saving logic
- `docs/FORMAT_NONE_OPTION.md` - Documentation for "none" format

## Testing Notes

When testing format implementations:
1. Verify correct file extension is used
2. Verify content format matches specification
3. Verify timestamps are formatted correctly
4. Verify database writes still happen
5. Verify error handling for each format
6. Test with diarization enabled/disabled
7. Test with video metadata present/absent
