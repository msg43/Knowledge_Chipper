# YouTube Download Format Logging

## Problem

When downloading YouTube videos for transcription, the system was downloading video files instead of audio-only files, but only showing cryptic format codes like "format 18" with no clear indication that video was being downloaded.

**Example Issue:**
- 16-minute video downloaded as 47MB MP4 file (video + audio)
- Expected: ~6-15MB audio-only file
- Logs only showed: "format 18" with no explanation

## Solution

### 1. Enhanced Format Logging

Added detailed logging after each download that shows:
- **Format type**: Clearly marked as "audio-only" (✅) or "VIDEO+AUDIO" (⚠️)
- **Format ID**: The yt-dlp format code (e.g., "251", "18", "140")
- **Format note**: Human-readable quality description
- **Codecs**: Video codec (vcodec) and audio codec (acodec)
- **File extension**: Actual file format (webm, m4a, mp4, etc.)
- **File size**: Approximate size in MB

### 2. Video Fallback Warnings

When no audio-only format is available and the system falls back to video:
```
⚠️  Downloaded VIDEO+AUDIO (fallback): format=18 (360p), ext=mp4, 
    vcodec=avc1, acodec=mp4a, size=47.2MB
⚠️  No audio-only format available - fell back to video. 
    Audio will be extracted during transcription.
```

### 3. Audio-Only Success Messages

When audio-only download succeeds:
```
✅ Downloaded audio-only: format=251 (tiny), ext=webm, codec=opus, size=8.5MB
```

## Format Selection Priority

The download system tries formats in this order:
1. `worstaudio[ext=webm]` - Smallest WebM audio
2. `worstaudio[ext=opus]` - Smallest Opus audio  
3. `worstaudio[ext=m4a]` - Smallest M4A audio
4. `worstaudio` - Any worst audio format
5. `bestaudio[ext=webm][abr<=96]` - WebM audio ≤96kbps
6. `bestaudio[ext=m4a][abr<=128]` - M4A audio ≤128kbps
7. `bestaudio[abr<=128]` - Any audio ≤128kbps
8. `bestaudio` - Best available audio-only
9. **⚠️ FALLBACK**: `worst[height<=480]` - Worst video ≤480p (if no audio-only)
10. **⚠️ FALLBACK**: `worst` - Absolute worst quality video
11. **⚠️ FALLBACK**: `best` - Best quality (last resort)

## Expected File Sizes

For a 16-minute episode:

| Format Type | Bitrate | Expected Size |
|------------|---------|---------------|
| Tiny opus (worstaudio) | ~50kbps | ~6MB |
| Low quality audio | 64kbps | ~8MB |
| Medium audio | 96kbps | ~11MB |
| Good audio (128kbps) | 128kbps | ~15MB |
| **360p video+audio** | varies | **~40-50MB** |
| 720p video+audio | varies | ~100-150MB |

## Why Video Fallback Exists

Some videos may not have audio-only streams available:
- Very old YouTube videos
- Videos with copyright restrictions
- Regional blocks on audio formats
- Temporary YouTube API issues

Rather than failing completely, the system downloads video as a fallback and extracts the audio during transcription. This is less efficient but ensures downloads don't fail unnecessarily.

## Files Modified

- `src/knowledge_system/processors/youtube_download.py`
  - Line 786-814: Added format logging after single video download
  - Line 1162-1188: Added format logging for playlist entries
  - Line 72: Updated format string to include video fallback

## Example Logs

### Audio-Only Download (Ideal)
```
✅ Downloaded audio-only: The Movement That Could End Ca... | 
   format=251 (tiny), ext=webm, codec=opus, size=8.5MB
```

### Video Fallback (Warning)
```
⚠️  Downloaded VIDEO+AUDIO (fallback): The Movement That Could End Ca... | 
   format=18 (360p), ext=mp4, vcodec=avc1, acodec=mp4a, size=47.2MB
⚠️  No audio-only format available - fell back to video. 
   Audio will be extracted during transcription.
```

## Impact

- **Before**: Unclear why files were larger than expected, no indication video was downloaded
- **After**: Clear visibility into format selection, immediate warning when video fallback occurs
- **Benefit**: Users can identify format issues and understand download sizes, while still preventing failures

## Related Issues

This logging helps debug:
- Unexpectedly large downloads
- Wrong file format selection
- YouTube format availability issues
- Proxy/region-specific format restrictions

