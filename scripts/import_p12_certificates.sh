#!/bin/bash
# import_p12_certificates.sh - Import certificates from .p12 file

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔑 Import Certificates from .p12 File${NC}"
echo "====================================="
echo ""
echo "This imports certificates WITH their private keys from a .p12 backup"
echo ""

# Find .p12 files
echo "Looking for .p12 files..."
P12_FILES=$(find ~ -name "*.p12" -not -path "*/Library/*" -not -path "*/.Trash/*" 2>/dev/null | head -10)

if [ ! -z "$P12_FILES" ]; then
    echo "Found .p12 files:"
    echo "$P12_FILES"
    echo ""
fi

# Get the .p12 file path
read -p "Enter the path to your .p12 file: " P12_FILE

if [ ! -f "$P12_FILE" ]; then
    echo -e "${RED}✗${NC} File not found: $P12_FILE"
    exit 1
fi

# Import the .p12 file
echo -e "\n${BLUE}Importing certificates and private keys...${NC}"
echo "You'll be prompted for:"
echo "1. The password you set when exporting the .p12 file"
echo "2. Your macOS login password (to access keychain)"
echo ""

security import "$P12_FILE" -k ~/Library/Keychains/login.keychain-db -T /usr/bin/codesign -T /usr/bin/productbuild

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓${NC} Import successful!"

    # Verify
    echo -e "\n${BLUE}Verifying certificates...${NC}"
    VALID_IDS=$(security find-identity -v -p codesigning | grep "Developer ID")

    if [ ! -z "$VALID_IDS" ]; then
        echo -e "${GREEN}✓ Found valid signing identities:${NC}"
        echo "$VALID_IDS"
        echo ""
        echo -e "${GREEN}Success! You can now use the notarization scripts.${NC}"
        echo ""
        echo "Next steps:"
        echo "1. Run: ./scripts/setup_notarization_credentials.sh"
        echo "2. Run: ./scripts/test_notarization_simple.sh"
    else
        echo -e "${YELLOW}⚠️${NC} Certificates imported but not showing as valid identities"
        echo "This might mean the private keys weren't included in the .p12 file"
    fi
else
    echo -e "${RED}✗${NC} Import failed. Check the password and try again."
fi
