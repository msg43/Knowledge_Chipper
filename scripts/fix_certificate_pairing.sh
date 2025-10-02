#!/bin/bash
# fix_certificate_pairing.sh - Fix certificate and private key pairing

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔧 Fixing Certificate-Key Pairing${NC}"
echo "================================="
echo ""
echo "You have certificates and keys, but they're not linked."
echo "This script will fix the pairing."
echo ""

# Step 1: Export certificates to files
echo -e "${BLUE}Step 1: Exporting certificates...${NC}"
security find-certificate -c "Developer ID Application: Matthew Seymour Greer" -p > /tmp/app_cert.pem
security find-certificate -c "Developer ID Installer: Matthew Seymour Greer" -p > /tmp/inst_cert.pem

# Step 2: Clean everything
echo -e "\n${BLUE}Step 2: Cleaning keychain...${NC}"
echo -e "${YELLOW}This will remove all Developer ID items. Continue? (y/n)${NC}"
read -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Delete certificates
security delete-certificate -c "Developer ID Application: Matthew Seymour Greer" 2>/dev/null || true
security delete-certificate -c "Developer ID Installer: Matthew Seymour Greer" 2>/dev/null || true

# List all generic passwords/keys that might be related
echo -e "\n${BLUE}Cleaning up imported private keys...${NC}"
echo "Please manually delete the 'Imported Private Key' items in Keychain Access"
echo "Then press Enter to continue..."
read

# Step 3: Re-import from original p12 files with forced pairing
echo -e "\n${BLUE}Step 3: Re-importing with proper pairing...${NC}"

# Convert p12 to pem with both cert and key
openssl pkcs12 -in docs/internal/Certificates.p12 -passin pass:katana -out /tmp/app_full.pem -nodes -legacy
openssl pkcs12 -in docs/internal/Certificates2.p12 -passin pass:katana -out /tmp/inst_full.pem -nodes -legacy

# Create new p12 with proper attributes
openssl pkcs12 -export \
    -in /tmp/app_full.pem \
    -out /tmp/app_final.p12 \
    -passout pass:temppass \
    -name "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)"

openssl pkcs12 -export \
    -in /tmp/inst_full.pem \
    -out /tmp/inst_final.p12 \
    -passout pass:temppass \
    -name "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"

# Import with all permissions
echo -e "\n${BLUE}Importing certificates with keys...${NC}"
security import /tmp/app_final.p12 -k ~/Library/Keychains/login.keychain-db -P temppass -T /usr/bin/codesign -T /usr/bin/productbuild -T /usr/bin/security
security import /tmp/inst_final.p12 -k ~/Library/Keychains/login.keychain-db -P temppass -T /usr/bin/codesign -T /usr/bin/productbuild -T /usr/bin/security

# Clean up
rm -f /tmp/*.pem /tmp/*.p12

# Step 4: Verify
echo -e "\n${BLUE}Step 4: Verifying...${NC}"
echo "Waiting for keychain to update..."
sleep 2

IDENTITIES=$(security find-identity -v -p codesigning)
if echo "$IDENTITIES" | grep -q "2 valid identities found"; then
    echo -e "\n${GREEN}✅ SUCCESS! Certificates are now properly paired:${NC}"
    echo "$IDENTITIES"
else
    echo -e "\n${YELLOW}⚠️  Still showing issues. Trying alternate method...${NC}"

    # Try to manually set certificate trust
    echo -e "\n${BLUE}Setting certificate trust...${NC}"
    echo "In Keychain Access:"
    echo "1. Double-click each Developer ID certificate"
    echo "2. Expand 'Trust' section"
    echo "3. Set 'Code Signing' to 'Always Trust'"
    echo "4. Close and authenticate with your password"
    echo ""
    echo "After doing this for both certificates, run:"
    echo "  security find-identity -v -p codesigning"
fi

echo ""
echo "Done!"
