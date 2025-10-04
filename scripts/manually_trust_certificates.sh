#!/bin/bash
# manually_trust_certificates.sh - Set explicit trust for Developer ID certificates

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔧 Setting Trust for Developer ID Certificates${NC}"
echo "============================================="
echo ""

# Export certificates
echo -e "${BLUE}Exporting Developer ID certificates...${NC}"
security find-certificate -c "Developer ID Application: Matthew Seymour Greer" -p > /tmp/dev_id_app.pem
security find-certificate -c "Developer ID Installer: Matthew Seymour Greer" -p > /tmp/dev_id_inst.pem

# Create trust settings
echo -e "\n${BLUE}Creating trust settings file...${NC}"
cat > /tmp/trust_settings.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>trustSettings</key>
    <dict>
        <key>Developer ID Application: Matthew Seymour Greer (W2AT7M9482)</key>
        <array>
            <dict>
                <key>kSecTrustSettingsPolicy</key>
                <data>
                AaEaAQ==
                </data>
                <key>kSecTrustSettingsResult</key>
                <integer>1</integer>
            </dict>
        </array>
        <key>Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)</key>
        <array>
            <dict>
                <key>kSecTrustSettingsPolicy</key>
                <data>
                AaEaAQ==
                </data>
                <key>kSecTrustSettingsResult</key>
                <integer>1</integer>
            </dict>
        </array>
    </dict>
</dict>
</plist>
EOF

echo -e "\n${BLUE}Manual Steps Required:${NC}"
echo ""
echo "1. Open Keychain Access"
echo ""
echo "2. For EACH Developer ID certificate:"
echo "   a. Double-click the certificate"
echo "   b. Expand 'Trust' section"
echo "   c. Set 'Code Signing' to 'Always Trust'"
echo "   d. Set 'When using this certificate' to 'Use System Defaults'"
echo "   e. Close and save (enter password)"
echo ""
echo "3. In Terminal, run these commands:"
echo ""
echo -e "${YELLOW}# Reset certificate trust${NC}"
echo "security trust-settings-export -d ~/Desktop/current_trust.plist"
echo ""
echo -e "${YELLOW}# Import certificates to System keychain (requires sudo)${NC}"
echo "sudo security add-certificates -k /Library/Keychains/System.keychain /tmp/dev_id_app.pem"
echo "sudo security add-certificates -k /Library/Keychains/System.keychain /tmp/dev_id_inst.pem"
echo ""
echo -e "${YELLOW}# Alternative: Use custom keychain${NC}"
echo "security create-keychain -p \"\" codesign.keychain"
echo "security import /tmp/dev_id_app.pem -k codesign.keychain"
echo "security import /tmp/dev_id_inst.pem -k codesign.keychain"
echo "security list-keychains -s ~/Library/Keychains/login.keychain-db codesign.keychain"
echo ""
echo "4. Test signing:"
echo "   codesign -s \"Developer ID Application: Matthew Seymour Greer (W2AT7M9482)\" --timestamp /tmp/test -v"
