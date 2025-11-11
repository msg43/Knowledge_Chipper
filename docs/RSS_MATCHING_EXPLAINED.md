# RSS to YouTube Matching - How It Works

## Overview

The RSS downloader matches podcast episodes to YouTube videos you've provided, allowing the system to download the podcast version instead (better audio quality, no ads, direct download).

## What Are "Targets"?

**Targets** = The YouTube video URLs you provide to the system.

### Example Flow:

1. **You provide**: `https://youtube.com/watch?v=abc123` (1 target)
2. **System searches**: Podcast RSS feed with 280 episodes
3. **System finds**: Episode #5 matches your YouTube video
4. **System downloads**: Podcast version instead of YouTube
5. **System links**: Both versions in database (YouTube ID ↔ Podcast ID)

## Matching Algorithm

The system uses **3 methods** to match episodes to YouTube videos:

### Method 1: Exact Title Match (100% confidence)
```python
Episode title: "The Future of AI"
YouTube title: "The Future of AI"
→ MATCH (confidence: 1.0)
```

### Method 2: Fuzzy Title Match (90%+ similarity)
```python
Episode title: "The Future of AI - Episode 42"
YouTube title: "The Future of AI (Ep 42)"
→ Similarity: 0.92
→ MATCH (confidence: 0.92)
```

### Method 3: Fuzzy Title + Date Proximity
```python
Episode title: "AI Discussion"
YouTube title: "AI Discussion with Guest"
→ Title similarity: 0.85
→ Published dates: 1 day apart
→ MATCH (confidence: 0.92)
```

## Matching Thresholds

| Title Similarity | Date Match | Result |
|-----------------|------------|--------|
| ≥ 0.9 | Any | ✅ Match (high confidence) |
| ≥ 0.8 | Within 2 days | ✅ Match (medium confidence) |
| ≥ 0.7 | Within 2 days | ✅ Match (low confidence) |
| < 0.7 | Any | ❌ No match |

## Metadata Sources

### YouTube Metadata (for matching)
1. **Database first** (fast): Checks if video already downloaded
2. **yt-dlp fallback** (slower): Fetches metadata if not in database

Retrieved fields:
- Title
- Upload date (YYYYMMDD format)
- Duration
- Uploader

### RSS Episode Metadata
- Title
- Published date
- GUID (unique identifier)
- Audio URL(s)
- Audio type (mp3, m4a, etc.)
- File size (length)
- Duration

## Audio Quality Selection

### YouTube Strategy (for comparison)
```python
format: "worstaudio[vcodec=none]/worstaudio"
format_sort: ["+abr", "+asr"]  # Smallest bitrate/sample rate first
```
→ Downloads ~48-50kbps m4a (smallest available)

### RSS Strategy (NEW)
```python
# Collect all audio enclosures
audio_enclosures = [all audio/* MIME types]

# Sort by file size (ascending)
selected = min(audio_enclosures, key=lambda e: e.length)
```
→ Downloads smallest audio file available

**Rationale**: Transcription doesn't need high quality audio. Smaller files = faster downloads, less bandwidth, less storage.

## Performance Optimization

### Old Behavior (SLOW)
```
Check all 280 episodes even after finding match
→ Time: ~20-30 seconds
```

### New Behavior (FAST)
```
Track unmatched targets
Stop immediately when all targets matched
→ Time: ~0.5-2 seconds (40-280x faster!)
```

### Example with 1 Target

| Match Position | Episodes Checked | Time Saved |
|---------------|------------------|------------|
| Episode #1 (most recent) | 1 instead of 280 | 280x faster |
| Episode #5 | 5 instead of 280 | 56x faster |
| Episode #50 | 50 instead of 280 | 5.6x faster |

## Why Match Instead of Just Downloading Latest?

### Use Cases:

1. **Specific episodes**: You want episode #42, not the latest
2. **Batch processing**: Match 10 YouTube URLs to their podcast versions
3. **Quality preference**: Podcast audio often better than YouTube
4. **Metadata richness**: Podcast RSS has better episode metadata
5. **Source linking**: Track that content exists in multiple places

## Database Linking

When a match is found, the system creates a **source alias**:

```python
create_source_alias(
    primary_source_id="abc123",           # YouTube video ID
    alias_source_id="podcast_xyz789",     # Podcast episode ID
    alias_type="youtube_to_podcast",
    match_confidence=0.92,
    match_method="title_fuzzy_date",
    verified_by="system"
)
```

This allows:
- ✅ Knowing both versions exist
- ✅ Avoiding duplicate transcription
- ✅ Preferring podcast audio when available
- ✅ Tracking match confidence for review

## Terminal Output (NEW)

```
📡 Fetching podcast feed (timeout: 30s)...
✅ Feed fetched successfully (45231 bytes)
🔍 Matching 280 episodes against 1 target(s)...
💡 Will stop early once all 1 target(s) are matched

Matching episodes: 2%|▏ | 5/280 [00:00<00:15, matches=1/1, remaining=0]

✅ [1/1] Matched: The Future of AI - Episode 42 (confidence=0.92, method=title_fuzzy)
✅ All 1 target(s) matched! Stopping early (checked 5/280 episodes)

📥 Downloading 1 matched episode(s)...
[1/1] Downloading: The Future of AI - Episode 42...
Selected lowest quality audio: 12.3 MB (audio/mpeg)
✅ Downloaded: The_Future_of_AI_Episode_42_podcast_a1b2c3d4.mp3
🔗 Created alias: abc123 ↔ podcast_xyz789
```

## Configuration

Currently hardcoded, but could be made configurable:

```python
# Matching thresholds
EXACT_MATCH_THRESHOLD = 1.0
HIGH_CONFIDENCE_THRESHOLD = 0.9
MEDIUM_CONFIDENCE_THRESHOLD = 0.8
LOW_CONFIDENCE_THRESHOLD = 0.7
DATE_PROXIMITY_DAYS = 2

# Quality preference
PREFER_LOWEST_QUALITY = True  # Minimize bandwidth
```

## Future Enhancements

1. **Manual verification UI**: Review low-confidence matches
2. **Configurable thresholds**: Adjust matching sensitivity
3. **Multiple RSS feeds**: Check multiple podcast sources
4. **Quality override**: Option to download highest quality
5. **Batch matching report**: Show all matches before downloading
