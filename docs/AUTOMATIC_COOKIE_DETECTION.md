# Automatic Cookie Detection

**Date:** November 2, 2025  
**Status:** ✅ Complete  
**Impact:** Simplified UX - removed redundant checkbox

## Problem

The Transcription tab had an "Enable multi-account" checkbox that was redundant. The system already automatically detected multi-account mode based on the number of cookie files provided.

**User Question:**
> "Do we really need the enable multi account checkbox in the transcribe tab? If the user uses one cookies file then they use one cookie file. If they use multiple cookie files, then we are enabling multi user account, right?"

**Answer:** Absolutely correct! The checkbox was unnecessary.

## Solution

Removed the "Enable multi-account" checkbox and made cookie authentication automatic:

### Automatic Detection Logic

```python
# Cookie authentication is automatically enabled when cookie files are present
cookie_files = self.cookie_manager.get_all_cookie_files()
cookies_enabled = len(cookie_files) > 0
use_multi_account = len(cookie_files) > 1
```

### Behavior

| Cookie Files | Cookie Auth | Multi-Account | Proxy Mode (Auto) |
|-------------|-------------|---------------|-------------------|
| 0 files     | ❌ Disabled  | ❌ Disabled    | ✅ Enabled        |
| 1 file      | ✅ Enabled   | ❌ Single      | ❌ Disabled       |
| 2+ files    | ✅ Enabled   | ✅ Multi       | ❌ Disabled       |

## Changes Made

### 1. Removed UI Checkbox
**File:** `src/knowledge_system/gui/tabs/transcription_tab.py`

**Before:**
```python
# Enable multi-account checkbox
self.enable_cookies_checkbox = QCheckBox("Enable multi-account")
self.enable_cookies_checkbox.setChecked(True)
cookie_layout.addWidget(self.enable_cookies_checkbox)

# Multi-account cookie manager widget
self.cookie_manager = CookieFileManager()
self.cookie_manager.setEnabled(False)  # Disabled by default
self.enable_cookies_checkbox.toggled.connect(self._on_cookies_toggled)
```

**After:**
```python
# Multi-account cookie manager widget
# Cookie authentication is automatically enabled when cookie files are provided
# Multi-account mode is automatically enabled when multiple cookie files are provided
self.cookie_manager = CookieFileManager()
# Always enabled - no toggle needed
```

### 2. Automatic Cookie Detection
**File:** `src/knowledge_system/gui/tabs/transcription_tab.py`

**Before:**
```python
# Determine if we should use proxies based on mode and cookie state
cookies_enabled = self.enable_cookies_checkbox.isChecked()
```

**After:**
```python
# Determine if we should use proxies based on mode and cookie state
# Cookies are automatically enabled when cookie files are present
cookie_files = self.cookie_manager.get_all_cookie_files()
cookies_enabled = len(cookie_files) > 0
```

### 3. Simplified Settings Persistence

**Before:**
```python
# Save cookie authentication settings (multi-account support)
self.gui_settings.set_checkbox_state(
    self.tab_name,
    "enable_cookies",
    self.enable_cookies_checkbox.isChecked(),
)
# Save cookie files list
gui_settings["cookie_files"] = self.cookie_manager.get_all_cookie_files()
```

**After:**
```python
# Save cookie files list (cookie auth is automatically enabled when files are present)
cookie_files = self.cookie_manager.get_all_cookie_files()
gui_settings["cookie_files"] = cookie_files
```

### 4. Simplified Validation

**Before:**
```python
def _validate_cookie_settings(self) -> bool:
    # Check if cookies are enabled but no files are selected
    if self.enable_cookies_checkbox.isChecked():
        cookie_files = self.cookie_manager.get_all_cookie_files()
        if not cookie_files:
            # Show warning about no cookies selected
            # ... 30+ lines of dialog code ...
```

**After:**
```python
def _validate_cookie_settings(self) -> bool:
    # Check if cookie files are provided and validate them
    cookie_files = self.cookie_manager.get_all_cookie_files()
    if cookie_files:
        # Verify they exist
        missing_files = [f for f in cookie_files if not Path(f).exists()]
        if missing_files:
            self.show_warning(...)
            return False
    return True
```

### 5. Removed Toggle Method

Removed the `_on_cookies_toggled()` method entirely - no longer needed.

## Benefits

### 1. **Simpler UX**
- One less checkbox to understand
- Behavior is intuitive: add cookie files → cookies are used
- No confusion about "enabling" vs "providing" cookies

### 2. **Cleaner Code**
- Removed ~50 lines of checkbox handling code
- Removed redundant validation logic
- Simplified settings persistence

### 3. **More Intuitive**
- Users don't need to understand the difference between "having cookie files" and "enabling cookies"
- Multi-account mode is automatically detected
- Proxy mode "Auto" works as expected

### 4. **Fewer Edge Cases**
- Can't have "cookies enabled but no files"
- Can't have "cookies disabled but files present"
- State is always consistent

## User Experience

### Before
1. Add cookie files
2. Check "Enable multi-account" checkbox
3. Configure proxy mode
4. Start download

### After
1. Add cookie files (done! cookies automatically enabled)
2. Configure proxy mode (optional - Auto mode works intelligently)
3. Start download

## Backwards Compatibility

✅ **Fully backwards compatible**

- Old settings with `enable_cookies` checkbox state are ignored
- Cookie files from old sessions are loaded correctly
- Download logic works identically (just detects cookies automatically)

## Testing

### Manual Testing Checklist

- [ ] Add 0 cookie files → proxies enabled (Auto mode)
- [ ] Add 1 cookie file → single-account mode, proxies disabled (Auto mode)
- [ ] Add 2+ cookie files → multi-account mode, proxies disabled (Auto mode)
- [ ] Remove cookie files → reverts to no cookies
- [ ] Cookie files persist across sessions
- [ ] Validation works for missing cookie files
- [ ] Proxy mode "Always" overrides cookie detection
- [ ] Proxy mode "Never" works with cookies

## Related Files

- `src/knowledge_system/gui/tabs/transcription_tab.py` - Main changes
- `src/knowledge_system/gui/widgets/cookie_file_manager.py` - Cookie file widget (unchanged)
- `MANIFEST.md` - Updated with this change

## Documentation

- This file: `docs/AUTOMATIC_COOKIE_DETECTION.md`
- MANIFEST.md entry: "Automatic Cookie Detection (November 2, 2025)"

## Conclusion

The "Enable multi-account" checkbox was redundant. Cookie authentication is now automatically enabled when cookie files are present, and multi-account mode is automatically enabled when multiple files are present. This simplifies the UX and reduces code complexity while maintaining all functionality.
