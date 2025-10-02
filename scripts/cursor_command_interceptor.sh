#!/bin/bash

# Cursor Command Interceptor - Universal command wrapping at shell level
# This script intercepts ALL commands and intelligently decides whether to wrap them

# Only run if we're in a Cursor environment
if [[ -z "$CURSOR_AUTO_WRAP" ]] || [[ "$CURSOR_AUTO_WRAP" != "1" ]]; then
    exit 0
fi

# Get the original command
ORIGINAL_COMMAND=("$@")
COMMAND_STRING="${*}"

# Project configuration
CURSOR_PROJECT_ROOT="${CURSOR_PROJECT_ROOT:-$(pwd)}"
CURSOR_SCRIPTS_DIR="$CURSOR_PROJECT_ROOT/scripts"
SMART_DETECTOR="$CURSOR_SCRIPTS_DIR/cursor_smart_detector.py"
SAFE_RUN="$CURSOR_SCRIPTS_DIR/cursor_safe_run.sh"

# Logging
cursor_log() {
    echo -e "\033[0;34m[CURSOR]\033[0m $*" >&2
}

cursor_debug() {
    if [[ "$CURSOR_DEBUG" == "1" ]]; then
        echo -e "\033[0;35m[DEBUG]\033[0m $*" >&2
    fi
}

# Check if we should intercept this command
should_intercept() {
    local cmd="$1"

    # Never intercept our own commands
    if [[ "$cmd" == *"cursor_"* ]]; then
        return 1
    fi

    # Never intercept shell builtins
    if builtin type "$cmd" 2>/dev/null | grep -q "builtin"; then
        return 1
    fi

    # Never intercept cd, exit, etc.
    case "$cmd" in
        cd|exit|source|.|export|alias|unalias|history|jobs|bg|fg)
            return 1
            ;;
    esac

    return 0
}

# Main interception logic
main() {
    local first_arg="${ORIGINAL_COMMAND[0]}"

    cursor_debug "Intercepting command: $COMMAND_STRING"

    # Check if we should intercept
    if ! should_intercept "$first_arg"; then
        cursor_debug "Not intercepting: $first_arg"
        exec "${ORIGINAL_COMMAND[@]}"
        return $?
    fi

    # Use smart detector if available
    if [[ -f "$SMART_DETECTOR" ]]; then
        cursor_debug "Using smart detector for: $COMMAND_STRING"

        if python3 "$SMART_DETECTOR" --project-root "$CURSOR_PROJECT_ROOT" "$COMMAND_STRING" >/dev/null 2>&1; then
            cursor_log "Auto-wrapping detected long command: $COMMAND_STRING"

            # Record start time for statistics
            start_time=$(date +%s.%N)

            # Determine wrapper type
            if [[ "$first_arg" == "python"* ]] || [[ "$first_arg" == "pip"* ]] || [[ "$first_arg" == "pytest"* ]]; then
                "$SAFE_RUN" --python "${ORIGINAL_COMMAND[@]}"
            else
                "$SAFE_RUN" "${ORIGINAL_COMMAND[@]}"
            fi

            exit_code=$?

            # Record statistics
            end_time=$(date +%s.%N)
            duration=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")

            if command -v python3 >/dev/null 2>&1; then
                python3 "$SMART_DETECTOR" --project-root "$CURSOR_PROJECT_ROOT" \
                    --record "$COMMAND_STRING" "$duration" "true" >/dev/null 2>&1 || true
            fi

            return $exit_code
        else
            cursor_debug "Smart detector says no wrapping needed"
        fi
    fi

    # Fallback: run command normally but still record statistics
    cursor_debug "Running command normally: $COMMAND_STRING"

    start_time=$(date +%s.%N)
    "${ORIGINAL_COMMAND[@]}"
    exit_code=$?
    end_time=$(date +%s.%N)

    # Record statistics for learning
    if [[ -f "$SMART_DETECTOR" ]] && command -v python3 >/dev/null 2>&1; then
        duration=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
        python3 "$SMART_DETECTOR" --project-root "$CURSOR_PROJECT_ROOT" \
            --record "$COMMAND_STRING" "$duration" "false" >/dev/null 2>&1 || true
    fi

    return $exit_code
}

# Execute main function
main "$@"
