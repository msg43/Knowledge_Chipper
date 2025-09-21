#!/bin/bash
# create_simple_dmg.sh - Create a simple DMG with just the app, no installer

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")
BUILD_DIR="$PROJECT_ROOT/build_dmg"

echo "📀 Creating Simple App DMG"
echo "========================="
echo "Version: $VERSION"
echo ""

# Clean build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# First, build the app bundle
echo "Building app bundle..."
"$SCRIPT_DIR/build_pkg_installer.sh" --prepare-only >/dev/null 2>&1 || {
    echo "❌ Failed to build app bundle"
    exit 1
}

# Copy just the app to DMG staging
echo "Preparing DMG contents..."
cp -R "$PROJECT_ROOT/build_pkg/package_root/Applications/Skip the Podcast Desktop.app" "$BUILD_DIR/"

# Ad-hoc sign the app
echo "Ad-hoc signing app..."
codesign --force --deep --sign - "$BUILD_DIR/Skip the Podcast Desktop.app"

# Create Applications symlink
ln -s /Applications "$BUILD_DIR/Applications"

# Create background directory (optional, for future use)
mkdir -p "$BUILD_DIR/.background"

# Create DMG
echo "Creating DMG..."
DMG_NAME="Skip_the_Podcast_Desktop-${VERSION}.dmg"
hdiutil create -volname "Skip the Podcast Desktop" \
               -srcfolder "$BUILD_DIR" \
               -ov -format UDZO \
               "$PROJECT_ROOT/dist/$DMG_NAME"

# Sign the DMG
echo "Signing DMG..."
codesign --force --sign - "$PROJECT_ROOT/dist/$DMG_NAME"

# Cleanup
rm -rf "$BUILD_DIR"
rm -rf "$PROJECT_ROOT/build_pkg"

# Create checksum
shasum -a 256 "$PROJECT_ROOT/dist/$DMG_NAME" | awk '{print $1}' > "$PROJECT_ROOT/dist/$DMG_NAME.sha256"

echo ""
echo "✅ Simple DMG created!"
echo "Location: dist/$DMG_NAME"
echo "Size: $(du -h "$PROJECT_ROOT/dist/$DMG_NAME" | cut -f1)"
echo ""
echo "This DMG:"
echo "• Contains just the app (no installer)"
echo "• User drags to Applications"
echo "• First launch: right-click → Open"
echo "• Components download on first run"
echo ""
echo "This is how most Mac apps are distributed!"
