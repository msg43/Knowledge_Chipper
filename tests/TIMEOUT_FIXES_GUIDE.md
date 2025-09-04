# Process Timeout and Hanging Fixes Guide

This guide explains the comprehensive fixes implemented to solve process timeout and hanging issues in the Knowledge Chipper testing modules.

## Summary of Issues Fixed

### 1. Core Timeout Problems
- **Fixed**: Insufficient timeout management with fixed, too-short timeouts
- **Fixed**: Poor process state detection that missed actual process states
- **Fixed**: Inadequate force stop mechanisms that couldn't kill subprocess chains
- **Fixed**: Missing resource cleanup leaving orphaned processes
- **Fixed**: Weak heartbeat monitoring that failed silently

### 2. Solutions Implemented

#### A. Enhanced GUI Automation (`gui_automation.py`)
```python
# New features:
- Adaptive timeout detection based on UI state changes
- Stuck state detection (consecutive no-change cycles)
- Multi-method force stop (graceful → aggressive → kill)
- Process-level cleanup using psutil
- Better button state monitoring
```

**Key Improvements:**
- **Stuck Detection**: Monitors UI state changes to detect when processes are truly stuck
- **Staged Intervention**: Graceful stop → Force stop → Process kill cascade
- **Process Safety**: Never kills GUI or test processes, only processing workers

#### B. Robust Process Monitoring (`process_monitor.py`)
```python
# New ProcessMonitor class features:
- Background process monitoring with heartbeat tracking
- Automatic timeout and cleanup
- Graceful and force termination
- Resource usage tracking
- Global monitor for system-wide process management
```

**Key Features:**
- **Heartbeat Monitoring**: Tracks process activity and detects silent failures
- **Automatic Cleanup**: Kills processes that exceed timeouts or stop responding
- **Safe Termination**: Uses SIGTERM first, then SIGKILL if needed
- **Process Groups**: Creates process groups to ensure child processes are cleaned up

#### C. Improved Test Orchestrator (`test_orchestrator.py`)
```python
# Enhanced timeout handling:
- Adaptive timeouts based on operation type (transcribe: 5min, summarize: 3min)
- Aggressive cleanup for stuck processes
- Better error recovery and state reset
- Process group management for subprocess chains
```

**Timeout Strategy:**
- **Quick Mode**: 60 seconds (for startup delay tolerance)
- **Transcription**: 300 seconds (5 minutes)
- **Summarization**: 180 seconds (3 minutes) 
- **Stress Mode**: 600 seconds (10 minutes)
- **Default**: 240 seconds (4 minutes)

#### D. Enhanced CLI Test Suite (`comprehensive_test_suite.py`)
```python
# New process management:
- Process groups for killing child processes
- Graceful termination with fallback force kill
- Better signal handling (SIGTERM → SIGKILL)
- Proper cleanup of subprocess chains
```

## Usage Examples

### 1. Running Tests with New Timeout Management

```bash
# CLI tests now handle timeouts automatically
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python tests/comprehensive_test_suite.py

# The tests will:
# - Use adaptive timeouts based on operation type
# - Automatically kill hung processes
# - Clean up resources properly
# - Continue testing even after timeouts
```

### 2. GUI Tests with Process Monitoring

```python
# The GUI automation now includes:
from tests.gui_comprehensive.test_orchestrator import TestOrchestrator
from tests.gui_comprehensive.process_monitor import get_global_monitor

# Start the global process monitor
monitor = get_global_monitor()

# Run tests - they'll automatically use the new timeout handling
orchestrator = TestOrchestrator(...)
orchestrator.setup()
orchestrator.run_comprehensive_tests()

# Cleanup happens automatically, but can be done manually:
orchestrator._perform_aggressive_cleanup()
```

### 3. Manual Process Cleanup

```python
from tests.gui_comprehensive.process_monitor import ProcessCleanup

# Clean up all Knowledge System processes
ProcessCleanup.cleanup_knowledge_system_processes()

# Or clean up specific process types
ProcessCleanup.kill_processes_by_name(['whisper', 'ffmpeg', 'sox'])
```

## Key Configuration Changes

### 1. Timeout Settings
```python
# Old: Fixed 30-60 second timeouts
timeout = 30 if quick_mode else 60

# New: Adaptive timeouts
if quick_mode:
    timeout = 60  # Allow for startup delays
elif 'transcribe' in operation:
    timeout = 300  # 5 minutes for transcription
elif 'summarize' in operation:
    timeout = 180  # 3 minutes for summarization
else:
    timeout = 240  # 4 minutes default
```

### 2. Process Detection
```python
# Old: Simple button text scanning
if "processing" in button_text:
    processing_active = True

# New: Comprehensive state tracking
consecutive_no_change_count = 0
last_button_state = None
force_stop_attempted = False

# Detect stuck states and intervene proactively
if consecutive_no_change_count > stuck_threshold:
    logger.warning("Processing appears stuck, intervening...")
    self._attempt_force_stop()
```

### 3. Process Cleanup
```python
# Old: Basic process.terminate()
process.terminate()

# New: Multi-stage cleanup
try:
    proc.terminate()  # SIGTERM first
    proc.wait(timeout=3)
except subprocess.TimeoutExpired:
    proc.kill()  # SIGKILL if needed
    proc.wait()
```

## Testing the Fixes

### 1. Verify Timeout Handling
```bash
# Test with a process that should timeout
python -c "
from tests.gui_comprehensive.gui_automation import GUIAutomation
# Create a test scenario that times out
# The new system should detect and clean up automatically
"
```

### 2. Verify Process Cleanup
```bash
# Before running tests, check for orphaned processes
ps aux | grep -E "(whisper|ffmpeg|knowledge_system)"

# Run tests
python tests/comprehensive_test_suite.py

# After tests, verify cleanup (should be minimal/none)
ps aux | grep -E "(whisper|ffmpeg|knowledge_system)"
```

### 3. Monitor Process Activity
```bash
# In one terminal, monitor processes
watch -n 1 "ps aux | grep -E '(whisper|ffmpeg|knowledge)' | grep -v grep"

# In another terminal, run tests
python tests/comprehensive_test_suite.py

# You should see processes start and get cleaned up properly
```

## Expected Behavior After Fixes

### ✅ What Should Work Now:
1. **No More Hanging Tests**: Tests timeout appropriately and continue
2. **Proper Process Cleanup**: All spawned processes are killed when tests finish
3. **Graceful Recovery**: Tests can recover from timeouts and continue
4. **Resource Management**: Memory and CPU usage stay reasonable
5. **Faster Testing**: Less time waiting for hung processes

### ⚠️ What to Watch For:
1. **Process Kill Messages**: Normal to see "Force killing process" messages
2. **Timeout Warnings**: Expected for tests with problematic files
3. **Cleanup Delays**: 3-5 second delays for cleanup are normal

### 🚨 What Should No Longer Happen:
1. ❌ Tests hanging indefinitely
2. ❌ Orphaned whisper/ffmpeg processes after tests
3. ❌ Memory leaks from stuck processes
4. ❌ Need to manually kill processes between test runs
5. ❌ Tests requiring restart of terminal/IDE

## Configuration Options

### Environment Variables
```bash
# Optional: Adjust default timeouts
export KNOWLEDGE_CHIPPER_TEST_TIMEOUT=600        # Default test timeout
export KNOWLEDGE_CHIPPER_TRANSCRIBE_TIMEOUT=300  # Transcription timeout
export KNOWLEDGE_CHIPPER_SUMMARIZE_TIMEOUT=180   # Summarization timeout
```

### Process Monitor Settings
```python
# In process_monitor.py, adjust these settings:
MONITORING_INTERVAL = 5     # Check processes every 5 seconds
HEARTBEAT_TIMEOUT = 60      # Consider process stuck after 60s of no activity
CLEANUP_TIMEOUT = 10        # Wait 10s for graceful shutdown before force kill
```

## Troubleshooting

### If Tests Still Hang:
1. **Check Process Monitor**: Ensure the global monitor is running
2. **Manual Cleanup**: Run `ProcessCleanup.cleanup_knowledge_system_processes()`
3. **Increase Timeouts**: Modify timeout values in test configuration
4. **Check System Resources**: Ensure sufficient CPU/memory available

### If Process Cleanup Fails:
1. **Check Permissions**: Ensure the test process can kill child processes
2. **Manual Kill**: Use `killall whisper ffmpeg` or similar
3. **Restart Terminal**: If processes are truly stuck, restart your development environment

### If False Positives Occur:
1. **Adjust Stuck Detection**: Increase `stuck_threshold` in gui_automation.py
2. **Extend Timeouts**: Increase timeout values for slow operations
3. **Disable Force Stop**: Comment out aggressive cleanup for debugging

## Integration Notes

### Requirements Added:
- `psutil` package for cross-platform process management
- Enhanced signal handling in subprocess creation
- Threading for background process monitoring

### Backward Compatibility:
- All existing test interfaces remain the same
- New features are opt-in and fail gracefully
- Old timeout values are preserved as minimums

This comprehensive fix should resolve the process hanging and timeout issues that were preventing effective testing of the Knowledge Chipper system.
