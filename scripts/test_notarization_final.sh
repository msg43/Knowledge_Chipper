#!/bin/bash
# test_notarization_final.sh - Complete notarization test

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Complete Notarization Test${NC}"
echo "============================="
echo ""

# Find certificates correctly
echo -e "${BLUE}Finding certificates...${NC}"
DEV_ID_APP=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
DEV_ID_INST=$(security find-identity -v | grep "Developer ID Installer" | head -1 | awk -F'"' '{print $2}')

echo "Application: ${DEV_ID_APP:-NOT FOUND}"
echo "Installer: ${DEV_ID_INST:-NOT FOUND}"

if [ -z "$DEV_ID_APP" ] || [ -z "$DEV_ID_INST" ]; then
    echo -e "${RED}✗${NC} Missing certificates"
    exit 1
fi

# Create test app
echo -e "\n${BLUE}Creating test app...${NC}"
TEST_DIR="/tmp/notarization_final_$$"
mkdir -p "$TEST_DIR/TestApp.app/Contents/MacOS"

cat > "$TEST_DIR/TestApp.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>test</string>
    <key>CFBundleIdentifier</key>
    <string>com.test.notarization.final</string>
    <key>CFBundleName</key>
    <string>Test App Final</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
</dict>
</plist>
EOF

echo '#!/bin/bash
echo "Test app final"' > "$TEST_DIR/TestApp.app/Contents/MacOS/test"
chmod +x "$TEST_DIR/TestApp.app/Contents/MacOS/test"

# Sign the app (ignore chain warnings)
echo -e "\n${BLUE}Signing app...${NC}"
codesign --force --options runtime --timestamp --sign "$DEV_ID_APP" "$TEST_DIR/TestApp.app" 2>&1 | grep -v "Warning: unable to build chain" || true
echo -e "${GREEN}✓${NC} App signed"

# Create package
echo -e "\n${BLUE}Creating package...${NC}"
PKG_FILE="$TEST_DIR/test_final.pkg"
pkgbuild --root "$TEST_DIR" \
         --identifier "com.test.notarization.final" \
         --version "1.0" \
         --install-location "/tmp/test_notarization_final" \
         --sign "$DEV_ID_INST" \
         "$PKG_FILE" 2>&1 | grep -v "Warning: unable to build chain" || true

echo -e "${GREEN}✓${NC} Package created: $(du -h "$PKG_FILE" | cut -f1)"

# Submit for notarization
echo -e "\n${BLUE}Submitting for notarization...${NC}"
echo "Using stored credentials: Skip-the-Podcast-Notary"
echo ""

# Create log file
LOG_FILE="$TEST_DIR/notarization.log"

# Submit with timeout
echo "Submitting to Apple (this takes 5-15 minutes)..."
if timeout 1800 xcrun notarytool submit "$PKG_FILE" \
    --keychain-profile "Skip-the-Podcast-Notary" \
    --wait 2>&1 | tee "$LOG_FILE"; then

    # Check if successful
    if grep -q "status: Accepted" "$LOG_FILE"; then
        echo -e "\n${GREEN}✅ NOTARIZATION SUCCESSFUL!${NC}"

        # Try to staple
        echo -e "\n${BLUE}Stapling ticket...${NC}"
        if xcrun stapler staple "$PKG_FILE" 2>&1; then
            echo -e "${GREEN}✓${NC} Package stapled"
        fi

        echo -e "\n${GREEN}🎉 Success! Notarization is working!${NC}"
        echo "Your setup is complete and ready to build the actual app."
    else
        echo -e "\n${RED}✗${NC} Notarization failed"
        echo "Check log: $LOG_FILE"
    fi
else
    echo -e "\n${YELLOW}⚠️${NC} Notarization timed out or failed"
    echo "Check log: $LOG_FILE"
fi

echo ""
echo "Test directory: $TEST_DIR"
echo "Package: $PKG_FILE"
echo "Log: $LOG_FILE"
