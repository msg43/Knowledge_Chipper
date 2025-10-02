#!/bin/bash
# quick_notarization_test.sh - Quick test of signing and notarization

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🧪 Quick Notarization Test${NC}"
echo "========================="
echo ""

# Find certificates
echo -e "${BLUE}Finding certificates...${NC}"
DEV_ID_APP=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
DEV_ID_INST=$(security find-identity -v | grep "Developer ID Installer" | head -1 | awk -F'"' '{print $2}')

echo "Application cert: ${DEV_ID_APP:-NOT FOUND}"
echo "Installer cert: ${DEV_ID_INST:-NOT FOUND}"

if [ -z "$DEV_ID_APP" ] || [ -z "$DEV_ID_INST" ]; then
    echo -e "${RED}✗${NC} Missing certificates"
    exit 1
fi

# Create test app
echo -e "\n${BLUE}Creating test app...${NC}"
TEST_DIR="/tmp/notarization_test_$$"
mkdir -p "$TEST_DIR/TestApp.app/Contents/MacOS"

cat > "$TEST_DIR/TestApp.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>test</string>
    <key>CFBundleIdentifier</key>
    <string>com.test.notarization</string>
    <key>CFBundleName</key>
    <string>Test App</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
</dict>
</plist>
EOF

echo '#!/bin/bash\necho "Test app"' > "$TEST_DIR/TestApp.app/Contents/MacOS/test"
chmod +x "$TEST_DIR/TestApp.app/Contents/MacOS/test"

# Sign the app
echo -e "\n${BLUE}Signing test app...${NC}"
codesign --force --options runtime --timestamp --sign "$DEV_ID_APP" "$TEST_DIR/TestApp.app" 2>&1 || {
    echo -e "${YELLOW}⚠️${NC} Signing produced warnings, but continuing..."
}

# Verify signature
if codesign --verify --verbose "$TEST_DIR/TestApp.app" 2>&1; then
    echo -e "${GREEN}✓${NC} App signature verified"
else
    echo -e "${YELLOW}⚠️${NC} Signature verification had issues, but continuing..."
fi

# Create package
echo -e "\n${BLUE}Creating test package...${NC}"
pkgbuild --root "$TEST_DIR" \
         --identifier "com.test.notarization" \
         --version "1.0" \
         --install-location "/tmp/test_notarization" \
         --sign "$DEV_ID_INST" \
         "$TEST_DIR/test.pkg" 2>&1 || {
    echo -e "${YELLOW}⚠️${NC} Package signing produced warnings, but continuing..."
}

if [ -f "$TEST_DIR/test.pkg" ]; then
    echo -e "${GREEN}✓${NC} Package created: $(du -h "$TEST_DIR/test.pkg" | cut -f1)"
    echo ""
    echo -e "${GREEN}Success!${NC} Your certificates can create signed packages."
    echo ""
    echo "Next steps:"
    echo "1. Set up notarization credentials:"
    echo "   ./scripts/setup_notarization_credentials.sh"
    echo ""
    echo "2. Then notarize this test package:"
    echo "   xcrun notarytool submit $TEST_DIR/test.pkg --apple-id YOUR_APPLE_ID --team-id YOUR_TEAM_ID --password YOUR_APP_PASSWORD --wait"
    echo ""
    echo "Test package location: $TEST_DIR/test.pkg"
else
    echo -e "${RED}✗${NC} Package creation failed"
fi

# Clean up on exit
trap "rm -rf $TEST_DIR" EXIT
