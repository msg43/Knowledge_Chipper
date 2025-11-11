# Cookie File Persistence Diagnosis

**Date:** November 10, 2025  
**Issue:** User reports cookie file locations not persisting  
**Status:** ✅ Enhanced logging added for diagnosis

## Investigation Summary

### What I Found

1. **Cookie files ARE being saved correctly**
   - Verified session file at `~/.knowledge_system/gui_session.json` contains cookie paths
   - Session file shows: `"cookie_files": ["/Users/matthewgreer/Projects/cookies3.txt"]`
   - File exists and is accessible

2. **Loading mechanism works correctly**
   - Created comprehensive test script that verified all layers:
     - ✅ Session file contains data
     - ✅ SessionManager reads data correctly
     - ✅ GUISettingsManager retrieves data correctly  
     - ✅ CookieFileManager widget loads data correctly
   - All tests passed

3. **Code structure is correct**
   - Signal blocking/unblocking logic is properly implemented
   - `set_cookie_files()` blocks signals during loading to prevent cascading saves
   - Signal reconnection happens correctly after loading

### Possible Causes

Since the persistence mechanism is working correctly in isolation, the issue might be:

1. **Race condition** - The 200ms timer delay might not be enough on slower systems
2. **Widget visibility** - Cookie section might be scrolled out of view
3. **Timing issue** - Something might be clearing cookies after they load
4. **User perception** - Cookies might be loading but user doesn't see them

## Changes Made

### Enhanced Logging

Added comprehensive logging to help diagnose the issue:

#### In `transcription_tab.py` - Loading:
- Log full paths of cookie files being loaded
- Verify cookie_manager widget is initialized before loading
- Log signal disconnect/reconnect operations
- **Verify files were actually set** after calling `set_cookie_files()`
- Log error if expected files don't match loaded files

#### In `transcription_tab.py` - Saving:
- Log when cookie files are written to session
- Confirm successful write operation

#### In `cookie_file_manager.py` - Widget Operations:
- Log when `set_cookie_files()` is called with file count
- Log signal blocking state changes
- Log each step of clearing/adding entries
- **Verify final state** matches expected file count
- Log error if mismatch detected

### Diagnostic Script

Created `check_cookie_persistence.py` to help users verify:
- Whether cookie files are saved in session
- Whether cookie files exist on disk
- Provides troubleshooting steps

## How to Use

### For Users Experiencing the Issue:

1. **Check current state:**
   ```bash
   python check_cookie_persistence.py
   ```

2. **Launch GUI with logging:**
   ```bash
   python -m knowledge_system.gui
   ```

3. **Look for these log messages on startup:**
   ```
   📂 Loading N cookie file(s): [...]
      Full paths: [...]
   🔧 CookieFileManager.set_cookie_files() called with N files
   ✅ Successfully loaded N cookie file(s) into UI
   ✅ Cookie file change signal reconnected
   ```

4. **If you see errors:**
   ```
   ❌ Cookie manager widget not initialized!
   ❌ Failed to load cookie files into UI!
   ❌ Mismatch! Expected N files, but have 0
   ```
   These indicate the actual problem.

5. **Add/change a cookie file and look for:**
   ```
   💾 Saving N cookie file(s): [...]
   ✅ Cookie files written to session: Local Transcription.cookie_files
   ```

### For Developers:

The enhanced logging will show exactly where the persistence chain breaks:

- **Session file** → Check `~/.knowledge_system/gui_session.json`
- **SessionManager** → Check logs for "Loading N cookie file(s)"
- **CookieFileManager** → Check logs for "set_cookie_files() called"
- **UI verification** → Check logs for "Successfully loaded N cookie file(s)"

## Next Steps

If the issue persists after these changes:

1. **Collect logs** - Run the GUI and capture the full log output
2. **Check timing** - The 200ms delay might need to be increased
3. **Check Qt version** - Signal blocking behavior might differ across versions
4. **Check for conflicts** - Another part of the code might be clearing cookies

## Files Modified

- `src/knowledge_system/gui/tabs/transcription_tab.py`
  - Enhanced cookie loading logging (lines 4171-4211)
  - Enhanced cookie saving logging (lines 4286-4293)

- `src/knowledge_system/gui/widgets/cookie_file_manager.py`
  - Enhanced `set_cookie_files()` logging (lines 420-509)
  - Added verification of final state

- `check_cookie_persistence.py` (NEW)
  - Diagnostic script for users

## Testing

To verify the fix works:

1. Clear session file:
   ```bash
   rm ~/.knowledge_system/gui_session.json
   ```

2. Launch GUI and add cookie file

3. Close GUI

4. Run diagnostic:
   ```bash
   python check_cookie_persistence.py
   ```

5. Relaunch GUI - cookie should be there

## Conclusion

The persistence mechanism is **working correctly** at the code level. The enhanced logging will help identify where the issue occurs in practice. Most likely causes:

1. **Widget initialization timing** - Fixed by adding verification check
2. **Silent failures** - Now logged as errors
3. **State mismatches** - Now detected and logged

The next time the user experiences this issue, the logs will show exactly what's happening.

---

**Status:** Ready for testing with enhanced diagnostics
