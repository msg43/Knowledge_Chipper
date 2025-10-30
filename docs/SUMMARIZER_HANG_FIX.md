# Summarizer Hang and Validation Error Fixes

**Date**: 2025-10-30  
**Status**: ✅ Fixed

## Issues Identified

### Issue 1: Parallel Processing Hang
The summarizer would hang indefinitely after printing:
```
⚡ Processing 67 segments with 7 parallel workers
```

**Root Cause**: Nested event loop deadlock in `System2LLM` class.

**Details**:
1. `ParallelHCEProcessor` creates an asyncio event loop via `asyncio.run()`
2. Inside that loop, it calls synchronous `mine_segment()` function
3. `mine_segment()` calls synchronous `generate_structured_json()`
4. `generate_structured_json()` detected it was in an async context and tried to spawn a ThreadPoolExecutor and call `asyncio.run()` inside it
5. This created a nested `asyncio.run()` call which deadlocked

### Issue 2: Schema Validation Error
```
ERROR: 1 validation error for EvidenceSpan
context_type
  Input should be 'exact', 'extended' or 'segment' [type=literal_error, input_value='sentence', input_type=str]
```

**Root Cause**: Mismatch between prompt instructions and schema validation.

**Details**:
- The unified miner prompts instructed the LLM to use `context_type` values: `"sentence"` and `"paragraph"`
- The schema only accepted: `"exact"`, `"extended"`, `"segment"`
- LLM followed the prompt instructions, causing validation failures

## Fixes Applied

### Fix 1: Async/Sync Event Loop Handling

**File**: `src/knowledge_system/processors/hce/models/llm_system2.py`

**Changes**: Updated three methods (`complete()`, `generate_json()`, `generate_structured_json()`) to properly handle being called from within an async context.

**Before**:
```python
# Used ThreadPoolExecutor + asyncio.run() (causes deadlock)
with concurrent.futures.ThreadPoolExecutor() as pool:
    future = pool.submit(asyncio.run, self._complete_async(prompt, **kwargs))
    return future.result()
```

**After**:
```python
# Creates new thread with independent event loop
def run_in_new_loop():
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    try:
        result = new_loop.run_until_complete(
            self._complete_async(prompt, **kwargs)
        )
        result_container.append(result)
    finally:
        new_loop.close()
        asyncio.set_event_loop(None)

thread = threading.Thread(target=run_in_new_loop)
thread.start()
thread.join()
```

**Why This Works**:
- Creates a completely independent event loop in a separate thread
- No nested `asyncio.run()` calls
- Proper cleanup of event loop after completion
- Thread-safe result passing via containers

### Fix 2: Schema Validation Repair

**File**: `src/knowledge_system/processors/hce/schema_validator.py`

**Changes**: Added automatic repair logic to map invalid `context_type` values to valid ones.

```python
# Map common invalid values to valid ones
context_type_map = {
    "sentence": "exact",
    "paragraph": "extended",
    "full": "segment",
    "partial": "exact",
    "complete": "segment",
}
evidence["context_type"] = context_type_map.get(
    evidence["context_type"], "exact"
)
```

**Applied to**:
- Claims evidence spans
- Jargon evidence spans
- Mental models evidence spans

### Fix 3: Prompt Corrections

**Files**:
- `src/knowledge_system/processors/hce/prompts/unified_miner.txt`
- `src/knowledge_system/processors/hce/prompts/unified_miner_conservative.txt`
- `src/knowledge_system/processors/hce/prompts/unified_miner_liberal.txt`
- `src/knowledge_system/processors/hce/prompts/unified_miner_moderate.txt`

**Changes**: Updated all prompt files to use correct `context_type` values.

**Before**:
```
- **context_type**: "exact" (just quote), "sentence" (full sentence), or "paragraph" (full paragraph)
```

**After**:
```
- **context_type**: "exact" (just quote), "extended" (1-2 sentences), or "segment" (full segment)
```

Also updated all example JSON in prompts from `"context_type": "sentence"` to `"context_type": "extended"`.

## Testing

The fixes address both issues:

1. **Hang Fix**: The parallel processor will no longer deadlock when calling sync LLM methods from async context
2. **Validation Fix**: Even if the LLM generates invalid `context_type` values, they will be automatically repaired to valid ones

## Impact

- ✅ Parallel processing now works correctly without hanging
- ✅ Schema validation errors are automatically repaired
- ✅ Future LLM outputs will use correct `context_type` values (due to prompt fixes)
- ✅ Backward compatible - old data with invalid values will be auto-repaired

## Related Files

- `src/knowledge_system/processors/hce/models/llm_system2.py` - Async/sync handling
- `src/knowledge_system/processors/hce/schema_validator.py` - Validation repair
- `src/knowledge_system/processors/hce/prompts/*.txt` - Prompt corrections
- `src/knowledge_system/processors/hce/parallel_processor.py` - Parallel processing (no changes needed)
