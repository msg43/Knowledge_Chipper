# Whisper-cli Transcription Fix Summary

## Problem Identified
The transcription was getting stuck at 80% because:
1. We added an invalid `-v` flag that doesn't exist in whisper-cli
2. Whisper-cli exited immediately with error code showing help text
3. The error was reported as "No output generated" even though it did produce help text (to stderr)

## Fix Applied
1. **Removed the invalid `-v` flag**
2. **Added `--print-progress` flag** which is the correct way to get progress output from whisper-cli
3. **Enhanced progress parsing** to handle whisper.cpp's actual progress format (e.g., "progress = 10%")
4. **Improved logging** to show all whisper output for debugging

## Key Changes Made

### Command Line Fix
```diff
- cmd.append("-v")  # REMOVED - invalid flag
+ "--print-progress",  # Added to output-json command extension
```

### Progress Parsing Enhancement
- Now parses "progress = X%" format from whisper output
- Maps whisper's 0-100% progress to our 50-80% UI range
- Falls back to time-based estimation if no progress output

### Debugging Improvements
- Changed from buffered to unbuffered I/O for real-time output
- All whisper stdout/stderr is logged with INFO level
- Process PID is logged when started
- Periodic "no output" status logged every 30 seconds

## Expected Behavior Now
1. Whisper-cli should start successfully without the invalid flag
2. Progress output should be visible in logs: `[whisper.cpp stderr] progress = X%`
3. The progress bar should update smoothly from 50% to 80% during transcription
4. JSON output file should be created upon completion

## Testing
Run a transcription and watch for:
- No more "unknown argument: -v" error
- Progress updates in the logs
- Successful completion with transcribed text
