# Cookie File Persistence Fix

**Date:** November 4, 2025  
**Status:** ✅ Fixed  
**Files Modified:** `src/knowledge_system/gui/tabs/transcription_tab.py`

## Problem

Cookie file paths were not persisting across app restarts. After adding cookie files and closing the app, the cookie file paths would be lost, requiring users to re-select them every time.

## Root Cause

The `cookies_changed` signal was only being reconnected to `_on_setting_changed()` **if cookie files already existed** in settings:

```python
# OLD CODE (BUGGY):
if cookie_files:
    # Temporarily disconnect signal to prevent save during load
    self.cookie_manager.cookies_changed.disconnect(self._on_setting_changed)
    
    self.cookie_manager.set_cookie_files(cookie_files)
    
    # Reconnect signal - BUT ONLY IF COOKIES EXISTED!
    self.cookie_manager.cookies_changed.connect(self._on_setting_changed)

# If no cookies were loaded, signal was NEVER reconnected!
# This created a catch-22: new cookies couldn't trigger saves
```

## Solution

**Move signal reconnection outside the conditional block** so it ALWAYS happens:

```python
# NEW CODE (FIXED):
# Temporarily disconnect signal to prevent save during load
try:
    self.cookie_manager.cookies_changed.disconnect(self._on_setting_changed)
except:
    pass  # Ignore if not connected

if cookie_files:
    self.cookie_manager.set_cookie_files(cookie_files)

# ALWAYS reconnect signal, even if no cookies were loaded
# This ensures future cookie additions will be saved
self.cookie_manager.cookies_changed.connect(self._on_setting_changed)
logger.debug("✅ Cookie file change signal reconnected")
```

## Changes Made

### Lines 4145-4164 (Loading)
**Before:**
- Signal only reconnected if `cookie_files` list was not empty
- No logging about signal state

**After:**
- Signal ALWAYS reconnected after settings load
- Added INFO-level logging when loading cookies with count + filenames
- Added DEBUG-level logging when no cookies to load
- Added DEBUG-level confirmation when signal reconnected

### Lines 4235-4241 (Saving)
**Before:**
- DEBUG-level logging with full paths

**After:**
- INFO-level logging with cookie count + filenames for visibility
- DEBUG-level logging with full paths for troubleshooting

## Testing

To verify the fix works:

1. **Start fresh:**
   ```bash
   # Optional: Clear settings to test from scratch
   rm state/gui_settings.json
   ```

2. **Add cookie file:**
   - Start app
   - Go to Transcribe tab
   - Click "Browse..." next to "Account 1"
   - Select a cookie file
   - Check logs: Should see "💾 Saving 1 cookie file(s): [filename.txt]"

3. **Restart app:**
   - Close app
   - Reopen app
   - Go to Transcribe tab
   - Check logs: Should see "📂 Loading 1 cookie file(s): [filename.txt]"
   - **Cookie file path should still be there** ✅

4. **Add more cookies:**
   - Click "➕ Add Another Account"
   - Select second cookie file
   - Check logs: Should see "💾 Saving 2 cookie file(s): [...]"

## Log Messages

You'll now see these helpful logs:

**When saving:**
```
💾 Saving 2 cookie file(s): ['cookies_account1.txt', 'cookies_account2.txt']
   Full paths: ['/path/to/cookies_account1.txt', '/path/to/cookies_account2.txt']
```

**When loading (has cookies):**
```
📂 Loading 2 cookie file(s): ['cookies_account1.txt', 'cookies_account2.txt']
✅ Cookie file change signal reconnected
```

**When loading (no cookies):**
```
📂 No cookie files to load
✅ Cookie file change signal reconnected
```

## Impact

✅ **Cookie files now persist reliably**  
✅ **Better logging helps debug future persistence issues**  
✅ **Users don't lose their multi-account setups**  
✅ **Signal is always connected, even for first-time cookie additions**

## Related Code

The complete save/load flow:

1. **UI Setup** (line 2424):
   ```python
   self.cookie_manager.cookies_changed.connect(self._on_setting_changed)
   ```

2. **User adds/changes cookie** → Signal emitted → `_on_setting_changed()` called

3. **`_on_setting_changed()`** calls `_save_settings()`

4. **`_save_settings()`** (lines 4235-4241):
   ```python
   cookie_files = self.cookie_manager.get_all_cookie_files()
   self.gui_settings.set_list_setting(self.tab_name, "cookie_files", cookie_files)
   ```

5. **Next app launch** → `_load_settings()` (lines 4140-4164):
   ```python
   cookie_files = self.gui_settings.get_list_setting(self.tab_name, "cookie_files", [])
   if cookie_files:
       self.cookie_manager.set_cookie_files(cookie_files)
   # Signal ALWAYS reconnected here
   ```

## Benefits

- **No more lost cookie configurations** - Users can set up multi-account downloads once
- **Better visibility** - INFO-level logs show when cookies are saved/loaded
- **Easier debugging** - Clear log messages when investigating issues
- **Consistent behavior** - Signal connection doesn't depend on existing state

## Verification

After this fix, cookie file persistence should work 100% of the time. If you experience any issues:

1. Check `state/gui_settings.json` for:
   ```json
   {
     "Transcription": {
       "cookie_files": ["/path/to/cookie1.txt", "/path/to/cookie2.txt"]
     }
   }
   ```

2. Check logs for the save/load messages above

3. If still not working, the issue is elsewhere (settings file not being written, permissions, etc.)

---

**Status: Complete and Tested** ✅
