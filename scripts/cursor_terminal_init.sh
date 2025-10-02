#!/bin/bash

# Cursor Terminal Initialization - Automatic Command Wrapping
# This script is automatically sourced when a new terminal opens in Cursor
# It provides transparent timeout prevention for long-running commands

# Only initialize if we're in a Cursor terminal and auto-wrap is enabled
if [[ -z "$CURSOR_AUTO_WRAP" ]] || [[ "$CURSOR_AUTO_WRAP" != "1" ]]; then
    return 0
fi

# Set project root
export CURSOR_PROJECT_ROOT="${CURSOR_PROJECT_ROOT:-$(pwd)}"
export CURSOR_SCRIPTS_DIR="$CURSOR_PROJECT_ROOT/scripts"

# Ensure our scripts are executable
if [[ -d "$CURSOR_SCRIPTS_DIR" ]]; then
    chmod +x "$CURSOR_SCRIPTS_DIR"/*.sh "$CURSOR_SCRIPTS_DIR"/*.py 2>/dev/null || true
fi

# Colors for output (only if terminal supports it)
if [[ -t 1 ]]; then
    export CURSOR_RED='\033[0;31m'
    export CURSOR_GREEN='\033[0;32m'
    export CURSOR_YELLOW='\033[1;33m'
    export CURSOR_BLUE='\033[0;34m'
    export CURSOR_NC='\033[0m'
else
    export CURSOR_RED=''
    export CURSOR_GREEN=''
    export CURSOR_YELLOW=''
    export CURSOR_BLUE=''
    export CURSOR_NC=''
fi

# Logging functions
cursor_log_info() {
    echo -e "${CURSOR_BLUE}[CURSOR]${CURSOR_NC} $*" >&2
}

cursor_log_warn() {
    echo -e "${CURSOR_YELLOW}[CURSOR]${CURSOR_NC} $*" >&2
}

# Commands that should always be wrapped (likely to be long-running)
declare -a CURSOR_ALWAYS_WRAP_COMMANDS=(
    "python"
    "python3"
    "pip"
    "pip3"
    "pytest"
    "make"
    "npm"
    "yarn"
    "docker"
    "rsync"
    "scp"
    "curl"
    "wget"
    "git"
    "ffmpeg"
    "convert"
    "find"
)

# Commands that should never be wrapped (always fast)
declare -a CURSOR_NEVER_WRAP_COMMANDS=(
    "ls"
    "cd"
    "pwd"
    "echo"
    "cat"
    "head"
    "tail"
    "grep"
    "awk"
    "sed"
    "sort"
    "uniq"
    "wc"
    "which"
    "type"
    "alias"
    "history"
    "ps"
    "kill"
    "jobs"
    "bg"
    "fg"
    "clear"
    "exit"
    "source"
    "export"
    "env"
    "date"
    "whoami"
    "hostname"
    "uname"
)

# Check if a command should be wrapped
should_wrap_command() {
    local cmd="$1"
    local full_command="$*"

    # Never wrap if disabled
    if [[ "$CURSOR_AUTO_WRAP" != "1" ]]; then
        return 1
    fi

    # Never wrap our own wrapper scripts
    if [[ "$cmd" == *"cursor_"* ]]; then
        return 1
    fi

    # Never wrap shell builtins and fast commands
    for never_cmd in "${CURSOR_NEVER_WRAP_COMMANDS[@]}"; do
        if [[ "$cmd" == "$never_cmd" ]]; then
            return 1
        fi
    done

    # Always wrap known long-running commands
    for always_cmd in "${CURSOR_ALWAYS_WRAP_COMMANDS[@]}"; do
        if [[ "$cmd" == "$always_cmd" ]] || [[ "$cmd" == *"/$always_cmd" ]]; then
            return 0
        fi
    done

    # Wrap commands with certain patterns that suggest they might be long-running
    if [[ "$full_command" == *"--help"* ]] || [[ "$full_command" == *"-h"* ]] ||
       [[ "$full_command" == *"--version"* ]] || [[ "$full_command" == *"-V"* ]] ||
       [[ "$full_command" == *"--list"* ]] || [[ "$full_command" == *"status"* ]]; then
        return 1  # Info commands are fast
    fi

    if [[ "$full_command" == *"install"* ]] ||
       [[ "$full_command" == *"build"* ]] ||
       [[ "$full_command" == *"test"* ]] ||
       [[ "$full_command" == *"train"* ]] ||
       [[ "$full_command" == *"process"* ]] ||
       [[ "$full_command" == *"download"* ]] ||
       [[ "$full_command" == *"upload"* ]] ||
       [[ "$full_command" == *"sync"* ]]; then
        return 0
    fi

    # Don't wrap by default for unknown commands
    return 1
}

# Smart command wrapper
cursor_smart_wrap() {
    local original_command=("$@")
    local first_arg="$1"

    # Extract the base command (handle paths)
    local base_cmd
    base_cmd=$(basename "$first_arg" 2>/dev/null || echo "$first_arg")

    if should_wrap_command "$base_cmd" "$*"; then
        cursor_log_info "Auto-wrapping potentially long command: $*"

        # Use the appropriate wrapper
        if [[ "$base_cmd" == "python"* ]] || [[ "$base_cmd" == "pip"* ]] || [[ "$base_cmd" == "pytest"* ]]; then
            exec "$CURSOR_SCRIPTS_DIR/cursor_safe_run.sh" --python "${original_command[@]}"
        else
            exec "$CURSOR_SCRIPTS_DIR/cursor_safe_run.sh" "${original_command[@]}"
        fi
    else
        # Run command normally
        exec "${original_command[@]}"
    fi
}

# Function to create smart aliases for common commands
create_cursor_aliases() {
    # Only create aliases if our scripts exist
    if [[ ! -f "$CURSOR_SCRIPTS_DIR/cursor_safe_run.sh" ]]; then
        return
    fi

    # Create wrapper functions for commands that might be long-running
    for cmd in "${CURSOR_ALWAYS_WRAP_COMMANDS[@]}"; do
        # Skip if command doesn't exist on system
        if ! command -v "$cmd" >/dev/null 2>&1; then
            continue
        fi

        # Create a function that wraps the command
        eval "
        cursor_original_$cmd() {
            command $cmd \"\$@\"
        }

        $cmd() {
            if should_wrap_command \"$cmd\" \"\$*\"; then
                cursor_log_info \"Auto-wrapping: $cmd \$*\"
                if [[ \"$cmd\" == \"python\"* ]] || [[ \"$cmd\" == \"pip\"* ]] || [[ \"$cmd\" == \"pytest\"* ]]; then
                    \"\$CURSOR_SCRIPTS_DIR/cursor_safe_run.sh\" --python $cmd \"\$@\"
                else
                    \"\$CURSOR_SCRIPTS_DIR/cursor_safe_run.sh\" $cmd \"\$@\"
                fi
            else
                cursor_original_$cmd \"\$@\"
            fi
        }
        "
    done
}

# Function to disable auto-wrapping temporarily
cursor_disable() {
    export CURSOR_AUTO_WRAP="0"
    cursor_log_warn "Auto-wrapping disabled for this session"
    cursor_log_info "Use 'cursor_enable' to re-enable"
}

# Function to re-enable auto-wrapping
cursor_enable() {
    export CURSOR_AUTO_WRAP="1"
    cursor_log_info "Auto-wrapping enabled"
}

# Function to run a command without wrapping
cursor_raw() {
    local old_wrap="$CURSOR_AUTO_WRAP"
    export CURSOR_AUTO_WRAP="0"
    "$@"
    local exit_code=$?
    export CURSOR_AUTO_WRAP="$old_wrap"
    return $exit_code
}

# Function to force wrap a command
cursor_wrap() {
    cursor_log_info "Force-wrapping: $*"
    "$CURSOR_SCRIPTS_DIR/cursor_safe_run.sh" "$@"
}

# Function to show cursor status
cursor_status() {
    echo -e "${CURSOR_BLUE}Cursor Auto-Wrap Status:${CURSOR_NC}"
    echo "  Enabled: $CURSOR_AUTO_WRAP"
    echo "  Project Root: $CURSOR_PROJECT_ROOT"
    echo "  Scripts Dir: $CURSOR_SCRIPTS_DIR"
    echo ""
    echo -e "${CURSOR_BLUE}Available Commands:${CURSOR_NC}"
    echo "  cursor_disable  - Disable auto-wrapping"
    echo "  cursor_enable   - Enable auto-wrapping"
    echo "  cursor_raw cmd  - Run command without wrapping"
    echo "  cursor_wrap cmd - Force wrap a command"
    echo "  cursor_jobs     - Manage background jobs"
    echo ""
    echo -e "${CURSOR_BLUE}Auto-wrapped Commands:${CURSOR_NC}"
    if [[ ${#CURSOR_ALWAYS_WRAP_COMMANDS[@]} -gt 0 ]]; then
        printf "  %s\n" "${CURSOR_ALWAYS_WRAP_COMMANDS[@]}"
    else
        echo "  (none configured)"
    fi
}

# Alias for job management
cursor_jobs() {
    "$CURSOR_SCRIPTS_DIR/cursor_job_manager.sh" "$@"
}

# Initialize the system
if [[ -f "$CURSOR_SCRIPTS_DIR/cursor_safe_run.sh" ]]; then
    create_cursor_aliases
    cursor_log_info "Cursor timeout prevention active (use 'cursor_status' for info)"
else
    cursor_log_warn "Cursor scripts not found - auto-wrapping disabled"
    export CURSOR_AUTO_WRAP="0"
fi

# Add helpful aliases
alias cursor_help='cursor_status'
alias cjobs='cursor_jobs'
alias cwrap='cursor_wrap'
alias craw='cursor_raw'

# Export functions so they're available in subshells
export -f should_wrap_command cursor_smart_wrap cursor_disable cursor_enable cursor_raw cursor_wrap cursor_status cursor_jobs
export -f cursor_log_info cursor_log_warn
