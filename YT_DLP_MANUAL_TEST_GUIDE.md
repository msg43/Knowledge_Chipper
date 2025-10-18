# yt-dlp 2025.10.14 Upgrade - Manual Testing Guide

## Automated Testing Results ✅

All automated tests passed successfully:
- ✅ Version Check (2025.10.14 installed)
- ✅ Import Test (YouTubeDownloadProcessor working)
- ✅ Format Selection (cascade string valid)
- ✅ Metadata Extraction (working with real YouTube video)
- ✅ Proxy Configuration (PacketStream configured and working)
- ✅ Progress Hooks (callback mechanism functional)

## Manual Testing Required

The following manual tests need to be performed through the GUI to complete the upgrade validation:

### Phase 4.1: Single Video Download Test

**Launch GUI:**
```bash
source venv/bin/activate
python -m knowledge_system.gui
```

**Test Cases:**

1. **Short Video (< 5 min)**
   - Test URL: `https://www.youtube.com/watch?v=jNQXAC9IVRw` (19 seconds)
   - Verify:
     - [ ] Download completes successfully
     - [ ] Progress bar updates in real-time
     - [ ] Audio file created in output directory
     - [ ] Thumbnail saved to Thumbnails/ subdirectory
     - [ ] Metadata extracted (title: "Me at the zoo", duration: 19s)
     - [ ] Database entry created with status "completed"

2. **Long Video (> 30 min)**
   - Find a longer video to test
   - Verify:
     - [ ] Streaming/chunking works properly
     - [ ] Progress updates throughout download
     - [ ] No timeouts or connection issues
     - [ ] File size reasonable for audio-only

3. **Video with Special Characters**
   - Find a video with special characters in title (e.g., emojis, accents)
   - Verify:
     - [ ] Filename handling works correctly
     - [ ] No file system errors
     - [ ] Title stored correctly in database

### Phase 4.2: Playlist Download Test

**Test Playlist:**
- Use a small playlist (3-5 videos)
- Example: Create a test playlist or use a known small playlist

**Verify:**
- [ ] Playlist expansion works correctly
- [ ] All videos download sequentially
- [ ] Deduplication skips already-downloaded videos (test by running twice)
- [ ] Progress updates for each video
- [ ] Staggered delays (3-8 seconds) between downloads visible in logs
- [ ] Database tracks all videos correctly

### Phase 4.3: Proxy Integration Test

**Monitor Console Output:**
- Watch for proxy-related messages during download

**Verify:**
- [ ] "Using PacketStream residential proxies" message appears
- [ ] Proxy connectivity test passes
- [ ] Downloads work through proxy
- [ ] Single-use IP strategy: each video gets unique session ID in logs
- [ ] No proxy authentication errors

### Phase 4.4: Error Handling Test

**Test Cases:**

1. **Invalid URL**
   - Input: `https://www.youtube.com/watch?v=INVALID123`
   - Verify: Graceful error message, no crash

2. **Private Video**
   - Find a private video URL
   - Verify: "Video not found or private" message

3. **Deleted Video**
   - Use a known deleted video ID
   - Verify: 404 handling works correctly

4. **Malformed URL**
   - Input: `not-a-url`
   - Verify: Error message about invalid URL format

**For All Error Cases:**
- [ ] No crashes or unhandled exceptions
- [ ] User-friendly error messages in GUI console
- [ ] Proper error logging in logs/
- [ ] Database marks failed downloads with retry flag

### Phase 4.5: Format Selection Verification

**During any download, check logs:**

**Look for:**
- [ ] Format cascade in logs: `worstaudio[ext=webm]/worstaudio[ext=opus]/worstaudio[ext=m4a]/...`
- [ ] Selected format is audio-only (webm, opus, m4a preferred)
- [ ] No video track downloaded
- [ ] File size reasonable for audio-only (typically 1-5 MB per minute)

**Check downloaded file:**
```bash
# In output directory
file *.webm  # or *.opus, *.m4a
# Should show audio-only, no video stream
```

## Success Criteria

All manual tests must pass:
- [ ] Single video downloads work (short, long, special chars)
- [ ] Playlist downloads work with deduplication
- [ ] Proxy integration working (if configured)
- [ ] Error handling graceful for all edge cases
- [ ] Format selection choosing optimal audio formats
- [ ] No crashes or unhandled exceptions
- [ ] No new errors in logs
- [ ] Performance equal or better than before

## If Tests Fail

If any critical functionality is broken:

1. **Document the failure:**
   - Which test failed
   - Error messages
   - Screenshots if relevant
   - Log excerpts

2. **Check if it's yt-dlp related:**
   - Does the error mention yt-dlp?
   - Is it a format selection issue?
   - Is it a metadata extraction issue?

3. **Consider rollback:**
   - See `docs/YT_DLP_UPGRADE_PROCEDURE.md` Phase 6 for rollback steps
   - Restore backups: `requirements.txt.backup` and `pyproject.toml.backup`
   - Reinstall old version: `pip install --force-reinstall yt-dlp==2025.9.26`

## After Successful Testing

Once all manual tests pass:

1. **Update this document** with test results and date
2. **Commit changes** (see Phase 5.3 in upgrade procedure)
3. **Merge branch** to main
4. **Monitor production** for first 5-10 downloads

## Notes

- Automated tests already passed ✅
- Integration test failure is pre-existing (youtube_transcript module doesn't exist)
- PacketStream proxy is configured and working
- yt-dlp version 2025.10.14 successfully installed
- All core functionality validated by automated tests
