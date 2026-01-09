#!/bin/bash
# build_signed_notarized_zip.sh
# Build, sign, and notarize app as .zip (WORKING METHOD)
# Uses Developer ID Application certificate (not Installer)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     BUILD, SIGN & NOTARIZE (.zip method)                       ║${NC}"
echo -e "${BLUE}║     Uses working Application certificate                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"

# Certificate
DEV_ID_APP="Developer ID Application: Matthew Seymour Greer (W2AT7M9482)"

# Credentials
APPLE_ID="${APPLE_ID:-Matt@rainfall.llc}"
TEAM_ID="${TEAM_ID:-W2AT7M9482}"

# Find the app to sign
if [ -n "$1" ]; then
    APP_PATH="$1"
elif [ -d "$DIST_DIR" ]; then
    APP_PATH=$(find "$DIST_DIR" -name "*.app" -type d | head -1)
fi

if [ -z "$APP_PATH" ] || [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}Error: No .app bundle found${NC}"
    echo "Usage: $0 /path/to/YourApp.app"
    echo "Or place the .app in the dist/ directory"
    exit 1
fi

APP_NAME=$(basename "$APP_PATH" .app)
OUTPUT_DIR=$(dirname "$APP_PATH")
ZIP_PATH="$OUTPUT_DIR/${APP_NAME}.zip"
NOTARIZED_ZIP="$OUTPUT_DIR/${APP_NAME}-notarized.zip"

echo "App: $APP_PATH"
echo "Output: $NOTARIZED_ZIP"
echo ""

# Get password if not set
if [ -z "$APP_PASSWORD" ]; then
    echo -e "${YELLOW}Enter app-specific password:${NC}"
    read -s APP_PASSWORD
    echo ""
fi

# Step 1: Sign the app
echo -e "${BLUE}[1/5] Signing app with Developer ID Application...${NC}"
codesign --force --deep --options runtime --timestamp \
    --sign "$DEV_ID_APP" \
    "$APP_PATH" \
    --verbose

# Verify signature
echo -e "${BLUE}[2/5] Verifying signature...${NC}"
if codesign --verify --deep --strict --verbose=2 "$APP_PATH" 2>&1; then
    echo -e "${GREEN}✓ Signature verified${NC}"
else
    echo -e "${RED}✗ Signature verification failed${NC}"
    exit 1
fi

# Step 2: Create zip with ditto
echo -e "${BLUE}[3/5] Packaging with ditto...${NC}"
rm -f "$ZIP_PATH"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
echo "Created: $ZIP_PATH ($(du -h "$ZIP_PATH" | cut -f1))"

# Step 3: Submit for notarization
echo -e "${BLUE}[4/5] Submitting for notarization...${NC}"
echo "This may take 5-15 minutes..."
echo ""

RESULT=$(xcrun notarytool submit "$ZIP_PATH" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_PASSWORD" \
    --wait 2>&1)

echo "$RESULT"

if echo "$RESULT" | grep -q "status: Accepted"; then
    echo -e "${GREEN}✓ Notarization successful!${NC}"
    
    # Step 4: Staple the app
    echo -e "${BLUE}[5/5] Stapling ticket to app...${NC}"
    xcrun stapler staple "$APP_PATH"
    echo -e "${GREEN}✓ Ticket stapled${NC}"
    
    # Recreate zip with stapled app
    rm -f "$NOTARIZED_ZIP"
    ditto -c -k --keepParent "$APP_PATH" "$NOTARIZED_ZIP"
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    SUCCESS!                                    ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Notarized app: $APP_PATH"
    echo "Distribution zip: $NOTARIZED_ZIP"
    echo ""
    echo "Users can download and extract the .zip,"
    echo "then drag the app to Applications folder."
    
    # Cleanup intermediate zip
    rm -f "$ZIP_PATH"
else
    echo -e "${RED}✗ Notarization failed${NC}"
    
    # Get submission ID for log
    SUB_ID=$(echo "$RESULT" | grep "id:" | head -1 | awk '{print $2}')
    if [ -n "$SUB_ID" ]; then
        echo ""
        echo "Getting detailed log..."
        xcrun notarytool log "$SUB_ID" \
            --apple-id "$APPLE_ID" \
            --team-id "$TEAM_ID" \
            --password "$APP_PASSWORD"
    fi
    exit 1
fi

