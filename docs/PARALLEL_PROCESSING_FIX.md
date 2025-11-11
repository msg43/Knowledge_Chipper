# Parallel Processing Fix (November 3, 2025)

## Issue
When attempting to run summarization with parallel processing (`max_workers > 1`), the system would hang with "futures unfinished" errors and eventually timeout.

## Root Cause
The issue had two components:

### 1. Event Loop Conflict (FIXED ✅)
The `System2LLM` wrapper was trying to detect parent event loops from worker threads created by `ThreadPoolExecutor`. This caused:
- "asyncio.run() cannot be called from a running event loop" errors
- "Semaphore object is bound to a different event loop" errors
- Worker threads attempting to create nested event loops

### 2. Ollama Concurrency Limitation (MITIGATION ⚠️)
Ollama's local API has performance issues with concurrent requests for larger models:
- Requests taking 90+ seconds per segment
- Timeouts occurring at the HTTP client level
- Unable to process multiple segments in parallel efficiently

## Solution

### Event Loop Fix
Modified `src/knowledge_system/processors/hce/models/llm_system2.py` to detect worker threads and handle them differently:

```python
def complete(self, prompt: str, **kwargs) -> str:
    import threading
    
    # Worker threads can safely use asyncio.run() directly
    is_worker_thread = threading.current_thread() != threading.main_thread()
    
    if is_worker_thread:
        # Clean execution in worker thread - no parent loop detection
        return asyncio.run(self._complete_async(prompt, **kwargs))
    
    # Main thread logic with event loop detection...
```

**Key insight**: Worker threads from `ThreadPoolExecutor` should NOT try to detect parent event loops. They can safely create their own event loop with `asyncio.run()`.

### Ollama Timeout Adjustment
Reduced HTTP timeout from 300s (5 minutes) to 90s in `src/knowledge_system/core/llm_adapter.py`:
- Prevents extremely long hangs
- Allows faster failure and retry
- Still reasonable for 7B model inference

## Results

### ✅ Sequential Processing (max_workers=1)
- **Status**: Working perfectly
- **Performance**: ~2-3 minutes for 6 segments
- **Claims Extracted**: 4 claims, 2 people, 4 jargon terms
- **Recommendation**: Use for Ollama local models

### ⚠️ Parallel Processing (max_workers=2+)
- **Status**: Times out with Ollama
- **Issue**: Ollama cannot handle concurrent requests efficiently for qwen2.5:7b
- **Workaround**: Use sequential processing or use cloud APIs (OpenAI, Anthropic)
- **Future**: May work better with smaller models or with Ollama concurrency tuning

## Recommendations

1. **For Ollama users**: Set `max_workers=1` for reliable processing ✅ **NOW DEFAULT**
2. **For cloud API users**: Parallel processing should work fine (untested in this fix)
3. **For performance**: Consider using cloud APIs for parallel claim extraction

## Configuration

The summarization tab now defaults to `max_workers=1` for all processing. This is set in:
- `src/knowledge_system/gui/tabs/summarization_tab.py` (lines 1292, 1331)

```python
gui_settings = {
    # ... other settings ...
    "max_workers": 1,  # Sequential processing for Ollama reliability
}
```

This ensures reliable claim extraction with local Ollama models without requiring manual configuration.

## Files Modified

- `src/knowledge_system/processors/hce/models/llm_system2.py` - Fixed event loop detection for worker threads
- `src/knowledge_system/core/llm_adapter.py` - Reduced Ollama timeout from 300s to 90s
- `src/knowledge_system/gui/tabs/summarization_tab.py` - Set default max_workers=1 in GUI settings
- `src/knowledge_system/core/system2_orchestrator_mining.py` - Extract max_workers from gui_settings

## Testing

```bash
# Sequential (works) - NOW DEFAULT
max_workers=1: ✅ 4 claims extracted in ~5 minutes
  parallel=1 ✓
  Claims: 4
  People: 2
  Jargon: 4

# Parallel (timeouts)
max_workers=2+: ❌ Times out after ~9 minutes
  parallel=auto (calculated as 7 workers)
  All futures timeout
```

### Verification
The fix has been tested and confirmed working:
- GUI settings correctly pass `max_workers=1` to the pipeline
- Sequential processing completes successfully
- Claims are extracted reliably with Ollama

## Related Issues

- Original crash fix: `docs/SUMMARIZATION_CRASH_FIX.md`
- Schema alignment: Database segment loading improvements
