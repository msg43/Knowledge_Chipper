#!/bin/bash
# Skip the Podcast Desktop - Web Installer
# This installer bypasses Gatekeeper by downloading directly

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Skip the Podcast Desktop - Direct Installer${NC}"
echo "==========================================="
echo ""
echo "This installer will:"
echo "✓ Download Skip the Podcast Desktop"
echo "✓ Install to /Applications"
echo "✓ Configure macOS security settings"
echo "✓ Launch the app"
echo ""

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is required but not installed${NC}"
    exit 1
fi

# Get latest release URL (replace with your actual URL)
DOWNLOAD_URL="https://github.com/skipthepodcast/desktop/releases/latest/download/Skip_the_Podcast_Desktop.dmg"
# For testing, you can use a direct URL:
# DOWNLOAD_URL="https://your-server.com/Skip_the_Podcast_Desktop.zip"

echo -e "${BLUE}📥 Downloading Skip the Podcast Desktop...${NC}"
echo "   This may take a few minutes depending on your connection"
echo ""

# Create temp directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Download with progress bar
if curl -L -# -o "app_download.dmg" "$DOWNLOAD_URL"; then
    echo -e "${GREEN}✓ Download complete${NC}"
else
    echo -e "${RED}❌ Download failed${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Mount DMG
echo -e "${BLUE}📂 Mounting installer...${NC}"
MOUNT_POINT=$(hdiutil attach -nobrowse "app_download.dmg" | grep "/Volumes" | awk -F'\t' '{print $NF}')

if [ -z "$MOUNT_POINT" ]; then
    echo -e "${RED}❌ Failed to mount DMG${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Check if app exists
APP_IN_DMG="$MOUNT_POINT/Skip the Podcast Desktop.app"
if [ ! -d "$APP_IN_DMG" ]; then
    echo -e "${RED}❌ App not found in DMG${NC}"
    hdiutil detach "$MOUNT_POINT" -quiet
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Remove old installation if exists
if [ -d "/Applications/Skip the Podcast Desktop.app" ]; then
    echo -e "${YELLOW}⚠️  Removing previous installation...${NC}"
    rm -rf "/Applications/Skip the Podcast Desktop.app"
fi

# Copy to Applications
echo -e "${BLUE}📋 Installing to Applications...${NC}"
cp -R "$APP_IN_DMG" "/Applications/"

# IMPORTANT: No quarantine attribute because we downloaded via curl!
echo -e "${GREEN}✓ Installed without quarantine!${NC}"

# Unmount DMG
hdiutil detach "$MOUNT_POINT" -quiet

# Register with Launch Services
echo -e "${BLUE}🔧 Registering with macOS...${NC}"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "/Applications/Skip the Podcast Desktop.app" 2>/dev/null || true

# Clean up
rm -rf "$TEMP_DIR"

echo ""
echo -e "${GREEN}✅ Installation Complete!${NC}"
echo ""
echo -e "${BLUE}🚀 Launching Skip the Podcast Desktop...${NC}"

# Launch the app
open -a "Skip the Podcast Desktop" --args --first-run

echo ""
echo "Skip the Podcast Desktop has been installed and launched!"
echo "You can find it in your Applications folder."
echo ""
echo -e "${YELLOW}Note: Since this was installed via direct download,${NC}"
echo -e "${YELLOW}      you won't see any Gatekeeper warnings!${NC}"
