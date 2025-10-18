# GUI Freeze (Beachball) Fix When Stopping Transcription

## Problem
When clicking "Stop Processing" during transcription, the GUI would freeze (beachball on macOS) indefinitely. This happened because:

1. The worker thread was running a subprocess (whisper-cli)
2. When the thread was terminated, the subprocess continued running
3. The subprocess had blocking operations (like `time.sleep()`) that prevented clean termination
4. The GUI thread was waiting for the worker to stop, causing the freeze

## Root Cause
The whisper subprocess was not being terminated when the worker thread was stopped. The `QThread.terminate()` method only terminates the Python thread, not any subprocesses it spawned.

## Solution
Added proper subprocess management:

### 1. Track Subprocess Reference
In `WhisperCppTranscribeProcessor`:
- Added `self._current_subprocess` to track the running whisper process
- Store the subprocess when it starts
- Clear the reference when it completes

### 2. Add Subprocess Termination Method
Added `terminate_subprocess()` method that:
- Checks if a subprocess is running
- Sends SIGTERM for graceful shutdown
- Waits 0.5 seconds
- Sends SIGKILL if still running
- Cleans up the reference

### 3. Call Subprocess Termination Before Thread Termination
In the transcription tab's stop handler:
- Store reference to audio processor in worker
- Call `_terminate_subprocess()` before `worker.terminate()`
- This ensures the subprocess is killed before attempting to stop the thread

## Code Changes

### whisper_cpp_transcribe.py
1. Added subprocess tracking:
   ```python
   self._current_subprocess = None  # In __init__
   self._current_subprocess = process  # When starting
   self._current_subprocess = None  # When finished
   ```

2. Added termination method:
   ```python
   def terminate_subprocess(self):
       """Terminate any running subprocess."""
       if self._current_subprocess:
           self._current_subprocess.terminate()
           time.sleep(0.5)
           if self._current_subprocess.poll() is None:
               self._current_subprocess.kill()
   ```

### transcription_tab.py
1. Store processor reference in worker:
   ```python
   self.audio_processor = processor
   ```

2. Terminate subprocess before thread:
   ```python
   def _terminate_subprocess(self):
       """Attempt to terminate any running subprocess."""
       if hasattr(self.transcription_worker, 'audio_processor'):
           # ... navigate to transcriber and call terminate_subprocess()
   ```

## Result
Now when stopping transcription:
1. The whisper subprocess is terminated immediately
2. The worker thread can exit cleanly
3. The GUI remains responsive (no more beachball)
4. The stop operation completes quickly

The fix ensures that all system resources are properly cleaned up without blocking the GUI thread.
