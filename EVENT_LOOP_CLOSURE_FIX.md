# Event Loop Closure Fix - Async Client Cleanup

## Issue
Summarization was failing with `RuntimeError: Event loop is closed` errors during async HTTP client cleanup:

```
RuntimeError: Event loop is closed
Task exception was never retrieved
future: <Task finished name='Task-205' coro=<AsyncClient.aclose() done...> exception=RuntimeError('Event loop is closed')>
```

## Root Cause
The problem occurred in the `LLMAdapter` class when using OpenAI and Anthropic async clients:

1. `AsyncOpenAI` and `AsyncAnthropic` clients were created without async context managers
2. When `asyncio.run()` completed in a ThreadPoolExecutor (from the previous event loop fix), it closed the event loop
3. The async clients' `__del__` methods tried to schedule cleanup tasks on the closed event loop
4. This caused the `RuntimeError: Event loop is closed` exception

### Example of the Problem
```python
# In llm_adapter.py line 374 (OLD CODE)
async def _call_openai(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
    # Create async client
    client = AsyncOpenAI(api_key=api_key)  # No context manager!
    
    # Make API call
    response = await client.chat.completions.create(...)
    
    # Return response
    # Client is NOT explicitly closed - cleanup happens in __del__
    # If event loop closes before __del__ runs, we get RuntimeError
```

## Solution
Use async context managers (`async with`) for all async HTTP clients to ensure proper cleanup **before** the event loop closes.

### Changes Made

**File:** `src/knowledge_system/core/llm_adapter.py`

#### 1. OpenAI Client (Line 373-396)
```python
# OLD: Client created without context manager
client = AsyncOpenAI(api_key=api_key)
response = await client.chat.completions.create(...)

# NEW: Client properly managed with async context manager
async with AsyncOpenAI(api_key=api_key) as client:
    response = await client.chat.completions.create(...)
    # Client automatically closed when exiting context
```

#### 2. Anthropic Client (Line 428-456)
```python
# OLD: Client created without context manager
client = AsyncAnthropic(api_key=api_key)
response = await client.messages.create(...)

# NEW: Client properly managed with async context manager  
async with AsyncAnthropic(api_key=api_key) as client:
    response = await client.messages.create(...)
    # Client automatically closed when exiting context
```

## Why This Fixes the Issue

1. **Explicit cleanup**: The `async with` statement ensures the client's `aclose()` method is called **while the event loop is still running**
2. **No deferred cleanup**: Without context managers, cleanup happens in `__del__`, which may run after the event loop closes
3. **Proper resource management**: Context managers guarantee cleanup even if exceptions occur

## Related Issues

This fix complements the earlier fix in `ASYNCIO_EVENT_LOOP_FIX.md`, which addressed:
- Running async code from sync contexts using ThreadPoolExecutor
- Preventing nested `asyncio.run()` calls

Together, these fixes ensure:
- ✅ Async code can run from GUI threads (via ThreadPoolExecutor)
- ✅ Event loops are properly managed (via asyncio.run in separate thread)
- ✅ HTTP clients are properly cleaned up (via async context managers)
- ✅ No "Event loop is closed" errors

## Testing

To verify the fix:
1. Run summarization from the GUI
2. Monitor logs for the absence of "Event loop is closed" errors
3. Verify summarization completes successfully
4. Check that no async cleanup tasks remain after completion

## Impact

**Before the fix:**
- Summarization would work but spam errors in logs
- Potential resource leaks from unclosed HTTP connections
- Event loop closure errors during async client cleanup

**After the fix:**
- Clean summarization execution with no event loop errors
- Proper cleanup of HTTP clients and connections
- No resource leaks or orphaned async tasks

## Files Modified
- `src/knowledge_system/core/llm_adapter.py`
  - Line 373-396: Fixed OpenAI client cleanup
  - Line 428-456: Fixed Anthropic client cleanup

