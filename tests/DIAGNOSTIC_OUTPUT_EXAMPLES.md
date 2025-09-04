# Enhanced Diagnostic Output Examples

This document shows examples of the comprehensive diagnostic information now available when timeouts or process issues occur in the testing system.

## Example 1: Transcription Timeout with System Analysis

```
2024-01-15 14:23:45 - INFO - Starting processing with 300s timeout for transcribe_only operation
2024-01-15 14:23:45 - INFO - Test file: /path/to/large_audio.mp3 (size: 150.2MB, duration: 45min)
2024-01-15 14:23:45 - INFO - Process command: whisper --model base --output-dir /output large_audio.mp3
2024-01-15 14:23:45 - INFO - Process context: {'model': 'base', 'device': 'auto', 'format': 'md'}

# ... Normal processing logs for 4+ minutes ...

2024-01-15 14:27:45 - INFO - Process Whisper-Transcription status at 240s: CPU: 25.3%, Memory: 850.2MB (peak: 1150.5MB)
2024-01-15 14:28:15 - WARNING - Processing appears stuck after 270.3s (no UI changes for 15 cycles)
2024-01-15 14:28:15 - INFO - Attempting graceful stop via stop button
2024-01-15 14:28:20 - WARNING - Attempting force stop of stuck processes
2024-01-15 14:28:20 - INFO - Attempting process cleanup via ProcessCleanup
2024-01-15 14:28:20 - WARNING - Force killing process: 12345 (whisper)

2024-01-15 14:28:23 - ERROR - === TIMEOUT ANALYSIS ===
2024-01-15 14:28:23 - ERROR - Test: /path/to/large_audio.mp3 -> transcribe_only
2024-01-15 14:28:23 - ERROR - Timeout: 300s
2024-01-15 14:28:23 - ERROR - File size: 150.2MB
2024-01-15 14:28:23 - ERROR - System: CPU=85.2%, Memory=78.5%, Disk=45.3%
2024-01-15 14:28:23 - ERROR - Active processes (1):
2024-01-15 14:28:23 - ERROR -   PID 12345: whisper (CPU: 2.1%, Memory: 850.2MB)
2024-01-15 14:28:23 - ERROR -     Command: whisper --model base --output-dir /output large_audio.mp3
2024-01-15 14:28:23 - ERROR - GUI buttons: 'Stop Transcription' (enabled), 'Clear Files' (enabled), 'Start Transcription' (disabled)
2024-01-15 14:28:23 - ERROR - Recent errors:
2024-01-15 14:28:23 - ERROR -   [Whisper] Processing segment 180/450...
2024-01-15 14:28:23 - ERROR -   [Whisper] Warning: Processing taking longer than expected

2024-01-15 14:28:23 - ERROR - === LIKELY CAUSES ===
2024-01-15 14:28:23 - ERROR - 🔥 HIGH CPU USAGE - System may be overloaded
2024-01-15 14:28:23 - ERROR - 🚫 1 processes with low CPU usage (possibly stuck)
2024-01-15 14:28:23 - ERROR - 📁 Large file (150.2MB) for transcription - may need longer timeout
2024-01-15 14:28:23 - ERROR - === END DIAGNOSIS ===
2024-01-15 14:28:23 - ERROR - === END TIMEOUT ANALYSIS ===

2024-01-15 14:28:25 - INFO - === Process Summary: Whisper-Transcription (timeout) ===
2024-01-15 14:28:25 - INFO - Runtime: 300.1s
2024-01-15 14:28:25 - INFO - Command: whisper --model base --output-dir /output large_audio.mp3
2024-01-15 14:28:25 - INFO - CPU Usage: avg=22.5%, max=45.2%
2024-01-15 14:28:25 - INFO - Memory: initial=125.5MB, peak=1150.5MB
2024-01-15 14:28:25 - INFO - Context: {'model': 'base', 'device': 'auto', 'format': 'md'}
2024-01-15 14:28:25 - INFO - === End Summary ===

2024-01-15 14:28:25 - WARNING - Test 'transcribe_large_audio' FAILED: Processing timed out after 300 seconds
```

## Example 2: Memory-Related Process Failure

```
2024-01-15 15:45:12 - INFO - Starting processing with 180s timeout for summarize_only operation
2024-01-15 15:45:12 - INFO - Process command: python -m knowledge_system summarize --model gpt-4 large_document.pdf

2024-01-15 15:47:30 - ERROR - === TIMEOUT ANALYSIS ===
2024-01-15 15:47:30 - ERROR - Test: /path/to/large_document.pdf -> summarize_only
2024-01-15 15:47:30 - ERROR - Timeout: 180s
2024-01-15 15:47:30 - ERROR - File size: 25.8MB
2024-01-15 15:47:30 - ERROR - System: CPU=45.1%, Memory=95.8%, Disk=32.1%
2024-01-15 15:47:30 - ERROR - Active processes (2):
2024-01-15 15:47:30 - ERROR -   PID 23456: python (CPU: 0.5%, Memory: 2150.3MB)
2024-01-15 15:47:30 - ERROR -     Command: python -m knowledge_system summarize --model gpt-4 large_document.pdf
2024-01-15 15:47:30 - ERROR - Recent errors:
2024-01-15 15:47:30 - ERROR -   MemoryError: Unable to allocate 1.5GB for array
2024-01-15 15:47:30 - ERROR -   Processing failed: Out of memory during document processing

2024-01-15 15:47:30 - ERROR - === LIKELY CAUSES ===
2024-01-15 15:47:30 - ERROR - 💾 HIGH MEMORY USAGE - System may be out of memory
2024-01-15 15:47:30 - ERROR - 💾 1 processes using >1GB memory
2024-01-15 15:47:30 - ERROR - 💾 Memory allocation errors detected
2024-01-15 15:47:30 - ERROR - === END DIAGNOSIS ===
```

## Example 3: GPU/CUDA Error Detection

```
2024-01-15 16:12:05 - INFO - Starting processing with 300s timeout for transcribe_only operation
2024-01-15 16:12:05 - INFO - Process command: whisper --model large --device cuda audio.mp3

2024-01-15 16:12:25 - ERROR - === TIMEOUT ANALYSIS ===
2024-01-15 16:12:25 - ERROR - Test: /path/to/audio.mp3 -> transcribe_only
2024-01-15 16:12:25 - ERROR - Timeout: 300s
2024-01-15 16:12:25 - ERROR - Recent errors:
2024-01-15 16:12:25 - ERROR -   RuntimeError: CUDA out of memory. Tried to allocate 2.50 GiB
2024-01-15 16:12:25 - ERROR -   torch.cuda.OutOfMemoryError: CUDA out of memory

2024-01-15 16:12:25 - ERROR - === LIKELY CAUSES ===
2024-01-15 16:12:25 - ERROR - 🖥️ GPU/CUDA related errors detected
2024-01-15 16:12:25 - ERROR - 💾 Memory allocation errors detected
2024-01-15 16:12:25 - ERROR - === END DIAGNOSIS ===
```

## Example 4: Successful Process with Monitoring

```
2024-01-15 17:30:15 - INFO - Starting processing with 60s timeout for transcribe_only operation (quick mode)
2024-01-15 17:30:15 - INFO - Process command: whisper --model tiny --device cpu short_audio.wav
2024-01-15 17:30:15 - INFO - Process context: {'model': 'tiny', 'device': 'cpu', 'format': 'md'}

2024-01-15 17:30:45 - INFO - Process Whisper-Transcription status at 30s: CPU: 45.2%, Memory: 85.3MB (peak: 95.1MB)

2024-01-15 17:31:05 - INFO - Processing completed - start button is ready again
2024-01-15 17:31:05 - INFO - Process Whisper-Transcription (PID: 34567) completed normally after 50.2s

2024-01-15 17:31:05 - INFO - === Process Summary: Whisper-Transcription (completed) ===
2024-01-15 17:31:05 - INFO - Runtime: 50.2s
2024-01-15 17:31:05 - INFO - Command: whisper --model tiny --device cpu short_audio.wav
2024-01-15 17:31:05 - INFO - CPU Usage: avg=42.1%, max=65.3%
2024-01-15 17:31:05 - INFO - Memory: initial=25.5MB, peak=95.1MB
2024-01-15 17:31:05 - INFO - Context: {'model': 'tiny', 'device': 'cpu', 'format': 'md'}
2024-01-15 17:31:05 - INFO - === End Summary ===

2024-01-15 17:31:05 - INFO - Test 'transcribe_short_audio' PASSED (50.2s)
```

## What This Diagnostic Data Tells You

### 🔍 **For Investigation & Debugging:**

1. **Root Cause Identification:**
   - System resource constraints (CPU/Memory/Disk)
   - Process behavior patterns (stuck vs. actively working)
   - Error message patterns and types
   - File size vs. operation appropriateness

2. **Performance Insights:**
   - CPU usage patterns over time
   - Memory consumption and peak usage
   - Process lifecycle from start to finish
   - Comparison between successful and failed runs

3. **Configuration Issues:**
   - Model size vs. available resources
   - Device selection (CPU vs. GPU vs. auto)
   - Timeout appropriateness for file sizes
   - Command line parameters and their effects

### 🛠️ **For Corrective Actions:**

#### **System-Level Fixes:**
```bash
# If high memory usage detected:
# - Close other applications
# - Increase swap space
# - Use smaller models (base → tiny)

# If high CPU usage detected:
# - Reduce concurrent processes
# - Use CPU instead of auto device selection
# - Process smaller chunks at a time
```

#### **Configuration Adjustments:**
```python
# Timeout adjustments based on file size
if file_size_mb > 100:
    timeout = 600  # 10 minutes for large files
elif file_size_mb > 50:
    timeout = 400  # 6.5 minutes for medium files
else:
    timeout = 180  # 3 minutes for small files

# Model selection based on available memory
available_memory_gb = psutil.virtual_memory().available / (1024**3)
if available_memory_gb < 4:
    model = "tiny"
elif available_memory_gb < 8:
    model = "base" 
else:
    model = "small"
```

#### **Process Management Improvements:**
```python
# Based on diagnostic data, you might:
# 1. Implement chunked processing for large files
# 2. Add memory monitoring and cleanup
# 3. Use different models based on system capabilities
# 4. Adjust timeouts dynamically based on file size
# 5. Implement retry logic with different parameters
```

### 📊 **Example Investigation Workflow:**

1. **Timeout Occurs** → Check diagnostic logs
2. **Identify Pattern** → Look for common error indicators
3. **System Analysis** → Review CPU/Memory/Disk usage
4. **Process Analysis** → Check if processes were stuck or actively working
5. **Error Context** → Review specific error messages
6. **Root Cause** → Combine all data points for diagnosis
7. **Fix Implementation** → Apply appropriate configuration changes
8. **Verification** → Re-run tests to confirm fix

This comprehensive diagnostic system gives you enough information to not just know that something failed, but to understand **why** it failed and **how** to fix it.
