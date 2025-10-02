#!/bin/bash

# Cursor Safe Run - Easy-to-use wrapper for common long-running commands
# This script automatically applies the timeout prevention patterns

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_SCRIPT="$SCRIPT_DIR/cursor_tool_wrapper.sh"
PYTHON_WRAPPER="$SCRIPT_DIR/cursor_progress_wrapper.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

show_usage() {
    cat << EOF
Cursor Safe Run - Prevent tool timeouts for long-running commands

Usage: $0 [options] [command] [args...]

Options:
  --background, -b      Run in background and return job info
  --timeout=DURATION    Set timeout (default: 2h)
  --python             Use Python wrapper (better for Python scripts)
  --help, -h           Show this help

Common Commands (automatically wrapped):
  $0 python script.py                    # Run Python script with progress tracking
  $0 make build                          # Run make with proper output handling
  $0 npm install                         # Run npm with timeout prevention
  $0 pytest tests/                       # Run tests with real-time output
  $0 docker build -t myapp .            # Run Docker build with progress
  $0 --background rsync -av src/ dest/  # Run in background

Examples:
  # Run a Python script safely
  $0 python train_model.py --epochs 100

  # Run tests in background
  $0 -b pytest tests/ --verbose

  # Build with custom timeout
  $0 --timeout=4h make build

  # Use Python wrapper for better Python integration
  $0 --python python long_script.py

Special Python Integration:
  For Python scripts, you can also integrate the wrapper directly:

  from scripts.cursor_progress_wrapper import CursorProgressWrapper

  wrapper = CursorProgressWrapper()
  wrapper.start()
  wrapper.emit_status("processing", 50, "Halfway done")
  # ... your code ...
  wrapper.emit_done(True, "Completed successfully")
  wrapper.stop()

EOF
}

# Detect command type and apply appropriate wrapping
wrap_command() {
    local use_python_wrapper=false
    local background_mode=false
    local timeout="2h"
    local command_args=()

    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            --python)
                use_python_wrapper=true
                shift
                ;;
            --background|-b)
                background_mode=true
                shift
                ;;
            --timeout=*)
                timeout="${1#*=}"
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            --)
                shift
                command_args=("$@")
                break
                ;;
            *)
                command_args=("$@")
                break
                ;;
        esac
    done

    if [[ ${#command_args[@]} -eq 0 ]]; then
        log_error "No command specified"
        show_usage
        exit 1
    fi

    local first_arg="${command_args[0]}"

    # Auto-detect Python wrapper usage
    if [[ "$first_arg" == "python"* ]] || [[ "$first_arg" == "pip"* ]] || [[ "$first_arg" == "pytest"* ]]; then
        if [[ "$use_python_wrapper" != true ]]; then
            log_info "Detected Python command, consider using --python for better integration"
        fi
    fi

    # Prepare wrapper arguments
    local wrapper_args=()
    wrapper_args+=("--timeout=$timeout")

    if [[ "$background_mode" == true ]]; then
        wrapper_args+=("--background")
    fi

    if [[ "$use_python_wrapper" == true ]]; then
        log_info "Using Python wrapper for command: ${command_args[*]}"

        if [[ "$background_mode" == true ]]; then
            log_warn "Background mode not directly supported with Python wrapper"
            log_info "Use the bash wrapper for background jobs"
            exec "$WRAPPER_SCRIPT" "${wrapper_args[@]}" -- "$PYTHON_WRAPPER" "${command_args[@]}"
        else
            exec "$PYTHON_WRAPPER" "${command_args[@]}"
        fi
    else
        log_info "Using bash wrapper for command: ${command_args[*]}"
        exec "$WRAPPER_SCRIPT" "${wrapper_args[@]}" -- "${command_args[@]}"
    fi
}

# Add some common command presets
case "${1:-}" in
    "hce")
        # Knowledge Chipper HCE processing
        shift
        log_info "Running HCE processing with safe wrapper"
        wrap_command --python python -m knowledge_system.processors.hce.parallel_processor "$@"
        ;;
    "test")
        # Run tests safely
        shift
        log_info "Running tests with safe wrapper"
        wrap_command --python pytest "$@"
        ;;
    "build")
        # Run build safely
        shift
        log_info "Running build with safe wrapper"
        wrap_command make build "$@"
        ;;
    "install")
        # Run installation safely
        shift
        log_info "Running installation with safe wrapper"
        wrap_command pip install "$@"
        ;;
    *)
        # Regular command wrapping
        wrap_command "$@"
        ;;
esac
