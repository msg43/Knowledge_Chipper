# PacketStream Sticky Sessions Implementation

## Summary

Successfully implemented sticky IP sessions for PacketStream proxy to ensure:
- Each URL gets a consistent IP address across all requests (metadata, download chunks, thumbnail)
- Different URLs get different IP addresses (avoiding bot detection)
- Support for concurrent downloads with multiple IPs

## Changes Made

### 1. Core Proxy Manager (`src/knowledge_system/utils/packetstream_proxy.py`)

**Updated `get_proxy_url()` method** (line 114):
- Added `session_id` parameter for sticky IP sessions
- Session ID is appended to auth credentials: `username:auth_key-session-{session_id}`
- PacketStream handles the IP assignment based on session ID

**Added `generate_session_id()` static method** (line 138):
- Generates consistent session IDs from URLs or video IDs
- For YouTube videos: uses video ID directly (e.g., "dQw4w9WgXcQ")
- For other content: generates hash from URL (e.g., "url_a1b2c3d4e5f6")
- Ensures deterministic behavior: same URL = same session = same IP

### 2. Main Download Processor (`src/knowledge_system/processors/youtube_download.py`)

**Lines 548-565**: Replaced manual `rotate_session()` calls with session ID approach:
- Generates unique session ID per video using `generate_session_id(url, video_id)`
- Passes session ID to `get_proxy_url(session_id=session_id)`
- Each video gets its own sticky IP automatically
- Removed manual rotation delays and logic

### 3. GUI Batch Worker (`src/knowledge_system/gui/workers/youtube_batch_worker.py`)

**Lines 1461-1478**: Updated proxy URL generation:
- Creates `proxy_session_id` using `generate_session_id(url, video_id)`
- Each concurrent download thread gets its own sticky session
- Supports parallel downloads with different IPs simultaneously

### 4. Metadata Proxy Processor (`src/knowledge_system/processors/youtube_metadata_proxy.py`)

**Lines 148-175**: Updated metadata extraction with session management:
- First attempt: uses sticky session based on URL/video_id
- Retry attempts: uses different session IDs to rotate IP (e.g., "{video_id}_retry1")
- Provides better reliability while maintaining sticky sessions for normal operations

## How It Works

### Session ID Format in Proxy URL

Before (no sticky session):
```
http://username:auth_key@proxy.packetstream.io:31112
```

After (with sticky session):
```
http://username:auth_key-session-dQw4w9WgXcQ@proxy.packetstream.io:31112
```

PacketStream sees the session parameter and ensures all requests with the same session use the same IP.

### Session ID Generation Logic

```python
# YouTube video
generate_session_id("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ")
# Returns: "dQw4w9WgXcQ"

# Non-YouTube URL (RSS feed, etc.)
generate_session_id("https://example.com/feed.xml", None)
# Returns: "url_a1b2c3d4e5f6" (MD5 hash of URL)
```

## Benefits

### 1. Sticky IP Per URL
- All requests for a single video (metadata, chunks, thumbnail) use the same IP
- Natural browsing behavior (YouTube sees one IP downloading one video)
- Reduces risk of bot detection

### 2. Different IPs Per URL
- Each video in a batch gets a unique session ID
- Different session IDs = different IPs from PacketStream pool
- Distributes load across multiple IPs

### 3. Concurrent Downloads
- Multiple threads can download simultaneously
- Each thread passes its own session_id
- No race conditions or conflicts
- Example:
  - Thread 1: downloads video "dQw4w9WgXcQ" via IP 1.2.3.4
  - Thread 2: downloads video "abc123def45" via IP 5.6.7.8
  - Thread 3: downloads video "xyz789pqr12" via IP 9.10.11.12

### 4. Cleaner Code
- Removed manual `rotate_session()` calls
- No shared state to manage
- Deterministic behavior (testable)
- PacketStream handles IP assignment server-side

## Testing

A test script has been created: `test_sticky_sessions.py`

Run it to verify:
```bash
python test_sticky_sessions.py
```

Tests:
1. Same URL gets same session ID consistently
2. Different URLs get different session IDs
3. Works with YouTube videos and generic URLs
4. Proxy URLs contain correct session parameters

## Backward Compatibility

- `get_proxy_url()` still works without `session_id` parameter (defaults to None)
- Existing code without session IDs continues to work (just without sticky sessions)
- No breaking changes to API

## Performance Impact

- No performance overhead (session ID is just a string parameter)
- Better reliability (fewer retries due to consistent IP per URL)
- Improved success rate for bulk downloads

## Related Files Modified

1. `src/knowledge_system/utils/packetstream_proxy.py` - Core proxy manager
2. `src/knowledge_system/processors/youtube_download.py` - Main download processor
3. `src/knowledge_system/gui/workers/youtube_batch_worker.py` - GUI batch downloads
4. `src/knowledge_system/processors/youtube_metadata_proxy.py` - Metadata extraction

## Next Steps

To use sticky sessions in other parts of the codebase:

```python
from knowledge_system.utils.packetstream_proxy import PacketStreamProxyManager

# Initialize proxy manager
proxy_manager = PacketStreamProxyManager()

# Generate session ID for your URL
session_id = PacketStreamProxyManager.generate_session_id(url, video_id)

# Get proxy URL with sticky session
proxy_url = proxy_manager.get_proxy_url(session_id=session_id)

# Use proxy_url in your download/request code
```

---

*Implementation completed: October 11, 2025*
