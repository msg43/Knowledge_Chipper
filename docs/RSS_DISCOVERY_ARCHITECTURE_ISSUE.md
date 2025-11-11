# RSS Discovery Architecture Issue

## The Problem (User's Insight)

The current implementation has a backwards and inefficient architecture:

### Current Flow (BACKWARDS):
```
1. User provides: YouTube URL "How to Grow Lemon Trees"
2. System extracts: Channel name from YouTube metadata
3. System searches: PodcastIndex/iTunes for channel name
4. System gets: RSS feed URL (e.g., 280 episodes)
5. System downloads: ALL 280 episodes metadata
6. System matches: Title "How to Grow Lemon Trees" against 280 episodes
7. System downloads: Podcast audio if match found
```

**Problems:**
- ❌ Searches by **channel name** instead of **video title**
- ❌ Downloads **entire feed** (280 episodes) to find 1 match
- ❌ Requires user to already have YouTube URL
- ❌ Inefficient: O(n) where n = total episodes in feed

### Correct Flow (FORWARD):
```
1. User provides: YouTube URL "How to Grow Lemon Trees"
2. System extracts: Video title "How to Grow Lemon Trees"
3. System searches: iTunes API by title: "How to Grow Lemon Trees"
4. System gets: Matching podcast episodes (1-5 results)
5. If 1 match: Done! Download that episode
6. If multiple matches: Check channel relationship
   - Does YouTube channel "Gardening Pro" match podcast "Gardening Pro Podcast"?
   - Use previous aliases/relationships from database
7. System downloads: Only the matched episode
```

**Benefits:**
- ✅ Searches by **video title** (more specific)
- ✅ Gets **only matching episodes** (1-5 results)
- ✅ Much faster: O(1) instead of O(n)
- ✅ Can work even without YouTube URL (direct podcast search)

## Current Implementation Details

### Step 1: Channel Discovery (`youtube_to_podcast_mapper.py`)
```python
# Gets YouTube metadata
video_metadata = self._get_youtube_metadata(video_id)
channel_id = video_metadata.get("channel_id")
channel_name = video_metadata.get("channel_name")  # ← Searches by THIS

# Finds RSS feed by CHANNEL name
rss_url = self._find_podcast_feed(channel_id, channel_name)
```

### Step 2: Episode Matching (`podcast_rss_downloader.py`)
```python
# Downloads ENTIRE feed
episodes = self._parse_podcast_feed(rss_url)  # 280 episodes!

# Matches against ALL episodes
for episode in episodes:  # ← Checks all 280!
    is_match = self._match_episode_to_youtube(episode, youtube_video)
```

## Proposed Architecture

### New API-First Approach

```python
class PodcastEpisodeSearcher:
    """Search for specific podcast episodes by title."""
    
    def search_by_title(self, title: str) -> list[PodcastEpisode]:
        """
        Search iTunes/PodcastIndex for episodes matching title.
        
        Args:
            title: Episode title to search for
            
        Returns:
            List of matching episodes (typically 1-5 results)
        """
        # iTunes Search API supports episode-level search
        url = "https://itunes.apple.com/search"
        params = {
            "term": title,
            "media": "podcast",
            "entity": "podcastEpisode",  # ← Search EPISODES, not shows
            "limit": 5
        }
        
        response = requests.get(url, params=params)
        results = response.json().get("results", [])
        
        return [self._parse_episode(r) for r in results]
    
    def resolve_ambiguity(
        self, 
        matches: list[PodcastEpisode],
        youtube_channel: str
    ) -> PodcastEpisode | None:
        """
        Resolve multiple matches using channel relationship.
        
        1. Check database for existing YouTube ↔ Podcast aliases
        2. Fuzzy match channel names
        3. Check historical relationships
        """
        # Check if we've seen this YouTube channel before
        existing_alias = db.get_channel_alias(youtube_channel)
        if existing_alias:
            # Filter matches to this known podcast
            for match in matches:
                if match.podcast_name == existing_alias.podcast_name:
                    return match
        
        # Fuzzy match channel names
        for match in matches:
            similarity = fuzzy_match(youtube_channel, match.podcast_name)
            if similarity > 0.9:
                # Create alias for future use
                db.create_channel_alias(
                    youtube_channel=youtube_channel,
                    podcast_name=match.podcast_name,
                    confidence=similarity
                )
                return match
        
        return None  # User intervention needed
```

### New Flow

```python
def download_podcast_for_youtube_video(youtube_url: str):
    """Download podcast version of YouTube video."""
    
    # 1. Get YouTube metadata
    video_id = extract_video_id(youtube_url)
    metadata = get_youtube_metadata(video_id)
    
    # 2. Search for podcast episode by TITLE
    searcher = PodcastEpisodeSearcher()
    matches = searcher.search_by_title(metadata["title"])
    
    if len(matches) == 0:
        # No podcast version exists
        return download_from_youtube(youtube_url)
    
    elif len(matches) == 1:
        # Perfect! One match, download it
        episode = matches[0]
        return download_podcast_episode(episode)
    
    else:
        # Multiple matches - use channel relationship
        episode = searcher.resolve_ambiguity(
            matches,
            youtube_channel=metadata["channel_name"]
        )
        
        if episode:
            return download_podcast_episode(episode)
        else:
            # Can't resolve - ask user or fallback to YouTube
            return download_from_youtube(youtube_url)
```

## API Capabilities

### iTunes Search API (FREE)

**Episode-level search:**
```bash
curl "https://itunes.apple.com/search?term=How+to+Grow+Lemon+Trees&media=podcast&entity=podcastEpisode&limit=5"
```

Returns:
```json
{
  "results": [
    {
      "trackName": "How to Grow Lemon Trees",
      "collectionName": "Gardening Pro Podcast",
      "feedUrl": "https://feeds.megaphone.fm/gardeningpro",
      "episodeUrl": "https://example.com/episode123.mp3",
      "releaseDate": "2024-03-15",
      "trackTimeMillis": 3600000
    }
  ]
}
```

**Benefits:**
- ✅ Free, no API key required
- ✅ Searches episode titles directly
- ✅ Returns RSS feed URL + episode URL
- ✅ Fast (< 1 second)
- ✅ Returns only matching episodes (not entire feed)

### PodcastIndex.org API

**Episode search:**
```bash
curl -H "X-Auth-Key: YOUR_KEY" \
  "https://api.podcastindex.org/api/1.0/search/byterm?q=How+to+Grow+Lemon+Trees"
```

**Benefits:**
- ✅ More comprehensive than iTunes
- ✅ Better metadata
- ✅ Free tier available
- ✅ Episode-level search

## Migration Path

### Phase 1: Add Episode Search (Non-Breaking)
1. Add `PodcastEpisodeSearcher` class
2. Add episode-level search methods
3. Keep existing channel-based flow as fallback

### Phase 2: Prefer Episode Search
1. Try episode search first
2. Fall back to channel search if no results
3. Log which method worked for analytics

### Phase 3: Remove Channel Search
1. Once episode search proves reliable
2. Remove channel-based discovery
3. Simplify codebase

## Channel Alias Database

Store YouTube ↔ Podcast relationships:

```sql
CREATE TABLE channel_aliases (
    youtube_channel_id TEXT PRIMARY KEY,
    youtube_channel_name TEXT,
    podcast_feed_url TEXT,
    podcast_name TEXT,
    confidence REAL,  -- Fuzzy match confidence
    verified_by TEXT,  -- 'system' or 'user'
    created_at DATETIME,
    last_used_at DATETIME
);
```

**Usage:**
- First match: System creates alias (confidence < 1.0)
- User confirmation: Updates verified_by='user', confidence=1.0
- Future matches: Instant lookup, no API calls needed

## Benefits Summary

### Performance
- **Before**: Download 280 episodes, match against all
- **After**: Get 1-5 results directly from API
- **Speedup**: 50-280x faster

### Accuracy
- **Before**: Match by channel name (broad)
- **After**: Match by episode title (specific)
- **Improvement**: Fewer false positives

### User Experience
- **Before**: User must provide YouTube URL
- **After**: User can search by title directly
- **Improvement**: More flexible input

### Bandwidth
- **Before**: Download full RSS feed (megabytes)
- **After**: Get JSON results (kilobytes)
- **Savings**: 100-1000x less data

## Implementation Priority

1. **High Priority**: Episode search by title
2. **Medium Priority**: Channel alias database
3. **Low Priority**: User disambiguation UI

## Example: Real-World Scenario

**User wants**: "Huberman Lab - How to Optimize Your Brain"

### Current (Slow):
1. Search "Huberman Lab" channel → Get RSS
2. Download 200+ episodes
3. Match "How to Optimize Your Brain" against all
4. Time: ~20 seconds

### Proposed (Fast):
1. Search "How to Optimize Your Brain" in iTunes
2. Get 2 results:
   - Huberman Lab Podcast
   - Brain Science Podcast
3. Check: YouTube channel "Huberman Lab" matches "Huberman Lab Podcast"
4. Download that episode
5. Time: ~2 seconds

**10x faster, more accurate!**
