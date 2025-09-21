#!/bin/bash
# Quick installer for Packages.app

echo "📦 Installing Packages.app"
echo "========================"
echo ""

# Check if already installed
if [ -d "/Applications/Packages.app" ]; then
    echo "✅ Packages.app is already installed!"
    echo ""
    # Install command line tools if needed
    if ! command -v packagesbuild &> /dev/null; then
        echo "Installing command line tools..."
        sudo installer -pkg "/Applications/Packages.app/Contents/Resources/Packages_Command_Line_Tools.pkg" -target /
    fi
    exit 0
fi

# Check if DMG is mounted
if [ -d "/Volumes/Packages 1.2.10" ]; then
    echo "Found mounted Packages installer"
else
    echo "Mounting Packages DMG..."
    hdiutil attach ~/Downloads/Packages.dmg
fi

echo ""
echo "Installing Packages.app (requires admin password)..."
sudo installer -pkg "/Volumes/Packages 1.2.10/Install Packages.pkg" -target /

echo ""
echo "Unmounting installer..."
hdiutil detach "/Volumes/Packages 1.2.10" 2>/dev/null || true

echo ""
echo "✅ Packages.app installed successfully!"
echo ""
echo "Next step: Run ./scripts/build_packages_installer.sh"
