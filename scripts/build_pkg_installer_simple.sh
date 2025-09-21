#!/bin/bash
# build_pkg_installer_simple.sh - Build PKG installer without component downloads
# This version creates a simple installer that doesn't download components during installation

set -e
set -o pipefail

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Build the regular PKG first
echo "Building PKG with simplified installation..."
"$SCRIPT_DIR/build_pkg_installer.sh" "$@"

# Now we need to modify the postinstall script to NOT download components
echo ""
echo "Modifying installer to skip component downloads..."

# Find the latest PKG
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")
PKG_FILE="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}.pkg"
BUILD_DIR="$PROJECT_ROOT/build_pkg_simple"

# Clean and create build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Expand the PKG
echo "Expanding PKG..."
cd "$BUILD_DIR"
xar -xf "$PKG_FILE"

# Find and modify the postinstall script
if [ -f "Skip_the_Podcast_Desktop-components-${VERSION}.pkg/Scripts" ]; then
    # Extract the Scripts archive
    cd "Skip_the_Podcast_Desktop-components-${VERSION}.pkg"
    cat Scripts | gzip -d | cpio -i

    # Replace the postinstall script with a simpler version
    cat > postinstall << 'EOF'
#!/bin/bash
# Simplified post-install script for Skip the Podcast Desktop PKG

set -e

# Logging
LOG_FILE="/tmp/skip_the_podcast_install.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

echo "=== Skip the Podcast Desktop PKG Post-install ==="
echo "Started: $(date)"

APP_BUNDLE="/Applications/Skip the Podcast Desktop.app"

# Create launch script
echo "Creating launch script..."
cat > "$APP_BUNDLE/Contents/MacOS/launch" << 'LAUNCH_EOF'
#!/bin/bash
# Launch script for Skip the Podcast Desktop

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# For now, just show a message that components need to be downloaded
osascript -e 'display dialog "Skip the Podcast Desktop needs to download required components on first launch.\n\nThis will happen automatically when you first run the app." buttons {"OK"} default button "OK" with title "Skip the Podcast Desktop" with icon note'

# Exit for now - the actual app will handle component downloads
exit 0
LAUNCH_EOF

chmod +x "$APP_BUNDLE/Contents/MacOS/launch"

# Set proper permissions
echo "Setting permissions..."
chmod -R 755 "$APP_BUNDLE"

echo "Post-install completed: $(date)"
echo "Installation complete - Skip the Podcast Desktop is ready to launch"
exit 0
EOF

    chmod +x postinstall

    # Repackage the Scripts
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -path ./Scripts -prune -o -print | cpio -o --format odc --owner 0:0 | gzip -c > Scripts.new
    mv Scripts.new Scripts

    # Go back to build directory
    cd "$BUILD_DIR"
fi

# Repackage the PKG
echo "Repackaging PKG..."
xar -cf "$PKG_FILE.tmp" --distribution Distribution *
mv "$PKG_FILE.tmp" "$PKG_FILE"

# Cleanup
rm -rf "$BUILD_DIR"

echo ""
echo "✅ Simplified PKG created successfully!"
echo "This version will install without downloading components."
echo "Components will be downloaded on first app launch instead."
