#!/bin/bash
# Create a .pkg installer that bypasses some Gatekeeper checks
# This provides a more professional installation experience

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
APP_NAME="Skip the Podcast Desktop"
APP_PATH="$SCRIPT_DIR/.app_build/$APP_NAME.app"
PKG_NAME="SkipThePodcastDesktop"
VERSION=$(grep '^version =' "$PROJECT_ROOT/pyproject.toml" | cut -d'"' -f2)

echo "📦 Creating .pkg installer for $APP_NAME v$VERSION"
echo "================================================"

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "❌ App not found at: $APP_PATH"
    echo "Run build_macos_app.sh first"
    exit 1
fi

# Create temporary directory for package building
PKG_ROOT="/tmp/skip_the_podcast_pkg_$$"
mkdir -p "$PKG_ROOT/Applications"
mkdir -p "$PKG_ROOT/usr/local/bin"

# Copy app to package root
echo "📋 Copying app to package structure..."
cp -R "$APP_PATH" "$PKG_ROOT/Applications/"

# Create a command-line launcher
echo "🔧 Creating command-line launcher..."
cat > "$PKG_ROOT/usr/local/bin/skip-the-podcast" << 'EOF'
#!/bin/bash
open -a "Skip the Podcast Desktop" "$@"
EOF
chmod +x "$PKG_ROOT/usr/local/bin/skip-the-podcast"

# Create post-install script that removes quarantine
mkdir -p "$SCRIPT_DIR/.pkg_scripts"
cat > "$SCRIPT_DIR/.pkg_scripts/postinstall" << 'EOF'
#!/bin/bash
# Post-installation script

echo "🔧 Completing Skip the Podcast Desktop installation..."

# Remove quarantine attribute from the app
if [ -d "/Applications/Skip the Podcast Desktop.app" ]; then
    xattr -dr com.apple.quarantine "/Applications/Skip the Podcast Desktop.app" 2>/dev/null || true
    echo "✅ Removed quarantine attributes"
fi

# Create launch services entry
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "/Applications/Skip the Podcast Desktop.app" 2>/dev/null || true

# Touch the app to update its timestamp
touch "/Applications/Skip the Podcast Desktop.app"

echo "✅ Installation complete!"

# Create a marker for successful installation
touch "$HOME/.skip_the_podcast_installed_via_pkg"

exit 0
EOF
chmod +x "$SCRIPT_DIR/.pkg_scripts/postinstall"

# Create pre-install script to check requirements
cat > "$SCRIPT_DIR/.pkg_scripts/preinstall" << 'EOF'
#!/bin/bash
# Pre-installation script

echo "🔍 Checking installation requirements..."

# Check macOS version
OS_VERSION=$(sw_vers -productVersion)
OS_MAJOR=$(echo "$OS_VERSION" | cut -d. -f1)
OS_MINOR=$(echo "$OS_VERSION" | cut -d. -f2)

if [ "$OS_MAJOR" -lt 11 ]; then
    echo "❌ This app requires macOS 11.0 or later"
    echo "   Your version: $OS_VERSION"
    exit 1
fi

# Check if app is running
if pgrep -x "Skip the Podcast Desktop" > /dev/null; then
    echo "⚠️  Skip the Podcast Desktop is currently running"
    echo "   Please quit the app before installing"
    osascript -e 'tell application "Skip the Podcast Desktop" to quit'
    sleep 2
fi

echo "✅ Requirements check passed"
exit 0
EOF
chmod +x "$SCRIPT_DIR/.pkg_scripts/preinstall"

# Create package info
cat > "$SCRIPT_DIR/.pkg_scripts/PackageInfo" << EOF
<?xml version="1.0" encoding="utf-8"?>
<pkg-info overwrite-permissions="true" followSymLinks="false" format-version="2" generator-version="InstallCmds-821" install-location="/" auth="root">
    <payload installKBytes="$(du -sk "$PKG_ROOT" | awk '{print $1}')" numberOfFiles="$(find "$PKG_ROOT" -type f | wc -l)"/>
    <bundle-version>
        <bundle id="com.skipthepodcast.desktop" CFBundleVersion="$VERSION" path="Applications/Skip the Podcast Desktop.app"/>
    </bundle-version>
    <scripts>
        <preinstall file="./preinstall"/>
        <postinstall file="./postinstall"/>
    </scripts>
</pkg-info>
EOF

# Build the package
echo "🏗️  Building installer package..."
pkgbuild \
    --root "$PKG_ROOT" \
    --scripts "$SCRIPT_DIR/.pkg_scripts" \
    --identifier "com.skipthepodcast.desktop" \
    --version "$VERSION" \
    --install-location "/" \
    "$SCRIPT_DIR/${PKG_NAME}-${VERSION}.pkg"

# Create a distribution XML for a more professional installer
cat > "$SCRIPT_DIR/.pkg_scripts/distribution.xml" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Skip the Podcast Desktop</title>
    <organization>com.skipthepodcast</organization>
    <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
    <options customize="never" require-scripts="true" hostArchitectures="x86_64,arm64"/>
    <license file="LICENSE.txt"/>
    <readme file="README.txt"/>
    <background file="background.png" alignment="bottomleft" scaling="none"/>
    <choices-outline>
        <line choice="default">
            <line choice="com.skipthepodcast.desktop"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="com.skipthepodcast.desktop" visible="false">
        <pkg-ref id="com.skipthepodcast.desktop"/>
    </choice>
    <pkg-ref id="com.skipthepodcast.desktop" version="$VERSION" onConclusion="none">SkipThePodcastDesktop-${VERSION}.pkg</pkg-ref>
</installer-gui-script>
EOF

# Create README for installer
cat > "$SCRIPT_DIR/.pkg_scripts/README.txt" << EOF
Skip the Podcast Desktop v$VERSION
=================================

Thank you for installing Skip the Podcast Desktop!

What will be installed:
• Skip the Podcast Desktop.app → /Applications
• Command-line tool → /usr/local/bin/skip-the-podcast

After installation:
1. Find "Skip the Podcast Desktop" in your Applications folder
2. Double-click to launch
3. If prompted about security, click "Open"

The installer automatically handles macOS security settings for you.

For more information, visit: https://github.com/skipthepodcast/desktop
EOF

# Clean up
echo "🧹 Cleaning up..."
rm -rf "$PKG_ROOT"

echo ""
echo "✅ Package created successfully!"
echo "📦 Output: $SCRIPT_DIR/${PKG_NAME}-${VERSION}.pkg"
echo ""
echo "📝 Package benefits:"
echo "   • Professional installation experience"
echo "   • Automatic quarantine removal"
echo "   • Registers with Launch Services"
echo "   • Shows in Applications immediately"
echo "   • Less likely to trigger Gatekeeper"
echo ""
echo "🚀 Users can install with:"
echo "   1. Double-click the .pkg file"
echo "   2. Follow the installer prompts"
echo "   3. App launches without security warnings*"
echo ""
echo "   *Note: The .pkg itself may show a security warning if not notarized"
