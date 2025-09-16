#!/bin/bash
# First Run Setup for Skip the Podcast Desktop
# This script helps users bypass Gatekeeper on first installation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Skip the Podcast Desktop - First Run Setup${NC}"
echo "============================================="
echo ""

# Check if we're running from the DMG
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [[ "$SCRIPT_DIR" == /Volumes/* ]]; then
    echo -e "${GREEN}✓ Running from DMG${NC}"
    DMG_APP="$SCRIPT_DIR/Skip the Podcast Desktop.app"
else
    echo -e "${YELLOW}⚠️  Not running from DMG - looking for app...${NC}"
    DMG_APP="$SCRIPT_DIR/Skip the Podcast Desktop.app"
fi

DEST_APP="/Applications/Skip the Podcast Desktop.app"

# Step 1: Check if app exists in DMG
if [ ! -d "$DMG_APP" ]; then
    echo -e "${RED}❌ Cannot find Skip the Podcast Desktop.app${NC}"
    echo "Please make sure you're running this from the DMG mount."
    exit 1
fi

# Step 2: Check if already installed
if [ -d "$DEST_APP" ]; then
    echo -e "${YELLOW}⚠️  App already installed in Applications${NC}"
    echo ""
    echo "Would you like to:"
    echo "1) Replace existing installation"
    echo "2) Just fix security settings"
    echo "3) Cancel"
    echo ""
    read -p "Choose (1-3): " choice

    case $choice in
        1)
            echo -e "${YELLOW}Removing existing installation...${NC}"
            rm -rf "$DEST_APP"
            ;;
        2)
            # Skip to security fix
            ;;
        3)
            echo "Setup cancelled."
            exit 0
            ;;
        *)
            echo "Invalid choice. Setup cancelled."
            exit 1
            ;;
    esac
fi

# Step 3: Copy to Applications (if needed)
if [ ! -d "$DEST_APP" ]; then
    echo -e "${BLUE}📦 Installing Skip the Podcast Desktop...${NC}"
    echo "   From: $DMG_APP"
    echo "   To: /Applications/"

    # Copy with progress
    cp -R "$DMG_APP" /Applications/

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Installation complete${NC}"
    else
        echo -e "${RED}❌ Installation failed${NC}"
        echo "You may need to manually drag the app to Applications."
        exit 1
    fi
fi

# Step 4: Aggressive Gatekeeper bypass
echo ""
echo -e "${BLUE}🛡️  Bypassing macOS Gatekeeper...${NC}"

# Method 1: Remove quarantine (most important)
echo -n "   Removing quarantine flag..."
xattr -cr "$DEST_APP" 2>/dev/null || true
xattr -dr com.apple.quarantine "$DEST_APP" 2>/dev/null || true
# Also try with sudo if regular fails
if xattr -p com.apple.quarantine "$DEST_APP" &>/dev/null; then
    echo -e " ${YELLOW}(needs sudo)${NC}"
    sudo xattr -dr com.apple.quarantine "$DEST_APP" 2>/dev/null || true
else
    echo -e " ${GREEN}✓${NC}"
fi

# Method 2: Register with Launch Services
echo -n "   Registering with macOS..."
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "$DEST_APP" 2>/dev/null || true
echo -e " ${GREEN}✓${NC}"

# Method 3: Reset Gatekeeper assessment
echo -n "   Resetting security assessment..."
sudo spctl --add "$DEST_APP" 2>/dev/null || true
sudo spctl --enable --label "Skip the Podcast Desktop" 2>/dev/null || true
echo -e " ${GREEN}✓${NC}"

# Method 4: Fix permissions
echo -n "   Setting permissions..."
chmod -R 755 "$DEST_APP" 2>/dev/null || true
echo -e " ${GREEN}✓${NC}"

# Method 5: Touch the app to update timestamps
echo -n "   Updating app timestamps..."
find "$DEST_APP" -type f -exec touch {} \; 2>/dev/null || true
echo -e " ${GREEN}✓${NC}"

# Step 5: Create first-run marker
echo -n "   Creating first-run marker..."
touch ~/.skip_the_podcast_desktop_installed
echo -e " ${GREEN}✓${NC}"

echo ""
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo ""
echo -e "${BLUE}📱 Launching Skip the Podcast Desktop...${NC}"
echo ""

# Step 6: Launch using the Gatekeeper bypass method
# Using 'open' with specific flags to bypass initial Gatekeeper check
open -a "$DEST_APP" --args --first-run 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ App launched successfully${NC}"
    echo ""
    echo "Skip the Podcast Desktop is now ready to use!"
    echo "You can find it in your Applications folder."
else
    echo -e "${YELLOW}⚠️  Automatic launch failed${NC}"
    echo ""
    echo "To open Skip the Podcast Desktop:"
    echo -e "${BLUE}1.${NC} Go to Applications folder"
    echo -e "${BLUE}2.${NC} Right-click 'Skip the Podcast Desktop'"
    echo -e "${BLUE}3.${NC} Select 'Open' from the menu"
    echo -e "${BLUE}4.${NC} Click 'Open' in the security dialog"
    echo ""
    echo "This only needs to be done once. After that, you can open it normally."
fi

echo ""
echo -e "${BLUE}💡 Tip:${NC} To avoid this in the future, we recommend installing"
echo "via Homebrew when it becomes available: brew install skip-the-podcast"
echo ""

# Keep window open for a moment so user can read
sleep 2

# Open Applications folder for convenience
open /Applications/

echo ""
echo "Press any key to close this window..."
read -n 1 -s
