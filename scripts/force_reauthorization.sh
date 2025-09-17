#!/bin/bash
# Force re-authorization for Skip the Podcast Desktop
# Use this to test the authorization flow

set -e

echo "🔐 Force Re-authorization Tool for Skip the Podcast Desktop"
echo "=========================================================="
echo ""

APP_PATH="/Applications/Skip the Podcast Desktop.app"

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "❌ App not found at: $APP_PATH"
    echo "Please install the app first."
    exit 1
fi

echo "📍 Found app at: $APP_PATH"
echo ""

# Show current authorization status
echo "🔍 Current Authorization Status:"
echo "================================"

# Check for authorization marker
if [ -f "$HOME/.skip_the_podcast_desktop_authorized" ]; then
    echo "✅ Authorization marker exists: $HOME/.skip_the_podcast_desktop_authorized"
    echo "   Created: $(stat -f '%Sm' "$HOME/.skip_the_podcast_desktop_authorized")"
else
    echo "❌ No authorization marker found"
fi

# Check for quarantine attribute
if xattr -p com.apple.quarantine "$APP_PATH" &>/dev/null; then
    echo "⚠️  App has quarantine attribute (will trigger Gatekeeper)"
    quarantine_info=$(xattr -p com.apple.quarantine "$APP_PATH")
    echo "   Quarantine info: $quarantine_info"
else
    echo "ℹ️  App does NOT have quarantine attribute"
fi

# Check if app is properly signed
echo ""
echo "🔒 Code Signing Status:"
codesign_output=$(codesign -dv "$APP_PATH" 2>&1 || echo "Not signed")
echo "   $codesign_output"

echo ""
echo "========================="
echo ""

# Offer to force re-authorization
read -p "Do you want to force re-authorization? This will remove the auth marker and add quarantine if needed. (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔄 Forcing re-authorization..."

    # Remove authorization marker
    if [ -f "$HOME/.skip_the_podcast_desktop_authorized" ]; then
        rm -f "$HOME/.skip_the_podcast_desktop_authorized"
        echo "✅ Removed authorization marker"
    fi

    # Add quarantine attribute if it doesn't exist
    if ! xattr -p com.apple.quarantine "$APP_PATH" &>/dev/null; then
        echo "🏷️  Adding quarantine attribute to trigger Gatekeeper..."
        xattr -w com.apple.quarantine "0083;$(date +%s);Safari;|com.apple.Safari" "$APP_PATH"
        echo "✅ Quarantine attribute added"
    fi

    echo ""
    echo "🚀 Now opening the app - you should see the authorization dialog..."
    echo ""
    echo "Expected flow:"
    echo "1. Professional authorization dialog appears"
    echo "2. You click 'Authorize'"
    echo "3. macOS password prompt appears"
    echo "4. App gets authorized and asks you to reopen"
    echo "5. Next launch should be seamless"
    echo ""

    # Wait a moment then open the app
    sleep 2
    open "$APP_PATH"

    echo "🔍 Monitor the logs at:"
    echo "   ~/Library/Logs/Skip the Podcast Desktop/knowledge_system.log"

else
    echo ""
    echo "❌ Re-authorization cancelled"
    echo ""
    echo "💡 To manually test authorization:"
    echo "   1. Remove auth marker: rm ~/.skip_the_podcast_desktop_authorized"
    echo "   2. Add quarantine: xattr -w com.apple.quarantine \"0083;$(date +%s);Safari;|com.apple.Safari\" \"$APP_PATH\""
    echo "   3. Open app: open \"$APP_PATH\""
fi

echo ""
echo "📋 Troubleshooting:"
echo "==================="
echo "• If no dialog appears: Check that authorization marker was removed"
echo "• If 'Move to Trash' appears: App needs proper signing or manual right-click → Open"
echo "• Check logs: ~/Library/Logs/Skip the Podcast Desktop/knowledge_system.log"
echo "• Verify launch script: $APP_PATH/Contents/MacOS/launch"
