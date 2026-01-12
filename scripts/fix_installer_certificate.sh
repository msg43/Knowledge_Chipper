#!/bin/bash
# fix_installer_certificate.sh
# Identifies and optionally removes the broken Developer ID Installer certificate
# See docs/PKG_NOTARIZATION_FIX.md for details

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Developer ID Installer Certificate Diagnostic${NC}"
echo "=============================================="
echo ""

# Certificate SHA-1 hashes
BROKEN_CERT="40BD7C59C03F68AC4B37EC4E431DC57A219109A8"
WORKING_CERT="773033671956B8F6DD90593740863F2E48AD2024"

echo "Checking for Developer ID Installer certificates..."
echo ""

# Check for broken certificate
if security find-identity -v -p basic | grep -q "$BROKEN_CERT"; then
    echo -e "${RED}✗ BROKEN CERTIFICATE FOUND${NC}"
    echo "  SHA-1: $BROKEN_CERT"
    echo "  Issued: Sep 21, 2025"
    echo "  Status: Fails notarization with certificate chain error"
    BROKEN_FOUND=true
else
    echo -e "${GREEN}✓ Broken certificate not found${NC}"
    BROKEN_FOUND=false
fi

echo ""

# Check for working certificate
if security find-identity -v -p basic | grep -q "$WORKING_CERT"; then
    echo -e "${GREEN}✓ WORKING CERTIFICATE FOUND${NC}"
    echo "  SHA-1: $WORKING_CERT"
    echo "  Issued: Oct 4, 2025"
    echo "  Status: Passes notarization successfully"
    WORKING_FOUND=true
else
    echo -e "${RED}✗ Working certificate not found${NC}"
    echo "  You may need to download it from Apple Developer portal"
    WORKING_FOUND=false
fi

echo ""
echo "=============================================="
echo ""

# Provide recommendations
if [ "$BROKEN_FOUND" = true ] && [ "$WORKING_FOUND" = true ]; then
    echo -e "${YELLOW}RECOMMENDATION:${NC}"
    echo "You have both certificates installed. The build scripts have been"
    echo "updated to use the working certificate (Oct 2025) by default."
    echo ""
    echo "You can optionally remove the broken certificate to avoid confusion:"
    echo ""
    read -p "Remove broken certificate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Removing broken certificate..."
        security delete-certificate -Z "$BROKEN_CERT" 2>&1 || {
            echo -e "${RED}Failed to remove certificate.${NC}"
            echo "You may need to remove it manually from Keychain Access:"
            echo "1. Open Keychain Access"
            echo "2. Search for 'Developer ID Installer'"
            echo "3. Find the certificate issued on Sep 21, 2025"
            echo "4. Right-click and select 'Delete'"
            exit 1
        }
        echo -e "${GREEN}✓ Broken certificate removed${NC}"
    else
        echo ""
        echo "Certificate kept. Build scripts will use the working certificate."
    fi
elif [ "$BROKEN_FOUND" = true ] && [ "$WORKING_FOUND" = false ]; then
    echo -e "${RED}WARNING:${NC}"
    echo "Only the broken certificate is installed. You need to:"
    echo "1. Download the working certificate from Apple Developer portal"
    echo "2. Install it in your keychain"
    echo "3. Run this script again to verify"
elif [ "$BROKEN_FOUND" = false ] && [ "$WORKING_FOUND" = true ]; then
    echo -e "${GREEN}✓ PERFECT SETUP${NC}"
    echo "Only the working certificate is installed. No action needed."
else
    echo -e "${RED}ERROR:${NC}"
    echo "No Developer ID Installer certificates found."
    echo "Please download and install your certificate from:"
    echo "https://developer.apple.com/account/resources/certificates/list"
fi

echo ""
echo "For more information, see: docs/PKG_NOTARIZATION_FIX.md"
