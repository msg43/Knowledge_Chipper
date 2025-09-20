#!/bin/bash
# Replace the broken installed app with the working staging version

STAGING_APP="/Users/matthewgreer/Projects/Knowledge_Chipper/scripts/.app_build/Skip the Podcast Desktop.app"
INSTALLED_APP="/Applications/Skip the Podcast Desktop.app"

echo "🔄 Replacing Broken App with Working Version"
echo "============================================="

if [ ! -d "$STAGING_APP" ]; then
    echo "❌ Staging app not found: $STAGING_APP"
    echo "You may need to rebuild first with: bash scripts/build_macos_app.sh --skip-install"
    exit 1
fi

echo "✅ Staging app found: $STAGING_APP"

# Remove the old broken app
if [ -d "$INSTALLED_APP" ]; then
    echo "🗑️  Removing old app: $INSTALLED_APP"
    sudo rm -rf "$INSTALLED_APP"
else
    echo "ℹ️  No existing app to remove"
fi

# Copy the working staging app
echo "📦 Installing working app..."
sudo cp -R "$STAGING_APP" "/Applications/"

# Fix permissions
echo "🔐 Setting correct permissions..."
sudo chown -R root:wheel "$INSTALLED_APP"
sudo chmod -R 755 "$INSTALLED_APP"

# Remove quarantine
echo "🔓 Removing quarantine attributes..."
sudo xattr -dr com.apple.quarantine "$INSTALLED_APP"

echo ""
echo "✅ App installation complete!"
echo ""
echo "🚀 Try launching 'Skip the Podcast Desktop' from Applications folder"
echo ""
echo "📝 The working version includes:"
echo "   • Proper Python virtual environment"
echo "   • Bundled FFMPEG setup"
echo "   • Bundled model configuration"
echo "   • Updated launch script (44 lines vs old broken version)"
