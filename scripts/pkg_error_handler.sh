#!/bin/bash
# pkg_error_handler.sh - Comprehensive error handling for PKG installer
# Implements robust fallback mechanisms and recovery procedures

set -e
set -o pipefail

# Configuration
LOG_FILE="/tmp/skip_the_podcast_install.log"
ERROR_LOG="/tmp/skip_the_podcast_errors.log"
RETRY_ATTEMPTS=3
TIMEOUT_SECONDS=300

# Error codes
ERR_NETWORK=1
ERR_DISK_SPACE=2
ERR_PERMISSIONS=3
ERR_CHECKSUM=4
ERR_EXTRACTION=5
ERR_VERIFICATION=6

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Logging functions
log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1" | tee -a "$LOG_FILE" "$ERROR_LOG"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_FILE" "$ERROR_LOG"
}

# Progress reporting
report_progress() {
    local percent="$1"
    local message="$2"
    echo "##INSTALLER_PROGRESS## $percent $message"
    log_info "Progress: $percent% - $message"
}

# Network connectivity check with fallbacks
check_network_connectivity() {
    local hosts=("github.com" "api.github.com" "8.8.8.8")

    for host in "${hosts[@]}"; do
        if ping -c 1 -W 5000 "$host" &>/dev/null; then
            log_info "Network connectivity verified via $host"
            return 0
        fi
    done

    log_error "No network connectivity detected"
    return $ERR_NETWORK
}

# Disk space verification
check_disk_space() {
    local required_gb="$1"
    local required_kb=$((required_gb * 1024 * 1024))
    local available_kb=$(df / | tail -1 | awk '{print $4}')

    if [ "$available_kb" -lt "$required_kb" ]; then
        log_error "Insufficient disk space. Required: ${required_gb}GB, Available: $((available_kb / 1024 / 1024))GB"
        return $ERR_DISK_SPACE
    fi

    log_info "Disk space check passed: $((available_kb / 1024 / 1024))GB available"
    return 0
}

# Download with retry and fallback
download_with_retry() {
    local url="$1"
    local target="$2"
    local expected_size="$3"
    local attempt=1

    while [ $attempt -le $RETRY_ATTEMPTS ]; do
        log_info "Download attempt $attempt for $(basename "$target")"

        if curl -L --connect-timeout 30 --max-time $TIMEOUT_SECONDS \
                --retry 2 --retry-delay 5 \
                --progress-bar \
                -o "$target" "$url"; then

            # Verify file size if provided
            if [ -n "$expected_size" ]; then
                local actual_size=$(stat -f%z "$target" 2>/dev/null || echo "0")
                local size_diff=$((expected_size - actual_size))
                local size_diff_abs=${size_diff#-}
                local tolerance=$((expected_size / 100))  # 1% tolerance

                if [ $size_diff_abs -gt $tolerance ]; then
                    log_warning "Size mismatch: expected $expected_size, got $actual_size"
                    rm -f "$target"
                    attempt=$((attempt + 1))
                    continue
                fi
            fi

            log_info "Download successful: $(basename "$target")"
            return 0
        fi

        log_warning "Download attempt $attempt failed"
        rm -f "$target"
        attempt=$((attempt + 1))

        if [ $attempt -le $RETRY_ATTEMPTS ]; then
            local delay=$((attempt * 5))
            log_info "Retrying in ${delay}s..."
            sleep $delay
        fi
    done

    log_error "Download failed after $RETRY_ATTEMPTS attempts: $url"
    return $ERR_NETWORK
}

# Checksum verification
verify_checksum() {
    local file="$1"
    local expected_checksum="$2"

    if [ -z "$expected_checksum" ]; then
        log_warning "No checksum provided for $(basename "$file"), skipping verification"
        return 0
    fi

    local actual_checksum=$(shasum -a 256 "$file" | cut -d' ' -f1)

    if [ "$actual_checksum" = "$expected_checksum" ]; then
        log_info "Checksum verified for $(basename "$file")"
        return 0
    else
        log_error "Checksum mismatch for $(basename "$file")"
        log_error "Expected: $expected_checksum"
        log_error "Actual:   $actual_checksum"
        return $ERR_CHECKSUM
    fi
}

# Safe extraction with verification
safe_extract() {
    local archive="$1"
    local target_dir="$2"
    local expected_files="$3"

    log_info "Extracting $(basename "$archive") to $target_dir"

    # Create temporary extraction directory
    local temp_dir
    temp_dir=$(mktemp -d)

    # Extract to temporary directory first
    if tar -xf "$archive" -C "$temp_dir" 2>/dev/null; then
        # Verify expected files exist
        if [ -n "$expected_files" ]; then
            local missing_files=()
            IFS=',' read -ra files <<< "$expected_files"

            for file in "${files[@]}"; do
                if [ ! -e "$temp_dir/$file" ]; then
                    missing_files+=("$file")
                fi
            done

            if [ ${#missing_files[@]} -ne 0 ]; then
                log_error "Missing files after extraction: ${missing_files[*]}"
                rm -rf "$temp_dir"
                return $ERR_EXTRACTION
            fi
        fi

        # Move to final location
        mkdir -p "$target_dir"
        if mv "$temp_dir"/* "$target_dir/"; then
            log_info "Extraction successful"
            rm -rf "$temp_dir"
            return 0
        else
            log_error "Failed to move extracted files"
            rm -rf "$temp_dir"
            return $ERR_EXTRACTION
        fi
    else
        log_error "Extraction failed for $(basename "$archive")"
        rm -rf "$temp_dir"
        return $ERR_EXTRACTION
    fi
}

# Component verification
verify_component() {
    local component_type="$1"
    local component_path="$2"

    case "$component_type" in
        "python_framework")
            local python_exe="$component_path/Versions/3.13/bin/python3.13"
            if [ -x "$python_exe" ] && "$python_exe" -c "import sys; sys.exit(0)" 2>/dev/null; then
                log_info "Python framework verification successful"
                return 0
            else
                log_error "Python framework verification failed"
                return $ERR_VERIFICATION
            fi
            ;;
        "ffmpeg")
            if [ -x "$component_path" ] && "$component_path" -version >/dev/null 2>&1; then
                log_info "FFmpeg verification successful"
                return 0
            else
                log_error "FFmpeg verification failed"
                return $ERR_VERIFICATION
            fi
            ;;
        "ollama")
            if [ -x "$component_path" ] && "$component_path" --version >/dev/null 2>&1; then
                log_info "Ollama verification successful"
                return 0
            else
                log_error "Ollama verification failed"
                return $ERR_VERIFICATION
            fi
            ;;
        "ai_models")
            if [ -f "$component_path/models_manifest.json" ]; then
                log_info "AI models verification successful"
                return 0
            else
                log_error "AI models verification failed"
                return $ERR_VERIFICATION
            fi
            ;;
        *)
            log_warning "Unknown component type: $component_type"
            return 0
            ;;
    esac
}

# Cleanup function for failed installations
cleanup_failed_installation() {
    local app_bundle="$1"

    log_info "Cleaning up failed installation"

    if [ -d "$app_bundle" ]; then
        log_info "Removing incomplete app bundle: $app_bundle"
        rm -rf "$app_bundle"
    fi

    # Clean up temp files
    rm -f /tmp/skip_the_podcast_*
    rm -rf /tmp/stp_installer_*

    log_info "Cleanup completed"
}

# Recovery mode installation
recovery_mode_install() {
    local component="$1"

    log_info "Attempting recovery mode installation for $component"

    case "$component" in
        "python_framework")
            # Try system Python as fallback
            if command -v python3.13 >/dev/null 2>&1; then
                log_info "Using system Python 3.13 as fallback"
                return 0
            elif command -v python3 >/dev/null 2>&1; then
                local version=$(python3 --version | cut -d' ' -f2)
                if [[ $version == 3.1[3-9]* ]]; then
                    log_info "Using system Python $version as fallback"
                    return 0
                fi
            fi
            ;;
        "ollama")
            # Try installing via script
            if curl -fsSL https://ollama.com/install.sh | sh; then
                log_info "Ollama installed via recovery script"
                return 0
            fi
            ;;
    esac

    log_error "Recovery mode failed for $component"
    return 1
}

# Main error handler
handle_installation_error() {
    local error_code="$1"
    local component="$2"
    local app_bundle="$3"

    case "$error_code" in
        $ERR_NETWORK)
            report_progress -1 "Network error - please check internet connection"
            ;;
        $ERR_DISK_SPACE)
            report_progress -1 "Insufficient disk space - please free up space and retry"
            ;;
        $ERR_PERMISSIONS)
            report_progress -1 "Permission error - please run installer as administrator"
            ;;
        $ERR_CHECKSUM)
            report_progress -1 "Download corruption detected - retrying with fresh download"
            ;;
        $ERR_EXTRACTION)
            report_progress -1 "Archive extraction failed - file may be corrupted"
            ;;
        $ERR_VERIFICATION)
            report_progress -1 "Component verification failed - attempting recovery"
            if recovery_mode_install "$component"; then
                return 0
            fi
            ;;
    esac

    # Final cleanup
    cleanup_failed_installation "$app_bundle"

    # Create error report
    cat > "/tmp/skip_the_podcast_error_report.txt" << EOF
Skip the Podcast Desktop Installation Failed

Error Code: $error_code
Component: $component
Timestamp: $(date)

Error Log:
$(tail -20 "$ERROR_LOG" 2>/dev/null || echo "No error log available")

System Information:
- macOS Version: $(sw_vers -productVersion)
- Architecture: $(uname -m)
- Available Disk Space: $(df -h / | tail -1 | awk '{print $4}')
- Python Version: $(python3 --version 2>/dev/null || echo "Not available")

Please check the full log at: $LOG_FILE
EOF

    log_error "Installation failed with error code $error_code"
    return "$error_code"
}

# Export functions for use by installer scripts
export -f log_info log_warning log_error report_progress
export -f check_network_connectivity check_disk_space
export -f download_with_retry verify_checksum safe_extract
export -f verify_component cleanup_failed_installation
export -f recovery_mode_install handle_installation_error
