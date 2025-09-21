#!/bin/bash
# test_system_pkg.sh - Create a PKG that writes to system directories

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/test_system_build"
DIST_DIR="$PROJECT_ROOT/dist"

echo "Creating test PKG that writes to system directories..."

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/root/Library/LaunchDaemons"
mkdir -p "$BUILD_DIR/scripts"

# Create a launch daemon (requires root to install)
cat > "$BUILD_DIR/root/Library/LaunchDaemons/com.test.daemon.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.test.daemon</string>
    <key>Disabled</key>
    <true/>
</dict>
</plist>
EOF

# Set correct ownership and permissions
chmod 644 "$BUILD_DIR/root/Library/LaunchDaemons/com.test.daemon.plist"

# Create preinstall script
cat > "$BUILD_DIR/scripts/preinstall" << 'EOF'
#!/bin/bash
echo "Installing system daemon (requires root)"
exit 0
EOF
chmod +x "$BUILD_DIR/scripts/preinstall"

# Build with explicit settings
pkgbuild \
    --root "$BUILD_DIR/root" \
    --identifier "com.test.system" \
    --version "1.0.0" \
    --install-location "/" \
    --scripts "$BUILD_DIR/scripts" \
    --ownership preserve \
    "$BUILD_DIR/test-system.pkg"

# Create distribution requiring root
cat > "$BUILD_DIR/distribution.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Test System Package</title>
    <organization>com.test</organization>
    <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
    <options customize="never" require-scripts="true" rootVolumeOnly="true"/>
    <choices-outline>
        <line choice="default">
            <line choice="com.test.system"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="com.test.system" visible="false">
        <pkg-ref id="com.test.system"/>
    </choice>
    <pkg-ref id="com.test.system" version="1.0.0" auth="root">test-system.pkg</pkg-ref>
</installer-gui-script>
EOF

productbuild \
    --distribution "$BUILD_DIR/distribution.xml" \
    --package-path "$BUILD_DIR" \
    "$DIST_DIR/test-system.pkg"

echo ""
echo "Test package created: $DIST_DIR/test-system.pkg"
echo ""
echo "This package installs to /Library/LaunchDaemons which:"
echo "- Has permissions: drwxr-xr-x root:wheel"
echo "- ONLY root can write to it"
echo "- Is a critical system directory"
echo ""
echo "If this doesn't prompt for auth, something is very wrong."
