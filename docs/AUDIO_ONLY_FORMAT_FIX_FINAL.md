# Audio-Only Format Selection - Final Fix

**Date:** October 31, 2025  
**Issue:** Still downloading video+audio despite initial fix

---

## Problem Analysis

The initial fix changed the player_client priority from Android-first to Web-first, which was correct. However, the format string itself may not have been aggressive enough in rejecting video streams.

### Original Format String (Too Permissive)
```python
"format": "worstaudio[ext=webm]/worstaudio[ext=opus]/worstaudio[ext=m4a]/worstaudio/bestaudio[ext=webm][abr<=96]/bestaudio[ext=m4a][abr<=128]/bestaudio[abr<=128]/bestaudio/worst[height<=480]/worst/best"
```

**Problem:** This format string includes video fallbacks:
- `worst[height<=480]` - Downloads 480p video if no audio-only available
- `worst` - Downloads worst quality video
- `best` - Downloads best quality (often video+audio)

These fallbacks were intended to prevent failures, but they're causing video+audio downloads.

---

## Final Solution

### 1. More Aggressive Format String

Changed to explicitly filter out any format with video codec:

```python
"format": "ba[vcodec=none]/bestaudio[vcodec=none]/ba[acodec=opus]/ba[acodec=vorbis]/ba/bestaudio"
```

**What this does:**
- `ba[vcodec=none]` - Best audio with NO video codec
- `bestaudio[vcodec=none]` - Best audio explicitly without video
- `ba[acodec=opus]` - Best audio with opus codec (common for YouTube)
- `ba[acodec=vorbis]` - Best audio with vorbis codec (common for YouTube)
- `ba` - Best audio (fallback)
- `bestaudio` - Best audio (final fallback)

**NO VIDEO FALLBACKS** - If no audio-only format exists, download will fail rather than download video.

### 2. Web Client Priority (Already Fixed)

```python
"player_client": ["web", "android"]  # Web first, Android fallback
```

Web client respects audio-only format selectors better than Android client.

---

## Why It Was Still Downloading Video+Audio

### Possible Reasons:

1. **App Not Restarted** ⚠️ MOST LIKELY
   - Python code changes require app restart
   - Old code still in memory
   - **Solution:** Restart the app

2. **Format String Too Permissive**
   - Old format string had video fallbacks
   - yt-dlp was using those fallbacks
   - **Solution:** New format string (applied above)

3. **Cached yt-dlp Configuration**
   - yt-dlp might cache format info
   - **Solution:** Restart app clears cache

4. **Specific Videos Don't Have Audio-Only**
   - Very rare, but some videos only have combined streams
   - **Solution:** New format string will fail rather than download video

---

## Files Modified

1. **src/knowledge_system/processors/youtube_download.py**
   - Line 75: Changed format string to be more aggressive about audio-only
   - Lines 380-395: Changed player_client priority (already done)
   - Lines 533-537: Added diagnostic logging (already done)

---

## Testing Instructions

### CRITICAL: Restart the App First!

**Before testing, you MUST restart the app for Python code changes to take effect.**

### Test Steps:

1. **Restart the app completely** (close and reopen)

2. **Check the logs for diagnostic output:**
   ```
   🔍 yt-dlp format string: ba[vcodec=none]/bestaudio[vcodec=none]/ba[acodec=opus]/ba[acodec=vorbis]/ba/bestaudio
   🔍 yt-dlp extractor_args: {'youtube': {'player_client': ['web', 'android'], 'player_skip': ['configs']}}
   ```

3. **Download a test video** (with cookies enabled)

4. **Check the download logs:**
   - ✅ Should see: `✅ Downloaded audio-only: format=251 (tiny), ext=webm, codec=opus`
   - ❌ Should NOT see: `⚠️ Downloaded VIDEO+AUDIO (fallback)`

5. **Check file size:**
   - For 16-minute video: Should be ~6-15MB (audio-only)
   - Should NOT be ~40-50MB (video+audio)

6. **Check file extension:**
   - Should be: `.webm`, `.m4a`, `.opus`, `.ogg` (audio formats)
   - Should NOT be: `.mp4` (usually video+audio)

---

## What If It Still Downloads Video?

If after restarting the app it STILL downloads video+audio, check these:

### 1. Verify the Code Changes Were Applied

Run this command:
```bash
grep "ba\[vcodec=none\]" src/knowledge_system/processors/youtube_download.py
```

Should output:
```
"format": "ba[vcodec=none]/bestaudio[vcodec=none]/ba[acodec=opus]/ba[acodec=vorbis]/ba/bestaudio",
```

### 2. Check the Diagnostic Logs

The logs should show:
```
🔍 yt-dlp format string: ba[vcodec=none]/bestaudio[vcodec=none]/ba[acodec=opus]/ba[acodec=vorbis]/ba/bestaudio
```

If it shows the OLD format string with `worst[height<=480]`, the code wasn't reloaded.

### 3. Check What Format Was Actually Downloaded

The logs should show:
```
✅ Downloaded audio-only: format=251 (tiny), ext=webm, codec=opus, size=8.5MB
```

If it shows:
```
⚠️ Downloaded VIDEO+AUDIO (fallback): format=18 (360p), ext=mp4, vcodec=avc1, acodec=mp4a, size=47.2MB
```

Then either:
- The specific video doesn't have audio-only formats (very rare)
- Something else is overriding the format string

### 4. Test with a Known Good Video

Try this video (known to have audio-only formats):
```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

If this downloads audio-only but your target video doesn't, the issue is with the specific video.

---

## Format String Comparison

### OLD (Permissive - Downloads Video as Fallback)
```python
"format": "worstaudio[ext=webm]/worstaudio[ext=opus]/worstaudio[ext=m4a]/worstaudio/bestaudio[ext=webm][abr<=96]/bestaudio[ext=m4a][abr<=128]/bestaudio[abr<=128]/bestaudio/worst[height<=480]/worst/best"
```
- ❌ Has video fallbacks: `worst[height<=480]/worst/best`
- ❌ Will download video+audio if no audio-only available

### NEW (Strict - Audio-Only or Fail)
```python
"format": "ba[vcodec=none]/bestaudio[vcodec=none]/ba[acodec=opus]/ba[acodec=vorbis]/ba/bestaudio"
```
- ✅ Explicitly filters out video: `[vcodec=none]`
- ✅ No video fallbacks
- ✅ Will fail rather than download video

---

## Expected Behavior After Fix

### Successful Audio-Only Download
```
🔍 yt-dlp format string: ba[vcodec=none]/bestaudio[vcodec=none]/ba[acodec=opus]/ba[acodec=vorbis]/ba/bestaudio
🔍 yt-dlp extractor_args: {'youtube': {'player_client': ['web', 'android'], 'player_skip': ['configs']}}
✅ Using cookies from throwaway account
✅ Configured yt-dlp to use Web client (preserves audio-only format selection with cookies)
Downloading audio for: https://www.youtube.com/watch?v=...
✅ Downloaded audio-only: format=251 (tiny), ext=webm, codec=opus, size=8.5MB
```

### If Video Has No Audio-Only Formats (Rare)
```
❌ Download failed: No formats found matching format selector
```

This is BETTER than silently downloading 40MB of video when you only need 8MB of audio.

---

## Cost Impact

For a batch of 7000 videos (average 30 minutes each):

### Before Fix (Video+Audio)
- File size: ~70MB per video
- Total: ~490GB (7000 × 70MB)
- Bandwidth cost: ~$50-100 (depending on provider)

### After Fix (Audio-Only)
- File size: ~10MB per video
- Total: ~70GB (7000 × 10MB)
- Bandwidth cost: ~$7-15

**Savings:** ~420GB storage, ~$35-85 bandwidth costs

---

## Troubleshooting

### "Still downloading video+audio after restart"

1. Verify app was actually restarted (not just tab switched)
2. Check logs for diagnostic output with new format string
3. Try a different test video
4. Check if you're using GUI or CLI (both should work)

### "Downloads are failing now"

If downloads start failing with "No formats found", it means:
- The video truly doesn't have audio-only formats (very rare)
- You can temporarily revert to old format string if needed
- But this is better than wasting bandwidth on video

### "Format string in logs doesn't match code"

- Python code wasn't reloaded
- Try: Kill app completely, restart
- Check if running from source or installed package

---

## Related Documentation

- `docs/COOKIE_PERSISTENCE_AND_FORMAT_FIX_2025.md` - Initial fix documentation
- `docs/YOUTUBE_DOWNLOAD_FORMAT_LOGGING.md` - Format logging details
- `scripts/test_cookie_and_format_fixes.sh` - Automated test script

---

## Summary

**Root Cause:** Format string was too permissive and included video fallbacks

**Solution:** 
1. More aggressive format string with explicit `[vcodec=none]` filter
2. Web client priority (already fixed)
3. **MUST restart app for changes to take effect**

**Expected Result:** Audio-only downloads (6-15MB) instead of video+audio (40-50MB)

**If still not working:** Check diagnostic logs and verify format string is being used

