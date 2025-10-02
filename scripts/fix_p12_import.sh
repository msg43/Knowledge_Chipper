#!/bin/bash
# fix_p12_import.sh - Convert and import legacy .p12 files

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔧 Fixing P12 Import Issues${NC}"
echo "==========================="
echo ""

# Clean up any existing certificates
echo "Cleaning up existing certificates..."
security delete-certificate -c "Matthew Seymour Greer" ~/Library/Keychains/login.keychain-db 2>/dev/null || true
security delete-certificate -c "Developer ID" ~/Library/Keychains/login.keychain-db 2>/dev/null || true

# Convert legacy P12 files to PEM format
echo -e "\n${BLUE}Converting legacy P12 files...${NC}"

# Convert Application certificate
echo "Converting Application certificate..."
openssl pkcs12 -legacy -in docs/internal/Certificates.p12 -passin pass:katana -nodes -out /tmp/app_cert.pem 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Application certificate converted"
else
    echo -e "${YELLOW}⚠${NC} Failed to convert Application certificate"
fi

# Convert Installer certificate
echo "Converting Installer certificate..."
openssl pkcs12 -legacy -in docs/internal/Certificates2.p12 -passin pass:katana -nodes -out /tmp/inst_cert.pem 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Installer certificate converted"
else
    echo -e "${YELLOW}⚠${NC} Failed to convert Installer certificate"
fi

# Extract certificates and keys separately
echo -e "\n${BLUE}Extracting certificates and keys...${NC}"

# Application certificate
openssl x509 -in /tmp/app_cert.pem -out /tmp/app_cert.crt
openssl pkey -in /tmp/app_cert.pem -out /tmp/app_key.key

# Installer certificate
openssl x509 -in /tmp/inst_cert.pem -out /tmp/inst_cert.crt
openssl pkey -in /tmp/inst_cert.pem -out /tmp/inst_key.key

# Create new P12 files with modern encryption
echo -e "\n${BLUE}Creating modern P12 files...${NC}"

# Application P12
openssl pkcs12 -export -in /tmp/app_cert.crt -inkey /tmp/app_key.key \
    -out /tmp/app_modern.p12 -passout pass:katana \
    -name "Developer ID Application" 2>/dev/null

# Installer P12
openssl pkcs12 -export -in /tmp/inst_cert.crt -inkey /tmp/inst_key.key \
    -out /tmp/inst_modern.p12 -passout pass:katana \
    -name "Developer ID Installer" 2>/dev/null

# Import to keychain
echo -e "\n${BLUE}Importing to keychain...${NC}"

# Import Application certificate
echo "Importing Application certificate..."
security import /tmp/app_modern.p12 -k ~/Library/Keychains/login.keychain-db \
    -P "katana" -T /usr/bin/codesign -T /usr/bin/productbuild

# Import Installer certificate
echo "Importing Installer certificate..."
security import /tmp/inst_modern.p12 -k ~/Library/Keychains/login.keychain-db \
    -P "katana" -T /usr/bin/codesign -T /usr/bin/productbuild

# Clean up temp files
rm -f /tmp/app_cert.pem /tmp/inst_cert.pem /tmp/app_cert.crt /tmp/inst_cert.crt \
      /tmp/app_key.key /tmp/inst_key.key /tmp/app_modern.p12 /tmp/inst_modern.p12 \
      /tmp/temp_cert.pem /tmp/temp_cert2.pem /tmp/modern_cert.p12

# Verify installation
echo -e "\n${BLUE}Verifying installation...${NC}"
VALID_IDS=$(security find-identity -v -p codesigning | grep "Developer ID" | wc -l)

if [ "$VALID_IDS" -ge 2 ]; then
    echo -e "\n${GREEN}✅ Success! Found $VALID_IDS valid signing identities:${NC}"
    security find-identity -v -p codesigning | grep "Developer ID"
else
    echo -e "\n${YELLOW}⚠️  Found $VALID_IDS identities (expected 2)${NC}"
    echo ""
    echo "Checking all certificates:"
    security find-certificate -a ~/Library/Keychains/login.keychain-db | grep -A2 "Developer ID" | head -20
fi

echo ""
echo "Done!"
