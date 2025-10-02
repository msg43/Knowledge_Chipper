#!/bin/bash

# Cursor Job Manager - Simplified interface for managing background jobs
# Usage: ./cursor_job_manager.sh [command] [args...]

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_SCRIPT="$SCRIPT_DIR/cursor_tool_wrapper.sh"
JOB_DIR="/tmp/cursor_jobs"

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

# List all jobs
list_jobs() {
    log_info "Active Cursor jobs:"

    if [[ ! -d "$JOB_DIR" ]]; then
        log_warn "No job directory found. No jobs have been created yet."
        return 0
    fi

    local found_jobs=false

    for pid_file in "$JOB_DIR"/*.pid; do
        if [[ ! -f "$pid_file" ]]; then
            continue
        fi

        local job_id
        job_id=$(basename "$pid_file" .pid)

        local status_output
        status_output=$("$WRAPPER_SCRIPT" --status="$job_id" 2>/dev/null || echo '{"state":"error"}')

        local is_running
        is_running=$(echo "$status_output" | grep -o '"is_running":[^,}]*' | cut -d: -f2 || echo "false")

        local pid
        pid=$(echo "$status_output" | grep -o '"pid":"[^"]*"' | cut -d: -f2 | tr -d '"' || echo "unknown")

        if [[ "$is_running" == "true" ]]; then
            echo -e "  ${GREEN}●${NC} $job_id (PID: $pid) - Running"
        else
            echo -e "  ${RED}○${NC} $job_id (PID: $pid) - Stopped"
        fi

        found_jobs=true
    done

    if [[ "$found_jobs" == false ]]; then
        log_info "No jobs found."
    fi
}

# Start a new background job
start_job() {
    if [[ $# -eq 0 ]]; then
        log_error "No command specified for background job"
        echo "Usage: $0 start -- command [args...]"
        return 1
    fi

    log_info "Starting background job with command: $*"

    local job_info
    job_info=$("$WRAPPER_SCRIPT" --background -- "$@")

    local job_id
    job_id=$(echo "$job_info" | grep -o '"job_id":"[^"]*"' | cut -d: -f2 | tr -d '"')

    log_success "Started job: $job_id"
    echo "$job_info" | jq . 2>/dev/null || echo "$job_info"

    echo
    log_info "Use these commands to monitor the job:"
    echo "  Status: $0 status $job_id"
    echo "  Logs:   $0 logs $job_id"
    echo "  Kill:   $0 kill $job_id"
}

# Check job status with auto-refresh
monitor_job() {
    local job_id="$1"
    local refresh_interval="${2:-5}"

    log_info "Monitoring job $job_id (refreshing every ${refresh_interval}s). Press Ctrl+C to stop."

    while true; do
        clear
        echo "=== Job Monitor: $job_id ==="
        echo "Refresh interval: ${refresh_interval}s"
        echo "Time: $(date)"
        echo

        local status_output
        status_output=$("$WRAPPER_SCRIPT" --status="$job_id" 2>/dev/null || echo '{"state":"error"}')

        echo "Status:"
        echo "$status_output" | jq . 2>/dev/null || echo "$status_output"

        echo
        echo "Recent logs:"
        "$WRAPPER_SCRIPT" --logs="$job_id" 2>/dev/null | tail -n 15 || echo "No logs available"

        local is_running
        is_running=$(echo "$status_output" | grep -o '"is_running":[^,}]*' | cut -d: -f2 || echo "false")

        if [[ "$is_running" != "true" ]]; then
            echo
            log_info "Job has finished. Final status above."
            break
        fi

        sleep "$refresh_interval"
    done
}

# Show usage
show_usage() {
    cat << EOF
Cursor Job Manager - Manage long-running background jobs

Usage: $0 [command] [args...]

Commands:
  list                    List all jobs
  start -- <command>      Start a new background job
  status <job_id>         Check status of a job
  logs <job_id> [lines]   Show job logs (default: 50 lines)
  monitor <job_id> [interval]  Monitor job with auto-refresh (default: 5s)
  kill <job_id>           Kill a running job
  cleanup                 Remove old job files

Examples:
  $0 list
  $0 start -- python long_running_script.py
  $0 start -- make build
  $0 monitor job_1234567890_12345
  $0 logs job_1234567890_12345 100
  $0 kill job_1234567890_12345

The background jobs will continue running even if this terminal closes.
Job files are stored in: $JOB_DIR
EOF
}

# Cleanup old job files
cleanup_jobs() {
    log_info "Cleaning up old job files..."

    if [[ ! -d "$JOB_DIR" ]]; then
        log_info "No job directory found. Nothing to clean up."
        return 0
    fi

    local cleaned_count=0

    for pid_file in "$JOB_DIR"/*.pid; do
        if [[ ! -f "$pid_file" ]]; then
            continue
        fi

        local job_id
        job_id=$(basename "$pid_file" .pid)

        local pid
        if pid=$(<"$pid_file"); then
            if ! kill -0 "$pid" 2>/dev/null; then
                log_info "Cleaning up job $job_id (PID $pid no longer running)"
                rm -f "$JOB_DIR/$job_id".*
                ((cleaned_count++))
            fi
        fi
    done

    # Also clean up files older than 7 days
    find "$JOB_DIR" -name "job_*" -mtime +7 -delete 2>/dev/null || true

    log_success "Cleaned up $cleaned_count old job files"
}

# Main command dispatcher
main() {
    if [[ $# -eq 0 ]]; then
        show_usage
        return 0
    fi

    local command="$1"
    shift

    case "$command" in
        list|ls)
            list_jobs
            ;;
        start)
            if [[ $# -gt 0 && "$1" == "--" ]]; then
                shift
            fi
            start_job "$@"
            ;;
        status)
            if [[ $# -eq 0 ]]; then
                log_error "Job ID required"
                echo "Usage: $0 status <job_id>"
                return 1
            fi
            "$WRAPPER_SCRIPT" --status="$1" | jq . 2>/dev/null || "$WRAPPER_SCRIPT" --status="$1"
            ;;
        logs)
            if [[ $# -eq 0 ]]; then
                log_error "Job ID required"
                echo "Usage: $0 logs <job_id> [lines]"
                return 1
            fi
            local lines="${2:-50}"
            "$WRAPPER_SCRIPT" --logs="$1" "$lines"
            ;;
        monitor)
            if [[ $# -eq 0 ]]; then
                log_error "Job ID required"
                echo "Usage: $0 monitor <job_id> [interval]"
                return 1
            fi
            monitor_job "$1" "${2:-5}"
            ;;
        kill|stop)
            if [[ $# -eq 0 ]]; then
                log_error "Job ID required"
                echo "Usage: $0 kill <job_id>"
                return 1
            fi
            "$WRAPPER_SCRIPT" --kill="$1"
            ;;
        cleanup|clean)
            cleanup_jobs
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown command: $command"
            echo
            show_usage
            return 1
            ;;
    esac
}

main "$@"
