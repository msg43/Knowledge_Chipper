# RSS Feed URL Guide

## How to Get Raw RSS Feed URLs

The Knowledge Chipper system requires **raw RSS feed URLs**, not web page URLs from podcast platforms.

### Quick Reference

| Platform | Web Page URL | Raw RSS Feed URL |
|----------|--------------|------------------|
| Apple Podcasts | `https://podcasts.apple.com/us/podcast/name/id1702067155` | Use iTunes API or desktop app |
| RSS.com | `https://rss.com/podcasts/zeihan/` | `https://media.rss.com/zeihan/feed.xml` |
| Direct Feed | `https://feeds.megaphone.fm/hubermanlab` | Already correct! |

---

## Method 1: Apple Podcasts (Desktop App)

1. Open the podcast in **Apple Podcasts desktop app** (macOS/Windows)
2. **Right-click** the podcast show
3. Select **"Copy RSS Feed URL"**
4. Paste into Knowledge Chipper

**Example:**
- Web page: `https://podcasts.apple.com/us/podcast/the-peter-zeihan-podcast-series/id1702067155`
- RSS feed: `https://media.rss.com/zeihan/feed.xml`

---

## Method 2: Apple Podcasts (iTunes API)

Use the iTunes Search API to extract the RSS feed URL:

```bash
# Extract podcast ID from URL (e.g., id1702067155)
PODCAST_ID="1702067155"

# Query iTunes API
curl "https://itunes.apple.com/lookup?id=${PODCAST_ID}&entity=podcast" | jq -r '.results[0].feedUrl'
```

**Example:**
```bash
curl "https://itunes.apple.com/lookup?id=1702067155&entity=podcast" | jq -r '.results[0].feedUrl'
# Output: https://media.rss.com/zeihan/feed.xml
```

---

## Method 3: RSS.com Podcasts

RSS.com URLs follow a predictable pattern:

**Pattern:**
```
Web page:  https://rss.com/podcasts/{slug}/
RSS feed:  https://media.rss.com/{slug}/feed.xml
```

**Examples:**
- Peter Zeihan: `https://media.rss.com/zeihan/feed.xml`
- Huberman Lab: `https://media.rss.com/hubermanlab/feed.xml`

**Steps:**
1. Extract the `{slug}` from the RSS.com URL
2. Construct: `https://media.rss.com/{slug}/feed.xml`
3. Verify it works by opening in browser

---

## Method 4: Using the RSS Feed Extractor Utility

Knowledge Chipper includes a utility to automatically extract RSS feeds:

```python
from knowledge_system.utils.rss_feed_extractor import extract_rss_feed_url

# Apple Podcasts URL
apple_url = "https://podcasts.apple.com/us/podcast/id1702067155"
rss_feed = extract_rss_feed_url(apple_url)
print(rss_feed)  # https://media.rss.com/zeihan/feed.xml

# RSS.com URL
rss_com_url = "https://rss.com/podcasts/zeihan/"
rss_feed = extract_rss_feed_url(rss_com_url)
print(rss_feed)  # https://media.rss.com/zeihan/feed.xml

# Direct RSS feed (pass-through)
direct_feed = "https://feeds.megaphone.fm/hubermanlab"
rss_feed = extract_rss_feed_url(direct_feed)
print(rss_feed)  # https://feeds.megaphone.fm/hubermanlab
```

---

## Method 5: Browser Developer Tools

For any podcast website:

1. Open the podcast page in your browser
2. Open **Developer Tools** (F12 or Cmd+Option+I)
3. Go to **Network** tab
4. Look for requests to URLs containing:
   - `feed.xml`
   - `rss`
   - `feed`
5. Copy the RSS feed URL

---

## Method 6: View Page Source

1. Open the podcast page in your browser
2. **View Page Source** (Ctrl+U or Cmd+Option+U)
3. Search for: `application/rss+xml`
4. Find the `<link>` tag with RSS feed URL:
   ```html
   <link rel="alternate" type="application/rss+xml" href="https://media.rss.com/zeihan/feed.xml">
   ```
5. Copy the `href` value

---

## Common Podcast Platforms

### Spotify
Spotify does **not** provide public RSS feeds for podcasts. You'll need to:
- Find the podcast on another platform (Apple Podcasts, RSS.com, etc.)
- Or use the YouTube version if available

### YouTube
For YouTube channels that also have podcasts:
- Knowledge Chipper can automatically map YouTube URLs to RSS feeds
- Just paste the YouTube URL directly

### Megaphone, Simplecast, Libsyn, etc.
These platforms typically provide direct RSS feed URLs:
- `https://feeds.megaphone.fm/{show-name}`
- `https://feeds.simplecast.com/{show-id}`
- `https://feeds.libsyn.com/{show-name}`

---

## Verifying RSS Feed URLs

To verify an RSS feed URL is correct:

1. **Open in browser**: Should show XML content starting with `<rss>` or `<feed>`
2. **Check for episodes**: Look for `<item>` tags with `<enclosure>` (audio files)
3. **Test with curl**:
   ```bash
   curl -I "https://media.rss.com/zeihan/feed.xml"
   # Should return: Content-Type: application/rss+xml
   ```

---

## Peter Zeihan Podcast Example

Based on your URLs:

**Apple Podcasts URL:**
```
https://podcasts.apple.com/us/podcast/regime-change-for-venezuela-peter-zeihan/id1702067155?i=1000734606759
```

**RSS.com URL:**
```
https://rss.com/podcasts/zeihan/2296354/
```

**Raw RSS Feed URL (use this in Knowledge Chipper):**
```
https://media.rss.com/zeihan/feed.xml
```

---

## Future Enhancement

The `RSSFeedExtractor` utility (`src/knowledge_system/utils/rss_feed_extractor.py`) can be integrated into the GUI to automatically extract RSS feeds from Apple Podcasts and RSS.com URLs. This would allow users to paste any podcast URL and have it automatically converted to the raw RSS feed.

**Proposed workflow:**
1. User pastes: `https://podcasts.apple.com/us/podcast/id1702067155`
2. System detects it's an Apple Podcasts URL
3. System queries iTunes API to get RSS feed
4. System downloads from: `https://media.rss.com/zeihan/feed.xml`

This enhancement would make the system more user-friendly and eliminate the need for manual RSS feed extraction.
