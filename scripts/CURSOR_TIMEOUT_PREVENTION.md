# Cursor Timeout Prevention System

This system prevents Cursor AI tool timeouts when running long-running processes by implementing the patterns you outlined: making commands "chatty, honest, and killable."

## Quick Start

The easiest way to use this system is with the `cursor_safe_run.sh` script:

```bash
# Run any command safely (prevents timeouts)
./scripts/cursor_safe_run.sh python long_script.py

# Run in background and get job ID
./scripts/cursor_safe_run.sh --background make build

# Use Python wrapper for better Python integration
./scripts/cursor_safe_run.sh --python python train_model.py

# Run with custom timeout
./scripts/cursor_safe_run.sh --timeout=4h docker build -t myapp .
```

## System Components

### 1. Core Wrapper (`cursor_tool_wrapper.sh`)

The main bash wrapper that implements:
- **Real-time output**: Uses `stdbuf -oL -eL` to prevent buffering
- **Proper error handling**: Uses `set -Eeuo pipefail` and error traps
- **Timeout management**: Uses `timeout` command with clear exit codes
- **Heartbeat mechanism**: Emits periodic "still running" messages
- **Structured logging**: Emits parseable status messages

### 2. Job Manager (`cursor_job_manager.sh`)

Manages background jobs with these commands:
```bash
./scripts/cursor_job_manager.sh list                    # List all jobs
./scripts/cursor_job_manager.sh start -- python script.py  # Start background job
./scripts/cursor_job_manager.sh status job_1234567890   # Check job status
./scripts/cursor_job_manager.sh monitor job_1234567890  # Monitor with auto-refresh
./scripts/cursor_job_manager.sh logs job_1234567890     # Show job logs
./scripts/cursor_job_manager.sh kill job_1234567890     # Kill running job
```

### 3. Python Wrapper (`cursor_progress_wrapper.py`)

For Python scripts, provides:
- Progress tracking with structured status updates
- Heartbeat mechanism
- Context managers for easy integration
- Test mode for validation

### 4. Safe Run Script (`cursor_safe_run.sh`)

One-stop convenience script that automatically chooses the right wrapper and applies common patterns.

## Usage Patterns

### Pattern A: Direct Safe Execution

For commands that should run in the foreground but need timeout prevention:

```bash
# Instead of this (can timeout):
python long_running_script.py

# Use this:
./scripts/cursor_safe_run.sh python long_running_script.py
```

### Pattern B: Background Jobs + Polling

For very long commands that you want to monitor:

```bash
# Start the job
job_info=$(./scripts/cursor_job_manager.sh start -- python train_model.py --epochs 100)
job_id=$(echo "$job_info" | jq -r .job_id)

# Monitor it
./scripts/cursor_job_manager.sh monitor "$job_id"

# Or check status periodically
./scripts/cursor_job_manager.sh status "$job_id"
```

### Pattern C: Python Integration

For Python scripts, integrate the wrapper directly:

```python
from scripts.cursor_progress_wrapper import CursorProgressWrapper

def my_long_function():
    wrapper = CursorProgressWrapper()
    
    try:
        wrapper.start()
        wrapper.log_info("Starting processing")
        
        # Use progress tracking
        with wrapper.progress_context(100) as progress:
            for i in range(100):
                # Do work
                time.sleep(0.1)
                
                # Update progress
                progress.update(i, "processing", f"Step {i}/100")
        
        wrapper.emit_done(True, "Processing completed")
        
    except Exception as e:
        wrapper.emit_error("processing", str(e))
        raise
    finally:
        wrapper.stop()

if __name__ == "__main__":
    my_long_function()
```

## Features Implemented

### ✅ Force Real-time Output
- Uses `PYTHONUNBUFFERED=1` and `python -u`
- Uses `stdbuf -oL -eL` for line buffering
- Flushes output immediately

### ✅ Fail Loud, Not Silent
- Uses `set -Eeuo pipefail` in bash
- Error traps that surface failures
- Structured error reporting

### ✅ Timeout with Clear Exit Codes
- Uses `timeout` command with preservation
- Exit code 124 = timed out (easy to detect)
- Configurable timeout durations

### ✅ Always Tee Logs
- All output goes to both console and log files
- Logs persist even if UI dies
- Easy log retrieval with job manager

### ✅ Background Jobs + Polling
- Start/status/logs pattern implemented
- JSON status files for easy parsing
- PID tracking for process management

### ✅ Heartbeat Mechanism
- Periodic "still alive" messages
- Configurable heartbeat intervals
- Prevents silent timeouts

### ✅ Structured Status Lines
- `::status::` for progress updates
- `::done::` for completion
- `::error::` for errors
- JSON format for easy parsing

## Common Command Examples

### HCE Processing
```bash
# Safe HCE processing
./scripts/cursor_safe_run.sh hce --input video.mp4

# Background HCE processing
./scripts/cursor_job_manager.sh start -- python -m knowledge_system.processors.hce.parallel_processor --input video.mp4
```

### Testing
```bash
# Safe test running
./scripts/cursor_safe_run.sh test tests/ --verbose

# Background testing
./scripts/cursor_job_manager.sh start -- pytest tests/ --verbose
```

### Building
```bash
# Safe building
./scripts/cursor_safe_run.sh build

# With custom timeout
./scripts/cursor_safe_run.sh --timeout=4h make build
```

### Docker
```bash
# Safe Docker builds
./scripts/cursor_safe_run.sh docker build -t myapp .

# Background Docker builds
./scripts/cursor_job_manager.sh start -- docker build -t myapp .
```

## Testing the System

Test with the built-in sample process:

```bash
# Test direct execution
./scripts/cursor_progress_wrapper.py --test

# Test background job
./scripts/cursor_job_manager.sh start -- ./scripts/cursor_progress_wrapper.py --test

# Monitor the test job
job_id=$(./scripts/cursor_job_manager.sh list | grep -o 'job_[0-9_]*' | head -1)
./scripts/cursor_job_manager.sh monitor "$job_id"
```

## Troubleshooting

### Problem: Command still times out
**Solution**: Ensure the command produces output. Add `--heartbeat=10` for more frequent heartbeats.

### Problem: Background job not found
**Solution**: Check if the job directory exists: `ls -la /tmp/cursor_jobs/`

### Problem: Python wrapper not working
**Solution**: Ensure Python script is executable and uses proper imports.

### Problem: Logs not appearing
**Solution**: Check log file permissions and ensure `tee` is working properly.

## Advanced Configuration

### Environment Variables
```bash
export CURSOR_JOB_DIR="/custom/job/directory"
export CURSOR_HEARTBEAT_INTERVAL=30
export CURSOR_DEFAULT_TIMEOUT="4h"
```

### Custom Status Updates
In your scripts, emit status updates:
```bash
echo "::status::{\"phase\":\"downloading\",\"percent\":25,\"message\":\"Fetching data\"}"
echo "::done::{\"success\":true,\"message\":\"Download complete\"}"
```

### Integration with Existing Scripts
Wrap existing scripts without modification:
```bash
./scripts/cursor_safe_run.sh ./your_existing_script.sh arg1 arg2
```

This system ensures that Cursor's AI tools never timeout on long-running processes while providing full visibility into what's happening.
