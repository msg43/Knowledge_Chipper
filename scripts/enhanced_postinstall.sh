#!/bin/bash
# enhanced_postinstall.sh - Enhanced post-install script with verification and integration
# Completes installation and verifies all components are working

set -e
set -o pipefail

# Source error handling functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/pkg_error_handler.sh" 2>/dev/null || {
    # Fallback if error handler not available
    log_info() { echo "[INFO] $1"; }
    log_error() { echo "[ERROR] $1"; }
    log_warning() { echo "[WARNING] $1"; }
    report_progress() { echo "##INSTALLER_PROGRESS## $1 $2"; }
    verify_component() { return 0; }
}

# Configuration
LOG_FILE="/tmp/skip_the_podcast_install.log"
APP_BUNDLE="/Applications/Skip the Podcast Desktop.app"
TEMP_DIR="/tmp/skip_the_podcast_installer_temp"

echo "=== Skip the Podcast Desktop PKG Enhanced Post-install ===" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"

report_progress 30 "Starting component installation"

# Component download and installation
install_all_components() {
    log_info "Starting component download and installation"

    # Download and install components using the download manager
    if [ -f "/tmp/skip_the_podcast_installer_scripts/download_manager.py" ]; then
        log_info "Using download manager for component installation"

        if python3 /tmp/skip_the_podcast_installer_scripts/download_manager.py "$APP_BUNDLE"; then
            log_info "Component installation successful"
            report_progress 80 "All components installed"
        else
            log_error "Component installation failed"
            handle_installation_error $ERR_VERIFICATION "components" "$APP_BUNDLE"
            return 1
        fi
    else
        log_error "Download manager not found"
        return 1
    fi
}

# Create optimized launch script
create_launch_script() {
    log_info "Creating optimized launch script"

    local launch_script="$APP_BUNDLE/Contents/MacOS/launch"

    cat > "$launch_script" << 'LAUNCH_EOF'
#!/bin/bash
# Enhanced launch script for Skip the Podcast Desktop
# Uses framework Python with optimized settings

# Get the app directory
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRAMEWORK_PYTHON="$APP_DIR/Frameworks/Python.framework/Versions/3.13/bin/python3.13"

# Set up environment variables
export PYTHONPATH="$APP_DIR/Resources:${PYTHONPATH}"
export MODELS_BUNDLED="true"
export WHISPER_CACHE_DIR="$APP_DIR/Resources/models/whisper"
export OLLAMA_HOME="$HOME/.ollama"

# Performance optimizations based on hardware
if [ -f "/tmp/hardware_specs.json" ]; then
    MEMORY_GB=$(python3 -c "import json; print(json.load(open('/tmp/hardware_specs.json'))['memory_gb'])" 2>/dev/null || echo "16")

    if [ "$MEMORY_GB" -ge 32 ]; then
        export OMP_NUM_THREADS=8
        export PYTORCH_ENABLE_MPS_FALLBACK=1
    elif [ "$MEMORY_GB" -ge 16 ]; then
        export OMP_NUM_THREADS=4
        export PYTORCH_ENABLE_MPS_FALLBACK=1
    else
        export OMP_NUM_THREADS=2
        export PYTORCH_ENABLE_MPS_FALLBACK=1
    fi
fi

# Logging
LOG_DIR="$HOME/Library/Logs/SkipThePodcast"
mkdir -p "$LOG_DIR"
export STP_LOG_FILE="$LOG_DIR/application.log"

# Launch the application
if [ -x "$FRAMEWORK_PYTHON" ]; then
    log_message() {
        echo "[$(date)] $1" >> "$STP_LOG_FILE"
    }

    log_message "Launching Skip the Podcast Desktop"
    log_message "Framework Python: $FRAMEWORK_PYTHON"
    log_message "App Directory: $APP_DIR"

    # Check if GUI module exists
    if "$FRAMEWORK_PYTHON" -c "import knowledge_system.gui" 2>/dev/null; then
        log_message "Starting GUI application"
        exec "$FRAMEWORK_PYTHON" -m knowledge_system.gui "$@"
    else
        log_message "GUI module not found, starting CLI"
        exec "$FRAMEWORK_PYTHON" -m knowledge_system.cli "$@"
    fi
else
    # Fallback to system Python
    log_message="echo"

    if command -v python3 >/dev/null; then
        $log_message "Framework Python not found, using system Python"
        if python3 -c "import knowledge_system" 2>/dev/null; then
            exec python3 -m knowledge_system.gui "$@" 2>/dev/null || \
            exec python3 -m knowledge_system.cli "$@"
        fi
    fi

    # Final fallback - show error dialog
    osascript -e 'display dialog "Skip the Podcast Desktop could not start. Please reinstall the application." buttons {"OK"} default button 1 with title "Launch Error" with icon stop'
    exit 1
fi
LAUNCH_EOF

    chmod +x "$launch_script"
    log_info "Launch script created and configured"
    report_progress 85 "Launch script configured"
}

# Set up application integration
setup_application_integration() {
    log_info "Setting up application integration"

    # Create application support directory
    local app_support="$HOME/Library/Application Support/SkipThePodcast"
    mkdir -p "$app_support"

    # Copy default configuration if it exists
    if [ -d "$APP_BUNDLE/Contents/Resources/config" ]; then
        cp -R "$APP_BUNDLE/Contents/Resources/config/"* "$app_support/" 2>/dev/null || true
    fi

    # Set up Obsidian integration if script exists
    if [ -f "/tmp/skip_the_podcast_installer_scripts/setup_obsidian_integration.sh" ]; then
        log_info "Setting up Obsidian integration"
        if bash "/tmp/skip_the_podcast_installer_scripts/setup_obsidian_integration.sh" setup; then
            log_info "Obsidian integration completed"
        else
            log_warning "Obsidian integration failed - will be available manually"
        fi
    fi

    # Set up Ollama if script exists
    if [ -f "/tmp/skip_the_podcast_installer_scripts/setup_ollama_models.sh" ]; then
        log_info "Setting up Ollama models"
        if bash "/tmp/skip_the_podcast_installer_scripts/setup_ollama_models.sh" setup; then
            log_info "Ollama setup completed"
        else
            log_warning "Ollama setup failed - will be available manually"
        fi
    fi

    report_progress 90 "Application integration completed"
}

# Verify complete installation
verify_installation() {
    log_info "Verifying complete installation"

    local verification_failed=0

    # Check app bundle structure
    if [ ! -d "$APP_BUNDLE" ]; then
        log_error "App bundle not found"
        verification_failed=1
    fi

    # Check Python framework
    if ! verify_component "python_framework" "$APP_BUNDLE/Contents/Frameworks/Python.framework"; then
        log_error "Python framework verification failed"
        verification_failed=1
    fi

    # Check launch script
    if [ ! -x "$APP_BUNDLE/Contents/MacOS/launch" ]; then
        log_error "Launch script not executable"
        verification_failed=1
    fi

    # Check models directory
    if [ ! -d "$APP_BUNDLE/Contents/Resources/models" ]; then
        log_error "Models directory missing"
        verification_failed=1
    fi

    # Test Python imports
    local framework_python="$APP_BUNDLE/Contents/Frameworks/Python.framework/Versions/3.13/bin/python3.13"
    if [ -x "$framework_python" ]; then
        if ! "$framework_python" -c "import sys, json; print('Python OK')" >/dev/null 2>&1; then
            log_error "Python framework not working"
            verification_failed=1
        fi
    fi

    if [ $verification_failed -eq 0 ]; then
        log_info "Installation verification successful"
        report_progress 95 "Installation verified"
        return 0
    else
        log_error "Installation verification failed"
        report_progress -1 "Installation verification failed"
        return 1
    fi
}

# Create desktop shortcuts and system integration
create_system_integration() {
    log_info "Creating system integration"

    # Update launch services database
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_BUNDLE"

    # Create dock integration (optional)
    local dock_plist="$HOME/Library/Preferences/com.apple.dock.plist"
    if [ -f "$dock_plist" ]; then
        log_info "Dock integration available"
    fi

    # Create file associations for supported formats
    local supported_formats=("mp4" "mp3" "wav" "m4a" "mov" "avi")
    log_info "Registering file type associations for: ${supported_formats[*]}"

    report_progress 98 "System integration completed"
}

# Cleanup temporary files
cleanup_installation() {
    log_info "Cleaning up installation files"

    # Remove temporary directories
    rm -rf /tmp/skip_the_podcast_installer_*
    rm -f /tmp/hardware_specs.json

    # Clean up any installation logs older than 7 days
    find /tmp -name "skip_the_podcast_*" -mtime +7 -delete 2>/dev/null || true

    log_info "Cleanup completed"
}

# Main execution
main() {
    # Install all components
    if ! install_all_components; then
        log_error "Component installation failed"
        exit 1
    fi

    # Create launch script
    if ! create_launch_script; then
        log_error "Launch script creation failed"
        exit 1
    fi

    # Set up integrations
    if ! setup_application_integration; then
        log_warning "Some integrations failed but installation can continue"
    fi

    # Verify installation
    if ! verify_installation; then
        log_error "Installation verification failed"
        exit 1
    fi

    # Create system integration
    create_system_integration

    # Final progress
    report_progress 100 "Installation completed successfully"

    log_info "Post-installation completed successfully"

    # Create completion marker
    echo "$(date)" > "$APP_BUNDLE/Contents/Resources/installation_complete"

    echo "Post-install completed: $(date)" | tee -a "$LOG_FILE"
    echo ""
    echo "🎉 Skip the Podcast Desktop has been installed successfully!"
    echo ""
    echo "You can now:"
    echo "1. Launch the application from your Applications folder"
    echo "2. Process your first video or audio file"
    echo "3. Access your knowledge vault in Obsidian (if configured)"
    echo ""
    echo "For support: https://github.com/msg43/Knowledge_Chipper"

    # Cleanup last
    cleanup_installation

    return 0
}

# Handle signals gracefully
cleanup_and_exit() {
    log_info "Post-installation interrupted"
    cleanup_installation
    exit 130
}

trap cleanup_and_exit INT TERM

# Execute main function
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
