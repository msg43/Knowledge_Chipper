#!/bin/bash
# diagnose_notarization_issues.sh - Comprehensive diagnostic tool for Apple notarization issues

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}🔍 Apple Notarization Diagnostic Tool${NC}"
echo "======================================"
echo "This tool checks for common issues that cause notarization to hang or fail"
echo ""

# Results tracking
ISSUES_FOUND=0
WARNINGS_FOUND=0

# Print functions
print_section() {
    echo ""
    echo -e "${BLUE}${BOLD}▸ $1${NC}"
    echo "$(printf '%.0s-' {1..50})"
}

print_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    ((ISSUES_FOUND++))
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS_FOUND++))
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# 1. System Information
print_section "System Information"
echo "macOS Version: $(sw_vers -productVersion)"
echo "Architecture: $(uname -m)"
echo "Xcode Version: $(xcodebuild -version 2>/dev/null | head -1 || echo "Not installed")"
echo "User: $(whoami)"
echo "Current Time: $(date)"

# 2. Network Connectivity
print_section "Network Connectivity"

# Check basic internet
if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
    print_ok "Internet connectivity"
else
    print_error "No internet connectivity"
fi

# Check Apple connectivity
if ping -c 1 -W 2 apple.com > /dev/null 2>&1; then
    print_ok "Can reach apple.com"
else
    print_error "Cannot reach apple.com"
fi

# Check for proxies
if [ ! -z "$HTTP_PROXY" ] || [ ! -z "$HTTPS_PROXY" ] || [ ! -z "$ALL_PROXY" ]; then
    print_warning "Proxy configuration detected:"
    [ ! -z "$HTTP_PROXY" ] && echo "  HTTP_PROXY=$HTTP_PROXY"
    [ ! -z "$HTTPS_PROXY" ] && echo "  HTTPS_PROXY=$HTTPS_PROXY"
    [ ! -z "$ALL_PROXY" ] && echo "  ALL_PROXY=$ALL_PROXY"
    print_info "Proxies can cause notarization to hang"
fi

# Check DNS resolution
if host -W 2 developer.apple.com > /dev/null 2>&1; then
    print_ok "DNS resolution working"
else
    print_warning "DNS resolution issues detected"
fi

# 3. Apple Developer Status
print_section "Apple Developer Service Status"

# Simple check - in production you'd parse the actual status
if curl -s --connect-timeout 5 https://developer.apple.com/system-status/ > /dev/null 2>&1; then
    print_ok "Apple Developer portal reachable"
    print_info "Check https://developer.apple.com/system-status/ for current status"
else
    print_warning "Cannot reach Apple Developer portal"
fi

# 4. Developer Certificates
print_section "Developer Certificates"

# Check for certificates
DEV_ID_APP=$(security find-identity -v -p codesigning | grep "Developer ID Application" | grep -v "Expired" | head -1)
DEV_ID_INST=$(security find-identity -v -p codesigning | grep "Developer ID Installer" | grep -v "Expired" | head -1)

if [ ! -z "$DEV_ID_APP" ]; then
    print_ok "Developer ID Application certificate found"
    echo "  $DEV_ID_APP"
else
    print_error "No valid Developer ID Application certificate found"
fi

if [ ! -z "$DEV_ID_INST" ]; then
    print_ok "Developer ID Installer certificate found"
    echo "  $DEV_ID_INST"
else
    print_error "No valid Developer ID Installer certificate found"
fi

# Check for expired certificates
EXPIRED_CERTS=$(security find-identity -v -p codesigning | grep "Developer ID" | grep "Expired" || true)
if [ ! -z "$EXPIRED_CERTS" ]; then
    print_warning "Expired certificates found:"
    echo "$EXPIRED_CERTS" | sed 's/^/  /'
fi

# 5. Keychain Status
print_section "Keychain Status"

# Check default keychain
DEFAULT_KEYCHAIN=$(security default-keychain | tr -d '"' | xargs basename)
print_info "Default keychain: $DEFAULT_KEYCHAIN"

# Check if locked
if security show-keychain-info 2>&1 | grep -q "User interaction is not allowed"; then
    print_error "Keychain is locked or requires user interaction"
    print_info "Run: security unlock-keychain"
elif security show-keychain-info 2>&1 | grep -q "no-timeout"; then
    print_ok "Keychain is unlocked (no timeout)"
else
    TIMEOUT_INFO=$(security show-keychain-info 2>&1 | grep "timeout" || echo "unknown")
    print_ok "Keychain is unlocked ($TIMEOUT_INFO)"
fi

# 6. Notarization Tool
print_section "Notarization Tool (notarytool)"

# Check if notarytool is available
if which xcrun > /dev/null 2>&1 && xcrun --find notarytool > /dev/null 2>&1; then
    print_ok "notarytool is available"
    NOTARYTOOL_PATH=$(xcrun --find notarytool)
    print_info "Path: $NOTARYTOOL_PATH"
else
    print_error "notarytool not found - Xcode 13+ required"
fi

# Check for stored credentials
print_info "Checking for stored credentials..."
STORED_CREDS=$(xcrun notarytool store-credentials --list 2>&1 || true)
if echo "$STORED_CREDS" | grep -q "No keychain items"; then
    print_warning "No stored notarization credentials found"
else
    echo "$STORED_CREDS" | grep -v "^$" | sed 's/^/  /'
fi

# 7. Environment Variables
print_section "Environment Variables"

# Check for Apple-related env vars
ENV_VARS=("DEVELOPER_ID_APPLICATION" "DEVELOPER_ID_INSTALLER" "APPLE_ID" "APPLE_TEAM_ID" "APP_PASSWORD")
for var in "${ENV_VARS[@]}"; do
    if [ ! -z "${!var}" ]; then
        if [[ "$var" == *"PASSWORD"* ]]; then
            print_ok "$var is set (hidden)"
        else
            print_ok "$var is set: ${!var}"
        fi
    else
        print_info "$var is not set"
    fi
done

# 8. Common File System Issues
print_section "File System Checks"

# Check temp space
TEMP_SPACE=$(df -h /tmp | tail -1 | awk '{print $4}')
print_info "Available temp space: $TEMP_SPACE"

# Check for case sensitivity
if [ -d "/Volumes" ]; then
    FS_INFO=$(diskutil info / | grep "File System" || echo "Unknown")
    print_info "Root file system: $FS_INFO"
fi

# 9. Recent Notarization History
print_section "Recent Notarization History"

if which xcrun > /dev/null 2>&1; then
    # Try to get history with stored credentials
    if xcrun notarytool store-credentials --list 2>&1 | grep -q "Skip-the-Podcast-Notary"; then
        print_info "Checking recent submissions with stored credentials..."
        HISTORY=$(xcrun notarytool history --keychain-profile "Skip-the-Podcast-Notary" 2>&1 | head -10 || true)
        if echo "$HISTORY" | grep -q "Successfully"; then
            echo "$HISTORY" | sed 's/^/  /'
        else
            print_info "No recent history or credentials invalid"
        fi
    else
        print_info "Cannot check history without stored credentials"
    fi
fi

# 10. Process and Port Checks
print_section "System Process Checks"

# Check for multiple notarytool processes
NOTARY_PROCS=$(ps aux | grep -i notarytool | grep -v grep || true)
if [ ! -z "$NOTARY_PROCS" ]; then
    print_warning "Active notarytool processes found:"
    echo "$NOTARY_PROCS" | sed 's/^/  /'
fi

# Check system load
LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}')
print_info "System load:$LOAD_AVG"

# 11. Known Issues Check
print_section "Known Issues and Recommendations"

# Check macOS version for known issues
MAC_VERSION=$(sw_vers -productVersion)
if [[ "$MAC_VERSION" == "14."* ]]; then
    print_info "macOS Sonoma detected - ensure Xcode 15+ is installed"
fi

# Summary
print_section "Diagnostic Summary"

echo ""
if [ $ISSUES_FOUND -eq 0 ] && [ $WARNINGS_FOUND -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✅ No major issues found!${NC}"
    echo "Your system appears to be properly configured for notarization."
else
    echo -e "${RED}${BOLD}Issues found: $ISSUES_FOUND${NC}"
    echo -e "${YELLOW}${BOLD}Warnings: $WARNINGS_FOUND${NC}"
    echo ""
    echo "Recommendations:"

    if [ $ISSUES_FOUND -gt 0 ]; then
        echo "1. Fix the critical issues marked with ✗ above"
    fi

    if [ ! -z "$HTTP_PROXY" ] || [ ! -z "$HTTPS_PROXY" ]; then
        echo "2. Try disabling proxy temporarily:"
        echo "   unset HTTP_PROXY HTTPS_PROXY ALL_PROXY"
    fi

    echo "3. Ensure you have:"
    echo "   - Valid Apple Developer account"
    echo "   - Accepted all agreements at developer.apple.com"
    echo "   - App-specific password for notarization"
    echo "   - Xcode 13 or later installed"
fi

echo ""
echo "For hanging issues specifically:"
echo "- Use the debug notarization script with timeout"
echo "- Check network connectivity and firewall rules"
echo "- Try notarizing a small test package first"
echo "- Monitor Activity Monitor for stuck processes"
echo ""
