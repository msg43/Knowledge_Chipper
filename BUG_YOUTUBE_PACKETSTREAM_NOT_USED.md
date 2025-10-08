# BUG: PacketStream Credentials Not Used for YouTube Downloads

## 📍 Location
`src/knowledge_system/processors/youtube_download.py`

## 🔍 Description
YouTube download processor is configured to use PacketStream proxy but has dead code from old Bright Data integration that prevents the proxy from actually being used.

## 🐛 Root Cause

### Problem 1: Undefined Variable `use_bright_data`
**Line 587:** `if use_bright_data:`

This variable is **NEVER initialized** anywhere in the function. It's only set to `False` in error handlers (lines 351, 408), meaning:
- If execution reaches line 587, `use_bright_data` will cause a `NameError`
- The code will fail before even attempting to use the proxy

### Problem 2: Undefined Variable `session_manager`
**Lines 598-603:** Code tries to use `session_manager.create_session_for_file()` and `session_manager.get_proxy_url_for_file()`, but `session_manager` is **never created** or imported.

### Problem 3: Wrong Proxy Being Used
The code correctly initializes `PacketStreamProxyManager` at line 253 and gets `proxy_url` at line 295, but then **ignores it** and tries to use Bright Data instead.

## 📝 Evidence

### What's Working:
```python
# Lines 252-260: PacketStream initialization ✅
proxy_manager = PacketStreamProxyManager()
if proxy_manager.username and proxy_manager.auth_key:
    use_proxy = True  # ✅ This works
    logger.info("Using PacketStream residential proxies for YouTube processing")
    
# Line 295: Get proxy URL ✅
proxy_url = proxy_manager.get_proxy_url() if proxy_manager else None
```

### What's Broken:
```python
# Line 587: UNDEFINED VARIABLE ❌
if use_bright_data:  # NameError: name 'use_bright_data' is not defined
    # Lines 598-603: UNDEFINED VARIABLE ❌
    session_manager.create_session_for_file(...)  # NameError: name 'session_manager' is not defined
```

## 🎯 Impact

### Test Results:
- **All 6 YouTube tests fail** despite PacketStream credentials being configured
- Playlist expansion works (uses PacketStream correctly in `youtube_utils.py`)
- Video download never happens because code crashes on `use_bright_data`

### Logs Show:
```
✅ Using PacketStream residential proxies for playlist expansion
✅ Expanded playlist 'ALREADY SUMMARIZED' to 4 videos
❌ [Video download never starts - crashes before reaching yt-dlp]
```

## 🔧 Fix Required

### Option 1: Use PacketStream (Recommended)
Remove all Bright Data logic and use the already-initialized PacketStream proxy:

```python
# Line 584: Simply use the proxy_url we already have
current_proxy_url = proxy_url  # Already set from PacketStream at line 295

# Lines 587-613: DELETE ALL THIS CODE
# It references undefined variables and tries to use Bright Data
```

### Option 2: Initialize use_bright_data
If Bright Data support needs to be maintained:

```python
# After line 250, add:
use_bright_data = False  # Default to False
session_manager = None

# Then check if Bright Data is configured:
try:
    from ..utils.bright_data import BrightDataSessionManager
    session_manager = BrightDataSessionManager()
    if session_manager._validate_credentials():
        use_bright_data = True
except:
    use_bright_data = False
```

## 📊 Verification

### Before Fix:
```
❌ youtube_transcribe_Youtube_Playlists_1_no_diarization
❌ youtube_transcribe_Youtube_Playlists_1_with_diarization
(NameError on line 587: use_bright_data is not defined)
```

### After Fix:
```
✅ youtube_transcribe_Youtube_Playlists_1_no_diarization
✅ youtube_transcribe_Youtube_Playlists_1_with_diarization
(Uses PacketStream proxy correctly)
```

## 🚨 Severity
**CRITICAL** - Completely blocks YouTube downloads when using PacketStream credentials

## 💡 Additional Notes

The code has mixed concerns from two different proxy providers:
1. **PacketStream**: Initialized and working (lines 252-260)
2. **Bright Data**: Referenced but never initialized (lines 587-613)

This suggests the code was migrated from Bright Data to PacketStream but the download logic wasn't fully updated.

---

*Found: October 7, 2025*  
*Tests Run: comprehensive_test_suite.py*  
*Status: Ready for fix*
