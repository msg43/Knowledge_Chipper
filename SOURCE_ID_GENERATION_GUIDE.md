# Source ID Generation Guide

**Date:** November 2, 2025  
**Purpose:** Comprehensive guide to how source_ids are generated across all media types

---

## Overview

The `source_id` is the **universal identifier** for all media in the Knowledge System. It's the primary key in the `MediaSource` table and is used throughout the system to link transcripts, summaries, claims, and other data to their source.

**Key Principle:** Source IDs must be **deterministic** - processing the same content twice should generate the same source_id.

---

## Source ID Formats by Media Type

### 1. YouTube Videos ✅
**Format:** `VIDEO_ID` (11-character YouTube video ID)  
**Example:** `dQw4w9WgXcQ`

**Generation:**
```python
from knowledge_system.utils.video_id_extractor import VideoIDExtractor

source_id = VideoIDExtractor.extract_video_id(url)
# Input: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
# Output: "dQw4w9WgXcQ"
```

**Properties:**
- **Deterministic:** ✅ Same video always has same ID
- **Unique:** ✅ YouTube guarantees uniqueness
- **Human-readable:** ✅ Can be used in URLs
- **Collision-free:** ✅ YouTube's responsibility

**File:** `src/knowledge_system/utils/video_id_extractor.py`

---

### 2. Podcast Episodes (RSS) ✅
**Format:** `podcast_{feed_hash}_{episode_guid_hash}`  
**Example:** `podcast_abc12345_def67890`

**Generation:**
```python
import hashlib

# Hash feed URL (8 chars)
feed_hash = hashlib.md5(
    feed_url.encode(), 
    usedforsecurity=False
).hexdigest()[:8]

# Hash episode GUID (8 chars)
guid_hash = hashlib.md5(
    episode_guid.encode(), 
    usedforsecurity=False
).hexdigest()[:8]

source_id = f"podcast_{feed_hash}_{guid_hash}"
# Example: "podcast_abc12345_def67890"
```

**Properties:**
- **Deterministic:** ✅ Same episode always generates same ID
- **Unique:** ✅ Feed URL + GUID is unique
- **Human-readable:** ⚠️ Hash is not readable, but prefix indicates type
- **Collision-free:** ✅ MD5 collision extremely unlikely for 16-char hash

**File:** `src/knowledge_system/services/podcast_rss_downloader.py`

---

### 3. Documents (PDF, DOCX, TXT, MD, RTF, EPUB) ✅
**Format:** `doc_{filename}_{path_hash}`  
**Example:** `doc_whitepaper_a1b2c3d4`

**Generation:**
```python
import hashlib
from pathlib import Path

file_path = Path("/path/to/whitepaper.pdf")

# Hash absolute file path (8 chars)
path_hash = hashlib.md5(
    str(file_path.absolute()).encode(),
    usedforsecurity=False
).hexdigest()[:8]

source_id = f"doc_{file_path.stem}_{path_hash}"
# Example: "doc_whitepaper_a1b2c3d4"
```

**Properties:**
- **Deterministic:** ✅ Same file path always generates same ID
- **Unique:** ✅ File path is unique on filesystem
- **Human-readable:** ✅ Includes filename for easy identification
- **Collision-free:** ✅ MD5 collision extremely unlikely

**File:** `src/knowledge_system/processors/document_processor.py` (lines 274-281)

**Supported Formats:**
- `.pdf` - PDF documents
- `.docx`, `.doc` - Microsoft Word
- `.txt` - Plain text
- `.md` - Markdown
- `.rtf` - Rich Text Format
- `.epub` - E-books (future support)

---

### 4. Local Audio Files (Non-YouTube) 🔄
**Format:** `audio_{filename}_{path_hash}`  
**Example:** `audio_interview_x9y8z7w6`

**Generation:**
```python
import hashlib
from pathlib import Path

audio_file = Path("/path/to/interview.mp3")

# Hash absolute file path (8 chars)
path_hash = hashlib.md5(
    str(audio_file.absolute()).encode(),
    usedforsecurity=False
).hexdigest()[:8]

source_id = f"audio_{audio_file.stem}_{path_hash}"
# Example: "audio_interview_x9y8z7w6"
```

**Properties:**
- **Deterministic:** ✅ Same file path always generates same ID
- **Unique:** ✅ File path is unique on filesystem
- **Human-readable:** ✅ Includes filename
- **Collision-free:** ✅ MD5 collision extremely unlikely

**File:** `src/knowledge_system/processors/audio_processor.py`

**Supported Formats:**
- `.mp3` - MP3 audio
- `.m4a` - M4A audio
- `.wav` - WAV audio
- `.flac` - FLAC audio
- `.ogg` - OGG audio
- `.opus` - Opus audio

---

## Design Principles

### 1. Deterministic Generation
**Why:** Re-processing the same content should update the existing record, not create duplicates.

**Good:**
```python
# First run
source_id = generate_source_id("/path/to/file.pdf")  # "doc_file_abc123"

# Second run (same file)
source_id = generate_source_id("/path/to/file.pdf")  # "doc_file_abc123" (same!)
```

**Bad:**
```python
# Using timestamps (non-deterministic)
source_id = f"doc_{file.stem}_{int(time.time())}"  # Different every time!
```

### 2. Collision Resistance
**Why:** Two different files should never have the same source_id.

**Strategy:**
- **YouTube:** Use YouTube's video ID (guaranteed unique by YouTube)
- **Podcasts:** Hash feed URL + episode GUID (both unique)
- **Local files:** Hash absolute file path (unique on filesystem)

**Hash Length:** 8 characters (MD5 truncated)
- **Collision probability:** ~1 in 4 billion (2^32)
- **Acceptable risk:** For local files, extremely unlikely

### 3. Human Readability
**Why:** Makes debugging and logging easier.

**Format:** `{type}_{readable_part}_{hash}`

**Examples:**
- `doc_whitepaper_abc123` - Clearly a document, filename visible
- `podcast_abc_def` - Clearly a podcast
- `dQw4w9WgXcQ` - YouTube video (standard format)

### 4. Database Compatibility
**Why:** source_id is the primary key in MediaSource table.

**Requirements:**
- **Type:** String (TEXT in SQLite)
- **Max length:** ~50 characters (current max is ~30)
- **Characters:** Alphanumeric + underscore (no spaces, no special chars)
- **Case:** Lowercase preferred (for consistency)

---

## Implementation Examples

### Example 1: Processing a PDF
```python
from pathlib import Path
from knowledge_system.processors.document_processor import DocumentProcessor

# Process PDF
processor = DocumentProcessor()
result = processor.process("/path/to/research_paper.pdf")

# Source ID generated automatically
# Format: "doc_research_paper_a1b2c3d4"
```

### Example 2: Downloading YouTube Video
```python
from knowledge_system.processors.youtube_download import YouTubeDownloadProcessor

# Download YouTube video
processor = YouTubeDownloadProcessor()
result = processor.process("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# Source ID extracted from URL
# Format: "dQw4w9WgXcQ"
```

### Example 3: Processing Podcast RSS
```python
from knowledge_system.services.podcast_rss_downloader import PodcastRSSDownloader

# Download podcast episode
downloader = PodcastRSSDownloader()
files = downloader.download_from_rss(
    rss_url="https://feeds.megaphone.fm/hubermanlab",
    target_source_ids={"dQw4w9WgXcQ": "https://youtube.com/..."},
    output_dir=Path("downloads")
)

# Source ID generated from feed URL + episode GUID
# Format: "podcast_abc12345_def67890"
```

---

## Edge Cases & Special Situations

### 1. File Moved to Different Location
**Problem:** File path changes, so hash changes, creating new source_id.

**Current Behavior:**
```python
# Original location
source_id_1 = generate_source_id("/downloads/file.pdf")  # "doc_file_abc123"

# Moved to new location
source_id_2 = generate_source_id("/archive/file.pdf")    # "doc_file_xyz789" (different!)
```

**Impact:** Creates duplicate record in database.

**Workaround:** Use `audio_file_path` field to find existing record:
```python
# Check if file already processed
existing = db.get_source_by_file_path("/archive/file.pdf")
if existing:
    # Update existing record
    db.update_source(existing.source_id, audio_file_path="/archive/file.pdf")
```

**Future Enhancement:** Use content hash instead of path hash for documents.

### 2. Same Content, Different Filenames
**Problem:** Same PDF saved with different names creates different source_ids.

**Current Behavior:**
```python
source_id_1 = generate_source_id("/path/to/paper_v1.pdf")  # "doc_paper_v1_abc123"
source_id_2 = generate_source_id("/path/to/paper_v2.pdf")  # "doc_paper_v2_xyz789"
```

**Impact:** Duplicate records for same content.

**Workaround:** Use multi-source deduplication (see `MULTI_SOURCE_DEDUPLICATION_COMPLETE.md`).

**Future Enhancement:** Use content hash (SHA256 of file contents) for true deduplication.

### 3. YouTube Video Reposted
**Problem:** Same video uploaded by different channels has different video IDs.

**Current Behavior:**
```python
# Original upload
source_id_1 = "dQw4w9WgXcQ"

# Reposted by different channel
source_id_2 = "xYz9w8v7u6T"
```

**Impact:** Two records for same content.

**Workaround:** Use multi-source deduplication with fuzzy title matching.

**Future Enhancement:** Audio fingerprinting to detect identical content.

---

## Future Enhancements

### 1. Content-Based Hashing for Documents
**Current:** Hash file path (changes if file moved)  
**Proposed:** Hash file contents (stable across moves)

```python
import hashlib

def generate_content_hash(file_path: Path) -> str:
    """Generate hash from file contents."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]  # 16 chars = 64 bits

source_id = f"doc_{file_path.stem}_{generate_content_hash(file_path)}"
```

**Benefits:**
- ✅ Stable across file moves
- ✅ Detects duplicate content
- ✅ Still deterministic

**Drawbacks:**
- ⚠️ Slower (must read entire file)
- ⚠️ Doesn't work for streaming content

### 2. DOI-Based IDs for Academic Papers
**Current:** Hash file path  
**Proposed:** Use DOI if available

```python
def generate_paper_source_id(file_path: Path, doi: str | None) -> str:
    """Generate source_id for academic paper."""
    if doi:
        # Use DOI (guaranteed unique by publishers)
        doi_clean = doi.replace('/', '_').replace('.', '_')
        return f"paper_{doi_clean}"
    else:
        # Fallback to content hash
        return f"doc_{file_path.stem}_{generate_content_hash(file_path)}"
```

**Benefits:**
- ✅ Globally unique (DOI system)
- ✅ Stable across all copies
- ✅ Can link to external databases

### 3. ISBN for Books
**Current:** Hash file path  
**Proposed:** Use ISBN for EPUB/MOBI files

```python
def generate_book_source_id(file_path: Path, isbn: str | None) -> str:
    """Generate source_id for books."""
    if isbn:
        # Use ISBN (guaranteed unique by publishers)
        isbn_clean = isbn.replace('-', '')
        return f"book_{isbn_clean}"
    else:
        # Fallback to content hash
        return f"doc_{file_path.stem}_{generate_content_hash(file_path)}"
```

---

## Testing Source ID Generation

### Test Case 1: Deterministic Generation
```python
import hashlib
from pathlib import Path

def test_deterministic_generation():
    """Verify same input generates same source_id."""
    file_path = Path("/test/file.pdf")
    
    # Generate twice
    id1 = generate_source_id(file_path)
    id2 = generate_source_id(file_path)
    
    assert id1 == id2, "Source IDs must be deterministic"
```

### Test Case 2: Collision Resistance
```python
def test_collision_resistance():
    """Verify different files generate different source_ids."""
    file1 = Path("/test/file1.pdf")
    file2 = Path("/test/file2.pdf")
    
    id1 = generate_source_id(file1)
    id2 = generate_source_id(file2)
    
    assert id1 != id2, "Different files must have different source_ids"
```

### Test Case 3: Format Validation
```python
def test_format_validation():
    """Verify source_id format is valid."""
    file_path = Path("/test/whitepaper.pdf")
    source_id = generate_source_id(file_path)
    
    # Check format
    assert source_id.startswith("doc_"), "Document IDs must start with 'doc_'"
    assert len(source_id) <= 50, "Source ID too long"
    assert source_id.replace('_', '').isalnum(), "Source ID must be alphanumeric"
```

---

## Summary

### Current Source ID Formats

| Media Type | Format | Example | Deterministic | Unique |
|------------|--------|---------|---------------|--------|
| YouTube | `VIDEO_ID` | `dQw4w9WgXcQ` | ✅ | ✅ |
| Podcast | `podcast_{feed_hash}_{guid_hash}` | `podcast_abc_def` | ✅ | ✅ |
| Document | `doc_{filename}_{path_hash}` | `doc_paper_abc123` | ✅ | ✅ |
| Audio | `audio_{filename}_{path_hash}` | `audio_interview_xyz` | ✅ | ✅ |

### Key Files

1. **YouTube:** `src/knowledge_system/utils/video_id_extractor.py`
2. **Podcasts:** `src/knowledge_system/services/podcast_rss_downloader.py`
3. **Documents:** `src/knowledge_system/processors/document_processor.py` (lines 274-281)
4. **Audio:** `src/knowledge_system/processors/audio_processor.py`

### Design Principles

1. ✅ **Deterministic** - Same content = same ID
2. ✅ **Collision-resistant** - Different content = different ID
3. ✅ **Human-readable** - Include type prefix and filename
4. ✅ **Database-compatible** - Alphanumeric + underscore only

---

## Questions?

**Q: What if I move a file to a different folder?**  
A: The source_id will change (based on path hash). Use `get_source_by_file_path()` to find the existing record and update it.

**Q: What if I have the same PDF with different filenames?**  
A: Currently creates duplicate records. Use multi-source deduplication or wait for content-based hashing.

**Q: Can I manually set a source_id?**  
A: Not recommended. Let the system generate it to ensure consistency. For special cases, use the `create_source()` method directly.

**Q: What about URLs from websites (not YouTube)?**  
A: Not currently supported. Would need a new source_id format like `web_{url_hash}`.
