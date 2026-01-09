#!/bin/bash
#
# Build DMG Installer for GetReceipts Daemon
#
# This script:
# 1. Builds the daemon with PyInstaller
# 2. Creates a DMG with the installer
#
# Requirements:
#   - Python 3.11+ with venv
#   - PyInstaller
#   - create-dmg (brew install create-dmg)
#
# Usage:
#   ./build_dmg.sh
#

set -e

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
BUILD_DIR="$PROJECT_ROOT/build/daemon"
DIST_DIR="$PROJECT_ROOT/dist"
DMG_NAME="GetReceiptsInstaller"
VERSION="1.0.0"

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

log() {
    echo -e "${GREEN}=>${NC} $1"
}

# Clean previous builds
log "Cleaning previous builds..."
rm -rf "$BUILD_DIR"
rm -rf "$DIST_DIR/daemon_dist"
rm -f "$DIST_DIR/$DMG_NAME.dmg"

# Activate virtual environment
log "Activating virtual environment..."
cd "$PROJECT_ROOT"
source venv/bin/activate

# Ensure PyInstaller is installed
log "Checking PyInstaller..."
pip install pyinstaller --quiet

# Build daemon executable
log "Building daemon with PyInstaller..."
pyinstaller installer/daemon.spec --distpath "$DIST_DIR/daemon_dist" --workpath "$BUILD_DIR"

# Create staging directory for DMG
log "Staging DMG contents..."
DMG_STAGING="$BUILD_DIR/dmg_staging"
mkdir -p "$DMG_STAGING"

# Copy installer components
cp "$DIST_DIR/daemon_dist/GetReceiptsDaemon" "$DMG_STAGING/" 2>/dev/null || \
    cp -R "$DIST_DIR/daemon_dist/GetReceiptsDaemon.app" "$DMG_STAGING/"
cp "$SCRIPT_DIR/install.sh" "$DMG_STAGING/"
cp "$SCRIPT_DIR/org.getreceipts.daemon.plist" "$DMG_STAGING/"

# Create README for DMG
cat > "$DMG_STAGING/README.txt" << 'EOF'
GetReceipts Local Processor
===========================

This installer sets up the GetReceipts daemon for local video processing.

INSTALLATION:
1. Double-click "install.sh" (or run it in Terminal)
2. The daemon will start automatically

WHAT IT DOES:
- Runs a local server on port 8765
- Processes YouTube videos on your Mac
- Uploads extracted claims to GetReceipts.org

AFTER INSTALLATION:
- Open "GetReceipts" in your Applications folder
- Or visit https://getreceipts.org/contribute

UNINSTALL:
- Run: ./install.sh --uninstall

EOF

# Check if create-dmg is available
if command -v create-dmg &> /dev/null; then
    log "Creating DMG with create-dmg..."
    create-dmg \
        --volname "GetReceipts Installer" \
        --volicon "$PROJECT_ROOT/Assets/icon.icns" 2>/dev/null || true \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --hide-extension "install.sh" \
        --app-drop-link 425 175 \
        "$DIST_DIR/$DMG_NAME-$VERSION.dmg" \
        "$DMG_STAGING"
else
    # Fallback: use hdiutil
    log "Creating DMG with hdiutil..."
    hdiutil create \
        -volname "GetReceipts Installer" \
        -srcfolder "$DMG_STAGING" \
        -ov \
        -format UDZO \
        "$DIST_DIR/$DMG_NAME-$VERSION.dmg"
fi

log "DMG created: $DIST_DIR/$DMG_NAME-$VERSION.dmg"

# Package daemon binary separately for GitHub releases (auto-update)
log "Packaging daemon binary for auto-update..."
DAEMON_PACKAGE="$DIST_DIR/GetReceiptsDaemon-${VERSION}-macos.tar.gz"
cd "$DIST_DIR/daemon_dist"
if [ -f "GetReceiptsDaemon" ]; then
    tar -czf "$DAEMON_PACKAGE" GetReceiptsDaemon
    log "Daemon package created: $DAEMON_PACKAGE"
elif [ -d "GetReceiptsDaemon.app" ]; then
    tar -czf "$DAEMON_PACKAGE" GetReceiptsDaemon.app
    log "Daemon app package created: $DAEMON_PACKAGE"
else
    log "Warning: Could not find daemon binary to package"
fi
cd "$PROJECT_ROOT"

# Cleanup
log "Cleaning up..."
rm -rf "$DMG_STAGING"

echo ""
echo "=========================================="
echo "  Build Complete!"
echo "=========================================="
echo ""
echo "DMG: $DIST_DIR/$DMG_NAME-$VERSION.dmg"
echo "Daemon Package: $DAEMON_PACKAGE"
echo ""
echo "To test locally:"
echo "  1. Mount the DMG"
echo "  2. Run install.sh"
echo "  3. Visit http://localhost:8765/docs"
echo ""
echo "For GitHub release:"
echo "  Upload both $DMG_NAME-$VERSION.dmg and GetReceiptsDaemon-${VERSION}-macos.tar.gz"
echo ""

