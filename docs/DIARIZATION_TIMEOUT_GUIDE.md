# Diarization Timeout Guide

## When to Give Up

### Expected Processing Times

**On MPS (Apple Silicon):**
- 5-minute audio: ~6-8 seconds
- 22-minute audio: ~30-40 seconds
- 60-minute audio: ~90 seconds

**On CPU:**
- 5-minute audio: ~200+ seconds
- 22-minute audio: ~800+ seconds (13+ minutes)
- 60-minute audio: ~2000+ seconds (33+ minutes)

## Current Timeout: 5 Minutes (300 seconds)

If you're stuck at 80% for 300 seconds, something is wrong:

1. **The timeout mechanism may have failed**
2. **MPS encountered an unexpected operation**
3. **The process is deadlocked**

## What to Do

### Immediate Action:
1. **Kill the process**: Press `Ctrl+C` or close terminal
2. **Don't wait longer** - 300 seconds is already too long for MPS

### Debugging Steps:
1. Check if you're actually using MPS:
   ```bash
   python -c "import torch; print('MPS:', torch.backends.mps.is_available())"
   ```

2. Try with explicit CPU to isolate the issue:
   ```bash
   transcribe "your_video_url" --device cpu
   ```

3. Check system resources:
   ```bash
   # Check CPU usage
   top
   
   # Check if Python is stuck
   ps aux | grep python
   ```

### Potential Causes:

1. **MPS Operation Failure**: Despite our testing, there might be an edge case
2. **Memory Issues**: Very long audio might cause memory problems
3. **Deadlock**: The threading/subprocess might have deadlocked

## Recommended Workarounds

### For Single Files:
```bash
# Force CPU for this specific file
transcribe "your_video_url" --device cpu
```

### For Batch Processing:
```python
# Add per-file timeout wrapper
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Diarization took too long")

# Set 2-minute timeout for MPS
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(120)  # 2 minutes
try:
    # Run processing
    process_file(...)
finally:
    signal.alarm(0)  # Cancel alarm
```

## Prevention

1. **Monitor first few files** in a batch
2. **Test with shorter clips** first
3. **Use CPU fallback** for files that consistently fail on MPS
