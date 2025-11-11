# Transcript Display Fix - November 2025

## Summary

Fixed two display issues with transcript markdown files when viewed in Obsidian and similar markdown viewers:

1. **Removed Duplicate Title**: Eliminated redundant H1 heading that appeared below YAML frontmatter
2. **Natural Filenames**: Changed filenames to preserve spaces instead of converting to underscores

## Issues Fixed

### 1. Duplicate Title Display

**Problem**: Transcript markdown files had both:
- A `title:` field in YAML frontmatter (shown in properties panel)
- An H1 heading `# Title` in the document body (shown as main heading)

This created duplicate titles in Obsidian's UI:
- Properties panel showed: `title: "Will Japan and South Korea Gang Up on China?"`
- Document heading showed: `# Will Japan and South Korea Gang Up on China?`

**Root Cause**: The markdown generation code added an H1 heading after the YAML frontmatter, not realizing that Obsidian and similar markdown viewers automatically display the YAML `title` field as the document heading.

**Solution**: Removed the H1 heading generation from markdown files. Modern markdown viewers like Obsidian automatically use the YAML `title` field as the document heading, so adding a separate H1 was redundant.

### 2. Underscores in Filenames

**Problem**: Transcript filenames converted spaces to underscores:
- Example: `Will_Japan_and_South_Korea_Gang_Up_on_China__Peter_Zeihan_transcript.md`

This made filenames harder to read in file browsers and Obsidian's file tree.

**Root Cause**: The filename sanitization code explicitly converted spaces to underscores with `safe_name.replace(" ", "_")`, likely following an old convention for filesystem compatibility.

**Solution**: Removed the space-to-underscore conversion. Modern filesystems (macOS, Linux, Windows) handle spaces in filenames perfectly well, and preserving spaces provides much better readability:
- New example: `Will Japan and South Korea Gang Up on China Peter Zeihan_transcript.md`

## Files Changed

### 1. `src/knowledge_system/processors/audio_processor.py`

**Change 1**: Removed H1 heading generation (lines 1260-1264)
```python
# Before:
lines = frontmatter + [""]
heading_title = (display_title or "Transcript").strip()
lines.append(f"# {heading_title}")
lines.append("")

# After:
lines = frontmatter + [""]
# Note: We don't add an H1 heading here because Obsidian and similar markdown viewers
# automatically display the YAML title field as the document heading.
# Adding a redundant H1 would create duplicate titles in the UI.
```

**Change 2**: Removed space-to-underscore conversion in filenames (lines 1460-1478)
```python
# Before:
safe_name = "".join(
    c for c in clean_title if c.isalnum() or c in (" ", "-", "_")
).rstrip()
safe_name = safe_name.replace(" ", "_")  # ❌ Removed this line

# After:
safe_name = "".join(
    c for c in clean_title if c.isalnum() or c in (" ", "-", "_")
).rstrip()
# Keep spaces in filename for natural display in Obsidian and file browsers
```

### 2. `src/knowledge_system/services/file_generation.py`

**Change**: Removed H1 heading from database-generated transcripts (line 267)
```python
# Before:
markdown_content = f"""---
{yaml_frontmatter}---
{hashtags_section}
# {video.title}

**Video URL:** ...

# After:
markdown_content = f"""---
{yaml_frontmatter}---
{hashtags_section}
**Video URL:** ...
```

### 3. `tests/test_audio_processor.py`

**Added Tests**:
1. `test_markdown_no_duplicate_h1_heading()`: Verifies no H1 heading appears after YAML frontmatter
2. `test_filename_preserves_spaces()`: Verifies filenames contain spaces instead of underscores

## Testing

Both new tests pass successfully:
```bash
pytest tests/test_audio_processor.py::test_markdown_no_duplicate_h1_heading -v  # ✅ PASSED
pytest tests/test_audio_processor.py::test_filename_preserves_spaces -v          # ✅ PASSED
```

## Impact

### User Experience
- **Cleaner UI**: No more duplicate titles in Obsidian properties panel and document heading
- **Better Readability**: Filenames with spaces are easier to read in file browsers and Obsidian's file tree
- **YouTube-like Display**: Titles now look exactly as they appear on YouTube, without underscores

### Backward Compatibility
- **Existing Files**: Old transcript files with underscores will continue to work fine
- **New Files**: All newly generated transcripts will use the improved format
- **No Breaking Changes**: The YAML frontmatter structure remains unchanged

## Example

### Before
**Filename**: `Will_Japan_and_South_Korea_Gang_Up_on_China__Peter_Zeihan_transcript.md`

**Content**:
```markdown
---
title: "Will Japan and South Korea Gang Up on China? ｜｜ Peter Zeihan"
source: "https://www.youtube.com/watch?v=Aye8dYGyyI0"
---

# Will Japan and South Korea Gang Up on China? ｜｜ Peter Zeihan

**Video URL:** [https://www.youtube.com/watch?v=Aye8dYGyyI0]
...
```

**Result in Obsidian**: 
- Properties panel: `title: "Will Japan and South Korea Gang Up on China?"`
- Document heading: `# Will Japan and South Korea Gang Up on China?` ❌ Duplicate!

### After
**Filename**: `Will Japan and South Korea Gang Up on China Peter Zeihan_transcript.md`

**Content**:
```markdown
---
title: "Will Japan and South Korea Gang Up on China? ｜｜ Peter Zeihan"
source: "https://www.youtube.com/watch?v=Aye8dYGyyI0"
---

**Video URL:** [https://www.youtube.com/watch?v=Aye8dYGyyI0]
...
```

**Result in Obsidian**: 
- Properties panel: `title: "Will Japan and South Korea Gang Up on China?"` ✅ Single title!
- Filename in file tree: `Will Japan and South Korea Gang Up on China Peter Zeihan_transcript.md` ✅ Readable!

## Related Documentation

- See `CHANGELOG.md` for version history
- See `docs/TRANSCRIPT_OUTPUT_FIXES_2025.md` for previous transcript improvements
