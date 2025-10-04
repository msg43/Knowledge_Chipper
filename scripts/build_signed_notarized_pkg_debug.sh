#!/bin/bash
# build_signed_notarized_pkg_debug.sh - Debug version with comprehensive diagnostics
# Diagnoses and fixes Apple notarization hanging issues

set -e
set -o pipefail

# Enable debug output
set -x

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")
TIMEOUT_SECONDS=1800  # 30 minutes timeout

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}🔐 Signed & Notarized PKG Builder (DEBUG MODE)${NC}"
echo "=============================================="
echo "Version: $VERSION"
echo "Date: $(date)"
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

print_debug() {
    echo -e "${BLUE}🔍${NC} DEBUG: $1"
}

# Function to check network connectivity
check_network() {
    print_debug "Checking network connectivity..."

    # Check basic connectivity
    if ! ping -c 1 apple.com > /dev/null 2>&1; then
        print_error "Cannot reach apple.com - check network connection"
        return 1
    fi

    # Check Apple notarization service
    if ! curl -s -o /dev/null -w "%{http_code}" https://notary.apple.com > /dev/null 2>&1; then
        print_warning "Cannot reach notary.apple.com directly (this may be normal)"
    fi

    # Check for proxy settings
    if [ ! -z "$HTTP_PROXY" ] || [ ! -z "$HTTPS_PROXY" ]; then
        print_warning "Proxy detected: HTTP_PROXY=$HTTP_PROXY HTTPS_PROXY=$HTTPS_PROXY"
        print_warning "Proxies can cause notarization to hang"
    fi

    print_status "Network connectivity OK"
}

# Function to check Apple system status
check_apple_status() {
    print_debug "Checking Apple Developer Status..."

    # This is a simple check - in practice you might want to parse the actual status page
    if curl -s https://developer.apple.com/system-status/ | grep -q "All Systems Operational"; then
        print_status "Apple Developer services appear operational"
    else
        print_warning "Cannot verify Apple Developer service status - check https://developer.apple.com/system-status/"
    fi
}

# Function to verify certificates
verify_certificates() {
    print_debug "Verifying certificates..."

    # Check for Developer ID Installer (do not restrict to codesigning policy; some systems omit it there)
    INSTALLER_CERTS=$(security find-identity -v | grep "Developer ID Installer")
    if [ -z "$INSTALLER_CERTS" ]; then
        print_error "No Developer ID Installer certificate found"
        return 1
    else
        print_status "Developer ID Installer certificate found:"
        echo "$INSTALLER_CERTS" | head -5
    fi

    # Check for Developer ID Application
    APP_CERTS=$(security find-identity -v -p codesigning | grep "Developer ID Application")
    if [ -z "$APP_CERTS" ]; then
        print_error "No Developer ID Application certificate found"
        return 1
    else
        print_status "Developer ID Application certificate found:"
        echo "$APP_CERTS" | head -5
    fi

    # Check certificate validity
    print_debug "Checking certificate expiration..."
    security find-identity -v -p codesigning | grep "Developer ID" | while read -r line; do
        cert_hash=$(echo "$line" | awk '{print $2}')
        cert_info=$(security find-certificate -c "$cert_hash" -p | openssl x509 -noout -dates 2>/dev/null || true)
        if [ ! -z "$cert_info" ]; then
            echo "  Certificate $cert_hash: $cert_info"
        fi
    done
}

# Function to check keychain access
check_keychain() {
    print_debug "Checking keychain access..."

    # List keychains
    print_debug "Available keychains:"
    security list-keychains

    # Check default keychain
    print_debug "Default keychain:"
    security default-keychain

    # Check if keychain is unlocked
    if security show-keychain-info 2>&1 | grep -q "locked"; then
        print_warning "Keychain appears to be locked - this can cause hanging"
        print_warning "Run: security unlock-keychain"
    else
        print_status "Keychain is unlocked"
    fi
}

# Function to check for existing notarization credentials
check_notary_credentials() {
    print_debug "Checking for stored notarization credentials..."

    # Prefer a pre-set profile name from the environment
    if [ -n "$NOTARY_PROFILE" ]; then
        print_status "Using NOTARY_PROFILE from environment: $NOTARY_PROFILE"
        if xcrun notarytool history --keychain-profile "$NOTARY_PROFILE" >/dev/null 2>&1; then
            print_status "Stored credentials are valid"
            return 0
        else
            print_warning "Specified NOTARY_PROFILE is not valid in keychain"
        fi
    fi

    # Fallback: try our default profile name
    if xcrun notarytool history --keychain-profile "Skip-the-Podcast-Notary" >/dev/null 2>&1; then
        print_status "Found stored notarization credentials: Skip-the-Podcast-Notary"
        NOTARY_PROFILE="Skip-the-Podcast-Notary"
        return 0
    fi

    print_warning "No stored notarization credentials found"
    return 1
}

# Function to check app bundle for common issues
check_app_bundle() {
    local app_path="$1"
    print_debug "Checking app bundle for common issues..."

    if [ ! -d "$app_path" ]; then
        print_error "App bundle not found at: $app_path"
        return 1
    fi

    # Check for unsigned components
    print_debug "Checking for unsigned components..."
    local unsigned_count=0
    find "$app_path" \( -name "*.dylib" -o -name "*.framework" -o -name "*.app" -o -name "*.bundle" \) -print0 | while IFS= read -r -d '' item; do
        if ! codesign -v "$item" 2>/dev/null; then
            print_warning "Unsigned component: $item"
            ((unsigned_count++))
        fi
    done

    if [ $unsigned_count -gt 0 ]; then
        print_warning "Found $unsigned_count unsigned components - these must be signed"
    fi

    # Check for hardened runtime
    print_debug "Checking hardened runtime..."
    if codesign -d -vv "$app_path" 2>&1 | grep -q "flags=0x10000(runtime)"; then
        print_status "App has hardened runtime enabled"
    else
        print_warning "App does not have hardened runtime - required for notarization"
    fi

    # Check for secure timestamp
    print_debug "Checking secure timestamp..."
    if codesign -d -vv "$app_path" 2>&1 | grep -q "Timestamp="; then
        print_status "App has secure timestamp"
    else
        print_warning "App missing secure timestamp"
    fi

    # Check bundle size
    local bundle_size=$(du -sh "$app_path" | cut -f1)
    print_debug "App bundle size: $bundle_size"

    # Check for .DS_Store files (can cause issues)
    local ds_store_count=$(find "$app_path" -name ".DS_Store" | wc -l)
    if [ $ds_store_count -gt 0 ]; then
        print_warning "Found $ds_store_count .DS_Store files - consider removing"
    fi
}

# Main diagnostic flow
echo -e "\n${BLUE}🔍 Running Pre-flight Diagnostics...${NC}"
echo "===================================="

# Run all diagnostics
check_network || exit 1
check_apple_status
verify_certificates || exit 1
check_keychain
check_notary_credentials && NOTARY_PROFILE="Skip-the-Podcast-Notary"

# Check for required environment variables or prompt
if [ -z "$DEVELOPER_ID_INSTALLER" ]; then
    echo "Finding Developer ID Installer certificate..."
    # Avoid filtering by codesigning; use full identity list
    DEVELOPER_ID_INSTALLER=$(security find-identity -v | grep "Developer ID Installer" | head -1 | awk -F'"' '{print $2}')
    if [ -z "$DEVELOPER_ID_INSTALLER" ]; then
        print_error "No Developer ID Installer certificate found"
        exit 1
    fi
    echo "Found: $DEVELOPER_ID_INSTALLER"
fi

if [ -z "$DEVELOPER_ID_APPLICATION" ]; then
    echo "Finding Developer ID Application certificate..."
    DEVELOPER_ID_APPLICATION=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
    if [ -z "$DEVELOPER_ID_APPLICATION" ]; then
        print_error "No Developer ID Application certificate found"
        exit 1
    fi
    echo "Found: $DEVELOPER_ID_APPLICATION"
fi

# Prompt for notarization credentials if not set and no profile
if [ -z "$NOTARY_PROFILE" ]; then
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
fi

# Build the app bundle first
echo -e "\n${BLUE}📦 Building app bundle...${NC}"
"$SCRIPT_DIR/build_pkg_installer.sh" --prepare-only

# Check the app bundle before signing
APP_BUNDLE="$PROJECT_ROOT/build_pkg/package_root/Applications/Skip the Podcast Desktop.app"
check_app_bundle "$APP_BUNDLE"

# Sign the app bundle with detailed logging
echo -e "\n${BLUE}🔏 Signing app bundle with detailed logging...${NC}"

# Remove any existing signatures first
print_debug "Removing existing signatures..."
find "$APP_BUNDLE" -type f -perm +111 -exec codesign --remove-signature {} \; 2>/dev/null || true

# Sign all frameworks and dylibs first
print_debug "Signing frameworks and libraries..."
find "$APP_BUNDLE" -name "*.dylib" -o -name "*.framework" | while read -r item; do
    echo "Signing: $(basename "$item")"
    codesign --force --options runtime --timestamp --sign "$DEVELOPER_ID_APPLICATION" -v "$item" 2>&1
done

# Sign the main app
print_debug "Signing main application..."
codesign --force --options runtime --timestamp --sign "$DEVELOPER_ID_APPLICATION" --deep -v "$APP_BUNDLE" 2>&1

# Verify app signature
echo -e "\n${BLUE}🔍 Verifying app signature...${NC}"
codesign --verify --deep --strict --verbose=4 "$APP_BUNDLE" 2>&1
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
PKG_FILE="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}-debug.pkg"

# Create distribution XML
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

# Package info
echo -e "\n${BLUE}📋 Package Information:${NC}"
echo "Size: $(du -h "$PKG_FILE" | cut -f1)"
echo "SHA256: $(cat "$PKG_FILE.sha256")"

# Notarize with timeout and detailed logging
echo -e "\n${BLUE}📤 Submitting package for notarization with timeout...${NC}"
echo "This may take several minutes (timeout: ${TIMEOUT_SECONDS}s)..."

NOTARY_LOG_FILE="$PROJECT_ROOT/logs/notarization_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$PROJECT_ROOT/logs"

# Function to submit with timeout
submit_for_notarization() {
    if [ -n "$NOTARY_PROFILE" ]; then
        timeout $TIMEOUT_SECONDS xcrun notarytool submit "$PKG_FILE" \
            --keychain-profile "$NOTARY_PROFILE" \
            --wait \
            --timeout "$TIMEOUT_SECONDS" \
            -v 2>&1 | tee "$NOTARY_LOG_FILE"
    else
        timeout $TIMEOUT_SECONDS xcrun notarytool submit "$PKG_FILE" \
            --apple-id "$APPLE_ID" \
            --team-id "$APPLE_TEAM_ID" \
            --password "$APP_PASSWORD" \
            --wait \
            --timeout "$TIMEOUT_SECONDS" \
            -v 2>&1 | tee "$NOTARY_LOG_FILE"
    fi
}

# Submit for notarization
NOTARY_OUTPUT=$(submit_for_notarization)
NOTARY_EXIT_CODE=$?

echo "$NOTARY_OUTPUT"

# Check exit code
if [ $NOTARY_EXIT_CODE -eq 124 ]; then
    print_error "Notarization timed out after ${TIMEOUT_SECONDS} seconds!"
    print_warning "This often indicates network issues or Apple service problems"

    # Try to extract submission ID for manual checking
    SUBMISSION_ID=$(echo "$NOTARY_OUTPUT" | grep -o 'id: [a-z0-9-]*' | head -1 | cut -d' ' -f2)
    if [ -n "$SUBMISSION_ID" ]; then
        echo ""
        echo "Submission ID: $SUBMISSION_ID"
        echo "You can check status manually with:"
        if [ -n "$NOTARY_PROFILE" ]; then
            echo "  xcrun notarytool info $SUBMISSION_ID --keychain-profile '$NOTARY_PROFILE'"
        else
            echo "  xcrun notarytool info $SUBMISSION_ID --apple-id '$APPLE_ID' --team-id '$APPLE_TEAM_ID' --password '$APP_PASSWORD'"
        fi
    fi

    echo ""
    echo "Log saved to: $NOTARY_LOG_FILE"
    echo ""
    echo "Common causes of hanging:"
    echo "1. Network issues (proxy, firewall)"
    echo "2. Large file size"
    echo "3. Apple service issues"
    echo "4. Invalid credentials"
    echo "5. Unsigned nested components"

    exit 1
fi

# Check if notarization succeeded
if echo "$NOTARY_OUTPUT" | grep -q "status: Accepted"; then
    print_status "Notarization successful!"

    # Staple the notarization ticket
    echo -e "\n${BLUE}📎 Stapling notarization ticket...${NC}"
    xcrun stapler staple -v "$PKG_FILE" 2>&1
    print_status "Notarization ticket stapled"

    # Verify the stapling
    echo -e "\n${BLUE}🔍 Verifying notarization...${NC}"
    xcrun stapler validate -v "$PKG_FILE" 2>&1
    print_status "Package is properly notarized and stapled"
else
    print_error "Notarization failed!"
    echo "Check the notarization log for details: $NOTARY_LOG_FILE"

    # Extract submission ID for log retrieval
    SUBMISSION_ID=$(echo "$NOTARY_OUTPUT" | grep -o 'id: [a-z0-9-]*' | head -1 | cut -d' ' -f2)
    if [ -n "$SUBMISSION_ID" ]; then
        echo "Getting detailed notarization log..."
        if [ -n "$NOTARY_PROFILE" ]; then
            xcrun notarytool log "$SUBMISSION_ID" --keychain-profile "$NOTARY_PROFILE" 2>&1 | tee -a "$NOTARY_LOG_FILE"
        else
            xcrun notarytool log "$SUBMISSION_ID" \
                --apple-id "$APPLE_ID" \
                --team-id "$APPLE_TEAM_ID" \
                --password "$APP_PASSWORD" 2>&1 | tee -a "$NOTARY_LOG_FILE"
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
echo "Log: $NOTARY_LOG_FILE"
echo ""
echo "✅ Signed with Developer ID"
echo "✅ Notarized by Apple"
echo "✅ Stapled for offline verification"
echo "✅ Zero security warnings!"
echo ""
