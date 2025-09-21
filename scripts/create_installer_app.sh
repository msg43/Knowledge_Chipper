#!/bin/bash
# create_installer_app.sh - Create a single-click installer app

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_installer_app"
DIST_DIR="$PROJECT_ROOT/dist"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}🔧 Creating Single-Click Installer App${NC}"
echo "========================================"
echo "This creates a standalone installer app that prompts for password"
echo ""

# Print status functions
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

# Clean build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Find the latest PKG
PKG_FILE="$DIST_DIR/Skip_the_Podcast_Desktop-${VERSION}.pkg"
if [ ! -f "$PKG_FILE" ]; then
    print_error "PKG file not found: $PKG_FILE"
    echo "Please run ./scripts/build_pkg_installer.sh first"
    exit 1
fi

# Create the app bundle
echo -e "\n${BLUE}🏗️ Creating installer app bundle...${NC}"
APP_NAME="Skip the Podcast Desktop Installer"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Copy PKG into the app bundle
cp "$PKG_FILE" "$RESOURCES_DIR/installer.pkg"

# Create Info.plist
cat > "$CONTENTS_DIR/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>installer</string>
    <key>CFBundleIdentifier</key>
    <string>com.knowledgechipper.installer</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>Skip the Podcast Desktop Installer</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
EOF

# Create the installer executable
cat > "$MACOS_DIR/installer" << 'EOF'
#!/bin/bash
# Single-click installer that forces authentication

# Get the path to our resources
RESOURCES_DIR="$(dirname "$0")/../Resources"
PKG_PATH="$RESOURCES_DIR/installer.pkg"

# Use AppleScript to run the installer with admin privileges
osascript << 'EOA'
    -- Get the installer package path
    set pkgPath to (POSIX path of (path to me)) & "Contents/Resources/installer.pkg"

    try
        -- Show installation dialog
        set dialogResult to display dialog "Skip the Podcast Desktop Installer" & return & return & ¬
            "This will install Skip the Podcast Desktop to your Applications folder." & return & return & ¬
            "Administrator privileges are required for installation." & return & ¬
            "You will be prompted for your password." ¬
            buttons {"Cancel", "Install"} default button "Install" ¬
            with title "Skip the Podcast Desktop" ¬
            with icon POSIX file ((POSIX path of (path to me)) & "Contents/Resources/AppIcon.icns")

        if button returned of dialogResult is "Install" then
            -- Show progress
            display notification "Starting installation..." with title "Skip the Podcast Desktop"

            -- Run installer with administrator privileges
            set installCmd to "installer -pkg " & quoted form of pkgPath & " -target /"
            do shell script installCmd with administrator privileges

            -- Success
            display notification "Installation complete!" with title "Skip the Podcast Desktop"

            -- Ask to launch
            set launchResult to display dialog "Installation complete!" & return & return & ¬
                "Skip the Podcast Desktop has been installed successfully." ¬
                buttons {"Launch App", "Done"} default button "Done" ¬
                with title "Skip the Podcast Desktop" ¬
                with icon note

            if button returned of launchResult is "Launch App" then
                tell application "Skip the Podcast Desktop" to activate
            end if
        end if

    on error errMsg number errNum
        if errNum is not -128 then -- -128 is user cancelled
            display dialog "Installation failed:" & return & return & errMsg ¬
                buttons {"OK"} default button "OK" ¬
                with title "Installation Error" ¬
                with icon stop
        end if
    end try

    -- Quit the installer app
    tell application "System Events"
        set myName to name of (path to me)
        tell application myName to quit
    end tell
EOA
EOF

chmod +x "$MACOS_DIR/installer"

# Create/convert icon
echo -e "\n${BLUE}🎨 Creating app icon...${NC}"
# Try STP_Icon_1.png first (better size), fall back to chipper.png
ICON_FILE=""
if [ -f "$PROJECT_ROOT/Assets/STP_Icon_1.png" ]; then
    ICON_FILE="$PROJECT_ROOT/Assets/STP_Icon_1.png"
elif [ -f "$PROJECT_ROOT/Assets/chipper.png" ]; then
    ICON_FILE="$PROJECT_ROOT/Assets/chipper.png"
fi

if [ -n "$ICON_FILE" ]; then
    # Create icon set
    ICONSET="$BUILD_DIR/AppIcon.iconset"
    mkdir -p "$ICONSET"

    # Use sips to create different sizes
    sips -z 16 16     "$ICON_FILE" --out "$ICONSET/icon_16x16.png"      >/dev/null 2>&1
    sips -z 32 32     "$ICON_FILE" --out "$ICONSET/icon_16x16@2x.png"   >/dev/null 2>&1
    sips -z 32 32     "$ICON_FILE" --out "$ICONSET/icon_32x32.png"      >/dev/null 2>&1
    sips -z 64 64     "$ICON_FILE" --out "$ICONSET/icon_32x32@2x.png"   >/dev/null 2>&1
    sips -z 128 128   "$ICON_FILE" --out "$ICONSET/icon_128x128.png"    >/dev/null 2>&1
    sips -z 256 256   "$ICON_FILE" --out "$ICONSET/icon_128x128@2x.png" >/dev/null 2>&1
    sips -z 256 256   "$ICON_FILE" --out "$ICONSET/icon_256x256.png"    >/dev/null 2>&1
    sips -z 512 512   "$ICON_FILE" --out "$ICONSET/icon_256x256@2x.png" >/dev/null 2>&1
    sips -z 512 512   "$ICON_FILE" --out "$ICONSET/icon_512x512.png"    >/dev/null 2>&1
    sips -z 1024 1024 "$ICON_FILE" --out "$ICONSET/icon_512x512@2x.png" >/dev/null 2>&1

    # Convert to icns
    iconutil -c icns "$ICONSET" -o "$RESOURCES_DIR/AppIcon.icns" 2>/dev/null || {
        echo -e "${YELLOW}Warning: iconutil failed, trying alternative method${NC}"
        # If iconutil fails, try copying the PNG and let macOS handle it
        sips -z 512 512 "$ICON_FILE" --out "$RESOURCES_DIR/AppIcon.png" >/dev/null 2>&1
    }
    rm -rf "$ICONSET"

    print_status "App icon created from $(basename "$ICON_FILE")"
else
    print_error "No icon file found in Assets directory"
fi

print_status "Installer app created"

# Create DMG with just the installer app
echo -e "\n${BLUE}📀 Creating DMG...${NC}"
DMG_TEMP="$BUILD_DIR/temp.dmg"
DMG_NAME="Skip_the_Podcast_Desktop-${VERSION}-Installer.dmg"
DMG_PATH="$DIST_DIR/$DMG_NAME"

# Create a folder for DMG contents
DMG_CONTENTS="$BUILD_DIR/dmg_contents"
mkdir -p "$DMG_CONTENTS"
cp -R "$APP_BUNDLE" "$DMG_CONTENTS/"

# Create a symbolic link to Applications
ln -s /Applications "$DMG_CONTENTS/Applications"

# Create DMG
hdiutil create -volname "Skip the Podcast Desktop" \
               -srcfolder "$DMG_CONTENTS" \
               -ov -format UDZO \
               "$DMG_PATH" >/dev/null 2>&1

# Clean up
rm -rf "$BUILD_DIR"

# Create checksum
shasum -a 256 "$DMG_PATH" | awk '{print $1}' > "$DMG_PATH.sha256"

print_status "DMG created successfully"

echo ""
echo -e "${GREEN}${BOLD}🎉 Installer App Created!${NC}"
echo "=============================================="
echo "DMG: $DMG_PATH"
echo "Size: $(du -h "$DMG_PATH" | cut -f1)"
echo ""
echo "Features:"
echo "• Single installer app - no extra files"
echo "• Custom app icon from your Assets"
echo "• Double-click to install (opens DMG → drag to Applications → run)"
echo "• Always prompts for administrator password"
echo "• Clean, professional installation experience"
echo ""
echo "Users should:"
echo "1. Download and open the DMG"
echo "2. Drag the installer to Applications (or run from DMG)"
echo "3. Double-click to start installation"
echo "4. Enter administrator password when prompted"
echo ""
