#!/bin/bash
# sign_installer_simple.sh - Simple ad-hoc signing for the installer app

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")

echo "🔐 Ad-hoc Signing Installer..."
echo "=============================="

# We need to rebuild the installer with signing
BUILD_DIR="$PROJECT_ROOT/build_signed"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Extract the installer app from DMG
DMG_FILE="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}-Installer.dmg"
if [ ! -f "$DMG_FILE" ]; then
    echo "❌ Installer DMG not found. Run create_installer_app.sh first."
    exit 1
fi

echo "Extracting installer app..."
MOUNT_POINT="/tmp/dmg_mount_$$"
mkdir -p "$MOUNT_POINT"
hdiutil attach -nobrowse -mountpoint "$MOUNT_POINT" "$DMG_FILE"
cp -R "$MOUNT_POINT/Skip the Podcast Desktop Installer.app" "$BUILD_DIR/"
hdiutil detach "$MOUNT_POINT"
rmdir "$MOUNT_POINT"

# Ad-hoc sign the app
echo "Signing app..."
codesign --force --deep --sign - "$BUILD_DIR/Skip the Podcast Desktop Installer.app"

# Verify signing
echo "Verifying signature..."
codesign --verify --verbose "$BUILD_DIR/Skip the Podcast Desktop Installer.app"

# Create new DMG
echo "Creating signed DMG..."
ln -s /Applications "$BUILD_DIR/Applications"
hdiutil create -volname "Skip the Podcast Desktop" \
               -srcfolder "$BUILD_DIR" \
               -ov -format UDZO \
               "$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}-Installer-Signed.dmg"

# Cleanup
rm -rf "$BUILD_DIR"

echo ""
echo "✅ Signed installer created!"
echo "Location: dist/Skip_the_Podcast_Desktop-${VERSION}-Installer-Signed.dmg"
echo ""
echo "This reduces warnings but users still need to:"
echo "1. Right-click the installer app"
echo "2. Choose 'Open'"
echo "3. Click 'Open' in the security dialog"
echo ""
echo "For zero warnings, you need a paid Apple Developer account."
