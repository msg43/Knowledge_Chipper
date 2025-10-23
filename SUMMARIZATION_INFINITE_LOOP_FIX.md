# Summarization Infinite Loop Fix

## Problem

The summarization process appeared to run infinitely without completing or providing feedback about what was happening.

## Root Cause

The `EnhancedSummarizationWorker` in `src/knowledge_system/gui/workers/processing_workers.py` was calling the deprecated `HCEAdapter.create_summarizer()` method, which raises `NotImplementedError` because `SummarizerProcessor` was removed in favor of `System2Orchestrator`.

**Old Code (Line 44)**:
```python
# Create processor with GUI settings via adapter
processor = hce_adapter.create_summarizer(  # ❌ This raises NotImplementedError!
    provider=self.gui_settings["provider"],
    model=self.gui_settings["model"],
    max_tokens=self.gui_settings["max_tokens"],
)
```

## Solution

### 1. Replaced Deprecated HCEAdapter with System2Orchestrator

**File**: `src/knowledge_system/gui/workers/processing_workers.py`

**Changes**:
- Removed call to deprecated `HCEAdapter.create_summarizer()`
- Replaced with direct use of `System2Orchestrator`
- Updated processing loop to use `orchestrator.process_transcript()`

**New Code**:
```python
from ...core.system2_orchestrator import System2Orchestrator

orchestrator = System2Orchestrator(
    provider=self.gui_settings["provider"],
    model=self.gui_settings["model"],
    max_tokens=self.gui_settings.get("max_tokens", 10000),
)

# Process file
result = orchestrator.process_transcript(
    file_path,
    progress_callback=progress_callback,
)
```

### 2. Added Comprehensive Logging

Added detailed logging at every step to diagnose future issues:

**Startup Logging**:
```
================================================================================
SUMMARIZATION WORKER STARTED
Files to process: 1
Provider: local
Model: qwen2.5:3b
================================================================================
```

**Per-File Logging**:
```
============================================================
Processing file 1/1: /path/to/file.md
============================================================
Step 3.1: Setting up progress callback for /path/to/file.md
Step 4.1: Calling orchestrator.process_transcript() for /path/to/file.md
Step 5.1: Processing complete. Success: True
✅ Successfully summarized: /path/to/file.md
Result keys: ['success', 'output_path', 'hce_data', ...]
Output written to: /path/to/output.md
```

**Progress Updates**:
```python
logger.debug(f"Progress update: {progress_obj.current_step} - {progress_obj.status}")
```

**Error Logging**:
```python
logger.error(f"❌ FATAL: Summarization worker error: {e}", exc_info=True)
logger.error(f"Error type: {type(e).__name__}")
logger.error(f"Error details: {str(e)}")
```

### 3. Fixed Result Handling

Updated to handle `System2Orchestrator` result format:

**Old**:
```python
if result.success:  # ❌ Assuming ProcessorResult object
    result.metadata.get("hce_data")
```

**New**:
```python
if result.get('success'):  # ✅ Dictionary result
    hce_data = result.get("hce_data") or result.get("metadata", {}).get("hce_data")
```

### 4. Improved Error Handling

- Added `exc_info=True` to log full stack traces
- Log error type and details separately
- Continue processing other files even if one fails
- Emit proper error signals to GUI

## What to Look For in Logs

When running summarization, you should now see:

### Normal Operation:
```
SUMMARIZATION WORKER STARTED
Step 1: Importing System2Orchestrator...
✅ System2Orchestrator imported successfully
Step 2: Creating System2Orchestrator with provider=local, model=qwen2.5:3b
✅ System2Orchestrator created successfully
Processing file 1/1: /path/to/transcript.md
Step 3.1: Setting up progress callback...
Step 4.1: Calling orchestrator.process_transcript()...
[Progress updates from System2Orchestrator]
Step 5.1: Processing complete. Success: True
✅ Successfully summarized: /path/to/transcript.md
Output written to: /path/to/output.md
ALL FILES PROCESSED
```

### If It Hangs:
Check the logs to see which step it stopped at:

1. **Stops after "SUMMARIZATION WORKER STARTED"** → Import error
2. **Stops after "Step 1"** → System2Orchestrator import failed
3. **Stops after "Step 2"** → Orchestrator creation failed
4. **Stops after "Step 4"** → `process_transcript()` is hanging
5. **No progress updates** → Progress callback not working

### If It Fails:
Look for error messages:
```
❌ Failed to summarize /path/to/file.md: [error message]
❌ Exception processing /path/to/file.md: [stack trace]
❌ FATAL: Summarization worker error: [stack trace]
```

## Testing

1. **Open the app**
2. **Go to Summarization tab**
3. **Select a transcript file**
4. **Click "Start Processing"**
5. **Watch the logs** (`logs/` directory or console output)

You should see detailed step-by-step logging showing exactly where the process is.

## Migration Notes

### For Other Components Using HCEAdapter

If you find other code using `HCEAdapter.create_summarizer()`, replace it with:

```python
# OLD (deprecated)
from knowledge_system.gui.adapters.hce_adapter import HCEAdapter
adapter = HCEAdapter()
processor = adapter.create_summarizer(provider=..., model=...)

# NEW (correct)
from knowledge_system.core.system2_orchestrator import System2Orchestrator
orchestrator = System2Orchestrator(provider=..., model=...)
result = orchestrator.process_transcript(file_path, progress_callback=...)
```

### Progress Callback Changes

**Old format** (HCEAdapter):
```python
def progress_callback(stage: str, percentage: int):
    # Simple string + number
    pass
```

**New format** (System2Orchestrator):
```python
def progress_callback(progress_obj: SummarizationProgress):
    # Full progress object with current_step, status, file_percent, etc.
    pass
```

## Related Files

- `src/knowledge_system/gui/workers/processing_workers.py` - Fixed worker
- `src/knowledge_system/gui/adapters/hce_adapter.py` - Deprecated adapter (shows error message)
- `src/knowledge_system/core/system2_orchestrator.py` - Correct orchestrator to use

## Prevention

To prevent similar issues in the future:

1. **Never catch and ignore exceptions** - Always log them
2. **Add logging at major steps** - Makes debugging 10x easier
3. **Check for deprecated methods** - Read error messages from NotImplementedError
4. **Use proper error propagation** - Don't silently fail
5. **Test after refactoring** - Especially when removing/replacing components

## Summary

**Before**: Infinite loop due to calling deprecated method that raises NotImplementedError  
**After**: Proper use of System2Orchestrator with comprehensive logging at every step

The summarization process should now complete successfully and provide detailed progress information throughout.

