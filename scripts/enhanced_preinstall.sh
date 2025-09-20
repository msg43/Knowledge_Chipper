#!/bin/bash
# enhanced_preinstall.sh - Enhanced pre-install script with comprehensive error handling
# Performs all pre-installation checks and preparations with robust error recovery

set -e
set -o pipefail

# Source error handling functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/pkg_error_handler.sh" 2>/dev/null || {
    # Fallback if error handler not available
    log_info() { echo "[INFO] $1"; }
    log_error() { echo "[ERROR] $1"; }
    report_progress() { echo "##INSTALLER_PROGRESS## $1 $2"; }
    check_network_connectivity() { ping -c 1 github.com >/dev/null 2>&1; }
    check_disk_space() {
        local required_gb="$1"
        local available_gb=$(df / | tail -1 | awk '{print int($4/1024/1024)}')
        [ "$available_gb" -ge "$required_gb" ]
    }
}

# Configuration
LOG_FILE="/tmp/skip_the_podcast_install.log"
REQUIRED_SPACE_GB=8
MIN_MACOS_VERSION="12.0"

echo "=== Skip the Podcast Desktop PKG Enhanced Pre-install ==="
echo "Started: $(date)" | tee "$LOG_FILE"

report_progress 0 "Starting installation validation"

# System compatibility check
check_system_compatibility() {
    log_info "Checking system compatibility"

    # Check macOS version
    local macos_version=$(sw_vers -productVersion)
    local major_version=$(echo "$macos_version" | cut -d. -f1)
    local minor_version=$(echo "$macos_version" | cut -d. -f2)

    if [ "$major_version" -lt 12 ] || ([ "$major_version" -eq 12 ] && [ "$minor_version" -lt 0 ]); then
        log_error "macOS $MIN_MACOS_VERSION or later required. Found: $macos_version"
        report_progress -1 "Incompatible macOS version"
        exit 1
    fi

    log_info "macOS version check passed: $macos_version"

    # Check architecture
    local arch=$(uname -m)
    if [[ "$arch" != "arm64" && "$arch" != "x86_64" ]]; then
        log_error "Unsupported architecture: $arch"
        report_progress -1 "Unsupported system architecture"
        exit 1
    fi

    log_info "Architecture check passed: $arch"

    # Check if running in recovery mode or safe mode
    if [ -n "$(nvram -p | grep boot-args | grep -E '(single|safe)')" ]; then
        log_error "Installation not supported in recovery or safe mode"
        report_progress -1 "System in recovery/safe mode"
        exit 1
    fi

    log_info "System mode check passed"
}

# Security and permissions check
check_security_permissions() {
    log_info "Checking security and permissions"

    # Check if installer is running with admin privileges
    if [ "$EUID" -ne 0 ]; then
        log_error "Installation requires administrator privileges"
        report_progress -1 "Administrator privileges required"
        exit 3
    fi

    # Check System Integrity Protection status
    local sip_status=$(csrutil status 2>/dev/null | grep -o "enabled\|disabled" || echo "unknown")
    log_info "System Integrity Protection: $sip_status"

    # Check if Applications directory is writable
    if [ ! -w "/Applications" ]; then
        log_error "Applications directory is not writable"
        report_progress -1 "Cannot write to Applications directory"
        exit 3
    fi

    log_info "Permissions check passed"
}

# Hardware requirements check
check_hardware_requirements() {
    log_info "Checking hardware requirements"

    # Check available memory
    local memory_gb=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)}')
    local min_memory_gb=4

    if [ "$memory_gb" -lt "$min_memory_gb" ]; then
        log_error "Insufficient memory: ${memory_gb}GB (minimum: ${min_memory_gb}GB)"
        report_progress -1 "Insufficient system memory"
        exit 2
    fi

    log_info "Memory check passed: ${memory_gb}GB available"

    # Check CPU cores
    local cpu_cores=$(sysctl -n hw.ncpu)
    local min_cores=2

    if [ "$cpu_cores" -lt "$min_cores" ]; then
        log_error "Insufficient CPU cores: $cpu_cores (minimum: $min_cores)"
        report_progress -1 "Insufficient CPU cores"
        exit 2
    fi

    log_info "CPU check passed: $cpu_cores cores"
}

# Network and connectivity check
check_network_requirements() {
    log_info "Checking network connectivity"

    if ! check_network_connectivity; then
        log_error "No internet connection available"
        report_progress -1 "Internet connection required"
        exit 1
    fi

    report_progress 10 "Internet connectivity verified"

    # Test GitHub API access
    if ! curl -s --connect-timeout 10 "https://api.github.com/repos/msg43/Knowledge_Chipper/releases/latest" >/dev/null; then
        log_error "Cannot access GitHub releases"
        report_progress -1 "Cannot access component downloads"
        exit 1
    fi

    log_info "GitHub access verified"
}

# Storage requirements check
check_storage_requirements() {
    log_info "Checking storage requirements"

    if ! check_disk_space "$REQUIRED_SPACE_GB"; then
        local available_gb=$(df / | tail -1 | awk '{print int($4/1024/1024)}')
        log_error "Insufficient disk space: ${available_gb}GB (required: ${REQUIRED_SPACE_GB}GB)"
        report_progress -1 "Insufficient disk space - please free up space"
        exit 2
    fi

    report_progress 15 "Disk space check passed"

    # Check for existing installation
    if [ -d "/Applications/Skip the Podcast Desktop.app" ]; then
        log_info "Existing installation found - will be replaced"

        # Check if app is currently running
        if pgrep -f "Skip the Podcast Desktop" >/dev/null; then
            log_error "Skip the Podcast Desktop is currently running"
            report_progress -1 "Please quit the application before installing"
            exit 1
        fi
    fi
}

# Dependency check
check_system_dependencies() {
    log_info "Checking system dependencies"

    # Check for required system frameworks
    local required_frameworks=(
        "/System/Library/Frameworks/Foundation.framework"
        "/System/Library/Frameworks/AppKit.framework"
        "/System/Library/Frameworks/CoreServices.framework"
    )

    for framework in "${required_frameworks[@]}"; do
        if [ ! -d "$framework" ]; then
            log_error "Missing system framework: $framework"
            report_progress -1 "System frameworks missing"
            exit 1
        fi
    done

    # Check for system Python (as fallback)
    if ! command -v python3 >/dev/null; then
        log_warning "System Python 3 not found - will use bundled Python"
    else
        local py_version=$(python3 --version | cut -d' ' -f2)
        log_info "System Python available: $py_version"
    fi

    log_info "System dependencies check passed"
}

# Hardware detection and optimization
perform_hardware_detection() {
    log_info "Performing hardware detection"

    # Run hardware detection
    python3 - << 'HARDWARE_EOF' > /tmp/hardware_specs.json 2>/dev/null || {
        log_warning "Hardware detection failed, using defaults"
        echo '{"chip_name": "unknown", "memory_gb": 16}' > /tmp/hardware_specs.json
    }
import subprocess
import json
import sys

def detect_hardware():
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {"chip_name": "unknown", "memory_gb": 16}

        data = json.loads(result.stdout)
        hardware_info = data["SPHardwareDataType"][0]

        chip_name = hardware_info.get("chip_type", "").lower()
        memory_str = hardware_info.get("physical_memory", "16 GB")
        memory_gb = int(memory_str.split()[0])

        return {"chip_name": chip_name, "memory_gb": memory_gb}

    except Exception:
        return {"chip_name": "unknown", "memory_gb": 16}

specs = detect_hardware()
print(json.dumps(specs))
HARDWARE_EOF

    if [ -f "/tmp/hardware_specs.json" ]; then
        local chip=$(python3 -c "import json; print(json.load(open('/tmp/hardware_specs.json'))['chip_name'])")
        local memory=$(python3 -c "import json; print(json.load(open('/tmp/hardware_specs.json'))['memory_gb'])")
        log_info "Hardware detected: $chip, ${memory}GB RAM"
        report_progress 20 "Hardware optimization configured"
    fi
}

# Create installation environment
prepare_installation_environment() {
    log_info "Preparing installation environment"

    # Create temporary directories
    mkdir -p /tmp/skip_the_podcast_installer_temp
    mkdir -p /tmp/skip_the_podcast_installer_scripts

    # Set proper permissions
    chmod 755 /tmp/skip_the_podcast_installer_*

    # Copy installer scripts if available
    local installer_scripts_dir="$1"
    if [ -d "$installer_scripts_dir" ]; then
        cp -R "$installer_scripts_dir"/* /tmp/skip_the_podcast_installer_scripts/
        chmod +x /tmp/skip_the_podcast_installer_scripts/*.py 2>/dev/null || true
    fi

    report_progress 25 "Installation environment prepared"
}

# Main execution
main() {
    local installer_scripts_dir="$1"

    # Run all pre-installation checks
    check_system_compatibility
    report_progress 5 "System compatibility verified"

    check_security_permissions
    report_progress 8 "Security permissions verified"

    check_hardware_requirements
    report_progress 12 "Hardware requirements satisfied"

    check_network_requirements
    # Progress reported within function

    check_storage_requirements
    # Progress reported within function

    check_system_dependencies
    report_progress 18 "System dependencies verified"

    perform_hardware_detection
    # Progress reported within function

    prepare_installation_environment "$installer_scripts_dir"
    # Progress reported within function

    # Final validation
    log_info "All pre-installation checks passed"
    report_progress 30 "Pre-installation validation complete"

    echo "Pre-install completed successfully: $(date)" | tee -a "$LOG_FILE"
    return 0
}

# Handle signals gracefully
cleanup_and_exit() {
    log_info "Installation interrupted by user"
    rm -rf /tmp/skip_the_podcast_installer_*
    exit 130
}

trap cleanup_and_exit INT TERM

# Execute main function
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
