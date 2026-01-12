#!/bin/bash
#
# Build Signed & Notarized PKG for GetReceipts Daemon
#
# This script:
# 1. Builds the daemon with PyInstaller
# 2. Signs the app bundle with Developer ID Application certificate
# 3. Creates a PKG with postinstall script
# 4. Signs the PKG with Developer ID Installer certificate (working cert)
# 5. Notarizes the PKG with Apple
# 6. Staples the notarization ticket
#
# Requirements:
#   - Python 3.11+ with venv
#   - PyInstaller
#   - Developer ID certificates installed
#   - App-specific password for notarization
#
# Usage:
#   ./build_pkg.sh
#
# Environment Variables:
#   APP_PASSWORD - Apple app-specific password for notarization
#   APPLE_ID - Apple ID email (default: Matt@rainfall.llc)
#   TEAM_ID - Apple Team ID (default: W2AT7M9482)
#

set -e

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
BUILD_DIR="$PROJECT_ROOT/build/daemon_pkg"
DIST_DIR="$PROJECT_ROOT/dist"

# Get version from daemon/__init__.py
VERSION=$(python3 -c "import sys; sys.path.insert(0, '$PROJECT_ROOT'); from daemon import __version__; print(__version__)")

PKG_NAME="GetReceipts-Daemon-${VERSION}.pkg"

# Apple credentials
APPLE_ID="${APPLE_ID:-Matt@rainfall.llc}"
TEAM_ID="${TEAM_ID:-W2AT7M9482}"

# Certificate identities
# Use the working installer certificate explicitly (Oct 2025 cert)
DEV_ID_APP="Developer ID Application: Matthew Seymour Greer (W2AT7M9482)"
DEV_ID_INSTALLER="773033671956B8F6DD90593740863F2E48AD2024"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}==>${NC} $1"
}

error() {
    echo -e "${RED}ERROR:${NC} $1"
    exit 1
}

warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

# Banner
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  GetReceipts Daemon PKG Builder                ║${NC}"
echo -e "${BLUE}║  Version: ${VERSION}                                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Check for app password
if [ -z "$APP_PASSWORD" ]; then
    # Check for stored keychain profile
    if xcrun notarytool history --keychain-profile "Skip-the-Podcast-Notary" >/dev/null 2>&1; then
        log "Using stored notarization credentials"
        USE_KEYCHAIN_PROFILE=true
    else
        echo -e "${YELLOW}Enter app-specific password for notarization:${NC}"
        read -s APP_PASSWORD
        echo ""
        if [ -z "$APP_PASSWORD" ]; then
            error "App-specific password required for notarization"
        fi
        USE_KEYCHAIN_PROFILE=false
    fi
else
    USE_KEYCHAIN_PROFILE=false
fi

# Clean previous builds
log "Cleaning previous builds..."
rm -rf "$BUILD_DIR"
rm -rf "$DIST_DIR/daemon_dist"

# Aggressive Python cache cleaning
log "Cleaning Python bytecode cache..."
find "$PROJECT_ROOT/daemon" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_ROOT/daemon" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$PROJECT_ROOT/daemon" -type f -name "*.pyo" -delete 2>/dev/null || true
find "$PROJECT_ROOT/src" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_ROOT/src" -type f -name "*.pyc" -delete 2>/dev/null || true

# Force PyInstaller cache clear
log "Clearing PyInstaller cache..."
rm -rf ~/.pyinstaller_cache 2>/dev/null || true
rm -rf "$PROJECT_ROOT/.pyinstaller" 2>/dev/null || true

# Kill any running development processes
log "Killing stray daemon processes..."
pkill -9 -f "python.*daemon.main" 2>/dev/null || true
pkill -9 -f "GetReceiptsDaemon" 2>/dev/null || true
sleep 2

mkdir -p "$BUILD_DIR"
mkdir -p "$DIST_DIR"

# Activate virtual environment
log "Activating virtual environment..."
cd "$PROJECT_ROOT"
if [ ! -d "venv" ]; then
    error "Virtual environment not found. Run: python3 -m venv venv && source venv/bin/activate && pip install -e ."
fi
source venv/bin/activate

# Ensure PyInstaller is installed
log "Checking PyInstaller..."
pip install pyinstaller --quiet || error "Failed to install PyInstaller"

# Build daemon executable with PyInstaller
log "Building daemon with PyInstaller..."
pyinstaller installer/daemon.spec \
    --distpath "$DIST_DIR/daemon_dist" \
    --workpath "$BUILD_DIR/build" \
    --clean \
    || error "PyInstaller build failed"

# Verify the app was built
APP_BUNDLE="$DIST_DIR/daemon_dist/GetReceiptsDaemon.app"
if [ ! -d "$APP_BUNDLE" ]; then
    error "App bundle not found at: $APP_BUNDLE"
fi

log "App bundle built: $APP_BUNDLE"

# Sign the app bundle
log "Signing app bundle with Developer ID Application..."
codesign --force --deep --options runtime --timestamp \
    --sign "$DEV_ID_APP" \
    "$APP_BUNDLE" \
    --verbose || error "Code signing failed"

# Verify signature
log "Verifying app signature..."
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE" || error "Signature verification failed"
log "✓ App signature verified"

# Verify built daemon version matches expected version
log "Verifying built daemon version..."
BUILT_BINARY="$DIST_DIR/daemon_dist/GetReceiptsDaemon.app/Contents/MacOS/GetReceiptsDaemon"
BUILT_VERSION=$(strings "$BUILT_BINARY" | grep -E "^__version__\s*=\s*['\"]" | sed -E 's/.*["'\'']([0-9.]+)["'\'']/\1/' | head -1)

if [ -z "$BUILT_VERSION" ]; then
    warning "Could not extract version from binary (may be obfuscated)"
elif [ "$BUILT_VERSION" != "$VERSION" ]; then
    error "Version mismatch! Built: $BUILT_VERSION, Expected: $VERSION
    
This indicates stale cache. Run:
    make clean
    rm -rf build/ dist/
    find daemon/ -name '__pycache__' -exec rm -rf {} +
    
Then rebuild."
else
    log "✓ Version verified: $BUILT_VERSION matches $VERSION"
fi

# Create package root structure
log "Creating package structure..."
PKG_ROOT="$BUILD_DIR/package_root"
mkdir -p "$PKG_ROOT/Applications"
cp -R "$APP_BUNDLE" "$PKG_ROOT/Applications/GetReceipts Daemon.app"

# Ensure postinstall script is executable
chmod +x "$SCRIPT_DIR/scripts/postinstall"

# Build the PKG
log "Building PKG with pkgbuild..."
COMPONENT_PKG="$BUILD_DIR/component.pkg"

pkgbuild \
    --root "$PKG_ROOT" \
    --scripts "$SCRIPT_DIR/scripts" \
    --identifier "org.getreceipts.daemon" \
    --version "$VERSION" \
    --install-location "/" \
    "$COMPONENT_PKG" \
    || error "pkgbuild failed"

log "Component PKG created"

# Create Distribution XML for productbuild
log "Creating distribution package..."
DISTRIBUTION_XML="$BUILD_DIR/Distribution.xml"

cat > "$DISTRIBUTION_XML" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>GetReceipts Daemon</title>
    <organization>org.getreceipts</organization>
    <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
    <options customize="never" require-scripts="true" hostArchitectures="x86_64,arm64"/>
    <welcome file="welcome.html"/>
    <conclusion file="conclusion.html"/>
    <choices-outline>
        <line choice="default"/>
    </choices-outline>
    <choice id="default" title="GetReceipts Daemon" description="Install GetReceipts Local Processor">
        <pkg-ref id="org.getreceipts.daemon"/>
    </choice>
    <pkg-ref id="org.getreceipts.daemon" auth="root">component.pkg</pkg-ref>
</installer-gui-script>
EOF

# Create welcome and conclusion HTML
mkdir -p "$BUILD_DIR/resources"

cat > "$BUILD_DIR/resources/welcome.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
        h1 { color: #1a73e8; }
    </style>
</head>
<body>
    <h1>Welcome to GetReceipts Daemon</h1>
    <p>This installer will set up the GetReceipts local processor on your Mac.</p>
    <p><strong>What it does:</strong></p>
    <ul>
        <li>Installs the daemon to /Applications</li>
        <li>Sets up automatic startup on login</li>
        <li>Creates a desktop restart button</li>
        <li>Starts the daemon immediately</li>
    </ul>
    <p>After installation, visit <strong>getreceipts.org</strong> to start using it!</p>
</body>
</html>
EOF

cat > "$BUILD_DIR/resources/conclusion.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
        h1 { color: #34a853; }
    </style>
</head>
<body>
    <h1>Installation Complete!</h1>
    <p>GetReceipts Daemon has been installed successfully.</p>
    <p><strong>What's next:</strong></p>
    <ul>
        <li>The daemon is now running at <strong>http://localhost:8765</strong></li>
        <li>A restart button has been created on your Desktop</li>
        <li>The daemon will start automatically on login</li>
    </ul>
    <p>Visit <strong><a href="https://getreceipts.org">getreceipts.org</a></strong> to start processing videos!</p>
</body>
</html>
EOF

# Build the final distribution PKG with signing
log "Building signed distribution PKG..."
productbuild \
    --distribution "$DISTRIBUTION_XML" \
    --package-path "$BUILD_DIR" \
    --resources "$BUILD_DIR/resources" \
    --sign "$DEV_ID_INSTALLER" \
    "$DIST_DIR/$PKG_NAME" \
    || error "productbuild failed"

log "✓ PKG created and signed: $DIST_DIR/$PKG_NAME"

# Verify PKG signature
log "Verifying PKG signature..."
pkgutil --check-signature "$DIST_DIR/$PKG_NAME" || warning "PKG signature check failed"

# Create checksum
log "Creating checksum..."
shasum -a 256 "$DIST_DIR/$PKG_NAME" | awk '{print $1}' > "$DIST_DIR/$PKG_NAME.sha256"

# Notarize the PKG
log "Submitting PKG for notarization..."
echo "This may take several minutes..."

if [ "$USE_KEYCHAIN_PROFILE" = true ]; then
    NOTARY_OUTPUT=$(xcrun notarytool submit "$DIST_DIR/$PKG_NAME" \
        --keychain-profile "Skip-the-Podcast-Notary" \
        --wait 2>&1)
else
    NOTARY_OUTPUT=$(xcrun notarytool submit "$DIST_DIR/$PKG_NAME" \
        --apple-id "$APPLE_ID" \
        --team-id "$TEAM_ID" \
        --password "$APP_PASSWORD" \
        --wait 2>&1)
fi

echo "$NOTARY_OUTPUT"

# Check if notarization succeeded
if echo "$NOTARY_OUTPUT" | grep -q "status: Accepted"; then
    log "✓ Notarization successful!"
    
    # Staple the notarization ticket
    log "Stapling notarization ticket..."
    xcrun stapler staple "$DIST_DIR/$PKG_NAME" || warning "Stapling failed (PKG may still work)"
    
    # Verify stapling
    log "Verifying stapled ticket..."
    xcrun stapler validate "$DIST_DIR/$PKG_NAME" || warning "Staple validation failed"
    
    log "✓ PKG is fully notarized and stapled"
else
    error "Notarization failed! Check the output above for details."
fi

# Note: No need for separate stable PKG - GitHub's /releases/latest/download/ 
# automatically points to the latest release's assets

# Cleanup
log "Cleaning up build artifacts..."
rm -rf "$BUILD_DIR"

# Final summary
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Build Complete!                               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}PKG File:${NC}      $DIST_DIR/$PKG_NAME"
echo -e "${BLUE}Size:${NC}          $(du -h "$DIST_DIR/$PKG_NAME" | cut -f1)"
echo -e "${BLUE}Checksum:${NC}      $(cat "$DIST_DIR/$PKG_NAME.sha256")"
echo ""
echo -e "${GREEN}✓${NC} Signed with Developer ID"
echo -e "${GREEN}✓${NC} Notarized by Apple"
echo -e "${GREEN}✓${NC} Stapled for offline verification"
echo -e "${GREEN}✓${NC} Ready for distribution"
echo ""
echo "Upload to GitHub releases:"
echo "  - $PKG_NAME"
echo ""
echo "Website download URL (auto-points to latest):"
echo "  https://github.com/msg43/Skipthepodcast.com/releases/latest/download/$PKG_NAME"
echo ""
