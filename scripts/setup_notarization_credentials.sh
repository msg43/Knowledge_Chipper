#!/bin/bash
# setup_notarization_credentials.sh - Set up notarization credentials

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔑 Notarization Credential Setup${NC}"
echo "================================"
echo ""

# Check for certificates
echo "Checking for certificates..."
DEV_CERTS=$(security find-identity -v -p codesigning | grep "Developer ID" || true)
if [ -z "$DEV_CERTS" ]; then
    echo -e "${YELLOW}⚠️  No Developer ID certificates found!${NC}"
    echo ""
    echo "You need to:"
    echo "1. Sign in to https://developer.apple.com"
    echo "2. Create Developer ID certificates"
    echo "3. Install them in Keychain Access"
    echo ""
    echo "Or if you have them on another Mac, export and import them."
    exit 1
fi

echo "Found certificates:"
echo "$DEV_CERTS"
echo ""

# Get credentials
echo "Enter your notarization credentials:"
echo "(These will be stored securely in your keychain)"
echo ""

read -p "Apple ID email: " APPLE_ID
read -p "Team ID (10 characters, e.g., ABC123DEF4): " TEAM_ID

echo ""
echo "Create an app-specific password at:"
echo "https://appleid.apple.com/account/manage"
echo ""
read -s -p "App-specific password (format: xxxx-xxxx-xxxx-xxxx): " APP_PASSWORD
echo ""
echo ""

# Validate format
if [[ ! "$APP_PASSWORD" =~ ^[a-z]{4}-[a-z]{4}-[a-z]{4}-[a-z]{4}$ ]]; then
    echo -e "${YELLOW}⚠️  Password format seems incorrect. Expected: xxxx-xxxx-xxxx-xxxx${NC}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Store credentials
echo "Storing credentials in keychain..."
xcrun notarytool store-credentials "Skip-the-Podcast-Notary" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_PASSWORD"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Credentials stored successfully!${NC}"

    # Test the credentials
    echo ""
    echo "Testing credentials..."
    if xcrun notarytool history --keychain-profile "Skip-the-Podcast-Notary" 2>&1 | head -5; then
        echo -e "${GREEN}✅ Credentials are working!${NC}"
    else
        echo -e "${YELLOW}⚠️  Could not verify credentials${NC}"
    fi

    # Create environment file (optional)
    echo ""
    read -p "Create environment file for GitHub Actions? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cat > "config/apple_signing_credentials.env" << EOF
# Apple signing credentials (DO NOT COMMIT!)
export APPLE_ID="$APPLE_ID"
export APPLE_TEAM_ID="$TEAM_ID"
export APP_PASSWORD="$APP_PASSWORD"
EOF
        chmod 600 "config/apple_signing_credentials.env"
        echo -e "${GREEN}✅ Created config/apple_signing_credentials.env${NC}"
        echo "   Remember to add this file to .gitignore!"
    fi
else
    echo -e "${YELLOW}⚠️  Failed to store credentials${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "You can now use the notarization scripts:"
echo "  ./scripts/build_signed_notarized_pkg.sh"
echo "  ./scripts/build_signed_notarized_pkg_debug.sh"
echo ""
echo "Your credentials are stored as: Skip-the-Podcast-Notary"
