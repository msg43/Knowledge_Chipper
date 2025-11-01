# Cookie Files Persistence Fix

**Date:** October 31, 2025  
**Issue:** Cookie file locations not persisting between sessions  
**Status:** ✅ FIXED

## Problem

Cookie file paths were not being saved/restored correctly between app sessions. Users had to re-select their cookie files every time they launched the app.

## Root Cause

The `CookieFileManager` widget emits `cookies_changed` signal whenever:
1. Cookie entries are added/removed
2. File input text changes

During settings load, `set_cookie_files()` triggers these signals multiple times:
- Removes existing entries → emits signal
- Sets text on inputs → emits signal  
- Adds new entries → emits signal

Even though the cookie_manager widget was in the `widgets_to_block` list (line 3898), the signal blocking wasn't preventing the internal emissions from child widgets.

## Solution Implemented

**Added explicit signal disconnect/reconnect during settings load** (lines 4037-4046):

```python
# Load cookie files list
cookie_files = self.gui_settings.get_list_setting(
    self.tab_name, "cookie_files", []
)

logger.debug(f"📂 Loaded cookie files: {cookie_files}")
if cookie_files:
    # Temporarily disconnect signal to prevent save during load
    try:
        self.cookie_manager.cookies_changed.disconnect(self._on_setting_changed)
    except:
        pass  # Ignore if not connected
    
    self.cookie_manager.set_cookie_files(cookie_files)
    
    # Reconnect signal
    self.cookie_manager.cookies_changed.connect(self._on_setting_changed)
```

**Added debug logging for save operation** (line 4133):
```python
cookie_files = self.cookie_manager.get_all_cookie_files()
logger.debug(f"💾 Saving cookie files: {cookie_files}")
```

## How It Works Now

1. **On App Launch:**
   - Settings manager loads cookie files from persistent storage
   - Signal is temporarily disconnected
   - Cookie manager is populated with saved paths
   - Signal is reconnected
   - No spurious saves triggered

2. **When User Changes Cookies:**
   - User adds/removes/browses for cookie files
   - `cookies_changed` signal fires
   - `_on_setting_changed()` is called
   - Settings are saved immediately

3. **On App Close:**
   - Final save happens
   - Cookie files persist to storage

## Testing

1. **Add cookie files:**
   - Go to Transcription tab
   - Enable cookies
   - Add 1-6 cookie file paths
   - Close app

2. **Verify persistence:**
   - Relaunch app
   - Go to Transcription tab
   - Cookie file paths should be restored
   - Check logs for: `📂 Loaded cookie files: [...]`

3. **Verify saves work:**
   - Change a cookie file path
   - Check logs for: `💾 Saving cookie files: [...]`

## Files Modified

- `src/knowledge_system/gui/tabs/transcription_tab.py`
  - Lines 4037-4046: Added signal disconnect/reconnect during load
  - Line 4133: Added debug logging for save

## Related Issues

This fix also ensures that the cookie manager's internal state stays consistent with the saved settings, preventing edge cases where:
- Empty cookie list overwrites saved paths
- Duplicate saves during initialization
- Race conditions between load and auto-save

## Verification

Run the app and check logs:
```bash
# Should see on launch:
📂 Loaded cookie files: ['/path/to/cookie1.txt', '/path/to/cookie2.txt']

# Should see when changing cookies:
💾 Saving cookie files: ['/path/to/cookie1.txt', '/path/to/cookie2.txt', '/path/to/cookie3.txt']
```

If cookie files are not persisting, check:
1. Are the log messages appearing?
2. Is the settings file writable?
3. Are there any errors in the logs?

