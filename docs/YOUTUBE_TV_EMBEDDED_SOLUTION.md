# YouTube Audio-Only Downloads - tv_embedded Client Solution

**Date:** October 31, 2025  
**Final Solution:** Use `tv_embedded` client with m4a format 139 targeting

---

## The Optimal Configuration

### Format String
```python
"format": "ba[ext=m4a][abr<=60][vcodec=none]/ba[vcodec=none]"
```

**Targets:**
1. `ba[ext=m4a][abr<=60][vcodec=none]` - M4A audio ≤60kbps, no video (format 139)
2. `ba[vcodec=none]` - Any audio-only format (fallback)

### Format Sorting
```python
"format_sort": ["+abr", "+asr"]
```

**Effect:** Sorts by ascending bitrate → gets format 139 (48-50kbps) when available

### Client Configuration
```python
"player_client": ["tv_embedded", "android", "web"]
```

**Priority:**
1. **tv_embedded** - Most reliable for DASH format listings
2. **android** - Fallback if tv_embedded fails
3. **web** - Last resort (increasingly SABR-only)

---

## Why tv_embedded?

### Problem with Other Clients

**Web Client:**
- Increasingly returns SABR-only manifests
- Hides many formats or breaks format URL availability
- Audio-only still works but listings are incomplete
- Example warning: "web client https formats skipped / SABR"

**Android Client:**
- Better than web but still affected by SABR rollouts
- Format availability can be inconsistent

### tv_embedded Advantages

✅ **Exposes classic DASH entries**  
✅ **Less impacted by SABR-only manifests**  
✅ **More complete format listings**  
✅ **Stable under SABR rollouts**  
✅ **Reliable for audio-only extraction**

---

## Format 139: YouTube's True "Worst" Audio

### Technical Details
- **Format ID:** 139
- **Container:** M4A
- **Codec:** AAC-LC (mp4a.40.5)
- **Bitrate:** ~48-50 kbps
- **Sample Rate:** 22.05 kHz
- **File Size:** ~3-5MB per 16 minutes

### Why Format 139?

**Lowest Consistent Audio:**
- Format 139 is YouTube's floor for audio quality
- Consistently available across most videos
- Opus (webm/251) starts much higher (120-160 kbps+)
- Great for podcasts/speech where quality isn't critical

**Quality vs Size:**
- 48-50 kbps is sufficient for speech/podcasts
- 3x-4x smaller than Opus (120-160 kbps)
- Still intelligible, just lower fidelity

---

## File Size Comparison (16-minute video)

| Format | Codec | Bitrate | Size | Use Case |
|--------|-------|---------|------|----------|
| **139 (m4a)** | AAC-LC | 48-50 kbps | **3-5MB** | ✅ Podcasts/speech (optimal) |
| 140 (m4a) | AAC-LC | 128 kbps | 15MB | Music/high quality |
| 251 (webm) | Opus | 120-160 kbps | 14-19MB | Music/high quality |
| 18 (mp4) | H.264+AAC | varies | 47MB | ❌ Video+audio (wasteful) |

**For 7000 videos:**
- Format 139: **25GB** (3.5MB each)
- Format 251: **100GB** (14MB each)
- Video+audio: **490GB** (70MB each)

**Savings with format 139:** **465GB (95% reduction)**

---

## Command Line Equivalent

This Python configuration is equivalent to:

```bash
yt-dlp --extractor-args "youtube:player_client=tv_embedded" \
       -f "ba[ext=m4a][abr<=60][vcodec=none]/ba[vcodec=none]" \
       -S "+abr,+asr" \
       URL
```

---

## Expected Results

### Logs After Restart
```
🔍 yt-dlp format string: ba[ext=m4a][abr<=60][vcodec=none]/ba[vcodec=none]
🔍 yt-dlp extractor_args: {'youtube': {'player_client': ['tv_embedded', 'android', 'web'], 'player_skip': ['configs']}}
✅ Configured yt-dlp to use tv_embedded client (most reliable for audio-only DASH formats)
✅ Downloaded audio-only: format=139 (tiny), ext=m4a, codec=mp4a, size=3.8MB
```

### File Details
- **Extension:** `.m4a`
- **Size:** 3-5MB for 16 minutes
- **Codec:** AAC-LC (mp4a.40.5)
- **Quality:** 48-50 kbps @ 22.05 kHz

---

## Why This Is The Best Solution

### 1. **Smallest Possible Files**
- Format 139 is YouTube's absolute floor
- 95% reduction vs video+audio
- 75% reduction vs Opus audio

### 2. **Most Reliable Client**
- tv_embedded unaffected by SABR rollouts
- Complete format listings
- Stable extraction

### 3. **Bulletproof Format Selection**
- `[vcodec=none]` guarantees no video
- `[abr<=60]` targets format 139
- Bitrate sorting ensures lowest available

### 4. **Perfect for Podcasts**
- Speech remains intelligible at 48-50 kbps
- Massive storage/bandwidth savings
- Faster downloads and processing

---

## When Format 139 Isn't Available

The fallback `ba[vcodec=none]` will catch:
- Format 140 (128 kbps AAC) - ~15MB
- Format 251 (120-160 kbps Opus) - ~14-19MB
- Other audio-only formats

**Still audio-only, just slightly larger.**

---

## Quality Considerations

### Is 48-50 kbps Enough?

**For Speech/Podcasts:** ✅ Yes
- Voice remains clear and intelligible
- Sufficient for transcription
- Acceptable for listening

**For Music:** ❌ No
- Noticeable quality loss
- Use format 140 (128 kbps) or 251 (Opus) instead

**For This Use Case (Transcription):**
- Perfect - we only need intelligible speech
- Transcription quality unaffected
- Massive cost savings

---

## Migration from Previous Solutions

### Old Configuration
```python
"format": "ba[acodec=opus][vcodec=none]/ba[acodec^=mp4a][vcodec=none]/ba[vcodec=none]"
"player_client": ["android", "web"]
```

**Result:** 14-19MB Opus files (good but not optimal)

### New Configuration
```python
"format": "ba[ext=m4a][abr<=60][vcodec=none]/ba[vcodec=none]"
"player_client": ["tv_embedded", "android", "web"]
```

**Result:** 3-5MB M4A files (optimal for speech)

**Improvement:** 75% smaller files, more reliable extraction

---

## Files Modified

**src/knowledge_system/processors/youtube_download.py**
- Line 76: Updated format string to target m4a format 139
- Line 394: Changed to tv_embedded client (most reliable)

---

## Testing

### 1. Restart the App
Python code changes require full restart.

### 2. Check Logs
```
🔍 yt-dlp format string: ba[ext=m4a][abr<=60][vcodec=none]/ba[vcodec=none]
✅ Configured yt-dlp to use tv_embedded client
```

### 3. Download Test Video
```
✅ Downloaded audio-only: format=139 (tiny), ext=m4a, codec=mp4a, size=3.8MB
```

### 4. Verify File
- Extension: `.m4a`
- Size: 3-5MB for 16 minutes
- Plays correctly in audio player

---

## Sources

- **tv_embedded client:** wiki.archiveteam.org
- **Format 139 details:** jcgl.orpheusweb.co.uk (public format dumps)
- **SABR issues:** GitHub yt-dlp discussions, Reddit reports
- **Format sorting:** man.archlinux.org (yt-dlp documentation)

---

## Summary

**Best Configuration for Audio-Only Downloads:**

```python
# Target YouTube's lowest audio format (139 - 48-50 kbps AAC)
"format": "ba[ext=m4a][abr<=60][vcodec=none]/ba[vcodec=none]"

# Sort by lowest bitrate first
"format_sort": ["+abr", "+asr"]

# Use most reliable client for format listings
"player_client": ["tv_embedded", "android", "web"]
```

**Result:**
- ✅ 3-5MB files (95% reduction vs video+audio)
- ✅ Reliable extraction (unaffected by SABR)
- ✅ Perfect for speech/podcasts
- ✅ Massive cost savings

**For 7000 videos: 465GB savings vs video+audio, 75GB savings vs Opus**
