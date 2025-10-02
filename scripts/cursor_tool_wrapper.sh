#!/bin/bash

# Cursor Tool Wrapper - Prevents timeouts and provides real-time feedback
# Usage: ./cursor_tool_wrapper.sh [options] -- command [args...]
#
# Options:
#   --timeout=DURATION    Set timeout (default: 2h)
#   --heartbeat=SECONDS   Heartbeat interval (default: 20s)
#   --job-dir=PATH        Job directory (default: /tmp/cursor_jobs)
#   --background          Run in background and return job info
#   --status=JOB_ID       Check status of background job
#   --logs=JOB_ID         Show logs of job
#   --kill=JOB_ID         Kill background job

set -Eeuo pipefail

# Default configuration
TIMEOUT="2h"
HEARTBEAT_INTERVAL=20
JOB_DIR="/tmp/cursor_jobs"
BACKGROUND_MODE=false
STATUS_MODE=""
LOGS_MODE=""
KILL_MODE=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date -Iseconds): $*" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date -Iseconds): $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date -Iseconds): $*" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date -Iseconds): $*" >&2
}

# Structured status logging
emit_status() {
    local phase="$1"
    local percent="${2:-0}"
    local message="${3:-}"
    echo "::status::{\"phase\":\"$phase\",\"percent\":$percent,\"message\":\"$message\",\"timestamp\":\"$(date -Iseconds)\"}"
}

emit_done() {
    local success="${1:-true}"
    local message="${2:-}"
    echo "::done::{\"success\":$success,\"message\":\"$message\",\"timestamp\":\"$(date -Iseconds)\"}"
}

emit_error() {
    local step="$1"
    local message="$2"
    echo "::error::{\"step\":\"$step\",\"message\":\"$message\",\"timestamp\":\"$(date -Iseconds)\"}"
}

# Parse command line arguments
parse_args() {
    local parsing_options=true

    while [[ $# -gt 0 ]] && $parsing_options; do
        case $1 in
            --timeout=*)
                TIMEOUT="${1#*=}"
                shift
                ;;
            --heartbeat=*)
                HEARTBEAT_INTERVAL="${1#*=}"
                shift
                ;;
            --job-dir=*)
                JOB_DIR="${1#*=}"
                shift
                ;;
            --background)
                BACKGROUND_MODE=true
                shift
                ;;
            --status=*)
                STATUS_MODE="${1#*=}"
                shift
                ;;
            --logs=*)
                LOGS_MODE="${1#*=}"
                shift
                ;;
            --kill=*)
                KILL_MODE="${1#*=}"
                shift
                ;;
            --)
                shift
                parsing_options=false
                ;;
            *)
                parsing_options=false
                ;;
        esac
    done

    # Remaining arguments are the command to run
    COMMAND_ARGS=("$@")
}

# Create job directory
ensure_job_dir() {
    mkdir -p "$JOB_DIR"
}

# Generate unique job ID
generate_job_id() {
    echo "job_$(date +%s)_$$"
}

# Get job files
get_job_files() {
    local job_id="$1"
    local base_path="$JOB_DIR/$job_id"

    echo "$base_path.log" "$base_path.status" "$base_path.pid" "$base_path.exit"
}

# Heartbeat function
start_heartbeat() {
    local log_file="$1"

    (
        while true; do
            sleep "$HEARTBEAT_INTERVAL"
            echo "[HB] $(date -Iseconds) - Process still running..." >> "$log_file"
        done
    ) &

    echo $!
}

# Error trap
error_trap() {
    local exit_code=$?
    local line_number=$1
    log_error "Command failed at line $line_number with exit code $exit_code"
    emit_error "execution" "Command failed at line $line_number with exit code $exit_code"
    exit $exit_code
}

# Run command with full monitoring
run_command() {
    local job_id="$1"
    shift
    local command=("$@")

    read -r log_file status_file pid_file exit_file <<< "$(get_job_files "$job_id")"

    # Set up error trapping
    trap 'error_trap $LINENO' ERR

    log_info "Starting job $job_id with command: ${command[*]}"
    emit_status "starting" 0 "Initializing command execution"

    # Start heartbeat
    local heartbeat_pid
    heartbeat_pid=$(start_heartbeat "$log_file")

    # Cleanup function
    cleanup() {
        log_info "Cleaning up job $job_id"
        kill "$heartbeat_pid" 2>/dev/null || true
        rm -f "$pid_file" 2>/dev/null || true
    }

    trap cleanup EXIT

    # Run the actual command with proper output handling
    (
        # Set up environment for unbuffered output
        export PYTHONUNBUFFERED=1
        export NODE_UNBUFFERED=1

        emit_status "running" 10 "Command started"

        # Execute with timeout and proper error handling
        timeout --preserve-status --signal=SIGINT --kill-after=30s "$TIMEOUT" \
            stdbuf -oL -eL bash -c "
                set -Eeuo pipefail
                trap 'echo \"[ERR] exit:\$?: \$BASH_COMMAND\" >&2' ERR
                exec $(printf '%q ' "${command[@]}")
            " 2>&1

    ) | tee -a "$log_file" | while IFS= read -r line; do
        # Parse structured status updates
        if [[ "$line" == ::status::* ]]; then
            echo "$line" > "$status_file"
        elif [[ "$line" == ::done::* ]]; then
            echo "$line" > "$status_file"
        elif [[ "$line" == ::error::* ]]; then
            echo "$line" > "$status_file"
        fi

        # Always output the line
        echo "$line"
    done

    local exit_code=$?
    echo "$exit_code" > "$exit_file"

    # Kill heartbeat
    kill "$heartbeat_pid" 2>/dev/null || true

    if [[ $exit_code -eq 0 ]]; then
        log_success "Job $job_id completed successfully"
        emit_done true "Command completed successfully"
    elif [[ $exit_code -eq 124 ]]; then
        log_error "Job $job_id timed out after $TIMEOUT"
        emit_error "timeout" "Command timed out after $TIMEOUT"
    else
        log_error "Job $job_id failed with exit code $exit_code"
        emit_error "execution" "Command failed with exit code $exit_code"
    fi

    return $exit_code
}

# Background job management
start_background_job() {
    local job_id
    job_id=$(generate_job_id)

    read -r log_file status_file pid_file exit_file <<< "$(get_job_files "$job_id")"

    # Initialize status file
    emit_status "initializing" 0 "Job queued for execution" > "$status_file"

    # Start job in background
    (
        echo $$ > "$pid_file"
        run_command "$job_id" "${COMMAND_ARGS[@]}"
    ) &

    local bg_pid=$!

    # Wait a moment to ensure the job starts
    sleep 1

    # Return job information as JSON
    cat << EOF
{
  "job_id": "$job_id",
  "pid": $bg_pid,
  "log_file": "$log_file",
  "status_file": "$status_file",
  "started_at": "$(date -Iseconds)"
}
EOF
}

# Check job status
check_job_status() {
    local job_id="$1"
    read -r log_file status_file pid_file exit_file <<< "$(get_job_files "$job_id")"

    if [[ ! -f "$status_file" ]]; then
        echo '{"state":"not_found","error":"Job not found"}'
        return 1
    fi

    local pid=""
    if [[ -f "$pid_file" ]]; then
        pid=$(<"$pid_file")
    fi

    local is_running=false
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        is_running=true
    fi

    local exit_code=""
    if [[ -f "$exit_file" ]]; then
        exit_code=$(<"$exit_file")
    fi

    local last_status=""
    if [[ -f "$status_file" ]]; then
        last_status=$(<"$status_file")
    fi

    local last_lines=""
    if [[ -f "$log_file" ]]; then
        last_lines=$(tail -n 10 "$log_file" | sed 's/"/\\"/g' | tr '\n' '\\n')
    fi

    cat << EOF
{
  "job_id": "$job_id",
  "is_running": $is_running,
  "pid": "$pid",
  "exit_code": "$exit_code",
  "last_status": $last_status,
  "last_lines": "$last_lines",
  "log_file": "$log_file"
}
EOF
}

# Show job logs
show_job_logs() {
    local job_id="$1"
    local lines="${2:-50}"

    read -r log_file status_file pid_file exit_file <<< "$(get_job_files "$job_id")"

    if [[ ! -f "$log_file" ]]; then
        log_error "Log file not found for job $job_id"
        return 1
    fi

    log_info "Showing last $lines lines for job $job_id"
    tail -n "$lines" "$log_file"
}

# Kill job
kill_job() {
    local job_id="$1"
    read -r log_file status_file pid_file exit_file <<< "$(get_job_files "$job_id")"

    if [[ ! -f "$pid_file" ]]; then
        log_error "PID file not found for job $job_id"
        return 1
    fi

    local pid
    pid=$(<"$pid_file")

    if kill -0 "$pid" 2>/dev/null; then
        log_info "Killing job $job_id (PID: $pid)"
        kill -TERM "$pid"
        sleep 2

        if kill -0 "$pid" 2>/dev/null; then
            log_warn "Job didn't respond to TERM, sending KILL"
            kill -KILL "$pid"
        fi

        echo "killed" > "$exit_file"
        emit_error "killed" "Job was manually killed" > "$status_file"

        log_success "Job $job_id killed successfully"
    else
        log_info "Job $job_id is not running"
    fi
}

# Main execution
main() {
    parse_args "$@"
    ensure_job_dir

    # Handle different modes
    if [[ -n "$STATUS_MODE" ]]; then
        check_job_status "$STATUS_MODE"
    elif [[ -n "$LOGS_MODE" ]]; then
        show_job_logs "$LOGS_MODE"
    elif [[ -n "$KILL_MODE" ]]; then
        kill_job "$KILL_MODE"
    elif [[ "$BACKGROUND_MODE" == true ]]; then
        if [[ ${#COMMAND_ARGS[@]} -eq 0 ]]; then
            log_error "No command specified for background execution"
            exit 1
        fi
        start_background_job
    else
        # Direct execution mode
        if [[ ${#COMMAND_ARGS[@]} -eq 0 ]]; then
            log_error "No command specified"
            echo "Usage: $0 [options] -- command [args...]"
            exit 1
        fi

        local job_id
        job_id=$(generate_job_id)
        run_command "$job_id" "${COMMAND_ARGS[@]}"
    fi
}

# Run main function with all arguments
main "$@"
