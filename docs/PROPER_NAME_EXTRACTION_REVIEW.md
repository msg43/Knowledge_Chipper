# Proper Name Extraction for Whisper - Code Review

## Overview

The proper name extraction code (lines 1001-1067 in `whisper_cpp_transcribe.py`) is **very well designed** and solves the root cause of name transcription errors like "Zeihan" → "Zine".

## Current Implementation ✅

### Strategy
1. Extract proper names from video metadata (title, uploader)
2. Place names FIRST in Whisper's initial_prompt (highest priority)
3. Add uploader and topic context
4. Filter common words and limit length

### Pattern Matching
```python
# Pattern 1: Names before separators
"Peter Zeihan || Topic" → extracts "Peter Zeihan"

# Pattern 2: Capitalized words in uploader
"Peter Zeihan Geopolitics" → extracts "Peter Zeihan"
```

### Prompt Structure
```
"Featuring Peter Zeihan. This is a video by Peter Zeihan Geopolitics. Topics: china, economy, trade."
```

## Strengths

### 1. Strategic Positioning ⭐⭐⭐⭐⭐
Names appear FIRST - exactly where Whisper pays most attention in the initial_prompt.

### 2. Robust Pattern Matching ⭐⭐⭐⭐
Handles multiple title formats:
- `"Name || Topic"`
- `"Name | Topic"`
- Extracts from uploader field

### 3. Noise Filtering ⭐⭐⭐⭐
```python
common_words = {"This", "The", "A", "An", "In", "On", "With", "And", "Or", "For", "To", "Of"}
proper_names = {name for name in proper_names if name not in common_words}
```
Prevents false positives like "With Mike" → "With"

### 4. Context Layering ⭐⭐⭐⭐⭐
Builds context in priority order:
1. Names (spelling guide)
2. Uploader (speaker identity)
3. Tags (topic context)
4. Title (fallback)

### 5. Length Management ⭐⭐⭐⭐
Caps at 250 chars to avoid overwhelming Whisper's context window.

### 6. Logging ⭐⭐⭐⭐⭐
```python
logger.info(f"📝 Extracted proper names for Whisper: {names_str}")
logger.info(f"📝 Whisper initial prompt: {prompt}")
```
Makes debugging easy!

## Potential Enhancements

### 1. Handle Multi-Word Surnames
**Current Issue:** May not catch names like "van der Waals" or "de la Cruz"

**Suggested Fix:**
```python
# Enhanced pattern for multi-word names
pattern = r'\b[A-Z][a-z]+(?:(?:\s+(?:van|de|del|von|la)\s+)?[A-Z][a-z]+)*\b'
names = re.findall(pattern, text)
```

**Examples:**
- "Ludwig van Beethoven" ✓
- "Oscar de la Renta" ✓
- "Vincent van Gogh" ✓

### 2. Handle Mononyms and Uncommon Names
**Current Issue:** Pattern `[A-Z][a-z]+` won't catch:
- All caps names: "MKBHD"
- Mixed case: "LaVar" 
- Single names: "Cher", "Madonna"

**Suggested Enhancement:**
```python
# Pattern for all-caps brand names / handles
all_caps = re.findall(r'\b[A-Z]{2,}\b', title)
proper_names.update(all_caps)

# Pattern for mixed-case names (LaVar, DeAndre, etc.)
mixed_case = re.findall(r'\b[A-Z][a-z]*[A-Z][a-z]*\b', title)
proper_names.update(mixed_case)
```

### 3. Expand Common Words Filter
**Current List:**
```python
common_words = {"This", "The", "A", "An", "In", "On", "With", "And", "Or", "For", "To", "Of"}
```

**Suggested Additions:**
```python
common_words = {
    # Articles
    "This", "The", "A", "An",
    # Prepositions
    "In", "On", "With", "And", "Or", "For", "To", "Of", "At", "By", "From",
    # Common video title words
    "How", "What", "Why", "When", "Where", "Who",
    "Episode", "Part", "Season", "Chapter",
    "Interview", "Discussion", "Talk", "Conversation",
    "Official", "Full", "Complete", "New", "Best",
    # Common verbs
    "Explains", "Discusses", "Talks", "Shares", "Reveals",
}
```

### 4. Handle Titles and Honorifics
**Examples:**
- "Dr. Anthony Fauci" → currently extracts "Dr" and "Anthony" separately
- "Prof. Stephen Hawking"
- "Sen. Bernie Sanders"

**Suggested Enhancement:**
```python
# Pattern for titles + names
titles_pattern = r'\b(?:Dr|Prof|Sen|Rep|Mr|Ms|Mrs)\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
titled_names = re.findall(titles_pattern, text)
proper_names.update(titled_names)

# Add titles to filter so they don't appear alone
common_words.update({"Dr", "Prof", "Sen", "Rep", "Mr", "Ms", "Mrs"})
```

### 5. Handle Acronyms and Initialisms
**Examples:**
- "J.K. Rowling"
- "C.S. Lewis"
- "J.R.R. Tolkien"

**Suggested Enhancement:**
```python
# Pattern for initial-based names
initials_pattern = r'\b(?:[A-Z]\.)+\s+[A-Z][a-z]+\b'
initialed_names = re.findall(initials_pattern, text)
proper_names.update(initialed_names)
```

### 6. Cache Name Extractions
For channels you process repeatedly, cache the extracted names:

```python
# In AudioProcessor.__init__ or whisper_cpp_transcribe
self.name_cache = {}  # channel_id -> set of names

# In extraction code
channel_id = video_metadata.get("uploader_id")
if channel_id in self.name_cache:
    proper_names.update(self.name_cache[channel_id])
else:
    # Extract names...
    self.name_cache[channel_id] = proper_names
```

### 7. Add Test Cases

Create `tests/test_proper_name_extraction.py`:

```python
import pytest

def test_basic_name_extraction():
    """Test simple name extraction from title."""
    title = "Peter Zeihan || China's Economic Slowdown"
    names = extract_proper_names(title, "")
    assert "Peter Zeihan" in names

def test_multicultural_names():
    """Test extraction of non-English names."""
    title = "Xi Jinping || China Policy"
    names = extract_proper_names(title, "")
    assert "Xi Jinping" in names or "Xi" in names

def test_filter_common_words():
    """Test that common words are filtered."""
    title = "The Best Interview With Jordan Peterson"
    names = extract_proper_names(title, "")
    assert "The" not in names
    assert "Best" not in names
    assert "Interview" not in names
    assert "Jordan Peterson" in names

def test_all_caps_handles():
    """Test extraction of all-caps brand names."""
    title = "MKBHD Reviews iPhone"
    names = extract_proper_names(title, "")
    assert "MKBHD" in names

def test_titles_with_names():
    """Test extraction of titles with names."""
    title = "Dr. Anthony Fauci on COVID"
    names = extract_proper_names(title, "")
    assert "Dr. Anthony Fauci" in names or "Anthony Fauci" in names
```

## Priority Ranking

| Enhancement | Impact | Effort | Priority |
|------------|--------|--------|----------|
| Multi-word surnames | Medium | Low | Medium |
| Expand common words | High | Low | **High** |
| Handle all-caps names | Medium | Low | Medium |
| Titles/honorifics | Low | Medium | Low |
| Test cases | High | Medium | **High** |
| Name caching | Low | Medium | Low |

## Recommendation

### Immediate Actions (High Priority)
1. ✅ **Expand common words filter** - Quick win, prevents false positives
2. ✅ **Add test cases** - Ensures quality as patterns evolve

### Medium Priority
3. **Add multi-word surname support** - Important for international names
4. **Handle all-caps and mixed-case names** - Catches modern brand names

### Low Priority (Edge Cases)
5. Titles/honorifics - Less common in YouTube titles
6. Caching - Only useful for channels you process repeatedly

## Current Assessment

**Overall Grade: A-** (Very Good, Minor Enhancements Recommended)

The current implementation is:
- ✅ Production-ready
- ✅ Solves the root cause problem
- ✅ Well-documented and logged
- ✅ Properly integrated with Whisper's initial_prompt

The suggested enhancements are **nice-to-have** improvements for edge cases, not critical fixes. The core functionality is excellent!

## Related Files

- `src/knowledge_system/processors/whisper_cpp_transcribe.py` - Implementation (lines 1001-1067)
- `src/knowledge_system/processors/audio_processor.py` - Passes video_metadata to transcriber
- `src/knowledge_system/gui/tabs/transcription_tab.py` - Retrieves metadata from database
- `docs/SPEAKER_ATTRIBUTION_ROOT_CAUSE_FIX_2025.md` - Full documentation (if exists)

## Testing Notes

To verify this is working:

1. **Check logs** for extracted names:
   ```
   📝 Extracted proper names for Whisper: Peter Zeihan, John Doe
   📝 Whisper initial prompt: Featuring Peter Zeihan, John Doe. This is a video by...
   ```

2. **Test with problem names:**
   - "Peter Zeihan" should NOT become "Peter Zine"
   - "Yuval Harari" should NOT become "Yuval Harare"
   - "Dwarkesh Patel" should NOT become "Dwarke Patel"

3. **Compare before/after:**
   - Take a video that previously had misspelled names
   - Re-transcribe with this feature
   - Verify names are now correct

## Conclusion

This is **excellent work** that solves a real problem elegantly. The suggested enhancements are optimizations, not fixes. The code is production-ready and should significantly improve name transcription accuracy across all videos.
