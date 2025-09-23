#!/bin/bash
# build_signed_notarized_pkg.sh - Build, sign, notarize, and staple PKG installer
# Requires Apple Developer account and certificates

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}🔐 Signed & Notarized PKG Builder${NC}"
echo "===================================="
echo "Version: $VERSION"
echo ""

# Print status functions
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

# Check for required environment variables or find certificates
if [ -z "$DEVELOPER_ID_INSTALLER" ]; then
    echo "Finding Developer ID Installer certificate..."
    # Check if we have a specific keychain path (from GitHub Actions)
    if [ -n "$RUNNER_TEMP" ] && [ -f "$RUNNER_TEMP/build.keychain" ]; then
        DEVELOPER_ID_INSTALLER=$(security find-identity -v -p codesigning "$RUNNER_TEMP/build.keychain" | grep "Developer ID Installer" | head -1 | awk -F'"' '{print $2}')
    else
        DEVELOPER_ID_INSTALLER=$(security find-identity -v -p codesigning | grep "Developer ID Installer" | head -1 | awk -F'"' '{print $2}')
    fi
    if [ -z "$DEVELOPER_ID_INSTALLER" ]; then
        print_error "No Developer ID Installer certificate found"
        echo "Please install your Developer ID Installer certificate in Keychain"
        exit 1
    fi
    echo "Found: $DEVELOPER_ID_INSTALLER"
fi

if [ -z "$DEVELOPER_ID_APPLICATION" ]; then
    echo "Finding Developer ID Application certificate..."
    # Check if we have a specific keychain path (from GitHub Actions)
    if [ -n "$RUNNER_TEMP" ] && [ -f "$RUNNER_TEMP/build.keychain" ]; then
        DEVELOPER_ID_APPLICATION=$(security find-identity -v -p codesigning "$RUNNER_TEMP/build.keychain" | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
    else
        DEVELOPER_ID_APPLICATION=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
    fi
    if [ -z "$DEVELOPER_ID_APPLICATION" ]; then
        print_error "No Developer ID Application certificate found"
        echo "Please install your Developer ID Application certificate in Keychain"
        exit 1
    fi
    echo "Found: $DEVELOPER_ID_APPLICATION"
fi

# Prompt for notarization credentials if not set
if [ -z "$APPLE_ID" ]; then
    read -p "Enter your Apple ID email: " APPLE_ID
fi

if [ -z "$APPLE_TEAM_ID" ]; then
    read -p "Enter your Team ID (found in developer.apple.com): " APPLE_TEAM_ID
fi

if [ -z "$APP_PASSWORD" ]; then
    echo "You need an app-specific password for notarization"
    echo "Create one at: https://appleid.apple.com/account/manage"
    read -s -p "Enter app-specific password: " APP_PASSWORD
    echo
fi

# Store credentials in keychain for future use (optional)
echo ""
read -p "Store credentials in keychain for future use? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    xcrun notarytool store-credentials "Skip-the-Podcast-Notary" \
        --apple-id "$APPLE_ID" \
        --team-id "$APPLE_TEAM_ID" \
        --password "$APP_PASSWORD"
    NOTARY_PROFILE="Skip-the-Podcast-Notary"
fi

# Build the app bundle first
echo -e "\n${BLUE}📦 Building app bundle...${NC}"
"$SCRIPT_DIR/build_pkg_installer.sh" --prepare-only

# Sign the app bundle
echo -e "\n${BLUE}🔏 Signing app bundle...${NC}"
APP_BUNDLE="$PROJECT_ROOT/build_pkg/package_root/Applications/Skip the Podcast Desktop.app"

# Sign all frameworks and dylibs first (if any)
find "$APP_BUNDLE" -name "*.dylib" -o -name "*.framework" | while read -r item; do
    echo "Signing: $(basename "$item")"
    codesign --force --options runtime --timestamp --sign "$DEVELOPER_ID_APPLICATION" "$item"
done

# Sign the main app
codesign --force --options runtime --timestamp --sign "$DEVELOPER_ID_APPLICATION" --deep "$APP_BUNDLE"

# Verify app signature
echo -e "\n${BLUE}🔍 Verifying app signature...${NC}"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"
print_status "App bundle signed successfully"

# Build the component package
echo -e "\n${BLUE}📦 Building component package...${NC}"
COMPONENT_PKG="$PROJECT_ROOT/build_pkg/component.pkg"
pkgbuild --root "$PROJECT_ROOT/build_pkg/package_root" \
         --scripts "$PROJECT_ROOT/build_pkg/scripts" \
         --identifier "com.knowledgechipper.skipthepodcast" \
         --version "$VERSION" \
         --install-location "/" \
         --sign "$DEVELOPER_ID_INSTALLER" \
         "$COMPONENT_PKG"

print_status "Component package built and signed"

# Build the distribution package
echo -e "\n${BLUE}📦 Building distribution package...${NC}"
PKG_FILE="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}.pkg"

# Create distribution XML with proper settings
cat > "$PROJECT_ROOT/build_pkg/Distribution.xml" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Skip the Podcast Desktop</title>
    <organization>com.knowledgechipper</organization>
    <domains enable_anywhere="true" enable_currentUserHome="false" enable_localSystem="true"/>
    <options customize="never" require-scripts="true" hostArchitectures="x86_64,arm64"/>
    <choices-outline>
        <line choice="default"/>
    </choices-outline>
    <choice id="default" title="Skip the Podcast Desktop" description="Install Skip the Podcast Desktop">
        <pkg-ref id="com.knowledgechipper.skipthepodcast"/>
    </choice>
    <pkg-ref id="com.knowledgechipper.skipthepodcast" auth="root">component.pkg</pkg-ref>
</installer-gui-script>
EOF

productbuild --distribution "$PROJECT_ROOT/build_pkg/Distribution.xml" \
             --package-path "$PROJECT_ROOT/build_pkg" \
             --resources "$PROJECT_ROOT/build_pkg/resources" \
             --sign "$DEVELOPER_ID_INSTALLER" \
             "$PKG_FILE"

print_status "Distribution package built and signed"

# Create checksum
shasum -a 256 "$PKG_FILE" | awk '{print $1}' > "$PKG_FILE.sha256"

# Notarize the package
echo -e "\n${BLUE}📤 Submitting package for notarization...${NC}"
echo "This may take several minutes..."

if [ -n "$NOTARY_PROFILE" ]; then
    NOTARY_OUTPUT=$(xcrun notarytool submit "$PKG_FILE" \
        --keychain-profile "$NOTARY_PROFILE" \
        --wait 2>&1)
else
    NOTARY_OUTPUT=$(xcrun notarytool submit "$PKG_FILE" \
        --apple-id "$APPLE_ID" \
        --team-id "$APPLE_TEAM_ID" \
        --password "$APP_PASSWORD" \
        --wait 2>&1)
fi

echo "$NOTARY_OUTPUT"

# Check if notarization succeeded
if echo "$NOTARY_OUTPUT" | grep -q "status: Accepted"; then
    print_status "Notarization successful!"

    # Staple the notarization ticket
    echo -e "\n${BLUE}📎 Stapling notarization ticket...${NC}"
    xcrun stapler staple "$PKG_FILE"
    print_status "Notarization ticket stapled"

    # Verify the stapling
    echo -e "\n${BLUE}🔍 Verifying notarization...${NC}"
    xcrun stapler validate "$PKG_FILE"
    print_status "Package is properly notarized and stapled"
else
    print_error "Notarization failed!"
    echo "Check the notarization log for details"

    # Extract submission ID for log retrieval
    SUBMISSION_ID=$(echo "$NOTARY_OUTPUT" | grep -o 'id: [a-z0-9-]*' | head -1 | cut -d' ' -f2)
    if [ -n "$SUBMISSION_ID" ]; then
        echo "Getting notarization log..."
        if [ -n "$NOTARY_PROFILE" ]; then
            xcrun notarytool log "$SUBMISSION_ID" --keychain-profile "$NOTARY_PROFILE"
        else
            xcrun notarytool log "$SUBMISSION_ID" \
                --apple-id "$APPLE_ID" \
                --team-id "$APPLE_TEAM_ID" \
                --password "$APP_PASSWORD"
        fi
    fi
    exit 1
fi

# Cleanup
echo -e "\n${BLUE}🧹 Cleaning up...${NC}"
rm -rf "$PROJECT_ROOT/build_pkg"

# Final summary
echo ""
echo -e "${GREEN}${BOLD}🎉 Signed & Notarized PKG Created!${NC}"
echo "=============================================="
echo "Package: $PKG_FILE"
echo "Size: $(du -h "$PKG_FILE" | cut -f1)"
echo "Version: $VERSION"
echo ""
echo "✅ Signed with Developer ID"
echo "✅ Notarized by Apple"
echo "✅ Stapled for offline verification"
echo "✅ Zero security warnings!"
echo ""
echo "This package will install smoothly with no warnings on any Mac!"
