#!/bin/bash
# test_notarization_simple.sh - Simple test to isolate notarization issues

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🧪 Simple Notarization Test${NC}"
echo "==========================="
echo "This creates a minimal test package to isolate notarization issues"
echo ""

# Configuration
TEST_DIR="/tmp/notarization_test_$$"
TEST_APP="$TEST_DIR/TestApp.app"
TEST_PKG="$TEST_DIR/test.pkg"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create test directory
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

echo -e "${BLUE}1. Creating minimal test app...${NC}"

# Create app bundle structure
mkdir -p "$TEST_APP/Contents/MacOS"
mkdir -p "$TEST_APP/Contents/Resources"

# Create Info.plist
cat > "$TEST_APP/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>test</string>
    <key>CFBundleIdentifier</key>
    <string>com.test.notarization</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Test App</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
</dict>
</plist>
EOF

# Create minimal executable
cat > "$TEST_APP/Contents/MacOS/test" << 'EOF'
#!/bin/bash
echo "Test app"
EOF
chmod +x "$TEST_APP/Contents/MacOS/test"

echo -e "${GREEN}✓${NC} Test app created"

# Find certificates
echo -e "\n${BLUE}2. Finding certificates...${NC}"
DEV_ID_APP=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
DEV_ID_INST=$(security find-identity -v -p codesigning | grep "Developer ID Installer" | head -1 | awk -F'"' '{print $2}')

if [ -z "$DEV_ID_APP" ] || [ -z "$DEV_ID_INST" ]; then
    echo -e "${RED}✗${NC} Missing required certificates"
    echo "Developer ID Application: ${DEV_ID_APP:-NOT FOUND}"
    echo "Developer ID Installer: ${DEV_ID_INST:-NOT FOUND}"
    exit 1
fi

echo "App cert: $DEV_ID_APP"
echo "Installer cert: $DEV_ID_INST"

# Sign the app
echo -e "\n${BLUE}3. Signing test app...${NC}"
codesign --force --options runtime --timestamp --sign "$DEV_ID_APP" "$TEST_APP"

# Verify signature
if codesign --verify --verbose "$TEST_APP" 2>&1; then
    echo -e "${GREEN}✓${NC} App signed successfully"
else
    echo -e "${RED}✗${NC} App signing failed"
    exit 1
fi

# Create package
echo -e "\n${BLUE}4. Creating test package...${NC}"
pkgbuild --root "$TEST_DIR" \
         --identifier "com.test.notarization" \
         --version "1.0" \
         --install-location "/tmp/test_notarization" \
         --sign "$DEV_ID_INST" \
         "$TEST_PKG"

if [ -f "$TEST_PKG" ]; then
    echo -e "${GREEN}✓${NC} Package created: $(du -h "$TEST_PKG" | cut -f1)"
else
    echo -e "${RED}✗${NC} Package creation failed"
    exit 1
fi

# Get credentials
echo -e "\n${BLUE}5. Notarization credentials...${NC}"

# Check for stored profile
if xcrun notarytool store-credentials --list 2>&1 | grep -q "Skip-the-Podcast-Notary"; then
    echo "Using stored profile: Skip-the-Podcast-Notary"
    USE_PROFILE=true
else
    USE_PROFILE=false
    if [ -z "$APPLE_ID" ]; then
        read -p "Apple ID: " APPLE_ID
    fi
    if [ -z "$APPLE_TEAM_ID" ]; then
        read -p "Team ID: " APPLE_TEAM_ID
    fi
    if [ -z "$APP_PASSWORD" ]; then
        echo "App-specific password (create at appleid.apple.com):"
        read -s APP_PASSWORD
        echo
    fi
fi

# Submit for notarization
echo -e "\n${BLUE}6. Submitting for notarization...${NC}"
echo "Package: $TEST_PKG"
echo "Time: $(date)"
echo ""

LOG_FILE="$TEST_DIR/notarization_log_$TIMESTAMP.txt"

# Function to monitor progress
monitor_progress() {
    local pid=$1
    local start_time=$(date +%s)

    while kill -0 $pid 2>/dev/null; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        printf "\rElapsed: %02d:%02d" $((elapsed/60)) $((elapsed%60))
        sleep 1
    done
    echo ""
}

# Submit with monitoring
if [ "$USE_PROFILE" = true ]; then
    xcrun notarytool submit "$TEST_PKG" \
        --keychain-profile "Skip-the-Podcast-Notary" \
        --wait \
        -v > "$LOG_FILE" 2>&1 &
else
    xcrun notarytool submit "$TEST_PKG" \
        --apple-id "$APPLE_ID" \
        --team-id "$APPLE_TEAM_ID" \
        --password "$APP_PASSWORD" \
        --wait \
        -v > "$LOG_FILE" 2>&1 &
fi

NOTARY_PID=$!
echo "Notarization PID: $NOTARY_PID"
echo "Log file: $LOG_FILE"
echo ""
echo "Monitoring progress (Ctrl+C to stop monitoring, notarization continues)..."

# Set up trap to handle Ctrl+C
trap 'echo -e "\n\nStopped monitoring. Notarization continues in background."; echo "Check: tail -f $LOG_FILE"; exit 0' INT

# Monitor the process
monitor_progress $NOTARY_PID

# Wait for completion
wait $NOTARY_PID
NOTARY_EXIT=$?

echo ""
if [ $NOTARY_EXIT -eq 0 ]; then
    # Check if successful
    if grep -q "status: Accepted" "$LOG_FILE"; then
        echo -e "${GREEN}✓${NC} Notarization successful!"

        # Get submission ID
        SUBMISSION_ID=$(grep "id:" "$LOG_FILE" | head -1 | awk '{print $2}')
        echo "Submission ID: $SUBMISSION_ID"

        # Try to staple
        echo -e "\n${BLUE}7. Stapling ticket...${NC}"
        if xcrun stapler staple "$TEST_PKG" 2>&1; then
            echo -e "${GREEN}✓${NC} Package stapled successfully"
        else
            echo -e "${YELLOW}⚠${NC} Stapling failed (this is often a timing issue)"
        fi
    else
        echo -e "${RED}✗${NC} Notarization rejected"
        echo "Check log: $LOG_FILE"
    fi
else
    echo -e "${RED}✗${NC} Notarization failed with exit code: $NOTARY_EXIT"
    echo "Check log: $LOG_FILE"
fi

# Show last 20 lines of log
echo -e "\n${BLUE}Log tail:${NC}"
tail -20 "$LOG_FILE"

echo -e "\n${BLUE}Test complete${NC}"
echo "Test directory: $TEST_DIR"
echo "Full log: $LOG_FILE"
echo ""
echo "To clean up: rm -rf $TEST_DIR"
