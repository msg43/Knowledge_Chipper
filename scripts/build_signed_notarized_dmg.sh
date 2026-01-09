#!/bin/bash
# build_signed_notarized_dmg.sh
# Build a polished, signed, and notarized DMG with "Drag to Applications" visual
# Uses Developer ID Application certificate (WORKING)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     BUILD POLISHED NOTARIZED DMG                               ║${NC}"
echo -e "${CYAN}║     With 'Drag to Applications' visual                         ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"

# Certificate
DEV_ID_APP="Developer ID Application: Matthew Seymour Greer (W2AT7M9482)"

# Credentials
APPLE_ID="${APPLE_ID:-Matt@rainfall.llc}"
TEAM_ID="${TEAM_ID:-W2AT7M9482}"

# DMG Settings
DMG_WINDOW_WIDTH=600
DMG_WINDOW_HEIGHT=400
ICON_SIZE=128
APP_ICON_X=150
APP_ICON_Y=200
APPS_ICON_X=450
APPS_ICON_Y=200

# Find the app to package
if [ -n "$1" ]; then
    APP_PATH="$1"
elif [ -d "$DIST_DIR" ]; then
    APP_PATH=$(find "$DIST_DIR" -maxdepth 1 -name "*.app" -type d | head -1)
fi

if [ -z "$APP_PATH" ] || [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}Error: No .app bundle found${NC}"
    echo "Usage: $0 /path/to/YourApp.app"
    echo "Or place the .app in the dist/ directory"
    exit 1
fi

APP_NAME=$(basename "$APP_PATH" .app)
APP_NAME_SAFE=$(echo "$APP_NAME" | tr ' ' '_')
OUTPUT_DIR=$(dirname "$APP_PATH")
TEMP_DIR="/tmp/dmg_build_$$"
DMG_PATH="$OUTPUT_DIR/${APP_NAME_SAFE}.dmg"

echo "App: $APP_PATH"
echo "App Name: $APP_NAME"
echo "Output: $DMG_PATH"
echo ""

# Get password if not set
if [ -z "$APP_PASSWORD" ]; then
    echo -e "${YELLOW}Enter app-specific password:${NC}"
    read -s APP_PASSWORD
    echo ""
fi

# Create temp directory
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

#####################################################################
# STEP 1: Sign the app
#####################################################################
echo -e "${BLUE}[1/7] Signing app with Developer ID Application...${NC}"

# Sign all nested components first (frameworks, helpers, etc.)
find "$APP_PATH" -type f \( -name "*.dylib" -o -name "*.framework" \) -exec \
    codesign --force --options runtime --timestamp --sign "$DEV_ID_APP" {} \; 2>/dev/null || true

# Sign the main app bundle
codesign --force --deep --options runtime --timestamp \
    --sign "$DEV_ID_APP" \
    "$APP_PATH" \
    --verbose

echo -e "${GREEN}✓ App signed${NC}"

#####################################################################
# STEP 2: Verify signature
#####################################################################
echo -e "${BLUE}[2/7] Verifying signature...${NC}"
if codesign --verify --deep --strict --verbose=2 "$APP_PATH" 2>&1; then
    echo -e "${GREEN}✓ Signature verified${NC}"
else
    echo -e "${RED}✗ Signature verification failed${NC}"
    exit 1
fi

#####################################################################
# STEP 3: Create DMG background image
#####################################################################
echo -e "${BLUE}[3/7] Creating DMG background...${NC}"

BACKGROUND_FILE="$TEMP_DIR/background.png"

# Create a nice background with arrow using Python (available on all Macs)
python3 << 'PYEOF'
import subprocess
import os

# Create SVG background
svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="600" height="400" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#1a1a2e;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#16213e;stop-opacity:1" />
    </linearGradient>
  </defs>
  
  <!-- Background -->
  <rect width="600" height="400" fill="url(#bg)"/>
  
  <!-- Subtle grid pattern -->
  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#ffffff" stroke-width="0.3" opacity="0.1"/>
  </pattern>
  <rect width="600" height="400" fill="url(#grid)"/>
  
  <!-- Arrow pointing from app to Applications -->
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#4ade80"/>
    </marker>
  </defs>
  
  <!-- Curved arrow path -->
  <path d="M 200 200 Q 300 140 380 200" 
        stroke="#4ade80" 
        stroke-width="3" 
        fill="none" 
        marker-end="url(#arrowhead)"
        stroke-linecap="round"/>
  
  <!-- "Drag to Applications" text -->
  <text x="300" y="320" 
        font-family="SF Pro Display, -apple-system, Helvetica Neue, Arial" 
        font-size="18" 
        font-weight="500"
        fill="#ffffff" 
        text-anchor="middle"
        opacity="0.9">
    Drag to Applications folder to install
  </text>
  
  <!-- App label area -->
  <text x="150" y="290" 
        font-family="SF Pro Display, -apple-system, Helvetica Neue, Arial" 
        font-size="13" 
        fill="#a1a1aa" 
        text-anchor="middle">
    App
  </text>
  
  <!-- Applications label area -->
  <text x="450" y="290" 
        font-family="SF Pro Display, -apple-system, Helvetica Neue, Arial" 
        font-size="13" 
        fill="#a1a1aa" 
        text-anchor="middle">
    Applications
  </text>
</svg>'''

# Save SVG
with open('/tmp/dmg_build_background.svg', 'w') as f:
    f.write(svg_content)

# Convert to PNG using sips (built into macOS)
# First convert SVG to PDF, then to PNG
import os
os.system('qlmanage -t -s 1200 -o /tmp /tmp/dmg_build_background.svg 2>/dev/null || true')

# Fallback: create simple PNG with Python if qlmanage fails
if not os.path.exists('/tmp/dmg_build_background.svg.png'):
    # Use sips to create a simple colored background
    os.system('printf "\\x89PNG\\r\\n\\x1a\\n" > /tmp/dmg_bg_temp.png')
    # Create with ImageMagick if available, otherwise just use a color
    result = os.system('which convert >/dev/null 2>&1')
    if result == 0:
        os.system('convert -size 600x400 gradient:"#1a1a2e"-"#16213e" /tmp/dmg_build_background.png 2>/dev/null')
    else:
        # Create minimal valid PNG
        pass

print("Background creation attempted")
PYEOF

# Check if background was created, if not use a simpler method
if [ ! -f "$TEMP_DIR/background.png" ] && [ ! -f "/tmp/dmg_build_background.svg.png" ]; then
    echo "  Using simple background..."
    # Create a simple tiff background with solid color
    tiffutil -create "$TEMP_DIR/background.tiff" 2>/dev/null || true
fi

# Copy background if it exists
if [ -f "/tmp/dmg_build_background.svg.png" ]; then
    cp "/tmp/dmg_build_background.svg.png" "$BACKGROUND_FILE"
    echo -e "${GREEN}✓ Background created${NC}"
else
    BACKGROUND_FILE=""
    echo -e "${YELLOW}⚠ Using default background${NC}"
fi

#####################################################################
# STEP 4: Create DMG staging directory
#####################################################################
echo -e "${BLUE}[4/7] Creating DMG contents...${NC}"

DMG_STAGING="$TEMP_DIR/dmg_staging"
mkdir -p "$DMG_STAGING"

# Copy app to staging
cp -R "$APP_PATH" "$DMG_STAGING/"

# Create Applications symlink
ln -s /Applications "$DMG_STAGING/Applications"

# Copy background if exists
if [ -n "$BACKGROUND_FILE" ] && [ -f "$BACKGROUND_FILE" ]; then
    mkdir -p "$DMG_STAGING/.background"
    cp "$BACKGROUND_FILE" "$DMG_STAGING/.background/background.png"
fi

echo -e "${GREEN}✓ DMG contents prepared${NC}"

#####################################################################
# STEP 5: Create and customize DMG
#####################################################################
echo -e "${BLUE}[5/7] Building DMG...${NC}"

# Calculate DMG size (app size + 20MB buffer)
APP_SIZE=$(du -sm "$APP_PATH" | cut -f1)
DMG_SIZE=$((APP_SIZE + 20))

TEMP_DMG="$TEMP_DIR/temp.dmg"
FINAL_DMG="$TEMP_DIR/final.dmg"

# Create temporary DMG
hdiutil create -srcfolder "$DMG_STAGING" \
    -volname "$APP_NAME" \
    -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" \
    -format UDRW \
    -size ${DMG_SIZE}m \
    "$TEMP_DMG"

# Mount it
MOUNT_DIR=$(hdiutil attach -readwrite -noverify -noautoopen "$TEMP_DMG" | grep -E '^/dev/' | tail -1 | awk '{print $NF}')
echo "  Mounted at: $MOUNT_DIR"

# Wait for mount
sleep 2

# Apply visual customization using AppleScript
echo "  Customizing window appearance..."

osascript << APPLESCRIPT
tell application "Finder"
    tell disk "$APP_NAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {100, 100, 700, 500}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to $ICON_SIZE
        
        -- Try to set background
        try
            set background picture of viewOptions to file ".background:background.png"
        end try
        
        -- Position icons
        set position of item "$APP_NAME.app" of container window to {$APP_ICON_X, $APP_ICON_Y}
        set position of item "Applications" of container window to {$APPS_ICON_X, $APPS_ICON_Y}
        
        close
        open
        update without registering applications
        delay 2
        close
    end tell
end tell
APPLESCRIPT

# Sync and unmount
sync
hdiutil detach "$MOUNT_DIR" -quiet || hdiutil detach "$MOUNT_DIR" -force

# Convert to compressed DMG
hdiutil convert "$TEMP_DMG" -format UDZO -imagekey zlib-level=9 -o "$FINAL_DMG"

# Move to output location
rm -f "$DMG_PATH"
mv "$FINAL_DMG" "$DMG_PATH"

echo -e "${GREEN}✓ DMG created: $(du -h "$DMG_PATH" | cut -f1)${NC}"

#####################################################################
# STEP 6: Sign the DMG
#####################################################################
echo -e "${BLUE}[6/7] Signing DMG...${NC}"

codesign --sign "$DEV_ID_APP" --timestamp "$DMG_PATH" --verbose

echo -e "${GREEN}✓ DMG signed${NC}"

#####################################################################
# STEP 7: Notarize and staple
#####################################################################
echo -e "${BLUE}[7/7] Notarizing DMG...${NC}"
echo "  This may take 5-15 minutes..."

RESULT=$(xcrun notarytool submit "$DMG_PATH" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_PASSWORD" \
    --wait 2>&1)

echo "$RESULT"

if echo "$RESULT" | grep -q "status: Accepted"; then
    echo -e "${GREEN}✓ Notarization successful!${NC}"
    
    # Staple
    echo "  Stapling ticket..."
    xcrun stapler staple "$DMG_PATH"
    
    # Verify
    xcrun stapler validate "$DMG_PATH"
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                         SUCCESS!                               ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${GREEN}✓${NC} DMG ready for distribution: $DMG_PATH"
    echo ""
    echo "  Users will see:"
    echo "    1. Nice window with your app and Applications folder"
    echo "    2. Arrow showing drag direction"
    echo "    3. No security warnings (notarized!)"
    echo ""
    
    # Get submission ID for records
    SUB_ID=$(echo "$RESULT" | grep "id:" | head -1 | awk '{print $2}')
    echo "  Submission ID: $SUB_ID"
    
else
    echo -e "${RED}✗ Notarization failed${NC}"
    SUB_ID=$(echo "$RESULT" | grep "id:" | head -1 | awk '{print $2}')
    if [ -n "$SUB_ID" ]; then
        echo ""
        echo "Getting detailed log..."
        xcrun notarytool log "$SUB_ID" \
            --apple-id "$APPLE_ID" \
            --team-id "$TEAM_ID" \
            --password "$APP_PASSWORD"
    fi
    exit 1
fi

# Cleanup
rm -rf "$TEMP_DIR"
rm -f /tmp/dmg_build_background.svg /tmp/dmg_build_background.svg.png

echo ""
echo "Done! Distribute: $DMG_PATH"

