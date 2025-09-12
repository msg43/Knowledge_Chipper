#!/bin/bash
# Debug launcher for Skip the Podcast Desktop DMG

APP_PATH="/Applications/Skip the Podcast Desktop.app"
EXECUTABLE="$APP_PATH/Contents/MacOS/Skip the Podcast Desktop"

echo "🔍 Debug Launch for Skip the Podcast Desktop"
echo "=============================================="

if [ ! -d "$APP_PATH" ]; then
    echo "❌ App not found at: $APP_PATH"
    echo ""
    echo "Searching for the app in Applications..."
    find /Applications -name "*Skip*" -o -name "*Podcast*" -o -name "*Knowledge*" 2>/dev/null | head -10
    exit 1
fi

echo "✅ App found at: $APP_PATH"

# Check executable
if [ ! -f "$EXECUTABLE" ]; then
    echo "❌ Executable not found at: $EXECUTABLE"
    echo ""
    echo "Available executables in MacOS folder:"
    ls -la "$APP_PATH/Contents/MacOS/"

    # Try to find the actual executable
    ACTUAL_EXECUTABLE=$(find "$APP_PATH/Contents/MacOS" -type f -perm +111 | head -1)
    if [ -n "$ACTUAL_EXECUTABLE" ]; then
        echo ""
        echo "🔄 Found alternative executable: $ACTUAL_EXECUTABLE"
        EXECUTABLE="$ACTUAL_EXECUTABLE"
    else
        echo "❌ No executable files found in app bundle"
        exit 1
    fi
fi

echo "✅ Executable found: $EXECUTABLE"

# Check permissions
if [ ! -x "$EXECUTABLE" ]; then
    echo "⚠️  Executable lacks execute permissions - fixing..."
    chmod +x "$EXECUTABLE"
fi

echo ""
echo "🚀 Attempting to launch with debug output..."
echo "Press Ctrl+C to stop if it hangs"
echo ""

# Set environment variables for debugging
export DYLD_PRINT_LIBRARIES=1
export DYLD_PRINT_STATISTICS=1

# Launch with full debug output
cd "$APP_PATH/Contents/MacOS"
"$EXECUTABLE" 2>&1 | tee /tmp/skip_podcast_debug.log

echo ""
echo "📝 Debug output saved to: /tmp/skip_podcast_debug.log"
echo "Share this log if you need further assistance"
