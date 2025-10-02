#!/bin/bash
# fix_apple_root_certificates.sh - Install Apple root certificates in System keychain

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔧 Fixing Apple Root Certificate Installation${NC}"
echo "==========================================="
echo ""
echo "The issue: Apple Root CA certificates are in your user keychain"
echo "but need to be in the System keychain for code signing to work."
echo ""

# Export certificates from login keychain
echo -e "${BLUE}Exporting Apple certificates from login keychain...${NC}"
security find-certificate -c "Apple Root CA" -p ~/Library/Keychains/login.keychain-db > /tmp/apple_root_ca.pem
security find-certificate -c "Apple Root CA - G2" -p ~/Library/Keychains/login.keychain-db > /tmp/apple_root_ca_g2.pem 2>/dev/null || true

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}This script needs to run with sudo to add certificates to System keychain${NC}"
    echo ""
    echo "Please run:"
    echo "  sudo ./scripts/fix_apple_root_certificates.sh"
    exit 1
fi

# Add to System keychain
echo -e "\n${BLUE}Adding Apple Root CA to System keychain...${NC}"
security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain /tmp/apple_root_ca.pem

if [ -f /tmp/apple_root_ca_g2.pem ]; then
    echo -e "${BLUE}Adding Apple Root CA - G2 to System keychain...${NC}"
    security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain /tmp/apple_root_ca_g2.pem
fi

# Clean up
rm -f /tmp/apple_root_ca.pem /tmp/apple_root_ca_g2.pem

echo -e "\n${GREEN}✅ Apple Root certificates installed in System keychain${NC}"

# Test signing
echo -e "\n${BLUE}Testing code signing...${NC}"
echo '#!/bin/bash\necho "test"' > /tmp/test_signing
chmod +x /tmp/test_signing

# Find the certificate
DEV_ID=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
if [ ! -z "$DEV_ID" ]; then
    if codesign -s "$DEV_ID" --force --timestamp /tmp/test_signing -v 2>&1; then
        echo -e "${GREEN}✅ Code signing works!${NC}"
    else
        echo -e "${YELLOW}⚠️  Code signing still has issues${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  No Developer ID Application certificate found${NC}"
fi

rm -f /tmp/test_signing

echo ""
echo "Next step: Try notarization again with:"
echo "  ./scripts/test_notarization_final.sh"
