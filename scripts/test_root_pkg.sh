#!/bin/bash
# test_root_pkg.sh - Create an absolutely minimal PKG that MUST require root

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/test_root_build"
DIST_DIR="$PROJECT_ROOT/dist"

echo "Creating minimal test PKG that absolutely requires root..."

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/root/usr/local/bin"
mkdir -p "$BUILD_DIR/scripts"

# Create a test binary that goes to /usr/local/bin (requires root)
echo '#!/bin/bash
echo "Test command installed successfully"' > "$BUILD_DIR/root/usr/local/bin/test-root-pkg"
chmod +x "$BUILD_DIR/root/usr/local/bin/test-root-pkg"

# Create preinstall script
cat > "$BUILD_DIR/scripts/preinstall" << 'EOF'
#!/bin/bash
echo "Installing to /usr/local/bin (requires root)"
exit 0
EOF
chmod +x "$BUILD_DIR/scripts/preinstall"

# Build component package with explicit ownership
pkgbuild \
    --root "$BUILD_DIR/root" \
    --identifier "com.test.rootpkg" \
    --version "1.0.0" \
    --install-location "/" \
    --scripts "$BUILD_DIR/scripts" \
    --ownership preserve \
    "$BUILD_DIR/test-root.pkg"

# Create distribution with all the flags
cat > "$BUILD_DIR/distribution.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Test Root Package</title>
    <organization>com.test</organization>
    <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
    <options customize="never" require-scripts="true" rootVolumeOnly="true" hostArchitectures="x86_64,arm64"/>
    <background file="background.png" mime-type="image/png"/>
    <choices-outline>
        <line choice="default">
            <line choice="com.test.rootpkg"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="com.test.rootpkg" visible="false">
        <pkg-ref id="com.test.rootpkg"/>
    </choice>
    <pkg-ref id="com.test.rootpkg" version="1.0.0" auth="root">test-root.pkg</pkg-ref>
</installer-gui-script>
EOF

# Build final package
productbuild \
    --distribution "$BUILD_DIR/distribution.xml" \
    --package-path "$BUILD_DIR" \
    "$DIST_DIR/test-root-minimal.pkg"

echo ""
echo "Test package created: $DIST_DIR/test-root-minimal.pkg"
echo ""
echo "This package installs to /usr/local/bin which:"
echo "- Has permissions: drwxr-xr-x root:wheel"
echo "- ONLY root can write to it"
echo "- Should absolutely require authentication"
echo ""
echo "Try installing this package to see if it prompts for auth."
