#!/bin/bash
# Test script to create a minimal PKG that requires authentication

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_BUILD_DIR="$PROJECT_ROOT/test_auth_build"
VERSION="1.0.0"

echo "Creating minimal test PKG to debug authentication..."

# Clean and create build directories
rm -rf "$TEST_BUILD_DIR"
mkdir -p "$TEST_BUILD_DIR/root/Library/Application Support/TestAuthPkg"
mkdir -p "$TEST_BUILD_DIR/scripts"

# Create a file that goes into a protected location
echo "Test file requiring root access" > "$TEST_BUILD_DIR/root/Library/Application Support/TestAuthPkg/test.txt"

# Create minimal preinstall script
cat > "$TEST_BUILD_DIR/scripts/preinstall" << 'EOF'
#!/bin/bash
echo "Running preinstall script..."
exit 0
EOF
chmod +x "$TEST_BUILD_DIR/scripts/preinstall"

# Build component package WITHOUT custom PackageInfo
echo "Building test package..."
pkgbuild \
    --root "$TEST_BUILD_DIR/root" \
    --identifier "com.test.authpkg" \
    --version "$VERSION" \
    --install-location "/" \
    --scripts "$TEST_BUILD_DIR/scripts" \
    "$TEST_BUILD_DIR/test-auth-component.pkg"

# Create simple distribution
cat > "$TEST_BUILD_DIR/distribution.xml" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1">
    <title>Test Auth Package</title>
    <organization>com.test</organization>
    <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
    <options customize="never" require-scripts="true" rootVolumeOnly="true"/>

    <choices-outline>
        <line choice="default">
            <line choice="com.test.authpkg"/>
        </line>
    </choices-outline>

    <choice id="default"/>
    <choice id="com.test.authpkg" visible="false">
        <pkg-ref id="com.test.authpkg"/>
    </choice>

    <pkg-ref id="com.test.authpkg" version="$VERSION" auth="root">#test-auth-component.pkg</pkg-ref>
</installer-gui-script>
EOF

# Build final package
productbuild \
    --distribution "$TEST_BUILD_DIR/distribution.xml" \
    --package-path "$TEST_BUILD_DIR" \
    "$PROJECT_ROOT/dist/test-auth.pkg"

echo ""
echo "Test package created: $PROJECT_ROOT/dist/test-auth.pkg"
echo ""
echo "This minimal package:"
echo "- Installs to /Library/Application Support/ (requires root)"
echo "- Has auth=\"root\" in pkg-ref"
echo "- Has rootVolumeOnly=\"true\""
echo ""
echo "Try installing this to see if it prompts for authentication."
