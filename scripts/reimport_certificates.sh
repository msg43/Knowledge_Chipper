#!/bin/bash
# reimport_certificates.sh - Properly import .p12 files with private keys

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔑 Re-importing Certificates with Private Keys${NC}"
echo "============================================"
echo ""

# First, let's verify the .p12 files contain private keys
echo -e "${BLUE}Verifying .p12 files contain private keys...${NC}"

# Check first p12
echo "Checking Certificates.p12..."
if openssl pkcs12 -legacy -in docs/internal/Certificates.p12 -passin pass:katana -info -noout 2>&1 | grep -q "MAC verified OK"; then
    echo -e "${GREEN}✓${NC} Certificates.p12 is valid"
    # Check for private key
    if openssl pkcs12 -legacy -in docs/internal/Certificates.p12 -passin pass:katana -nocerts -nodes 2>/dev/null | grep -q "BEGIN PRIVATE KEY"; then
        echo -e "${GREEN}✓${NC} Contains private key"
    else
        echo -e "${RED}✗${NC} No private key found!"
    fi
else
    echo -e "${RED}✗${NC} Invalid or corrupt file"
fi

echo ""
echo "Checking Certificates2.p12..."
if openssl pkcs12 -legacy -in docs/internal/Certificates2.p12 -passin pass:katana -info -noout 2>&1 | grep -q "MAC verified OK"; then
    echo -e "${GREEN}✓${NC} Certificates2.p12 is valid"
    # Check for private key
    if openssl pkcs12 -legacy -in docs/internal/Certificates2.p12 -passin pass:katana -nocerts -nodes 2>/dev/null | grep -q "BEGIN PRIVATE KEY"; then
        echo -e "${GREEN}✓${NC} Contains private key"
    else
        echo -e "${RED}✗${NC} No private key found!"
    fi
else
    echo -e "${RED}✗${NC} Invalid or corrupt file"
fi

# Clean up existing certificates
echo -e "\n${BLUE}Removing existing certificates...${NC}"
# Remove by common name
security delete-certificate -c "Matthew Seymour Greer" ~/Library/Keychains/login.keychain-db 2>/dev/null || true
security delete-certificate -c "Developer ID Application" ~/Library/Keychains/login.keychain-db 2>/dev/null || true
security delete-certificate -c "Developer ID Installer" ~/Library/Keychains/login.keychain-db 2>/dev/null || true

# Try to delete by exact name from your screenshot
security delete-certificate -c "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)" ~/Library/Keychains/login.keychain-db 2>/dev/null || true
security delete-certificate -c "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)" ~/Library/Keychains/login.keychain-db 2>/dev/null || true

echo -e "${GREEN}✓${NC} Cleaned up existing certificates"

# Create a combined p12 with both certificates
echo -e "\n${BLUE}Creating combined certificate bundle...${NC}"

# Extract everything to PEM
openssl pkcs12 -legacy -in docs/internal/Certificates.p12 -passin pass:katana -out /tmp/app.pem -nodes 2>/dev/null
openssl pkcs12 -legacy -in docs/internal/Certificates2.p12 -passin pass:katana -out /tmp/inst.pem -nodes 2>/dev/null

# Create new p12 files with explicit settings
echo -e "\n${BLUE}Creating new P12 files with proper settings...${NC}"

# For Application certificate
openssl pkcs12 -export -legacy \
    -in /tmp/app.pem \
    -out /tmp/app_import.p12 \
    -passout pass:katana \
    -name "Developer ID Application"

# For Installer certificate
openssl pkcs12 -export -legacy \
    -in /tmp/inst.pem \
    -out /tmp/inst_import.p12 \
    -passout pass:katana \
    -name "Developer ID Installer"

echo -e "${GREEN}✓${NC} Created import files"

# Import with full permissions
echo -e "\n${BLUE}Importing certificates...${NC}"
echo -e "${YELLOW}Note: You may be prompted for your macOS password${NC}"

# Import with explicit ACL settings
security import /tmp/app_import.p12 -k ~/Library/Keychains/login.keychain-db \
    -f pkcs12 -P katana -A -T /usr/bin/codesign -T /usr/bin/productbuild

security import /tmp/inst_import.p12 -k ~/Library/Keychains/login.keychain-db \
    -f pkcs12 -P katana -A -T /usr/bin/codesign -T /usr/bin/productbuild

# Clean up
rm -f /tmp/app.pem /tmp/inst.pem /tmp/app_import.p12 /tmp/inst_import.p12

# Verify
echo -e "\n${BLUE}Verifying import...${NC}"
IDENTITIES=$(security find-identity -v -p codesigning | grep "Developer ID")

if [ ! -z "$IDENTITIES" ]; then
    echo -e "${GREEN}✅ Success! Found valid signing identities:${NC}"
    echo "$IDENTITIES"
else
    echo -e "${RED}❌ No valid identities found${NC}"
    echo ""
    echo "This usually means:"
    echo "1. The private keys are missing from the .p12 files"
    echo "2. The keychain is locked"
    echo "3. The certificates don't match the private keys"
    echo ""
    echo -e "${YELLOW}Alternative: Manual Import${NC}"
    echo "1. Open Keychain Access"
    echo "2. File → Import Items..."
    echo "3. Select BOTH .p12 files at once (Cmd+Click)"
    echo "4. Import with password: katana"
    echo "5. If prompted, allow access for codesign and productbuild"
fi

echo ""
echo "Done!"
