#!/bin/bash
# diagnose_notarization_root_cause.sh
# Automated diagnostic to identify the source of notarization failures
# Based on Apple Support feedback for Case ID: 102789234714

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
TEST_DIR="/tmp/notarization_diagnosis_$$"
RESULTS_FILE="$TEST_DIR/diagnosis_results.txt"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Credentials (will prompt if not set)
APPLE_ID="${APPLE_ID:-Matt@rainfall.llc}"
TEAM_ID="${TEAM_ID:-W2AT7M9482}"

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     NOTARIZATION ROOT CAUSE DIAGNOSTIC                         ║${NC}"
echo -e "${CYAN}║     Apple Case ID: 102789234714                                ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Create test directory
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

echo "Test directory: $TEST_DIR"
echo "Results will be saved to: $RESULTS_FILE"
echo ""

# Initialize results file
cat > "$RESULTS_FILE" << EOF
NOTARIZATION DIAGNOSTIC RESULTS
================================
Date: $(date)
Test Directory: $TEST_DIR
Apple ID: $APPLE_ID
Team ID: $TEAM_ID

EOF

# Get password if not set
if [ -z "$APP_PASSWORD" ]; then
    echo -e "${YELLOW}Enter app-specific password:${NC}"
    read -s APP_PASSWORD
    echo ""
fi

# Find certificates
echo -e "${BLUE}[1/7] Finding certificates...${NC}"
DEV_ID_APP="Developer ID Application: Matthew Seymour Greer (W2AT7M9482)"
DEV_ID_INST="Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"

echo "  App cert: $DEV_ID_APP"
echo "  Installer cert: $DEV_ID_INST"

echo "" >> "$RESULTS_FILE"
echo "CERTIFICATES" >> "$RESULTS_FILE"
echo "------------" >> "$RESULTS_FILE"
security find-identity -v >> "$RESULTS_FILE" 2>&1

#####################################################################
# TEST 1: Compiled Swift binary with ditto (Apple's recommended way)
#####################################################################
echo ""
echo -e "${BLUE}[2/7] TEST 1: Compiled Swift binary + ditto (Apple's way)${NC}"

TEST1_DIR="$TEST_DIR/test1_swift_ditto"
mkdir -p "$TEST1_DIR/SwiftTest.app/Contents/MacOS"
mkdir -p "$TEST1_DIR/SwiftTest.app/Contents/Resources"

# Create Info.plist
cat > "$TEST1_DIR/SwiftTest.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>SwiftTest</string>
    <key>CFBundleIdentifier</key>
    <string>com.greer.swifttest</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>SwiftTest</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Create and compile Swift source
cat > "$TEST1_DIR/main.swift" << 'EOF'
import Foundation
print("SwiftTest - Notarization diagnostic binary")
EOF

echo "  Compiling Swift binary..."
swiftc -o "$TEST1_DIR/SwiftTest.app/Contents/MacOS/SwiftTest" "$TEST1_DIR/main.swift" 2>&1 || {
    echo -e "  ${RED}Swift compilation failed, trying C...${NC}"
    # Fallback to C
    cat > "$TEST1_DIR/main.c" << 'CEOF'
#include <stdio.h>
int main() {
    printf("CTest - Notarization diagnostic binary\n");
    return 0;
}
CEOF
    clang -o "$TEST1_DIR/SwiftTest.app/Contents/MacOS/SwiftTest" "$TEST1_DIR/main.c"
}

# Sign with hardened runtime
echo "  Signing app bundle..."
codesign --force --options runtime --timestamp --sign "$DEV_ID_APP" \
    "$TEST1_DIR/SwiftTest.app" --verbose 2>&1 | tee -a "$RESULTS_FILE"

# Verify signature
echo "  Verifying signature..."
codesign --verify --deep --strict --verbose=4 "$TEST1_DIR/SwiftTest.app" 2>&1 | tee -a "$RESULTS_FILE"

# Check binary type
echo "" >> "$RESULTS_FILE"
echo "TEST 1: Binary Info" >> "$RESULTS_FILE"
file "$TEST1_DIR/SwiftTest.app/Contents/MacOS/SwiftTest" >> "$RESULTS_FILE"

# Package with ditto (Apple's recommended method)
echo "  Packaging with ditto..."
ditto -c -k --keepParent "$TEST1_DIR/SwiftTest.app" "$TEST1_DIR/SwiftTest.zip"
echo "  Created: $TEST1_DIR/SwiftTest.zip ($(du -h "$TEST1_DIR/SwiftTest.zip" | cut -f1))"

# Detailed codesign info
echo "" >> "$RESULTS_FILE"
echo "TEST 1: Detailed Code Signature" >> "$RESULTS_FILE"
codesign -dvvv "$TEST1_DIR/SwiftTest.app" >> "$RESULTS_FILE" 2>&1

# Submit for notarization
echo "  Submitting for notarization..."
TEST1_RESULT=$(xcrun notarytool submit "$TEST1_DIR/SwiftTest.zip" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_PASSWORD" \
    --wait 2>&1) || true

echo "$TEST1_RESULT" | tee -a "$RESULTS_FILE"

if echo "$TEST1_RESULT" | grep -q "status: Accepted"; then
    echo -e "  ${GREEN}✓ TEST 1 PASSED: Swift binary + ditto works!${NC}"
    TEST1_STATUS="PASSED"
else
    echo -e "  ${RED}✗ TEST 1 FAILED${NC}"
    TEST1_STATUS="FAILED"
    # Get detailed log
    TEST1_ID=$(echo "$TEST1_RESULT" | grep "id:" | head -1 | awk '{print $2}')
    if [ -n "$TEST1_ID" ]; then
        echo "  Getting detailed log for $TEST1_ID..."
        xcrun notarytool log "$TEST1_ID" \
            --apple-id "$APPLE_ID" \
            --team-id "$TEAM_ID" \
            --password "$APP_PASSWORD" 2>&1 | tee -a "$RESULTS_FILE"
    fi
fi

#####################################################################
# TEST 2: Compiled binary with pkgbuild (our current method)
#####################################################################
echo ""
echo -e "${BLUE}[3/7] TEST 2: Compiled binary + pkgbuild (our method)${NC}"

TEST2_DIR="$TEST_DIR/test2_binary_pkg"
mkdir -p "$TEST2_DIR/BinaryTest.app/Contents/MacOS"

# Create Info.plist
cat > "$TEST2_DIR/BinaryTest.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>BinaryTest</string>
    <key>CFBundleIdentifier</key>
    <string>com.greer.binarytest</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>BinaryTest</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
</dict>
</plist>
EOF

# Create and compile
cat > "$TEST2_DIR/main.c" << 'EOF'
#include <stdio.h>
int main() {
    printf("BinaryTest - PKG diagnostic\n");
    return 0;
}
EOF

echo "  Compiling C binary..."
clang -o "$TEST2_DIR/BinaryTest.app/Contents/MacOS/BinaryTest" "$TEST2_DIR/main.c"

# Sign
echo "  Signing app bundle..."
codesign --force --options runtime --timestamp --sign "$DEV_ID_APP" \
    "$TEST2_DIR/BinaryTest.app" --verbose 2>&1 | tee -a "$RESULTS_FILE"

# Package with pkgbuild (our method)
echo "  Packaging with pkgbuild..."
pkgbuild --component "$TEST2_DIR/BinaryTest.app" \
    --install-location "/Applications" \
    --sign "$DEV_ID_INST" \
    "$TEST2_DIR/BinaryTest.pkg" 2>&1 | tee -a "$RESULTS_FILE"

echo "  Created: $TEST2_DIR/BinaryTest.pkg ($(du -h "$TEST2_DIR/BinaryTest.pkg" | cut -f1))"

# Submit for notarization
echo "  Submitting for notarization..."
TEST2_RESULT=$(xcrun notarytool submit "$TEST2_DIR/BinaryTest.pkg" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_PASSWORD" \
    --wait 2>&1) || true

echo "$TEST2_RESULT" | tee -a "$RESULTS_FILE"

if echo "$TEST2_RESULT" | grep -q "status: Accepted"; then
    echo -e "  ${GREEN}✓ TEST 2 PASSED: Compiled binary + pkgbuild works!${NC}"
    TEST2_STATUS="PASSED"
else
    echo -e "  ${RED}✗ TEST 2 FAILED${NC}"
    TEST2_STATUS="FAILED"
    TEST2_ID=$(echo "$TEST2_RESULT" | grep "id:" | head -1 | awk '{print $2}')
    if [ -n "$TEST2_ID" ]; then
        echo "  Getting detailed log for $TEST2_ID..."
        xcrun notarytool log "$TEST2_ID" \
            --apple-id "$APPLE_ID" \
            --team-id "$TEAM_ID" \
            --password "$APP_PASSWORD" 2>&1 | tee -a "$RESULTS_FILE"
    fi
fi

#####################################################################
# TEST 3: Shell script with ditto (what we had + Apple's packaging)
#####################################################################
echo ""
echo -e "${BLUE}[4/7] TEST 3: Shell script + ditto${NC}"

TEST3_DIR="$TEST_DIR/test3_script_ditto"
mkdir -p "$TEST3_DIR/ScriptTest.app/Contents/MacOS"

cat > "$TEST3_DIR/ScriptTest.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>ScriptTest</string>
    <key>CFBundleIdentifier</key>
    <string>com.greer.scripttest</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>ScriptTest</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
</dict>
</plist>
EOF

# Shell script executable (what our original test used)
cat > "$TEST3_DIR/ScriptTest.app/Contents/MacOS/ScriptTest" << 'EOF'
#!/bin/bash
echo "ScriptTest - Shell script diagnostic"
EOF
chmod +x "$TEST3_DIR/ScriptTest.app/Contents/MacOS/ScriptTest"

echo "  Signing shell script app..."
codesign --force --options runtime --timestamp --sign "$DEV_ID_APP" \
    "$TEST3_DIR/ScriptTest.app" --verbose 2>&1 | tee -a "$RESULTS_FILE"

echo "  Packaging with ditto..."
ditto -c -k --keepParent "$TEST3_DIR/ScriptTest.app" "$TEST3_DIR/ScriptTest.zip"

echo "  Submitting for notarization..."
TEST3_RESULT=$(xcrun notarytool submit "$TEST3_DIR/ScriptTest.zip" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_PASSWORD" \
    --wait 2>&1) || true

echo "$TEST3_RESULT" | tee -a "$RESULTS_FILE"

if echo "$TEST3_RESULT" | grep -q "status: Accepted"; then
    echo -e "  ${GREEN}✓ TEST 3 PASSED: Shell script + ditto works!${NC}"
    TEST3_STATUS="PASSED"
else
    echo -e "  ${RED}✗ TEST 3 FAILED${NC}"
    TEST3_STATUS="FAILED"
    TEST3_ID=$(echo "$TEST3_RESULT" | grep "id:" | head -1 | awk '{print $2}')
    if [ -n "$TEST3_ID" ]; then
        xcrun notarytool log "$TEST3_ID" \
            --apple-id "$APPLE_ID" \
            --team-id "$TEAM_ID" \
            --password "$APP_PASSWORD" 2>&1 | tee -a "$RESULTS_FILE"
    fi
fi

#####################################################################
# TEST 4: Shell script with pkgbuild (our original failing test)
#####################################################################
echo ""
echo -e "${BLUE}[5/7] TEST 4: Shell script + pkgbuild (our original test)${NC}"

TEST4_DIR="$TEST_DIR/test4_script_pkg"
mkdir -p "$TEST4_DIR/OrigTest.app/Contents/MacOS"

cat > "$TEST4_DIR/OrigTest.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>OrigTest</string>
    <key>CFBundleIdentifier</key>
    <string>com.test.notarization</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>OrigTest</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
</dict>
</plist>
EOF

cat > "$TEST4_DIR/OrigTest.app/Contents/MacOS/OrigTest" << 'EOF'
#!/bin/bash
echo "Test app"
EOF
chmod +x "$TEST4_DIR/OrigTest.app/Contents/MacOS/OrigTest"

echo "  Signing shell script app..."
codesign --force --options runtime --timestamp --sign "$DEV_ID_APP" \
    "$TEST4_DIR/OrigTest.app" --verbose 2>&1 | tee -a "$RESULTS_FILE"

echo "  Packaging with pkgbuild..."
pkgbuild --component "$TEST4_DIR/OrigTest.app" \
    --install-location "/Applications" \
    --sign "$DEV_ID_INST" \
    "$TEST4_DIR/OrigTest.pkg" 2>&1 | tee -a "$RESULTS_FILE"

echo "  Submitting for notarization..."
TEST4_RESULT=$(xcrun notarytool submit "$TEST4_DIR/OrigTest.pkg" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_PASSWORD" \
    --wait 2>&1) || true

echo "$TEST4_RESULT" | tee -a "$RESULTS_FILE"

if echo "$TEST4_RESULT" | grep -q "status: Accepted"; then
    echo -e "  ${GREEN}✓ TEST 4 PASSED${NC}"
    TEST4_STATUS="PASSED"
else
    echo -e "  ${RED}✗ TEST 4 FAILED (expected - this is what we had before)${NC}"
    TEST4_STATUS="FAILED"
    TEST4_ID=$(echo "$TEST4_RESULT" | grep "id:" | head -1 | awk '{print $2}')
    if [ -n "$TEST4_ID" ]; then
        xcrun notarytool log "$TEST4_ID" \
            --apple-id "$APPLE_ID" \
            --team-id "$TEAM_ID" \
            --password "$APP_PASSWORD" 2>&1 | tee -a "$RESULTS_FILE"
    fi
fi

#####################################################################
# TEST 5: productbuild vs pkgbuild
#####################################################################
echo ""
echo -e "${BLUE}[6/7] TEST 5: Compiled binary + productbuild${NC}"

TEST5_DIR="$TEST_DIR/test5_productbuild"
mkdir -p "$TEST5_DIR/ProdTest.app/Contents/MacOS"

cat > "$TEST5_DIR/ProdTest.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>ProdTest</string>
    <key>CFBundleIdentifier</key>
    <string>com.greer.prodtest</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>ProdTest</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
</dict>
</plist>
EOF

cat > "$TEST5_DIR/main.c" << 'EOF'
#include <stdio.h>
int main() {
    printf("ProdTest - productbuild diagnostic\n");
    return 0;
}
EOF

clang -o "$TEST5_DIR/ProdTest.app/Contents/MacOS/ProdTest" "$TEST5_DIR/main.c"

echo "  Signing app..."
codesign --force --options runtime --timestamp --sign "$DEV_ID_APP" \
    "$TEST5_DIR/ProdTest.app" --verbose 2>&1 | tee -a "$RESULTS_FILE"

echo "  Packaging with productbuild..."
productbuild --component "$TEST5_DIR/ProdTest.app" /Applications \
    --sign "$DEV_ID_INST" \
    "$TEST5_DIR/ProdTest.pkg" 2>&1 | tee -a "$RESULTS_FILE"

echo "  Submitting for notarization..."
TEST5_RESULT=$(xcrun notarytool submit "$TEST5_DIR/ProdTest.pkg" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_PASSWORD" \
    --wait 2>&1) || true

echo "$TEST5_RESULT" | tee -a "$RESULTS_FILE"

if echo "$TEST5_RESULT" | grep -q "status: Accepted"; then
    echo -e "  ${GREEN}✓ TEST 5 PASSED: productbuild works!${NC}"
    TEST5_STATUS="PASSED"
else
    echo -e "  ${RED}✗ TEST 5 FAILED${NC}"
    TEST5_STATUS="FAILED"
    TEST5_ID=$(echo "$TEST5_RESULT" | grep "id:" | head -1 | awk '{print $2}')
    if [ -n "$TEST5_ID" ]; then
        xcrun notarytool log "$TEST5_ID" \
            --apple-id "$APPLE_ID" \
            --team-id "$TEAM_ID" \
            --password "$APP_PASSWORD" 2>&1 | tee -a "$RESULTS_FILE"
    fi
fi

#####################################################################
# SUMMARY
#####################################################################
echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                    DIAGNOSTIC SUMMARY                          ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo "TEST RESULTS MATRIX"
echo "==================="
echo ""
printf "%-40s | %-10s\n" "Test" "Result"
echo "-----------------------------------------+-----------"
printf "%-40s | %-10s\n" "TEST 1: Swift/C binary + ditto (.zip)" "$TEST1_STATUS"
printf "%-40s | %-10s\n" "TEST 2: C binary + pkgbuild (.pkg)" "$TEST2_STATUS"
printf "%-40s | %-10s\n" "TEST 3: Shell script + ditto (.zip)" "$TEST3_STATUS"
printf "%-40s | %-10s\n" "TEST 4: Shell script + pkgbuild (.pkg)" "$TEST4_STATUS"
printf "%-40s | %-10s\n" "TEST 5: C binary + productbuild (.pkg)" "$TEST5_STATUS"
echo ""

# Analysis
echo -e "${BLUE}[7/7] ANALYSIS${NC}"
echo ""

# Save summary to results file
cat >> "$RESULTS_FILE" << EOF

===================
DIAGNOSTIC SUMMARY
===================
TEST 1 (Swift/C binary + ditto): $TEST1_STATUS
TEST 2 (C binary + pkgbuild): $TEST2_STATUS
TEST 3 (Shell script + ditto): $TEST3_STATUS
TEST 4 (Shell script + pkgbuild): $TEST4_STATUS
TEST 5 (C binary + productbuild): $TEST5_STATUS
EOF

# Determine root cause
if [ "$TEST1_STATUS" = "PASSED" ]; then
    echo -e "${GREEN}✓ GOOD NEWS: Certificates work with Apple's recommended workflow!${NC}"
    echo ""
    
    if [ "$TEST2_STATUS" = "FAILED" ] && [ "$TEST5_STATUS" = "FAILED" ]; then
        echo -e "${YELLOW}→ CONCLUSION: Problem is with PKG packaging method${NC}"
        echo "  The certificates work fine with .zip but not with .pkg"
        echo "  Consider distributing as .zip instead of .pkg"
    elif [ "$TEST3_STATUS" = "FAILED" ] && [ "$TEST4_STATUS" = "FAILED" ]; then
        echo -e "${YELLOW}→ CONCLUSION: Problem is with shell script executables${NC}"
        echo "  The certificates work with compiled binaries but not scripts"
        echo "  Your actual app likely uses compiled binaries, so this may not apply"
    elif [ "$TEST2_STATUS" = "PASSED" ] && [ "$TEST4_STATUS" = "FAILED" ]; then
        echo -e "${YELLOW}→ CONCLUSION: Problem is BOTH shell scripts AND pkgbuild together${NC}"
        echo "  Compiled binaries work with any packaging method"
    fi
else
    echo -e "${RED}✗ BAD NEWS: Even Apple's recommended workflow fails${NC}"
    echo "  This indicates a deeper issue with certificates/account"
    echo "  Report back to Apple Support with these results"
fi

echo ""
echo "Full results saved to: $RESULTS_FILE"
echo "Test directory: $TEST_DIR"
echo ""
echo "To clean up: rm -rf $TEST_DIR"

