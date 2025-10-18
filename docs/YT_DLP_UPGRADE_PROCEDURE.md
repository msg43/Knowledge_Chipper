# yt-dlp Upgrade Procedure

## Current Status
- **Current Version**: 2025.9.26
- **Target Version**: 2025.10.14
- **Last Tested**: 2025-10-11

## Pre-Upgrade Checklist

### 1. Check Changelog
Visit: https://github.com/yt-dlp/yt-dlp/releases/tag/2025.10.14

Key things to look for:
- Breaking changes in format selection
- Changes to proxy handling
- Updates to progress hooks API
- YouTube extractor changes

### 2. Create Test Environment

```bash
# Create a test branch
git checkout -b test-ytdlp-2025.10.14

# Backup current requirements
cp requirements.txt requirements.txt.backup
cp pyproject.toml pyproject.toml.backup
```

### 3. Update Version Files

Update both files to maintain consistency (pyproject.toml is source of truth):

**pyproject.toml** (line 52):
```toml
"yt-dlp==2025.10.14",  # Last tested: 2025-10-18 - See docs/YT_DLP_UPGRADE_PROCEDURE.md
```

**requirements.txt** (line 29):
```
yt-dlp==2025.10.14  # Last tested: 2025-10-18 - format selection and signature extraction working
```

### 4. Install and Test

```bash
# Install the new version
pip install --upgrade yt-dlp==2025.10.14

# Verify installation
yt-dlp --version
```

## Testing Protocol

### Test 1: Basic Single Video Download
Test with a known working video to verify basic functionality:

```bash
# Start the GUI
python -m knowledge_system.gui

# Test cases:
# 1. Single short video (< 5 min)
# 2. Single long video (> 30 min)
# 3. Age-restricted video
# 4. Video with unusual characters in title
```

**What to verify:**
- ✅ Download completes successfully
- ✅ Progress bar updates correctly
- ✅ Audio file is created in correct format
- ✅ Thumbnail downloads
- ✅ Metadata extraction works
- ✅ Database entry created correctly

### Test 2: Playlist Download
Test playlist expansion and bulk download:

```bash
# Test a small playlist (3-5 videos)
# Example: https://www.youtube.com/playlist?list=...
```

**What to verify:**
- ✅ Playlist expansion works
- ✅ All videos download
- ✅ Deduplication works
- ✅ Progress updates for each video
- ✅ Staggered delays between downloads

### Test 3: Proxy Integration
Test with PacketStream proxy (if configured):

```bash
# Test with proxy enabled
# Monitor logs for proxy connection messages
```

**What to verify:**
- ✅ Proxy connectivity test passes
- ✅ Downloads work through proxy
- ✅ Single-use IP strategy works
- ✅ Error handling for proxy failures

### Test 4: Error Handling
Test edge cases:

```bash
# Test cases:
# 1. Invalid URL
# 2. Private video
# 3. Deleted video
# 4. Geographically restricted video
```

**What to verify:**
- ✅ Graceful error messages
- ✅ No crashes
- ✅ Proper error logging
- ✅ Database marks failed downloads correctly

### Test 5: Format Selection
Verify the format cascade still works:

```bash
# Check logs for format selection messages
# Should see: "worstaudio[ext=webm]/worstaudio[ext=opus]/..."
```

**What to verify:**
- ✅ Smallest audio format selected
- ✅ Audio-only (no video track)
- ✅ File size reasonable for audio-only

### Test 6: Integration Test
Run the existing integration test:

```bash
python test_youtube_integration.py
```

**What to verify:**
- ✅ All tests pass
- ✅ No import errors
- ✅ Processor instantiates correctly

## Rollback Procedure

If tests fail, rollback immediately:

```bash
# Restore backup files
cp requirements.txt.backup requirements.txt
cp pyproject.toml.backup pyproject.toml

# Reinstall old version
pip install --force-reinstall yt-dlp==2025.9.26

# Verify rollback
yt-dlp --version

# Return to main branch
git checkout remove-cli-add-gui-tests
git branch -D test-ytdlp-2025.10.14
```

## Known Issues to Watch For

Based on your code analysis, monitor for:

1. **Format Selection Changes**
   - Your cascade: `worstaudio[ext=webm]/worstaudio[ext=opus]/worstaudio[ext=m4a]/...`
   - Watch for: Changes in format availability or selection logic

2. **Proxy Handling**
   - You use: `"proxy": current_proxy_url` in ydl_opts
   - Watch for: Proxy connection failures or authentication issues

3. **Progress Hooks**
   - You use: `progress_hooks` for GUI updates
   - Watch for: Changes in hook callback signature or data structure

4. **Metadata Extraction**
   - You extract: title, duration, uploader, description, etc.
   - Watch for: Missing or renamed metadata fields

5. **Fragment Downloading**
   - You use: `http_chunk_size`, `fragment_retries`, `no_part`
   - Watch for: Changes in chunked download behavior

## Success Criteria

Upgrade is successful when:
- ✅ All 6 test scenarios pass
- ✅ No regressions in existing functionality
- ✅ No new errors in logs
- ✅ Performance is equal or better
- ✅ Integration test passes

## Post-Upgrade Actions

After successful testing:

1. **Update Documentation**
   - Update "Last tested" date in both files
   - Document any new issues discovered
   - Update this procedure with lessons learned

2. **Commit Changes**
   ```bash
   git add requirements.txt pyproject.toml docs/YT_DLP_UPGRADE_PROCEDURE.md
   git commit -m "chore: upgrade yt-dlp to 2025.10.14
   
   - Updated from 2025.9.26 to 2025.10.14
   - Tested: single video, playlist, proxy, error handling
   - All tests passing
   - See docs/YT_DLP_UPGRADE_PROCEDURE.md for details"
   ```

3. **Monitor Production**
   - Watch logs for first few downloads
   - Monitor error rates
   - Check user reports

## Maintenance Schedule

Recommended upgrade frequency:
- **Critical fixes**: Upgrade immediately (YouTube blocking issues)
- **Regular updates**: Every 2-4 weeks
- **Security patches**: Within 1 week
- **Feature updates**: As needed

## Reference Links

- yt-dlp Releases: https://github.com/yt-dlp/yt-dlp/releases
- yt-dlp Issues: https://github.com/yt-dlp/yt-dlp/issues
- Format Selection: https://github.com/yt-dlp/yt-dlp#format-selection
- Proxy Support: https://github.com/yt-dlp/yt-dlp#network-options
