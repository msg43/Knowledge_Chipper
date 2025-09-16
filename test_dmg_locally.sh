#!/bin/bash
# Test the DMG locally to simulate third-party machine experience

echo "🧪 Testing DMG Installation Locally"
echo "==================================="
echo "This simulates what happens on a third-party machine"
echo ""

DMG_PATH="$HOME/Projects/Knowledge_Chipper/dist/Skip_the_Podcast_Desktop-3.2.8.dmg"
TEST_APP="/Applications/Skip the Podcast Desktop.app"

# 1. Remove existing app if present
if [ -d "$TEST_APP" ]; then
    echo "🗑️  Removing existing app..."
    sudo rm -rf "$TEST_APP"
fi

# 2. Mount the DMG
echo "📦 Mounting DMG..."
hdiutil attach "$DMG_PATH" -quiet
MOUNT_POINT=$(mount | grep "Skip the Podcast" | awk '{print $3}')

if [ -z "$MOUNT_POINT" ]; then
    echo "❌ Failed to mount DMG"
    exit 1
fi

echo "✅ DMG mounted at: $MOUNT_POINT"

# 3. Copy app to Applications (this triggers Gatekeeper)
echo "📋 Copying app to Applications..."
sudo cp -R "$MOUNT_POINT/Skip the Podcast Desktop.app" /Applications/

# 4. Unmount DMG
echo "💿 Unmounting DMG..."
hdiutil detach "$MOUNT_POINT" -quiet

# 5. Apply quarantine attribute (simulates download)
echo "🔒 Applying quarantine attribute (simulating download)..."
sudo xattr -w com.apple.quarantine "0081;00000000;Safari;|com.apple.Safari" "$TEST_APP"

# 6. Check quarantine status
echo ""
echo "📊 Quarantine Status:"
xattr -l "$TEST_APP" | grep quarantine || echo "No quarantine attribute"

# 7. Try to launch the app
echo ""
echo "🚀 Attempting to launch app..."
echo "----------------------------------------"

# First, try opening with open command (simulates double-click)
echo "Method 1: Using 'open' command (simulates double-click):"
if open "$TEST_APP" 2>&1; then
    echo "✅ App opened successfully"
    sleep 3
    # Check if process is running
    if pgrep -f "Skip the Podcast" >/dev/null; then
        echo "✅ App is running"
        pkill -f "Skip the Podcast"
    else
        echo "❌ App opened but immediately closed"
    fi
else
    echo "❌ Failed to open with 'open' command"
fi

echo ""
echo "Method 2: Direct launch from terminal:"
cd "$TEST_APP/Contents/MacOS"
./launch 2>&1 | head -20

echo ""
echo "----------------------------------------"
echo "🛡️  Gatekeeper Solutions:"
echo ""
echo "1. Remove quarantine (requires admin password):"
echo "   sudo xattr -dr com.apple.quarantine '$TEST_APP'"
echo ""
echo "2. Allow in System Settings:"
echo "   System Settings > Privacy & Security > Allow app"
echo ""
echo "3. Right-click method:"
echo "   Right-click app > Open > Open (bypasses Gatekeeper)"
echo ""
echo "4. Sign the app (developer solution):"
echo "   codesign --force --deep --sign - '$TEST_APP'"
