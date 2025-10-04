#!/bin/bash
# create_new_certificates.sh - Generate new certificates with private keys on this Mac

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔑 Generate New Apple Developer Certificates${NC}"
echo "==========================================="
echo ""
echo "This will create NEW certificates to replace the ones without private keys."
echo ""

# Step 1: Create CSR
echo -e "${BLUE}Step 1: Creating Certificate Signing Requests${NC}"
echo ""

# Get user info
read -p "Enter your name (as it appears in Apple Developer): " USER_NAME
read -p "Enter your email address: " USER_EMAIL

# Create CSR for Application
echo "Creating CSR for Developer ID Application..."
CSR_APP="/tmp/CertificateSigningRequest_App.certSigningRequest"
openssl req -new -newkey rsa:2048 -nodes -keyout /tmp/app_private.key -out "$CSR_APP" -subj "/emailAddress=$USER_EMAIL/CN=Developer ID Application: $USER_NAME/C=US"

# Create CSR for Installer
echo "Creating CSR for Developer ID Installer..."
CSR_INST="/tmp/CertificateSigningRequest_Installer.certSigningRequest"
openssl req -new -newkey rsa:2048 -nodes -keyout /tmp/installer_private.key -out "$CSR_INST" -subj "/emailAddress=$USER_EMAIL/CN=Developer ID Installer: $USER_NAME/C=US"

echo -e "${GREEN}✓${NC} CSRs created!"
echo ""

# Step 2: Instructions for Apple Developer Portal
echo -e "${BLUE}Step 2: Upload CSRs to Apple Developer Portal${NC}"
echo ""
echo "1. Go to: https://developer.apple.com/account/resources/certificates/add"
echo ""
echo "2. For FIRST certificate:"
echo "   - Choose: Developer ID Application"
echo "   - Click Continue"
echo "   - Upload: $CSR_APP"
echo "   - Download the certificate"
echo ""
echo "3. For SECOND certificate:"
echo "   - Choose: Developer ID Installer"
echo "   - Click Continue"
echo "   - Upload: $CSR_INST"
echo "   - Download the certificate"
echo ""
echo "4. IMPORTANT: You may need to REVOKE the existing certificates first"
echo "   if Apple says you've reached the limit (usually 5 per type)"
echo ""

read -p "Press Enter when you've downloaded both certificates..."

# Step 3: Install certificates with private keys
echo -e "\n${BLUE}Step 3: Installing Certificates with Private Keys${NC}"
echo ""

# Find downloaded certificates
echo "Looking for downloaded certificates..."
DOWNLOADS=~/Downloads
APP_CERT=$(find "$DOWNLOADS" -name "*application*.cer" -o -name "*Application*.cer" | head -1)
INST_CERT=$(find "$DOWNLOADS" -name "*installer*.cer" -o -name "*Installer*.cer" | head -1)

if [ -z "$APP_CERT" ] || [ -z "$INST_CERT" ]; then
    echo -e "${YELLOW}Could not auto-detect certificates.${NC}"
    read -p "Enter path to Developer ID Application certificate: " APP_CERT
    read -p "Enter path to Developer ID Installer certificate: " INST_CERT
fi

echo "Found:"
echo "  App cert: $APP_CERT"
echo "  Installer cert: $INST_CERT"
echo ""

# Import private keys first
echo "Importing private keys..."
security import /tmp/app_private.key -k ~/Library/Keychains/login.keychain-db -T /usr/bin/codesign
security import /tmp/installer_private.key -k ~/Library/Keychains/login.keychain-db -T /usr/bin/codesign

# Import certificates
echo "Importing certificates..."
security import "$APP_CERT" -k ~/Library/Keychains/login.keychain-db
security import "$INST_CERT" -k ~/Library/Keychains/login.keychain-db

# Clean up
rm -f /tmp/app_private.key /tmp/installer_private.key "$CSR_APP" "$CSR_INST"

# Verify
echo -e "\n${BLUE}Step 4: Verifying Installation${NC}"
echo ""

VALID_IDS=$(security find-identity -v -p codesigning | grep "Developer ID" | wc -l)
if [ "$VALID_IDS" -ge 2 ]; then
    echo -e "${GREEN}✓ Success! Found $VALID_IDS valid signing identities:${NC}"
    security find-identity -v -p codesigning | grep "Developer ID"
    echo ""
    echo -e "${GREEN}You can now use the notarization scripts!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Run: ./scripts/setup_notarization_credentials.sh"
    echo "2. Run: ./scripts/test_notarization_simple.sh"
else
    echo -e "${YELLOW}⚠️  Warning: Expected 2 valid identities but found $VALID_IDS${NC}"
    echo "Check output above for errors."
fi
