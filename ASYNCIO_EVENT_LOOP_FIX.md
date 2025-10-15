# AsyncIO Event Loop Fix

## Problem

The system was crashing with an endless loop of errors:

```
ERROR | Structured JSON generation failed: asyncio.run() cannot be called from a running event loop
WARNING | Structured JSON generation failed, falling back: asyncio.run() cannot be called from a running event loop
ERROR | JSON generation failed: asyncio.run() cannot be called from a running event loop
WARNING | Unified mining failed for segment seg_0240: asyncio.run() cannot be called from a running event loop
```

## Root Cause

The issue occurred when the GUI's summarization tab called the System2 orchestrator's async `process_job()` method using `asyncio.run()`:

```python
# In src/knowledge_system/gui/tabs/summarization_tab.py:184
result = asyncio.run(orchestrator.process_job(job_id))
```

This created a running event loop. However, the `System2LLM` class (used by the unified miner) was also using `asyncio.run()` in its synchronous wrapper methods:

```python
# In src/knowledge_system/processors/hce/models/llm_system2.py
def complete(self, prompt: str, **kwargs) -> str:
    return asyncio.run(self._complete_async(prompt, **kwargs))
```

When `asyncio.run()` is called from within an already running event loop, Python raises a `RuntimeError` because you cannot nest event loops in this way.

## Solution

Modified the `System2LLM` class to detect if it's already running in an async context and handle it appropriately:

1. **Check for running loop**: Use `asyncio.get_running_loop()` to detect if we're in an async context
2. **If in async context**: Run the async function in a separate thread with its own event loop using `ThreadPoolExecutor`
3. **If not in async context**: Use `asyncio.run()` as before (safe for synchronous contexts)

### Code Changes

Updated three methods in `src/knowledge_system/processors/hce/models/llm_system2.py`:

1. `complete()` - Line 80-105
2. `generate_json()` - Line 133-156  
3. `generate_structured_json()` - Line 177-204

Each method now follows this pattern:

```python
def sync_method(self, ...):
    try:
        # Check if we're already in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context - run in separate thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run, 
                    self._async_method(...)
                )
                return future.result()
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            return asyncio.run(self._async_method(...))
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        raise
```

## Why This Works

- `asyncio.get_running_loop()` raises `RuntimeError` if no event loop is running
- When a loop IS running, we use `ThreadPoolExecutor` to run the async code in a separate thread with its own event loop
- When NO loop is running, we use `asyncio.run()` directly (the original behavior)
- This makes the code work correctly in both synchronous and asynchronous contexts

## Testing

The fix allows:
- GUI batch processing to work without event loop conflicts
- CLI commands to continue working as before (no running loop)
- System2 orchestrator to properly chain async operations
- Unified mining to process segments without errors

## Files Modified

- `src/knowledge_system/processors/hce/models/llm_system2.py` - Fixed event loop handling in sync wrapper methods

