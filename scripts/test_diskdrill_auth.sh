#!/bin/bash
# Test the Disk Drill-style authorization

echo "Testing Disk Drill-style Gatekeeper authorization..."
echo ""

# Simulate quarantine on test app
TEST_APP="/Applications/Skip the Podcast Desktop.app"

if [ ! -d "$TEST_APP" ]; then
    echo "❌ App not found at: $TEST_APP"
    echo "Please install the app first"
    exit 1
fi

echo "Current quarantine status:"
if xattr -p com.apple.quarantine "$TEST_APP" 2>/dev/null; then
    echo "✅ App has quarantine attribute (will trigger Gatekeeper)"
else
    echo "❌ App does NOT have quarantine attribute"
    echo ""
    echo "Adding quarantine to simulate download..."
    xattr -w com.apple.quarantine "0083;00000000;Safari;|com.apple.Safari" "$TEST_APP"
    echo "✅ Quarantine added"
fi

echo ""
echo "Removing authorization marker to test fresh..."
rm -f ~/.skip_the_podcast_desktop_authorized

echo ""
echo "Now try to open the app. You should see:"
echo "1. A professional authorization dialog (like Disk Drill)"
echo "2. A password prompt"
echo "3. Automatic fix of Gatekeeper restrictions"
echo "4. App opens without 'Move to Trash' warning"
echo ""
echo "Opening app..."
open "$TEST_APP"
