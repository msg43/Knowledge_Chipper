#!/bin/bash
# Fix macOS quarantine issues for Skip the Podcast Desktop

APP_PATH="/Applications/Skip the Podcast Desktop.app"

echo "🔍 Checking Skip the Podcast Desktop app..."

if [ ! -d "$APP_PATH" ]; then
    echo "❌ App not found at: $APP_PATH"
    echo "Please check if the app name is different or located elsewhere"
    exit 1
fi

echo "✅ App found at: $APP_PATH"

# Check current quarantine status
echo ""
echo "🔍 Checking quarantine status..."
xattr -l "$APP_PATH" | grep com.apple.quarantine && echo "⚠️  App is quarantined" || echo "✅ App is not quarantined"

# Remove quarantine recursively
echo ""
echo "🔓 Removing quarantine attributes..."
sudo xattr -dr com.apple.quarantine "$APP_PATH"

# Verify removal
echo ""
echo "🔍 Verifying quarantine removal..."
if xattr -l "$APP_PATH" | grep com.apple.quarantine > /dev/null; then
    echo "❌ Quarantine removal failed"
else
    echo "✅ Quarantine successfully removed"
fi

# Check app bundle structure
echo ""
echo "🔍 Checking app bundle structure..."
if [ -f "$APP_PATH/Contents/Info.plist" ]; then
    echo "✅ Info.plist found"
else
    echo "❌ Info.plist missing - app bundle may be corrupted"
fi

if [ -f "$APP_PATH/Contents/MacOS/Skip the Podcast Desktop" ]; then
    echo "✅ Main executable found"
    # Check if executable is actually executable
    if [ -x "$APP_PATH/Contents/MacOS/Skip the Podcast Desktop" ]; then
        echo "✅ Executable has proper permissions"
    else
        echo "⚠️  Executable lacks execute permissions - fixing..."
        chmod +x "$APP_PATH/Contents/MacOS/Skip the Podcast Desktop"
    fi
else
    echo "❌ Main executable missing"
    echo "Looking for alternative executable names..."
    ls -la "$APP_PATH/Contents/MacOS/"
fi

echo ""
echo "🚀 Try launching the app again from Applications folder"
echo "If it still doesn't work, check Console.app for error messages"
