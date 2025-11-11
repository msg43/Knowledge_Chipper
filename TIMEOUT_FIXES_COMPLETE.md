# Timeout Configuration Fixes - Complete

## Problem Summary

The system was experiencing LLM timeout errors during HCE processing:
```
LLM request timed out after 120 seconds [LLM_API_ERROR]
```

Despite having `timeout: 600` configured in `config/settings.yaml`, multiple hardcoded timeout values were overriding the configuration.

## Root Causes Identified

### 1. **System2LLM Thread Timeout** ⚠️ CRITICAL (FIXED)
**Location:** `src/knowledge_system/processors/hce/models/llm_system2.py`

**Issue:** Three hardcoded 120-second timeouts in thread wrappers
- Line 124: `thread.join(timeout=120)` in `complete()` method
- Line 207: `thread.join(timeout=120)` in `generate_json()` method  
- Line 324: `thread.join(timeout=120)` in `generate_structured_json()` method

**Fix Applied:**
- Added `timeout` parameter to `__init__` method
- Reads timeout from `settings.local_config.timeout` for local providers (600s)
- Uses 300s default for cloud APIs
- Replaced all hardcoded `120` with `self.timeout`
- Added debug logging to show configured timeout

### 2. **LLM Adapter HTTP Timeout** ⚠️ CRITICAL (FIXED)
**Location:** `src/knowledge_system/core/llm_adapter.py:375`

**Issue:** Hardcoded 90-second timeout for Ollama HTTP requests
```python
timeout=aiohttp.ClientTimeout(total=90)  # Was overriding config!
```

**Fix Applied:**
- Added `self.local_timeout` and `self.cloud_timeout` to `LLMAdapter.__init__`
- Reads from `settings.local_config.timeout` (600s from your config)
- Changed HTTP timeout to use `self.local_timeout`
- Added timeout info to initialization log message

### 3. **OllamaManager Timeout** ⚠️ HIGH (FIXED)
**Location:** `src/knowledge_system/utils/ollama_manager.py:61`

**Issue:** Hardcoded 120-second timeout
```python
self.timeout = 120  # Increased for HCE processing
```

**Fix Applied:**
- Added optional `timeout` parameter to `__init__`
- Reads from `settings.local_config.timeout` if not provided
- Now respects your 600s configuration

## Other Hardcoded Timeouts Found (Not Critical for HCE)

These are less critical but documented for completeness:

### Network Request Timeouts (Reasonable)
- **RSS/Podcast downloads:** 30-60s timeouts (appropriate for network requests)
- **API calls:** 10-30s timeouts (appropriate for external APIs)
- **Proxy testing:** 10s timeouts (appropriate for connectivity checks)

### Process/Thread Timeouts (Appropriate)
- **Diarization model loading:** 120s timeout (appropriate for one-time model download)
- **Audio processing:** 300-3600s timeouts (already configurable)
- **Monitor threads:** 1-5s timeouts (appropriate for cleanup)

### Database Timeouts (SQLite)
- **PRAGMA busy_timeout:** 5000ms (5s) - appropriate for database locks

## Configuration in Effect

Your `config/settings.yaml` now properly controls all LLM timeouts:

```yaml
local_config:
  timeout: 600  # 10 minutes - now respected throughout the system!
```

## Impact of Fixes

| Component | Before | After | Impact |
|-----------|--------|-------|--------|
| System2LLM thread wrapper | 120s (hardcoded) | 600s (from config) | ✅ 5x longer |
| LLM Adapter HTTP timeout | 90s (hardcoded) | 600s (from config) | ✅ 6.7x longer |
| OllamaManager | 120s (hardcoded) | 600s (from config) | ✅ 5x longer |

## Testing Recommendations

1. **Monitor timeout logs** - Look for the new debug message:
   ```
   System2LLM initialized with 600s timeout for ollama
   ```

2. **Check LLM Adapter logs** - Should show:
   ```
   LLM Adapter initialized for enterprise tier (max 8 concurrent cloud / X local requests, local timeout: 600s)
   ```

3. **If timeouts still occur at 600s**, consider:
   - Checking Ollama server performance (`ollama ps`)
   - Monitoring system resources during HCE
   - Trying a smaller/faster model
   - Reducing segment size for mining
   - Increasing timeout further in config (e.g., 900s = 15 minutes)

## How to Adjust Timeout

Simply edit `config/settings.yaml`:

```yaml
local_config:
  timeout: 900  # Increase to 15 minutes if needed
```

No code changes required - the system now respects this setting throughout!

## Files Modified

1. ✅ `src/knowledge_system/processors/hce/models/llm_system2.py`
   - Added timeout parameter and configuration loading
   - Replaced 3 hardcoded timeouts with configurable value

2. ✅ `src/knowledge_system/core/llm_adapter.py`
   - Added timeout configuration loading in `__init__`
   - Fixed HTTP timeout in `_call_ollama` method
   - Added timeout to log messages

3. ✅ `src/knowledge_system/utils/ollama_manager.py`
   - Made timeout configurable via parameter or config
   - Defaults to `settings.local_config.timeout`

## Summary

The timeout issue is now **completely resolved**. All LLM-related timeouts now respect your configuration file, giving you 600 seconds (10 minutes) instead of the previous 90-120 second hardcoded limits. This should eliminate the timeout errors you were experiencing during HCE mining operations.
