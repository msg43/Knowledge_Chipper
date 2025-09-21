#!/bin/bash
# build_simple_packages.sh - Simplified Packages.app build

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")

echo "📦 Simple Packages.app Build"
echo "==========================="
echo "Version: $VERSION"
echo ""

# First build the regular PKG
echo "Building app bundle..."
"$SCRIPT_DIR/build_pkg_installer.sh" --prepare-only

# Now let's just use the native productbuild with signing
echo ""
echo "Creating signed installer package..."
PKG_FILE="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}.pkg"

# Sign the app bundle first
echo "Ad-hoc signing app bundle..."
codesign --force --deep --sign - "$PROJECT_ROOT/build_pkg/package_root/Applications/Skip the Podcast Desktop.app"

# Create a simple installer that always requires auth
echo "Building installer package..."
pkgbuild --root "$PROJECT_ROOT/build_pkg/package_root" \
         --scripts "$PROJECT_ROOT/build_pkg/scripts" \
         --identifier "com.knowledgechipper.skipthepodcast" \
         --version "$VERSION" \
         --install-location "/" \
         --ownership preserve \
         "$PKG_FILE.tmp"

# Create distribution with explicit auth requirement
cat > "$PROJECT_ROOT/build_pkg/Distribution.xml" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Skip the Podcast Desktop</title>
    <organization>com.knowledgechipper</organization>
    <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
    <options customize="never" require-scripts="true" rootVolumeOnly="true"/>
    <choices-outline>
        <line choice="default"/>
    </choices-outline>
    <choice id="default" title="Skip the Podcast Desktop" description="Install Skip the Podcast Desktop">
        <pkg-ref id="com.knowledgechipper.skipthepodcast"/>
    </choice>
    <pkg-ref id="com.knowledgechipper.skipthepodcast" auth="root">Skip_the_Podcast_Desktop-${VERSION}.pkg.tmp</pkg-ref>
</installer-gui-script>
EOF

# Build distribution package
productbuild --distribution "$PROJECT_ROOT/build_pkg/Distribution.xml" \
             --package-path "$(dirname "$PKG_FILE.tmp")" \
             --resources "$PROJECT_ROOT/build_pkg/resources" \
             "$PKG_FILE"

# Cleanup
rm -f "$PKG_FILE.tmp"
rm -rf "$PROJECT_ROOT/build_pkg"

# Create checksum
shasum -a 256 "$PKG_FILE" | awk '{print $1}' > "$PKG_FILE.sha256"

echo ""
echo "✅ Installer package created!"
echo "Location: $PKG_FILE"
echo "Size: $(du -h "$PKG_FILE" | cut -f1)"
echo ""
echo "This package:"
echo "• Has ad-hoc signed app (reduces warnings)"
echo "• Requires root authentication"
echo "• Professional installer experience"
