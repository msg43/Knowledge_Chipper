# Division by Zero Fix - Whisper Transcription

## Problem

Transcription was failing with the following errors:
```
ERROR | Error reading stdout: float division by zero
ERROR | Whisper.cpp subprocess error: Command died with <Signals.SIGPIPE: 13>
```

## Root Cause

In `src/knowledge_system/processors/whisper_cpp_transcribe.py`, the `_parse_whisper_output_for_progress()` method was calculating realtime speed and attempting to divide by zero:

```python
realtime_speed = audio_processed_seconds / elapsed_time
if realtime_speed >= 1.0:
    speed_info = f" ({realtime_speed:.1f}x Realtime)"
else:
    speed_info = f" ({1/realtime_speed:.1f}x slower than realtime)"  # ❌ Division by zero!
```

This occurred when:
1. `whisper_progress` was 0% (at the very start)
2. `audio_processed_seconds = audio_duration * 0 = 0`
3. `realtime_speed = 0 / elapsed_time = 0`
4. Code tried to compute `1/realtime_speed = 1/0` → **ZeroDivisionError**

The exception in the stream reading thread caused it to exit prematurely, which led to:
- whisper-cli process continuing to write to stdout/stderr
- No process reading from the pipes
- OS sending SIGPIPE signal to whisper-cli
- Complete transcription failure

## Solution

### Fix 1: Add Zero Check Before Division

Changed the condition from:
```python
else:
    speed_info = f" ({1/realtime_speed:.1f}x slower than realtime)"
```

To:
```python
elif realtime_speed > 0:
    speed_info = f" ({1/realtime_speed:.1f}x slower than realtime)"
```

This prevents division by zero by only calculating the inverse speed when `realtime_speed > 0`.

**Applied in two locations:**
- Line 1637: Percentage-based progress parsing
- Line 1673: Timestamp-based progress parsing

### Fix 2: Wrap Progress Parsing in Try-Except

Added defensive error handling around progress parsing to prevent ANY error from killing the reading thread:

```python
if self.progress_callback and line_stripped:
    try:
        elapsed = time.time() - start_time
        self._parse_whisper_output_for_progress(line_stripped, elapsed)
    except Exception:
        pass  # Don't let progress parsing errors interrupt streaming
```

This ensures that even if an unexpected error occurs during progress parsing, the stream reading continues and SIGPIPE is avoided.

## Files Modified

- `src/knowledge_system/processors/whisper_cpp_transcribe.py`
  - Lines 1637-1640: Added `elif realtime_speed > 0` check
  - Lines 1673-1676: Added `elif realtime_speed > 0` check  
  - Lines 1458-1464: Wrapped progress parsing in try-except

## Testing

Test script created: `scripts/test_division_by_zero_fix.sh`

To verify the fix:
1. Run a transcription through the GUI
2. Monitor logs for absence of "float division by zero" errors
3. Confirm transcription completes successfully without SIGPIPE

## Impact

- **Before**: Transcriptions would fail immediately with division by zero and SIGPIPE errors
- **After**: Progress parsing handles edge cases gracefully, transcriptions proceed normally

## Related Issues

This fix also improves resilience against other potential progress parsing errors by ensuring the stream reading thread continues operating regardless of parsing failures.
