# Cookie & Proxy Settings Wiring Fix

## Problem Summary

When using cookie authentication with the "Disable proxies with cookies" checkbox enabled in the GUI, YouTube downloads were still getting 403 Forbidden errors. The issue was that the GUI checkbox state was **not being passed through** to the actual download processor.

## Root Causes

### 1. Missing Parameter in Download Processor
The `YouTubeDownloadProcessor.__init__()` did not accept a `disable_proxies_with_cookies` parameter, so the GUI setting could never be passed through.

### 2. Hardcoded Config File Lookup
In `youtube_download.py` line 265, the code was:
```python
disable_proxies_check = yt_config.disable_proxies_with_cookies
```

This **always** read from the YAML config file, completely ignoring any GUI checkbox state.

### 3. Missing GUI Setting Pass-Through
The GUI collected the checkbox state but never added it to the `gui_settings` dictionary that gets passed to the worker thread.

### 4. Settings.yaml Missing Configuration
Your `config/settings.yaml` didn't have the `disable_proxies_with_cookies` setting, so it was using the default value from `config.py` (which is `True`), but this was never being respected because the GUI state wasn't being passed.

## Solution

### Changes Made

#### 1. Updated `YouTubeDownloadProcessor.__init__()` 
Added `disable_proxies_with_cookies` parameter:
```python
def __init__(
    self,
    name: str | None = None,
    output_format: str = "best",
    download_thumbnails: bool = True,
    enable_cookies: bool = False,
    cookie_file_path: str | None = None,
    disable_proxies_with_cookies: bool | None = None,  # NEW
) -> None:
    # ... store it as instance variable
    self.disable_proxies_with_cookies = disable_proxies_with_cookies
```

#### 2. Fixed Proxy Check Logic
Changed from always reading config file to checking instance variable first:
```python
# CRITICAL: Check instance variable first (from GUI), then fall back to config
disable_proxies_check = (
    self.disable_proxies_with_cookies
    if self.disable_proxies_with_cookies is not None
    else yt_config.disable_proxies_with_cookies
)
```

#### 3. Updated GUI to Pass Setting
Added to `transcription_tab.py` line ~2896:
```python
gui_settings["disable_proxies_with_cookies"] = self.disable_proxies_with_cookies_checkbox.isChecked()
```

#### 4. Updated All Instantiation Points
Updated every place that creates a `YouTubeDownloadProcessor` to pass the parameter:
- `transcription_tab.py` (single-account mode)
- `transcription_tab.py` (re-download mode)
- `transcription_tab.py` (multi-account mode via scheduler)
- `youtube_download_service.py`
- `download_scheduler.py`
- `multi_account_downloader.py`

## Testing Verification

To verify the fix is working, check the logs for these messages:

### Expected Log Output (Cookies + Disable Proxies)
```
🍪 Cookie configuration:
   enable_cookies: True
   cookie_files: ['/path/to/cookies.txt']
   use_multi_account: False
   disable_proxies_with_cookies: True

🏠 Cookies enabled - using direct connection (home IP) as configured
✅ Using cookies from file: /path/to/cookies.txt
🍪 Using cookies from throwaway account
```

### Expected Log Output (Cookies WITHOUT Disable Proxies)
```
🍪 Cookie configuration:
   enable_cookies: True
   cookie_files: ['/path/to/cookies.txt']
   use_multi_account: False
   disable_proxies_with_cookies: False

🌐 Using PacketStream residential proxies for YouTube processing
✅ Using cookies from file: /path/to/cookies.txt
```

## Why This Caused 403 Errors

When cookies are enabled but proxies are NOT disabled:
1. yt-dlp tries to use cookies through a proxy
2. The proxy may not properly forward cookie headers
3. YouTube sees an unauthenticated request and returns 403 Forbidden

When cookies are enabled AND proxies are disabled:
1. yt-dlp uses cookies directly from your home IP
2. YouTube sees a properly authenticated request
3. Download succeeds

## Files Modified

- `src/knowledge_system/processors/youtube_download.py`
- `src/knowledge_system/gui/tabs/transcription_tab.py`
- `src/knowledge_system/services/youtube_download_service.py`
- `src/knowledge_system/services/download_scheduler.py`
- `src/knowledge_system/services/multi_account_downloader.py`

## Configuration Recommendation

Add to your `config/settings.yaml`:
```yaml
youtube_processing:
  # ... existing settings ...
  
  # Cookie authentication settings
  enable_cookies: true
  cookie_file_path: "/path/to/your/cookies.txt"
  disable_proxies_with_cookies: true  # Use home IP when cookies are enabled
```

However, the GUI settings will now **override** these config file settings, which is the correct behavior.
