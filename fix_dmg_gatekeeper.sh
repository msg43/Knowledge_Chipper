#!/bin/bash
# Fix Skip the Podcast Desktop Gatekeeper Issues
# Run this script after installing from DMG if the app won't open

echo "🛡️  Skip the Podcast Desktop - Gatekeeper Fix"
echo "============================================"
echo ""

APP_PATH="/Applications/Skip the Podcast Desktop.app"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ App not found at: $APP_PATH"
    echo "Please install Skip the Podcast Desktop first."
    exit 1
fi

echo "This script will fix common macOS security issues that prevent the app from opening."
echo ""
echo "🔐 You'll be asked for your admin password."
echo ""

# 1. Remove quarantine attribute
echo "1️⃣ Removing quarantine attribute..."
sudo xattr -dr com.apple.quarantine "$APP_PATH"
echo "✅ Quarantine removed"
echo ""

# 2. Remove code signature (forces Gatekeeper to treat as unsigned local app)
echo "2️⃣ Removing code signatures..."
sudo codesign --remove-signature "$APP_PATH" 2>/dev/null || true
echo "✅ Signatures removed"
echo ""

# 3. Set proper permissions
echo "3️⃣ Setting permissions..."
sudo chmod -R 755 "$APP_PATH"
sudo chown -R "$USER":admin "$APP_PATH"
echo "✅ Permissions fixed"
echo ""

# 4. Test launch
echo "4️⃣ Testing app launch..."
echo "----------------------------------------"
cd "$APP_PATH/Contents/MacOS"
./launch 2>&1 | head -10 | grep -E "Version|Python|Launching" || echo "Check logs for details"
echo "----------------------------------------"
echo ""

echo "✅ Fixes applied!"
echo ""
echo "🚀 Try launching Skip the Podcast Desktop now:"
echo "   - Double-click the app in Applications"
echo "   - Or right-click → Open → Open"
echo ""
echo "📝 If it still doesn't work:"
echo "   1. Open System Settings → Privacy & Security"
echo "   2. Look for 'Skip the Podcast Desktop was blocked'"
echo "   3. Click 'Open Anyway'"
echo ""
echo "💡 For persistent issues, check:"
echo "   ~/Library/Logs/Skip the Podcast Desktop/knowledge_system.log"
