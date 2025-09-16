#!/bin/bash
# Skip the Podcast Desktop - Smart Installer
# This script installs the app without triggering Gatekeeper

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

clear
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    Skip the Podcast Desktop Installer      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DMG_APP="$SCRIPT_DIR/Skip the Podcast Desktop.app"
DEST_APP="/Applications/Skip the Podcast Desktop.app"

# Check if we're running from DMG
if [[ "$SCRIPT_DIR" != /Volumes/* ]]; then
    echo -e "${RED}❌ This installer must be run from the mounted DMG${NC}"
    echo "Please mount the DMG and run this installer from there."
    read -p "Press any key to exit..."
    exit 1
fi

# Check if app exists in DMG
if [ ! -d "$DMG_APP" ]; then
    echo -e "${RED}❌ Cannot find Skip the Podcast Desktop.app${NC}"
    exit 1
fi

echo -e "${YELLOW}This installer will:${NC}"
echo "  • Copy Skip the Podcast Desktop to Applications"
echo "  • Configure it to bypass security warnings"
echo "  • Launch the app automatically"
echo ""
echo -e "${YELLOW}You'll be asked for your password to complete installation.${NC}"
echo ""
read -p "Press ENTER to continue or Ctrl+C to cancel..."

# Remove existing installation if present
if [ -d "$DEST_APP" ]; then
    echo -e "${YELLOW}Removing previous installation...${NC}"
    sudo rm -rf "$DEST_APP" 2>/dev/null || {
        echo -e "${RED}Failed to remove existing app. Please delete it manually.${NC}"
        exit 1
    }
fi

# Install with sudo to bypass quarantine
echo -e "${BLUE}Installing Skip the Podcast Desktop...${NC}"
echo "Please enter your password when prompted:"

# Use sudo to copy WITHOUT quarantine attribute
sudo bash -c "
    # Copy app without extended attributes
    cp -R '$DMG_APP' '$DEST_APP'

    # Remove ALL extended attributes (including quarantine)
    xattr -cr '$DEST_APP'

    # Set proper ownership
    chown -R $USER:admin '$DEST_APP'

    # Make executable
    chmod -R 755 '$DEST_APP'

    # Add to Gatekeeper whitelist
    spctl --add '$DEST_APP' 2>/dev/null || true

    # Force LaunchServices to recognize the app
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f '$DEST_APP' 2>/dev/null || true
"

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Installation Complete!${NC}"
    echo ""

    # Create marker that we've done a clean install
    touch ~/.skip_podcast_clean_install

    echo -e "${BLUE}Launching Skip the Podcast Desktop...${NC}"

    # Launch the app using open (which won't apply quarantine)
    open -n "$DEST_APP" 2>/dev/null &

    echo ""
    echo -e "${GREEN}Skip the Podcast Desktop is now installed and running!${NC}"
    echo "You can find it in your Applications folder."
    echo ""

    # Eject the DMG
    echo "Ejecting installer disk..."
    sleep 2
    diskutil eject "$SCRIPT_DIR" 2>/dev/null || true

else
    echo -e "${RED}❌ Installation failed${NC}"
    echo "Please try dragging the app to Applications manually."
    exit 1
fi

echo "This window will close in 5 seconds..."
sleep 5
