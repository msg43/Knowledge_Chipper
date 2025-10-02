# Cursor Auto-Wrap System - Automatic Timeout Prevention

This system **automatically prevents Cursor AI tool timeouts** without you having to remember to wrap commands. It's completely invisible and learns from your usage patterns.

## 🚀 Quick Start

The system is already installed! Here's how to use it:

### Option 1: Automatic (Recommended)
When you open a new terminal in Cursor, the system is automatically active. Just run commands normally:

```bash
# These commands will be automatically wrapped if needed:
python train_model.py --epochs 100
make build
npm install
pytest tests/
```

### Option 2: Manual Activation
If auto-activation isn't working, manually activate in any terminal:

```bash
source ./activate_cursor_wrap.sh
```

## ✨ Key Features

### 🧠 Smart Detection
- **Learns from your usage**: Tracks which commands are slow and automatically wraps them
- **Pattern recognition**: Detects long-running patterns like "install", "build", "train", etc.
- **Historical data**: Remembers command durations and wrap success rates

### 🔄 Completely Invisible
- **No command changes needed**: Run `python script.py` exactly as before
- **Automatic wrapping**: System decides when to apply timeout prevention
- **Seamless integration**: Works with all your existing workflows

### 📊 Background Job Management
- **Auto-background for very long tasks**: Automatically runs extremely long commands in background
- **Job monitoring**: Easy status checking and log viewing
- **Smart notifications**: Get updates without blocking your terminal

## 🎛️ Control Commands

Once activated, you have these control commands:

```bash
cursor_status      # Show system status and configuration
cursor_disable     # Temporarily disable auto-wrapping
cursor_enable      # Re-enable auto-wrapping
cursor_raw cmd     # Run a command without any wrapping
cursor_wrap cmd    # Force wrap a command
cursor_jobs list   # List background jobs
cursor_jobs monitor job_id  # Monitor a specific job
```

## 🔧 How It Works

### 1. Smart Command Detection
The system analyzes each command and decides whether to wrap it based on:

- **Command patterns**: Known slow commands (python, make, npm, etc.)
- **Argument analysis**: Flags like `--install`, `--build`, `--epochs`
- **Historical data**: How long similar commands took before
- **File size detection**: Large file operations
- **Project context**: ML training, builds, tests, etc.

### 2. Automatic Wrapping Levels

**Level 1 - Fast Commands (No Wrapping)**
```bash
ls, cd, pwd, echo, cat, grep, git status
# These run normally - no overhead
```

**Level 2 - Medium Commands (Smart Wrapping)**
```bash
python script.py    # Wrapped if script looks long-running
make               # Wrapped if Makefile suggests long build
```

**Level 3 - Slow Commands (Always Wrapped)**
```bash
pip install package
docker build -t app .
pytest tests/ --coverage
python train_model.py --epochs 100
```

**Level 4 - Very Slow Commands (Background + Monitoring)**
```bash
# Automatically run in background with job ID returned
rsync -av large_dataset/ remote:/backup/
python massive_training_job.py
```

### 3. Learning System

The system gets smarter over time:

- **Duration tracking**: Records how long each command actually takes
- **Success rate monitoring**: Tracks when wrapping helps vs. hurts
- **Pattern learning**: Identifies new slow command patterns
- **Project-specific adaptation**: Learns your specific workflow patterns

## 📋 Examples

### Automatic Python Script Wrapping
```bash
# You type this:
python long_script.py

# System detects it might be slow and automatically runs:
# ./scripts/cursor_safe_run.sh --python python long_script.py
# 
# You see normal output plus occasional status updates:
# [INFO] 2024-01-01T10:00:00: Starting script
# ::status::{"phase":"processing","percent":25,"message":"Loading data"}
# [HB] 2024-01-01T10:00:20: Process still running...
# ::status::{"phase":"training","percent":75,"message":"Training model"}
# [SUCCESS] 2024-01-01T10:05:00: Script completed
```

### Automatic Background Jobs
```bash
# You type this:
python very_long_training.py --epochs 1000

# System detects this will be very slow and asks:
# [CURSOR] This looks like a very long command. Run in background? (y/n)
# 
# If you say yes, you get:
# {
#   "job_id": "job_1234567890_12345",
#   "pid": 54321,
#   "log_file": "/tmp/cursor_jobs/job_1234567890_12345.log"
# }
# 
# Then monitor with:
cursor_jobs monitor job_1234567890_12345
```

### Smart Build Detection
```bash
# You type this:
make build

# System checks your Makefile and sees complex build steps
# Automatically wraps with proper output handling:
# [CURSOR] Auto-wrapping detected build command: make build
# [INFO] Starting build process
# ::status::{"phase":"compiling","percent":30,"message":"Building sources"}
# [HB] Process still running (elapsed: 45.2s)
# ::status::{"phase":"linking","percent":80,"message":"Linking binaries"}
# [SUCCESS] Build completed successfully
```

## 🎯 Project-Specific Integration

### VS Code Tasks
The system creates VS Code tasks that automatically use safe wrapping:

- **Ctrl+Shift+P** → "Tasks: Run Task" → "Safe Python Run"
- **Ctrl+Shift+P** → "Tasks: Run Task" → "Safe Test Run"
- **Ctrl+Shift+P** → "Tasks: Run Task" → "HCE Process (Safe)"

### Shell Integration
Add to your `.zshrc` or `.bashrc` for global activation:

```bash
# Auto-activate Cursor wrapping in project directories
cursor_auto_activate() {
    if [[ -f "./activate_cursor_wrap.sh" ]]; then
        source ./activate_cursor_wrap.sh
    fi
}

# Run on directory change
chpwd_functions+=(cursor_auto_activate)  # zsh
# or for bash:
# cd() { builtin cd "$@" && cursor_auto_activate; }
```

## 🔍 Monitoring and Debugging

### Check System Status
```bash
cursor_status
# Shows:
# - Whether auto-wrap is enabled
# - Which commands are configured for wrapping
# - Project root and script locations
# - Available control commands
```

### View Learning Data
```bash
python scripts/cursor_smart_detector.py --stats
# Shows historical command data and learning patterns
```

### Debug Mode
```bash
export CURSOR_DEBUG=1
# Enables verbose logging of wrapping decisions
```

### Manual Override Examples
```bash
# Force wrap a command that system thinks is fast
cursor_wrap ls -la /very/large/directory

# Run a command without any wrapping
cursor_raw python slow_script.py

# Temporarily disable for multiple commands
cursor_disable
python script1.py
make build
python script2.py
cursor_enable
```

## 🛠️ Configuration

### Environment Variables
```bash
export CURSOR_AUTO_WRAP=1                    # Enable/disable system
export CURSOR_PROJECT_ROOT=/path/to/project  # Project root directory
export CURSOR_DEBUG=1                        # Enable debug logging
export CURSOR_HEARTBEAT_INTERVAL=30          # Heartbeat frequency (seconds)
export CURSOR_DEFAULT_TIMEOUT=4h             # Default command timeout
```

### Customizing Detection Patterns

Edit `scripts/cursor_smart_detector.py` to add your own patterns:

```python
# Add to long_running_patterns list:
self.long_running_patterns.extend([
    r"my_slow_command",
    r"custom_build_script",
    r"--my-slow-flag"
])

# Add to fast_commands set:
self.fast_commands.update({
    "my_fast_cmd",
    "quick_status"
})
```

## 🚨 Troubleshooting

### System Not Activating
1. Check if files exist: `ls scripts/cursor_*.sh`
2. Manual activation: `source ./activate_cursor_wrap.sh`
3. Check permissions: `chmod +x scripts/*.sh`

### Commands Not Being Wrapped
1. Check status: `cursor_status`
2. Force wrap to test: `cursor_wrap your_command`
3. Check detection: `python scripts/cursor_smart_detector.py your_command`

### Background Jobs Not Working
1. Check job directory: `ls -la /tmp/cursor_jobs/`
2. Test job manager: `cursor_jobs list`
3. Check permissions: `chmod +x scripts/cursor_job_manager.sh`

### Performance Issues
1. Disable learning: `export CURSOR_SMART_DETECTION=0`
2. Use manual patterns only
3. Check log file sizes in `/tmp/cursor_jobs/`

## 🎉 Success Indicators

You know the system is working when:

- ✅ Long commands show `[CURSOR] Auto-wrapping detected long command`
- ✅ You see periodic `[HB]` heartbeat messages during long operations
- ✅ Commands show structured status updates like `::status::`
- ✅ Cursor AI tools never timeout, even on very long operations
- ✅ `cursor_status` shows "Enabled: 1"

## 🔄 Updates and Maintenance

The system is self-maintaining:

- **Automatic cleanup**: Old job files are cleaned up automatically
- **Learning improvement**: Detection gets better with more usage
- **Statistics rotation**: Keeps only recent command history
- **Log management**: Automatically manages log file sizes

To manually clean up:
```bash
cursor_jobs cleanup  # Remove old job files
rm -rf tmp/cursor_jobs/*  # Nuclear cleanup
```

---

**That's it!** The system now runs invisibly in the background, preventing timeouts automatically while learning your specific usage patterns. Just use Cursor normally - the timeout prevention is completely transparent.

For any issues or questions, check the troubleshooting section above or examine the logs in `/tmp/cursor_jobs/`.
