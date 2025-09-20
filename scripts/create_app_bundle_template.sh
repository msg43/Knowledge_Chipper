#!/bin/bash
# create_app_bundle_template.sh - Create optimized app bundle template for PKG installer
# Replaces complex DMG approach with clean framework-based structure

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")

# App configuration
APP_NAME="Skip the Podcast Desktop"
BUNDLE_ID="com.knowledgechipper.skipthepodcast"
BUILD_DIR="$PROJECT_ROOT/build_app_template"
TEMPLATE_DIR="$BUILD_DIR/app_template"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}🏗️ App Bundle Template Creator${NC}"
echo "===================================="
echo "Creating optimized app bundle structure for PKG installer"
echo "Version: $VERSION"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

# Clean and create build directories
echo -e "${BLUE}📁 Setting up build environment...${NC}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$TEMPLATE_DIR"

print_status "Build directories created"

# Create app bundle structure
echo -e "\n${BLUE}🏗️ Creating app bundle structure...${NC}"

APP_BUNDLE="$TEMPLATE_DIR/$APP_NAME.app"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"
mkdir -p "$APP_BUNDLE/Contents/Frameworks"
mkdir -p "$APP_BUNDLE/Contents/Helpers"

print_status "App bundle structure created"

# Create Info.plist with enhanced configuration
echo -e "\n${BLUE}📄 Creating Info.plist...${NC}"

cat > "$APP_BUNDLE/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>launch</string>
    <key>CFBundleIconFile</key>
    <string>app_icon</string>
    <key>CFBundleIconName</key>
    <string>app_icon</string>
    <key>CFBundleIdentifier</key>
    <string>$BUNDLE_ID</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.productivity</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
        <key>NSExceptionDomains</key>
        <dict>
            <key>github.com</key>
            <dict>
                <key>NSExceptionAllowsInsecureHTTPLoads</key>
                <true/>
                <key>NSExceptionMinimumTLSVersion</key>
                <string>TLSv1.0</string>
            </dict>
            <key>huggingface.co</key>
            <dict>
                <key>NSExceptionAllowsInsecureHTTPLoads</key>
                <true/>
            </dict>
        </dict>
    </dict>
    <key>NSAppleEventsUsageDescription</key>
    <string>Skip the Podcast Desktop uses Apple Events to integrate with other applications.</string>
    <key>NSDocumentsFolderUsageDescription</key>
    <string>Skip the Podcast Desktop needs access to your Documents folder to save processed knowledge files.</string>
    <key>NSDesktopFolderUsageDescription</key>
    <string>Skip the Podcast Desktop can save processed files to your Desktop.</string>
    <key>NSDownloadsFolderUsageDescription</key>
    <string>Skip the Podcast Desktop can process files from your Downloads folder.</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Skip the Podcast Desktop can record audio for transcription.</string>
    <key>NSCameraUsageDescription</key>
    <string>Skip the Podcast Desktop can capture video for processing.</string>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>mp4</string>
                <string>mov</string>
                <string>avi</string>
                <string>mkv</string>
                <string>m4v</string>
            </array>
            <key>CFBundleTypeIconFile</key>
            <string>video_icon</string>
            <key>CFBundleTypeName</key>
            <string>Video File</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSHandlerRank</key>
            <string>Alternate</string>
            <key>LSTypeIsPackage</key>
            <false/>
        </dict>
        <dict>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>mp3</string>
                <string>wav</string>
                <string>m4a</string>
                <string>aac</string>
                <string>flac</string>
            </array>
            <key>CFBundleTypeIconFile</key>
            <string>audio_icon</string>
            <key>CFBundleTypeName</key>
            <string>Audio File</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSHandlerRank</key>
            <string>Alternate</string>
            <key>LSTypeIsPackage</key>
            <false/>
        </dict>
        <dict>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>pdf</string>
            </array>
            <key>CFBundleTypeIconFile</key>
            <string>pdf_icon</string>
            <key>CFBundleTypeName</key>
            <string>PDF Document</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSHandlerRank</key>
            <string>Alternate</string>
            <key>LSTypeIsPackage</key>
            <false/>
        </dict>
    </array>
    <key>UTExportedTypeDeclarations</key>
    <array>
        <dict>
            <key>UTTypeConformsTo</key>
            <array>
                <string>public.data</string>
            </array>
            <key>UTTypeDescription</key>
            <string>Skip the Podcast Knowledge File</string>
            <key>UTTypeIdentifier</key>
            <string>com.knowledgechipper.knowledge</string>
            <key>UTTypeTagSpecification</key>
            <dict>
                <key>public.filename-extension</key>
                <array>
                    <string>stpk</string>
                </array>
            </dict>
        </dict>
    </array>
</dict>
</plist>
EOF

print_status "Info.plist created with comprehensive configuration"

# Copy application icons if available
echo -e "\n${BLUE}🎨 Setting up application icons...${NC}"

# Check for existing icons in the project
ICON_SOURCES=(
    "$PROJECT_ROOT/Assets/chipper.icns"
    "$PROJECT_ROOT/Assets/chipper.png"
    "$PROJECT_ROOT/Assets/STP_Icon_1.png"
)

ICON_FOUND=0
for icon_source in "${ICON_SOURCES[@]}"; do
    if [ -f "$icon_source" ]; then
        echo "Found icon: $icon_source"

        if [[ "$icon_source" == *.icns ]]; then
            cp "$icon_source" "$APP_BUNDLE/Contents/Resources/app_icon.icns"
        else
            # Convert to ICNS if possible
            if command -v sips >/dev/null 2>&1; then
                sips -s format icns "$icon_source" --out "$APP_BUNDLE/Contents/Resources/app_icon.icns" 2>/dev/null || {
                    cp "$icon_source" "$APP_BUNDLE/Contents/Resources/app_icon.png"
                }
            else
                cp "$icon_source" "$APP_BUNDLE/Contents/Resources/app_icon.png"
            fi
        fi
        ICON_FOUND=1
        break
    fi
done

if [ $ICON_FOUND -eq 0 ]; then
    print_warning "No application icons found - using system default"
fi

print_status "Application icons configured"

# Create resources structure
echo -e "\n${BLUE}📦 Creating resources structure...${NC}"

# Create models directory structure
mkdir -p "$APP_BUNDLE/Contents/Resources/models/whisper"
mkdir -p "$APP_BUNDLE/Contents/Resources/models/voice_fingerprinting"
mkdir -p "$APP_BUNDLE/Contents/Resources/models/pyannote"

# Create config directory
mkdir -p "$APP_BUNDLE/Contents/Resources/config"

# Copy existing config if available
if [ -d "$PROJECT_ROOT/config" ]; then
    # Copy example configs
    cp "$PROJECT_ROOT/config/settings.example.yaml" "$APP_BUNDLE/Contents/Resources/config/" 2>/dev/null || true
    cp "$PROJECT_ROOT/config/credentials.example.yaml" "$APP_BUNDLE/Contents/Resources/config/" 2>/dev/null || true

    # Copy prompts if available
    if [ -d "$PROJECT_ROOT/config/prompts" ]; then
        cp -R "$PROJECT_ROOT/config/prompts" "$APP_BUNDLE/Contents/Resources/config/" 2>/dev/null || true
    fi
fi

# Create templates directory
mkdir -p "$APP_BUNDLE/Contents/Resources/templates"

# Create cache directories
mkdir -p "$APP_BUNDLE/Contents/Resources/cache"

print_status "Resources structure created"

# Create framework-optimized launch script template
echo -e "\n${BLUE}🚀 Creating framework-optimized launch script...${NC}"

cat > "$APP_BUNDLE/Contents/MacOS/launch" << 'LAUNCH_EOF'
#!/bin/bash
# Framework-optimized launch script for Skip the Podcast Desktop
# Uses bundled Python framework with complete isolation

# Get absolute path to app bundle
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRAMEWORK_DIR="$APP_DIR/Frameworks"
PYTHON_FRAMEWORK="$FRAMEWORK_DIR/Python.framework"
PYTHON_BIN="$PYTHON_FRAMEWORK/Versions/3.13/bin/python3.13"

# Logging setup
LOG_DIR="$HOME/Library/Logs/SkipThePodcast"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/launch.log"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log_message "=== Starting Skip the Podcast Desktop ==="
log_message "App Directory: $APP_DIR"
log_message "Framework Python: $PYTHON_BIN"

# Environment setup for framework isolation
export PYTHONHOME="$PYTHON_FRAMEWORK/Versions/3.13"
export PYTHONPATH="$APP_DIR/Resources:$PYTHON_FRAMEWORK/Versions/3.13/lib/python3.13/site-packages"
export DYLD_LIBRARY_PATH="$PYTHON_FRAMEWORK/Versions/3.13/lib:$DYLD_LIBRARY_PATH"
export DYLD_FRAMEWORK_PATH="$FRAMEWORK_DIR:$DYLD_FRAMEWORK_PATH"

# Application-specific environment
export STP_APP_DIR="$APP_DIR"
export STP_RESOURCES_DIR="$APP_DIR/Resources"
export STP_CONFIG_DIR="$APP_DIR/Resources/config"
export STP_MODELS_DIR="$APP_DIR/Resources/models"
export STP_CACHE_DIR="$APP_DIR/Resources/cache"
export STP_LOG_DIR="$LOG_DIR"

# Model paths
export WHISPER_CACHE_DIR="$STP_MODELS_DIR/whisper"
export PYANNOTE_CACHE="$STP_MODELS_DIR/pyannote"
export VOICE_MODELS_DIR="$STP_MODELS_DIR/voice_fingerprinting"

# Performance optimizations
export OMP_NUM_THREADS="$(sysctl -n hw.ncpu)"
export PYTORCH_ENABLE_MPS_FALLBACK=1
export TOKENIZERS_PARALLELISM=false

# Hardware-specific optimizations
MEMORY_GB=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)}')
if [ "$MEMORY_GB" -ge 32 ]; then
    export STP_PERFORMANCE_MODE="high"
    export OMP_NUM_THREADS=8
elif [ "$MEMORY_GB" -ge 16 ]; then
    export STP_PERFORMANCE_MODE="balanced"
    export OMP_NUM_THREADS=4
else
    export STP_PERFORMANCE_MODE="conservative"
    export OMP_NUM_THREADS=2
fi

log_message "Performance mode: $STP_PERFORMANCE_MODE (${MEMORY_GB}GB RAM)"

# Check framework Python
if [ ! -x "$PYTHON_BIN" ]; then
    log_message "ERROR: Framework Python not found at $PYTHON_BIN"

    # Show user-friendly error dialog
    osascript << 'APPLESCRIPT'
display dialog "Skip the Podcast Desktop installation is incomplete. The Python framework is missing.

Please reinstall the application using the PKG installer." \
buttons {"Quit", "Download Installer"} \
default button "Download Installer" \
with title "Installation Error" \
with icon stop

if button returned of result is "Download Installer" then
    open location "https://github.com/msg43/Knowledge_Chipper/releases/latest"
end if
APPLESCRIPT
    exit 1
fi

# Verify Python framework
log_message "Verifying Python framework..."
if ! "$PYTHON_BIN" -c "import sys; print(f'Python {sys.version}'); sys.exit(0)" >> "$LOG_FILE" 2>&1; then
    log_message "ERROR: Python framework verification failed"

    osascript -e 'display dialog "Python framework verification failed. Please reinstall the application." buttons {"OK"} default button 1 with title "Framework Error" with icon stop'
    exit 1
fi

log_message "Python framework verified successfully"

# Check for knowledge_system module
log_message "Checking for knowledge_system module..."
if ! "$PYTHON_BIN" -c "import knowledge_system; print(f'Knowledge System version: {knowledge_system.__version__}')" >> "$LOG_FILE" 2>&1; then
    log_message "ERROR: knowledge_system module not found"

    # Try to install from local resources
    if [ -f "$APP_DIR/Resources/knowledge_system" ] || [ -d "$APP_DIR/Resources/knowledge_system" ]; then
        log_message "Installing knowledge_system from resources..."
        PYTHONPATH="$APP_DIR/Resources:$PYTHONPATH" "$PYTHON_BIN" -c "import knowledge_system" >> "$LOG_FILE" 2>&1 || {
            log_message "ERROR: Failed to import knowledge_system from resources"
            osascript -e 'display dialog "Application modules are missing. Please reinstall the application." buttons {"OK"} default button 1 with title "Module Error" with icon stop'
            exit 1
        }
    else
        log_message "ERROR: knowledge_system module not found in resources"
        osascript -e 'display dialog "Application modules are missing. Please reinstall the application." buttons {"OK"} default button 1 with title "Module Error" with icon stop'
        exit 1
    fi
fi

log_message "Knowledge system module verified"

# Launch the application
log_message "Launching application..."

# Determine launch mode
LAUNCH_MODE="gui"
for arg in "$@"; do
    case "$arg" in
        --cli|cli)
            LAUNCH_MODE="cli"
            break
            ;;
        --help|-h)
            LAUNCH_MODE="help"
            break
            ;;
    esac
done

log_message "Launch mode: $LAUNCH_MODE"

# Launch based on mode
case "$LAUNCH_MODE" in
    "cli")
        log_message "Starting CLI mode"
        exec "$PYTHON_BIN" -m knowledge_system.cli "${@:2}"
        ;;
    "help")
        log_message "Showing help"
        "$PYTHON_BIN" -m knowledge_system.cli --help
        ;;
    "gui"|*)
        log_message "Starting GUI mode"
        # Check if GUI dependencies are available
        if "$PYTHON_BIN" -c "import PyQt6" >> "$LOG_FILE" 2>&1; then
            exec "$PYTHON_BIN" -m knowledge_system.gui "$@"
        else
            log_message "GUI dependencies not available, falling back to CLI"
            exec "$PYTHON_BIN" -m knowledge_system.cli "$@"
        fi
        ;;
esac
LAUNCH_EOF

chmod +x "$APP_BUNDLE/Contents/MacOS/launch"

print_status "Launch script created and configured"

# Create helper scripts
echo -e "\n${BLUE}🔧 Creating helper scripts...${NC}"

# CLI launcher
cat > "$APP_BUNDLE/Contents/Helpers/cli_launcher" << 'CLI_EOF'
#!/bin/bash
# CLI mode launcher
exec "$(dirname "${BASH_SOURCE[0]}")/../MacOS/launch" --cli "$@"
CLI_EOF
chmod +x "$APP_BUNDLE/Contents/Helpers/cli_launcher"

# Diagnostic script
cat > "$APP_BUNDLE/Contents/Helpers/diagnostics" << 'DIAG_EOF'
#!/bin/bash
# Diagnostic script for troubleshooting

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$APP_DIR/Frameworks/Python.framework/Versions/3.13/bin/python3.13"

echo "=== Skip the Podcast Desktop Diagnostics ==="
echo "Date: $(date)"
echo "macOS Version: $(sw_vers -productVersion)"
echo "Architecture: $(uname -m)"
echo "Memory: $(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)')}GB"
echo ""

echo "=== App Bundle Check ==="
echo "App Directory: $APP_DIR"
echo "Bundle exists: $([ -d "$APP_DIR" ] && echo "✅ Yes" || echo "❌ No")"
echo "Python framework: $([ -x "$PYTHON_BIN" ] && echo "✅ Found" || echo "❌ Missing")"
echo "Launch script: $([ -x "$APP_DIR/MacOS/launch" ] && echo "✅ Found" || echo "❌ Missing")"
echo ""

if [ -x "$PYTHON_BIN" ]; then
    echo "=== Python Framework Check ==="
    "$PYTHON_BIN" --version
    "$PYTHON_BIN" -c "import sys; print(f'Python path: {sys.executable}')"
    "$PYTHON_BIN" -c "import sys; print(f'Python paths: {sys.path[:3]}...')"
    echo ""

    echo "=== Module Check ==="
    for module in "knowledge_system" "PyQt6" "torch" "transformers"; do
        if "$PYTHON_BIN" -c "import $module; print(f'✅ $module: OK')" 2>/dev/null; then
            echo "✅ $module: Available"
        else
            echo "❌ $module: Missing"
        fi
    done
fi

echo ""
echo "=== Log Files ==="
LOG_DIR="$HOME/Library/Logs/SkipThePodcast"
if [ -d "$LOG_DIR" ]; then
    echo "Log directory: $LOG_DIR"
    ls -la "$LOG_DIR" 2>/dev/null || echo "No log files found"
else
    echo "Log directory not found"
fi

echo ""
echo "Diagnostics complete. Please share this output when reporting issues."
DIAG_EOF
chmod +x "$APP_BUNDLE/Contents/Helpers/diagnostics"

print_status "Helper scripts created"

# Create packaging script
echo -e "\n${BLUE}📦 Creating packaging script...${NC}"

cat > "$BUILD_DIR/package_app_template.sh" << 'PACKAGE_EOF'
#!/bin/bash
# Package the app template for distribution

TEMPLATE_DIR="$(dirname "${BASH_SOURCE[0]}")/app_template"
OUTPUT_DIR="$(dirname "${BASH_SOURCE[0]}")/../dist"

mkdir -p "$OUTPUT_DIR"

echo "📦 Creating app template archive..."
cd "$(dirname "$TEMPLATE_DIR")"
tar -czf "$OUTPUT_DIR/app_template.tar.gz" "$(basename "$TEMPLATE_DIR")"

echo "✅ App template packaged: $OUTPUT_DIR/app_template.tar.gz"
echo "Size: $(du -h "$OUTPUT_DIR/app_template.tar.gz" | cut -f1)"
PACKAGE_EOF

chmod +x "$BUILD_DIR/package_app_template.sh"

print_status "Packaging script created"

# Create documentation
echo -e "\n${BLUE}📚 Creating documentation...${NC}"

cat > "$BUILD_DIR/README.md" << 'README_EOF'
# Skip the Podcast Desktop App Bundle Template

This directory contains the optimized app bundle template for the PKG installer.

## Structure

```
Skip the Podcast Desktop.app/
├── Contents/
│   ├── Info.plist                 # App configuration and file associations
│   ├── MacOS/
│   │   └── launch                 # Framework-optimized launch script
│   ├── Resources/
│   │   ├── models/               # AI models (installed by PKG)
│   │   ├── config/               # Application configuration
│   │   ├── templates/            # Note templates
│   │   └── cache/                # Application cache
│   ├── Frameworks/
│   │   └── Python.framework/     # Isolated Python runtime (installed by PKG)
│   └── Helpers/
│       ├── cli_launcher          # CLI mode launcher
│       └── diagnostics           # Diagnostic script
```

## Features

- **Complete Python Isolation**: Framework-based Python with no system conflicts
- **Optimized Launch Script**: Hardware-aware performance optimization
- **File Associations**: Supports video, audio, and PDF processing
- **Error Handling**: Comprehensive error detection and user feedback
- **Diagnostics**: Built-in troubleshooting tools
- **Multi-mode Support**: GUI and CLI launch modes

## Integration with PKG Installer

The PKG installer will:
1. Install this app bundle skeleton
2. Download and install the Python framework
3. Download and install AI models
4. Configure hardware-optimized settings
5. Set up system integrations

## Testing

Use the diagnostic script to verify installation:
```bash
./Skip\ the\ Podcast\ Desktop.app/Contents/Helpers/diagnostics
```

## Maintenance

This template eliminates the need for:
- Complex Python detection logic
- Permission workarounds
- Environment variable management
- System Python conflicts
- Manual dependency installation
README_EOF

print_status "Documentation created"

# Final summary
echo -e "\n${GREEN}${BOLD}🎉 App Bundle Template Complete!${NC}"
echo "=============================================="
echo "Template Location: $APP_BUNDLE"
echo "Template Size: $(du -sh "$TEMPLATE_DIR" | cut -f1)"
echo ""
echo "Features implemented:"
echo "• Framework-based Python isolation"
echo "• Hardware-optimized launch script"
echo "• Comprehensive file associations"
echo "• Built-in error handling and diagnostics"
echo "• Multi-mode support (GUI/CLI)"
echo "• Complete resource structure"
echo ""
echo "To package template:"
echo "  $BUILD_DIR/package_app_template.sh"
echo ""
echo "Template ready for PKG installer integration!"
