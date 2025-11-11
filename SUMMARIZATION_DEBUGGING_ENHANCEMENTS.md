# Summarization Debugging Enhancements

**Date:** November 9, 2025  
**Issue:** Summarization hung at 35% and swallowed the failure without proper error reporting

## Problem Analysis

The summarization process was hanging at approximately 35% progress, which corresponds to the unified mining phase (between 30% "Extracting knowledge" and 55% "Knowledge extraction complete"). The system was not providing sufficient diagnostic information to identify where the hang occurred.

## Changes Made

### 1. Enhanced Progress Tracking in `unified_pipeline.py`

Added comprehensive logging and progress tracking for the mining phase:

- **Mining Configuration Logging**: Now logs the number of segments, max_workers, selectivity, and content_type at the start of mining
- **Per-Segment Progress Tracking**: Tracks each segment as it's processed with elapsed time and percentage complete
- **Dynamic Progress Updates**: Progress bar now updates from 30% to 55% based on actual segment completion
- **Mining Duration Tracking**: Logs total time taken for the mining phase
- **Output Validation**: Logs the number of segment outputs received after mining completes

### 2. Detailed Segment Processing in `unified_miner.py`

Added granular logging for individual segment mining:

- **Segment Start Logging**: Logs when mining starts for each segment with segment ID and timestamp range
- **LLM Request Tracking**: Logs when LLM request is sent for each segment
- **LLM Response Tracking**: Logs when response is received from LLM
- **Success Metrics**: Logs extraction counts (claims, jargon, people, concepts) for each successfully processed segment
- **Validation Warnings**: Logs when segment output fails validation
- **Enhanced Error Logging**: Changed warning to error level for mining failures and added full traceback in debug mode

### 3. Parallel Processing Visibility in `parallel_processor.py`

Added detailed tracking for parallel task execution:

- **Initial Batch Logging**: Logs when initial batch of tasks is submitted
- **Task Submission Tracking**: Logs each new task as it's submitted to the executor
- **Task Completion Tracking**: Logs each task completion with success/failure status
- **Periodic Status Updates**: Every 10 seconds, logs overall status including:
  - Completed count
  - Submitted count
  - Active tasks count
  - Current iteration number
- **Enhanced Error Reporting**: Added full traceback logging for failed tasks
- **Configuration Logging**: Logs whether asyncio or ThreadPoolExecutor is being used

## Diagnostic Information Now Available

When running summarization, you will now see:

1. **Mining Start**: Configuration details (segments, workers, selectivity)
2. **Parallel Processing**: Initial batch submission and mode (asyncio vs threads)
3. **Per-Segment Progress**: Each segment's start, LLM request, response, and completion
4. **Periodic Status**: Every 10 seconds, overall progress summary
5. **Error Details**: Full tracebacks for any failures at segment or task level
6. **Mining Completion**: Total duration and output validation

## Expected Log Output Pattern

```
INFO  | 🔧 Starting unified mining with 45 segments, max_workers=None, selectivity=moderate, content_type=transcript_own
INFO  | ⚡ Processing 45 items with 8 parallel workers (use_asyncio=True)
INFO  | 📤 Submitting initial batch of 8 tasks
INFO  | ✅ Initial batch submitted, waiting for completions...
DEBUG | 🔍 Starting mining for segment seg_0001 (00:00-02:30)
DEBUG | 📤 Sending LLM request for segment seg_0001
INFO  | 📥 Received LLM response for segment seg_0001
INFO  | ✅ Segment seg_0001 mining complete: 5 claims, 2 jargon, 1 people, 0 concepts
INFO  | ⛏️  Mining progress: 1/45 segments (2.2%) - 3.5s elapsed - Processed segment seg_0001
INFO  | 🔄 Status: 5/45 completed, 13/45 submitted, 8 active tasks, iteration 42
...
INFO  | ✅ Mining completed in 125.3s - received 45 segment outputs
INFO  | ✅ Extraction complete: 187 claims, 45 jargon terms, 23 people, 12 mental models
```

## Troubleshooting Guide

If the process hangs again:

1. **Check the last segment logged**: The segment ID will show which specific segment is causing issues
2. **Look for timeout warnings**: 60-second timeout per task will trigger "No futures completed" messages
3. **Monitor status updates**: If status updates stop appearing, the entire parallel processing is hung
4. **Check for error messages**: Any segment failures will now be logged at ERROR level with full tracebacks
5. **Verify LLM connectivity**: If you see "Sending LLM request" but no "Received LLM response", the LLM API is not responding

## Next Steps

If issues persist after these enhancements:

1. Review the specific segment content that causes hangs
2. Check LLM provider API status and rate limits
3. Consider reducing max_workers if seeing timeout issues
4. Examine memory pressure warnings if processing large batches
5. Verify network connectivity to LLM providers

## Files Modified

- `src/knowledge_system/processors/hce/unified_pipeline.py`
- `src/knowledge_system/processors/hce/unified_miner.py`
- `src/knowledge_system/processors/hce/parallel_processor.py`
