# Proxy Mode Simplification

## Summary

Simplified proxy control by removing redundant UI checkboxes and defaulting to automatic "smart" proxy mode.

## Problem

The Transcription tab had two confusing checkboxes:
1. **"Enable PacketStream proxy"** - Controls whether to use proxies
2. **"Disable proxies"** (in cookie section) - Controls whether to disable proxies when cookies are enabled

These were redundant and confusing because they controlled the same thing (proxy usage) from different angles.

## Solution

Removed both checkboxes and implemented automatic "smart" proxy mode:

**Default Behavior (Auto Mode):**
- When cookies are enabled → Proxies automatically disabled (home IP + cookies is most reliable)
- When cookies are NOT enabled → Proxies automatically enabled (if PacketStream configured)

This provides the best balance without requiring user configuration.

## Changes Made

### GUI (`transcription_tab.py`)

1. **Removed old controls:**
   - `self.use_proxy_checkbox` (Enable PacketStream proxy)
   - `self.disable_proxies_with_cookies_checkbox` (Disable proxies)

2. **No new UI control needed:**
   - Proxy mode is now automatic (hardcoded to "Auto")

3. **Updated logic:**
   - Proxy decision: `should_use_proxy = not cookies_enabled`
   - When cookies enabled → proxies disabled (home IP)
   - When cookies disabled → proxies enabled (if configured)
   - Strict mode enforcement updated
   - Settings save/load simplified (no proxy mode to save)

### Backend (`youtube_download.py`)

No changes needed - already correctly handles `disable_proxies_with_cookies` parameter.

### Config (`config.py`)

No changes needed - `disable_proxies_with_cookies` setting already exists.

## User Benefits

1. **Simpler interface** - No proxy controls needed, works automatically
2. **Smart defaults** - Auto mode handles all cases correctly
3. **Less confusion** - No need to understand proxy settings
4. **Best practice enforced** - Always uses optimal proxy strategy

## Testing

The changes preserve all existing functionality while simplifying the UI:

- ✅ Auto mode (hardcoded): Disables proxies with cookies, enables without
- ✅ Strict mode enforcement: Works correctly with auto mode
- ✅ Settings simplified: No proxy mode to save/load
- ✅ Backwards compatibility: YouTubeDownloadProcessor unchanged

## Migration

Users with existing settings will see:
- Old "use_youtube_proxy" setting ignored
- Proxy mode now automatic (no user control needed)
- Cookie files and other settings preserved
- Behavior: Same as old "Auto" mode (disable proxies when cookies enabled)
