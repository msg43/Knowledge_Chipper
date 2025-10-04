#!/bin/bash
# diagnose_certificate_chain.sh - Deep dive into certificate chain issues

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔍 Certificate Chain Diagnosis${NC}"
echo "=============================="
echo ""

# 1. Check certificate details
echo -e "${BLUE}1. Certificate Details:${NC}"
security find-identity -v -p codesigning | grep "Developer ID" || echo "No codesigning identities found"
echo ""

# 2. Export full certificate chain
echo -e "${BLUE}2. Exporting certificate chain...${NC}"
security find-certificate -c "Developer ID Application: Matthew Seymour Greer" -p > /tmp/app_cert.pem
security find-certificate -c "Developer ID Certification Authority" -p > /tmp/intermediate.pem
security find-certificate -c "Apple Root CA" -p > /tmp/root.pem 2>/dev/null || echo "Apple Root CA not found in current keychain"

# 3. Verify chain manually
echo -e "\n${BLUE}3. Manual chain verification:${NC}"
if [ -f /tmp/root.pem ]; then
    cat /tmp/intermediate.pem /tmp/root.pem > /tmp/chain.pem
    openssl verify -CAfile /tmp/chain.pem /tmp/app_cert.pem 2>&1 || echo "Chain verification failed"
else
    echo "Cannot verify - Apple Root CA missing"
fi

# 4. Check trust settings
echo -e "\n${BLUE}4. Current trust settings:${NC}"
security trust-settings-export -d /tmp/trust.plist 2>&1 || echo "No custom trust settings"
if [ -f /tmp/trust.plist ]; then
    echo "Custom trust settings exist - checking for Developer ID entries:"
    plutil -p /tmp/trust.plist | grep -A5 -B5 "Developer" || echo "No Developer ID trust settings found"
fi

# 5. Test with different signing methods
echo -e "\n${BLUE}5. Testing different signing approaches:${NC}"

# Create test executable
cat > /tmp/test_app.c << 'EOF'
#include <stdio.h>
int main() { printf("Hello\n"); return 0; }
EOF
clang -o /tmp/test_app /tmp/test_app.c

# Method 1: Basic signing
echo -e "\n${YELLOW}Method 1: Basic signing${NC}"
codesign -f -s "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)" /tmp/test_app 2>&1 | grep -v "replacing existing signature" || true

# Method 2: With specific keychain
echo -e "\n${YELLOW}Method 2: With keychain specified${NC}"
codesign -f -s "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)" \
    --keychain ~/Library/Keychains/login.keychain-db /tmp/test_app 2>&1 | grep -v "replacing existing signature" || true

# Method 3: Without runtime hardening
echo -e "\n${YELLOW}Method 3: Without runtime options${NC}"
codesign -f -s "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)" \
    --timestamp=none /tmp/test_app 2>&1 | grep -v "replacing existing signature" || true

# 6. Check certificate constraints
echo -e "\n${BLUE}6. Certificate constraints:${NC}"
security find-certificate -c "Developer ID Application: Matthew Seymour Greer" -p | \
    openssl x509 -text -noout | grep -A10 "Basic Constraints" || echo "No constraints found"

# 7. System information
echo -e "\n${BLUE}7. System information:${NC}"
echo "macOS version: $(sw_vers -productVersion)"
echo "Xcode version: $(xcodebuild -version 2>/dev/null | head -1 || echo 'Not installed')"
echo "Security framework: $(security 2>&1 | head -1)"

# Clean up
rm -f /tmp/app_cert.pem /tmp/intermediate.pem /tmp/root.pem /tmp/chain.pem /tmp/trust.plist /tmp/test_app /tmp/test_app.c

echo -e "\n${BLUE}Diagnosis complete.${NC}"
